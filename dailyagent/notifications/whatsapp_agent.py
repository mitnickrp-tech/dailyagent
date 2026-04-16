"""
WhatsApp Agent - Atendente inteligente para interacao via WhatsApp.

Este agente atua como interface entre o usuario e o DailyAgent, fornecendo:
- Respostas tecnicas detalhadas e formatadas para mobile
- Memoria de conversa persistente (RAM + PostgreSQL)
- Comandos especiais (/help, /status, /portfolio, etc.)
- Analise sob demanda com resumo inteligente dos 4 agentes
- Timeout protection e error handling robusto
"""

import asyncio
import httpx
import json
import traceback
from datetime import datetime, timezone
from ..core.config import settings
from ..core.logger import get_logger
from ..llm.client import LLMClient

logger = get_logger("WhatsAppAgent")


class ConversationMemory:
    """Armazena contexto das conversas por usuario (RAM + PostgreSQL)."""

    def __init__(self, max_history: int = 30):
        self.max_history = max_history
        self.conversations: dict[str, list] = {}

    def add_message(self, chat_id: str, role: str, content: str):
        """Adiciona mensagem ao historico (RAM + DB)."""
        if chat_id not in self.conversations:
            self.conversations[chat_id] = []

        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.conversations[chat_id].append(entry)

        if len(self.conversations[chat_id]) > self.max_history:
            self.conversations[chat_id] = self.conversations[chat_id][-self.max_history:]

        # Persiste no banco de dados
        try:
            from ..persistence.models import ChatMessage, db
            with db.connection_context():
                ChatMessage.create(
                    chat_id=chat_id,
                    role=role,
                    content=content
                )
        except Exception as e:
            logger.warning(f"Falha ao persistir mensagem no DB: {e}")

    def get_history(self, chat_id: str, last_n: int = 10) -> str:
        """Retorna historico formatado. Hidrata do DB se necessario."""
        if chat_id not in self.conversations or not self.conversations[chat_id]:
            self._hydrate_from_db(chat_id, last_n)

        if chat_id not in self.conversations:
            return "Sem historico de conversa."

        history = self.conversations[chat_id][-last_n:]
        formatted = []
        for msg in history:
            role_label = "Voce" if msg["role"] == "user" else "Assistente"
            formatted.append(f"{role_label}: {msg['content'][:200]}")

        return "\n".join(formatted)

    def clear(self, chat_id: str):
        """Limpa historico de um chat (RAM + DB)."""
        if chat_id in self.conversations:
            del self.conversations[chat_id]

        try:
            from ..persistence.models import ChatMessage, db
            with db.connection_context():
                ChatMessage.delete().where(ChatMessage.chat_id == chat_id).execute()
        except Exception as e:
            logger.warning(f"Falha ao limpar historico do DB: {e}")

    def _hydrate_from_db(self, chat_id: str, limit: int = 30):
        """Carrega historico do banco de dados para a memoria."""
        try:
            from ..persistence.models import ChatMessage, db
            with db.connection_context():
                rows = (
                    ChatMessage
                    .select()
                    .where(ChatMessage.chat_id == chat_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(limit)
                )
                messages = list(rows)

            if messages:
                self.conversations[chat_id] = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.created_at.isoformat() if msg.created_at else ""
                    }
                    for msg in reversed(messages)
                ]
        except Exception as e:
            logger.warning(f"Falha ao hidratar historico do DB: {e}")


# Memoria global (compartilhada entre instancias)
memory = ConversationMemory(max_history=30)


