"""
DailyAgent 2.0 - Agente Autônomo de Trading com IA

Um sistema completo de análise de mercado que combina:
- Análise técnica quantitativa (regime, sinais, scoring)
- Inteligência Artificial Multi-Agent (Debate entre 4 agentes LLM)
- Análise fundamentalista (notícias Yahoo Finance)
- Monitoramento em tempo real com validação automática de sinais
"""

__version__ = "2.0.0"
__author__ = "DailyAgent Team"

# Core
from .core.agent import DailyAgent
from .core.monitor import MonitorEngine
from .core.mt5_client import MT5Client
from .core.config import settings
from .core.logger import get_logger

# Features & Indicators
from .features.processor import FeatureProcessor
from .features.indicators import Indicators
from .features.fundamentals import FundamentalAnalyzer

# Regime & Signals
from .regime.classifier import RegimeClassifier
from .signals.engine import SignalEngine
from .scoring.engine import ScoringEngine

# LLM
from .llm.client import LLMClient
from .llm.debate import DebateEngine

# Notifications
from .notifications.ntfy import NotificationAgent
from .notifications.waha import WahaAgent
from .notifications.whatsapp_agent import WhatsAppAgent

# Persistence
from .persistence.models import Run, Signal, Report, ChatMessage, db, init_db

__all__ = [
    "DailyAgent",
    "MonitorEngine",
    "MT5Client",
    "settings",
    "get_logger",
    "FeatureProcessor",
    "Indicators",
    "FundamentalAnalyzer",
    "RegimeClassifier",
    "SignalEngine",
    "ScoringEngine",
    "LLMClient",
    "DebateEngine",
    "NotificationAgent",
    "WahaAgent",
    "WhatsAppAgent",
    "Run",
    "Signal",
    "Report",
    "ChatMessage",
    "db",
    "init_db",
]
