"""
Testes deterministicos para Structure Engine e Liquidity Engine.
Valida que as regras matematicas do PRD estao implementadas corretamente.
"""

import sys
import os
import types
import numpy as np
import pandas as pd

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

sys.modules["dailyagent"] = _da_mod
sys.modules["dailyagent.core"] = _core_mod
sys.modules["dailyagent.core.logger"] = _core_logger_mod

from dailyagent.structure.engine import StructureEngine
from dailyagent.liquidity.engine import LiquidityEngine


def make_df(highs, lows, opens=None, closes=None):
    """Cria DataFrame de teste a partir de listas."""
    n = len(highs)
    if opens is None:
        opens = [(h + l) / 2 for h, l in zip(highs, lows)]
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })


# ==========================================
# Test 1: Swing Detection (Fractal Simetrico)
# ==========================================
def test_swing_detection():
    """
    Testa o metodo fractal com SWING_WINDOW=3.
    Swing High em i: High[i] > High[i-1..i-3] AND High[i] > High[i+1..i+3]
    """
    # Constroi uma serie com um swing high claro no indice 10
    # e um swing low claro no indice 15
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n

    # Swing high em 10: high=1.5, vizinhos < 1.5
    highs[7] = 1.1; highs[8] = 1.2; highs[9] = 1.3
    highs[10] = 1.5
    highs[11] = 1.3; highs[12] = 1.2; highs[13] = 1.1

    # Swing low em 17: low=0.7, vizinhos > 0.7
    lows[14] = 0.85; lows[15] = 0.8; lows[16] = 0.75
    lows[17] = 0.7
    lows[18] = 0.75; lows[19] = 0.8; lows[20] = 0.85

    df = make_df(highs, lows)
    engine = StructureEngine(swing_window=3)
    sh, sl = engine._detect_swings(df)

    # Verifica swing high em indice 10
    sh_indices = [s["index"] for s in sh]
    assert 10 in sh_indices, f"Swing high esperado em 10, encontrados: {sh_indices}"
    assert sh[sh_indices.index(10)]["price"] == 1.5

    # Verifica swing low em indice 17
    sl_indices = [s["index"] for s in sl]
    assert 17 in sl_indices, f"Swing low esperado em 17, encontrados: {sl_indices}"
    assert sl[sl_indices.index(17)]["price"] == 0.7

    # confirmed_at deve ser index + window
    for s in sh:
        assert s["confirmed_at"] == s["index"] + 3

    print("  [PASS] test_swing_detection")


# ==========================================
# Test 2: Structure Classification (HH/HL/LH/LL)
# ==========================================
def test_structure_classification():
    """
    Testa HH/HL/LH/LL e determinacao de tendencia.
    """
    engine = StructureEngine()

    # Bullish: cada swing high maior que anterior, cada swing low maior que anterior
    swing_highs = [
        {"index": 5, "price": 1.10, "confirmed_at": 8},
        {"index": 15, "price": 1.15, "confirmed_at": 18},  # HH
        {"index": 25, "price": 1.20, "confirmed_at": 28},  # HH
    ]
    swing_lows = [
        {"index": 10, "price": 1.05, "confirmed_at": 13},
        {"index": 20, "price": 1.08, "confirmed_at": 23},  # HL
        {"index": 30, "price": 1.12, "confirmed_at": 33},  # HL
    ]

    points = engine._classify_structure(swing_highs, swing_lows)
    trend = engine._determine_trend(points)

    assert trend == "bullish", f"Esperado bullish, obteve {trend}"

    # Verifica labels
    high_labels = [p["label"] for p in points if p["type"] == "swing_high"]
    low_labels = [p["label"] for p in points if p["type"] == "swing_low"]
    assert all(l == "HH" for l in high_labels), f"Esperado todos HH: {high_labels}"
    assert all(l == "HL" for l in low_labels), f"Esperado todos HL: {low_labels}"

    # Bearish: swing highs descendentes, swing lows descendentes
    swing_highs_bear = [
        {"index": 5, "price": 1.20, "confirmed_at": 8},
        {"index": 15, "price": 1.15, "confirmed_at": 18},  # LH
    ]
    swing_lows_bear = [
        {"index": 10, "price": 1.10, "confirmed_at": 13},
        {"index": 20, "price": 1.05, "confirmed_at": 23},  # LL
    ]

    points_bear = engine._classify_structure(swing_highs_bear, swing_lows_bear)
    trend_bear = engine._determine_trend(points_bear)
    assert trend_bear == "bearish", f"Esperado bearish, obteve {trend_bear}"

    print("  [PASS] test_structure_classification")


