import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
from ..persistence.models import Signal, Run, BinarySignal, db
from .mt5_client import MT5Client
from .logger import get_logger
from .config import settings

logger = get_logger("ValidatorEngine")

class ValidatorEngine:
    def __init__(self):
        self.mt5 = MT5Client()

    def validate_pending_signals(self):
        logger.info("Iniciando validacao de sinais pendentes...")
        
        if not self.mt5.connect():
            return
            
        try:
            # Busca sinais forex pendentes dos ultimos 3 dias
            three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
            pending_signals = (
                Signal.select()
                .join(Run)
                .where(
                    Signal.status == "PENDING",
                    Run.timestamp > three_days_ago
                )
            )
            
            logger.info(f"Encontrados {len(pending_signals)} sinais forex para validar.")
            
            for signal in pending_signals:
                self._validate_single_signal(signal)

            # Valida sinais binarios expirados
            self._validate_pending_binary_signals()
                
        finally:
            self.mt5.disconnect()

    def _validate_single_signal(self, signal):
        # Pula sinais sem TP/SL definidos (dados incompletos)
        if signal.tp_price is None or signal.sl_price is None or signal.entry_price is None:
            return

        symbol = signal.run.symbol
        timeframe = signal.run.timeframe
        start_time = signal.run.timestamp
        
        # Baixa dados desde o momento do sinal até agora
        rates = mt5.copy_rates_range(symbol, timeframe, start_time, datetime.now(timezone.utc))
        
        if rates is None or len(rates) < 2:
            return

        df = pd.DataFrame(rates)
        
        # Verifica toque no TP ou SL
        hit_tp = False
        hit_sl = False
        pnl = 0.0
        
        for _, row in df.iterrows():
            if signal.direction == "BUY":
                if row['high'] >= signal.tp_price:
                    hit_tp = True
                    break
                if row['low'] <= signal.sl_price:
                    hit_sl = True
                    break
            else: # SELL
                if row['low'] <= signal.tp_price:
                    hit_tp = True
                    break
                if row['high'] >= signal.sl_price:
                    hit_sl = True
                    break
        
        # Atualiza status no banco
        if hit_tp:
            signal.status = "WIN"
            signal.pnl_points = abs(signal.tp_price - signal.entry_price)
            logger.info(f"✅ SINAL WIN: {symbol} | Entrada: {signal.entry_price} | Alvo: {signal.tp_price}")
        elif hit_sl:
            signal.status = "LOSS"
            signal.pnl_points = -abs(signal.entry_price - signal.sl_price)
            logger.info(f"❌ SINAL LOSS: {symbol} | Entrada: {signal.entry_price} | Stop: {signal.sl_price}")
        elif len(df) > 100: # Se passou de 100 candles e não tocou nada
            signal.status = "EXPIRED"
            logger.info(f"⚪ SINAL EXPIRED: {symbol} (Tempo limite atingido)")
            
        if signal.status != "PENDING":
            signal.validated_at = datetime.now(timezone.utc)
            signal.save()

    def _validate_pending_binary_signals(self):
        """Valida sinais binarios cujo tempo de expiracao ja passou."""
        now = datetime.now(timezone.utc)
        try:
            expired_signals = (
                BinarySignal.select(BinarySignal, Run)
                .join(Run)
                .where(
                    BinarySignal.status == "OPEN",
                    BinarySignal.expires_at <= now
                )
            )

            count = len(expired_signals)
            if count == 0:
                return
            logger.info(f"Validando {count} sinais binarios expirados...")

            for sig in expired_signals:
                symbol = sig.run.symbol
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    logger.warning(f"Sem tick para {symbol}, pulando validacao binaria.")
                    continue

                expiry_price = tick.bid
                sig.expiry_price = expiry_price
                sig.closed_at = now

                if sig.direction == "CALL":
                    if expiry_price > sig.entry_price:
                        sig.status = "ITM"
                    elif expiry_price < sig.entry_price:
                        sig.status = "OTM"
                    else:
                        sig.status = "TIE"
                else:  # PUT
                    if expiry_price < sig.entry_price:
                        sig.status = "ITM"
                    elif expiry_price > sig.entry_price:
                        sig.status = "OTM"
                    else:
                        sig.status = "TIE"

                sig.save()
                logger.info(
                    f"Binario {symbol}: {sig.direction} {sig.expiration} -> "
                    f"{sig.status} (entrada={sig.entry_price} saida={expiry_price})"
                )

                # Notifica resultado via WhatsApp
                if settings.notifications.waha_enabled:
                    try:
                        from ..notifications.waha import WahaAgent
                        waha = WahaAgent()
                        waha.send_binary_result(
                            symbol, sig.direction, sig.status,
                            sig.entry_price, expiry_price
                        )
                    except Exception as e:
                        logger.warning(f"Falha ao notificar resultado binario: {e}")

        except Exception as e:
            logger.error(f"Erro ao validar sinais binarios: {e}")

if __name__ == "__main__":
    # Permite rodar a validação manualmente
    validator = ValidatorEngine()
    validator.validate_pending_signals()
