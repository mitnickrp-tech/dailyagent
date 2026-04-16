"""
tests/test_structure_engine.py - DailyAgent 2.1

10 testes pytest para StructureEngine.
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

from dailyagent.structure.engine import StructureEngine


# ==========================================
# Helpers
# ==========================================

def make_df(highs, lows, opens=None, closes=None):
    """Cria DataFrame de teste a partir de listas."""
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
# Test 1: Swing High Detection
# ==========================================
def test_swing_high_detection():
    """Swing High fractal simetrico com window=3."""
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n

    # Swing high claro em 10
    highs[7] = 1.1; highs[8] = 1.2; highs[9] = 1.3
    highs[10] = 1.5
    highs[11] = 1.3; highs[12] = 1.2; highs[13] = 1.1

    df = make_df(highs, lows)
    engine = StructureEngine(swing_window=3)
    sh, _ = engine._detect_swings(df)

    sh_indices = [s["index"] for s in sh]
    assert 10 in sh_indices
    assert sh[sh_indices.index(10)]["price"] == 1.5
    assert sh[sh_indices.index(10)]["confirmed_at"] == 13


# ==========================================
# Test 2: Swing Low Detection
# ==========================================
def test_swing_low_detection():
    """Swing Low fractal simetrico com window=3."""
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n

    # Swing low claro em 12
    lows[9] = 0.85; lows[10] = 0.8; lows[11] = 0.75
    lows[12] = 0.7
    lows[13] = 0.75; lows[14] = 0.8; lows[15] = 0.85

    df = make_df(highs, lows)
    engine = StructureEngine(swing_window=3)
    _, sl = engine._detect_swings(df)

    sl_indices = [s["index"] for s in sl]
    assert 12 in sl_indices
    assert sl[sl_indices.index(12)]["price"] == 0.7
    assert sl[sl_indices.index(12)]["confirmed_at"] == 15


# ==========================================
# Test 3: Trend Bullish (majority voting)
# ==========================================
def test_trend_bullish():
    """Tendencia bullish quando HH+HL predominam nos ultimos 6 points."""
    engine = StructureEngine()

    points = [
        {"type": "swing_high", "label": "HH", "index": 10, "price": 1.10, "confirmed_at": 13},
        {"type": "swing_low",  "label": "HL", "index": 15, "price": 1.05, "confirmed_at": 18},
        {"type": "swing_high", "label": "HH", "index": 20, "price": 1.15, "confirmed_at": 23},
        {"type": "swing_low",  "label": "HL", "index": 25, "price": 1.08, "confirmed_at": 28},
    ]

    assert engine._determine_trend(points) == "bullish"


# ==========================================
# Test 4: Trend Bearish (majority voting)
# ==========================================
def test_trend_bearish():
    """Tendencia bearish quando LH+LL predominam nos ultimos 6 points."""
    engine = StructureEngine()

    points = [
        {"type": "swing_high", "label": "LH", "index": 10, "price": 1.20, "confirmed_at": 13},
        {"type": "swing_low",  "label": "LL", "index": 15, "price": 1.10, "confirmed_at": 18},
        {"type": "swing_high", "label": "LH", "index": 20, "price": 1.15, "confirmed_at": 23},
        {"type": "swing_low",  "label": "LL", "index": 25, "price": 1.05, "confirmed_at": 28},
    ]

    assert engine._determine_trend(points) == "bearish"


# ==========================================
# Test 5: BOS Bullish with threshold
# ==========================================
def test_bos_bullish_threshold():
    """BOS Bullish: Close >= level * (1 + threshold). Rejeita se abaixo."""
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing high em 10 (price=1.5)
    highs[7] = 1.2; highs[8] = 1.3; highs[9] = 1.4
    highs[10] = 1.5
    highs[11] = 1.4; highs[12] = 1.3; highs[13] = 1.2

    # Candle 18: close abaixo do threshold (1.5 * 1.01 = 1.515) -> NAO gera BOS
    closes[18] = 1.51
    opens[18] = 1.40
    highs[18] = 1.52
    lows[18] = 1.39

    df = make_df(highs, lows, opens, closes)
    engine = StructureEngine(swing_window=3, bos_threshold=0.01, bos_range_lookback=1)
    sh, sl = engine._detect_swings(df)
    bos = engine._detect_bos(df, sh, sl)

    bull_at_18 = [b for b in bos if b["direction"] == "bullish" and b["index"] == 18]
    assert len(bull_at_18) == 0, "Close 1.51 < threshold 1.515 nao deve gerar BOS"

    # Candle 20: close acima do threshold -> GERA BOS
    closes[20] = 1.52
    opens[20] = 1.40
    highs[20] = 1.53
    lows[20] = 1.39

    df2 = make_df(highs, lows, opens, closes)
    sh2, sl2 = engine._detect_swings(df2)
    bos2 = engine._detect_bos(df2, sh2, sl2)

    bull_bos = [b for b in bos2 if b["direction"] == "bullish"]
    assert len(bull_bos) > 0, "Close 1.52 >= 1.515 deve gerar BOS bullish"


# ==========================================
# Test 6: BOS Bearish with threshold
# ==========================================
def test_bos_bearish_threshold():
    """BOS Bearish: Close <= level * (1 - threshold). Simetrico ao bullish."""
    engine = StructureEngine(swing_window=3, bos_threshold=0.01, bos_range_lookback=1)

    n = 30
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing low em 10 (price=0.80)
    lows[7] = 0.88; lows[8] = 0.85; lows[9] = 0.82
    lows[10] = 0.80
    lows[11] = 0.82; lows[12] = 0.85; lows[13] = 0.88

    # Candle 22: close = 0.795 > 0.80*0.99=0.792 -> NAO gera BOS
    closes[22] = 0.795
    opens[22] = 0.92
    highs[22] = 0.93
    lows[22] = 0.79

    df = make_df(highs, lows, opens, closes)
    sh, sl = engine._detect_swings(df)
    bos = engine._detect_bos(df, sh, sl)
    bear_at_22 = [b for b in bos if b["direction"] == "bearish" and b["index"] == 22]
    assert len(bear_at_22) == 0

    # Candle 24: close = 0.790 <= 0.792 -> GERA BOS
    closes[24] = 0.790
    opens[24] = 0.92
    highs[24] = 0.93
    lows[24] = 0.785

    df2 = make_df(highs, lows, opens, closes)
    sh2, sl2 = engine._detect_swings(df2)
    bos2 = engine._detect_bos(df2, sh2, sl2)
    bear_bos = [b for b in bos2 if b["direction"] == "bearish"]
    assert len(bear_bos) > 0


# ==========================================
# Test 7: BOS rejects weak candle (low body_ratio)
# ==========================================
def test_bos_reject_weak_candle():
    """BOS nao dispara se body_ratio <= bos_body_ratio_min."""
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing high em 10 (price=1.5)
    highs[7] = 1.2; highs[8] = 1.3; highs[9] = 1.4
    highs[10] = 1.5
    highs[11] = 1.4; highs[12] = 1.3; highs[13] = 1.2

    # Candle 18: close ultrapassa threshold MAS body_ratio muito pequeno (doji)
    # close=1.52, open=1.519 -> body = 0.001, range = 1.53-0.9 = 0.63 -> ratio = 0.0016
    closes[18] = 1.52
    opens[18] = 1.519
    highs[18] = 1.53
    lows[18] = 0.9  # range enorme, body minimo -> doji

    df = make_df(highs, lows, opens, closes)
    engine = StructureEngine(swing_window=3, bos_threshold=0.001, bos_range_lookback=1)
    sh, sl = engine._detect_swings(df)
    bos = engine._detect_bos(df, sh, sl)

    bull_at_18 = [b for b in bos if b["direction"] == "bullish" and b["index"] == 18]
    assert len(bull_at_18) == 0, "Candle doji (body_ratio ~0) nao deve gerar BOS"


# ==========================================
# Test 8: CHoCH Bullish quality
# ==========================================
def test_choch_bullish_quality():
    """CHoCH Bullish: mercado bearish + close > LH + candle de qualidade."""
    engine = StructureEngine(
        swing_window=3,
        choch_body_ratio_min=0.5,
        choch_range_lookback=2,
        choch_range_multiplier=1.0,
    )

    # Cenario: tendencia bearish (LH + LL) seguida de rompimento acima do LH
    n = 40
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing highs descendentes -> LH
    # SH1 em 5: price=1.20 (base)
    highs[2] = 1.1; highs[3] = 1.15; highs[4] = 1.18
    highs[5] = 1.20
    highs[6] = 1.18; highs[7] = 1.15; highs[8] = 1.1

    # SH2 em 15: price=1.15 -> LH
    highs[12] = 1.1; highs[13] = 1.12; highs[14] = 1.13
    highs[15] = 1.15
    highs[16] = 1.13; highs[17] = 1.12; highs[18] = 1.1

    # Swing lows descendentes -> LL
    # SL1 em 10: price=0.85
    lows[7] = 0.88; lows[8] = 0.87; lows[9] = 0.86
    lows[10] = 0.85
    lows[11] = 0.86; lows[12] = 0.87; lows[13] = 0.88

    # SL2 em 20: price=0.80 -> LL
    lows[17] = 0.84; lows[18] = 0.83; lows[19] = 0.82
    lows[20] = 0.80
    lows[21] = 0.82; lows[22] = 0.83; lows[23] = 0.84

    # CHoCH candle em 25: close > LH (1.15), corpo forte
    closes[25] = 1.18
    opens[25] = 1.05
    highs[25] = 1.19
    lows[25] = 1.04   # range=0.15, body=0.13, ratio=0.867

    df = make_df(highs, lows, opens, closes)
    result = engine.analyze(df)

    assert result is not None
    choch_bull = [c for c in result["choch_events"] if c["direction"] == "bullish"]
    assert len(choch_bull) > 0, f"CHoCH bullish esperado. CHoCH events: {result['choch_events']}"


# ==========================================
# Test 9: CHoCH Bearish quality
# ==========================================
def test_choch_bearish_quality():
    """CHoCH Bearish: mercado bullish + close < HL + candle de qualidade."""
    engine = StructureEngine(
        swing_window=3,
        choch_body_ratio_min=0.5,
        choch_range_lookback=2,
        choch_range_multiplier=1.0,
    )

    n = 40
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing highs ascendentes -> HH
    # SH1 em 5: price=1.10
    highs[2] = 1.02; highs[3] = 1.05; highs[4] = 1.08
    highs[5] = 1.10
    highs[6] = 1.08; highs[7] = 1.05; highs[8] = 1.02

    # SH2 em 15: price=1.20 -> HH
    highs[12] = 1.12; highs[13] = 1.15; highs[14] = 1.18
    highs[15] = 1.20
    highs[16] = 1.18; highs[17] = 1.15; highs[18] = 1.12

    # Swing lows ascendentes -> HL
    # SL1 em 10: price=0.85
    lows[7] = 0.88; lows[8] = 0.87; lows[9] = 0.86
    lows[10] = 0.85
    lows[11] = 0.86; lows[12] = 0.87; lows[13] = 0.88

    # SL2 em 20: price=0.88 -> HL
    lows[17] = 0.92; lows[18] = 0.91; lows[19] = 0.90
    lows[20] = 0.88
    lows[21] = 0.90; lows[22] = 0.91; lows[23] = 0.92

    # CHoCH candle em 25: close < HL (0.88), corpo forte
    closes[25] = 0.85
    opens[25] = 0.98
    highs[25] = 0.99
    lows[25] = 0.84   # range=0.15, body=0.13, ratio=0.867

    df = make_df(highs, lows, opens, closes)
    result = engine.analyze(df)

    assert result is not None
    choch_bear = [c for c in result["choch_events"] if c["direction"] == "bearish"]
    assert len(choch_bear) > 0, f"CHoCH bearish esperado. CHoCH events: {result['choch_events']}"


# ==========================================
# Test 10: No lookahead bias
# ==========================================
def test_no_lookahead_bias():
    """
    Swings nos ultimos N candles NAO sao detectados.
    confirmed_at = index + swing_window.
    BOS so usa swings confirmados.
    """
    engine = StructureEngine(swing_window=3)

    n = 20
    highs = [1.0] * n
    lows = [0.9] * n

    # Swing high "potencial" em 18 (ultimos 2 candles a direita: 19 - insuficiente)
    highs[18] = 2.0

    df = make_df(highs, lows)
    sh, _ = engine._detect_swings(df)

    sh_indices = [s["index"] for s in sh]
    assert 18 not in sh_indices, "Swing no limite nao deveria ser detectado"

    # Todos os swings devem ter confirmed_at = index + window
    for s in sh:
        assert s["confirmed_at"] == s["index"] + 3
