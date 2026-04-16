# 📄 PRD — DailyAgent 2.1

## 🎯 Visão do Produto

O **DailyAgent 2.1** é um sistema de análise de mercado baseado em:

* Estrutura de preço (market structure)
* Liquidez (SMC)
* Contexto temporal (sessões)
* Deslocamento (momentum real)
* Score probabilístico

👉 Ele **não depende de indicadores tradicionais como edge principal**
👉 Ele replica uma leitura **institucional / smart money**

---

# 🧠 Problema que resolve

A versão 2.0 (atual) sofre de:

* Dependência de indicadores genéricos
* Baixa diferenciação de edge
* Scoring simplista (linear)
* Uso excessivo de LLM para decisão
* Falta de contexto de liquidez e sessão

---

# 🚀 Objetivo da 2.1

Construir um sistema que:

* Detecta oportunidades reais baseadas em estrutura
* Filtra entradas ruins automaticamente
* Gera sinais com maior qualidade (menos quantidade, mais precisão)
* Permite análise estatística posterior (edge real)

---

# 🧩 Arquitetura Funcional

## Pipeline principal

```text
Market Data (MT5)
   ↓
Structure Engine
   ↓
Liquidity Engine
   ↓
Session Engine
   ↓
Displacement Engine
   ↓
Zone Engine
   ↓
Setup Engine
   ↓
Scoring Engine (Probabilístico)
   ↓
Risk Filter
   ↓
Signal Output
   ↓
LLM (apenas explicação)
```

---

# 🧱 Componentes do Sistema

---

## 1. Structure Engine

### Objetivo:

Interpretar o mercado como sequência de estrutura.

### Features:

* Swing High / Swing Low
* HH / HL / LH / LL
* BOS (Break of Structure)
* CHoCH (Change of Character)
* Tendência atual
* Tendência HTF

### Output:

```json
{
  "trend": "bullish",
  "last_bos": "bullish",
  "last_choch": null,
  "structure_strength": 0.82
}
```

---

## 2. Liquidity Engine

### Objetivo:

Identificar onde o mercado “quer ir”.

### Features:

* Equal highs / lows
* Liquidity pools
* Sweep (stop hunt)
* Rejeição pós-sweep

### Output:

```json
{
  "sweep": "buy_side",
  "strength": 0.85,
  "liquidity_target": 1.0865
}
```

---

## 3. Session Engine

### Objetivo:

Filtrar quando operar.

### Sessões:

* Asia
* London Open
* London Mid
* New York Open
* New York Mid
* Dead Zone

### Features:

* Killzone detection
* Tempo desde abertura
* High/Low da sessão

### Output:

```json
{
  "session": "london_open",
  "killzone": true,
  "score": 0.78
}
```

---

## 4. Displacement Engine

### Objetivo:

Detectar intenção real do mercado.

### Features:

* Candle expansion
* Body dominance
* ATR spike relativo
* Sequência impulsiva

### Output:

```json
{
  "direction": "bearish",
  "strength": 0.87
}
```

---

## 5. Zone Engine

### Objetivo:

Definir regiões de entrada.

### Features:

* Order Blocks (simples)
* Fair Value Gap (FVG)
* Premium / Discount
* Reteste de zona

### Output:

```json
{
  "entry_zone": [1.0850, 1.0855],
  "zone_quality": 0.74
}
```

---

## 6. Setup Engine

### Objetivo:

Transformar contexto em setup operável.

### Setups suportados:

* Sweep + Rejection
* Sweep + CHoCH + Retest
* BOS continuation
* Displacement retest
* Session breakout
* Range mean reversion

### Output:

```json
{
  "type": "sweep_choch_retest",
  "direction": "sell",
  "valid": true
}
```

---

## 7. Scoring Engine (CORE DA 2.1)

### Objetivo:

Gerar probabilidade real de sucesso.

---

## Fórmula base:

```python
final_score = (
    structure_score * 0.25 +
    liquidity_score * 0.25 +
    displacement_score * 0.20 +
    session_score * 0.15 +
    zone_score * 0.10 +
    risk_score * 0.05
)
```

---

## Penalidades:

```python
if dead_zone:
    final_score *= 0.75

if against_trend:
    final_score *= 0.70

if mid_range_entry:
    final_score *= 0.80
```

---

## Thresholds:

| Nível     | Score       |
| --------- | ----------- |
| Ignorar   | < 0.65      |
| Candidato | 0.65 – 0.75 |
| Bom       | 0.75 – 0.82 |
| Forte     | > 0.82      |

