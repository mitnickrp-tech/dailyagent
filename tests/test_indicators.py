"""
Testes para o módulo de Indicadores Técnicos.
"""
import pytest
import pandas as pd
import numpy as np
from dailyagent.features.indicators import Indicators


class TestIndicators:
    
    def setup_method(self):
        self.indicators = Indicators()
    
    def test_calculate_returns(self, sample_ohlcv_data):
        """Testa cálculo de retornos."""
        df = self.indicators.calculate_returns(sample_ohlcv_data)
        
        assert 'returns' in df.columns
        assert 'log_returns' in df.columns
        assert df['returns'].iloc[0] != df['returns'].iloc[0]  # Primeiro é NaN
        assert len(df) == len(sample_ohlcv_data)
    
    def test_calculate_volatility(self, sample_ohlcv_data):
        """Testa cálculo de volatilidade e ATR."""
        df = self.indicators.calculate_returns(sample_ohlcv_data)
        df = self.indicators.calculate_volatility(df)
        
        assert 'realized_vol' in df.columns
        assert 'atr' in df.columns
        assert df['atr'].dropna().min() >= 0  # ATR sempre positivo
    
    def test_calculate_moving_averages(self, sample_ohlcv_data):
        """Testa cálculo de médias móveis."""
        df = self.indicators.calculate_moving_averages(sample_ohlcv_data)
        
        assert 'sma_20' in df.columns
        assert 'sma_50' in df.columns
        assert 'sma_200' in df.columns
        assert 'ema_9' in df.columns
        assert 'ema_21' in df.columns
        
        # SMA20 precisa de 20 candles, então primeiro válido é índice 19
        assert df['sma_20'].iloc[18] != df['sma_20'].iloc[18] or df['sma_20'].iloc[19] == df['sma_20'].iloc[19]
    
    def test_calculate_rsi(self, sample_ohlcv_data):
        """Testa cálculo de RSI."""
        df = self.indicators.calculate_rsi(sample_ohlcv_data)
        
        assert 'rsi' in df.columns
        assert 0 <= df['rsi'].dropna().min() <= 100
        assert 0 <= df['rsi'].dropna().max() <= 100
    
    def test_calculate_adx(self, sample_ohlcv_data):
        """Testa cálculo de ADX."""
        df = self.indicators.calculate_adx(sample_ohlcv_data)
        
        assert 'adx' in df.columns
        assert df['adx'].dropna().min() >= 0
    
    def test_calculate_candlestick_patterns(self, sample_ohlcv_data):
        """Testa detecção de padrões de candlestick."""
        df = self.indicators.calculate_candlestick_patterns(sample_ohlcv_data)
        
        assert 'is_pinbar_bull' in df.columns
        assert 'is_pinbar_bear' in df.columns
        assert 'is_engulfing_bull' in df.columns
        assert 'is_engulfing_bear' in df.columns
        
        # Valores devem ser booleanos
        assert df['is_pinbar_bull'].dtype == bool
    
    def test_full_pipeline(self, sample_ohlcv_data):
        """Testa pipeline completo de indicadores."""
        df = sample_ohlcv_data
        df = self.indicators.calculate_returns(df)
        df = self.indicators.calculate_volatility(df)
        df = self.indicators.calculate_moving_averages(df)
        df = self.indicators.calculate_rsi(df)
        df = self.indicators.calculate_adx(df)
        df = self.indicators.calculate_candlestick_patterns(df)
        
        df_clean = df.dropna()
        
        # Deve ter dados suficientes após limpeza
        assert len(df_clean) > 0
        assert 'rsi' in df_clean.columns
        assert 'adx' in df_clean.columns
        assert 'atr' in df_clean.columns
