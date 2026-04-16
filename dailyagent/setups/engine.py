"""
Setup Engine - DailyAgent 2.1

Combina output de StructureEngine e LiquidityEngine para identificar setups.
Setup principal: Sweep + CHoCH + Displacement.

Buy setup:  sell_side sweep -> CHoCH bullish -> displacement bullish
Sell setup: buy_side sweep  -> CHoCH bearish -> displacement bearish

Deterministico, sem lookahead bias, sem dependencia de LLM, sem I/O.

Input:  DataFrame + structure dict + liquidity dict
Output: dict com setup completo ou None
"""

import numpy as np
import pandas as pd


# ==========================================
# Parameters
# ==========================================

DISPLACEMENT_LOOKBACK = 20          # Candles para media de range na deteccao de displacement
DISPLACEMENT_MULTIPLIER = 1.5       # range > avg * multiplier
DISPLACEMENT_BODY_RATIO_MIN = 0.7   # body_ratio minimo do candle de displacement
DISPLACEMENT_SEARCH_WINDOW = 5      # Candles apos CHoCH para buscar displacement


class SetupEngine:
    """
    Engine de setups (combinacao de sinais).

    Pipeline: Sweep -> CHoCH -> Displacement -> Entry Zone -> Invalidation -> Target

    Requer outputs de StructureEngine e LiquidityEngine.
    """

    def __init__(
        self,
        displacement_lookback: int = DISPLACEMENT_LOOKBACK,
        displacement_multiplier: float = DISPLACEMENT_MULTIPLIER,
        displacement_body_ratio_min: float = DISPLACEMENT_BODY_RATIO_MIN,
        displacement_search_window: int = DISPLACEMENT_SEARCH_WINDOW,
    ):
        self.displacement_lookback = displacement_lookback
        self.displacement_multiplier = displacement_multiplier
        self.displacement_body_ratio_min = displacement_body_ratio_min
        self.displacement_search_window = displacement_search_window

    def analyze(
        self,
        df: pd.DataFrame,
        structure: dict,
        liquidity: dict,
    ) -> dict | None:
        """
        Analise de setup completo.

        Args:
            df: DataFrame com colunas [open, high, low, close].
            structure: Output de StructureEngine.analyze().
            liquidity: Output de LiquidityEngine.analyze().

        Returns:
            dict com setup completo ou None se nenhum setup valido.

            {
                "direction": "buy" | "sell",
                "setup_type": str,
                "sweep": {...},
                "choch": {...},
                "displacement": {...},
                "entry_zone": [float, float],   # [min, max] ordenado
                "invalid_level": float,
                "target_level": float | None,
                "setup_index": int,
                "sweep_index": int,
                "choch_index": int,
                "displacement_index": int,
                "structure_trend": str,
                "last_bos": str | None,
                "last_choch": str | None,
                "sweep_type": str,
                "sweep_strength": float,
                "displacement_score": float,
            }
        """
        if df is None or df.empty or structure is None or liquidity is None:
            return None

        df = df.reset_index(drop=True)

        sweeps = liquidity.get("sweeps", [])
        choch_events = structure.get("choch_events", [])

        if not sweeps or not choch_events:
            return None

        # Tenta encontrar setup valido (mais recente primeiro)
        for sweep in reversed(sweeps):
            setup = self._try_build_setup(df, sweep, choch_events, structure, liquidity)
            if setup is not None:
                return setup

        return None

    def _try_build_setup(
        self,
        df: pd.DataFrame,
        sweep: dict,
        choch_events: list[dict],
        structure: dict,
        liquidity: dict,
    ) -> dict | None:
        """
        Tenta construir um setup a partir de um sweep especifico.

        Buy:  sell_side sweep -> CHoCH bullish (apos sweep) -> displacement bullish
        Sell: buy_side sweep  -> CHoCH bearish (apos sweep) -> displacement bearish
        """
        sweep_type = sweep["type"]
        sweep_return_index = sweep["return_index"]

        if sweep_type == "sell_side":
            # Buy setup
            target_choch_dir = "bullish"
            target_displacement_dir = "bullish"
            setup_direction = "buy"
        elif sweep_type == "buy_side":
            # Sell setup
            target_choch_dir = "bearish"
            target_displacement_dir = "bearish"
            setup_direction = "sell"
        else:
            return None

        # Encontra CHoCH do tipo correto APOS o sweep return
        matching_choch = None
        for choch in choch_events:
            if choch["direction"] == target_choch_dir and choch["index"] >= sweep_return_index:
                matching_choch = choch
                break  # Primeiro CHoCH apos sweep

        if matching_choch is None:
            return None

        # Busca displacement APOS o CHoCH
        displacement = self._detect_displacement_after_index(
            df, matching_choch["index"], target_displacement_dir
        )

        if displacement is None:
            return None

        # Calcula entry zone, invalid level e target
        entry_zone = self._calculate_entry_zone(displacement)
        invalid_level = self._calculate_invalid_level(
            sweep, displacement, setup_direction
        )
        target_level = liquidity.get("liquidity_target")

        # Displacement score normalizado 0.0-1.0
        displacement_score = self._calculate_displacement_score(displacement)

        return {
            "direction": setup_direction,
            "setup_type": "sweep_choch_displacement",
            "sweep": sweep,
            "choch": matching_choch,
            "displacement": displacement,
            "entry_zone": entry_zone,
            "invalid_level": invalid_level,
            "target_level": target_level,
            # Indices para facilitar calculo de recencia/timing
            "setup_index": displacement["index"],
            "sweep_index": sweep["break_index"],
            "choch_index": matching_choch["index"],
            "displacement_index": displacement["index"],
            # Metadata para ScoringEngines
            "structure_trend": structure.get("trend", "range"),
            "last_bos": structure.get("last_bos"),
            "last_choch": structure.get("last_choch"),
            "sweep_type": sweep_type,
            "sweep_strength": sweep.get("strength", 0.0),
            "displacement_score": displacement_score,
        }

    def _detect_displacement_after_index(
        self,
        df: pd.DataFrame,
        start_index: int,
        direction: str,
    ) -> dict | None:
        """
        Detecta candle de displacement apos start_index.

        Displacement bullish:
            - Candle de alta (close > open)
            - range > avg_range * displacement_multiplier
            - body_ratio > displacement_body_ratio_min

        Displacement bearish:
            - Candle de baixa (close < open)
            - range > avg_range * displacement_multiplier
            - body_ratio > displacement_body_ratio_min

        Busca limitada a displacement_search_window candles apos start_index.
        """
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        ranges = highs - lows

        # Media de ranges para comparacao
        avg_ranges = np.full(len(df), np.nan)
        for idx in range(self.displacement_lookback, len(df)):
            avg_ranges[idx] = np.mean(ranges[idx - self.displacement_lookback : idx])

        # Busca nos candles apos start_index (exclusivo)
        search_start = start_index + 1
        search_end = min(search_start + self.displacement_search_window, len(df))

        for i in range(search_start, search_end):
            candle_range = ranges[i]
            if candle_range <= 0:
                continue

            body = abs(closes[i] - opens[i])
            body_ratio = body / candle_range

            if body_ratio <= self.displacement_body_ratio_min:
                continue

            # Verifica direcao
            if direction == "bullish" and closes[i] <= opens[i]:
                continue
            if direction == "bearish" and closes[i] >= opens[i]:
                continue

            # Verifica range vs media
            avg = avg_ranges[i]
            if not np.isnan(avg):
                if candle_range <= avg * self.displacement_multiplier:
                    continue
            # Se avg nao disponivel, aceita (dados insuficientes para lookback)

            return {
                "index": i,
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "range": float(candle_range),
                "body_ratio": round(float(body_ratio), 4),
                "direction": direction,
            }

        return None

    def _calculate_entry_zone(self, displacement: dict) -> list[float]:
        """
        Entry zone = corpo do candle de displacement, ordenado [min, max].
        """
        open_ = displacement["open"]
        close = displacement["close"]
        return [min(open_, close), max(open_, close)]

    def _calculate_invalid_level(
        self,
        sweep: dict,
        displacement: dict,
        direction: str,
    ) -> float:
        """
        Invalid level = escolha conservadora entre extremo do sweep e do displacement.

        Buy: invalid = min(sweep_low, displacement_low) -- abaixo invalida
        Sell: invalid = max(sweep_high, displacement_high) -- acima invalida
        """
        if direction == "buy":
            sweep_extreme = sweep.get("break_low", sweep.get("level_price", displacement["low"]))
            return min(sweep_extreme, displacement["low"])
        else:
            sweep_extreme = sweep.get("break_high", sweep.get("level_price", displacement["high"]))
            return max(sweep_extreme, displacement["high"])

    def _calculate_displacement_score(self, displacement: dict) -> float:
        """
        Score de displacement normalizado 0.0 - 1.0.

        Componentes:
        - body_ratio: ja entre 0.0-1.0
        - range_relative: normalizacao simplificada (capped a 1.0)

        score = (body_ratio + min(body_ratio * 1.5, 1.0)) / 2
        """
        body_ratio = displacement.get("body_ratio", 0.0)
        # body_ratio ja e a metrica principal; usamos uma versao escalada
        # como proxy de range_relative (quanto maior o body_ratio, mais forte)
        range_component = min(body_ratio * 1.5, 1.0)

        score = (body_ratio + range_component) / 2.0
        return round(min(max(score, 0.0), 1.0), 4)