# ==========================================
# Test 3: BOS Detection
# ==========================================
def test_bos_detection():
    """
    Testa BOS Bullish: Close > ultimo swing high * (1 + threshold).
    """
    # Cria dados com um swing high em 10 (price=1.5) e close que rompe em 18
    n = 25
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing high em 10
    for d in range(1, 4):
        highs[10 - d] = 1.0 + d * 0.1
        highs[10 + d] = 1.0 + d * 0.1
    highs[7] = 1.2; highs[8] = 1.3; highs[9] = 1.4
    highs[10] = 1.5
    highs[11] = 1.4; highs[12] = 1.3; highs[13] = 1.2

    # Candle 18 rompe com closes acima de 1.5 * 1.001 = 1.5015
    # Precisa ter body_ratio > 0.6 e range > avg
    closes[18] = 1.52
    opens[18] = 1.48
    highs[18] = 1.53
    lows[18] = 1.47

    df = make_df(highs, lows, opens, closes)
    engine = StructureEngine(swing_window=3, bos_threshold=0.001)

    swing_highs, swing_lows = engine._detect_swings(df)
    bos = engine._detect_bos(df, swing_highs, swing_lows)

    # Deve haver um BOS bullish
    bullish_bos = [b for b in bos if b["direction"] == "bullish"]
    assert len(bullish_bos) > 0, f"BOS bullish esperado, nenhum encontrado. BOS: {bos}"
    assert bullish_bos[0]["level"] == 1.5

    print("  [PASS] test_bos_detection")


# ==========================================
# Test 4: Equal Levels Detection
# ==========================================
def test_equal_levels():
    """
    Testa Equal Highs: |High[i] - High[j]| <= tolerance.
    """
    engine = LiquidityEngine(equal_tolerance=0.0003, min_swing_distance=6)

    # Swing highs com precos muito proximos (dentro de tolerance)
    swings = [
        {"index": 5, "price": 1.0850, "confirmed_at": 8},
        {"index": 15, "price": 1.0852, "confirmed_at": 18},  # diff = 0.0002 <= 0.0003
        {"index": 25, "price": 1.1000, "confirmed_at": 28},  # diff = 0.015 > 0.0003
    ]

    equal = engine._detect_equal_levels(swings)

    assert len(equal) == 1, f"Esperado 1 equal level, obteve {len(equal)}"
    assert equal[0]["touches"] == 2
    # Preco medio: (1.0850 + 1.0852) / 2 = 1.0851
    assert abs(equal[0]["price"] - 1.0851) < 0.0001

    # Teste com nenhum equal (todos distantes)
    swings_far = [
        {"index": 5, "price": 1.0850, "confirmed_at": 8},
        {"index": 15, "price": 1.0900, "confirmed_at": 18},
    ]
    equal_far = engine._detect_equal_levels(swings_far)
    assert len(equal_far) == 0

    print("  [PASS] test_equal_levels")


# ==========================================
# Test 5: Sweep Strength Formula
# ==========================================
def test_sweep_strength():
    """
    PRD: sweep_strength = (rompimento_distancia + velocidade_retorno + rejeicao_candle) / 3
    """
    engine = LiquidityEngine(sweep_lookahead=3)

    # Caso 1: sweep forte (grande break, retorno rapido, forte rejeicao)
    strength = engine._calculate_sweep_strength(
        break_distance=0.0010,      # 10 pips
        candles_to_return=1,        # retorno em 1 candle (mais rapido)
        return_candle_open=1.0860,
        return_candle_high=1.0870,  # upper wick = 1.0870 - 1.0860 = 0.0010
        return_candle_low=1.0840,   # range = 0.0030
        return_candle_close=1.0845,
        sweep_type="buy_side",
        avg_range_value=0.0010,     # break = 1 avg_range
    )

    # rompimento_distancia = min(0.0010/0.0010, 1.0) = 1.0
    # velocidade_retorno = 1.0 - (1-1)/3 = 1.0
    # rejeicao = upper_wick / range = 0.0010 / 0.0030 = 0.333
    expected = (1.0 + 1.0 + 0.0010 / 0.0030) / 3.0
    assert abs(strength - expected) < 0.001, f"Forca esperada ~{expected:.4f}, obteve {strength:.4f}"

    # Caso 2: sweep fraco (pequeno break, retorno lento)
    strength_weak = engine._calculate_sweep_strength(
        break_distance=0.0002,
        candles_to_return=3,        # lento
        return_candle_open=1.0850,
        return_candle_high=1.0855,
        return_candle_low=1.0845,
        return_candle_close=1.0850,
        sweep_type="buy_side",
        avg_range_value=0.0010,
    )

    assert strength_weak < strength, "Sweep fraco deve ter menor forca que sweep forte"

    print("  [PASS] test_sweep_strength")


# ==========================================
# Test 6: Full Pipeline Integration
# ==========================================
def test_full_pipeline():
    """
    Testa o pipeline completo: Structure -> Liquidity.
    Verifica que os engines se comunicam corretamente.
    """
    # Cria um cenario bullish com 50 candles
    np.random.seed(42)
    n = 50
    base = 1.0800
    trend_component = np.linspace(0, 0.0100, n)  # tendencia de alta
    noise = np.random.normal(0, 0.0005, n)
    prices = base + trend_component + noise

    # Adiciona volatilidade para criar swings
    highs = prices + np.abs(np.random.normal(0.0010, 0.0003, n))
    lows = prices - np.abs(np.random.normal(0.0010, 0.0003, n))
    opens = prices + np.random.normal(0, 0.0003, n)
    closes = prices + np.random.normal(0, 0.0003, n)

    # Garante high >= max(open,close) e low <= min(open,close)
    for i in range(n):
        highs[i] = max(highs[i], opens[i], closes[i])
        lows[i] = min(lows[i], opens[i], closes[i])

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
    })

    # Structure Engine
    structure_engine = StructureEngine(swing_window=3)
    structure = structure_engine.analyze(df)

    assert structure is not None, "StructureEngine retornou None"
    assert structure["trend"] in ("bullish", "bearish", "range")
    assert 0.0 <= structure["structure_strength"] <= 1.0
    assert len(structure["swing_highs"]) >= 0
    assert len(structure["swing_lows"]) >= 0

    # Liquidity Engine
    liquidity_engine = LiquidityEngine(equal_tolerance=0.0005)
    liquidity = liquidity_engine.analyze(df, structure)

    assert liquidity is not None, "LiquidityEngine retornou None"
    assert liquidity["sweep"] in ("buy_side", "sell_side", None)
    assert 0.0 <= liquidity["strength"] <= 1.0
    assert isinstance(liquidity["equal_highs"], list)
    assert isinstance(liquidity["equal_lows"], list)
    assert isinstance(liquidity["sweeps"], list)

    print("  [PASS] test_full_pipeline")
    print(f"         Structure: trend={structure['trend']}, "
          f"strength={structure['structure_strength']}, "
          f"swings_h={len(structure['swing_highs'])}, "
          f"swings_l={len(structure['swing_lows'])}")
    print(f"         Liquidity: sweep={liquidity['sweep']}, "
          f"strength={liquidity['strength']}, "
          f"eq_highs={len(liquidity['equal_highs'])}, "
          f"eq_lows={len(liquidity['equal_lows'])}, "
          f"sweeps={len(liquidity['sweeps'])}")


