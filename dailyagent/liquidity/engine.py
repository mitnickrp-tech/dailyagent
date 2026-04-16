"""
Liquidity Engine - DailyAgent 2.1

Identifica onde o mercado "quer ir" (Smart Money Concepts).
Detecta Equal Highs/Lows, Liquidity Pools e Sweeps (stop hunts).

Todas as regras seguem EXATAMENTE as definicoes matematicas do PRD.
Deterministico, sem lookahead bias, sem dependencia de LLM.

Input:  DataFrame [open, high, low, close] + output do StructureEngine
Output: dict com sweep, strength, liquidity_target, etc.
"""

import numpy as np
import pandas as pd


# ==========================================
# PRD Parameters (Secoes 5-6)
# ==========================================

EQUAL_TOLERANCE = 0.0003        # Tolerancia para equal highs/lows (depende do ativo)
SWEEP_LOOKAHEAD = 3             # Candles para confirmar retorno apos rompimento
SWEEP_RETURN_THRESHOLD = 0.5    # Fracao do rompimento que o fechamento deve retornar (filtro opcional)
MIN_SWING_DISTANCE = 6          # Distancia minima entre swing points para equal levels
EQUAL_MAX_SPAN = 100            # Span temporal maximo (candles) para grupo de equal levels
# Heuristico temporario ate futura versao orientada por contexto estrutural
SWEEP_COOLDOWN = 50             # Candles de cooldown antes de reutilizar um nivel varrido


