import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List

# Carrega o .env para segredos (API Keys, DB Passwords)
load_dotenv(override=True)

class ModelsConfig(BaseModel):
    trend_model: str = ""
    contrarian_model: str = ""
    fundamental_model: str = ""
    moderator_model: str = ""
    whatsapp_agent: str = ""

class LLMConfig(BaseModel):
    provider: str = "openrouter"
    max_rpm: int = 30
    max_retries: int = 3
    openrouter_models: ModelsConfig = Field(default_factory=ModelsConfig)
    nvidia_models: ModelsConfig = Field(default_factory=ModelsConfig)

    @property
    def active_models(self) -> ModelsConfig:
        if self.provider == "nvidia":
            return self.nvidia_models
        return self.openrouter_models

    @property
    def trend_model(self) -> str:
        return self.active_models.trend_model

    @property
    def contrarian_model(self) -> str:
        return self.active_models.contrarian_model

    @property
    def fundamental_model(self) -> str:
        return self.active_models.fundamental_model

    @property
    def moderator_model(self) -> str:
        return self.active_models.moderator_model

    @property
    def whatsapp_agent(self) -> str:
        return self.active_models.whatsapp_agent

class NotificationToggles(BaseModel):
    ntfy_enabled: bool = True
    waha_enabled: bool = False

class WahaConfig(BaseModel):
    api_url: str = "http://localhost:3000"
    session: str = "default"
    recipient_phone: str = ""
    webhook_token: str = ""
    api_key: str = ""

class WhatsAppAgentConfig(BaseModel):
    rate_limit_max_requests: int = 10
    rate_limit_window_seconds: int = 60
    analysis_timeout_seconds: int = 180
    llm_timeout_seconds: int = 60

class NtfyConfig(BaseModel):
    topic: str = "dailyagent-report"
    url: str = "https://ntfy.sh/"
    user: str = ""
    password: str = ""

class MonitoringConfig(BaseModel):
    default_interval_minutes: int = 15
    assets: List[str] = []

class BinaryConfig(BaseModel):
    enabled: bool = False
    expirations: List[str] = ["M5"]
    default_expiration: str = "M5"
    confidence_threshold: int = 65
    monitor_interval_seconds: int = 60
    assets: List[str] = []

class Settings(BaseModel):
    # Segredos do .env
    openrouter_api_key: str = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())
    nvidia_api_key: str = Field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", "").strip())
    db_host: str = Field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = Field(default_factory=lambda: int(os.getenv("DB_PORT", 5432)))
    db_name: str = Field(default_factory=lambda: os.getenv("DB_NAME", "dailyagent"))
    db_user: str = Field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    db_password: str = Field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    
    ntfy_topic: str = Field(default_factory=lambda: os.getenv("NTFY_TOPIC", "dailyagent-report"))
    ntfy_url: str = Field(default_factory=lambda: os.getenv("NTFY_URL", "https://ntfy.sh/"))
    ntfy_user: Optional[str] = Field(default_factory=lambda: os.getenv("NTFY_USER"))
    ntfy_password: Optional[str] = Field(default_factory=lambda: os.getenv("NTFY_PASSWORD"))

    # Configuracoes do config.json
    llm: LLMConfig = Field(default_factory=LLMConfig)
    notifications: NotificationToggles = Field(default_factory=NotificationToggles)
    ntfy: NtfyConfig = Field(default_factory=NtfyConfig)
    waha: WahaConfig = Field(default_factory=WahaConfig)
    whatsapp_config: WhatsAppAgentConfig = Field(default_factory=WhatsAppAgentConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    binary: BinaryConfig = Field(default_factory=BinaryConfig)

    def load_from_json(self, path="config.json"):
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                if "llm" in data: self.llm = LLMConfig(**data["llm"])
                if "notifications" in data: self.notifications = NotificationToggles(**data["notifications"])
                if "ntfy" in data: self.ntfy = NtfyConfig(**data["ntfy"])
                if "waha" in data: self.waha = WahaConfig(**data["waha"])
                if "whatsapp_config" in data: self.whatsapp_config = WhatsAppAgentConfig(**data["whatsapp_config"])
                if "monitoring" in data: self.monitoring = MonitoringConfig(**data["monitoring"])
                if "binary" in data: self.binary = BinaryConfig(**data["binary"])

settings = Settings()
settings.load_from_json()