# ==========================================
# Test 7: Anti-Lookahead Bias
# ==========================================
def test_no_lookahead_bias():
    """
    Verifica que swings nao sao detectados nos ultimos N candles
    (onde N=swing_window) e que BOS so usa swings confirmados.
    """
    engine = StructureEngine(swing_window=3)

    n = 20
    highs = [1.0] * n
    lows = [0.9] * n

    # Coloca um "swing high" potencial no indice 18 (ultimos 3 candles: 17,18,19)
    # Este NAO deve ser detectado pois nao tem 3 candles a direita
    highs[18] = 2.0

    df = make_df(highs, lows)
    sh, sl = engine._detect_swings(df)

    sh_indices = [s["index"] for s in sh]
    assert 18 not in sh_indices, "Swing high no indice 18 NAO deveria ser detectado (lookahead)"

    # Swing no indice 10 com window=3: confirmed_at = 13
    highs_v2 = [1.0] * n
    lows_v2 = [0.9] * n
    highs_v2[8] = 1.2; highs_v2[9] = 1.3
    highs_v2[10] = 1.5
    highs_v2[11] = 1.3; highs_v2[12] = 1.2
    df2 = make_df(highs_v2, lows_v2)
    sh2, _ = engine._detect_swings(df2)

    for s in sh2:
        if s["index"] == 10:
            assert s["confirmed_at"] == 13, f"confirmed_at deveria ser 13, obteve {s['confirmed_at']}"

    print("  [PASS] test_no_lookahead_bias")


# ==========================================
# Test 8: Determinismo
# ==========================================
def test_deterministic():
    """
    Verifica que a mesma entrada produz EXATAMENTE a mesma saida.
    """
    np.random.seed(123)
    n = 40
    prices = np.cumsum(np.random.normal(0, 0.001, n)) + 1.10
    highs = prices + 0.001
    lows = prices - 0.001
    df = pd.DataFrame({
        "open": prices,
        "high": highs,
        "low": lows,
        "close": prices,
    })

    engine = StructureEngine(swing_window=3)
    result1 = engine.analyze(df.copy())
    result2 = engine.analyze(df.copy())

    assert result1["trend"] == result2["trend"]
    assert result1["structure_strength"] == result2["structure_strength"]
    assert len(result1["swing_highs"]) == len(result2["swing_highs"])
    assert len(result1["bos_events"]) == len(result2["bos_events"])

    print("  [PASS] test_deterministic")


# ==========================================
# Test 9: BOS Bearish Symmetric Threshold (#2)
# ==========================================
def test_bos_bearish_threshold():
    """
    BOS Bearish agora exige Close <= level * (1 - BOS_THRESHOLD).
    Um close logo abaixo do level mas sem ultrapassar o threshold NAO deve gerar BOS.
    """
    # Usa bos_range_lookback=1 para que avg_range seja facilmente controlavel
    engine = StructureEngine(swing_window=3, bos_threshold=0.01, bos_range_lookback=1)

    n = 30
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Swing low em 10 (price=0.80)
    lows[7] = 0.88; lows[8] = 0.85; lows[9] = 0.82
    lows[10] = 0.80
    lows[11] = 0.82; lows[12] = 0.85; lows[13] = 0.88

    # Candle 20: close = 0.795 -> level * (1-0.01) = 0.80 * 0.99 = 0.792
    # 0.795 > 0.792, portanto NAO deve gerar BOS bearish
    # Candle com body forte e range grande para passar filtro de qualidade
    closes[20] = 0.795
    opens[20] = 0.92
    highs[20] = 0.93
    lows[20] = 0.79  # range = 0.14, body = |0.795 - 0.92| = 0.125, ratio = 0.89

    df = make_df(highs, lows, opens, closes)
    sh, sl = engine._detect_swings(df)
    bos = engine._detect_bos(df, sh, sl)

    bear_bos = [b for b in bos if b["direction"] == "bearish"]
    bos_at_20 = [b for b in bear_bos if b["index"] == 20]
    assert len(bos_at_20) == 0, (
        f"Close 0.795 > threshold 0.792, NAO deveria gerar BOS. Encontrado: {bos_at_20}"
    )

    # Candle 22: close = 0.790 <= 0.792 -> DEVE gerar BOS bearish
    # Candle com body forte e range grande
    closes[22] = 0.790
    opens[22] = 0.92
    highs[22] = 0.93
    lows[22] = 0.785  # range = 0.145, body = |0.790 - 0.92| = 0.13, ratio = 0.896

    df2 = make_df(highs, lows, opens, closes)
    sh2, sl2 = engine._detect_swings(df2)
    bos2 = engine._detect_bos(df2, sh2, sl2)
    bear_bos2 = [b for b in bos2 if b["direction"] == "bearish"]
    assert len(bear_bos2) > 0, f"Close 0.790 <= 0.792 deveria gerar BOS bearish. BOS: {bos2}"

    print("  [PASS] test_bos_bearish_threshold")


