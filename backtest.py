import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone
from dailyagent.core.mt5_client import MT5Client
from dailyagent.features.processor import FeatureProcessor
from dailyagent.regime.classifier import RegimeClassifier
from dailyagent.signals.engine import SignalEngine
from dailyagent.scoring.engine import ScoringEngine
from dailyagent.core.logger import get_logger
import argparse

logger = get_logger("BacktestEngine")

class BacktestEngine:
    def __init__(self):
        self.mt5 = MT5Client()
        self.processor = FeatureProcessor(self.mt5)
        self.regime_classifier = RegimeClassifier()
        self.signal_engine = SignalEngine()
        self.scoring_engine = ScoringEngine()

    def run_backtest(self, symbols, start_date, end_date, timeframe=mt5.TIMEFRAME_H1):
        """Executa backtest em um período personalizado."""
        logger.info(f"📅 Iniciando Backtest de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}...")

        if not self.mt5.connect():
            return

        all_results = []

        for symbol in symbols:
            logger.info(f"--- Analisando {symbol} ---")

            # Pega dados do período + 300 candles anteriores para indicadores
            df_full = self.processor.generate_features(symbol, timeframe, count=500)
            if df_full is None: continue

            # Filtra candles no período especificado
            period_candles = df_full[(df_full['time'] >= start_date) & (df_full['time'] <= end_date)]

            for i in range(len(period_candles)):
                # Simula o estado do mercado naquele candle específico
                current_time = period_candles.iloc[i]['time']
                df_slice = df_full[df_full['time'] <= current_time]

                # 1. Regime e Sinais
                regime = self.regime_classifier.classify(df_slice)
                signals = self.signal_engine.generate_signals(df_slice, regime)

                if signals:
                    for sig in signals:
                        # 2. Validação imediata (Olha o futuro no próprio DF)
                        result = self._validate_future(df_full, df_slice.iloc[-1], sig)

                        all_results.append({
                            "Symbol": symbol,
                            "Time": current_time.strftime("%H:%M"),
                            "Date": current_time.strftime("%d/%m/%Y"),
                            "Type": sig['type'],
                            "Direction": sig['direction'],
                            "Status": result['status'],
                            "PnL": result['pnl']
                        })
                        logger.info(f"🚩 Sinal Detectado: {symbol} {sig['direction']} às {current_time.strftime('%H:%M')} | Resultado: {result['status']}")

        self.mt5.disconnect()
        self._print_report(all_results)

    def run_yesterday_backtest(self, symbols=["EURUSD", "GBPUSD", "BTCUSD", "US500"]):
        """Executa backtest do dia anterior (mantido para compatibilidade)."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, tzinfo=timezone.utc)
        yesterday_end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, tzinfo=timezone.utc)
        
        self.run_backtest(symbols, yesterday_start, yesterday_end)

    def _validate_future(self, df_full, signal_row, signal):
        entry_price = signal_row['close']
        atr = signal_row['atr']
        
        if signal['direction'] == "BUY":
            tp = entry_price + (atr * 2.0)
            sl = entry_price - (atr * 1.5)
        else:
            tp = entry_price - (atr * 2.0)
            sl = entry_price + (atr * 1.5)
            
        # Busca candles futuros
        future_df = df_full[df_full['time'] > signal_row['time']]
        
        for _, row in future_df.iterrows():
            if signal['direction'] == "BUY":
                if row['high'] >= tp: return {"status": "WIN", "pnl": tp - entry_price}
                if row['low'] <= sl: return {"status": "LOSS", "pnl": sl - entry_price}
            else:
                if row['low'] <= tp: return {"status": "WIN", "pnl": entry_price - tp}
                if row['high'] >= sl: return {"status": "LOSS", "pnl": entry_price - sl}
                
        return {"status": "PENDING", "pnl": 0}

    def _print_report(self, results):
        if not results:
            print("\n❌ Nenhum sinal encontrado para o período com a confluência atual.")
            return

        df = pd.DataFrame(results)
        print("\n" + "="*70)
        print("📊 RELATÓRIO DE BACKTEST")
        print("="*70)
        print(df.to_string(index=False))
        print("="*70)

        wins = len(df[df['Status'] == "WIN"])
        losses = len(df[df['Status'] == "LOSS"])
        pending = len(df[df['Status'] == "PENDING"])
        accuracy = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        
        print(f"Total de Sinais: {len(df)}")
        print(f"WIN: {wins} | LOSS: {losses} | PENDING: {pending}")
        print(f"Taxa de Acerto Técnica: {accuracy:.2f}% ({wins}W - {losses}L)")
        print("="*70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DailyAgent Backtest Engine")
    parser.add_argument("--symbols", type=str, nargs="+", default=["EURUSD", "GBPUSD", "BTCUSD", "US500"],
                        help="Lista de símbolos para backtest")
    parser.add_argument("--start-date", type=str, help="Data inicial (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="Data final (YYYY-MM-DD)")
    parser.add_argument("--yesterday", action="store_true", help="Executar backtest do dia anterior")
    parser.add_argument("--timeframe", type=str, default="H1", help="Timeframe (M1, M5, M15, H1, D1)")
    
    args = parser.parse_args()
    
    backtest = BacktestEngine()
    
    # Mapeamento de timeframe
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "D1": mt5.TIMEFRAME_D1
    }
    tf = tf_map.get(args.timeframe.upper(), mt5.TIMEFRAME_H1)
    
    if args.yesterday or (not args.start_date and not args.end_date):
        # Modo padrão: backtest de ontem
        backtest.run_yesterday_backtest(args.symbols)
    elif args.start_date and args.end_date:
        # Modo personalizado
        start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, tzinfo=timezone.utc)
        backtest.run_backtest(args.symbols, start, end, tf)
    else:
        print("Erro: Forneça --yesterday ou ambas --start-date e --end-date")
        print("Exemplo: python backtest.py --start-date 2026-04-10 --end-date 2026-04-14")
        exit(1)
