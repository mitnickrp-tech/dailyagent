"""
Scoring Shared Helpers - DailyAgent 2.1

Funcoes e constantes compartilhadas entre ForexScoringEngine e BinaryScoringEngine.
Evita duplicacao de logica entre os dois modos de decisao.

Sem I/O, sem logging, determinístico.
"""


# ==========================================
# Shared constants
# ==========================================

DISPLACEMENT_STRONG_BODY_RATIO = 0.8

PENALTY_COUNTER_TREND = 0.7
PENALTY_WEAK_DISPLACEMENT = 0.8


# ==========================================
# Utility
# ==========================================

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp valor entre low e high."""
    return min(max(value, low), high)


def classify(score: float, strong_threshold: float, valid_threshold: float) -> str:
    """Classifica score em STRONG/VALID/IGNORE."""
    if score >= strong_threshold:
        return "STRONG"
    elif score >= valid_threshold:
        return "VALID"
    return "IGNORE"


# ==========================================
# Shared component calculators
# ==========================================

def calc_structure_score(structure: dict, setup: dict) -> float:
    """
    Qualidade da estrutura de mercado.

    - Base: structure_strength (0.0-1.0)
    - Bonus: trend alinhado (+0.10)
    - Bonus: BOS na mesma direcao (+0.05)
    - Bonus: CHoCH confirmado (+0.03)
    """
    base = structure.get("structure_strength", 0.0)
    trend = structure.get("trend", "range")
    direction = setup.get("direction", "")
    last_bos = structure.get("last_bos")
    last_choch = structure.get("last_choch")

    bonus = 0.0

    if (direction == "buy" and trend == "bullish") or \
       (direction == "sell" and trend == "bearish"):
        bonus += 0.10

    if (direction == "buy" and last_bos == "bullish") or \
       (direction == "sell" and last_bos == "bearish"):
        bonus += 0.05

    if last_choch is not None:
        bonus += 0.03

    return clamp(base + bonus)


def calc_liquidity_score(setup: dict) -> float:
    """
    Qualidade do sweep de liquidez.

    - Base: sweep_strength (0.0-1.0)
    - Bonus: equal level (+0.10)
    - Bonus: toques >= 3 (+0.05), == 2 (+0.03)
    """
    sweep_strength = setup.get("sweep_strength", 0.0)
    sweep = setup.get("sweep", {})

    bonus = 0.0

    if sweep.get("level_type") == "equal":
        bonus += 0.10

    touches = sweep.get("level_touches", 1)
    if touches >= 3:
        bonus += 0.05
    elif touches >= 2:
        bonus += 0.03

    return clamp(sweep_strength + bonus)


def calc_displacement_score(setup: dict) -> float:
    """Forca do displacement (0.0-1.0), ja calculado pelo SetupEngine."""
    return clamp(setup.get("displacement_score", 0.0))


def calc_session_score() -> float:
    """Score de sessao provisorio (0.5). Futuro: horario de mercado."""
    return 0.5


def is_counter_trend(structure: dict, setup: dict) -> bool:
    """Buy contra bearish ou sell contra bullish."""
    trend = structure.get("trend", "range")
    direction = setup.get("direction", "")
    if direction == "buy" and trend == "bearish":
        return True
    if direction == "sell" and trend == "bullish":
        return True
    return False


def is_weak_displacement(setup: dict) -> bool:
    """body_ratio < DISPLACEMENT_STRONG_BODY_RATIO."""
    displacement = setup.get("displacement", {})
    body_ratio = displacement.get("body_ratio", 0.0)
    return body_ratio < DISPLACEMENT_STRONG_BODY_RATIO
