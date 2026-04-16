"""
Binary Options Scoring Engine - DailyAgent 2.1

Score composto para modo Opcoes Binarias.
Prioriza timing e compatibilidade com expiracao em vez de risk/reward.

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
# Binary Weights
# ==========================================

WEIGHT_STRUCTURE = 0.22
WEIGHT_LIQUIDITY = 0.22
WEIGHT_DISPLACEMENT = 0.20
WEIGHT_TIMING = 0.18
WEIGHT_EXPIRY = 0.10
WEIGHT_SESSION = 0.08

# ==========================================
# Binary Penalties
# ==========================================

PENALTY_STALE_SETUP = 0.7     # Setup velho demais para a expiracao

# ==========================================
# Binary Thresholds
# ==========================================

THRESHOLD_STRONG = 0.80
THRESHOLD_VALID = 0.72

# ==========================================
# Expiry Windows (candles de tolerancia)
# ==========================================
# Cada expiracao define janelas maximas de recencia para sweep, choch, displacement.
# Se o evento esta mais distante que a janela, o score de expiry cai.

EXPIRY_PARAMS = {
    "M1": {
        "sweep_window": 5,
        "choch_window": 3,
        "displacement_window": 2,
        "stale_threshold": 8,       # candles alem desse limite = stale
    },
    "M5": {
        "sweep_window": 10,
        "choch_window": 7,
        "displacement_window": 5,
        "stale_threshold": 15,
    },
    "M15": {
        "sweep_window": 20,
        "choch_window": 15,
        "displacement_window": 10,
        "stale_threshold": 30,
    },
}

DEFAULT_EXPIRY = "M5"


class BinaryScoringEngine:
    """
    Scoring para modo Opcoes Binarias.

    6 componentes: structure, liquidity, displacement, timing, expiry, session.
    Prioriza recencia temporal e compatibilidade com expiracao.

    Penalidades: contra-tendencia, displacement fraco, setup velho.
    """

    def __init__(
        self,
        expiry_params: dict | None = None,
    ):
        self.expiry_params = expiry_params or EXPIRY_PARAMS

    def score(
        self,
        structure: dict,
        liquidity: dict,
        setup: dict,
        expiration: str = DEFAULT_EXPIRY,
        total_candles: int | None = None,
    ) -> dict:
        """
        Calcula score composto para setup de Opcoes Binarias.

        Args:
            structure: Output de StructureEngine.analyze().
            liquidity: Output de LiquidityEngine.analyze().
            setup: Output de SetupEngine.analyze() (nao-None).
            expiration: "M1", "M5" ou "M15".
            total_candles: Total de candles no DataFrame (para calcular recencia).
                           Se None, usa setup_index + 10 como estimativa.

        Returns:
            {
                "mode": "binary",
                "expiration": str,
                "final_score": float,
                "classification": "STRONG" | "VALID" | "IGNORE",
                "trade_candidate": bool,
                "components": {...},
                "penalties_applied": [...],
            }
        """
        if total_candles is None:
            total_candles = setup.get("setup_index", 0) + 10

        params = self.expiry_params.get(expiration, self.expiry_params.get(DEFAULT_EXPIRY))

        structure_score = calc_structure_score(structure, setup)
        liquidity_score = calc_liquidity_score(setup)
        displacement_score = calc_displacement_score(setup)
        timing_score = self._calc_timing_score(setup, total_candles)
        expiry_score = self._calc_expiry_score(setup, total_candles, params)
        session_score = calc_session_score()

        weighted = (
            structure_score * WEIGHT_STRUCTURE
            + liquidity_score * WEIGHT_LIQUIDITY
            + displacement_score * WEIGHT_DISPLACEMENT
            + timing_score * WEIGHT_TIMING
            + expiry_score * WEIGHT_EXPIRY
            + session_score * WEIGHT_SESSION
        )

        penalties = []
        final = weighted

        if is_counter_trend(structure, setup):
            final *= PENALTY_COUNTER_TREND
            penalties.append("counter_trend")

        if is_weak_displacement(setup):
            final *= PENALTY_WEAK_DISPLACEMENT
            penalties.append("weak_displacement")

        if self._is_stale_setup(setup, total_candles, params):
            final *= PENALTY_STALE_SETUP
            penalties.append("stale_setup")

        final = clamp(final)
        classification = classify(final, THRESHOLD_STRONG, THRESHOLD_VALID)

        return {
            "mode": "binary",
            "expiration": expiration,
            "final_score": round(final, 4),
            "classification": classification,
            "trade_candidate": classification in ("STRONG", "VALID"),
            "components": {
                "structure_score": round(structure_score, 4),
                "liquidity_score": round(liquidity_score, 4),
                "displacement_score": round(displacement_score, 4),
                "timing_score": round(timing_score, 4),
                "expiry_score": round(expiry_score, 4),
                "session_score": round(session_score, 4),
            },
            "penalties_applied": penalties,
        }

    # ==========================================================
    # Binary-specific components
    # ==========================================================

    def _calc_timing_score(self, setup: dict, total_candles: int) -> float:
        """
        Mede quao recente sao os eventos do setup.

        Combina recencia de sweep, choch e displacement.
        Cada sub-score: 1.0 se evento no ultimo candle, decai com distancia.
        Usa janela de 20 candles como referencia de normalizacao.
        """
        last_idx = total_candles - 1
        ref_window = 20.0  # Normalizacao: evento a 20+ candles = score 0

        sweep_idx = setup.get("sweep_index", 0)
        choch_idx = setup.get("choch_index", 0)
        disp_idx = setup.get("displacement_index", 0)

        sweep_age = last_idx - sweep_idx
        choch_age = last_idx - choch_idx
        disp_age = last_idx - disp_idx

        sweep_recency = clamp(1.0 - (sweep_age / ref_window))
        choch_recency = clamp(1.0 - (choch_age / ref_window))
        disp_recency = clamp(1.0 - (disp_age / ref_window))

        # Displacement mais importante, depois choch, depois sweep
        timing = (
            sweep_recency * 0.25
            + choch_recency * 0.35
            + disp_recency * 0.40
        )

        return clamp(timing)

    def _calc_expiry_score(
        self, setup: dict, total_candles: int, params: dict
    ) -> float:
        """
        Mede compatibilidade entre recencia do setup e expiracao escolhida.

        Para cada evento (sweep, choch, displacement):
        - Se age <= window -> score = 1.0
        - Se age > window -> score decai linearmente ate 0.0

        Combina os tres sub-scores.
        """
        last_idx = total_candles - 1

        sweep_age = last_idx - setup.get("sweep_index", 0)
        choch_age = last_idx - setup.get("choch_index", 0)
        disp_age = last_idx - setup.get("displacement_index", 0)

        sweep_w = params.get("sweep_window", 10)
        choch_w = params.get("choch_window", 7)
        disp_w = params.get("displacement_window", 5)

        def window_score(age: float, window: float) -> float:
            if age <= window:
                return 1.0
            # Decai linearmente ate 2x a janela, depois 0
            overshoot = age - window
            return clamp(1.0 - (overshoot / window))

        sweep_s = window_score(sweep_age, sweep_w)
        choch_s = window_score(choch_age, choch_w)
        disp_s = window_score(disp_age, disp_w)

        # Displacement e choch sao mais criticos que sweep para binarias
        expiry = (
            sweep_s * 0.25
            + choch_s * 0.35
            + disp_s * 0.40
        )

        return clamp(expiry)

    def _is_stale_setup(
        self, setup: dict, total_candles: int, params: dict
    ) -> bool:
        """
        Setup velho demais para a expiracao.

        Se o displacement (evento mais recente do setup) esta alem
        do stale_threshold, aplica penalidade.
        """
        last_idx = total_candles - 1
        disp_age = last_idx - setup.get("displacement_index", 0)
        stale_threshold = params.get("stale_threshold", 15)
        return disp_age > stale_threshold
