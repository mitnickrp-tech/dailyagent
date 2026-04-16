"""
Configuração de testes do DailyAgent.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone


@pytest.fixture
def sample_ohlcv_data():
    """Gera dados OHLCV simulados para testes."""
    np.random.seed(42)
    n = 300
    
    # Preços base
    base_price = 1.1000
    prices = [base_price]
    
    for i in range(1, n):
        change = np.random.normal(0, 0.001)
        prices.append(prices[-1] * (1 + change))
    
    # Cria DataFrame
    df = pd.DataFrame({
        'time': pd.date_range(start='2026-04-01', periods=n, freq='h', tz='UTC'),
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.002))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.002))) for p in prices],
        'close': prices,
        'tick_volume': np.random.randint(100, 1000, n)
    })
    
    # Garante que high >= close >= low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


@pytest.fixture
def sample_df_with_indicators(sample_ohlcv_data):
    """DataFrame com indicadores calculados."""
    from dailyagent.features.indicators import Indicators
    
    df = sample_ohlcv_data
    indicators = Indicators()
    
    df = indicators.calculate_returns(df)
    df = indicators.calculate_volatility(df)
    df = indicators.calculate_moving_averages(df)
    df = indicators.calculate_rsi(df)
    df = indicators.calculate_adx(df)
    df = indicators.calculate_candlestick_patterns(df)
    
    return df.dropna()