class WhatsAppAgent:
    """
    Atendente inteligente do DailyAgent via WhatsApp.

    Funcionalidades:
    - Responde perguntas sobre ativos
    - Fornece analises tecnicas detalhadas
    - Aceita comandos especiais
    - Mantem contexto da conversa
    - Totalmente async para integracao com FastAPI
    """

    def __init__(self, agent=None):
        self.enabled = settings.notifications.waha_enabled
        self.api_url = settings.waha.api_url.rstrip("/")
        self.session = settings.waha.session
        self.recipient = settings.waha.recipient_phone
        self.llm = LLMClient()
        self.model = settings.llm.whatsapp_agent
        self._agent = agent

        # HTTP client com header de autenticacao WAHA
        headers = {}
        if settings.waha.api_key:
            headers["X-Api-Key"] = settings.waha.api_key
        self._http_client = httpx.AsyncClient(timeout=15.0, headers=headers)

        # Comandos disponiveis
        self.commands = {
            "/help": self._cmd_help,
            "/ajuda": self._cmd_help,
            "/status": self._cmd_status,
            "/portfolio": self._cmd_portfolio,
            "/top5": self._cmd_top5,
            "/detalhar": self._cmd_detalhar,
            "/analisar": self._cmd_analisar,
            "/binary": self._cmd_binary,
            "/stats": self._cmd_stats,
            "/limpar": self._cmd_limpar,
            "/clear": self._cmd_limpar,
        }

    async def send_message(self, message: str, chat_id: str = None) -> bool:
        """Envia mensagem via WhatsApp (async)."""
        if not self.enabled:
            logger.warning("WAHA: Notificacoes desabilitadas.")
            return False

        target = chat_id or self.recipient
        if not target:
            logger.warning("WAHA: Nenhum destinatario configurado.")
            return False

        if "@c.us" not in target and "@g.us" not in target:
            target = f"{target}@c.us"

        payload = {
            "chatId": target,
            "text": message,
            "session": self.session
        }

        try:
            response = await self._http_client.post(
                f"{self.api_url}/api/sendText",
                json=payload
            )

            if response.status_code in [200, 201]:
                logger.info(f"WhatsApp: Mensagem enviada para {target}")
                return True
            else:
                logger.error(f"WAHA Error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Erro na conexao com WAHA: {e}")
            return False

    async def handle_message(self, user_message: str, chat_id: str) -> bool:
        """
        Processa mensagem do usuario e responde adequadamente.

        Fluxo:
        1. Verifica se e comando especial
        2. Verifica se e simbolo de ativo
        3. Usa LLM para responder de forma contextual
        """
        await asyncio.to_thread(memory.add_message, chat_id, "user", user_message)

        msg = user_message.strip()

        # 1. Verifica comandos especiais
        if msg.startswith("/"):
            command = msg.split()[0].lower()
            if command in self.commands:
                return await self.commands[command](chat_id, msg)
            else:
                await self.send_message(
                    f"Comando desconhecido: {command}\n\nDigite /help para ver os comandos disponiveis.",
                    chat_id
                )
                return False

        # 2. Verifica se parece ser um simbolo de ativo (3-10 chars, letras/numeros)
        cleaned = msg.upper().replace(" ", "")
        if 3 <= len(cleaned) <= 10 and cleaned.isalnum():
            return await self._handle_symbol(cleaned, chat_id)

        # 3. Resposta generica com LLM
        return await self._handle_conversation(msg, chat_id)

    async def _handle_symbol(self, symbol: str, chat_id: str) -> bool:
        """
        Processa solicitacao de analise de um ativo.
        Chama o DailyAgent completo e usa o LLM para resumir os resultados.
        """
        await self.send_message(
            f"*Analisando {symbol}...*\n\nAguarde um momento, estou consultando os dados tecnicos.",
            chat_id
        )

        try:
            agent = self._get_agent()
            import MetaTrader5 as mt5

            timeout = settings.whatsapp_config.analysis_timeout_seconds
            result = await asyncio.wait_for(
                asyncio.to_thread(agent.run_for_symbol, symbol, mt5.TIMEFRAME_H1),
                timeout=timeout
            )

            if "error" in result:
                await self.send_message(
                    f"Erro ao analisar {symbol}. Verifique se o ativo esta disponivel no MT5.",
                    chat_id
                )
                return False

            detailed_report = await self._generate_technical_summary(symbol, result)
            await asyncio.to_thread(memory.add_message, chat_id, "assistant", f"Analise de {symbol} gerada")
            return await self.send_message(detailed_report, chat_id)

        except asyncio.TimeoutError:
            logger.warning(f"Timeout ao analisar {symbol} ({timeout}s)")
            await self.send_message(
                f"A analise de {symbol} excedeu o tempo limite. O mercado ou servicos podem estar lentos. Tente novamente.",
                chat_id
            )
            return False
        except Exception as e:
            self._log_error("analisar ativo", e)
            await self.send_message(
                f"Ocorreu um erro ao analisar {symbol}. Tente novamente em alguns instantes.",
                chat_id
            )
            return False

    async def _generate_technical_summary(self, symbol: str, result: dict) -> str:
        """Usa LLM para gerar um resumo tecnico detalhado e bem formatado."""
        regime = result.get("regime", {})
        regime_parent = result.get("regime_parent", {})
        signals = result.get("signals", [])
        verdict = result.get("verdict", "")

        signals_str = json.dumps(signals, indent=2, ensure_ascii=False) if signals else "Nenhum sinal detectado"
        regime_str = json.dumps(regime, indent=2, ensure_ascii=False) if regime else "Nao disponivel"
        parent_str = json.dumps(regime_parent, indent=2, ensure_ascii=False) if regime_parent else "Nao disponivel"

        prompt = f"""
Voce e um *Assistente Tecnico de Trading Senior* do DailyAgent.
Sua tarefa e explicar de forma DETALHADA e TECNICA a analise do ativo {symbol}.

SEJA COMPLETO NOS DETALHES. O usuario quer saber TODOS os aspectos tecnicos.

DADOS PARA ANALISE:

REGIME LOCAL (Timeframe Operacional):
{regime_str}

REGIME GLOBAL (Timeframe Superior):
{parent_str}

SINAIS DETECTADOS:
{signals_str}

VEREDITO DO CONSENSO:
{verdict}

INSTRUCOES PARA SUA RESPOSTA:

1. *Comece com um RESUMO EXECUTIVO* claro (COMPRA/VENDA/AGUARDAR + confianca)

2. *Explique o REGIME LOCAL em detalhes:*
   - Tendencia atual e por que
   - Volatilidade e o que significa
   - Macro Score e sua interpretacao
   - RSI e situacao atual

3. *Explique o REGIME GLOBAL (Timeframe Superior):*
   - Se esta a favor ou contra a mare maior
   - Riscos de operar contra tendencia macro

4. *Detalhe os SINAIS TECNICOS:*
   - Tipo de cada sinal (Breakout/Pullback/Reversal)
   - Direcao e forca
   - Score final de cada um

5. *Sugira niveis de entrada, TP e SL* baseado nos sinais (se disponiveis)

6. *Termine com recomendacoes praticas*

SEJA TECNICO MAS DIDATICO. Use formatacao WhatsApp:
- *negrito* para destaques
- _italico_ para enfase
- Quebras de linha para clareza

Responda em Portugues do Brasil.
"""

        try:
            timeout = settings.whatsapp_config.llm_timeout_seconds
            response = await asyncio.wait_for(
                asyncio.to_thread(self.llm.generate_custom_prompt, prompt, model=self.model),
                timeout=timeout
            )

            if "Erro" in response or "Error" in response:
                return self._fallback_summary(symbol, result)

            return response

        except asyncio.TimeoutError:
            logger.warning(f"Timeout na geracao de resumo tecnico para {symbol}")
            return self._fallback_summary(symbol, result)
        except Exception as e:
            self._log_error("gerar resumo tecnico", e)
            return self._fallback_summary(symbol, result)

    def _fallback_summary(self, symbol: str, result: dict) -> str:
        """Resumo tecnico sem LLM (fallback)."""
        regime = result.get("regime", {})
        signals = result.get("signals", [])
        verdict = result.get("verdict", "Nao disponivel")

        msg = f"*ANALISE TECNICA: {symbol}*\n\n"

        msg += f"*Regime Local:*\n"
        msg += f"- Tendencia: {regime.get('trend', 'N/A')}\n"
        msg += f"- Volatilidade: {regime.get('volatility', 'N/A')}\n"
        msg += f"- Macro Score: {regime.get('macro_score', 0)}\n"
        msg += f"- RSI: {regime.get('rsi', 0):.1f}\n\n"

        if signals:
            msg += f"*Sinais Detectados ({len(signals)}):*\n"
            for i, sig in enumerate(signals[:3], 1):
                msg += f"{i}. {sig.get('type', '?')} {sig.get('direction', '?')} (Forca: {sig.get('strength', 0):.2f})\n"
            msg += "\n"

        msg += f"*Veredito:*\n{verdict}\n\n"
        msg += "_Para analise mais detalhada, tente novamente em alguns instantes._"

        return msg

    # ==========================================
    # COMANDOS ESPECIAIS
    # ==========================================

    async def _cmd_help(self, chat_id: str, msg: str) -> bool:
        """Mostra ajuda completa."""
        help_text = """*DAILYAGENT 2.0 - Assistente de Trading*

_Bem-vindo! Sou seu assistente tecnico de trading com IA._

*COMO USAR:*

*Basta enviar o nome de um ativo:*
_EURUSD, GBPUSD, BTCUSD, NAS100, etc._

Eu farei uma analise rapida com veredito automatico (1 LLM).

*COMANDOS FOREX:*

/help ou /ajuda - _Mostra esta ajuda_
/status - _Status do sistema_
/portfolio - _Ultimos sinais gerados_
/top5 - _Ranking dos 5 melhores ativos_
/detalhar SYMBOL - _Analise rapida 1 LLM (~10s)_
/analisar SYMBOL - _Debate completo 4 agentes (~60s)_

*COMANDOS BINARIOS:*

/binary - _Scan de todos os ativos binarios_
/binary SYMBOL - _Sinal binario para um ativo_
/binary SYMBOL M1 - _Com expiracao (M1/M5/M15)_
/stats - _Estatisticas de resultados_
/stats 7 - _Ultimos 7 dias_
/stats SYMBOL - _Filtro por ativo_

*OUTROS:*

/limpar ou /clear - _Limpa historico_

_Pronto para comecar? Envie um simbolo!_
"""
        return await self.send_message(help_text, chat_id)

    async def _cmd_status(self, chat_id: str, msg: str) -> bool:
        """Mostra status do sistema."""
        try:
            import MetaTrader5 as mt5

            mt5_info = await asyncio.to_thread(mt5.terminal_info)
            mt5_status = "Conectado" if mt5_info else "Desconectado"

            assets = settings.monitoring.assets
            assets_str = ", ".join(assets) if assets else "Nenhum configurado"

            status_text = f"""*DAILYAGENT 2.0 - STATUS*

*Sistema:*
- MT5: {mt5_status}
- API: Online
- WhatsApp: Conectado
- Intervalo Monitor: {settings.monitoring.default_interval_minutes}min

*Ativos Monitorados:*
{assets_str}

*Modelos IA Configurados:*
- Tendencia: {settings.llm.trend_model}
- Contrarian: {settings.llm.contrarian_model}
- Fundamentalista: {settings.llm.fundamental_model}
- Moderador: {settings.llm.moderator_model}
- WhatsApp: {settings.llm.whatsapp_agent}

*Ultima verificacao:* {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC

_Digite um simbolo para analise ou /help para ajuda._
"""
            return await self.send_message(status_text, chat_id)

        except Exception as e:
            self._log_error("verificar status", e)
            return await self.send_message(
                "Erro ao verificar status do sistema. Tente novamente.",
                chat_id
            )

    async def _cmd_portfolio(self, chat_id: str, msg: str) -> bool:
        """Mostra ultimos sinais do banco de dados."""
        try:
            from ..persistence.models import Signal, Run, db

            def _query_signals():
                with db.connection_context():
                    recent_signals = (
                        Signal
                        .select(Signal, Run)
                        .join(Run)
                        .order_by(Signal.id.desc())
                        .limit(5)
                    )
                    return list(recent_signals)

            recent_signals = await asyncio.to_thread(_query_signals)

            if not recent_signals:
                return await self.send_message("Nenhum sinal recente no banco de dados.", chat_id)

            text = "*ULTIMOS SINAIS GERADOS*\n\n"

            for sig in recent_signals:
                run = sig.run
                status_icon = {
                    "WIN": "[WIN]",
                    "LOSS": "[LOSS]",
                    "PENDING": "[PEND]",
                    "EXPIRED": "[EXP]"
                }.get(sig.status, "[?]")

                text += f"{status_icon} *{run.symbol}* ({run.trend})\n"
                text += f"   Direcao: {sig.direction} | Score: {sig.final_score:.2f}\n"
                text += f"   Entrada: {sig.entry_price:.5f}\n"
                if sig.tp_price and sig.tp_price > 0:
                    text += f"   TP: {sig.tp_price:.5f} | SL: {sig.sl_price:.5f}\n"
                text += "\n"

            text += "_Para analise detalhada, envie o simbolo do ativo._"

            return await self.send_message(text, chat_id)

        except Exception as e:
            self._log_error("buscar portfolio", e)
            return await self.send_message(
                "Erro ao buscar sinais recentes. Tente novamente.",
                chat_id
            )

    async def _cmd_limpar(self, chat_id: str, msg: str) -> bool:
        """Limpa historico do chat."""
        await asyncio.to_thread(memory.clear, chat_id)
        return await self.send_message("_Historico da conversa limpo com sucesso._", chat_id)

    async def _cmd_top5(self, chat_id: str, msg: str) -> bool:
        """Ranking dos top 5 ativos por score quantitativo."""
        await self.send_message(
            "*Escaneando ativos monitorados...*\n_Isso leva ~30 segundos._",
            chat_id
        )

        try:
            agent = self._get_agent()
            timeout = settings.whatsapp_config.analysis_timeout_seconds

            results = await asyncio.wait_for(
                asyncio.to_thread(agent.quick_scan_all),
                timeout=timeout
            )

            if not results:
                return await self.send_message(
                    "Nenhum ativo configurado para monitoramento.", chat_id
                )

            top5 = results[:5]
            report = self._format_top5(top5)
            await asyncio.to_thread(memory.add_message, chat_id, "assistant", "Top 5 gerado")
            return await self.send_message(report, chat_id)

        except asyncio.TimeoutError:
            return await self.send_message(
                "O scan excedeu o tempo limite. Tente novamente.", chat_id
            )
        except Exception as e:
            self._log_error("scan top5", e)
            return await self.send_message(
                "Erro ao escanear ativos. Tente novamente.", chat_id
            )

    def _format_top5(self, results: list) -> str:
        """Formata ranking top 5 para WhatsApp."""
        medals = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3"]

        text = "*TOP 5 ATIVOS - DailyAgent 2.0*\n"
        text += f"_Scan quantitativo em {datetime.now(timezone.utc).strftime('%H:%M')} UTC_\n\n"

        for i, r in enumerate(results):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            symbol = r.get("symbol", "?")

            if "error" in r:
                text += f"{medal} *{symbol}* - _Erro: {r['error']}_\n\n"
                continue

            regime = r.get("regime", {})
            signals = r.get("signals", [])
            score = r.get("top_score", 0)
            trend = regime.get("trend", "N/A")
            vol = regime.get("volatility", "N/A")
            rsi = regime.get("rsi", 0)

            best_signal = signals[0] if signals else None
            direction = best_signal['direction'] if best_signal else "N/A"
            sig_type = best_signal['type'] if best_signal else "N/A"

            text += f"{medal} *{symbol}* - Score: *{score:.2f}*\n"
            text += f"   Tendencia: {trend} | Vol: {vol}\n"
            text += f"   RSI: {rsi:.1f} | Sinal: {sig_type} {direction}\n\n"

        text += "_Envie o simbolo para analise completa com LLM._"
        return text

    # ==========================================
    # NOVOS COMANDOS (Detalhar, Analisar, Binary, Stats)
    # ==========================================

    async def _cmd_detalhar(self, chat_id: str, msg: str) -> bool:
        """Analise rapida com 1 LLM (resumo tecnico)."""
        parts = msg.split()
        if len(parts) < 2:
            return await self.send_message(
                "Uso: /detalhar SYMBOL\nExemplo: /detalhar EURUSD", chat_id
            )

        symbol = parts[1].upper()
        await self.send_message(
            f"*Detalhando {symbol}...*\n_Analise rapida com 1 LLM (~10s)._", chat_id
        )

        try:
            agent = self._get_agent()
            timeout = settings.whatsapp_config.analysis_timeout_seconds

            result = await asyncio.wait_for(
                asyncio.to_thread(agent.quick_scan, symbol),
                timeout=timeout
            )

            if "error" in result:
                return await self.send_message(
                    f"Erro ao detalhar {symbol}: {result['error']}", chat_id
                )

            detailed_report = await self._generate_technical_summary(symbol, result)
            await asyncio.to_thread(memory.add_message, chat_id, "assistant", f"Detalhe de {symbol}")
            return await self.send_message(detailed_report, chat_id)

        except asyncio.TimeoutError:
            return await self.send_message(
                f"Timeout ao detalhar {symbol}. Tente novamente.", chat_id
            )
        except Exception as e:
            self._log_error("detalhar ativo", e)
            return await self.send_message(
                f"Erro ao detalhar {symbol}. Tente novamente.", chat_id
            )

    async def _cmd_analisar(self, chat_id: str, msg: str) -> bool:
        """Debate completo com 4 agentes LLM (sob demanda)."""
        parts = msg.split()
        if len(parts) < 2:
            return await self.send_message(
                "Uso: /analisar SYMBOL\nExemplo: /analisar EURUSD", chat_id
            )

        symbol = parts[1].upper()
        await self.send_message(
            f"*Analisando {symbol} com 4 agentes IA...*\n"
            f"_Debate completo: Tendencia + Contrarian + Fundamentalista + Moderador._\n"
            f"_Isso pode levar ~60 segundos._",
            chat_id
        )

        try:
            agent = self._get_agent()
            import MetaTrader5 as mt5
            timeout = settings.whatsapp_config.analysis_timeout_seconds

            result = await asyncio.wait_for(
                asyncio.to_thread(agent.run_full_analysis, symbol, mt5.TIMEFRAME_H1),
                timeout=timeout
            )

            if "error" in result:
                return await self.send_message(
                    f"Erro ao analisar {symbol}: {result['error']}", chat_id
                )

            report = result.get("report", "")
            if report:
                await asyncio.to_thread(memory.add_message, chat_id, "assistant", f"Analise completa de {symbol}")
                return await self.send_message(report, chat_id)
            else:
                verdict = result.get("verdict", "Sem veredito disponivel.")
                return await self.send_message(
                    f"*ANALISE COMPLETA: {symbol}*\n\n{verdict}", chat_id
                )

        except asyncio.TimeoutError:
            return await self.send_message(
                f"A analise completa de {symbol} excedeu o tempo limite. Tente /detalhar para uma analise mais rapida.",
                chat_id
            )
        except Exception as e:
            self._log_error("analisar completo", e)
            return await self.send_message(
                f"Erro ao analisar {symbol}. Tente novamente.", chat_id
            )

    async def _cmd_binary(self, chat_id: str, msg: str) -> bool:
        """Sinal binario (CALL/PUT) sob demanda."""
        parts = msg.split()

        if len(parts) == 1:
            return await self._binary_scan_all(chat_id)

        symbol = parts[1].upper()
        expiration = parts[2].upper() if len(parts) > 2 else settings.binary.default_expiration

        valid_exps = settings.binary.expirations
        if expiration not in valid_exps:
            return await self.send_message(
                f"Expiracao invalida: {expiration}\nOpcoes: {', '.join(valid_exps)}",
                chat_id
            )

        await self.send_message(
            f"*Analisando {symbol} para binario ({expiration})...*", chat_id
        )

        try:
            agent = self._get_agent()
            timeout = settings.whatsapp_config.analysis_timeout_seconds

            result = await asyncio.wait_for(
                asyncio.to_thread(agent.run_for_symbol_binary, symbol, expiration),
                timeout=timeout
            )

            if "error" in result:
                return await self.send_message(f"Erro: {result['error']}", chat_id)

            if result.get("status") == "skipped":
                return await self.send_message(
                    f"Ja existe sinal OPEN para {symbol} {expiration}. Aguarde expirar.",
                    chat_id
                )

            if result.get("status") == "below_threshold":
                direction = result.get("direction", "WAIT")
                confidence = result.get("confidence", 0)
                return await self.send_message(
                    f"*{symbol} {expiration}*: {direction} (conf: {confidence}%)\n"
                    f"_Abaixo do threshold ({settings.binary.confidence_threshold}%). Sem sinal._",
                    chat_id
                )

            direction = result.get("direction", "?")
            confidence = result.get("confidence", 0)
            entry = result.get("entry_price", 0)
            expires = result.get("expires_at", "?")

            text = (
                f"*SINAL BINARIO EMITIDO*\n\n"
                f"Ativo: *{symbol}*\n"
                f"Direcao: *{direction}*\n"
                f"Expiracao: *{expiration}*\n"
                f"Confianca: *{confidence}%*\n"
                f"Entrada: *{entry:.5f}*\n"
                f"Expira em: {expires}"
            )
            await asyncio.to_thread(memory.add_message, chat_id, "assistant", f"Binary {symbol} {direction}")
            return await self.send_message(text, chat_id)

        except asyncio.TimeoutError:
            return await self.send_message(f"Timeout ao analisar {symbol} binario.", chat_id)
        except Exception as e:
            self._log_error("binary signal", e)
            return await self.send_message(f"Erro ao gerar sinal binario para {symbol}.", chat_id)

    async def _binary_scan_all(self, chat_id: str) -> bool:
        """Scan quantitativo de todos os ativos binarios configurados."""
        assets = settings.binary.assets
        if not assets:
            return await self.send_message(
                "Nenhum ativo binario configurado. Verifique config.json.", chat_id
            )

        await self.send_message(f"*Escaneando {len(assets)} ativos binarios...*", chat_id)

        try:
            agent = self._get_agent()
            import MetaTrader5 as mt5

            exp_tf = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
            tf = exp_tf.get(settings.binary.default_expiration, mt5.TIMEFRAME_M5)

            results = []
            for symbol in assets:
                try:
                    r = await asyncio.wait_for(
                        asyncio.to_thread(agent.quick_scan, symbol, tf),
                        timeout=30
                    )
                    results.append(r)
                except Exception:
                    results.append({"symbol": symbol, "error": "Timeout/Erro", "top_score": 0})

            results.sort(key=lambda x: x.get("top_score", 0), reverse=True)

            text = f"*SCAN BINARIO - DailyAgent 2.0*\n"
            text += f"_Exp: {settings.binary.default_expiration} | {datetime.now(timezone.utc).strftime('%H:%M')} UTC_\n\n"

            for r in results:
                sym = r.get("symbol", "?")
                if "error" in r:
                    text += f"*{sym}* - _Erro_\n"
                    continue
                score = r.get("top_score", 0)
                regime = r.get("regime", {})
                trend = regime.get("trend", "N/A")
                rsi = regime.get("rsi", 0)
                text += f"*{sym}* | Score: *{score:.2f}* | {trend} | RSI: {rsi:.1f}\n"

            text += f"\n_Use /binary SYMBOL para gerar sinal._"
            return await self.send_message(text, chat_id)

        except Exception as e:
            self._log_error("binary scan all", e)
            return await self.send_message("Erro ao escanear ativos binarios.", chat_id)

    async def _cmd_stats(self, chat_id: str, msg: str) -> bool:
        """Estatisticas de resultados binarios (auditoria)."""
        parts = msg.split()
        days = 30
        symbol_filter = None

        if len(parts) > 1:
            arg = parts[1]
            if arg.isdigit():
                days = int(arg)
            else:
                symbol_filter = arg.upper()

        try:
            from ..persistence.models import BinarySignal, Run, db
            from datetime import timedelta

            def _query_stats():
                with db.connection_context():
                    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                    query = (
                        BinarySignal.select(BinarySignal, Run)
                        .join(Run)
                        .where(BinarySignal.opened_at >= cutoff)
                    )
                    if symbol_filter:
                        query = query.where(Run.symbol == symbol_filter)
                    return list(query)

            signals = await asyncio.to_thread(_query_stats)

            if not signals:
                filter_text = f" para {symbol_filter}" if symbol_filter else ""
                return await self.send_message(
                    f"Nenhum sinal binario nos ultimos {days} dias{filter_text}.", chat_id
                )

            total = len(signals)
            itm = sum(1 for s in signals if s.status == "ITM")
            otm = sum(1 for s in signals if s.status == "OTM")
            tie = sum(1 for s in signals if s.status == "TIE")
            open_count = sum(1 for s in signals if s.status == "OPEN")
            closed = itm + otm + tie
            win_rate = (itm / closed * 100) if closed > 0 else 0

            exp_stats = {}
            for s in signals:
                exp = s.expiration
                if exp not in exp_stats:
                    exp_stats[exp] = {"itm": 0, "otm": 0, "tie": 0, "total": 0}
                exp_stats[exp]["total"] += 1
                if s.status in ("ITM", "OTM", "TIE"):
                    exp_stats[exp][s.status.lower()] += 1

            title = f"*STATS BINARIO"
            if symbol_filter:
                title += f" - {symbol_filter}"
            title += f" ({days} dias)*"

            text = f"{title}\n\n"
            text += f"*Geral:*\n"
            text += f"- Total: {total} sinais\n"
            text += f"- ITM: {itm} | OTM: {otm} | TIE: {tie}\n"
            text += f"- Em aberto: {open_count}\n"
            text += f"- Win Rate: *{win_rate:.1f}%*\n\n"

            if exp_stats:
                text += "*Por Expiracao:*\n"
                for exp, stats in sorted(exp_stats.items()):
                    exp_closed = stats["itm"] + stats["otm"] + stats["tie"]
                    exp_wr = (stats["itm"] / exp_closed * 100) if exp_closed > 0 else 0
                    text += f"  {exp}: {stats['total']} total | ITM: {stats['itm']} | WR: {exp_wr:.0f}%\n"

            return await self.send_message(text, chat_id)

        except Exception as e:
            self._log_error("stats binario", e)
            return await self.send_message("Erro ao buscar estatisticas.", chat_id)

    async def _handle_conversation(self, msg: str, chat_id: str) -> bool:
        """Responde a mensagens genericas de forma util."""
        history = await asyncio.to_thread(memory.get_history, chat_id, 5)

        prompt = f"""
Voce e um assistente de trading do DailyAgent 2.0.

O usuario enviou a seguinte mensagem:
"{msg}"

Historico recente:
{history}

Se a mensagem for sobre trading, ativos ou mercados financeiros, responda de forma tecnica e util.

Se for uma saudacao, seja amigavel e explique como funciona o sistema.

Se nao for relacionado a trading, responda educadamente que seu foco e analise tecnica de ativos financeiros.

Sempre termine incentivando o usuario a enviar um simbolo para analise.

Responda em Portugues do Brasil. Use formatacao WhatsApp (*negrito*, _italico_).
"""

        try:
            timeout = settings.whatsapp_config.llm_timeout_seconds
            response = await asyncio.wait_for(
                asyncio.to_thread(self.llm.generate_custom_prompt, prompt, model=self.model),
                timeout=timeout
            )
            await asyncio.to_thread(memory.add_message, chat_id, "assistant", response)
            return await self.send_message(response, chat_id)
        except asyncio.TimeoutError:
            logger.warning("Timeout na resposta conversacional")
            return await self.send_message(
                "A resposta demorou mais que o esperado. Tente enviar o nome de um ativo (ex: EURUSD) ou /help para ajuda.",
                chat_id
            )
        except Exception as e:
            self._log_error("responder conversa", e)
            return await self.send_message(
                "Nao entendi sua mensagem. Tente enviar o nome de um ativo (ex: EURUSD) ou /help para ajuda.",
                chat_id
            )

    # ==========================================
    # HELPERS
    # ==========================================

    def _get_agent(self):
        """Retorna instancia do DailyAgent (injetada ou lazy import)."""
        if self._agent is not None:
            return self._agent
        from ..core.agent import DailyAgent
        return DailyAgent()

    def _log_error(self, context: str, error: Exception):
        """Loga erro completo sem expor detalhes ao usuario."""
        logger.error(f"Erro ao {context}: {error}\n{traceback.format_exc()}")
