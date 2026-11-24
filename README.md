# DailyAgent 2.0

> Agente Autonomo de Trading com IA Multi-Agent

Sistema completo de analise de mercados financeiros que combina **analise tecnica quantitativa**, **inteligencia artificial (LLM)** e **analise fundamentalista** para gerar sinais de trading com alta confluencia. Suporta **Forex** (COMPRA/VENDA/AGUARDAR) e **Opcoes Binarias** (CALL/PUT/WAIT) com auditoria automatica.

---

## Funcionalidades

**Analise & Sinais**
- Analise Multi-Timeframe com confluencia entre timeframe operacional e superior
- Deteccao de Regime de mercado (tendencia, volatilidade, macro score)
- 3 tipos de sinais tecnicos: Breakout, Pullback e Reversal com scoring inteligente
- Analise fundamentalista com noticias em tempo real via Yahoo Finance

**Inteligencia Artificial**
- Quick Verdict (1 LLM) para monitoramento automatico rapido
- Debate entre 4 Agentes IA (sob demanda): Tendencia, Contrarian, Fundamentalista e Moderador
- Rate limiting com sliding window (30 RPM) e retry com backoff exponencial
- Suporte a provedores NVIDIA e OpenRouter

**Opcoes Binarias**
- Sinais CALL/PUT com expiracoes M1, M5 e M15
- Threshold de confianca configuravel (default 65%)
- Auditoria automatica ITM/OTM/TIE com calculo de win rate
- Deduplicacao de sinais (1 sinal aberto por ativo/expiracao)

**Comunicacao**
- Agente WhatsApp interativo com 7 comandos
- Notificacoes push via ntfy
- Rate limiting por chat_id no webhook

**Infraestrutura**
- Persistencia completa em PostgreSQL (Peewee ORM)
- Monitoramento continuo com loops paralelos (Forex 15min, Binarias 60s)
- API REST FastAPI com 8+ endpoints
- Dashboard React com graficos e metricas em tempo real
- Validacao automatica de sinais (TP/SL para Forex, expiracao para Binarias)

---

## Arquitetura

```
+-------------------------------------------------------------------+
|                         DailyAgent 2.0                            |
+-------------------------------------------------------------------+
|                                                                   |
|  MT5 Client --> Feature Processor --> Regime Classifier            |
|                  (RSI, ADX, ATR,      (trend, volatility,         |
|                   SMA, EMA, candles)   macro_score)               |
|                                                                   |
|                 Signal Engine --> Scoring Engine (MTF)             |
|                  (Breakout,       (local + parent TF              |
|                   Pullback,        confluencia)                   |
|                   Reversal)                                       |
|                                                                   |
|  Fundamental Analyzer (Yahoo Finance News)                        |
|                                                                   |
|  +-------------------------------------------------------------+ |
|  |              Estrategias LLM                                 | |
|  |                                                              | |
|  |  Quick Verdict (1 LLM)          Debate 4 Agentes            | |
|  |  - Automatico a cada ciclo      - Sob demanda /analisar     | |
|  |  - Forex: COMPRA/VENDA          - Trend Analyst             | |
|  |  - Binary: CALL/PUT             - Contrarian Analyst        | |
|  |  - ~10s por ativo               - Fundamental Analyst       | |
|  |                                  - Chief Risk Officer        | |
|  |                                  - ~60s por ativo            | |
|  +-------------------------------------------------------------+ |
|                                                                   |
|  Validator         Notifications        Dashboard                 |
|  - Forex: TP/SL    - WhatsApp (WAHA)    - React + Tailwind       |
|  - Binary: ITM/OTM  - Push (ntfy)        - Graficos Recharts     |
|  - Auto-audit       - Rate limited        - Dark terminal theme   |
|                                                                   |
|  Persistence (PostgreSQL) --> API FastAPI --> Dashboard React      |
+-------------------------------------------------------------------+
```

---

## Estrutura do Projeto

