"""
Scoring Factory - DailyAgent 2.1

Seleciona o ScoringEngine correto baseado no modo de operacao.

Uso:
    engine = get_scoring_engine("forex")
    engine = get_scoring_engine("binary")
"""

from .forex_engine import ForexScoringEngine
from .binary_engine import BinaryScoringEngine


_ENGINES = {
    "forex": ForexScoringEngine,
    "binary": BinaryScoringEngine,
}


def get_scoring_engine(mode: str = "forex"):
    """
    Retorna instancia do ScoringEngine para o modo especificado.

    Args:
        mode: "forex" ou "binary".

    Returns:
        ForexScoringEngine ou BinaryScoringEngine.

    Raises:
        ValueError: Se modo desconhecido.
    """
    mode = mode.lower().strip()

    engine_cls = _ENGINES.get(mode)
    if engine_cls is None:
        valid = ", ".join(sorted(_ENGINES.keys()))
        raise ValueError(f"Modo desconhecido: '{mode}'. Validos: {valid}")

    return engine_cls()
