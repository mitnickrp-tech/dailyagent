from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List, Optional

import MetaTrader5 as mt5
import pandas as pd


# =========================
# CONFIG
# =========================
SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "XAUUSD",
]

TIMEFRAME = mt5.TIMEFRAME_M15
BARS = 250

DEFAULT_MAX_SPREAD_POINTS = 60
SPECIAL_SPREAD_LIMITS = {
    "XAUUSD": 120,
    "BTCUSD": 5000,
}

MIN_ATR_RELATIVE = 0.0003
LOOKBACK_BREAKOUT = 10

# Ajuste para o caminho real do seu MT5
OUTPUT_JSON_PATH = Path(r"C:\Users\Ivan Encinas\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\market_filter.json")


# =========================
# MT5
# =========================
def initialize_mt5() -> None:
    if not mt5.initialize():
        code, message = mt5.last_error()
        raise RuntimeError(f"Falha ao inicializar MT5: {code} | {message}")


def shutdown_mt5() -> None:
    mt5.shutdown()


# =========================
# HELPERS
# =========================
def normalize(series: pd.Series) -> pd.Series:
    return (series - series.min()) / (series.max() - series.min() + 1e-9)


def get_max_spread_for_symbol(symbol: str) -> float:
    return SPECIAL_SPREAD_LIMITS.get(symbol, DEFAULT_MAX_SPREAD_POINTS)


def get_rates_df(symbol: str, timeframe: int, bars: int = 250) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        raise ValueError(f"Sem dados para {symbol}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["ema_20"] = data["close"].ewm(span=20, adjust=False).mean()
    data["ema_50"] = data["close"].ewm(span=50, adjust=False).mean()
    data["atr_14"] = calculate_atr(data, 14)
    data["return_1_pct"] = data["close"].pct_change(1) * 100.0
    data["return_5_pct"] = data["close"].pct_change(5) * 100.0
    return data


def classify_trend(last_close: float, ema_20: float, ema_50: float) -> str:
    if last_close > ema_20 > ema_50:
        return "bullish"
    if last_close < ema_20 < ema_50:
        return "bearish"
    return "neutral"


def classify_regime(
    trend: str,
    breakout_up: bool,
    breakout_down: bool,
    atr_relative: float,
    median_atr_relative: float,
) -> str:
    high_vol = atr_relative > median_atr_relative

    if breakout_up:
        return "breakout_up"
    if breakout_down:
        return "breakout_down"
    if trend in {"bullish", "bearish"} and high_vol:
        return "trending"
    if trend == "neutral" and high_vol:
        return "volatile_range"
    return "ranging"


def current_hour_allowed(symbol: str, hour: int) -> bool:
    # Horas baseadas no seu estudo
    per_symbol_hours = {
        "EURUSD": {14, 15, 16, 17},
        "GBPUSD": {13, 14, 15, 16, 17, 19},
        "XAUUSD": {8, 9, 10, 14, 15, 16, 17},
        "USDJPY": {15, 16, 17},
        "AUDUSD": {16, 17},
        "USDCAD": {14, 15, 16, 17},
    }

    allowed = per_symbol_hours.get(symbol)
    if allowed is None:
        return 14 <= hour <= 17

    return hour in allowed


def determine_priority_and_risk(regime: str, tradable: bool) -> tuple[str, float]:
    if not tradable:
        return "low", 0.0

    if regime in {"breakout_up", "breakout_down"}:
        return "high", 1.0

    if regime == "trending":
        return "high", 0.8

    if regime == "volatile_range":
        return "medium", 0.5

    return "low", 0.0


def determine_directions(trend: str, regime: str, tradable: bool) -> tuple[bool, bool]:
    if not tradable:
        return False, False

    if regime == "breakout_up":
        return True, False

    if regime == "breakout_down":
        return False, True

    if trend == "bullish":
        return True, False

    if trend == "bearish":
        return False, True

    return False, False


def analyze_symbol(symbol: str, timeframe: int = TIMEFRAME, bars: int = BARS) -> Optional[dict]:
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if symbol_info is None or tick is None:
        print(f"[WARN] Não foi possível ler info/tick de {symbol}")
        return None

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"[WARN] Não foi possível selecionar {symbol} no Market Watch")
            return None

    df = get_rates_df(symbol, timeframe=timeframe, bars=bars)
    df = add_indicators(df)

    if len(df) < 60:
        print(f"[WARN] Poucos dados para {symbol}")
        return None

    point = float(symbol_info.point or 0.0)
    digits = int(symbol_info.digits or 0)
    if point <= 0:
        return None

    bid = float(tick.bid)
    ask = float(tick.ask)
    spread_points = (ask - bid) / point

    last = df.iloc[-1]
    prev = df.iloc[-2]

    last_close = float(last["close"])
    return_1_pct = float(last["return_1_pct"])
    return_5_pct = float(last["return_5_pct"])
    ema_20 = float(last["ema_20"])
    ema_50 = float(last["ema_50"])
    atr_14 = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else math.nan
    atr_relative = atr_14 / last_close if last_close > 0 and not math.isnan(atr_14) else math.nan

    range_slice = df.iloc[-(LOOKBACK_BREAKOUT + 1):-1]
    range_high_10 = float(range_slice["high"].max())
    range_low_10 = float(range_slice["low"].min())

    breakout_up = bool(last_close > range_high_10 and prev["close"] <= range_high_10)
    breakout_down = bool(last_close < range_low_10 and prev["close"] >= range_low_10)

    trend = classify_trend(last_close, ema_20, ema_50)

    # Mediana local do símbolo
    median_atr_relative = float((df["atr_14"] / df["close"]).median())
    regime = classify_regime(
        trend=trend,
        breakout_up=breakout_up,
        breakout_down=breakout_down,
        atr_relative=float(atr_relative) if not math.isnan(atr_relative) else 0.0,
        median_atr_relative=median_atr_relative if not math.isnan(median_atr_relative) else 0.0,
    )

    max_spread = get_max_spread_for_symbol(symbol)
    spread_ok = spread_points <= max_spread
    atr_ok = bool(not math.isnan(atr_relative) and atr_relative >= MIN_ATR_RELATIVE)
    momentum_ok = abs(return_5_pct) > 0.02

    tradable = bool(spread_ok and atr_ok and momentum_ok)

    priority, risk_multiplier = determine_priority_and_risk(regime, tradable)
    allow_long, allow_short = determine_directions(trend, regime, tradable)

    now_hour = pd.Timestamp.now().hour
    allowed_now = current_hour_allowed(symbol, now_hour)

    return {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "spread_points": round(float(spread_points), 2),
        "point": point,
        "digits": digits,
        "last_close": last_close,
        "return_1_pct": round(return_1_pct, 6),
        "return_5_pct": round(return_5_pct, 6),
        "ema_20": ema_20,
        "ema_50": ema_50,
        "atr_14": atr_14,
        "atr_relative": atr_relative,
        "breakout_up": breakout_up,
        "breakout_down": breakout_down,
        "trend": trend,
        "regime": regime,
        "spread_ok": spread_ok,
        "atr_ok": atr_ok,
        "momentum_ok": momentum_ok,
        "tradable": tradable,
        "allow_long": allow_long,
        "allow_short": allow_short,
        "priority": priority,
        "risk_multiplier": risk_multiplier,
        "allowed_now": allowed_now,
    }


