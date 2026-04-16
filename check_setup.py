"""
Script de diagnóstico rápido do DailyAgent 2.0
Verifica se todas as dependências e configurações estão OK.
"""

import sys
import os

# Fix para Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def check_python_version():
    """Verifica versão do Python."""
    print("\n🐍 Python:")
    version = sys.version_info
    print(f"   Versão: {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 10:
        print("   ✅ Versão compatível (3.10+)")
        return True
    else:
        print("   ❌ Requer Python 3.10+")
        return False

def check_dependencies():
    """Verifica se todas as dependências estão instaladas."""
    print("\n📦 Dependências:")
    required = [
        ("MetaTrader5", "MetaTrader5"), ("pandas", "pandas"), ("numpy", "numpy"), 
        ("pydantic", "pydantic"), ("openai", "openai"), ("loguru", "loguru"),
        ("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
        ("httpx", "httpx"), ("yfinance", "yfinance"), ("peewee", "peewee")
    ]
    
    missing = []
    for pkg_name, pkg_import in required:
        try:
            __import__(pkg_import)
            print(f"   ✅ {pkg_name}")
        except ImportError:
            print(f"   ❌ {pkg_name} - NÃO INSTALADO")
            missing.append(pkg_name)
    
    if missing:
        print(f"\n   💡 Execute: pip install {' '.join(missing)}")
        return False
    return True

def check_env_file():
    """Verifica se .env existe."""
    print("\n🔐 Arquivo .env:")
    if os.path.exists(".env"):
        print("   ✅ .env encontrado")
        
        # Verifica se tem a API key
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        if api_key and len(api_key) > 10:
            print(f"   ✅ OpenRouter API Key configurada ({api_key[:5]}...{api_key[-5:]})")
        else:
            print("   ⚠️  OpenRouter API Key não configurada ou inválida")
            print("   💡 Edite o .env e adicione sua chave")
        return True
    else:
        print("   ❌ .env NÃO encontrado")
        print("   💡 Execute: copy .env.example .env")
        return False

def check_config_file():
    """Verifica se config.json existe."""
    print("\n⚙️  Arquivo config.json:")
    if os.path.exists("config.json"):
        import json
        with open("config.json") as f:
            config = json.load(f)
        print("   ✅ config.json encontrado e válido")
        
        # Verifica ativos configurados
        assets = config.get("monitoring", {}).get("assets", [])
        print(f"   📊 Ativos configurados: {', '.join(assets)}")
        return True
    else:
        print("   ❌ config.json NÃO encontrado")
        return False

def check_modules_import():
    """Verifica se todos os módulos importam corretamente."""
    print("\n🧩 Módulos do DailyAgent:")
    
    modules = [
        ("dailyagent.core.agent", "DailyAgent"),
        ("dailyagent.core.monitor", "MonitorEngine"),
        ("dailyagent.core.mt5_client", "MT5Client"),
        ("dailyagent.features.processor", "FeatureProcessor"),
        ("dailyagent.regime.classifier", "RegimeClassifier"),
        ("dailyagent.signals.engine", "SignalEngine"),
        ("dailyagent.scoring.engine", "ScoringEngine"),
        ("dailyagent.llm.debate", "DebateEngine"),
        ("dailyagent.notifications.ntfy", "NotificationAgent"),
        ("dailyagent.notifications.waha", "WahaAgent"),
        ("dailyagent.api.main", "app"),
    ]
    
    all_ok = True
    for module, cls in modules:
        try:
            mod = __import__(module, fromlist=[cls])
            getattr(mod, cls)
            print(f"   ✅ {module}.{cls}")
        except Exception as e:
            print(f"   ❌ {module}.{cls} - {str(e)[:50]}")
            all_ok = False
    
    return all_ok

def check_mt5():
    """Verifica conexão com MT5."""
    print("\n📈 MetaTrader 5:")
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            info = mt5.terminal_info()
            print(f"   ✅ MT5 conectado (Terminal: {info.name})")
            mt5.shutdown()
            return True
        else:
            print("   ⚠️  MT5 não inicializou (pode precisar estar logado)")
            return False
    except Exception as e:
        print(f"   ❌ Erro ao verificar MT5: {e}")
        return False

def main():
    print("="*60)
    print("🔍 DAILYAGENT 2.0 - DIAGNÓSTICO DO SISTEMA")
    print("="*60)
    
    results = {
        "Python": check_python_version(),
        "Dependências": check_dependencies(),
        "Arquivo .env": check_env_file(),
        "Arquivo config.json": check_config_file(),
        "Módulos": check_modules_import(),
        "MetaTrader 5": check_mt5(),
    }
    
    print("\n" + "="*60)
    print("📊 RESUMO")
    print("="*60)
    
    for check, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {check}")
    
    all_passed = all(results.values())
    
    print("="*60)
    if all_passed:
        print("🎉 Sistema pronto para uso!")
        print("\n🚀 Execute: python server.py")
    else:
        print("⚠️  Alguns itens precisam de atenção.")
        print("\n💡 Consulte o README.md para instruções de configuração.")
    print("="*60)

if __name__ == "__main__":
    main()
