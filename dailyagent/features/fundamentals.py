import yfinance as yf
from ..core.logger import get_logger
import json

logger = get_logger("FundamentalAnalyzer")

class FundamentalAnalyzer:
    def __init__(self):
        # Mapeamento de símbolos MT5 para Yahoo Finance
        self.symbol_map = {
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X",
            "BTCUSD": "BTC-USD",
            "ETHUSD": "ETH-USD",
            "US500": "^GSPC",
            "USTECH": "^IXIC",
            "US30": "^DJI",
            "GER40": "^GDAXI",
            "UK100": "^FTSE"
        }

    def get_latest_news(self, symbol: str, count: int = 5):
        """Busca as últimas notícias do ativo no Yahoo Finance."""
        yf_symbol = self.symbol_map.get(symbol, f"{symbol}=X")
        logger.info(f"Buscando notícias fundamentais para {symbol} (Ticker: {yf_symbol})...")
        
        try:
            ticker = yf.Ticker(yf_symbol)
            news = ticker.news
            
            if not news:
                logger.warning(f"Nenhuma notícia encontrada para {symbol}")
                return "Sem notícias recentes relevantes."
            
            # Formata as notícias (Título e Link se necessário)
            formatted_news = []
            for item in news[:count]:
                title = item.get('title', 'Sem título')
                publisher = item.get('publisher', 'Desconhecido')
                # thumbnail = item.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', '')
                formatted_news.append(f"- {title} (Fonte: {publisher})")
            
            news_str = "\n".join(formatted_news)
            logger.info(f"Notícias encontradas: {len(formatted_news)}")
            return news_str
            
        except Exception as e:
            logger.error(f"Erro ao buscar notícias no Yahoo Finance: {e}")
            return "Erro ao obter dados fundamentais."

    def get_summary_context(self, symbol: str):
        """Retorna um contexto pronto para o LLM."""
        news = self.get_latest_news(symbol)
        return f"\n--- NOTÍCIAS RECENTES (FUNDAMENTAL) para {symbol} ---\n{news}\n"
