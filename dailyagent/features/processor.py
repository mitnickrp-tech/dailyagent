import pandas as pd
from ..core.mt5_client import MT5Client
from .indicators import Indicators
from ..core.logger import get_logger

logger = get_logger("FeatureProcessor")

class FeatureProcessor:
    def __init__(self, mt5_client: MT5Client):
        self.mt5_client = mt5_client
        self.indicators = Indicators()

    def generate_features(self, symbol: str, timeframe: int, count: int = 500):
        logger.info(f"Gerando features para {symbol} (Timeframe: {timeframe})")

        # Coleta os dados brutos - solicita extras para garantir cálculo de indicadores
        # SMA200 precisa de pelo menos 200 candles, então pedimos count + buffer
        buffer = 200
        df = self.mt5_client.get_data(symbol, timeframe, count + buffer)
        if df is None or df.empty:
            logger.error(f"Não foi possível obter dados para {symbol}")
            return None

        if len(df) < 200:
            logger.warning(f"Dados insuficientes para {symbol}: apenas {len(df)} candles (mínimo 200 para SMA200)")
            return None

        # Calcula os indicadores
        df = self.indicators.calculate_returns(df)
        df = self.indicators.calculate_volatility(df)
        df = self.indicators.calculate_moving_averages(df)
        df = self.indicators.calculate_rsi(df)
        df = self.indicators.calculate_adx(df)
        df = self.indicators.calculate_candlestick_patterns(df)

        # Remove valores nulos
        df = df.dropna()

        # Garante que temos dados suficientes após limpeza
        if len(df) < count:
            logger.warning(f"Após limpeza, dados insuficientes para {symbol}: {len(df)} candles (esperado {count})")
            return None

        # Retorna apenas os últimos 'count' candles válidos
        df = df.tail(count)

        logger.info(f"Features geradas com sucesso: {len(df)} candles processados.")
        return df
