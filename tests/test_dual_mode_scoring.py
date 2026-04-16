"""
tests/test_dual_mode_scoring.py - DailyAgent 2.1

Testes para arquitetura dual-mode:
  - ForexScoringEngine
  - BinaryScoringEngine
  - Factory (get_scoring_engine)
  - Shared helpers

Sem dependencias externas. Usa mocks sinteticos.
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

from dailyagent.scoring.forex_engine import ForexScoringEngine
from dailyagent.scoring.binary_engine import BinaryScoringEngine
from dailyagent.scoring.factory import get_scoring_engine
from dailyagent.scoring.shared import (
    clamp, classify,
    calc_structure_score, calc_liquidity_score,
    calc_displacement_score, calc_session_score,
    is_counter_trend, is_weak_displacement,
)


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


def mock_liquidity(sweep_type="sell_side", strength=0.7):
    return {
        "sweep": sweep_type,
        "strength": strength,
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
    setup_index=45,
    sweep_index=28,
    choch_index=34,
    displacement_index=35,
):
    if entry_zone is None:
        entry_zone = [0.98, 1.02]
    return {
        "direction": direction,
        "setup_type": "sweep_choch_displacement",
        "sweep": {
            "type": "sell_side" if direction == "buy" else "buy_side",
            "break_index": sweep_index,
            "return_index": sweep_index + 2,
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
            "index": choch_index,
            "level": 1.01,
            "close": 1.015 if direction == "buy" else 0.985,
            "prev_trend": "bearish" if direction == "buy" else "bullish",
        },
        "displacement": {
            "index": displacement_index,
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
        "setup_index": setup_index,
        "sweep_index": sweep_index,
        "choch_index": choch_index,
        "displacement_index": displacement_index,
        "structure_trend": "bullish" if direction == "buy" else "bearish",
        "last_bos": "bullish" if direction == "buy" else "bearish",
        "last_choch": "bullish" if direction == "buy" else "bearish",
        "sweep_type": "sell_side" if direction == "buy" else "buy_side",
        "sweep_strength": sweep_strength,
        "displacement_score": displacement_score,
    }


# ==========================================================================
# SHARED HELPERS TESTS
# ==========================================================================

class TestSharedHelpers:
    def test_clamp_normal(self):
        assert clamp(0.5) == 0.5

    def test_clamp_below(self):
        assert clamp(-0.3) == 0.0

    def test_clamp_above(self):
        assert clamp(1.5) == 1.0

    def test_classify_strong(self):
        assert classify(0.85, 0.80, 0.72) == "STRONG"

    def test_classify_valid(self):
        assert classify(0.75, 0.80, 0.72) == "VALID"

    def test_classify_ignore(self):
        assert classify(0.50, 0.80, 0.72) == "IGNORE"

    def test_calc_structure_score_aligned(self):
        structure = mock_structure(trend="bullish", structure_strength=0.7, last_bos="bullish", last_choch="bullish")
        setup = mock_setup(direction="buy")
        score = calc_structure_score(structure, setup)
        # 0.7 + 0.10 (trend) + 0.05 (bos) + 0.03 (choch) = 0.88
        assert abs(score - 0.88) < 0.01

    def test_calc_structure_score_no_bonus(self):
        structure = mock_structure(trend="range", structure_strength=0.5, last_bos=None, last_choch=None)
        setup = mock_setup(direction="buy")
        score = calc_structure_score(structure, setup)
        assert abs(score - 0.5) < 0.01

    def test_calc_liquidity_score_with_bonus(self):
        setup = mock_setup(sweep_strength=0.6, level_type="equal", level_touches=3)
        score = calc_liquidity_score(setup)
        # 0.6 + 0.10 (equal) + 0.05 (touches>=3) = 0.75
        assert abs(score - 0.75) < 0.01

    def test_calc_displacement_score(self):
        setup = mock_setup(displacement_score=0.8)
        assert calc_displacement_score(setup) == 0.8

    def test_calc_session_score(self):
        assert calc_session_score() == 0.5

    def test_is_counter_trend_true(self):
        assert is_counter_trend({"trend": "bearish"}, {"direction": "buy"}) is True
        assert is_counter_trend({"trend": "bullish"}, {"direction": "sell"}) is True

    def test_is_counter_trend_false(self):
        assert is_counter_trend({"trend": "bullish"}, {"direction": "buy"}) is False
        assert is_counter_trend({"trend": "range"}, {"direction": "buy"}) is False

    def test_is_weak_displacement(self):
        assert is_weak_displacement({"displacement": {"body_ratio": 0.5}}) is True
        assert is_weak_displacement({"displacement": {"body_ratio": 0.9}}) is False


# ==========================================================================
# FOREX SCORING ENGINE TESTS
# ==========================================================================

class TestForexScoringEngine:
    def test_output_has_mode_forex(self):
        engine = ForexScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup())
        assert result["mode"] == "forex"

    def test_score_bounds(self):
        engine = ForexScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup())
        assert 0.0 <= result["final_score"] <= 1.0

    def test_all_forex_components(self):
        engine = ForexScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup())
        expected = {"structure_score", "liquidity_score", "displacement_score",
                    "session_score", "zone_score", "risk_score"}
        assert expected == set(result["components"].keys())

    def test_classification_strong(self):
        engine = ForexScoringEngine()
        structure = mock_structure(trend="bullish", structure_strength=0.9, last_bos="bullish")
        setup = mock_setup(
            direction="buy", sweep_strength=0.9, level_type="equal",
            level_touches=3, body_ratio=0.95,
            entry_zone=[0.98, 1.02], invalid_level=0.90, target_level=1.20,
            displacement_score=0.9,
        )
        result = engine.score(structure, mock_liquidity(), setup)
        assert result["classification"] == "STRONG"
        assert result["trade_candidate"] is True

    def test_classification_ignore_with_penalties(self):
        engine = ForexScoringEngine()
        structure = mock_structure(trend="bearish", structure_strength=0.2, last_bos=None)
        setup = mock_setup(
            direction="buy", sweep_strength=0.2, level_type="swing",
            level_touches=1, body_ratio=0.5, target_level=None,
            displacement_score=0.2,
        )
        result = engine.score(structure, mock_liquidity(), setup)
        assert result["classification"] == "IGNORE"
        assert "counter_trend" in result["penalties_applied"]
        assert "no_target" in result["penalties_applied"]
        assert "weak_displacement" in result["penalties_applied"]

    def test_forex_weights_sum(self):
        from dailyagent.scoring.forex_engine import (
            WEIGHT_STRUCTURE, WEIGHT_LIQUIDITY, WEIGHT_DISPLACEMENT,
            WEIGHT_SESSION, WEIGHT_ZONE, WEIGHT_RISK,
        )
        total = WEIGHT_STRUCTURE + WEIGHT_LIQUIDITY + WEIGHT_DISPLACEMENT + WEIGHT_SESSION + WEIGHT_ZONE + WEIGHT_RISK
        assert abs(total - 1.0) < 1e-9

    def test_forex_deterministic(self):
        engine = ForexScoringEngine()
        s, l, setup = mock_structure(), mock_liquidity(), mock_setup()
        r1 = engine.score(s, l, setup)
        r2 = engine.score(s, l, setup)
        assert r1["final_score"] == r2["final_score"]
        assert r1["components"] == r2["components"]

    def test_forex_risk_score_zero_risk(self):
        engine = ForexScoringEngine()
        setup = mock_setup(
            direction="buy", entry_zone=[0.99, 1.01],
            invalid_level=1.0, target_level=1.10, body_ratio=0.9,
        )
        result = engine.score(mock_structure(), mock_liquidity(), setup)
        assert result["components"]["risk_score"] == 0.0

    def test_forex_risk_score_good_rr(self):
        engine = ForexScoringEngine()
        setup = mock_setup(
            direction="buy", entry_zone=[0.99, 1.01],
            invalid_level=0.95, target_level=1.15, body_ratio=0.9,
        )
        result = engine.score(mock_structure(), mock_liquidity(), setup)
        assert result["components"]["risk_score"] == 1.0


# ==========================================================================
# BINARY SCORING ENGINE TESTS
# ==========================================================================

class TestBinaryScoringEngine:
    def test_output_has_mode_binary(self):
        engine = BinaryScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup(), total_candles=50)
        assert result["mode"] == "binary"

    def test_output_has_expiration(self):
        engine = BinaryScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup(),
                              expiration="M1", total_candles=50)
        assert result["expiration"] == "M1"

    def test_score_bounds(self):
        engine = BinaryScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup(), total_candles=50)
        assert 0.0 <= result["final_score"] <= 1.0

    def test_all_binary_components(self):
        engine = BinaryScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup(), total_candles=50)
        expected = {"structure_score", "liquidity_score", "displacement_score",
                    "timing_score", "expiry_score", "session_score"}
        assert expected == set(result["components"].keys())

    def test_binary_no_zone_no_risk(self):
        """Binary nao tem zone_score nem risk_score."""
        engine = BinaryScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup(), total_candles=50)
        assert "zone_score" not in result["components"]
        assert "risk_score" not in result["components"]

    def test_binary_weights_sum(self):
        from dailyagent.scoring.binary_engine import (
            WEIGHT_STRUCTURE, WEIGHT_LIQUIDITY, WEIGHT_DISPLACEMENT,
            WEIGHT_TIMING, WEIGHT_EXPIRY, WEIGHT_SESSION,
        )
        total = (WEIGHT_STRUCTURE + WEIGHT_LIQUIDITY + WEIGHT_DISPLACEMENT
                 + WEIGHT_TIMING + WEIGHT_EXPIRY + WEIGHT_SESSION)
        assert abs(total - 1.0) < 1e-9

    def test_timing_score_recent_events(self):
        """Eventos recentes devem dar timing_score alto."""
        engine = BinaryScoringEngine()
        # Events very close to last candle
        setup = mock_setup(sweep_index=45, choch_index=47, displacement_index=48, setup_index=48)
        result = engine.score(mock_structure(), mock_liquidity(), setup, total_candles=50)
        assert result["components"]["timing_score"] > 0.7

    def test_timing_score_old_events(self):
        """Eventos antigos devem dar timing_score baixo."""
        engine = BinaryScoringEngine()
        # Events far from last candle (age ~40 candles, ref_window=20)
        setup = mock_setup(sweep_index=5, choch_index=7, displacement_index=8, setup_index=8)
        result = engine.score(mock_structure(), mock_liquidity(), setup, total_candles=50)
        assert result["components"]["timing_score"] < 0.3

    def test_expiry_score_within_window(self):
        """Eventos dentro da janela de expiracao devem dar expiry_score alto."""
        engine = BinaryScoringEngine()
        # M5 windows: sweep=10, choch=7, displacement=5
        # Ages: sweep=4, choch=2, displacement=1 -> all within window
        setup = mock_setup(sweep_index=45, choch_index=47, displacement_index=48, setup_index=48)
        result = engine.score(mock_structure(), mock_liquidity(), setup,
                              expiration="M5", total_candles=50)
        assert result["components"]["expiry_score"] > 0.8

    def test_stale_setup_penalty(self):
        """Displacement alem do stale_threshold deve receber penalidade."""
        engine = BinaryScoringEngine()
        # M5 stale_threshold = 15
        # displacement_index=10, total=50 -> age=39 > 15 = stale
        setup = mock_setup(sweep_index=5, choch_index=8, displacement_index=10, setup_index=10)
        result = engine.score(mock_structure(), mock_liquidity(), setup,
                              expiration="M5", total_candles=50)
        assert "stale_setup" in result["penalties_applied"]

    def test_no_stale_penalty_when_fresh(self):
        """Displacement recente nao deve receber stale penalty."""
        engine = BinaryScoringEngine()
        # M5 stale_threshold = 15
        # displacement_index=45, total=50 -> age=4 < 15
        setup = mock_setup(sweep_index=40, choch_index=43, displacement_index=45, setup_index=45)
        result = engine.score(mock_structure(), mock_liquidity(), setup,
                              expiration="M5", total_candles=50)
        assert "stale_setup" not in result["penalties_applied"]

    def test_binary_counter_trend_penalty(self):
        """Binary tambem aplica penalty de contra-tendencia."""
        engine = BinaryScoringEngine()
        structure = mock_structure(trend="bearish")
        setup = mock_setup(direction="buy")
        result = engine.score(structure, mock_liquidity(), setup, total_candles=50)
        assert "counter_trend" in result["penalties_applied"]

    def test_binary_deterministic(self):
        engine = BinaryScoringEngine()
        s, l, setup = mock_structure(), mock_liquidity(), mock_setup()
        r1 = engine.score(s, l, setup, total_candles=50)
        r2 = engine.score(s, l, setup, total_candles=50)
        assert r1["final_score"] == r2["final_score"]
        assert r1["components"] == r2["components"]

    def test_m1_vs_m15_expiry_scores_differ(self):
        """M1 e M15 devem produzir expiry_scores diferentes para mesmo setup."""
        engine = BinaryScoringEngine()
        setup = mock_setup(sweep_index=35, choch_index=38, displacement_index=40, setup_index=40)
        r_m1 = engine.score(mock_structure(), mock_liquidity(), setup, expiration="M1", total_candles=50)
        r_m15 = engine.score(mock_structure(), mock_liquidity(), setup, expiration="M15", total_candles=50)
        # M1 has tighter windows, so expiry should be lower for older events
        assert r_m1["components"]["expiry_score"] != r_m15["components"]["expiry_score"]

    def test_total_candles_none_fallback(self):
        """Se total_candles=None, usa setup_index + 10."""
        engine = BinaryScoringEngine()
        setup = mock_setup(setup_index=40)
        result = engine.score(mock_structure(), mock_liquidity(), setup, total_candles=None)
        assert 0.0 <= result["final_score"] <= 1.0


# ==========================================================================
# FACTORY TESTS
# ==========================================================================

class TestFactory:
    def test_get_forex_engine(self):
        engine = get_scoring_engine("forex")
        assert isinstance(engine, ForexScoringEngine)

    def test_get_binary_engine(self):
        engine = get_scoring_engine("binary")
        assert isinstance(engine, BinaryScoringEngine)

    def test_case_insensitive(self):
        engine = get_scoring_engine("FOREX")
        assert isinstance(engine, ForexScoringEngine)

    def test_strip_whitespace(self):
        engine = get_scoring_engine("  binary  ")
        assert isinstance(engine, BinaryScoringEngine)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Modo desconhecido"):
            get_scoring_engine("crypto")

    def test_factory_returns_new_instances(self):
        e1 = get_scoring_engine("forex")
        e2 = get_scoring_engine("forex")
        assert e1 is not e2


# ==========================================================================
# BACKWARD COMPATIBILITY TESTS
# ==========================================================================

class TestBackwardCompat:
    def test_scoring_engine_still_importable(self):
        from dailyagent.scoring.engine import ScoringEngine
        engine = ScoringEngine()
        result = engine.score(mock_structure(), mock_liquidity(), mock_setup())
        assert 0.0 <= result["final_score"] <= 1.0
        # ScoringEngine (alias) should NOT have "mode" field
        assert "mode" not in result

    def test_scoring_engine_is_forex(self):
        from dailyagent.scoring.engine import ScoringEngine
        assert issubclass(ScoringEngine, ForexScoringEngine)

    def test_old_constants_still_importable(self):
        from dailyagent.scoring.engine import (
            WEIGHT_STRUCTURE, WEIGHT_LIQUIDITY, WEIGHT_DISPLACEMENT,
            WEIGHT_SESSION, WEIGHT_ZONE, WEIGHT_RISK,
            PENALTY_COUNTER_TREND, PENALTY_NO_TARGET,
            PENALTY_WEAK_DISPLACEMENT,
            THRESHOLD_STRONG, THRESHOLD_VALID,
            DISPLACEMENT_STRONG_BODY_RATIO, RISK_REWARD_IDEAL,
        )
        assert THRESHOLD_STRONG == 0.80
        assert THRESHOLD_VALID == 0.72
