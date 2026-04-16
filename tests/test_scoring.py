"""
tests/test_scoring.py - DailyAgent 2.1

Testes pytest para ScoringEngine (score composto probabilistico).
Usa mocks sinteticos, sem dependencias externas.
"""

import sys
import os
import types
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

from dailyagent.scoring.engine import ScoringEngine


# ==========================================
# Helpers - mock data builders
# ==========================================

def mock_structure(
    trend="bullish",
    structure_strength=0.7,
    last_bos="bullish",
    last_choch="bullish",
):
    return {
        "trend": trend,
        "last_bos": last_bos,
        "last_choch": last_choch,
        "structure_strength": structure_strength,
        "swing_highs": [],
        "swing_lows": [],
        "structure_points": [],
        "bos_events": [],
        "choch_events": [],
    }


def mock_liquidity(
    sweep_type="sell_side",
    strength=0.7,
    liquidity_target=1.10,
):
    return {
        "sweep": sweep_type,
        "strength": strength,
        "liquidity_target": liquidity_target,
        "equal_highs": [],
        "equal_lows": [],
        "sweeps": [],
        "buy_side_levels": [],
        "sell_side_levels": [],
    }


def mock_setup(
    direction="buy",
    sweep_strength=0.7,
    level_type="equal",
    level_touches=2,
    body_ratio=0.85,
    entry_zone=None,
    invalid_level=0.95,
    target_level=1.10,
    displacement_score=0.75,
):
    if entry_zone is None:
        entry_zone = [0.98, 1.02]
    return {
        "direction": direction,
        "sweep": {
            "type": "sell_side" if direction == "buy" else "buy_side",
            "break_index": 28,
            "return_index": 30,
            "level_price": 0.99 if direction == "buy" else 1.01,
            "break_low": 0.95 if direction == "buy" else None,
            "break_high": 1.05 if direction == "sell" else None,
            "return_close": 1.005 if direction == "buy" else 0.995,
            "break_distance": 0.005,
            "strength": sweep_strength,
            "level_type": level_type,
            "level_touches": level_touches,
        },
        "choch": {
            "direction": "bullish" if direction == "buy" else "bearish",
            "index": 34,
            "level": 1.01,
            "close": 1.015 if direction == "buy" else 0.985,
            "prev_trend": "bearish" if direction == "buy" else "bullish",
        },
        "displacement": {
            "index": 35,
            "open": entry_zone[0],
            "close": entry_zone[1],
            "high": max(entry_zone) + 0.005,
            "low": min(entry_zone) - 0.005,
            "range": 0.05,
            "body_ratio": body_ratio,
            "direction": "bullish" if direction == "buy" else "bearish",
        },
        "entry_zone": entry_zone,
        "invalid_level": invalid_level,
        "target_level": target_level,
        "structure_trend": "bullish" if direction == "buy" else "bearish",
        "last_bos": "bullish" if direction == "buy" else "bearish",
        "last_choch": "bullish" if direction == "buy" else "bearish",
        "sweep_type": "sell_side" if direction == "buy" else "buy_side",
        "sweep_strength": sweep_strength,
        "displacement_score": displacement_score,
    }


# ==========================================
# Test 1: Score final between 0.0 and 1.0
# ==========================================
def test_score_bounds():
    """final_score deve sempre estar entre 0.0 e 1.0."""
    engine = ScoringEngine()

    structure = mock_structure()
    liquidity = mock_liquidity()
    setup = mock_setup()

    result = engine.score(structure, liquidity, setup)

    assert 0.0 <= result["final_score"] <= 1.0


# ==========================================
# Test 2: All 6 components present
# ==========================================
def test_all_components_present():
    """Output deve conter todos os 6 componentes."""
    engine = ScoringEngine()

    result = engine.score(mock_structure(), mock_liquidity(), mock_setup())

    expected_keys = {
        "structure_score", "liquidity_score", "displacement_score",
        "session_score", "zone_score", "risk_score",
    }
    assert expected_keys == set(result["components"].keys())

    for key, val in result["components"].items():
        assert 0.0 <= val <= 1.0, f"{key} = {val} fora de [0.0, 1.0]"


# ==========================================
# Test 3: Classification STRONG
# ==========================================
def test_classification_strong():
    """Setup forte com todos os fatores alinhados -> STRONG."""
    engine = ScoringEngine()

    structure = mock_structure(trend="bullish", structure_strength=0.9, last_bos="bullish")
    liquidity = mock_liquidity(strength=0.9)
    setup = mock_setup(
        direction="buy",
        sweep_strength=0.9,
        level_type="equal",
        level_touches=3,
        body_ratio=0.95,
        entry_zone=[0.98, 1.02],
        invalid_level=0.90,
        target_level=1.20,
        displacement_score=0.9,
    )

    result = engine.score(structure, liquidity, setup)

    assert result["classification"] == "STRONG"
    assert result["trade_candidate"] is True
    assert result["final_score"] >= 0.80