---

# 📊 Output Final

```json
{
  "symbol": "EURUSD",
  "timeframe": "M15",
  "setup": "sweep_choch_retest",
  "direction": "buy",
  "score": 0.81,
  "confidence": "high",
  "entry_zone": [1.0845, 1.0848],
  "tp": 1.0862,
  "sl": 1.0839
}
```

---

# ⚙️ Requisitos Técnicos

## Backend

* Python 3.11+
* FastAPI
* Peewee / PostgreSQL
* MetaTrader5 API

## Frontend

* React + Vite + Tailwind
* Recharts

## Integrações

* WAHA (WhatsApp)
* OpenRouter / NVIDIA (LLM opcional)

---

# 🧠 Papel do LLM

## Permitido:

* Explicar sinais
* Gerar relatórios
* Interface conversacional

## Proibido:

* Decidir trade
* Gerar direção
* Substituir scoring

---

# 💾 Banco de Dados (Extensão)

Adicionar colunas:

* structure_state
* sweep_type
* session_name
* displacement_strength
* setup_type
* structure_score
* liquidity_score
* final_score

---

# 🧪 Backtesting

## Métricas obrigatórias:

* Win rate por setup
* Win rate por sessão
* Score vs resultado
* Drawdown
* Profit factor

---

# 🧭 Roadmap

## Fase 1 (Core)

* Structure
* Liquidity
* Session
* Setup
* Scoring

## Fase 2

* Zones
* Displacement refinado
* Dashboard upgrade

## Fase 3

* Estatística avançada
* Ajuste por ativo
* Otimização automática

---

# ⚠️ Riscos

* Overfitting se exagerar filtros
* Complexidade excessiva
* Latência se não otimizar pipeline

---

# 🔥 Diferencial da 2.1

A 2.1 deixa de ser:

❌ “bot de indicador com IA”

E vira:

✅ **motor de leitura de mercado estruturado com scoring quantitativo**

---

# 🧠 Conclusão

Você não está mais construindo um bot.

👉 Você está construindo um **framework de análise institucional automatizado**


Perfeito. Agora a gente sai do “conceito bonito” e entra no que realmente gera edge:

> **regras determinísticas + replicáveis + testáveis**

Isso aqui é o **CORE matemático da 2.1**. Se isso estiver sólido, o resto do sistema funciona.

---

# 🧠 Premissas base (importantíssimo)

Antes das fórmulas:

* Dados: OHLC (candle)
* Timeframe base: configurável (ex: M15)
* Tudo precisa ser:

  * determinístico
  * sem ambiguidade
  * reproduzível em backtest

---

# 📐 1. Definição de Swing (base de tudo)

## Método: Fractal simétrico

### Parâmetro:

```python
SWING_WINDOW = 3  # pode ser 2–5
```

---

## 📌 Swing High

Um candle `i` é swing high se:

```text
High[i] > High[i-1], High[i-2], ..., High[i-N]
AND
High[i] > High[i+1], High[i+2], ..., High[i+N]
```

---

## 📌 Swing Low

```text
Low[i] < Low[i-1], Low[i-2], ..., Low[i-N]
AND
Low[i] < Low[i+1], Low[i+2], ..., Low[i+N]
```

---

## 🧠 Observação crítica

* Isso gera estrutura **limpa**
* Evita ruído
* Funciona bem para M15+

---

# 📐 2. Estrutura de Mercado (HH, HL, LH, LL)

Depois de detectar swings:

---

## 📌 Regras

### Tendência de alta:

```text
HH = último swing high > swing high anterior
HL = último swing low > swing low anterior
```

### Tendência de baixa:

```text
LH = último swing high < anterior
LL = último swing low < anterior
```

---

## 📊 Classificação

```python
if HH and HL:
    trend = "bullish"

elif LH and LL:
    trend = "bearish"

else:
    trend = "range"
```

---

# 📐 3. Break of Structure (BOS)

## 📌 BOS Bullish

```text
Close[i] > último swing high válido
AND
Close[i] fecha pelo menos X% acima do nível
```

### Parâmetro:

```python
BOS_THRESHOLD = 0.001  # 0.1% do preço (ajustável)
```

---

## 📌 BOS Bearish

```text
Close[i] < último swing low válido
```

---

## 🧠 Filtro de qualidade

* candle de rompimento deve ter:

  * body_ratio > 0.6
  * range > média dos últimos N candles

---

# 📐 4. CHoCH (Change of Character)