```
dailyagent/
|-- main.py                     # CLI principal
|-- server.py                   # Servidor unificado (API + Monitor)
|-- backtest.py                 # Engine de backtest
|-- config.json                 # Configuracoes (LLM, notificacoes, binary, monitoring)
|-- requirements.txt            # Dependencias Python
|-- .env                        # Variaveis de ambiente (secrets)
|
|-- dailyagent/
|   |-- core/
|   |   |-- agent.py            # DailyAgent (quick scan, full analysis, binary)
|   |   |-- monitor.py          # MonitorEngine (loops Forex + Binary)
|   |   |-- mt5_client.py       # Conexao com MetaTrader 5
|   |   |-- config.py           # Settings, LLMConfig, BinaryConfig
|   |   |-- validator.py        # Validacao Forex (TP/SL) + Binary (ITM/OTM)
|   |   +-- logger.py           # Logger com Loguru
|   |
|   |-- features/
|   |   |-- processor.py        # Feature Pipeline
|   |   |-- indicators.py       # Indicadores (RSI, ADX, ATR, SMA, EMA, candles)
|   |   +-- fundamentals.py     # Analise fundamentalista (Yahoo Finance)
|   |
|   |-- regime/
|   |   +-- classifier.py       # Classificacao de regime de mercado
|   |
|   |-- signals/
|   |   +-- engine.py           # Geracao de sinais (Breakout, Pullback, Reversal)
|   |
|   |-- scoring/
|   |   +-- engine.py           # Scoring com confluencia MTF
|   |
|   |-- llm/
|   |   |-- client.py           # Cliente LLM (NVIDIA/OpenRouter) + Rate Limiter
|   |   +-- debate.py           # Quick Verdict + Debate 4 Agentes
|   |
|   |-- notifications/
|   |   |-- ntfy.py             # Notificacoes push
|   |   |-- waha.py             # WhatsApp API (alertas Forex + Binary)
|   |   +-- whatsapp_agent.py   # Agente WhatsApp interativo (7 comandos)
|   |
|   |-- persistence/
|   |   +-- models.py           # Modelos Peewee (Run, Signal, BinarySignal, Report, ChatMessage)
|   |
|   +-- api/
|       +-- main.py             # API FastAPI + Dashboard static serving
|
|-- dashboard/                  # Dashboard React
|   |-- package.json
|   |-- vite.config.ts          # Proxy /api -> localhost:8000
|   |-- tailwind.config.ts      # Design tokens (profit, loss, warn)
|   |-- src/
|   |   |-- main.tsx
|   |   |-- App.tsx             # Routes: /, /forex, /binary, /stats
|   |   |-- index.css           # Dark trading terminal theme
|   |   |-- lib/
|   |   |   |-- api.ts          # API client
|   |   |   |-- types.ts        # TypeScript interfaces
|   |   |   +-- utils.ts        # cn() utility
|   |   |-- components/
|   |   |   |-- ui/             # Card, Badge, Button
|   |   |   +-- layout/         # Sidebar, RootLayout
|   |   +-- pages/
|   |       |-- overview.tsx    # KPIs, tabelas recentes
|   |       |-- forex.tsx       # Analises Forex + relatorios
|   |       |-- binary.tsx      # Sinais binarios + stats
|   |       +-- stats.tsx       # Graficos (pie, bar) + detalhamento
|   +-- dist/                   # Build de producao (servido pelo FastAPI)
|
|-- tests/                      # Testes unitarios
+-- logs/                       # Logs da aplicacao
```

---

## Camadas de Estrategia

O sistema opera em 7 camadas empilhadas, do dado bruto ao sinal validado:

### 1. Indicadores Tecnicos (`features/indicators.py`)

| Indicador | Config | Uso |
|-----------|--------|-----|
| RSI | 14 periodos | Sobrecompra (>70) / Sobrevenda (<30) |
| ADX | 14 periodos | Forca da tendencia (>25 = forte) |
| ATR | 20 periodos | Volatilidade + calculo TP/SL |
| SMA | 20, 50, 200 | Classificacao de tendencia |
| EMA | 9, 21 | Suporte/resistencia para pullbacks |
| Volatilidade Realizada | 20 periodos | Classificacao vol regime |
| Pinbar | body <30%, shadow >60% | Padrao reversao bull/bear |
| Engulfing | 2 candles | Padrao reversao bull/bear |

### 2. Classificacao de Regime (`regime/classifier.py`)

**Tendencia** (alinhamento SMA 20/50/200):
- `strong_bullish` (+60) / `bullish` (+30) / `neutral` (0) / `bearish` (-30) / `strong_bearish` (-60)

