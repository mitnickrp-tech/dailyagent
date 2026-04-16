from openai import OpenAI
from ..core.config import settings
from ..core.logger import get_logger
import json
import time
import threading
import random

logger = get_logger("LLMClient")


class LLMRateLimiter:
    """Sliding window rate limiter para APIs LLM (thread-safe)."""

    def __init__(self, max_rpm: int = 30):
        self.max_rpm = max_rpm
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def wait_if_needed(self):
        """Bloqueia ate que haja slot disponivel dentro da janela de 60s."""
        with self._lock:
            now = time.monotonic()
            cutoff = now - 60.0
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self.max_rpm:
                sleep_time = self._timestamps[0] - cutoff + 0.1
                logger.warning(
                    f"Rate limiter: {len(self._timestamps)}/{self.max_rpm} RPM atingido. "
                    f"Aguardando {sleep_time:.1f}s..."
                )
                time.sleep(sleep_time)

            self._timestamps.append(time.monotonic())

# Configuracao por provider
PROVIDER_CONFIG = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_attr": "openrouter_api_key",
        "headers": {
            "HTTP-Referer": "https://github.com/dailyagent",
            "X-Title": "DailyAgent 2.0",
        },
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_attr": "nvidia_api_key",
        "headers": {},
    },
}


class LLMClient:
    # Rate limiter compartilhado entre todas as instancias
    _rate_limiter: LLMRateLimiter = None
    _rate_limiter_lock = threading.Lock()

    def __init__(self):
        self.provider = settings.llm.provider
        self.max_retries = getattr(settings.llm, 'max_retries', 3)

        # Inicializa rate limiter singleton (thread-safe)
        if LLMClient._rate_limiter is None:
            with LLMClient._rate_limiter_lock:
                if LLMClient._rate_limiter is None:
                    max_rpm = getattr(settings.llm, 'max_rpm', 30)
                    LLMClient._rate_limiter = LLMRateLimiter(max_rpm=max_rpm)
                    logger.info(f"Rate limiter inicializado: {max_rpm} RPM")
        
        if self.provider not in PROVIDER_CONFIG:
            logger.error(
                f"Provider '{self.provider}' invalido. "
                f"Opcoes: {', '.join(PROVIDER_CONFIG.keys())}"
            )
            self.client = None
            return

        config = PROVIDER_CONFIG[self.provider]
        self.base_url = config["base_url"]
        self.api_key = getattr(settings, config["key_attr"], "") or ""

        if self.api_key and len(self.api_key) > 10:
            logger.info(
                f"LLMClient inicializado | Provider: {self.provider} | "
                f"Chave: {self.api_key[:5]}...{self.api_key[-5:]}"
            )
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=config["headers"] or None,
            )
        else:
            logger.error(
                f"API Key do {self.provider} nao configurada. "
                f"Verifique a variavel de ambiente no .env."
            )
            self.client = None

    def generate_report(self, symbol: str, regime: dict, signals: list):
        if not self.client:
            return "Relatorio nao gerado: API Client nao disponivel."

        prompt = self._build_prompt(symbol, regime, signals)
        return self.generate_custom_prompt(prompt)

    def generate_custom_prompt(self, prompt: str, model: str = None):
        if not self.client:
            return "Erro: Client nao inicializado. Verifique sua API Key."

        if model is None:
            model = settings.llm.trend_model

        last_error = None
        for attempt in range(self.max_retries + 1):
            # Rate limiting antes de cada request
            LLMClient._rate_limiter.wait_if_needed()

            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    timeout=60.0
                )
                return response.choices[0].message.content

            except Exception as e:
                last_error = e
                err_msg = str(e)

                if "429" in err_msg:
                    if attempt < self.max_retries:
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"429 Rate limited ({self.provider}). "
                            f"Retry {attempt + 1}/{self.max_retries} em {backoff:.1f}s..."
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        logger.error(f"429 Rate limited ({self.provider}). Max retries atingido.")
                elif "401" in err_msg:
                    logger.error(f"ERRO 401: API Key do {self.provider} invalida.")
                    break
                elif "404" in err_msg:
                    logger.error(f"ERRO 404: Modelo '{model}' nao encontrado no {self.provider}.")
                    break
                else:
                    if attempt < self.max_retries:
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"Erro na API {self.provider}: {err_msg}. "
                            f"Retry {attempt + 1}/{self.max_retries} em {backoff:.1f}s..."
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        logger.error(f"Erro na API {self.provider}: {err_msg}")
                        break

        return f"Erro na geracao de resposta ({model}): {last_error}"

    def _build_prompt(self, symbol, regime, signals):
        signals_str = json.dumps(signals, indent=2)
        regime_str = json.dumps(regime, indent=2)

        return f"""
        Analise os seguintes dados quantitativos para o ativo {symbol}:
        
        DADOS DE REGIME:
        {regime_str}
        
        SINAIS DETECTADOS (Scored):
        {signals_str}
        
        Instrucoes:
        1. Resuma o sentimento atual do mercado (Bullish/Bearish/Neutral).
        2. Avalie a qualidade dos sinais detectados com base na volatilidade e regime.
        3. De uma recomendacao tecnica concisa (BUY/SELL/WAIT).
        4. Identifique pontos de atencao ou riscos imediatos.
        
        Seja tecnico e objetivo. Use portugues do Brasil.
        """
