"""
tests/test_setup_engine.py - DailyAgent 2.1

7 testes pytest para SetupEngine.
Usa DataFrames sinteticos e mocks de structure/liquidity outputs.
"""

import sys
import os
import types
import numpy as np
import pandas as pd
import pytest

# ==========================================
# Mock do logger para evitar dependencia de loguru/MT5
# ==========================================
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

class _MockLogger:
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def debug(self, *a, **kw): pass

def _mock_get_logger(name):
    return _MockLogger()

_pkg_dir = os.path.join(project_root, "dailyagent")
_core_dir = os.path.join(_pkg_dir, "core")

_da_mod = types.ModuleType("dailyagent")
_da_mod.__path__ = [_pkg_dir]
_da_mod.__package__ = "dailyagent"

_core_mod = types.ModuleType("dailyagent.core")
_core_mod.__path__ = [_core_dir]
_core_mod.__package__ = "dailyagent.core"

_core_logger_mod = types.ModuleType("dailyagent.core.logger")
_core_logger_mod.get_logger = _mock_get_logger

sys.modules.setdefault("dailyagent", _da_mod)
sys.modules.setdefault("dailyagent.core", _core_mod)
sys.modules.setdefault("dailyagent.core.logger", _core_logger_mod)

from dailyagent.setups.engine import SetupEngine


# ==========================================
# Helpers
# ==========================================

def make_df(n, base_price=1.0, spread=0.005):
    """Cria DataFrame sintetico de n candles com precos flat."""
    opens = [base_price] * n
    highs = [base_price + spread] * n
    lows = [base_price - spread] * n
    closes = [base_price] * n
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })


def make_buy_scenario_df(n=60):
    """
    Cria um DataFrame com um candle de displacement bullish no indice 35.
    - Candle grande de alta apos CHoCH.
    - Usa displacement_lookback curto para facilitar teste.
    """
    df = make_df(n, base_price=1.0, spread=0.003)
    # Candles normais tem range = 0.006

    # Displacement bullish no indice 35: candle grande de alta
    df.at[35, "open"] = 0.98
    df.at[35, "close"] = 1.02
    df.at[35, "high"] = 1.025
    df.at[35, "low"] = 0.975
    # range = 0.05, body = 0.04, ratio = 0.80

    return df


def make_sell_scenario_df(n=60):
    """
    Cria um DataFrame com um candle de displacement bearish no indice 35.
    """
    df = make_df(n, base_price=1.0, spread=0.003)

    # Displacement bearish no indice 35: candle grande de baixa
    df.at[35, "open"] = 1.02
    df.at[35, "close"] = 0.98
    df.at[35, "high"] = 1.025
    df.at[35, "low"] = 0.975
    # range = 0.05, body = 0.04, ratio = 0.80

    return df


def mock_structure(trend="bearish", choch_events=None, last_bos=None, last_choch=None):
    """Mock de output de StructureEngine."""
    if choch_events is None:
        choch_events = []
    return {
        "trend": trend,
        "last_bos": last_bos,
        "last_choch": last_choch,
        "structure_strength": 0.5,
        "swing_highs": [],
        "swing_lows": [],
        "structure_points": [],
        "bos_events": [],
        "choch_events": choch_events,
    }


def mock_liquidity(sweeps=None, liquidity_target=None):
    """Mock de output de LiquidityEngine."""
    if sweeps is None:
        sweeps = []
    return {
        "sweep": sweeps[-1]["type"] if sweeps else None,
        "strength": sweeps[-1]["strength"] if sweeps else 0.0,
        "liquidity_target": liquidity_target,
        "equal_highs": [],
        "equal_lows": [],
        "sweeps": sweeps,
        "buy_side_levels": [],
        "sell_side_levels": [],
    }