def build_scanner(symbols: List[str], timeframe: int = TIMEFRAME, bars: int = BARS) -> pd.DataFrame:
    rows = []

    for symbol in symbols:
        try:
            row = analyze_symbol(symbol, timeframe=timeframe, bars=bars)
            if row is not None:
                rows.append(row)
        except Exception as exc:
            print(f"[ERRO] {symbol}: {exc}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df["n_momentum"] = normalize(df["return_5_pct"].abs())
    df["n_atr_relative"] = normalize(df["atr_relative"].fillna(0))
    df["n_spread"] = normalize(df["spread_points"].fillna(0))

    df["score"] = (
        df["n_momentum"] * 0.35
        + df["n_atr_relative"] * 0.35
        - df["n_spread"] * 0.20
        + df["allow_long"].astype(float) * 0.05
        + df["allow_short"].astype(float) * 0.05
    )

    return df.sort_values("score", ascending=False).reset_index(drop=True)


def export_json(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for _, row in df.iterrows():
        records.append({
            "symbol": row["symbol"],
            "allow_long": bool(row["allow_long"]),
            "allow_short": bool(row["allow_short"]),
            "priority": str(row["priority"]),
            "risk_multiplier": float(row["risk_multiplier"]),
            "tradable": bool(row["tradable"]),
            "trend": str(row["trend"]),
            "regime": str(row["regime"]),
            "allowed_now": bool(row["allowed_now"]),
            "score": float(round(row["score"], 6)),
        })

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nJSON salvo em: {output_path}")


if __name__ == "__main__":
    initialize_mt5()

    try:
        df = build_scanner(SYMBOLS, timeframe=TIMEFRAME, bars=BARS)

        if df.empty:
            print("Nenhum dado encontrado.")
        else:
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 220)
            pd.set_option("display.float_format", lambda x: f"{x:.6f}")

            print(df[[
                "symbol", "trend", "regime", "tradable",
                "allow_long", "allow_short",
                "priority", "risk_multiplier",
                "allowed_now", "score"
            ]])

            export_json(df, OUTPUT_JSON_PATH)
    finally:
        shutdown_mt5()