"""
Structure Engine - DailyAgent 2.1

Interpreta o mercado como sequencia de estrutura (Market Structure).
Detecta Swing High/Low, HH/HL/LH/LL, BOS e CHoCH.

Todas as regras seguem EXATAMENTE as definicoes matematicas do PRD.
Deterministico, sem lookahead bias, sem dependencia de LLM.

Input:  DataFrame com colunas [open, high, low, close]
Output: dict com trend, last_bos, last_choch, structure_strength, etc.
"""

import numpy as np
import pandas as pd


# ==========================================
# PRD Parameters (Secoes 1-4)
# ==========================================

SWING_WINDOW = 3            # Fractal simetrico (pode ser 2-5)
BOS_THRESHOLD = 0.001       # 0.1% do preco (ajustavel)
BOS_BODY_RATIO_MIN = 0.6   # body_ratio minimo do candle de rompimento
BOS_RANGE_LOOKBACK = 20    # Candles para media de range no filtro de qualidade

CHOCH_BODY_RATIO_MIN = 0.5     # body_ratio minimo do candle de CHoCH
CHOCH_RANGE_LOOKBACK = 20      # Candles para media de range no filtro de qualidade CHoCH
CHOCH_RANGE_MULTIPLIER = 1.0   # Multiplicador: range > avg * multiplier


