import hmac
import time
import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from ..core.agent import DailyAgent
from ..persistence.models import Run, Signal, Report, BinarySignal
from ..core.config import settings
from ..core.logger import get_logger
from ..notifications.whatsapp_agent import WhatsAppAgent
import MetaTrader5 as mt5

logger = get_logger("API")
app = FastAPI(title="DailyAgent 2.0 API")
agent = DailyAgent()
whatsapp_agent = WhatsAppAgent(agent=agent)

# Referencia de tasks em background (evita garbage collection)
_background_tasks: set = set()


# ==========================================
# RATE LIMITER
# ==========================================

class RateLimiter:
    """Sliding window rate limiter in-memory por chat_id."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, chat_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if chat_id in self._requests:
            self._requests[chat_id] = [t for t in self._requests[chat_id] if t > cutoff]
        else:
            self._requests[chat_id] = []

        if len(self._requests[chat_id]) >= self.max_requests:
            return False

        self._requests[chat_id].append(now)
        return True

    def get_retry_after(self, chat_id: str) -> int:
        if chat_id not in self._requests or not self._requests[chat_id]:
            return 0
        oldest = self._requests[chat_id][0]
        remaining = self.window_seconds - (time.monotonic() - oldest)
        return max(1, int(remaining))


rate_limiter = RateLimiter(
    max_requests=settings.whatsapp_config.rate_limit_max_requests,
    window_seconds=settings.whatsapp_config.rate_limit_window_seconds
)


# ==========================================
# WEBHOOK HELPERS
# ==========================================

def _verify_webhook_token(request: Request) -> bool:
    """Valida token do webhook WAHA. Retorna True se valido ou se auth esta desabilitada."""
    expected_token = settings.waha.webhook_token
    if not expected_token:
        return True

    received_token = request.headers.get("X-Waha-Webhook-Token", "")
    return hmac.compare_digest(expected_token, received_token)


async def _safe_handle_message(body: str, chat_id: str):
    """Wrapper seguro para handle_message com error handling."""
    try:
        await whatsapp_agent.handle_message(body, chat_id)
    except Exception as e:
        logger.error(f"Erro no background task para {chat_id}: {e}", exc_info=True)
        try:
            await whatsapp_agent.send_message(
                "Ocorreu um erro interno. Tente novamente em alguns instantes.",
                chat_id
            )
        except Exception:
            logger.error(f"Falha ao enviar mensagem de erro para {chat_id}", exc_info=True)


# ==========================================
# STARTUP
# ==========================================

@app.on_event("startup")
async def startup_event():
    if not settings.waha.webhook_token:
        logger.warning(
            "WAHA webhook_token nao configurado. "
            "Webhook aceita requisicoes sem autenticacao. "
            "Configure 'webhook_token' em config.json > waha para proteger o endpoint."
        )


# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/health")
def health_check():
    return {"status": "healthy", "mt5_connected": mt5.terminal_info() is not None}


@app.post("/run-agent")
async def run_agent(symbol: str, timeframe: str = "H1"):
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1
    }
    selected_tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_H1)
    result = agent.run_for_symbol(symbol, selected_tf)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/waha/webhook")
async def waha_webhook(request: Request):
    """
    Webhook do WAHA - Recebe mensagens do WhatsApp e processa via WhatsAppAgent.

    Inclui autenticacao por token, rate limiting por chat_id, e
    error handling robusto para background tasks.
    """
    # 1. Autenticacao
    if not _verify_webhook_token(request):
        logger.warning(f"Webhook rejeitado: token invalido de {request.client.host}")
        raise HTTPException(status_code=403, detail="Forbidden")

    # 2. Parse do payload
    try:
        data = await request.json()
        logger.info(f"Recebido webhook do WAHA: {data.get('event')}")
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        return {"status": "error", "detail": "Invalid request"}

    # 3. Processa apenas mensagens recebidas
    event = data.get("event", "")
    if event not in ("message", "message.any", "message.created"):
        return {"status": "ignored"}

    message = data.get("payload", {})

    # Ignora mensagens enviadas por nos mesmos
    if message.get("fromMe"):
        return {"status": "ignored"}

    body = message.get("body", "").strip()
    chat_id = message.get("from")

    # Corrige formato LID (Linked ID) que WAHA WEBJS nao suporta para envio
    # Formato LID: "68139857490159@lid@c.us" -> usa chatId ou fallback para recipient
    if chat_id and "@lid" in chat_id:
        # Tenta usar o chatId do payload (pode ter formato correto)
        alt_chat_id = message.get("chatId", "")
        if alt_chat_id and "@lid" not in alt_chat_id:
            chat_id = alt_chat_id
            logger.info(f"LID detectado, usando chatId alternativo: {chat_id}")
        elif settings.waha.recipient_phone:
            chat_id = f"{settings.waha.recipient_phone}@c.us"
            logger.info(f"LID detectado, usando recipient configurado: {chat_id}")

    if not body or not chat_id:
        return {"status": "ignored"}

    logger.info(f"Mensagem WhatsApp de {chat_id}: {body[:50]}...")

    # 4. Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        retry_after = rate_limiter.get_retry_after(chat_id)
        logger.warning(f"Rate limit atingido para {chat_id}")
        asyncio.create_task(
            whatsapp_agent.send_message(
                f"Muitas mensagens. Aguarde {retry_after} segundos antes de enviar novamente.",
                chat_id
            )
        )
        return {"status": "rate_limited"}

    # 5. Executa em background com error handling
    task = asyncio.create_task(_safe_handle_message(body, chat_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "success"}


@app.get("/report/{run_id}")
def get_report(run_id: int):
    try:
        report = Report.get(Report.run_id == run_id)
        return {"run_id": run_id, "content": report.content}
    except Report.DoesNotExist:
        raise HTTPException(status_code=404, detail="Relatorio nao encontrado")


@app.get("/recent-runs")
def get_recent_runs(limit: int = 10):
    runs = Run.select().order_by(Run.timestamp.desc()).limit(limit)
    return list(runs.dicts())


@app.post("/run-analysis")
async def run_analysis(symbol: str, timeframe: str = "H1"):
    """Debate completo com 4 agentes LLM (sob demanda)."""
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1
    }
    selected_tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_H1)
    result = agent.run_full_analysis(symbol, selected_tf)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/run-binary")
async def run_binary(symbol: str, expiration: str = "M5"):
    """Gera sinal binario (CALL/PUT) para um ativo."""
    valid_exps = settings.binary.expirations
    if expiration.upper() not in valid_exps:
        raise HTTPException(
            status_code=400,
            detail=f"Expiracao invalida. Opcoes: {valid_exps}"
        )
    result = agent.run_for_symbol_binary(symbol, expiration.upper())
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/binary/stats")
def binary_stats(days: int = 30, symbol: str = None):
    """Estatisticas de sinais binarios."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        BinarySignal.select(BinarySignal, Run)
        .join(Run)
        .where(BinarySignal.opened_at >= cutoff)
    )
    if symbol:
        query = query.where(Run.symbol == symbol.upper())

    signals = list(query.dicts())
    total = len(signals)
    itm = sum(1 for s in signals if s.get("status") == "ITM")
    otm = sum(1 for s in signals if s.get("status") == "OTM")
    tie = sum(1 for s in signals if s.get("status") == "TIE")
    open_count = sum(1 for s in signals if s.get("status") == "OPEN")
    closed = itm + otm + tie
    win_rate = (itm / closed * 100) if closed > 0 else 0

    return {
        "days": days,
        "symbol": symbol,
        "total": total,
        "itm": itm,
        "otm": otm,
        "tie": tie,
        "open": open_count,
        "win_rate": round(win_rate, 1)
    }


@app.get("/binary/recent")
def binary_recent(limit: int = 10):
    """Ultimos sinais binarios."""
    signals = (
        BinarySignal.select(BinarySignal, Run)
        .join(Run)
        .order_by(BinarySignal.opened_at.desc())
        .limit(limit)
    )
    result = []
    for sig in signals:
        result.append({
            "symbol": sig.run.symbol,
            "direction": sig.direction,
            "expiration": sig.expiration,
            "confidence": sig.confidence,
            "entry_price": sig.entry_price,
            "expiry_price": sig.expiry_price,
            "status": sig.status,
            "opened_at": sig.opened_at.isoformat() if sig.opened_at else None,
            "expires_at": sig.expires_at.isoformat() if sig.expires_at else None,
            "closed_at": sig.closed_at.isoformat() if sig.closed_at else None,
        })
    return result


# ==========================================
# DASHBOARD (Static Files)
# ==========================================

_dashboard_dist = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"

if _dashboard_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_dashboard_dist / "assets")), name="dashboard-assets")

    @app.get("/{full_path:path}")
    async def serve_dashboard(full_path: str):
        """Serve o dashboard React (SPA fallback para index.html)."""
        file_path = _dashboard_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_dashboard_dist / "index.html"))