# ==========================================
# Test 10: Sweep Close < Level (#1)
# ==========================================
def test_sweep_close_below_level():
    """
    Sweep buy-side: confirmacao requer close < level_price (nao retorno parcial).
    Sweep sell-side: confirmacao requer close > level_price.
    """
    engine = LiquidityEngine(sweep_lookahead=3, sweep_cooldown=50)

    n = 30
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    # Level buy-side em 1.10
    buy_levels = [{"price": 1.10, "type": "swing", "side": "buy_side",
                   "touches": 1, "first_index": 3, "last_index": 3}]

    # Candle 10: high = 1.12 (rompe acima de 1.10)
    highs[10] = 1.12
    opens[10] = 1.08
    closes[10] = 1.11

    # Candle 11: close = 1.105 -> acima de level (1.10) -> NAO confirma sweep
    closes[11] = 1.105
    opens[11] = 1.11
    highs[11] = 1.115
    lows[11] = 1.10

    # Candle 12: close = 1.09 -> abaixo de level (1.10) -> CONFIRMA sweep
    closes[12] = 1.09
    opens[12] = 1.10
    highs[12] = 1.105
    lows[12] = 1.085

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, buy_levels, [])

    # Deve haver sweep confirmado no candle 12 (nao 11)
    assert len(sweeps) >= 1, f"Esperado pelo menos 1 sweep, obteve {len(sweeps)}"
    sweep = sweeps[0]
    assert sweep["return_index"] == 12, (
        f"Sweep deveria confirmar no candle 12, confirmou em {sweep['return_index']}"
    )
    assert sweep["return_close"] < 1.10, "Return close deveria ser < level_price"

    print("  [PASS] test_sweep_close_below_level")


# ==========================================
# Test 11: Equal Levels Max Span (#5)
# ==========================================
def test_equal_levels_max_span():
    """
    Grupos de equal levels com span > EQUAL_MAX_SPAN devem ser descartados.
    """
    engine = LiquidityEngine(equal_tolerance=0.0003, min_swing_distance=6,
                             equal_max_span=50)

    # Grupo com span = 10 (dentro do limite)
    swings_close = [
        {"index": 5, "price": 1.0850, "confirmed_at": 8},
        {"index": 15, "price": 1.0852, "confirmed_at": 18},
    ]
    eq_close = engine._detect_equal_levels(swings_close)
    assert len(eq_close) == 1, f"Grupo com span 10 deveria ser aceito, obteve {len(eq_close)}"

    # Grupo com span = 100 (excede o limite de 50)
    swings_far = [
        {"index": 5, "price": 1.0850, "confirmed_at": 8},
        {"index": 105, "price": 1.0852, "confirmed_at": 108},
    ]
    eq_far = engine._detect_equal_levels(swings_far)
    assert len(eq_far) == 0, f"Grupo com span 100 > max 50 deveria ser descartado, obteve {len(eq_far)}"

    print("  [PASS] test_equal_levels_max_span")


