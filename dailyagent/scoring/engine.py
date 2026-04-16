from ..core.logger import get_logger

logger = get_logger("ScoringEngine")

class ScoringEngine:
    def score_signals(self, signals, regime, regime_parent=None):
        scored_signals = []
        macro_score = regime['macro_score']
        
        for signal in signals:
            # 1. Ajuste baseado no regime local
            final_score = self._calculate_final_score(signal, macro_score)
            
            # 2. Ajuste baseado na confluência MTF (Timeframe Superior)
            if regime_parent:
                final_score = self._apply_mtf_confluence(signal, final_score, regime_parent)
            
            scored_signals.append({
                **signal,
                "final_score": round(final_score, 2)
            })
            
        # Ordena por score final (melhores sinais primeiro)
        scored_signals.sort(key=lambda x: x['final_score'], reverse=True)
        return scored_signals

    def _calculate_final_score(self, signal, macro_score):
        direction_multiplier = 1.0
        if signal['direction'] == "BUY":
            direction_multiplier = 1.0 + (macro_score / 500)
        else: # SELL
            direction_multiplier = 1.0 - (macro_score / 500)
            
        return signal['strength'] * direction_multiplier

    def _apply_mtf_confluence(self, signal, current_score, regime_parent):
        parent_trend = regime_parent['trend']
        bonus = 1.0
        
        # Confluência Bullish
        if signal['direction'] == "BUY":
            if "bullish" in parent_trend:
                bonus = 1.2 # +20% de bônus por estar a favor da maré maior
                logger.info(f"✨ Bônus MTF aplicado para BUY (Trend Pai: {parent_trend})")
            elif "bearish" in parent_trend:
                bonus = 0.7 # -30% de penalidade por operar contra a maré maior
                logger.info(f"⚠️ Penalidade MTF aplicada para BUY (Trend Pai: {parent_trend})")
        
        # Confluência Bearish
        elif signal['direction'] == "SELL":
            if "bearish" in parent_trend:
                bonus = 1.2
                logger.info(f"✨ Bônus MTF aplicado para SELL (Trend Pai: {parent_trend})")
            elif "bullish" in parent_trend:
                bonus = 0.7
                logger.info(f"⚠️ Penalidade MTF aplicada para SELL (Trend Pai: {parent_trend})")
                
        return current_score * bonus
