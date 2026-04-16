import pandas as pd
from ..core.logger import get_logger

logger = get_logger("RegimeClassifier")

class RegimeClassifier:
    def classify(self, df: pd.DataFrame):
        if df is None or df.empty:
            return None
            
        last_row = df.iloc[-1]
        
        # 1. Classificação de Tendência
        trend = self._classify_trend(last_row)
        
        # 2. Classificação de Volatilidade
        volatility = self._classify_volatility(df)
        
        # 3. Macro Regime Score (-100 a +100)
        macro_score = self._calculate_macro_score(trend, volatility, last_row)
        
        regime = {
            "trend": trend,
            "volatility": volatility,
            "macro_score": macro_score,
            "rsi": last_row['rsi']
        }
        
        logger.info(f"Regime detectado: {regime['trend']} | Vol: {regime['volatility']} | Score: {regime['macro_score']}")
        return regime

    def _classify_trend(self, row):
        # Lógica baseada em Médias Móveis (SMA 20, 50, 200)
        close = row['close']
        sma20 = row['sma_20']
        sma50 = row['sma_50']
        sma200 = row['sma_200']
        
        if close > sma20 > sma50 > sma200:
            return "strong_bullish"
        elif close > sma50:
            return "bullish"
        elif close < sma20 < sma50 < sma200:
            return "strong_bearish"
        elif close < sma50:
            return "bearish"
        else:
            return "neutral"

    def _classify_volatility(self, df):
        # Compara a volatilidade atual com a média histórica
        current_vol = df.iloc[-1]['realized_vol']
        avg_vol = df['realized_vol'].tail(50).mean()
        
        if current_vol > avg_vol * 1.5:
            return "high"
        elif current_vol > avg_vol * 1.1:
            return "expanding"
        elif current_vol < avg_vol * 0.7:
            return "low"
        else:
            return "normal"

    def _calculate_macro_score(self, trend, vol, row):
        score = 0
        
        # Contribuição da tendência
        trend_scores = {
            "strong_bullish": 60,
            "bullish": 30,
            "neutral": 0,
            "bearish": -30,
            "strong_bearish": -60
        }
        score += trend_scores.get(trend, 0)
        
        # Ajuste por RSI (sobrecompra/sobrevenda)
        rsi = row['rsi']
        if rsi > 70:
            score -= 10 # Penaliza bull extremo
        elif rsi < 30:
            score += 10 # Incentiva bear extremo (reversão)
            
        # Ajuste por Volatilidade
        if vol == "high":
            score *= 0.8 # Reduz exposição em alta volatilidade
            
        return max(-100, min(100, score))
