from peewee import *
from ..core.config import settings
from ..core.logger import get_logger
from datetime import datetime, timezone

logger = get_logger("Database")

# Conexão com o Banco de Dados
db = PostgresqlDatabase(
    settings.db_name,
    user=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port
)

class BaseModel(Model):
    class Meta:
        database = db

class Run(BaseModel):
    symbol = CharField()
    timeframe = IntegerField()
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))
    trend = CharField()
    volatility = CharField()
    macro_score = FloatField()
    rsi = FloatField()

class Signal(BaseModel):
    run = ForeignKeyField(Run, backref='signals')
    type = CharField()
    direction = CharField()
    strength = FloatField()
    final_score = FloatField()
    
    # Campos de Validação (Feedback)
    entry_price = FloatField(null=True)
    tp_price = FloatField(null=True)
    sl_price = FloatField(null=True)
    status = CharField(default="PENDING") # PENDING, WIN, LOSS, EXPIRED
    pnl_points = FloatField(null=True)
    validated_at = DateTimeField(null=True)

class Report(BaseModel):
    run = ForeignKeyField(Run, backref='reports')
    content = TextField()
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

class ChatMessage(BaseModel):
    chat_id = CharField(index=True)
    role = CharField()
    content = TextField()
    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc), index=True)

class BinarySignal(BaseModel):
    run = ForeignKeyField(Run, backref='binary_signals')
    direction = CharField()            # CALL, PUT
    expiration = CharField()           # M1, M5, M15
    confidence = IntegerField()        # 0-100
    entry_price = FloatField()
    expiry_price = FloatField(null=True)
    status = CharField(default="OPEN") # OPEN, ITM, OTM, TIE
    signal_type = CharField(null=True)
    regime_trend = CharField(null=True)
    regime_volatility = CharField(null=True)
    final_score = FloatField(null=True)
    opened_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    expires_at = DateTimeField()
    closed_at = DateTimeField(null=True)
    verdict_text = TextField(null=True)

def _migrate_missing_columns():
    """Adiciona colunas que faltam em tabelas existentes."""
    migrations = [
        ("signal", "entry_price", "REAL"),
        ("signal", "tp_price", "REAL"),
        ("signal", "sl_price", "REAL"),
        ("signal", "status", "VARCHAR(255) DEFAULT 'PENDING'"),
        ("signal", "pnl_points", "REAL"),
        ("signal", "validated_at", "TIMESTAMP"),
        ("chatmessage", "chat_id", "VARCHAR(255)"),
        ("chatmessage", "role", "VARCHAR(255)"),
        ("chatmessage", "content", "TEXT"),
        ("chatmessage", "created_at", "TIMESTAMP"),
        ("binarysignal", "direction", "VARCHAR(255)"),
        ("binarysignal", "expiration", "VARCHAR(255)"),
        ("binarysignal", "confidence", "INTEGER"),
        ("binarysignal", "entry_price", "REAL"),
        ("binarysignal", "expiry_price", "REAL"),
        ("binarysignal", "status", "VARCHAR(255) DEFAULT 'OPEN'"),
        ("binarysignal", "signal_type", "VARCHAR(255)"),
        ("binarysignal", "regime_trend", "VARCHAR(255)"),
        ("binarysignal", "regime_volatility", "VARCHAR(255)"),
        ("binarysignal", "final_score", "REAL"),
        ("binarysignal", "opened_at", "TIMESTAMP"),
        ("binarysignal", "expires_at", "TIMESTAMP"),
        ("binarysignal", "closed_at", "TIMESTAMP"),
        ("binarysignal", "verdict_text", "TEXT"),
    ]
    for table, column, col_type in migrations:
        try:
            db.execute_sql(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}')
            logger.info(f"Coluna '{column}' adicionada em '{table}'.")
        except Exception:
            pass  # Coluna ja existe, ignora


def init_db():
    """Inicializa a conexao e cria as tabelas se nao existirem."""
    try:
        db.connect()
        logger.info("Conexao com banco de dados estabelecida.")
        db.create_tables([Run, Signal, Report, ChatMessage, BinarySignal], safe=True)
        _migrate_missing_columns()
        logger.info("Tabelas verificadas/criadas com sucesso.")
        db.close()
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise
