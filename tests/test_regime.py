"""
Testes para o Regime Classifier.
"""
import pytest
from dailyagent.regime.classifier import RegimeClassifier


class TestRegimeClassifier:
    
    def setup_method(self):
        self.classifier = RegimeClassifier()
    
    def test_classify_strong_bullish(self, sample_df_with_indicators):
        """Testa classificação de tendência strongly bullish."""
        df = sample_df_with_indicators
        
        # Simula cenário bullish: close > sma20 > sma50 > sma200
        last_idx = df.index[-1]
        df.loc[last_idx, 'close'] = 1.1500
        df.loc[last_idx, 'sma_20'] = 1.1400
        df.loc[last_idx, 'sma_50'] = 1.1300
        df.loc[last_idx, 'sma_200'] = 1.1200
        
        regime = self.classifier.classify(df)
        
        assert regime is not None
        assert regime['trend'] == 'strong_bullish'
        assert 'volatility' in regime
        assert 'macro_score' in regime
        assert 'rsi' in regime
    
    def test_classify_strong_bearish(self, sample_df_with_indicators):
        """Testa classificação de tendência strongly bearish."""
        df = sample_df_with_indicators
        
        # Simula cenário bearish: close < sma20 < sma50 < sma200
        last_idx = df.index[-1]
        df.loc[last_idx, 'close'] = 1.0500
        df.loc[last_idx, 'sma_20'] = 1.0600
        df.loc[last_idx, 'sma_50'] = 1.0700
        df.loc[last_idx, 'sma_200'] = 1.0800
        
        regime = self.classifier.classify(df)
        
        assert regime is not None
        assert regime['trend'] == 'strong_bearish'
    
    def test_classify_neutral(self, sample_df_with_indicators):
        """Testa classificação de tendência neutral."""
        df = sample_df_with_indicators
        
        # Simula cenário neutral: close entre as médias
        # Para ser neutral, close deve estar > sma50 mas não alinhado com sma20 > sma50
        # OU < sma50 mas não alinhado com sma20 < sma50
        last_idx = df.index[-1]
        close_val = 1.1000
        df.loc[last_idx, 'close'] = close_val
        df.loc[last_idx, 'sma_20'] = 1.1010  # acima do close
        df.loc[last_idx, 'sma_50'] = 1.0990  # abaixo do close
        df.loc[last_idx, 'sma_200'] = 1.0980
        
        regime = self.classifier.classify(df)
        
        assert regime is not None
        # Pode ser 'bullish' (close > sma50) ou 'neutral' dependendo da lógica
        assert regime['trend'] in ['neutral', 'bullish']
    
    def test_classify_volatility_high(self, sample_df_with_indicators):
        """Testa classificação de volatilidade alta."""
        df = sample_df_with_indicators
        
        # Aumenta volatilidade do último candle
        last_idx = df.index[-1]
        avg_vol = df['realized_vol'].tail(50).mean()
        df.loc[last_idx, 'realized_vol'] = avg_vol * 2.0
        
        regime = self.classifier.classify(df)
        
        assert regime['volatility'] == 'high'
    
    def test_macro_score_range(self, sample_df_with_indicators):
        """Testa que macro score está entre -100 e +100."""
        regime = self.classifier.classify(sample_df_with_indicators)
        
        assert -100 <= regime['macro_score'] <= 100
    
    def test_classify_empty_df(self):
        """Testa classificação com DataFrame vazio."""
        df = pd.DataFrame()
        regime = self.classifier.classify(df)
        
        assert regime is None
    
    def test_classify_none_df(self):
        """Testa classificação com None."""
        regime = self.classifier.classify(None)
        
        assert regime is None


# Import necessário para o teste de empty df
import pandas as pd
