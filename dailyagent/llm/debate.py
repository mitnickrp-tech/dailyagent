from .client import LLMClient
from ..core.config import settings
from ..core.logger import get_logger
import json
import concurrent.futures

logger = get_logger("DebateEngine")

class DebateEngine:
    def __init__(self):
        self.llm = LLMClient()
        self.trend_model = settings.llm.trend_model
        self.contrarian_model = settings.llm.contrarian_model
        self.fundamental_model = settings.llm.fundamental_model
        self.moderator_model = settings.llm.moderator_model

    def get_consensus(self, symbol, regime, signals, regime_parent=None, news_context=""):
        logger.info(f"⚖️ Iniciando debate entre 4 Agentes para {symbol}...")
        
        # 1, 2 e 3. Rodar Agente de Tendência, Contrário e Fundamentalista em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_trend = executor.submit(
                self._run_agent, 
                "Analista de Tendência", 
                "Foque em identificar força, momentum e continuação de movimento. Respeite a tendência macro se ela for clara.", 
                symbol, regime, signals, self.trend_model, regime_parent
            )
            future_contrarian = executor.submit(
                self._run_agent, 
                "Analista Contrarian", 
                "Busque por sinais de exaustão, suportes/resistências fortes e riscos de reversão.", 
                symbol, regime, signals, self.contrarian_model, regime_parent
            )
            future_fundamental = executor.submit(
                self._run_fundamental_agent,
                symbol, news_context, self.fundamental_model
            )
            
            logger.info("⏳ Aguardando análises iniciais (paralelo: Tendência, Contrário, Fundamentalista)...")
            r1 = future_trend.result()
            r2 = future_contrarian.result()
            r3 = future_fundamental.result()
        
        # 4. Gerente de Risco (Veredito Final)
        logger.info("👨‍⚖️ Solicitando veredito final ao Moderador...")
        regime_parent_str = json.dumps(regime_parent) if regime_parent else "Não disponível"
        
        verdict_prompt = f"""
        Você é o Chefe de Mesa de Operações. Leia as TRÊS análises abaixo e dê o veredito final.
        
        DADOS MACRO (Timeframe Superior): {regime_parent_str}
        
        ANÁLISE 1 (Tendência): {r1}
        ANÁLISE 2 (Contrarian): {r2}
        ANÁLISE 3 (Fundamentalista): {r3}
        
        DADOS LOCAIS: {json.dumps(regime)} | {json.dumps(signals)}
        
        Instruções:
        1. Decida por COMPRA, VENDA ou AGUARDAR.
        2. Dê um peso CRÍTICO à análise fundamentalista se houver eventos de alto impacto (ex: CPI, Taxa de Juros).
        3. Justifique baseado na confluência de tempos gráficos e no contexto macroeconômico.
        4. Defina o nível de confiança (0-100%).
        
        Responda em Português.
        """
        verdict = self.llm.generate_custom_prompt(verdict_prompt, model=self.moderator_model)
        
        logger.info(f"✅ Veredito concluído para {symbol}")
        return {
            "trend_analysis": r1,
            "contrarian_analysis": r2,
            "fundamental_analysis": r3,
            "final_verdict": verdict
        }

    def _run_agent(self, role, instructions, symbol, regime, signals, model, regime_parent):
        logger.info(f"🤖 Agente {role} processando...")
        prompt = self._build_persona_prompt(role, instructions, symbol, regime, signals, regime_parent)
        return self.llm.generate_custom_prompt(prompt, model=model)

    def _run_fundamental_agent(self, symbol, news_context, model):
        logger.info(f"📰 Agente Fundamentalista processando...")
        prompt = f"""
        Você é um Analista Fundamentalista Senior. Sua tarefa é avaliar o impacto das notícias recentes no ativo {symbol}.
        
        NOTÍCIAS RECENTES:
        {news_context}
        
        Avalie o sentimento predominante (Bullish/Bearish/Neutral) e se há riscos iminentes.
        Seja técnico, rápido e direto.
        """
        return self.llm.generate_custom_prompt(prompt, model=model)

    def _build_persona_prompt(self, role, instructions, symbol, regime, signals, regime_parent):
        parent_context = f"\nCONTEXTO MACRO (Timeframe Superior):\n{json.dumps(regime_parent)}" if regime_parent else ""
        
        return f"""
        Você é um {role}. {instructions}
        
        Dados para {symbol}:
        Regime Local: {json.dumps(regime)}{parent_context}
        Sinais Detectados: {json.dumps(signals)}
        
        Faça uma análise técnica rápida e objetiva considerando a confluência entre os tempos gráficos.
        """

    def get_quick_verdict(self, symbol, regime, signals, regime_parent=None, mode="forex", expiration=None):
        """Veredito rapido com 1 unica chamada LLM (sem debate)."""
        logger.info(f"Quick verdict para {symbol} (mode={mode})...")

        regime_str = json.dumps(regime, ensure_ascii=False) if regime else "N/A"
        signals_str = json.dumps(signals, ensure_ascii=False) if signals else "N/A"
        parent_str = json.dumps(regime_parent, ensure_ascii=False) if regime_parent else "N/A"

        if mode == "binary":
            exp_label = expiration or "M5"
            decision_line = (
                f"Operacao binaria de {exp_label}. Foque em curtissimo prazo.\n"
                f"Decida: CALL, PUT ou WAIT. Confianca (0-100%).\n"
                f"Formato: DECISAO: CALL/PUT/WAIT | CONFIANCA: XX%"
            )
        else:
            decision_line = (
                "Decida: COMPRA, VENDA ou AGUARDAR. Confianca (0-100%).\n"
                "Formato: DECISAO: COMPRA/VENDA/AGUARDAR | CONFIANCA: XX%"
            )

        prompt = f"""Voce e um analista de trading. Baseado nos dados quantitativos abaixo, de um veredito RAPIDO.

Ativo: {symbol}
Regime: {regime_str}
Regime Superior: {parent_str}
Sinais: {signals_str}

{decision_line}

Seja DIRETO. Maximo 3 linhas."""

        verdict = self.llm.generate_custom_prompt(prompt, model=self.moderator_model)
        logger.info(f"Quick verdict concluido para {symbol}: {verdict[:80]}...")
        return verdict