# ==========================================
# Test 4: Classification IGNORE for weak setup
# ==========================================
def test_classification_ignore():
    """Setup fraco com penalidades multiplas -> IGNORE."""
    engine = ScoringEngine()

    # Contra tendencia + sem target + displacement fraco
    structure = mock_structure(trend="bearish", structure_strength=0.2, last_bos=None)
    liquidity = mock_liquidity(strength=0.2, liquidity_target=None)
    setup = mock_setup(
        direction="buy",
        sweep_strength=0.2,
        level_type="swing",
        level_touches=1,
        body_ratio=0.5,
        entry_zone=[0.99, 1.01],
        invalid_level=0.98,
        target_level=None,
        displacement_score=0.2,
    )

    result = engine.score(structure, liquidity, setup)

    assert result["classification"] == "IGNORE"
    assert result["trade_candidate"] is False
    assert "counter_trend" in result["penalties_applied"]
    assert "no_target" in result["penalties_applied"]
    assert "weak_displacement" in result["penalties_applied"]


# ==========================================
# Test 5: Counter-trend penalty applied
# ==========================================
def test_penalty_counter_trend():
    """Buy contra bearish deve receber penalidade de 0.7."""
    engine = ScoringEngine()

    # Aligned: buy + bullish
    structure_aligned = mock_structure(trend="bullish")
    liquidity = mock_liquidity()
    setup = mock_setup(direction="buy", body_ratio=0.9)

    result_aligned = engine.score(structure_aligned, liquidity, setup)

    # Counter: buy + bearish
    structure_counter = mock_structure(trend="bearish")
    result_counter = engine.score(structure_counter, liquidity, setup)

    assert result_counter["final_score"] < result_aligned["final_score"]
    assert "counter_trend" in result_counter["penalties_applied"]
    assert "counter_trend" not in result_aligned["penalties_applied"]


# ==========================================
# Test 6: No target penalty applied
# ==========================================
def test_penalty_no_target():
    """Sem target_level deve receber penalidade de 0.8."""
    engine = ScoringEngine()

    structure = mock_structure()
    liquidity = mock_liquidity()

    setup_with_target = mock_setup(target_level=1.10, body_ratio=0.9)
    setup_no_target = mock_setup(target_level=None, body_ratio=0.9)

    result_with = engine.score(structure, liquidity, setup_with_target)
    result_without = engine.score(structure, liquidity, setup_no_target)

    assert result_without["final_score"] < result_with["final_score"]
    assert "no_target" in result_without["penalties_applied"]
    assert "no_target" not in result_with["penalties_applied"]


# ==========================================
# Test 7: Weak displacement penalty applied
# ==========================================
def test_penalty_weak_displacement():
    """Displacement com body_ratio < 0.8 deve receber penalidade."""
    engine = ScoringEngine()

    structure = mock_structure()
    liquidity = mock_liquidity()

    setup_strong = mock_setup(body_ratio=0.9, displacement_score=0.8)
    setup_weak = mock_setup(body_ratio=0.6, displacement_score=0.5)

    result_strong = engine.score(structure, liquidity, setup_strong)
    result_weak = engine.score(structure, liquidity, setup_weak)

    assert "weak_displacement" not in result_strong["penalties_applied"]
    assert "weak_displacement" in result_weak["penalties_applied"]


# ==========================================
# Test 8: Session score is 0.5 (provisional)
# ==========================================
def test_session_score_provisional():
    """session_score deve ser 0.5 (provisorio)."""
    engine = ScoringEngine()

    result = engine.score(mock_structure(), mock_liquidity(), mock_setup())

    assert result["components"]["session_score"] == 0.5


# ==========================================
# Test 9: Risk score with good RR
# ==========================================
def test_risk_score_good_rr():
    """RR >= 2.0 deve dar risk_score = 1.0."""
    engine = ScoringEngine()

    # Buy: entry_mid=1.0, invalid=0.95, target=1.15
    # risk=0.05, reward=0.15, RR=3.0 >= 2.0
    setup = mock_setup(
        direction="buy",
        entry_zone=[0.99, 1.01],
        invalid_level=0.95,
        target_level=1.15,
        body_ratio=0.9,
    )

    result = engine.score(mock_structure(), mock_liquidity(), setup)

    assert result["components"]["risk_score"] == 1.0


# ==========================================
# Test 10: Risk score without target
# ==========================================
def test_risk_score_no_target():
    """Sem target, risk_score = 0.2."""
    engine = ScoringEngine()

    setup = mock_setup(
        direction="buy",
        entry_zone=[0.99, 1.01],
        invalid_level=0.95,
        target_level=None,
        body_ratio=0.9,
    )

    result = engine.score(mock_structure(), mock_liquidity(), setup)

    assert result["components"]["risk_score"] == 0.2