# ==========================================
# Test 1: Valid buy setup
# ==========================================
def test_valid_buy_setup():
    """
    Buy: sell_side sweep -> CHoCH bullish -> displacement bullish.
    """
    df = make_buy_scenario_df(n=60)

    # Sweep sell-side retorna no candle 30
    sweep = {
        "type": "sell_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 0.99,
        "break_low": 0.985,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }

    # CHoCH bullish no candle 34 (apos sweep return 30)
    choch = {
        "direction": "bullish",
        "index": 34,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure = mock_structure(
        trend="bearish",
        choch_events=[choch],
        last_choch="bullish",
    )
    liquidity = mock_liquidity(sweeps=[sweep], liquidity_target=1.05)

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result = engine.analyze(df, structure, liquidity)

    assert result is not None
    assert result["direction"] == "buy"
    assert result["sweep"] == sweep
    assert result["choch"] == choch
    assert result["displacement"]["direction"] == "bullish"
    assert result["target_level"] == 1.05


# ==========================================
# Test 2: Valid sell setup
# ==========================================
def test_valid_sell_setup():
    """
    Sell: buy_side sweep -> CHoCH bearish -> displacement bearish.
    """
    df = make_sell_scenario_df(n=60)

    sweep = {
        "type": "buy_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 1.01,
        "break_high": 1.015,
        "return_close": 0.995,
        "break_distance": 0.005,
        "strength": 0.65,
        "level_type": "equal",
        "level_touches": 2,
    }

    choch = {
        "direction": "bearish",
        "index": 34,
        "level": 0.99,
        "close": 0.985,
        "prev_trend": "bullish",
    }

    structure = mock_structure(
        trend="bullish",
        choch_events=[choch],
        last_choch="bearish",
    )
    liquidity = mock_liquidity(sweeps=[sweep], liquidity_target=0.95)

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result = engine.analyze(df, structure, liquidity)

    assert result is not None
    assert result["direction"] == "sell"
    assert result["displacement"]["direction"] == "bearish"
    assert result["target_level"] == 0.95


# ==========================================
# Test 3: Invalid - no CHoCH after sweep
# ==========================================
def test_invalid_no_choch():
    """Sem CHoCH apos sweep -> nenhum setup."""
    df = make_buy_scenario_df(n=60)

    sweep = {
        "type": "sell_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 0.99,
        "break_low": 0.985,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }

    # CHoCH ANTES do sweep (indice 25 < return_index 30) -> invalido
    choch_before = {
        "direction": "bullish",
        "index": 25,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure = mock_structure(choch_events=[choch_before])
    liquidity = mock_liquidity(sweeps=[sweep])

    engine = SetupEngine(displacement_search_window=5)
    result = engine.analyze(df, structure, liquidity)

    assert result is None, "CHoCH antes do sweep nao deve gerar setup"


# ==========================================
# Test 4: Invalid - no displacement after CHoCH
# ==========================================
def test_invalid_no_displacement():
    """CHoCH presente mas sem displacement forte -> nenhum setup."""
    # DataFrame com candles fracos (sem displacement)
    df = make_df(60, base_price=1.0, spread=0.003)

    sweep = {
        "type": "sell_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 0.99,
        "break_low": 0.985,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }

    choch = {
        "direction": "bullish",
        "index": 34,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure = mock_structure(choch_events=[choch])
    liquidity = mock_liquidity(sweeps=[sweep])

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result = engine.analyze(df, structure, liquidity)

    assert result is None, "Sem displacement forte nao deve gerar setup"


# ==========================================
# Test 5: Displacement only after CHoCH
# ==========================================
def test_displacement_only_after_choch():
    """Displacement deve ocorrer APOS o CHoCH, nao antes."""
    df = make_df(60, base_price=1.0, spread=0.003)

    # Coloca displacement ANTES do CHoCH (indice 30, CHoCH em 34)
    df.at[30, "open"] = 0.98
    df.at[30, "close"] = 1.02
    df.at[30, "high"] = 1.025
    df.at[30, "low"] = 0.975

    sweep = {
        "type": "sell_side",
        "break_index": 25,
        "return_index": 27,
        "level_price": 0.99,
        "break_low": 0.985,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }

    choch = {
        "direction": "bullish",
        "index": 34,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure = mock_structure(choch_events=[choch])
    liquidity = mock_liquidity(sweeps=[sweep])

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result = engine.analyze(df, structure, liquidity)

    assert result is None, "Displacement antes do CHoCH nao deve gerar setup"


# ==========================================
# Test 6: Entry zone ordered [min, max]
# ==========================================
def test_entry_zone_ordered():
    """Entry zone deve sempre ser [min, max] independente da direcao."""
    df = make_buy_scenario_df(n=60)

    sweep = {
        "type": "sell_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 0.99,
        "break_low": 0.985,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }

    choch = {
        "direction": "bullish",
        "index": 34,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure = mock_structure(choch_events=[choch])
    liquidity = mock_liquidity(sweeps=[sweep])

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result = engine.analyze(df, structure, liquidity)

    assert result is not None
    ez = result["entry_zone"]
    assert ez[0] <= ez[1], f"Entry zone deve ser [min, max], obteve {ez}"


# ==========================================
# Test 7: Invalid level and target coherence
# ==========================================
def test_invalid_level_target_coherent():
    """
    Buy: invalid_level abaixo da entry_zone.
    Sell: invalid_level acima da entry_zone.
    """
    # --- Buy setup ---
    df_buy = make_buy_scenario_df(n=60)

    sweep_buy = {
        "type": "sell_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 0.99,
        "break_low": 0.95,
        "return_close": 1.005,
        "break_distance": 0.005,
        "strength": 0.7,
        "level_type": "swing",
        "level_touches": 1,
    }
    choch_buy = {
        "direction": "bullish",
        "index": 34,
        "level": 1.01,
        "close": 1.015,
        "prev_trend": "bearish",
    }

    structure_buy = mock_structure(choch_events=[choch_buy])
    liquidity_buy = mock_liquidity(sweeps=[sweep_buy], liquidity_target=1.10)

    engine = SetupEngine(
        displacement_lookback=5,
        displacement_multiplier=1.5,
        displacement_body_ratio_min=0.7,
        displacement_search_window=5,
    )
    result_buy = engine.analyze(df_buy, structure_buy, liquidity_buy)

    assert result_buy is not None
    assert result_buy["invalid_level"] < result_buy["entry_zone"][0], (
        f"Buy: invalid_level ({result_buy['invalid_level']}) deve ser < "
        f"entry_zone min ({result_buy['entry_zone'][0]})"
    )

    # --- Sell setup ---
    df_sell = make_sell_scenario_df(n=60)

    sweep_sell = {
        "type": "buy_side",
        "break_index": 28,
        "return_index": 30,
        "level_price": 1.01,
        "break_high": 1.05,
        "return_close": 0.995,
        "break_distance": 0.005,
        "strength": 0.65,
        "level_type": "equal",
        "level_touches": 2,
    }
    choch_sell = {
        "direction": "bearish",
        "index": 34,
        "level": 0.99,
        "close": 0.985,
        "prev_trend": "bullish",
    }

    structure_sell = mock_structure(trend="bullish", choch_events=[choch_sell])
    liquidity_sell = mock_liquidity(sweeps=[sweep_sell], liquidity_target=0.90)

    result_sell = engine.analyze(df_sell, structure_sell, liquidity_sell)

    assert result_sell is not None
    assert result_sell["invalid_level"] > result_sell["entry_zone"][1], (
        f"Sell: invalid_level ({result_sell['invalid_level']}) deve ser > "
        f"entry_zone max ({result_sell['entry_zone'][1]})"
    )