**Volatilidade** (vol atual vs media 50p):
- `high` (>1.5x, penaliza 0.8x) / `expanding` (>1.1x) / `normal` / `low` (<0.7x)

**Macro Score** (-100 a +100):
```
score = trend_score + RSI_penalty + volatility_multiplier
```

### 3. Deteccao de Sinais (`signals/engine.py`)

| Sinal | Forca | Condicao |
|-------|-------|----------|
| BREAKOUT | 0.85 | Preco > max 20p OU < min 20p **E** ADX > 25 |
| PULLBACK | 0.80 | Tendencia ativa + preco toca EMA21 + padrao candle |
| REVERSAL | 0.75 | RSI extremo (<30 ou >70) + padrao candle |

### 4. Scoring Multi-Timeframe (`scoring/engine.py`)

```
1. Ajuste local:  score = strength x (1 + macro_score / 500)
2. Confluencia MTF:
   - Sinal alinhado com parent TF = +20% bonus
   - Sinal contra parent TF = -30% penalidade
3. Ranking por final_score (descendente)
```

### 5. Estrategias LLM (`llm/debate.py`)

**Quick Verdict** (1 LLM - automatico, ~10s):
- Usado no monitoramento continuo
- Forex: COMPRA / VENDA / AGUARDAR + confianca %
- Binary: CALL / PUT / WAIT + confianca %

**Debate 4 Agentes** (sob demanda via `/analisar`, ~60s):

| Agente | Modelo | Foco |
|--------|--------|------|
| Trend Analyst | `trend_model` | Momentum, continuacao, forca |
| Contrarian | `contrarian_model` | Exaustao, reversao, riscos |
| Fundamentalista | `fundamental_model` | Noticias, sentimento, macro |
| Chief Risk Officer | `moderator_model` | Sintese final, veredito |

### 6. Gestao de Risco

```
TP = entry +/- (ATR x 2.0)    # Take Profit: 2x ATR
SL = entry -/+ (ATR x 1.5)    # Stop Loss: 1.5x ATR
Ratio risco/retorno: 1.33:1
```

Binary: threshold minimo de 65% confianca para emitir sinal.

### 7. Validacao e Auditoria (`core/validator.py`)

**Forex** (lookback 3 dias, max 100 candles):
- TP atingido -> WIN | SL atingido -> LOSS | Timeout -> EXPIRED

**Binary** (expiracao M1/M5/M15):
- CALL + preco subiu -> ITM | CALL + preco desceu -> OTM | Igual -> TIE
- PUT + preco desceu -> ITM | PUT + preco subiu -> OTM | Igual -> TIE

---

## Instalacao

### Pre-requisitos

- **Python 3.10+**
- **Node.js 18+** (para o dashboard)
- **MetaTrader 5** instalado e logado (Windows)
- **PostgreSQL**
- **API Key NVIDIA ou OpenRouter** (para LLM)

### Passo a passo

1. **Crie um ambiente virtual**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

2. **Instale as dependencias Python**
```bash
pip install -r requirements.txt
```

3. **Configure as variaveis de ambiente**
```bash
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
copy config.example.json config.json  # Windows
cp config.example.json config.json   # Linux/Mac
```

Edite o `.env`:
```env
OPENROUTER_API_KEY=sk-or-v1-sua_chave_aqui
NVIDIA_API_KEY=nvapi-sua_chave_aqui
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dailyagent
DB_USER=postgres
DB_PASSWORD=senha_do_banco
```

4. **Configure o `config.json`** (crie uma cópia local de `config.example.json`; o arquivo real fica fora do Git)
```json
{
  "llm": {
    "provider": "nvidia",
    "max_rpm": 30,
    "max_retries": 3,
    "nvidia_models": {
      "trend_model": "z-ai/glm4.7",
      "contrarian_model": "nvidia/nemotron-content-safety-reasoning-4b",
      "fundamental_model": "deepseek-ai/deepseek-v3.2",
      "moderator_model": "mistralai/devstral-2-123b-instruct-2512",
      "whatsapp_agent": "deepseek-ai/deepseek-v3.2"
    }
  },
  "notifications": {
    "ntfy_enabled": false,
    "waha_enabled": true
  },
  "monitoring": {
    "default_interval_minutes": 15,
    "assets": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "NAS100", "SPX500"]
  },
  "binary": {
    "enabled": true,
    "expirations": ["M1", "M5", "M15"],
    "default_expiration": "M5",
    "confidence_threshold": 65,
    "monitor_interval_seconds": 60,
    "assets": ["EURUSD", "GBPUSD", "USDJPY", "XRPUSD", "LTCUSD", "BTCUSD", "ETHUSD"]
  }
}
```