👉 mudança de tendência

---

## 📌 CHoCH Bullish

```text
Mercado estava bearish (LH/LL)
AND
Close rompe acima do último LH
```

---

## 📌 CHoCH Bearish

```text
Mercado estava bullish
AND
Close rompe abaixo do último HL
```

---

## 🧠 Regra importante

👉 CHoCH sempre vem **antes** de mudança de tendência confirmada

---

# 📐 5. Equal Highs / Equal Lows

## Parâmetro:

```python
EQUAL_TOLERANCE = 0.0003  # depende do ativo
```

---

## 📌 Equal Highs

```text
|High[i] - High[j]| <= tolerance
```

---

## 📌 Equal Lows

```text
|Low[i] - Low[j]| <= tolerance
```

---

## 🧠 Validação

* distância mínima entre pontos (evitar duplicação)
* pelo menos 2 toques

---

# 📐 6. Liquidity Sweep (Stop Hunt)

Esse é o coração do SMC.

---

## 📌 Sweep de compra (buy-side)

```text
Preço rompe acima de equal highs OU swing high
AND
Retorna para dentro do range em até N candles
AND
Fecha abaixo do nível rompido
```

---

## 📌 Sweep de venda (sell-side)

```text
Preço rompe abaixo de equal lows OU swing low
AND
Retorna para dentro
AND
Fecha acima do nível
```

---

## Parâmetros:

```python
SWEEP_LOOKAHEAD = 3
SWEEP_RETURN_THRESHOLD = 0.5  # fechamento de volta
```

---

## 🧠 Classificação de força

```python
sweep_strength = (
    rompimento_distancia +
    velocidade_retorno +
    rejeicao_candle
) / 3
```

---

# 📐 7. Displacement (Deslocamento)

Detecta intenção real.

---

## 📌 Regras

```text
Candle é displacement se:

range[i] > média_range * MULTIPLIER
AND
body_ratio > 0.7
```

---

## Parâmetros:

```python
DISPLACEMENT_MULTIPLIER = 1.5
BODY_RATIO_MIN = 0.7
```

---

## 📊 Body Ratio

```python
body_ratio = abs(close - open) / (high - low)
```

---

# 📐 8. Session Engine (formalizado)

## Timezone padrão:

```python
UTC
```

---

## Sessões:

```python
LONDON_OPEN = 07:00 – 10:00 UTC
NY_OPEN     = 12:00 – 15:00 UTC
```

---

## 📌 Killzone

```python
is_killzone = time in (London_Open OR NY_Open)
```

---

## Score de sessão:

```python
if killzone:
    session_score = 1.0
else:
    session_score = 0.5
```

---

# 📐 9. Setup Principal (formalizado)

## 📌 Setup: Sweep + CHoCH + Displacement

### Compra:

```text
1. Sweep de venda
2. CHoCH bullish
3. Candle de displacement bullish
4. Preço retorna (retest)
```

---

### Venda:

```text
1. Sweep de compra
2. CHoCH bearish
3. Displacement bearish
4. Retest
```

---

## 📌 Condição de validade

```python
valid_setup = (
    sweep_detected and
    choch_detected and
    displacement_detected
)
```

---

# 📐 10. Entry / SL / TP

## Entrada:

```text
Retest da zona do displacement
```

---

## Stop:

```text
Abaixo/acima do sweep
```

---

## Take Profit:

```text
Próxima liquidez (equal highs/lows ou swing)
```

---

# 📐 11. Score Normalizado

Todos os scores devem ser:

```python
0.0 → 1.0
```

---

## 📊 Score final:

```python
final_score = (
    structure_score * 0.25 +
    liquidity_score * 0.25 +
    displacement_score * 0.20 +
    session_score * 0.15 +
    zone_score * 0.10 +
    risk_score * 0.05
)
```

---

## Penalizações:

```python
if not killzone:
    final_score *= 0.8

if against_trend:
    final_score *= 0.7

if no_displacement:
    final_score *= 0.6
```

---

# 📊 Threshold final

```python
if final_score >= 0.80:
    signal = "STRONG"

elif final_score >= 0.72:
    signal = "VALID"

else:
    signal = "IGNORE"
```

---

# 🧠 Resultado

Agora você tem:

✔ Sistema determinístico
✔ Regras replicáveis
✔ Edge baseado em estrutura real
✔ Base para backtest confiável

---

# 🔥 Insight mais importante

👉 O edge não vem do “setup”

👉 Vem da combinação:

* estrutura + liquidez + timing

---