class StructureEngine:
    """
    Engine de estrutura de mercado (Market Structure).

    Pipeline: Swings -> HH/HL/LH/LL -> BOS -> CHoCH -> Trend + Strength

    Anti-lookahead:
      - Swing em indice i so e confirmado no candle i + swing_window.
      - BOS/CHoCH em candle t so referencia swings com confirmed_at <= t.
    """

    def __init__(
        self,
        swing_window: int = SWING_WINDOW,
        bos_threshold: float = BOS_THRESHOLD,
        bos_body_ratio_min: float = BOS_BODY_RATIO_MIN,
        bos_range_lookback: int = BOS_RANGE_LOOKBACK,
        choch_body_ratio_min: float = CHOCH_BODY_RATIO_MIN,
        choch_range_lookback: int = CHOCH_RANGE_LOOKBACK,
        choch_range_multiplier: float = CHOCH_RANGE_MULTIPLIER,
    ):
        self.swing_window = swing_window
        self.bos_threshold = bos_threshold
        self.bos_body_ratio_min = bos_body_ratio_min
        self.bos_range_lookback = bos_range_lookback
        self.choch_body_ratio_min = choch_body_ratio_min
        self.choch_range_lookback = choch_range_lookback
        self.choch_range_multiplier = choch_range_multiplier

    def analyze(self, df: pd.DataFrame) -> dict | None:
        """
        Analise completa de estrutura de mercado.

        Args:
            df: DataFrame com colunas [open, high, low, close].
                Opcionalmente [time, volume].

        Returns:
            {
                "trend": "bullish" | "bearish" | "range",
                "last_bos": "bullish" | "bearish" | None,
                "last_choch": "bullish" | "bearish" | None,
                "structure_strength": float (0.0 - 1.0),
                "swing_highs": [{"index", "price", "confirmed_at"}, ...],
                "swing_lows": [{"index", "price", "confirmed_at"}, ...],
                "structure_points": [{"type", "label", "index", "price", "confirmed_at"}, ...],
                "bos_events": [{"direction", "index", "level", "close"}, ...],
                "choch_events": [{"direction", "index", "level", "close", "prev_trend"}, ...],
            }
        """
        if df is None or df.empty:
            return None

        min_candles = self.swing_window * 2 + 10
        if len(df) < min_candles:
            return None

        # Reset index para garantir iteracao por inteiros
        df = df.reset_index(drop=True)

        # 1. Deteccao de swings (fractal simetrico)
        swing_highs, swing_lows = self._detect_swings(df)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return self._empty_result(swing_highs, swing_lows)

        # 2. Classificacao HH/HL/LH/LL
        structure_points = self._classify_structure(swing_highs, swing_lows)
        trend = self._determine_trend(structure_points)

        # 3. Deteccao de BOS e CHoCH
        bos_events = self._detect_bos(df, swing_highs, swing_lows)
        choch_events = self._detect_choch(df, structure_points)

        last_bos = bos_events[-1]["direction"] if bos_events else None
        last_choch = choch_events[-1]["direction"] if choch_events else None

        # 4. Calculo de structure_strength (0.0 - 1.0)
        strength = self._calculate_strength(
            trend, structure_points, bos_events, len(df)
        )

        return {
            "trend": trend,
            "last_bos": last_bos,
            "last_choch": last_choch,
            "structure_strength": round(strength, 4),
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "structure_points": structure_points,
            "bos_events": bos_events,
            "choch_events": choch_events,
        }

    # ==========================================================
    # 1. Swing Detection (Fractal Simetrico)
    # PRD Secao 1: Definicao de Swing
    # ==========================================================

    def _detect_swings(
        self, df: pd.DataFrame
    ) -> tuple[list[dict], list[dict]]:
        """
        Metodo fractal simetrico com janela N (PRD Secao 1).

        Swing High em i:
            High[i] > High[i-1], High[i-2], ..., High[i-N]
            AND
            High[i] > High[i+1], High[i+2], ..., High[i+N]

        Swing Low em i:
            Low[i] < Low[i-1], Low[i-2], ..., Low[i-N]
            AND
            Low[i] < Low[i+1], Low[i+2], ..., Low[i+N]

        Anti-lookahead: swing em i so e confirmado no candle i+N.
        Os ultimos N candles nao geram swings (dados futuros ausentes).
        """
        N = self.swing_window
        highs = df["high"].values
        lows = df["low"].values

        swing_highs = []
        swing_lows = []

        # Iterar de N ate len-N (swing em i requer N candles apos)
        for i in range(N, len(df) - N):
            # --- Swing High ---
            # High[i] estritamente maior que todos os N vizinhos a esquerda e direita
            left_h = highs[i - N : i]       # N elementos antes de i
            right_h = highs[i + 1 : i + N + 1]  # N elementos apos i
            if np.all(highs[i] > left_h) and np.all(highs[i] > right_h):
                swing_highs.append({
                    "index": i,
                    "price": float(highs[i]),
                    "confirmed_at": i + N,
                })

            # --- Swing Low ---
            # Low[i] estritamente menor que todos os N vizinhos
            left_l = lows[i - N : i]
            right_l = lows[i + 1 : i + N + 1]
            if np.all(lows[i] < left_l) and np.all(lows[i] < right_l):
                swing_lows.append({
                    "index": i,
                    "price": float(lows[i]),
                    "confirmed_at": i + N,
                })

        return swing_highs, swing_lows

    # ==========================================================
    # 2. Structure Classification (HH/HL/LH/LL)
    # PRD Secao 2: Estrutura de Mercado
    # ==========================================================

    def _classify_structure(
        self, swing_highs: list[dict], swing_lows: list[dict]
    ) -> list[dict]:
        """
        PRD Secao 2 - Regras:

        Tendencia de alta:
            HH = ultimo swing high > swing high anterior
            HL = ultimo swing low > swing low anterior

        Tendencia de baixa:
            LH = ultimo swing high < anterior
            LL = ultimo swing low < anterior
        """
        points = []

        # Classificar swing highs consecutivos
        for k in range(1, len(swing_highs)):
            prev = swing_highs[k - 1]
            curr = swing_highs[k]
            label = "HH" if curr["price"] > prev["price"] else "LH"
            points.append({
                "type": "swing_high",
                "label": label,
                "index": curr["index"],
                "price": curr["price"],
                "confirmed_at": curr["confirmed_at"],
            })

        # Classificar swing lows consecutivos
        for k in range(1, len(swing_lows)):
            prev = swing_lows[k - 1]
            curr = swing_lows[k]
            label = "HL" if curr["price"] > prev["price"] else "LL"
            points.append({
                "type": "swing_low",
                "label": label,
                "index": curr["index"],
                "price": curr["price"],
                "confirmed_at": curr["confirmed_at"],
            })

        # Ordenar cronologicamente
        points.sort(key=lambda p: p["index"])
        return points

    def _determine_trend(self, structure_points: list[dict]) -> str:
        """
        PRD Secao 2 - Classificacao por votacao majoritaria:

        Analisa os ultimos 6 structure_points.
        Conta labels bullish (HH, HL) vs bearish (LH, LL).
        - Se bullish predomina -> "bullish"
        - Se bearish predomina -> "bearish"
        - Empate ou insuficiente -> "range"
        """
        if len(structure_points) < 2:
            return "range"

        # Limita analise aos ultimos N pontos para evitar ruido historico
        recent = structure_points[-6:] if len(structure_points) > 6 else structure_points

        bullish_count = 0  # HH + HL
        bearish_count = 0  # LH + LL

        for p in recent:
            if p["label"] in ("HH", "HL"):
                bullish_count += 1
            elif p["label"] in ("LH", "LL"):
                bearish_count += 1

        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        return "range"

    # ==========================================================
    # 3. BOS Detection
    # PRD Secao 3: Break of Structure
    # ==========================================================

    def _detect_bos(
        self,
        df: pd.DataFrame,
        swing_highs: list[dict],
        swing_lows: list[dict],
    ) -> list[dict]:
        """
        PRD Secao 3:

        BOS Bullish:
            Close[i] > ultimo swing high valido
            AND Close[i] >= level * (1 + BOS_THRESHOLD)
            AND body_ratio > 0.6
            AND range > media dos ultimos N candles

        BOS Bearish:
            Close[i] <= level * (1 - BOS_THRESHOLD)
            AND body_ratio > 0.6
            AND range > media dos ultimos N candles

        Anti-lookahead: no candle i, so usa swings com confirmed_at <= i.
        Cada nivel so dispara BOS uma vez (dedup).
        """
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        ranges = highs - lows

        # Pre-compute media de ranges para filtro de qualidade
        avg_ranges = np.full(len(df), np.nan)
        for i in range(self.bos_range_lookback, len(df)):
            avg_ranges[i] = np.mean(ranges[i - self.bos_range_lookback : i])

        bos_events = []

        # Ponteiros para swings confirmados (avancam monotonicamente)
        # Swings ja estao ordenados por index (e portanto por confirmed_at)
        active_sh = None  # Swing high ativo (ainda nao rompido)
        active_sl = None  # Swing low ativo
        sh_ptr = 0
        sl_ptr = 0
        start = self.swing_window * 2

        for i in range(start, len(df)):
            # Atualiza swing highs confirmados ate o candle i
            while sh_ptr < len(swing_highs) and swing_highs[sh_ptr]["confirmed_at"] <= i:
                active_sh = swing_highs[sh_ptr]
                sh_ptr += 1

            # Atualiza swing lows confirmados ate o candle i
            while sl_ptr < len(swing_lows) and swing_lows[sl_ptr]["confirmed_at"] <= i:
                active_sl = swing_lows[sl_ptr]
                sl_ptr += 1

            # --- BOS Bullish ---
            # Close[i] >= level * (1 + BOS_THRESHOLD)
            if active_sh is not None:
                level = active_sh["price"]
                if closes[i] >= level * (1 + self.bos_threshold):
                    if self._is_quality_bos_candle(
                        opens[i], highs[i], lows[i], closes[i],
                        ranges[i], avg_ranges[i]
                    ):
                        bos_events.append({
                            "direction": "bullish",
                            "index": i,
                            "level": float(level),
                            "close": float(closes[i]),
                        })
                        active_sh = None  # Consumido, proximo swing sera o ativo

            # --- BOS Bearish ---
            # Close[i] <= level * (1 - BOS_THRESHOLD)
            if active_sl is not None:
                level = active_sl["price"]
                if closes[i] <= level * (1 - self.bos_threshold):
                    if self._is_quality_bos_candle(
                        opens[i], highs[i], lows[i], closes[i],
                        ranges[i], avg_ranges[i]
                    ):
                        bos_events.append({
                            "direction": "bearish",
                            "index": i,
                            "level": float(level),
                            "close": float(closes[i]),
                        })
                        active_sl = None

        return bos_events

    def _is_quality_bos_candle(
        self,
        open_: float,
        high: float,
        low: float,
        close: float,
        candle_range: float,
        avg_range: float,
    ) -> bool:
        """
        PRD Secao 3 - Filtro de qualidade:
            - body_ratio > 0.6
            - range > media dos ultimos N candles
        """
        if candle_range <= 0:
            return False

        # body_ratio = |close - open| / (high - low)
        body_ratio = abs(close - open_) / candle_range
        if body_ratio <= self.bos_body_ratio_min:
            return False

        # range > media (se avg disponivel)
        if not np.isnan(avg_range):
            if candle_range <= avg_range:
                return False

        return True

    # ==========================================================
    # 4. CHoCH Detection
    # PRD Secao 4: Change of Character
    # ==========================================================

    def _detect_choch(
        self, df: pd.DataFrame, structure_points: list[dict]
    ) -> list[dict]:
        """
        PRD Secao 4:

        CHoCH Bullish:
            Mercado estava bearish (LH/LL)
            AND Close rompe acima do ultimo LH
            AND _is_quality_choch_candle() == True

        CHoCH Bearish:
            Mercado estava bullish
            AND Close rompe abaixo do ultimo HL
            AND _is_quality_choch_candle() == True

        Regra: CHoCH sempre vem ANTES de mudanca de tendencia confirmada.
        Anti-lookahead: usa apenas structure_points com confirmed_at <= candle atual.
        Cada nivel so dispara CHoCH uma vez.
        """
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        ranges = highs - lows

        # Media de ranges para filtro de qualidade CHoCH (usa choch_range_lookback)
        avg_ranges = np.full(len(df), np.nan)
        for idx in range(self.choch_range_lookback, len(df)):
            avg_ranges[idx] = np.mean(ranges[idx - self.choch_range_lookback : idx])
        choch_events = []

        # Estado corrente (atualizado conforme structure points sao confirmados)
        current_trend = "range"
        last_lh_price = None   # Preco do ultimo LH (para CHoCH bullish)
        last_lh_key = None
        last_hl_price = None   # Preco do ultimo HL (para CHoCH bearish)
        last_hl_key = None
        last_high_label = None
        last_low_label = None

        # Index structure points por confirmed_at para lookup O(1)
        sp_by_confirmed: dict[int, list[dict]] = {}
        for sp in structure_points:
            ca = sp["confirmed_at"]
            if ca not in sp_by_confirmed:
                sp_by_confirmed[ca] = []
            sp_by_confirmed[ca].append(sp)

        used_choch = set()

        for i in range(len(df)):
            # Atualiza estado com structure points confirmados neste candle
            if i in sp_by_confirmed:
                for sp in sp_by_confirmed[i]:
                    if sp["type"] == "swing_high":
                        last_high_label = sp["label"]
                        if sp["label"] == "LH":
                            last_lh_price = sp["price"]
                            last_lh_key = sp["index"]
                    elif sp["type"] == "swing_low":
                        last_low_label = sp["label"]
                        if sp["label"] == "HL":
                            last_hl_price = sp["price"]
                            last_hl_key = sp["index"]

                    # Reavalia tendencia
                    if last_high_label == "HH" and last_low_label == "HL":
                        current_trend = "bullish"
                    elif last_high_label == "LH" and last_low_label == "LL":
                        current_trend = "bearish"

            # --- CHoCH Bullish ---
            # Mercado bearish + Close > ultimo LH
            if (
                current_trend == "bearish"
                and last_lh_price is not None
                and last_lh_key is not None
            ):
                key = ("choch_bull", last_lh_key)
                if key not in used_choch and closes[i] > last_lh_price:
                    if self._is_quality_choch_candle(
                        opens[i], closes[i], ranges[i], avg_ranges[i]
                    ):
                        choch_events.append({
                            "direction": "bullish",
                            "index": i,
                            "level": float(last_lh_price),
                            "close": float(closes[i]),
                            "prev_trend": "bearish",
                        })
                        used_choch.add(key)
                        current_trend = "range"  # Transicao
                        last_lh_price = None

            # --- CHoCH Bearish ---
            # Mercado bullish + Close < ultimo HL
            if (
                current_trend == "bullish"
                and last_hl_price is not None
                and last_hl_key is not None
            ):
                key = ("choch_bear", last_hl_key)
                if key not in used_choch and closes[i] < last_hl_price:
                    if self._is_quality_choch_candle(
                        opens[i], closes[i], ranges[i], avg_ranges[i]
                    ):
                        choch_events.append({
                            "direction": "bearish",
                            "index": i,
                            "level": float(last_hl_price),
                            "close": float(closes[i]),
                            "prev_trend": "bullish",
                        })
                        used_choch.add(key)
                        current_trend = "range"
                        last_hl_price = None

        return choch_events

    def _is_quality_choch_candle(
        self,
        open_: float,
        close: float,
        candle_range: float,
        avg_range: float,
    ) -> bool:
        """
        Filtro de qualidade para candle de CHoCH:
            - body_ratio > choch_body_ratio_min
            - range > avg_range * choch_range_multiplier (se avg disponivel)
        """
        if candle_range <= 0:
            return False

        body_ratio = abs(close - open_) / candle_range
        if body_ratio <= self.choch_body_ratio_min:
            return False

        if not np.isnan(avg_range):
            if candle_range <= avg_range * self.choch_range_multiplier:
                return False

        return True

    # ==========================================================
    # Structure Strength (Score normalizado 0.0 - 1.0)
    # PRD Secao 11: todos scores 0.0 -> 1.0
    # ==========================================================

    def _calculate_strength(
        self,
        trend: str,
        structure_points: list[dict],
        bos_events: list[dict],
        total_candles: int,
    ) -> float:
        """
        Calcula structure_strength normalizado (0.0 a 1.0).

        Componentes (derivados dos conceitos do PRD):
        - Tendencia definida vs range (base)
        - Consistencia: sequencia de pontos na mesma direcao
        - Confirmacao: presenca e recencia de BOS
        """
        # Base: tendencia definida tem mais peso que range
        if trend == "range":
            base = 0.3
        else:
            base = 0.5

        # Consistencia: contar pontos consecutivos alinhados com a tendencia
        if trend == "bullish":
            aligned_labels = {"HH", "HL"}
        elif trend == "bearish":
            aligned_labels = {"LH", "LL"}
        else:
            aligned_labels = set()

        consecutive = 0
        for p in reversed(structure_points):
            if p["label"] in aligned_labels:
                consecutive += 1
            else:
                break

        # Bonus por consistencia: max +0.3 para 6+ pontos consecutivos
        consistency_bonus = min(consecutive / 6.0, 1.0) * 0.3

        # Bonus por BOS confirmado: max +0.2 (mais recente = mais forte)
        bos_bonus = 0.0
        if bos_events:
            last_bos = bos_events[-1]
            candles_since = total_candles - 1 - last_bos["index"]
            if candles_since <= 5:
                bos_bonus = 0.20
            elif candles_since <= 15:
                bos_bonus = 0.15
            else:
                bos_bonus = 0.10

        strength = base + consistency_bonus + bos_bonus
        return min(max(strength, 0.0), 1.0)

    # ==========================================================
    # Helpers
    # ==========================================================

    def _empty_result(
        self, swing_highs: list[dict], swing_lows: list[dict]
    ) -> dict:
        """Resultado padrao quando nao ha estrutura suficiente."""
        return {
            "trend": "range",
            "last_bos": None,
            "last_choch": None,
            "structure_strength": 0.0,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "structure_points": [],
            "bos_events": [],
            "choch_events": [],
        }