5. **Instale e compile o dashboard**
```bash
cd dashboard
npm install
npm run build
cd ..
```

---

## Uso

### Server Unificado (Recomendado)

**Iniciar API + Monitor + Dashboard:**
```bash
python server.py
```

**Apenas API:**
```bash
python server.py --api-only
```

**Apenas Monitor:**
```bash
python server.py --monitor-only --interval 10
```

**Porta personalizada:**
```bash
python server.py --port 8080
```

| Parametro | Descricao | Default |
|-----------|-----------|---------|
| `--api-only` | Iniciar apenas a API | - |
| `--monitor-only` | Iniciar apenas o Monitor | - |
| `--interval` | Intervalo do monitor (minutos) | 15 |
| `--port` | Porta da API | 8000 |
| `--host` | Host da API | 0.0.0.0 |

### CLI - Linha de Comando

```bash
# Analisar um ativo especifico
python main.py --symbol EURUSD --timeframe H1

# Iniciar a API REST
python main.py --api

# Monitorar multiplos ativos
python main.py --monitor --interval 15
```

---

## Dashboard

Dashboard web em React com tema dark de terminal de trading.

**Desenvolvimento:**
```bash
cd dashboard
npm run dev    # Porta 3000, proxy /api -> localhost:8000
```

**Producao:**
```bash
cd dashboard
npm run build  # Gera dist/ servido automaticamente pelo FastAPI
```

**Paginas:**

| Pagina | Rota | Conteudo |
|--------|------|----------|
| Visao Geral | `/` | KPIs (status API, runs, win rate, sinais abertos), tabelas recentes |
| Forex | `/forex` | Analise rapida sob demanda, tabela de runs com relatorios |
| Binarias | `/binary` | Stats cards, gerador de sinais, tabela com barra de confianca |
| Estatisticas | `/stats` | Pie chart (ITM/OTM/TIE), bar chart por ativo, detalhamento |

**Stack:** React 18, TypeScript, Vite, Tailwind CSS, Recharts, Lucide Icons

---

## Agente WhatsApp

O sistema inclui um agente WhatsApp interativo via WAHA com os seguintes comandos:

| Comando | Descricao |
|---------|-----------|
| `/ajuda` | Lista todos os comandos disponiveis |
| `/status` | Status do sistema, conexao MT5 e ultimo scan |
| `/detalhar EURUSD` | Scan rapido + resumo tecnico (1 LLM) |
| `/analisar EURUSD` | Debate completo com 4 agentes IA |
| `/binary EURUSD M5` | Gera sinal binario CALL/PUT |
| `/binary todos` | Scan de todos os ativos binarios |
| `/stats` | Estatisticas de win rate binario |

**Funcionalidades do agente:**
- Rate limiting por chat_id (10 msgs/min configuravel)
- Historico de conversa com contexto
- Autenticacao por webhook token
- Correcao automatica de formato LID do WAHA

---

## API REST

Acesse a documentacao Swagger: `http://localhost:8000/docs`

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| `GET` | `/health` | Status da API e conexao MT5 |
| `POST` | `/run-agent?symbol=EURUSD&timeframe=H1` | Quick scan (1 LLM) |
| `POST` | `/run-analysis?symbol=EURUSD&timeframe=H1` | Debate completo (4 LLMs) |
| `POST` | `/run-binary?symbol=EURUSD&expiration=M5` | Gerar sinal binario |
| `GET` | `/recent-runs?limit=10` | Ultimas execucoes |
| `GET` | `/report/{run_id}` | Relatorio completo de uma execucao |
| `GET` | `/binary/stats?days=30&symbol=EURUSD` | Estatisticas binarias |
| `GET` | `/binary/recent?limit=10` | Ultimos sinais binarios |
| `POST` | `/waha/webhook` | Webhook WhatsApp (WAHA) |

