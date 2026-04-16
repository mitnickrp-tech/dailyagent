import pandas as pd
from ..core.logger import get_logger

logger = get_logger("SignalEngine")

class SignalEngine:
    def __init__(self):
        pass

    def generate_signals(self, df: pd.DataFrame, regime: dict):
        if df is None or df.empty:
            return []
            
        signals = []
        last_row = df.iloc[-1]
        
        # 1. Breakout com Confluência (Rompimento + Tendência Forte)
        if self._is_breakout_confluence(df, last_row):
            signals.append({
                "type": "BREAKOUT",
                "direction": "BUY" if last_row['close'] > df['high'].iloc[-21:-1].max() else "SELL",
                "strength": 0.85 # Aumentado por causa da confluência ADX
            })
            
        # 2. Pullback com Confluência (Média + Padrão de Candle)
        pullback_direction = self._is_pullback_confluence(last_row, regime)
        if pullback_direction:
            signals.append({
                "type": "PULLBACK",
                "direction": pullback_direction,
                "strength": 0.8
            })
            
        # 3. Reversal com Confluência (RSI + Padrão de Candle)
        reversal_direction = self._is_reversal_confluence(last_row)
        if reversal_direction:
            signals.append({
                "type": "REVERSAL",
                "direction": reversal_direction,
                "strength": 0.75
            })
            
        return signals

    def _is_breakout_confluence(self, df, row):
        # Rompimento de 20 períodos + ADX indicando tendência forte (> 25)
        period = 20
        high_max = df['high'].iloc[-period-1:-1].max()
        low_min = df['low'].iloc[-period-1:-1].min()
        
        breakout = row['close'] > high_max or row['close'] < low_min
        strong_trend = row['adx'] > 25
        
        return breakout and strong_trend

    def _is_pullback_confluence(self, row, regime):
        # Toca a EMA 21 + Padrão de Candle (Pinbar ou Engolfo) a favor da tendência
        trend = regime['trend']
        
        # Pullback de Compra
        if "bullish" in trend:
            touches_ema = row['low'] <= row['ema_21'] <= row['high']
            confirmation = row['is_pinbar_bull'] or row['is_engulfing_bull']
            if touches_ema and confirmation:
                logger.info("✨ Confluência de Pullback de COMPRA detectada!")
                return "BUY"
                
        # Pullback de Venda
        if "bearish" in trend:
            touches_ema = row['high'] >= row['ema_21'] >= row['low']
            confirmation = row['is_pinbar_bear'] or row['is_engulfing_bear']
            if touches_ema and confirmation:
                logger.info("✨ Confluência de Pullback de VENDA detectada!")
                return "SELL"
                
        return None

    def _is_reversal_confluence(self, row):
        # RSI Extremo + Padrão de Reversão
        # Compra (Reversão de Baixa para Alta)
        if row['rsi'] < 30 and (row['is_pinbar_bull'] or row['is_engulfing_bull']):
            logger.info("✨ Confluência de Reversão de COMPRA detectada!")
            return "BUY"
            
        # Venda (Reversão de Alta para Baixa)
        if row['rsi'] > 70 and (row['is_pinbar_bear'] or row['is_engulfing_bear']):
            logger.info("✨ Confluência de Reversão de VENDA detectada!")
            return "SELL"
            
        return None
