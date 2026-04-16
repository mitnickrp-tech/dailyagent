import sys
import argparse
import time
from dailyagent.core.agent import DailyAgent
from dailyagent.core.monitor import MonitorEngine
from dailyagent.core.logger import get_logger
import MetaTrader5 as mt5

logger = get_logger("Main")

def main():
    parser = argparse.ArgumentParser(description="DailyAgent 2.0 CLI")
    parser.add_argument("--symbol", type=str, help="Símbolo para analisar (ex: EURUSD)")
    parser.add_argument("--timeframe", type=str, default="H1", help="Timeframe (M1, M5, M15, H1, D1)")
    parser.add_argument("--api", action="store_true", help="Iniciar a API FastAPI")
    parser.add_argument("--monitor", action="store_true", help="Monitorar principais ativos em tempo real")
    parser.add_argument("--interval", type=int, default=15, help="Intervalo de monitoramento em minutos")
    
    args = parser.parse_args()
    
    if args.api:
        import uvicorn
        logger.info("Iniciando API...")
        uvicorn.run("dailyagent.api.main:app", host="0.0.0.0", port=8000, reload=True)
        return

    if args.monitor:
        monitor = MonitorEngine()
        monitor.discover_main_symbols()
        monitor.start_monitoring(interval_minutes=args.interval)
        
        # Mantém o processo vivo enquanto a thread de monitoramento roda
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop()
            logger.info("Encerrando DailyAgent...")
        return

    if not args.symbol:
        logger.error("Você deve fornecer um --symbol, usar --api ou --monitor")
        sys.exit(1)

    agent = DailyAgent()
    
    # Mapeamento simples de timeframe
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "D1": mt5.TIMEFRAME_D1
    }
    tf = tf_map.get(args.timeframe.upper(), mt5.TIMEFRAME_H1)
    
    result = agent.run_for_symbol(args.symbol, tf)
    
    if "error" in result:
        print(f"Erro: {result['error']}")
    else:
        print("\n" + "="*50)
        print(f"RELATÓRIO PARA {args.symbol}")
        print("="*50)
        print(result['report'])
        print("="*50)

if __name__ == "__main__":
    main()
