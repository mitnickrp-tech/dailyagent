import httpx
from ..core.config import settings
from ..core.logger import get_logger
import base64

logger = get_logger("NotificationAgent")

class NotificationAgent:
    def __init__(self):
        # Prioridade: .env > config.json > defaults
        self.topic = settings.ntfy_topic or settings.ntfy.topic
        self.base_url = (settings.ntfy_url or settings.ntfy.url).rstrip("/")
        self.user = settings.ntfy_user or settings.ntfy.user
        self.password = settings.ntfy_password or settings.ntfy.password

    def notify(self, message: str, title: str = "DailyAgent 2.0", tags: list = None):
        if not self.topic:
            logger.warning("NTFY Topic não configurado. Notificação ignorada.")
            return

        # Remove emojis do título para o header se necessário, ou garante que o título seja codificado
        # O ntfy aceita UTF-8 no corpo, mas headers podem ser problemáticos em alguns clientes
        headers = {
            "Title": title.encode('utf-8').decode('latin-1'), # Hack comum para headers UTF-8
            "Tags": ",".join(tags) if tags else ""
        }
        
        if self.user and self.password:
            auth_str = f"{self.user}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"
        
        try:
            content_bytes = message.encode('utf-8')
            
            response = httpx.post(
                f"{self.base_url}/{self.topic}",
                content=content_bytes,
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"Notificação enviada com sucesso: {title}")
            else:
                logger.error(f"Erro ao enviar ntfy: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Erro na conexão com ntfy: {e}")

    def send_report_summary(self, symbol: str, regime: dict, signals: list):
        signal_count = len(signals)
        top_signal = signals[0]['type'] if signals else "NONE"
        
        msg = (
            f"Ativo: {symbol}\n"
            f"Regime: {regime['trend']} | Vol: {regime['volatility']}\n"
            f"Macro Score: {regime['macro_score']}\n"
            f"Sinais: {signal_count} detectados (Top: {top_signal})"
        )
        
        # Título sem emoji para evitar erro de header
        self.notify(msg, title=f"Relatorio de Mercado: {symbol}", tags=["chart_with_upwards_trend", symbol])
