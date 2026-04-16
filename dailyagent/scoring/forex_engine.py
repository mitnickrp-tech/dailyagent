"""
Forex Scoring Engine - DailyAgent 2.1

Score composto para modo Forex / Day Trade.
Reutiliza componentes compartilhados de scoring/shared.py.

Deterministico, sem I/O, sem logging.
"""

from .shared import (
    clamp, classify,
    calc_structure_score, calc_liquidity_score,
    calc_displacement_score, calc_session_score,
    is_counter_trend, is_weak_displacement,
    PENALTY_COUNTER_TREND, PENALTY_WEAK_DISPLACEMENT,
)


# ==========================================
# Forex Weights
# ==========================================

WEIGHT_STRUCTURE = 0.25
WEIGHT_LIQUIDITY = 0.25
WEIGHT_DISPLACEMENT = 0.20
WEIGHT_SESSION = 0.15
WEIGHT_ZONE = 0.10
WEIGHT_RISK = 0.05

# ==========================================
# Forex Penalties
# ==========================================

PENALTY_NO_TARGET = 0.8

# ==========================================
# Forex Thresholds
# ==========================================

THRESHOLD_STRONG = 0.80
THRESHOLD_VALID = 0.72

# ==========================================
# Forex Parameters
# ==========================================

RISK_REWARD_IDEAL = 2.0


class ForexScoringEngine:
    """
    Scoring para modo Forex / Day Trade.

    6 componentes: structure, liquidity, displacement, session, zone, risk.
    Penalidades: contra-tendencia, sem target, displacement fraco.
    """

    def score(
        self,
        structure: dict,
        liquidity: dict,
        setup: dict,
    ) -> dict:
        """
        Calcula score composto para setup Forex.

        Returns:
            {
                "mode": "forex",
                "final_score": float,
                "classification": "STRONG" | "VALID" | "IGNORE",
                "trade_candidate": bool,
                "components": {...},
                "penalties_applied": [...],
            }
        """
        structure_score = calc_structure_score(structure, setup)
        liquidity_score = calc_liquidity_score(setup)
        displacement_score = calc_displacement_score(setup)
        session_score = calc_session_score()
        zone_score = self._calc_zone_score(setup)
        risk_score = self._calc_risk_score(setup)

        weighted = (
            structure_score * WEIGHT_STRUCTURE
            + liquidity_score * WEIGHT_LIQUIDITY
            + displacement_score * WEIGHT_DISPLACEMENT
            + session_score * WEIGHT_SESSION
            + zone_score * WEIGHT_ZONE
            + risk_score * WEIGHT_RISK
        )

        penalties = []
        final = weighted

        if is_counter_trend(structure, setup):
            final *= PENALTY_COUNTER_TREND
            penalties.append("counter_trend")

        if setup.get("target_level") is None:
            final *= PENALTY_NO_TARGET
            penalties.append("no_target")

        if is_weak_displacement(setup):
            final *= PENALTY_WEAK_DISPLACEMENT
            penalties.append("weak_displacement")

        final = clamp(final)
        classification = classify(final, THRESHOLD_STRONG, THRESHOLD_VALID)

        return {
            "mode": "forex",
            "final_score": round(final, 4),
            "classification": classification,
            "trade_candidate": classification in ("STRONG", "VALID"),
            "components": {
                "structure_score": round(structure_score, 4),
                "liquidity_score": round(liquidity_score, 4),
                "displacement_score": round(displacement_score, 4),
                "session_score": round(session_score, 4),
                "zone_score": round(zone_score, 4),
                "risk_score": round(risk_score, 4),
            },
            "penalties_applied": penalties,
        }

    # ==========================================================
    # Forex-specific components
    # ==========================================================

    def _calc_zone_score(self, setup: dict) -> float:
        """Zone score baseado em body_ratio do displacement."""
        displacement = setup.get("displacement", {})
        body_ratio = displacement.get("body_ratio", 0.0)
        return clamp(body_ratio)

    def _calc_risk_score(self, setup: dict) -> float:
        """Risk score baseado em relacao risco/retorno."""
        entry_zone = setup.get("entry_zone")
        invalid_level = setup.get("invalid_level")
        target_level = setup.get("target_level")
        direction = setup.get("direction", "")

        if entry_zone is None or invalid_level is None:
            return 0.0

        if target_level is None:
            return 0.2

        entry_mid = (entry_zone[0] + entry_zone[1]) / 2.0

        if direction == "buy":
            risk = abs(entry_mid - invalid_level)
            reward = abs(target_level - entry_mid)
        else:
            risk = abs(invalid_level - entry_mid)
            reward = abs(entry_mid - target_level)

        if risk <= 0:
            return 0.0

        rr_ratio = reward / risk

        if rr_ratio >= RISK_REWARD_IDEAL:
            return 1.0

        return clamp(rr_ratio / RISK_REWARD_IDEAL)