class LiquidityEngine:
    """
    Engine de liquidez (SMC - Smart Money Concepts).

    Pipeline: Equal Levels -> Liquidity Levels -> Sweep Detection -> Strength -> Target

    Depende do output do StructureEngine (swing points).

    Anti-lookahead:
      - Sweep no candle j so e confirmado no candle j + sweep_lookahead.
      - Levels so incluem swings ja confirmados.
    """

    def __init__(
        self,
        equal_tolerance: float = EQUAL_TOLERANCE,
        sweep_lookahead: int = SWEEP_LOOKAHEAD,
        sweep_return_threshold: float = SWEEP_RETURN_THRESHOLD,
        min_swing_distance: int = MIN_SWING_DISTANCE,
        equal_max_span: int = EQUAL_MAX_SPAN,
        sweep_cooldown: int = SWEEP_COOLDOWN,
    ):
        self.equal_tolerance = equal_tolerance
        self.sweep_lookahead = sweep_lookahead
        self.sweep_return_threshold = sweep_return_threshold
        self.min_swing_distance = min_swing_distance
        self.equal_max_span = equal_max_span
        self.sweep_cooldown = sweep_cooldown

    def analyze(self, df: pd.DataFrame, structure: dict) -> dict | None:
        """
        Analise completa de liquidez.

        Args:
            df: DataFrame com colunas [open, high, low, close].
            structure: Output do StructureEngine.analyze().

        Returns:
            {
                "sweep": "buy_side" | "sell_side" | None,
                "strength": float (0.0 - 1.0),
                "liquidity_target": float | None,
                "equal_highs": [...],
                "equal_lows": [...],
                "sweeps": [...],
                "buy_side_levels": [...],
                "sell_side_levels": [...],
            }
        """
        if df is None or df.empty or structure is None:
            return None

        df = df.reset_index(drop=True)

        swing_highs = structure["swing_highs"]
        swing_lows = structure["swing_lows"]

        # 1. Detecta Equal Highs / Equal Lows (PRD Secao 5)
        equal_highs = self._detect_equal_levels(swing_highs)
        equal_lows = self._detect_equal_levels(swing_lows)

        # 2. Constroi niveis de liquidez
        #    PRD: "equal highs OU swing high" -> ambos sao niveis validos
        buy_side_levels = self._build_levels(equal_highs, swing_highs, "buy_side")
        sell_side_levels = self._build_levels(equal_lows, swing_lows, "sell_side")

        # 3. Detecta Sweeps (PRD Secao 6)
        sweeps = self._detect_sweeps(df, buy_side_levels, sell_side_levels)

        # 4. Resultado
        last_sweep = sweeps[-1] if sweeps else None
        current_price = float(df.iloc[-1]["close"])
        target = self._find_liquidity_target(
            last_sweep, current_price, buy_side_levels, sell_side_levels
        )

        return {
            "sweep": last_sweep["type"] if last_sweep else None,
            "strength": round(last_sweep["strength"], 4) if last_sweep else 0.0,
            "liquidity_target": round(target, 6) if target is not None else None,
            "equal_highs": equal_highs,
            "equal_lows": equal_lows,
            "sweeps": sweeps,
            "buy_side_levels": buy_side_levels,
            "sell_side_levels": sell_side_levels,
        }

    # ==========================================================
    # 1. Equal Highs / Equal Lows
    # PRD Secao 5
    # ==========================================================

    def _detect_equal_levels(self, swings: list[dict]) -> list[dict]:
        """
        PRD Secao 5 - Deteccao de Equal Highs / Equal Lows:

        Equal Highs:  |High[i] - High[j]| <= tolerance
        Equal Lows:   |Low[i] - Low[j]| <= tolerance

        Validacao:
          - Distancia minima entre pontos >= min_swing_distance (evitar duplicacao)
          - Pelo menos 2 toques no mesmo nivel
          - Span temporal (last_index - first_index) <= equal_max_span

        Algoritmo:
          1. Ordena swings por preco
          2. Agrupa consecutivos dentro de tolerance do anchor (primeiro do grupo)
          3. Garante pairwise: como lista esta ordenada, basta checar sorted[j] - anchor
          4. Descarta grupos com span temporal excessivo (ruido de longo prazo)

        Returns:
            Lista de dicts com {price, touches, first_index, last_index, points}
        """
        if len(swings) < 2:
            return []

        # Ordenar por preco
        sorted_swings = sorted(swings, key=lambda s: s["price"])

        levels = []
        i = 0

        while i < len(sorted_swings):
            anchor_price = sorted_swings[i]["price"]
            group = [sorted_swings[i]]
            j = i + 1

            while j < len(sorted_swings):
                # Todos no grupo devem estar dentro de tolerance do anchor
                # Como a lista esta ordenada, basta checar sorted[j] - anchor
                if sorted_swings[j]["price"] - anchor_price <= self.equal_tolerance:
                    # Checa distancia minima de tempo contra TODOS os membros
                    min_dist_ok = all(
                        abs(sorted_swings[j]["index"] - g["index"]) >= self.min_swing_distance
                        for g in group
                    )
                    if min_dist_ok:
                        group.append(sorted_swings[j])
                    j += 1
                else:
                    break

            # PRD: "pelo menos 2 toques" + span temporal limitado
            if len(group) >= 2:
                first_idx = min(s["index"] for s in group)
                last_idx = max(s["index"] for s in group)
                # Descarta grupos com span temporal excessivo
                if last_idx - first_idx > self.equal_max_span:
                    i = j
                    continue
                avg_price = sum(s["price"] for s in group) / len(group)
                levels.append({
                    "price": float(avg_price),
                    "touches": len(group),
                    "first_index": first_idx,
                    "last_index": last_idx,
                    "points": group,
                })

            i = j

        return levels

    # ==========================================================
    # Build Liquidity Levels
    # PRD: "equal highs OU swing high"
    # ==========================================================

    def _build_levels(
        self,
        equal_levels: list[dict],
        swings: list[dict],
        side: str,
    ) -> list[dict]:
        """
        Constroi lista unificada de niveis de liquidez.

        PRD: sweep pode atingir "equal highs OU swing high".
        Equal levels tem prioridade (mais toques = mais liquidez).
        Swing points individuais que NAO pertencem a nenhum equal level
        tambem sao incluidos.
        """
        # Indices de swings que ja fazem parte de equal levels
        used_indices = set()
        for eq in equal_levels:
            for p in eq["points"]:
                used_indices.add(p["index"])

        levels = []

        # 1. Equal levels (maior liquidez)
        for eq in equal_levels:
            levels.append({
                "price": eq["price"],
                "type": "equal",
                "side": side,
                "touches": eq["touches"],
                "first_index": eq["first_index"],
                "last_index": eq["last_index"],
            })

        # 2. Swing points individuais (nao cobertos por equal levels)
        for sw in swings:
            if sw["index"] not in used_indices:
                levels.append({
                    "price": sw["price"],
                    "type": "swing",
                    "side": side,
                    "touches": 1,
                    "first_index": sw["index"],
                    "last_index": sw["index"],
                })

        return levels

    # ==========================================================
    # 2. Sweep Detection (Stop Hunt)
    # PRD Secao 6: Liquidity Sweep
    # ==========================================================

    def _detect_sweeps(
        self,
        df: pd.DataFrame,
        buy_side_levels: list[dict],
        sell_side_levels: list[dict],
    ) -> list[dict]:
        """
        PRD Secao 6:

        Sweep de compra (buy-side):
            Preco rompe acima de equal highs OU swing high
            AND Retorna para dentro do range em ate N candles
            AND Fecha abaixo do nivel rompido (controlado por SWEEP_RETURN_THRESHOLD)

        Sweep de venda (sell-side):
            Preco rompe abaixo de equal lows OU swing low
            AND Retorna para dentro
            AND Fecha acima do nivel (controlado por SWEEP_RETURN_THRESHOLD)

        Anti-lookahead: sweep no candle j so e confirmado em j + lookahead.
        So processa candles onde j + lookahead < len(df).
        """
        highs = df["high"].values
        lows = df["low"].values
        opens = df["open"].values
        closes = df["close"].values
        ranges = highs - lows

        # Media de range (high-low) para normalizacao da forca
        avg_range_window = 20
        avg_range = np.full(len(df), np.nan)
        for k in range(avg_range_window, len(df)):
            avg_range[k] = np.mean(ranges[k - avg_range_window : k])

        sweeps = []
        # Heuristico temporario ate futura versao orientada por contexto estrutural:
        # Apos um sweep, o mesmo nivel entra em cooldown por N candles antes de poder
        # ser reutilizado. Isso evita falsos positivos em regioes de consolidacao.
        level_cooldowns = {}  # level_key -> ultimo break_index

        # Limite: sweep no candle j requer dados ate j + lookahead
        max_j = len(df) - self.sweep_lookahead - 1

        for j in range(0, max_j + 1):
            # --- Buy-side sweeps ---
            # High[j] rompe acima de um nivel buy-side
            for lvl in buy_side_levels:
                level_price = lvl["price"]
                # Nivel so e relevante se ja estava formado antes do candle j
                if lvl["last_index"] >= j:
                    continue
                # Rompimento: high ultrapassa o nivel
                if highs[j] <= level_price:
                    continue

                level_key = ("buy", round(level_price, 8))
                if level_key in level_cooldowns:
                    if j - level_cooldowns[level_key] < self.sweep_cooldown:
                        continue

                # Verifica retorno dentro de N candles
                break_distance = highs[j] - level_price

                for k in range(j + 1, min(j + self.sweep_lookahead + 1, len(df))):
                    if closes[k] < level_price:
                        # Sweep confirmado
                        candles_to_return = k - j
                        strength = self._calculate_sweep_strength(
                            break_distance=break_distance,
                            candles_to_return=candles_to_return,
                            return_candle_open=opens[k],
                            return_candle_high=highs[k],
                            return_candle_low=lows[k],
                            return_candle_close=closes[k],
                            sweep_type="buy_side",
                            avg_range_value=avg_range[j] if not np.isnan(avg_range[j]) else break_distance,
                        )
                        sweeps.append({
                            "type": "buy_side",
                            "break_index": j,
                            "return_index": k,
                            "level_price": float(level_price),
                            "break_high": float(highs[j]),
                            "return_close": float(closes[k]),
                            "break_distance": float(break_distance),
                            "strength": float(strength),
                            "level_type": lvl["type"],
                            "level_touches": lvl["touches"],
                        })
                        level_cooldowns[level_key] = j
                        break  # Primeiro retorno confirma

            # --- Sell-side sweeps ---
            # Low[j] rompe abaixo de um nivel sell-side
            for lvl in sell_side_levels:
                level_price = lvl["price"]
                if lvl["last_index"] >= j:
                    continue
                if lows[j] >= level_price:
                    continue

                level_key = ("sell", round(level_price, 8))
                if level_key in level_cooldowns:
                    if j - level_cooldowns[level_key] < self.sweep_cooldown:
                        continue

                break_distance = level_price - lows[j]

                for k in range(j + 1, min(j + self.sweep_lookahead + 1, len(df))):
                    if closes[k] > level_price:
                        candles_to_return = k - j
                        strength = self._calculate_sweep_strength(
                            break_distance=break_distance,
                            candles_to_return=candles_to_return,
                            return_candle_open=opens[k],
                            return_candle_high=highs[k],
                            return_candle_low=lows[k],
                            return_candle_close=closes[k],
                            sweep_type="sell_side",
                            avg_range_value=avg_range[j] if not np.isnan(avg_range[j]) else break_distance,
                        )
                        sweeps.append({
                            "type": "sell_side",
                            "break_index": j,
                            "return_index": k,
                            "level_price": float(level_price),
                            "break_low": float(lows[j]),
                            "return_close": float(closes[k]),
                            "break_distance": float(break_distance),
                            "strength": float(strength),
                            "level_type": lvl["type"],
                            "level_touches": lvl["touches"],
                        })
                        level_cooldowns[level_key] = j
                        break

        # Ordenar cronologicamente
        sweeps.sort(key=lambda s: s["break_index"])
        return sweeps

    # ==========================================================
    # Sweep Strength
    # PRD Secao 6: Classificacao de forca
    # ==========================================================

    def _calculate_sweep_strength(
        self,
        break_distance: float,
        candles_to_return: int,
        return_candle_open: float,
        return_candle_high: float,
        return_candle_low: float,
        return_candle_close: float,
        sweep_type: str,
        avg_range_value: float,
    ) -> float:
        """
        PRD Secao 6:

        sweep_strength = (
            rompimento_distancia +
            velocidade_retorno +
            rejeicao_candle
        ) / 3

        Cada componente normalizado para 0.0 - 1.0.
        """
        # 1. rompimento_distancia
        #    Distancia do rompimento normalizada pela media de range
        if avg_range_value > 0:
            rompimento_distancia = min(break_distance / avg_range_value, 1.0)
        else:
            rompimento_distancia = 0.0

        # 2. velocidade_retorno
        #    1 candle = mais rapido (1.0), N candles = mais lento
        if self.sweep_lookahead > 1:
            velocidade_retorno = 1.0 - (
                (candles_to_return - 1) / (self.sweep_lookahead)
            )
        else:
            velocidade_retorno = 1.0
        velocidade_retorno = max(velocidade_retorno, 0.0)

        # 3. rejeicao_candle
        #    Qualidade de rejeicao do candle de retorno
        candle_range = return_candle_high - return_candle_low
        if candle_range <= 0:
            rejeicao_candle = 0.0
        else:
            if sweep_type == "buy_side":
                # Rejeicao de alta: wick superior grande
                upper_wick = return_candle_high - max(
                    return_candle_open, return_candle_close
                )
                rejeicao_candle = upper_wick / candle_range
            else:
                # Rejeicao de baixa: wick inferior grande
                lower_wick = min(
                    return_candle_open, return_candle_close
                ) - return_candle_low
                rejeicao_candle = lower_wick / candle_range

        # PRD formula exata
        sweep_strength = (
            rompimento_distancia + velocidade_retorno + rejeicao_candle
        ) / 3.0

        return min(max(sweep_strength, 0.0), 1.0)

    # ==========================================================
    # Liquidity Target
    # ==========================================================

    def _find_liquidity_target(
        self,
        last_sweep: dict | None,
        current_price: float,
        buy_side_levels: list[dict],
        sell_side_levels: list[dict],
    ) -> float | None:
        """
        Encontra o proximo alvo de liquidez apos um sweep.

        Logica SMC:
          - Apos buy-side sweep (fake breakout acima):
            Smart money esta vendendo -> alvo = sell-side liquidity abaixo
          - Apos sell-side sweep (fake breakdown abaixo):
            Smart money esta comprando -> alvo = buy-side liquidity acima
        """
        if last_sweep is None:
            return None

        if last_sweep["type"] == "buy_side":
            # Alvo = sell-side (liquidez abaixo do preco atual)
            candidates = [
                lvl["price"]
                for lvl in sell_side_levels
                if lvl["price"] < current_price
            ]
            if candidates:
                return float(max(candidates))  # Mais proximo abaixo

        elif last_sweep["type"] == "sell_side":
            # Alvo = buy-side (liquidez acima do preco atual)
            candidates = [
                lvl["price"]
                for lvl in buy_side_levels
                if lvl["price"] > current_price
            ]
            if candidates:
                return float(min(candidates))  # Mais proximo acima

        return None
