"""
Testes para o Signal Engine.
"""
import pytest
from dailyagent.signals.engine import SignalEngine


class TestSignalEngine:
    
    def setup_method(self):
        self.engine = SignalEngine()
    
    def test_generate_signals_empty_df(self):
        """Testa geração de sinais com DataFrame vazio."""
        import pandas as pd
        df = pd.DataFrame()
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 50}
        
        signals = self.engine.generate_signals(df, regime)
        
        assert signals == []
    
    def test_generate_signals_none_df(self):
        """Testa geração de sinais com None."""
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 50}
        
        signals = self.engine.generate_signals(None, regime)
        
        assert signals == []
    
    def test_generate_signals_breakout(self, sample_df_with_indicators):
        """Testa detecção de sinal de breakout."""
        df = sample_df_with_indicators
        regime = {'trend': 'strong_bullish', 'volatility': 'normal', 'macro_score': 60, 'rsi': 55}
        
        # Simula breakout: close acima do máximo de 20 períodos + ADX > 25
        last_idx = df.index[-1]
        df.loc[last_idx, 'close'] = df['high'].iloc[-21:-1].max() * 1.01  # 1% acima
        df.loc[last_idx, 'adx'] = 30
        
        signals = self.engine.generate_signals(df, regime)
        
        # Deve ter pelo menos um sinal de breakout
        breakout_signals = [s for s in signals if s['type'] == 'BREAKOUT']
        assert len(breakout_signals) > 0
    
    def test_generate_signals_pullback(self, sample_df_with_indicators):
        """Testa detecção de sinal de pullback."""
        df = sample_df_with_indicators
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 45}
        
        # Simula pullback bull: preço toca EMA21 + pinbar bull
        last_idx = df.index[-1]
        ema21 = df.loc[last_idx, 'ema_21']
        df.loc[last_idx, 'low'] = ema21 * 0.999  # Levemente abaixo
        df.loc[last_idx, 'high'] = ema21 * 1.001  # Levemente acima
        df.loc[last_idx, 'close'] = ema21 * 1.0005
        df.loc[last_idx, 'open'] = ema21 * 0.9995
        df.loc[last_idx, 'is_pinbar_bull'] = True
        
        signals = self.engine.generate_signals(df, regime)
        
        pullback_signals = [s for s in signals if s['type'] == 'PULLBACK']
        assert len(pullback_signals) > 0
    
    def test_generate_signals_reversal(self, sample_df_with_indicators):
        """Testa detecção de sinal de reversão."""
        df = sample_df_with_indicators
        regime = {'trend': 'bearish', 'volatility': 'normal', 'macro_score': -30, 'rsi': 25}
        
        # Simula reversão bull: RSI < 30 + pinbar bull
        last_idx = df.index[-1]
        df.loc[last_idx, 'rsi'] = 25
        df.loc[last_idx, 'is_pinbar_bull'] = True
        
        signals = self.engine.generate_signals(df, regime)
        
        reversal_signals = [s for s in signals if s['type'] == 'REVERSAL']
        assert len(reversal_signals) > 0
    
    def test_signal_structure(self, sample_df_with_indicators):
        """Testa estrutura dos sinais gerados."""
        df = sample_df_with_indicators
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 45}
        
        # Força pelo menos um sinal
        last_idx = df.index[-1]
        df.loc[last_idx, 'rsi'] = 25
        df.loc[last_idx, 'is_pinbar_bull'] = True
        
        signals = self.engine.generate_signals(df, regime)
        
        if signals:
            signal = signals[0]
            assert 'type' in signal
            assert 'direction' in signal
            assert 'strength' in signal
            assert signal['type'] in ['BREAKOUT', 'PULLBACK', 'REVERSAL']
            assert signal['direction'] in ['BUY', 'SELL']
            assert 0 < signal['strength'] <= 1.0
