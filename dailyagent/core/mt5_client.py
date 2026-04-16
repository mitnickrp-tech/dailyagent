import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
from .logger import get_logger

logger = get_logger("MT5Client")

class MT5Client:
    def __init__(self):
        pass

    def connect(self):
        if mt5.initialize():
            logger.info("Conectado ao terminal MT5 ativo.")
            return True
        
        logger.error(f"Falha ao inicializar MT5: {mt5.last_error()}")
        return False

    def disconnect(self):
        mt5.shutdown()
        logger.info("Desconectado do MT5")

    def get_data(self, symbol: str, timeframe: int, count: int):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            logger.error(f"Falha ao obter dados para {symbol}: {mt5.last_error()}")
            return None
        
        df = pd.DataFrame(rates)
        # Força explicitamente o timezone UTC a partir dos segundos Unix
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        last_candle = df['time'].iloc[-1]
        logger.info(f"Dados capturados: {len(df)} candles. Último (UTC): {last_candle}")
        
        return df

    def get_symbols(self):
        symbols = mt5.symbols_get()
        if symbols is None:
            logger.error(f"Falha ao obter símbolos: {mt5.last_error()}")
            return []
        return [s.name for s in symbols]
