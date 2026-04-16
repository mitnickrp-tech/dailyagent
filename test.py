import json
import socket
import sys
import time
from urllib import request, error

PORT = 8000
ROOT_PATH = "/"
WEBHOOK_PATH = "/waha/webhook"
TIMEOUT = 4

CANDIDATES = [
    "172.26.16.1",          # vEthernet (WSL) -> melhor candidato
    "host.docker.internal", # pode funcionar dependendo do setup
    "192.168.0.100",        # IP LAN do Windows
    "localhost",            # às vezes funciona
    "172.17.80.1",          # Default Switch
]


def log(msg: str) -> None:
    print(f"[INFO] {msg}")


def ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def try_resolve(host: str) -> tuple[bool, str]:
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except Exception as e:
        return False, str(e)


def try_tcp(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True, "conectou"
    except Exception as e:
        return False, str(e)


def try_http(url: str, method: str = "GET", data: dict | None = None) -> tuple[bool, str, str]:
    try:
        body = None
        headers = {}

        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url=url, data=body, headers=headers, method=method)

        with request.urlopen(req, timeout=TIMEOUT) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return True, f"HTTP {resp.status}", content[:500]

    except error.HTTPError as e:
        try:
            content = e.read().decode("utf-8", errors="replace")
        except Exception:
            content = ""
        return False, f"HTTP {e.code}", content[:500]

    except Exception as e:
        return False, str(e), ""


def test_candidate(host: str) -> dict:
    result = {
        "host": host,
        "dns_ok": False,
        "resolved_ip": "",
        "tcp_ok": False,
        "root_ok": False,
        "webhook_ok": False,
        "notes": [],
    }

    log(f"Testando host: {host}")

    dns_ok, dns_info = try_resolve(host)
    if dns_ok:
        result["dns_ok"] = True
        result["resolved_ip"] = dns_info
        ok(f"DNS: {host} -> {dns_info}")
    else:
        result["notes"].append(f"DNS falhou: {dns_info}")
        fail(f"DNS falhou: {dns_info}")
        # IP literal ainda pode funcionar sem DNS
        if host.replace(".", "").isdigit():
            result["notes"].append("Host parece ser IP literal; seguindo mesmo sem DNS.")
        else:
            return result

    tcp_ok, tcp_info = try_tcp(host, PORT)
    if tcp_ok:
        result["tcp_ok"] = True
        ok(f"TCP OK em {host}:{PORT}")
    else:
        result["notes"].append(f"TCP falhou: {tcp_info}")
        fail(f"TCP falhou: {tcp_info}")
        return result

    root_url = f"http://{host}:{PORT}{ROOT_PATH}"
    root_ok, root_status, root_body = try_http(root_url, "GET")
    if root_ok:
        result["root_ok"] = True
        ok(f"GET {root_url} -> {root_status}")
    else:
        result["notes"].append(f"GET raiz falhou: {root_status}")
        fail(f"GET {root_url} -> {root_status}")

    webhook_url = f"http://{host}:{PORT}{WEBHOOK_PATH}"
    payload = {
        "event": "message",
        "session": "default",
        "engine": "WEBJS",
        "payload": {
            "id": "diag-test-001",
            "from": "5511999999999@c.us",
            "to": "5511888888888@c.us",
            "body": "teste diagnostico webhook",
            "fromMe": False,
            "timestamp": int(time.time()),
        },
    }

    webhook_ok, webhook_status, webhook_body = try_http(webhook_url, "POST", payload)
    if webhook_ok:
        result["webhook_ok"] = True
        ok(f"POST {webhook_url} -> {webhook_status}")
    else:
        result["notes"].append(f"POST webhook falhou: {webhook_status}")
        fail(f"POST {webhook_url} -> {webhook_status}")

    if root_body:
        result["notes"].append(f"Resposta GET /: {root_body[:120]}")
    if webhook_body:
        result["notes"].append(f"Resposta POST webhook: {webhook_body[:120]}")

    return result


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 80)
    print("RESUMO FINAL")
    print("=" * 80)

    for r in results:
        score = sum([
            1 if r["dns_ok"] else 0,
            1 if r["tcp_ok"] else 0,
            1 if r["root_ok"] else 0,
            2 if r["webhook_ok"] else 0,
        ])

        print(f"\nHost: {r['host']}")
        print(f"  DNS:     {'OK' if r['dns_ok'] else 'FAIL'}", end="")
        if r["resolved_ip"]:
            print(f" ({r['resolved_ip']})")
        else:
            print()
        print(f"  TCP:     {'OK' if r['tcp_ok'] else 'FAIL'}")
        print(f"  GET /:   {'OK' if r['root_ok'] else 'FAIL'}")
        print(f"  POST webhook: {'OK' if r['webhook_ok'] else 'FAIL'}")
        print(f"  Score:   {score}")

        if r["notes"]:
            for note in r["notes"][:4]:
                print(f"   - {note}")

    valid = [r for r in results if r["webhook_ok"]]
    if valid:
        best = valid[0]
        print("\n" + "-" * 80)
        ok(f"Melhor URL para usar no WAHA agora:")
        print(f"http://{best['host']}:{PORT}{WEBHOOK_PATH}")
    else:
        print("\n" + "-" * 80)
        fail("Nenhum host passou no teste completo do webhook.")
        print("Revise:")
        print("- sua API está rodando?")
        print("- a rota /webhook/waha existe?")
        print("- a rota aceita POST?")
        print("- o firewall do Windows está liberando a porta 8000?")


def main() -> int:
    print("=" * 80)
    print("DIAGNÓSTICO DE WEBHOOK WAHA -> API PYTHON")
    print("=" * 80)
    print(f"Porta alvo: {PORT}")
    print(f"Webhook path: {WEBHOOK_PATH}")
    print()

    results = []
    for host in CANDIDATES:
        results.append(test_candidate(host))
        print("-" * 80)

    print_summary(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())