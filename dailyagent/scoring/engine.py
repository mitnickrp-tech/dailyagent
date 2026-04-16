"""
Scoring Engine - DailyAgent 2.1 (Backward Compatibility)

Este modulo mantem a interface original ScoringEngine como alias
do ForexScoringEngine. Codigo existente que importa ScoringEngine
continua funcionando sem alteracao.

Para novos usos, prefira:
    from dailyagent.scoring.factory import get_scoring_engine
    engine = get_scoring_engine("forex")  # ou "binary"
"""

from .forex_engine import (
    ForexScoringEngine,
    WEIGHT_STRUCTURE,
    WEIGHT_LIQUIDITY,
    WEIGHT_DISPLACEMENT,
    WEIGHT_SESSION,
    WEIGHT_ZONE,
    WEIGHT_RISK,
    PENALTY_NO_TARGET,
    THRESHOLD_STRONG,
    THRESHOLD_VALID,
    RISK_REWARD_IDEAL,
)
from .shared import (
    PENALTY_COUNTER_TREND,
    PENALTY_WEAK_DISPLACEMENT,
    DISPLACEMENT_STRONG_BODY_RATIO,
)


class ScoringEngine(ForexScoringEngine):
    """
    Alias backward-compatible para ForexScoringEngine.

    Comportamento identico ao ForexScoringEngine.
    Output NAO inclui campo "mode" para manter compatibilidade
    com testes existentes que nao esperam esse campo.
    """

    def score(self, structure: dict, liquidity: dict, setup: dict) -> dict:
        result = super().score(structure, liquidity, setup)
        # Remove "mode" para manter compatibilidade com testes existentes
        result.pop("mode", None)
        return result


# Re-export _clamp for any code that imported it from here
def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp valor entre low e high."""
    return min(max(value, low), high)
