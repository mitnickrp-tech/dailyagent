from .mt5_client import MT5Client
from ..features.processor import FeatureProcessor
from ..features.fundamentals import FundamentalAnalyzer
from ..regime.classifier import RegimeClassifier
from ..signals.engine import SignalEngine
from ..scoring.engine import ScoringEngine
from ..llm.debate import DebateEngine
from ..notifications.ntfy import NotificationAgent
from ..notifications.waha import WahaAgent
from ..persistence.models import Run, Signal, Report, BinarySignal, db, init_db
from .logger import get_logger
from .config import settings
import MetaTrader5 as mt5
import json
import re
from datetime import datetime, timezone, timedelta

logger = get_logger("DailyAgent")

class DailyAgent:
    def __init__(self):
        self.mt5 = MT5Client()
        self.features = FeatureProcessor(self.mt5)
        self.fundamentals = FundamentalAnalyzer()
        self.regime = RegimeClassifier()
        self.signals = SignalEngine()
        self.scoring = ScoringEngine()
        self.debate_engine = DebateEngine()
        self.notifier = NotificationAgent()
        self.waha = WahaAgent()
        
        try:
            init_db()
        except Exception as e:
            logger.warning(f"Erro ao inicializar DB (verifique a configuração PostgreSQL): {e}")

    def run_for_symbol(self, symbol: str, timeframe: int = mt5.TIMEFRAME_H1):
        """Pipeline automatico: quantitativo + 1 LLM resumida (quick verdict)."""
        logger.info(f"Iniciando execucao para {symbol} (Quick Verdict Mode)...")
        
        if not self.mt5.connect():
            return {"error": "Falha na conexao MT5"}
            
        try:
            # --- 1. Analise Fundamentalista ---
            news_context = self.fundamentals.get_summary_context(symbol)
            
            # --- 2. Timeframe Superior ---
            parent_tf = self._get_parent_timeframe(timeframe)
            df_parent = self.features.generate_features(symbol, parent_tf, count=300)
            regime_parent = self.regime.classify(df_parent) if df_parent is not None else None
            
            # --- 3. Pipeline Quantitativo ---
            df = self.features.generate_features(symbol, timeframe)
            if df is None:
                return {"error": f"Dados insuficientes para {symbol}"}
                
            regime_data = self.regime.classify(df)
            raw_signals = self.signals.generate_signals(df, regime_data)
            scored_signals = self.scoring.score_signals(raw_signals, regime_data, regime_parent)
            
            # --- 4. Quick Verdict (1 LLM ao inves de 4) ---
            verdict_text = self.debate_engine.get_quick_verdict(
                symbol, regime_data, scored_signals, regime_parent, mode="forex"
            )
            
            # --- 5. Persistencia ---
            self._save_results(symbol, timeframe, regime_data, scored_signals, verdict_text, df)
            
            # --- 6. Notificacoes (somente vereditos acionaveis) ---
            decision = self._parse_verdict(verdict_text)

            if decision in ("COMPRA", "VENDA"):
                logger.info(f"Veredito acionavel para {symbol}: {decision} - enviando alerta")
                if settings.notifications.ntfy_enabled:
                    self.notifier.send_report_summary(symbol, regime_data, scored_signals)
                if settings.notifications.waha_enabled:
                    self.waha.send_report(symbol, verdict_text)
            else:
                logger.info(f"Veredito {decision} para {symbol} - alerta suprimido")
            
            return {
                "symbol": symbol,
                "regime": regime_data,
                "regime_parent": regime_parent,
                "signals": scored_signals,
                "verdict": verdict_text
            }
            
        finally:
            self.mt5.disconnect()

    def run_full_analysis(self, symbol: str, timeframe: int = mt5.TIMEFRAME_H1):
        """Debate completo com 4 agentes LLM (sob demanda via /analisar)."""
        logger.info(f"Iniciando analise completa para {symbol} (Debate 4 Agentes)...")
        
        if not self.mt5.connect():
            return {"error": "Falha na conexao MT5"}
            
        try:
            news_context = self.fundamentals.get_summary_context(symbol)
            parent_tf = self._get_parent_timeframe(timeframe)
            
            df_parent = self.features.generate_features(symbol, parent_tf, count=300)
            regime_parent = self.regime.classify(df_parent) if df_parent is not None else None
            
            df = self.features.generate_features(symbol, timeframe)
            if df is None:
                return {"error": f"Dados insuficientes para {symbol}"}
                
            regime_data = self.regime.classify(df)
            raw_signals = self.signals.generate_signals(df, regime_data)
            scored_signals = self.scoring.score_signals(raw_signals, regime_data, regime_parent)
            
            # Debate completo com 4 agentes
            debate_results = self.debate_engine.get_consensus(
                symbol, regime_data, scored_signals, regime_parent, news_context
            )
            full_report = self._format_debate_report(symbol, debate_results, timeframe, parent_tf)
            
            self._save_results(symbol, timeframe, regime_data, scored_signals, full_report, df)
            
            return {
                "symbol": symbol,
                "regime": regime_data,
                "regime_parent": regime_parent,
                "signals": scored_signals,
                "report": full_report,
                "verdict": debate_results['final_verdict']
            }
            
        finally:
            self.mt5.disconnect()

    def run_for_symbol_binary(self, symbol: str, expiration: str = "M5"):
        """Pipeline binario: quantitativo + quick verdict para CALL/PUT."""
        logger.info(f"Iniciando analise binaria para {symbol} ({expiration})...")

        # Deduplicacao: pula se ja existe sinal OPEN para este symbol
        try:
            open_signal = (
                BinarySignal.select()
                .join(Run)
                .where(
                    BinarySignal.status == "OPEN",
                    Run.symbol == symbol,
                    BinarySignal.expiration == expiration
                )
                .first()
            )
            if open_signal:
                logger.info(f"Sinal binario OPEN ja existe para {symbol} {expiration}, pulando.")
                return {"symbol": symbol, "status": "skipped", "reason": "open_signal_exists"}
        except Exception:
            pass  # DB pode nao estar disponivel

        # Mapeamento de expiracao para timeframe MT5
        exp_tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
        }
        timeframe = exp_tf_map.get(expiration, mt5.TIMEFRAME_M5)

        if not self.mt5.connect():
            return {"error": "Falha na conexao MT5"}

        try:
            parent_tf = self._get_parent_timeframe(timeframe)
            df_parent = self.features.generate_features(symbol, parent_tf, count=300)
            regime_parent = self.regime.classify(df_parent) if df_parent is not None else None

            df = self.features.generate_features(symbol, timeframe)
            if df is None:
                return {"error": f"Dados insuficientes para {symbol}"}

            regime_data = self.regime.classify(df)
            raw_signals = self.signals.generate_signals(df, regime_data)
            scored_signals = self.scoring.score_signals(raw_signals, regime_data, regime_parent)

            # Quick verdict no modo binario
            verdict_text = self.debate_engine.get_quick_verdict(
                symbol, regime_data, scored_signals, regime_parent,
                mode="binary", expiration=expiration
            )

            # Parse do veredito binario
            parsed = self._parse_binary_verdict(verdict_text)
            direction = parsed["direction"]
            confidence = parsed["confidence"]

            # Filtra por threshold de confianca
            threshold = settings.binary.confidence_threshold
            if direction == "WAIT" or confidence < threshold:
                logger.info(
                    f"Binario {symbol}: {direction} conf={confidence}% "
                    f"(threshold={threshold}%) - sinal suprimido"
                )
                return {
                    "symbol": symbol,
                    "direction": direction,
                    "confidence": confidence,
                    "status": "below_threshold"
                }

            # Preco de entrada
            last_row = df.iloc[-1]
            entry_price = float(last_row['close'])

            # Calcula expires_at
            exp_minutes = {"M1": 1, "M5": 5, "M15": 15}
            minutes = exp_minutes.get(expiration, 5)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=minutes)

            # Salva no banco
            self._save_binary_result(
                symbol, timeframe, regime_data, scored_signals,
                direction, expiration, confidence, entry_price,
                expires_at, verdict_text, df
            )

            # Notifica via WhatsApp
            if settings.notifications.waha_enabled:
                self.waha.send_binary_alert(
                    symbol, direction, confidence, expiration, entry_price
                )

            logger.info(
                f"Sinal binario emitido: {symbol} {direction} {expiration} "
                f"conf={confidence}% entrada={entry_price}"
            )

            return {
                "symbol": symbol,
                "direction": direction,
                "expiration": expiration,
                "confidence": confidence,
                "entry_price": entry_price,
                "expires_at": expires_at.isoformat(),
                "verdict": verdict_text
            }

        finally:
            self.mt5.disconnect()

    @staticmethod
    def _parse_verdict(verdict_text: str) -> str:
        """Extrai decisao do veredito (COMPRA, VENDA ou AGUARDAR).

        Usa regex para encontrar a decisao em contextos estruturados como
        'Decisao: COMPRA', 'Veredito: AGUARDAR', etc. Busca primeiro por
        padroes estruturados, depois faz fallback para analise das primeiras
        linhas do texto.
        """
        text = verdict_text.upper()

        # 1. Busca padroes estruturados (ex: "DECISAO: COMPRA", "VEREDITO: AGUARDAR")
        structured = re.search(
            r'(?:DECIS[AÃ]O|VEREDITO|RECOMENDA[CÇ][AÃ]O)\s*[:]\s*(AGUARDAR|COMPRA[R]?|VENDA|VENDER)',
            text
        )
        if structured:
            keyword = structured.group(1)
            if keyword.startswith("COMPRA"):
                return "COMPRA"
            if keyword in ("VENDA", "VENDER"):
                return "VENDA"
            return "AGUARDAR"

        # 2. Analisa as 3 primeiras linhas (onde o LLM tipicamente coloca a decisao)
        first_lines = "\n".join(text.strip().splitlines()[:3])
        if "AGUARDAR" in first_lines:
            return "AGUARDAR"
        if "COMPRA" in first_lines and "VENDA" not in first_lines:
            return "COMPRA"
        if "VENDA" in first_lines or "VENDER" in first_lines:
            return "VENDA"
        if "COMPRA" in first_lines:
            return "COMPRA"

        # 3. Fallback: busca no texto completo com prioridade para AGUARDAR
        if "AGUARDAR" in text:
            return "AGUARDAR"
        if "COMPRA" in text:
            return "COMPRA"
        if "VENDA" in text:
            return "VENDA"

        return "AGUARDAR"

    def _get_parent_timeframe(self, tf):
        """Mapeamento lógico de timeframes superiores."""
        mapping = {
            mt5.TIMEFRAME_M1: mt5.TIMEFRAME_M15,
            mt5.TIMEFRAME_M5: mt5.TIMEFRAME_H1,
            mt5.TIMEFRAME_M15: mt5.TIMEFRAME_H4,
            mt5.TIMEFRAME_H1: mt5.TIMEFRAME_D1,
            mt5.TIMEFRAME_H4: mt5.TIMEFRAME_D1,
            mt5.TIMEFRAME_D1: mt5.TIMEFRAME_W1
        }
        return mapping.get(tf, mt5.TIMEFRAME_D1)

    def _format_debate_report(self, symbol, debate, tf, parent_tf):
        return f"""
# 📊 RELATÓRIO DE CONSENSO ELITE: {symbol}
*Timeframe: {tf} | Referência Superior: {parent_tf}*

## 📈 ANÁLISE DE TENDÊNCIA
{debate['trend_analysis']}

## 📉 ANÁLISE CONTRARIAN
{debate['contrarian_analysis']}

## 📰 ANÁLISE FUNDAMENTALISTA
{debate['fundamental_analysis']}

## ⚖️ VEREDITO FINAL (CHEFE DE MESA)
{debate['final_verdict']}
"""

    def _save_results(self, symbol, timeframe, regime, signals, report_content, df):
        try:
            last_row = df.iloc[-1]
            entry_price = float(last_row['close'])
            atr = float(last_row.get('atr', 0))
            
            with db.atomic():
                run = Run.create(
                    symbol=symbol,
                    timeframe=timeframe,
                    trend=regime['trend'],
                    volatility=regime['volatility'],
                    macro_score=regime['macro_score'],
                    rsi=regime['rsi']
                )
                
                for s in signals:
                    tp_price = 0.0
                    sl_price = 0.0
                    
                    if s['direction'] == "BUY":
                        tp_price = entry_price + (atr * 2.0)
                        sl_price = entry_price - (atr * 1.5)
                    else:
                        tp_price = entry_price - (atr * 2.0)
                        sl_price = entry_price + (atr * 1.5)
                        
                    Signal.create(
                        run=run,
                        type=s['type'],
                        direction=s['direction'],
                        strength=s['strength'],
                        final_score=s['final_score'],
                        entry_price=entry_price,
                        tp_price=tp_price,
                        sl_price=sl_price,
                        status="PENDING"
                    )
                    
                Report.create(run=run, content=report_content)
                logger.info(f"Dados salvos no banco para {symbol} (Preco: {entry_price})")
        except Exception as e:
            logger.error(f"Erro ao salvar no banco de dados: {e}")

    @staticmethod
    def _parse_binary_verdict(verdict_text: str) -> dict:
        """Extrai direcao (CALL/PUT/WAIT) e confianca do veredito binario."""
        text = verdict_text.upper()
        direction = "WAIT"
        confidence = 0

        # Tier 1: Regex estruturado
        dir_match = re.search(r'DECIS[AÃ]O\s*[:]\s*(CALL|PUT|WAIT)', text)
        if dir_match:
            direction = dir_match.group(1)

        conf_match = re.search(r'CONFIAN[CÇ]A\s*[:]\s*(\d+)\s*%', text)
        if conf_match:
            confidence = int(conf_match.group(1))

        # Tier 2: Primeiras 3 linhas
        if direction == "WAIT" and not dir_match:
            first_lines = "\n".join(text.strip().splitlines()[:3])
            if "CALL" in first_lines and "PUT" not in first_lines:
                direction = "CALL"
            elif "PUT" in first_lines and "CALL" not in first_lines:
                direction = "PUT"

        # Tier 3: Texto completo, WAIT prioritario
        if direction == "WAIT" and not dir_match:
            if "CALL" in text and "PUT" not in text:
                direction = "CALL"
            elif "PUT" in text and "CALL" not in text:
                direction = "PUT"

        # Fallback confianca
        if confidence == 0:
            pct_match = re.search(r'(\d{2,3})\s*%', text)
            if pct_match:
                confidence = min(int(pct_match.group(1)), 100)

        return {"direction": direction, "confidence": confidence}

    def _save_binary_result(self, symbol, timeframe, regime, signals,
                            direction, expiration, confidence, entry_price,
                            expires_at, verdict_text, df):
        """Salva sinal binario no banco de dados."""
        try:
            top_signal = signals[0] if signals else {}
            with db.atomic():
                run = Run.create(
                    symbol=symbol,
                    timeframe=timeframe,
                    trend=regime.get('trend', 'N/A'),
                    volatility=regime.get('volatility', 'N/A'),
                    macro_score=regime.get('macro_score', 0),
                    rsi=regime.get('rsi', 0)
                )
                BinarySignal.create(
                    run=run,
                    direction=direction,
                    expiration=expiration,
                    confidence=confidence,
                    entry_price=entry_price,
                    status="OPEN",
                    signal_type=top_signal.get('type', ''),
                    regime_trend=regime.get('trend', ''),
                    regime_volatility=regime.get('volatility', ''),
                    final_score=top_signal.get('final_score', 0),
                    expires_at=expires_at,
                    verdict_text=verdict_text
                )
                logger.info(f"BinarySignal salvo: {symbol} {direction} {expiration} conf={confidence}%")
        except Exception as e:
            logger.error(f"Erro ao salvar BinarySignal: {e}")

    # ==========================================
    # QUICK SCAN (Pipeline quantitativo sem LLM)
    # ==========================================

    def quick_scan(self, symbol: str, timeframe: int = mt5.TIMEFRAME_H1) -> dict:
        """Pipeline quantitativo rapido (sem LLM). ~5s por ativo."""
        try:
            news_context = self.fundamentals.get_summary_context(symbol)
            parent_tf = self._get_parent_timeframe(timeframe)

            df_parent = self.features.generate_features(symbol, parent_tf, count=300)
            regime_parent = self.regime.classify(df_parent) if df_parent is not None else None

            df = self.features.generate_features(symbol, timeframe)
            if df is None:
                return {"symbol": symbol, "error": "Dados insuficientes", "top_score": 0.0}

            regime_data = self.regime.classify(df)
            raw_signals = self.signals.generate_signals(df, regime_data)
            scored_signals = self.scoring.score_signals(raw_signals, regime_data, regime_parent)

            top_score = scored_signals[0]['final_score'] if scored_signals else 0.0

            return {
                "symbol": symbol,
                "regime": regime_data,
                "regime_parent": regime_parent,
                "signals": scored_signals,
                "top_score": top_score
            }
        except Exception as e:
            logger.error(f"Erro no quick_scan de {symbol}: {e}")
            return {"symbol": symbol, "error": str(e), "top_score": 0.0}

    def quick_scan_all(self, timeframe: int = mt5.TIMEFRAME_H1) -> list:
        """Scan rapido de todos os ativos monitorados. Retorna lista ordenada por score."""
        assets = settings.monitoring.assets
        if not assets:
            return []

        if not self.mt5.connect():
            return [{"symbol": s, "error": "Falha MT5", "top_score": 0.0} for s in assets]

        try:
            results = []
            for symbol in assets:
                result = self.quick_scan(symbol, timeframe)
                results.append(result)

            results.sort(key=lambda x: x.get("top_score", 0), reverse=True)
            return results
        finally:
            self.mt5.disconnect()
