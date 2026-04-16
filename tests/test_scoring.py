"""
Testes para o Scoring Engine.
"""
import pytest
from dailyagent.scoring.engine import ScoringEngine


class TestScoringEngine:
    
    def setup_method(self):
        self.engine = ScoringEngine()
    
    def test_score_signals_basic(self):
        """Testa scoring básico de sinais."""
        signals = [
            {'type': 'BREAKOUT', 'direction': 'BUY', 'strength': 0.85},
            {'type': 'PULLBACK', 'direction': 'SELL', 'strength': 0.8},
        ]
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 45}
        
        scored = self.engine.score_signals(signals, regime)
        
        assert len(scored) == 2
        assert 'final_score' in scored[0]
        assert isinstance(scored[0]['final_score'], float)
    
    def test_score_signals_sorted(self):
        """Testa que sinais são ordenados por score."""
        signals = [
            {'type': 'WEAK', 'direction': 'BUY', 'strength': 0.5},
            {'type': 'STRONG', 'direction': 'BUY', 'strength': 0.9},
        ]
        regime = {'trend': 'neutral', 'volatility': 'normal', 'macro_score': 0, 'rsi': 50}
        
        scored = self.engine.score_signals(signals, regime)
        
        assert scored[0]['type'] == 'STRONG'
        assert scored[0]['final_score'] > scored[1]['final_score']
    
    def test_mtf_confluence_buy_bullish(self):
        """Testa bônus MTF para BUY em tendência bullish."""
        signals = [{'type': 'BREAKOUT', 'direction': 'BUY', 'strength': 0.85}]
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 45}
        regime_parent = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 40, 'rsi': 50}
        
        scored = self.engine.score_signals(signals, regime, regime_parent)
        
        # Deve ter bônus de 1.2x
        assert scored[0]['final_score'] > 0.85
    
    def test_mtf_confluence_buy_bearish_parent(self):
        """Testa penalidade MTF para BUY em tendência bearish superior."""
        signals = [{'type': 'BREAKOUT', 'direction': 'BUY', 'strength': 0.85}]
        regime = {'trend': 'bullish', 'volatility': 'normal', 'macro_score': 30, 'rsi': 45}
        regime_parent = {'trend': 'strong_bearish', 'volatility': 'normal', 'macro_score': -60, 'rsi': 30}
        
        scored = self.engine.score_signals(signals, regime, regime_parent)
        
        # Deve ter penalidade de 0.7x
        assert scored[0]['final_score'] < 0.85
    
    def test_mtf_confluence_sell_bearish(self):
        """Testa bônus MTF para SELL em tendência bearish."""
        signals = [{'type': 'BREAKOUT', 'direction': 'SELL', 'strength': 0.85}]
        regime = {'trend': 'bearish', 'volatility': 'normal', 'macro_score': -30, 'rsi': 55}
        regime_parent = {'trend': 'bearish', 'volatility': 'normal', 'macro_score': -40, 'rsi': 40}
        
        scored = self.engine.score_signals(signals, regime, regime_parent)
        
        # Deve ter bônus de 1.2x
        base_score = self.engine._calculate_final_score(signals[0], regime['macro_score'])
        assert scored[0]['final_score'] > base_score * 1.1