# ==========================================
# Test 11: Sell setup scoring
# ==========================================
def test_sell_setup_scoring():
    """Sell setup deve funcionar simetricamente ao buy."""
    engine = ScoringEngine()

    structure = mock_structure(trend="bearish", last_bos="bearish", last_choch="bearish")
    liquidity = mock_liquidity(sweep_type="buy_side", strength=0.8)
    setup = mock_setup(
        direction="sell",
        sweep_strength=0.8,
        level_type="equal",
        level_touches=2,
        body_ratio=0.9,
        entry_zone=[1.01, 0.97],
        invalid_level=1.05,
        target_level=0.90,
        displacement_score=0.8,
    )

    result = engine.score(structure, liquidity, setup)

    assert 0.0 <= result["final_score"] <= 1.0
    assert result["classification"] in ("STRONG", "VALID", "IGNORE")
    assert "counter_trend" not in result["penalties_applied"]


# ==========================================
# Test 12: Deterministic output
# ==========================================
def test_deterministic():
    """Mesma entrada deve produzir mesma saida."""
    engine = ScoringEngine()

    structure = mock_structure()
    liquidity = mock_liquidity()
    setup = mock_setup()

    r1 = engine.score(structure, liquidity, setup)
    r2 = engine.score(structure, liquidity, setup)

    assert r1["final_score"] == r2["final_score"]
    assert r1["classification"] == r2["classification"]
    assert r1["components"] == r2["components"]
    assert r1["penalties_applied"] == r2["penalties_applied"]


# ==========================================
# Test 13: Weights sum to 1.0
# ==========================================
def test_weights_sum():
    """Pesos dos componentes devem somar 1.0."""
    from dailyagent.scoring.engine import (
        WEIGHT_STRUCTURE, WEIGHT_LIQUIDITY, WEIGHT_DISPLACEMENT,
        WEIGHT_SESSION, WEIGHT_ZONE, WEIGHT_RISK,
    )

    total = (
        WEIGHT_STRUCTURE + WEIGHT_LIQUIDITY + WEIGHT_DISPLACEMENT
        + WEIGHT_SESSION + WEIGHT_ZONE + WEIGHT_RISK
    )
    assert abs(total - 1.0) < 1e-9, f"Pesos somam {total}, esperado 1.0"


# ==========================================
# Test 14: Equal level bonus in liquidity score
# ==========================================
def test_equal_level_bonus():
    """Sweep em equal level deve dar liquidity_score maior que swing isolado."""
    engine = ScoringEngine()

    structure = mock_structure()
    liquidity = mock_liquidity()

    setup_equal = mock_setup(level_type="equal", level_touches=3, sweep_strength=0.5)
    setup_swing = mock_setup(level_type="swing", level_touches=1, sweep_strength=0.5)

    r_equal = engine.score(structure, liquidity, setup_equal)
    r_swing = engine.score(structure, liquidity, setup_swing)

    assert r_equal["components"]["liquidity_score"] > r_swing["components"]["liquidity_score"]


# ==========================================
# Test 15: Risk score zero risk returns 0.0
# ==========================================
def test_risk_score_zero_risk():
    """risk <= 0 deve retornar 0.0 (nao 1.0)."""
    engine = ScoringEngine()

    # entry_mid = 1.0, invalid = 1.0 -> risk = 0
    setup = mock_setup(
        direction="buy",
        entry_zone=[0.99, 1.01],
        invalid_level=1.0,
        target_level=1.10,
        body_ratio=0.9,
    )

    result = engine.score(mock_structure(), mock_liquidity(), setup)

    assert result["components"]["risk_score"] == 0.0


# ==========================================
# Test 16: New thresholds are more restrictive
# ==========================================
def test_thresholds_calibrated():
    """THRESHOLD_STRONG=0.80, THRESHOLD_VALID=0.72."""
    from dailyagent.scoring.engine import THRESHOLD_STRONG, THRESHOLD_VALID

    assert THRESHOLD_STRONG == 0.80
    assert THRESHOLD_VALID == 0.72
    assert THRESHOLD_STRONG > THRESHOLD_VALID


# ==========================================
# Test 17: Structure score does not saturate easily
# ==========================================
def test_structure_score_no_saturation():
    """
    Com structure_strength=0.7 e todos os bonus, structure_score
    nao deve atingir 1.0 (max bonus = 0.10+0.05+0.03 = 0.18).
    0.7 + 0.18 = 0.88 < 1.0
    """
    engine = ScoringEngine()

    structure = mock_structure(
        trend="bullish",
        structure_strength=0.7,
        last_bos="bullish",
        last_choch="bullish",
    )
    setup = mock_setup(direction="buy")

    result = engine.score(structure, mock_liquidity(), setup)

    ss = result["components"]["structure_score"]
    assert ss < 1.0, f"structure_score={ss} nao deveria saturar com strength=0.7"
    assert abs(ss - 0.88) < 0.01, f"Esperado ~0.88, obteve {ss}"
