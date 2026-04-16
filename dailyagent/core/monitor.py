import threading
import time
from .agent import DailyAgent
from .validator import ValidatorEngine
from .logger import get_logger
from .config import settings
from .mt5_client import MT5Client
import MetaTrader5 as mt5

logger = get_logger("MonitorEngine")

class MonitorEngine:
    def __init__(self, symbols=None):
        self.agent = DailyAgent()
        self.validator = ValidatorEngine()
        self.mt5 = MT5Client()
        self.symbols = symbols or []
        self.is_running = False
        self._stop_event = threading.Event()
        self.threads = []

    def discover_main_symbols(self):
        if not self.mt5.connect():
            return []
            
        all_symbols = self.mt5.get_symbols()
        main_assets = []
        
        # Filtros para ativos principais
        patterns = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", # Forex Majors
            "BTCUSD", "ETHUSD", "SOLUSD",                    # Cryptos
            "US500", "USTECH", "GER40", "UK100"              # Indices
        ]
        
        for pattern in patterns:
            for s in all_symbols:
                if pattern in s.upper():
                    main_assets.append(s)
                    break
                    
        self.mt5.disconnect()
        self.symbols = list(set(main_assets))
        logger.info(f"Ativos selecionados para monitoramento: {self.symbols}")
        return self.symbols

    def start_monitoring(self, interval_minutes=15):
        self.is_running = True
        self._stop_event.clear()
        logger.info(f"Iniciando monitoramento em tempo real (Intervalo: {interval_minutes}min)")
        
        # Thread forex
        thread = threading.Thread(target=self._monitor_loop, args=(interval_minutes,))
        thread.daemon = True
        thread.start()
        self.threads.append(thread)

        # Thread binaria (se habilitada)
        if settings.binary.enabled and settings.binary.assets:
            interval_sec = settings.binary.monitor_interval_seconds
            logger.info(
                f"Iniciando monitor binario (Intervalo: {interval_sec}s, "
                f"Ativos: {settings.binary.assets})"
            )
            binary_thread = threading.Thread(
                target=self._binary_monitor_loop,
                args=(interval_sec,)
            )
            binary_thread.daemon = True
            binary_thread.start()
            self.threads.append(binary_thread)

    def _monitor_loop(self, interval_minutes):
        while self.is_running and not self._stop_event.is_set():
            logger.info("--- Iniciando ciclo de VALIDACAO ---")
            try:
                self.validator.validate_pending_signals()
            except Exception as e:
                logger.error(f"Erro no ciclo de validacao: {e}")

            if self._stop_event.is_set():
                break

            logger.info("--- Iniciando ciclo de MONITORAMENTO ---")
            for symbol in self.symbols:
                if self._stop_event.is_set():
                    break
                try:
                    self.agent.run_for_symbol(symbol, mt5.TIMEFRAME_H1)
                except Exception as e:
                    logger.error(f"Erro ao monitorar {symbol}: {e}")
                
                self._stop_event.wait(2)
                
            logger.info(f"Ciclo concluido. Proxima verificacao em {interval_minutes} minutos.")
            self._stop_event.wait(interval_minutes * 60)

    def _binary_monitor_loop(self, interval_seconds):
        """Loop de monitoramento para opcoes binarias."""
        binary_assets = settings.binary.assets
        default_exp = settings.binary.default_expiration

        while self.is_running and not self._stop_event.is_set():
            logger.info("--- Ciclo BINARIO ---")

            # Valida sinais expirados primeiro
            try:
                self.validator._validate_pending_binary_signals()
            except Exception as e:
                logger.error(f"Erro na validacao binaria: {e}")

            if self._stop_event.is_set():
                break

            # Gera novos sinais
            for symbol in binary_assets:
                if self._stop_event.is_set():
                    break
                try:
                    self.agent.run_for_symbol_binary(symbol, default_exp)
                except Exception as e:
                    logger.error(f"Erro no binario {symbol}: {e}")

                self._stop_event.wait(1)

            logger.info(f"Ciclo binario concluido. Proximo em {interval_seconds}s.")
            self._stop_event.wait(interval_seconds)

    def stop(self):
        self.is_running = False
        self._stop_event.set()
        logger.info("Monitoramento parado.")
