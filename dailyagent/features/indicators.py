import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        return df

    @staticmethod
    def calculate_volatility(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        df['realized_vol'] = df['returns'].rolling(window=window).std() * np.sqrt(252)
        
        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift(1))
        low_close = np.abs(df['low'] - df['close'].shift(1))
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(window=window).mean()
        return df

    @staticmethod
    def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        return df

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    @staticmethod
    def calculate_adx(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """Average Directional Index (ADX) - Força da Tendência."""
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = abs(minus_dm)
        
        tr = np.maximum(df['high'] - df['low'], 
                        np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                   abs(df['low'] - df['close'].shift(1))))
        
        atr = tr.rolling(window=window).mean()
        plus_di = 100 * (plus_dm.rolling(window=window).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=window).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['adx'] = dx.rolling(window=window).mean()
        return df

    @staticmethod
    def calculate_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
        """Detecta padrões Pinbar (Martelo) e Engolfo."""
        body = abs(df['close'] - df['open'])
        candle_range = df['high'] - df['low']
        
        # 1. Pinbar (Martelo/Estrela Cadente)
        # Corpo pequeno (< 30% do range) e uma das sombras > 60% do range
        df['is_pinbar_bull'] = (body < candle_range * 0.3) & ((df['low'] - df[['open', 'close']].min(axis=1)) < -candle_range * 0.6)
        df['is_pinbar_bear'] = (body < candle_range * 0.3) & ((df['high'] - df[['open', 'close']].max(axis=1)) > candle_range * 0.6)
        
        # 2. Engolfo (Engulfing)
        # O corpo atual "engole" o corpo anterior e as direções são opostas
        prev_body = abs(df['close'].shift(1) - df['open'].shift(1))
        df['is_engulfing_bull'] = (df['close'] > df['open']) & (df['close'].shift(1) < df['open'].shift(1)) & (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))
        df['is_engulfing_bear'] = (df['close'] < df['open']) & (df['close'].shift(1) > df['open'].shift(1)) & (df['close'] < df['open'].shift(1)) & (df['open'] > df['close'].shift(1))
        
        return df
