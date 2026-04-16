import httpx
from datetime import datetime, timezone
from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger("WahaAgent")

class WahaAgent:
    def __init__(self):
        self.enabled = settings.notifications.waha_enabled
        self.api_url = settings.waha.api_url.rstrip("/")
        self.session = settings.waha.session
        self.recipient = settings.waha.recipient_phone
        self.headers = {}
        if settings.waha.api_key:
            self.headers["X-Api-Key"] = settings.waha.api_key

    def send_message(self, message: str, chat_id: str = None):
        if not self.enabled:
            return
            
        target = chat_id or self.recipient
        if not target:
            logger.warning("WAHA: Nenhum destinatário configurado.")
            return

        # WAHA espera o chat_id formatado (ex: 5511999999999@c.us)
        if "@c.us" not in target and "@g.us" not in target:
            target = f"{target}@c.us"

        payload = {
            "chatId": target,
            "text": message,
            "session": self.session
        }
        
        try:
            response = httpx.post(
                f"{self.api_url}/api/sendText",
                json=payload,
                headers=self.headers,
                timeout=15.0
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Mensagem enviada via WhatsApp para {target}")
            else:
                logger.error(f"Erro no WAHA: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Erro na conexão com WAHA: {e}")

    def send_report(self, symbol, verdict):
        msg = f"*DailyAgent 2.0 - Veredito: {symbol}*\n\n{verdict}"
        self.send_message(msg)

    def send_binary_alert(self, symbol, direction, confidence, expiration, entry_price):
        """Envia alerta de sinal binario via WhatsApp."""
        arrow = "CALL" if direction == "CALL" else "PUT"
        now_str = datetime.now(timezone.utc).strftime('%H:%M')

        msg = (
            f"*SINAL BINARIO - DailyAgent 2.0*\n\n"
            f"Ativo: *{symbol}*\n"
            f"Direcao: *{arrow}*\n"
            f"Expiracao: *{expiration}*\n"
            f"Confianca: *{confidence}%*\n"
            f"Entrada: *{entry_price:.5f}*\n"
            f"Horario: {now_str} UTC"
        )
        self.send_message(msg)

    def send_binary_result(self, symbol, direction, status, entry_price, expiry_price):
        """Envia resultado de sinal binario via WhatsApp."""
        diff = expiry_price - entry_price
        pips = abs(diff) * 10000

        sign = "+" if diff >= 0 else "-"

        msg = (
            f"*RESULTADO: {symbol} - {status}*\n"
            f"{direction}: {entry_price:.5f} -> {expiry_price:.5f} ({sign}{pips:.1f} pips)"
        )
        self.send_message(msg)