**Exemplo:**
```bash
# Quick scan
curl -X POST "http://localhost:8000/run-agent?symbol=GBPUSD&timeframe=H1"

# Sinal binario
curl -X POST "http://localhost:8000/run-binary?symbol=EURUSD&expiration=M5"

# Estatisticas binarias
curl "http://localhost:8000/binary/stats?days=7"
```

---

## Banco de Dados

PostgreSQL com Peewee ORM. Tabelas criadas automaticamente no startup.

| Tabela | Descricao |
|--------|-----------|
| `run` | Execucoes do agente (symbol, timeframe, regime, macro_score, rsi) |
| `signal` | Sinais Forex com TP/SL (status: PENDING/WIN/LOSS/EXPIRED, pnl_points) |
| `binarysignal` | Sinais binarios (CALL/PUT, confidence, status: OPEN/ITM/OTM/TIE) |
| `report` | Relatorios completos gerados pelo debate engine |
| `chatmessage` | Historico de conversas do agente WhatsApp |

**Criar banco:**
```sql
CREATE DATABASE dailyagent;
```

Migracoes de colunas sao aplicadas automaticamente via `_migrate_missing_columns()`.

---

## Configuracao de Notificacoes

### WhatsApp (WAHA)

```json
{
  "waha": {
    "api_url": "https://sua-instancia-waha.com",
    "session": "default",
    "recipient_phone": "5511999999999",
    "webhook_token": "token_secreto_opcional",
    "api_key": "sua_api_key"
  },
  "whatsapp_config": {
    "rate_limit_max_requests": 10,
    "rate_limit_window_seconds": 60,
    "analysis_timeout_seconds": 180,
    "llm_timeout_seconds": 60
  }
}
```

### ntfy (Push Notifications)

```json
{
  "ntfy": {
    "topic": "dailyagent-report",
    "url": "https://ntfy.sh/",
    "user": "",
    "password": ""
  }
}
```

---

## Ativos Monitorados

**Forex (monitoramento a cada 15 min):**
EURUSD, GBPUSD, USDJPY, XAUUSD, NAS100, SPX500

**Opcoes Binarias (monitoramento a cada 60s):**
EURUSD, GBPUSD, USDJPY, XRPUSD, LTCUSD, BTCUSD, ETHUSD, BNBUSD, SOLUSD

Os ativos sao configuraveis via `config.json` nas secoes `monitoring.assets` e `binary.assets`.

---

## Backtest

```bash
python backtest.py
```

```python
from backtest import BacktestEngine

backtest = BacktestEngine()
backtest.run_yesterday_backtest(symbols=["EURUSD", "GBPUSD", "BTCUSD"])
```

---

## Logs

Logs salvos em `logs/dailyagent.log` com rotacao de 10MB e retencao de 10 dias.

```bash
# Linux/Mac
tail -f logs/dailyagent.log

# Windows PowerShell
Get-Content logs/dailyagent.log -Wait
```

---

## Thresholds e Parametros

| Parametro | Valor | Local |
|-----------|-------|-------|
| ADX breakout | > 25 | `signals/engine.py` |
| RSI sobrecompra | > 70 | `signals/engine.py` |
| RSI sobrevenda | < 30 | `signals/engine.py` |
| Pinbar body ratio | < 30% | `features/indicators.py` |
| Pinbar shadow ratio | > 60% | `features/indicators.py` |
| TP multiplier (ATR) | 2.0x | `core/agent.py` |
| SL multiplier (ATR) | 1.5x | `core/agent.py` |
| Binary confidence min | 65% | `config.json` |
| LLM rate limit | 30 RPM | `config.json` |
| Forex validation lookback | 3 dias | `core/validator.py` |
| Forex signal max candles | 100 | `core/validator.py` |

---

## Avisos Importantes

1. **Este projeto e para fins educacionais.** Nao constitui recomendacao de investimento.
2. **Trading envolve riscos.** Nunca invista mais do que pode perder.
3. **Teste exaustivamente em conta demo** antes de usar em conta real.
4. **MetaTrader 5 requer Windows** (ou Wine no Linux).

---

## Licenca

MIT License

---

**DailyAgent 2.0** - Analise quantitativa + IA multi-agente para trading
