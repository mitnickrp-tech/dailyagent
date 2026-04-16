"""
tests/test_liquidity_engine.py - DailyAgent 2.1

9 testes pytest para LiquidityEngine.
Usa DataFrames sinteticos, sem dependencias externas.
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

from dailyagent.liquidity.engine import LiquidityEngine


# ==========================================
# Helpers
# ==========================================

def make_df(highs, lows, opens=None, closes=None):
    n = len(highs)
    if opens is None:
        opens = [(h + l) / 2 for h, l in zip(highs, lows)]
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })


# ==========================================
# Test 1: Equal Highs detection
# ==========================================
def test_equal_highs():
    """Equal highs: |price_i - price_j| <= tolerance e min_swing_distance respeitado."""
    engine = LiquidityEngine(equal_tolerance=0.0003, min_swing_distance=6)

    swings = [
        {"index": 5,  "price": 1.0850, "confirmed_at": 8},
        {"index": 15, "price": 1.0852, "confirmed_at": 18},  # diff=0.0002 <= 0.0003
    ]

    eq = engine._detect_equal_levels(swings)
    assert len(eq) == 1
    assert eq[0]["touches"] == 2
    assert abs(eq[0]["price"] - 1.0851) < 0.0001


# ==========================================
# Test 2: Equal Lows detection
# ==========================================
def test_equal_lows():
    """Equal lows funciona identicamente a equal highs."""
    engine = LiquidityEngine(equal_tolerance=0.0005, min_swing_distance=6)

    swings = [
        {"index": 10, "price": 0.9900, "confirmed_at": 13},
        {"index": 20, "price": 0.9903, "confirmed_at": 23},  # diff=0.0003 <= 0.0005
        {"index": 30, "price": 0.9901, "confirmed_at": 33},  # diff=0.0001 do primeiro
    ]

    eq = engine._detect_equal_levels(swings)
    assert len(eq) == 1
    assert eq[0]["touches"] == 3


# ==========================================
# Test 3: Reject excessive span
# ==========================================
def test_reject_excessive_span():
    """Grupos com span > equal_max_span sao descartados."""
    engine = LiquidityEngine(equal_tolerance=0.0003, min_swing_distance=6, equal_max_span=50)

    # Span = 100 > 50
    swings = [
        {"index": 5,   "price": 1.0850, "confirmed_at": 8},
        {"index": 105, "price": 1.0852, "confirmed_at": 108},
    ]

    eq = engine._detect_equal_levels(swings)
    assert len(eq) == 0

    # Span = 40 <= 50 -> aceito
    swings_ok = [
        {"index": 5,  "price": 1.0850, "confirmed_at": 8},
        {"index": 45, "price": 1.0852, "confirmed_at": 48},
    ]

    eq_ok = engine._detect_equal_levels(swings_ok)
    assert len(eq_ok) == 1


# ==========================================
# Test 4: Buy-side sweep confirmation (close < level)
# ==========================================
def test_buy_side_sweep_confirmation():
    """Buy-side sweep: high rompe acima do level, close retorna abaixo."""
    engine = LiquidityEngine(sweep_lookahead=3, sweep_cooldown=50)

    n = 25
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    buy_levels = [{"price": 1.10, "type": "swing", "side": "buy_side",
                   "touches": 1, "first_index": 3, "last_index": 3}]

    # Candle 10: high rompe acima de 1.10
    highs[10] = 1.12; opens[10] = 1.08; closes[10] = 1.11

    # Candle 11: close = 1.09 < 1.10 -> confirma
    closes[11] = 1.09; opens[11] = 1.10; highs[11] = 1.105; lows[11] = 1.085

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, buy_levels, [])

    assert len(sweeps) >= 1
    assert sweeps[0]["type"] == "buy_side"
    assert sweeps[0]["return_close"] < 1.10


# ==========================================
# Test 5: Sell-side sweep confirmation (close > level)
# ==========================================
def test_sell_side_sweep_confirmation():
    """Sell-side sweep: low rompe abaixo do level, close retorna acima."""
    engine = LiquidityEngine(sweep_lookahead=3, sweep_cooldown=50)

    n = 25
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    sell_levels = [{"price": 0.88, "type": "swing", "side": "sell_side",
                    "touches": 1, "first_index": 3, "last_index": 3}]

    # Candle 10: low rompe abaixo de 0.88
    lows[10] = 0.86; opens[10] = 0.92; closes[10] = 0.87

    # Candle 11: close = 0.89 > 0.88 -> confirma
    closes[11] = 0.89; opens[11] = 0.87; highs[11] = 0.90; lows[11] = 0.865

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, [], sell_levels)

    assert len(sweeps) >= 1
    assert sweeps[0]["type"] == "sell_side"
    assert sweeps[0]["return_close"] > 0.88


# ==========================================
# Test 6: Reject insufficient return (close not past level)
# ==========================================
def test_reject_insufficient_return():
    """Sweep NAO confirma se close nao ultrapassa o level nos N candles."""
    engine = LiquidityEngine(sweep_lookahead=2, sweep_cooldown=50)

    n = 20
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    buy_levels = [{"price": 1.05, "type": "swing", "side": "buy_side",
                   "touches": 1, "first_index": 2, "last_index": 2}]

    # Candle 10: high rompe acima de 1.05
    highs[10] = 1.08; opens[10] = 1.03; closes[10] = 1.07

    # Candle 11: close = 1.06 (acima do level 1.05, nao retorna)
    closes[11] = 1.06; opens[11] = 1.07; highs[11] = 1.075; lows[11] = 1.055

    # Candle 12: close = 1.055 (ainda acima do level)
    closes[12] = 1.055; opens[12] = 1.06; highs[12] = 1.065; lows[12] = 1.05

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, buy_levels, [])

    sweep_at_10 = [s for s in sweeps if s["break_index"] == 10]
    assert len(sweep_at_10) == 0, "Close nunca retorna abaixo do level, sweep nao deve confirmar"


# ==========================================
# Test 7: Sweep cooldown
# ==========================================
def test_sweep_cooldown():
    """Apos sweep, mesmo nivel bloqueado por N candles de cooldown."""
    engine = LiquidityEngine(sweep_lookahead=3, sweep_cooldown=10)

    n = 40
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    buy_levels = [{"price": 1.05, "type": "swing", "side": "buy_side",
                   "touches": 1, "first_index": 2, "last_index": 2}]

    # Sweep 1: candle 10
    highs[10] = 1.08; opens[10] = 1.03; closes[10] = 1.06
    closes[11] = 1.04; opens[11] = 1.06; highs[11] = 1.07; lows[11] = 1.03

    # Tentativa 2: candle 15 (dentro do cooldown de 10)
    highs[15] = 1.08; opens[15] = 1.03; closes[15] = 1.06
    closes[16] = 1.04; opens[16] = 1.06; highs[16] = 1.07; lows[16] = 1.03

    # Sweep 3: candle 25 (fora do cooldown)
    highs[25] = 1.08; opens[25] = 1.03; closes[25] = 1.06
    closes[26] = 1.04; opens[26] = 1.06; highs[26] = 1.07; lows[26] = 1.03

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, buy_levels, [])

    break_indices = [s["break_index"] for s in sweeps]
    assert 10 in break_indices
    assert 15 not in break_indices, "Candle 15 dentro do cooldown"
    assert 25 in break_indices, "Candle 25 fora do cooldown"


# ==========================================
# Test 8: Liquidity target after sweep
# ==========================================
def test_liquidity_target():
    """Apos buy-side sweep, target e sell-side abaixo; apos sell-side, target e buy-side acima."""
    engine = LiquidityEngine()

    # Buy-side sweep -> target = sell-side mais proximo abaixo
    buy_levels = [{"price": 1.10, "type": "swing", "side": "buy_side", "touches": 1,
                   "first_index": 5, "last_index": 5}]
    sell_levels = [
        {"price": 0.95, "type": "swing", "side": "sell_side", "touches": 1,
         "first_index": 3, "last_index": 3},
        {"price": 0.90, "type": "swing", "side": "sell_side", "touches": 1,
         "first_index": 2, "last_index": 2},
    ]

    last_sweep = {"type": "buy_side", "break_index": 10}
    target = engine._find_liquidity_target(last_sweep, 1.05, buy_levels, sell_levels)
    assert target == 0.95, f"Target deveria ser 0.95 (mais proximo abaixo), obteve {target}"

    # Sell-side sweep -> target = buy-side mais proximo acima
    last_sweep_sell = {"type": "sell_side", "break_index": 10}
    target_sell = engine._find_liquidity_target(last_sweep_sell, 0.92, buy_levels, sell_levels)
    assert target_sell == 1.10, f"Target deveria ser 1.10 (mais proximo acima), obteve {target_sell}"


# ==========================================
# Test 9: Sweep strength bounds (0.0 - 1.0)
# ==========================================
def test_strength_bounds():
    """sweep_strength sempre clamped entre 0.0 e 1.0."""
    engine = LiquidityEngine(sweep_lookahead=3)

    # Caso extremo forte
    s1 = engine._calculate_sweep_strength(
        break_distance=0.0100,
        candles_to_return=1,
        return_candle_open=1.08,
        return_candle_high=1.09,
        return_candle_low=1.07,
        return_candle_close=1.075,
        sweep_type="buy_side",
        avg_range_value=0.0010,  # break = 10x avg -> clamped a 1.0
    )
    assert 0.0 <= s1 <= 1.0

    # Caso extremo fraco
    s2 = engine._calculate_sweep_strength(
        break_distance=0.0001,
        candles_to_return=3,
        return_candle_open=1.0,
        return_candle_high=1.0,
        return_candle_low=1.0,
        return_candle_close=1.0,
        sweep_type="buy_side",
        avg_range_value=0.01,
    )
    assert 0.0 <= s2 <= 1.0

    # Caso: avg_range_value = 0
    s3 = engine._calculate_sweep_strength(
        break_distance=0.001,
        candles_to_return=1,
        return_candle_open=1.0,
        return_candle_high=1.01,
        return_candle_low=0.99,
        return_candle_close=1.005,
        sweep_type="sell_side",
        avg_range_value=0.0,
    )
    assert 0.0 <= s3 <= 1.0
