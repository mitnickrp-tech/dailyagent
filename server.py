"""
DailyAgent Server - Inicia API e Monitor simultaneamente.

Uso:
    python server.py                  # Modo padrão (API + Monitor)
    python server.py --api-only       # Apenas API
    python server.py --monitor-only   # Apenas Monitor
    python server.py --interval 10    # Intervalo personalizado (minutos)
    python server.py --port 8080      # Porta personalizada
"""

import sys
import os
import argparse
import time
import signal
import threading
import uvicorn
from dailyagent.core.monitor import MonitorEngine
from dailyagent.core.logger import get_logger
from dailyagent.core.config import settings
from dailyagent.api.main import app

logger = get_logger("Server")

# Referencia global para shutdown limpo
_monitor: MonitorEngine = None
_uvicorn_server: uvicorn.Server = None


def start_api_server(host="0.0.0.0", port=8000):
    """Inicia o servidor FastAPI com shutdown controlavel."""
    global _uvicorn_server
    logger.info(f"Iniciando API FastAPI em {host}:{port}...")
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.run()


def start_monitor(interval_minutes=15):
    """Inicia o motor de monitoramento."""
    global _monitor
    logger.info(f"Iniciando MonitorEngine (intervalo: {interval_minutes}min)...")
    
    _monitor = MonitorEngine()
    
    # Usa ativos do config.json ou descobre automaticamente
    if settings.monitoring.assets:
        _monitor.symbols = settings.monitoring.assets
        logger.info(f"Ativos configurados: {_monitor.symbols}")
    else:
        logger.info("Nenhum ativo configurado, descobrindo automaticamente...")
        _monitor.discover_main_symbols()
    
    _monitor.start_monitoring(interval_minutes=interval_minutes)
    return _monitor


def _shutdown(signum=None, frame=None):
    """Shutdown limpo de todos os componentes."""
    logger.info("Encerrando DailyAgent Server...")
    if _monitor:
        _monitor.stop()
    if _uvicorn_server:
        _uvicorn_server.should_exit = True
    

def main():
    parser = argparse.ArgumentParser(description="DailyAgent Server (API + Monitor)")
    parser.add_argument("--api-only", action="store_true", help="Iniciar apenas a API")
    parser.add_argument("--monitor-only", action="store_true", help="Iniciar apenas o Monitor")
    parser.add_argument("--interval", type=int, default=None, help="Intervalo do monitor em minutos")
    parser.add_argument("--port", type=int, default=8000, help="Porta da API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host da API")
    
    args = parser.parse_args()
    
    # Registra handler de shutdown para SIGINT (Ctrl+C) e SIGTERM
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    
    # Usa intervalo do config.json se nao especificado
    interval = args.interval or settings.monitoring.default_interval_minutes
    
    logger.info("="*60)
    logger.info("DAILYAGENT SERVER 2.0")
    logger.info("="*60)
    
    if args.api_only:
        logger.info("Modo: API Only")
        start_api_server(args.host, args.port)
        
    elif args.monitor_only:
        logger.info(f"Modo: Monitor Only (intervalo: {interval}min)")
        monitor = start_monitor(interval)
        
        try:
            while not monitor._stop_event.is_set():
                monitor._stop_event.wait(1)
        except KeyboardInterrupt:
            _shutdown()
            
    else:
        logger.info(f"Modo: API + Monitor (intervalo: {interval}min)")
        logger.info(f"API: http://{args.host}:{args.port}")
        logger.info(f"Swagger: http://{args.host}:{args.port}/docs")
        logger.info(f"Monitor: {interval}min entre ciclos")
        
        # Inicia Monitor em thread separada
        monitor = start_monitor(interval)
        
        # Inicia API na thread principal (uvicorn gerencia seus proprios sinais)
        try:
            start_api_server(args.host, args.port)
        except KeyboardInterrupt:
            pass
        finally:
            _shutdown()


if __name__ == "__main__":
    main()