# ==========================================
# Test 12: Sweep Cooldown (#6)
# ==========================================
def test_sweep_cooldown():
    """
    Apos um sweep, o mesmo nivel so pode ser usado de novo apos N candles de cooldown.
    """
    engine = LiquidityEngine(sweep_lookahead=3, sweep_cooldown=10)

    n = 40
    highs = [1.0] * n
    lows = [0.9] * n
    opens = [0.95] * n
    closes = [0.95] * n

    buy_levels = [{"price": 1.05, "type": "swing", "side": "buy_side",
                   "touches": 1, "first_index": 2, "last_index": 2}]

    # Primeiro sweep no candle 10
    highs[10] = 1.08
    opens[10] = 1.03
    closes[10] = 1.06
    closes[11] = 1.04  # close < 1.05 -> confirma
    opens[11] = 1.06; highs[11] = 1.07; lows[11] = 1.03

    # Segundo rompimento no candle 15 (5 candles depois, dentro do cooldown de 10)
    highs[15] = 1.08
    opens[15] = 1.03
    closes[15] = 1.06
    closes[16] = 1.04
    opens[16] = 1.06; highs[16] = 1.07; lows[16] = 1.03

    # Terceiro rompimento no candle 25 (15 candles depois do primeiro, fora do cooldown)
    highs[25] = 1.08
    opens[25] = 1.03
    closes[25] = 1.06
    closes[26] = 1.04
    opens[26] = 1.06; highs[26] = 1.07; lows[26] = 1.03

    df = make_df(highs, lows, opens, closes)
    sweeps = engine._detect_sweeps(df, buy_levels, [])

    # Deve ter 2 sweeps: candle 10 e candle 25 (candle 15 bloqueado pelo cooldown)
    break_indices = [s["break_index"] for s in sweeps]
    assert 10 in break_indices, f"Sweep no candle 10 esperado. Encontrados: {break_indices}"
    assert 15 not in break_indices, f"Sweep no candle 15 NAO esperado (cooldown). Encontrados: {break_indices}"
    assert 25 in break_indices, f"Sweep no candle 25 esperado (fora cooldown). Encontrados: {break_indices}"

    print("  [PASS] test_sweep_cooldown")


# ==========================================
# Test 13: Trend Detection Limit (#8)
# ==========================================
def test_trend_recent_points():
    """
    _determine_trend deve considerar apenas os ultimos 6 structure_points.
    """
    engine = StructureEngine()

    # Muitos pontos bearish antigos + 2 pontos bullish recentes
    old_bearish = [
        {"type": "swing_high", "label": "LH", "index": i * 10, "price": 1.0 - i * 0.01, "confirmed_at": i * 10 + 3}
        for i in range(1, 6)
    ] + [
        {"type": "swing_low", "label": "LL", "index": i * 10 + 5, "price": 0.9 - i * 0.01, "confirmed_at": i * 10 + 8}
        for i in range(1, 6)
    ]

    # Ultimos pontos sao bullish
    recent_bullish = [
        {"type": "swing_high", "label": "HH", "index": 200, "price": 1.20, "confirmed_at": 203},
        {"type": "swing_low", "label": "HL", "index": 205, "price": 1.15, "confirmed_at": 208},
        {"type": "swing_high", "label": "HH", "index": 210, "price": 1.25, "confirmed_at": 213},
        {"type": "swing_low", "label": "HL", "index": 215, "price": 1.18, "confirmed_at": 218},
    ]

    all_points = sorted(old_bearish + recent_bullish, key=lambda p: p["index"])

    trend = engine._determine_trend(all_points)
    assert trend == "bullish", (
        f"Com ultimos pontos bullish, trend deveria ser bullish, obteve {trend}"
    )

    print("  [PASS] test_trend_recent_points")


# ==========================================
# Main
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("DailyAgent 2.1 - Testes Structure + Liquidity Engine")
    print("=" * 60)
    print()

    tests = [
        test_swing_detection,
        test_structure_classification,
        test_bos_detection,
        test_equal_levels,
        test_sweep_strength,
        test_full_pipeline,
        test_no_lookahead_bias,
        test_deterministic,
        test_bos_bearish_threshold,
        test_sweep_close_below_level,
        test_equal_levels_max_span,
        test_sweep_cooldown,
        test_trend_recent_points,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print()
    print(f"Resultado: {passed}/{passed + failed} testes passaram")
    if failed > 0:
        print(f"  {failed} teste(s) falharam!")
        sys.exit(1)
    else:
        print("  Todos os testes passaram!")
        sys.exit(0)
