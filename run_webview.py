"""
run_webview.py — Bellart ERP
Abre o sistema como janela desktop (pywebview) em vez do navegador.
Execute:  python run_webview.py
"""

import configparser
import ctypes
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn
import webview

from app.main import app

PORT = 8765
HOST = "0.0.0.0"
LOCAL_URL = f"http://127.0.0.1:{PORT}/"
CONFIG_FILE = "data/bellart.ini"


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def get_config_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    path = get_config_path()
    if not os.path.exists(path):
        config["Network"] = {"mode": "server", "server_ip": "127.0.0.1"}
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                config.write(f)
        except Exception:
            pass
    else:
        config.read(path)
    return config


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------

def get_all_ips() -> list[str]:
    import socket
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# API exposta ao JS (pywebview)
# ---------------------------------------------------------------------------

class Api:
    def save_file_dialog(self, filename: str, content_base64: str) -> dict:
        import base64
        import tkinter as tk
        from tkinter import filedialog
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".pdf",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
                title="Salvar PDF de Etiquetas",
            )
            root.destroy()
            if file_path:
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(content_base64))
                return {"ok": True, "path": file_path}
            return {"ok": False, "reason": "cancelled"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Servidor uvicorn (thread daemon)
# ---------------------------------------------------------------------------

def run_server():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("[run_webview] Iniciando...")

    config = load_config()
    try:
        mode = config["Network"].get("mode", "server").strip().lower()
        server_ip = config["Network"].get("server_ip", "127.0.0.1").strip()
    except Exception:
        mode = "server"
        server_ip = "127.0.0.1"

    all_ips = get_all_ips()
    lan_ip = all_ips[0]

    if mode == "client":
        target_url = f"http://{server_ip}:{PORT}/"
        window_title = f"Bellart (Cliente → {server_ip})"
        print(f"=== MODO CLIENTE ===\nConectando a: {target_url}")
        if not is_up(target_url):
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Não foi possível conectar ao servidor em: {server_ip}\n\n"
                f"Verifique:\n"
                f"1. O Bellart está aberto no servidor.\n"
                f"2. O IP {server_ip} está correto.\n"
                f"3. Firewall/Antivírus não está bloqueando.",
                "Erro de Conexão — Bellart",
                0x10,
            )
    else:
        target_url = LOCAL_URL
        window_title = f"Bellart (Servidor) — IP: {lan_ip}"
        ip_list = "\n".join(f"  - {ip}" for ip in all_ips)
        print(f"=== MODO SERVIDOR ===\nIPs disponíveis:\n{ip_list}")

        if not is_up(LOCAL_URL):
            # Sempre sobe o servidor — não testa antes (evita timeout)
            print(f"[run_webview] Iniciando servidor em {LOCAL_URL}...")
            threading.Thread(target=run_server, daemon=True).start()

            deadline = time.time() + 20
            while time.time() < deadline:
                if is_up(LOCAL_URL):
                    print("[run_webview] Servidor pronto.")
                    break
                time.sleep(0.2)
            else:
                print("[run_webview] Aviso: servidor demorou a responder.")

    try:
        api = Api()
        webview.create_window(
            window_title,
            target_url,
            width=1200,
            height=800,
            text_select=True,
            js_api=api,
        )
        webview.start(debug=False)
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"Erro fatal:\n{e}", "Erro — Bellart", 0x10)


if __name__ == "__main__":
    main()