import threading
import time
import urllib.request
import urllib.error
import webview
import uvicorn
import webbrowser
import os
import sys
import configparser
from app_web import app, get_resource_path

PORT = 8765
HOST = '0.0.0.0'
LOCAL_URL = f'http://127.0.0.1:{PORT}/'
CONFIG_FILE = 'bellart.ini'

def get_config_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)

def load_config():
    config = configparser.ConfigParser()
    path = get_config_path()
    
    if not os.path.exists(path):
        config['Network'] = {
            'mode': 'server',
            'server_ip': '127.0.0.1'
        }
        try:
            with open(path, 'w') as f:
                config.write(f)
        except:
            pass # se não conseguir escrever, usa padrão
    else:
        config.read(path)
    
    return config

def get_all_ips():
    import socket
    ips = []
    # Tentativa 1: Conectar a um DNS externo (Google) para pegar a interface de saída padrão
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        best_ip = s.getsockname()[0]
        s.close()
        ips.append(best_ip)
    except:
        pass

    # Tentativa 2: Listar todas as interfaces via hostname
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith('127.') and ip not in ips:
                ips.append(ip)
    except:
        pass
    
    if not ips:
        ips = ['127.0.0.1']
    return ips

def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


class Api:
    def save_file_dialog(self, filename, content_base64):
        import base64
        import tkinter as tk
        from tkinter import filedialog
        
        try:
            root = tk.Tk()
            root.withdraw() # Esconde a janela principal do Tkinter
            root.attributes('-topmost', True) # Garante que o diálogo apareça na frente
            
            file_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".pdf",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
                title="Salvar PDF de Etiquetas"
            )
            
            root.destroy()
            
            if file_path:
                # Decodifica base64 e salva
                data = base64.b64decode(content_base64)
                with open(file_path, 'wb') as f:
                    f.write(data)
                return {'ok': True, 'path': file_path}
            else:
                return {'ok': False, 'reason': 'cancelled'}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

def run_server():
    # inicia servidor com nível de log reduzido
    uvicorn.run(app, host=HOST, port=PORT, log_level='warning')


def main():
    print('[run_webview] Iniciando...')
    
    # Carregar configuração
    config = load_config()
    try:
        mode = config['Network'].get('mode', 'server').strip().lower()
        server_ip = config['Network'].get('server_ip', '127.0.0.1').strip()
    except:
        mode = 'server'
        server_ip = '127.0.0.1'

    all_ips = get_all_ips()
    # Pega o primeiro IP como principal, mas lista todos
    lan_ip = all_ips[0]
    my_lan_url = f'http://{lan_ip}:{PORT}/'
    
    import ctypes
    
    if mode == 'client':
        # MODO CLIENTE: conecta ao IP configurado
        target_url = f'http://{server_ip}:{PORT}/'
        window_title = f'Bellart (Cliente Conectado a {server_ip})'
        print(f'=== MODO CLIENTE ===')
        print(f'Conectando ao servidor: {target_url}')
        
        # Verifica se o servidor está online
        if not is_up(target_url):
             msg = (f"ERRO DE CONEXÃO\n\n"
                    f"Não foi possível conectar ao servidor em: {server_ip}\n\n"
                    f"DICAS:\n"
                    f"1. Verifique se o Bellart está ABERTO no computador Servidor.\n"
                    f"2. Verifique se o IP {server_ip} está correto (olhe a mensagem no Servidor).\n"
                    f"3. Verifique se o Firewall/Antivirus não está bloqueando.\n\n"
                    f"O programa vai tentar abrir mesmo assim.")
             ctypes.windll.user32.MessageBoxW(0, msg, "Erro Conexão - Bellart", 0x10)
    else:
        # MODO SERVIDOR (Padrão): Inicia servidor local
        target_url = LOCAL_URL
        
        ip_list_str = "\n".join([f"- {ip}" for ip in all_ips])
        window_title = f'Bellart (Servidor) - IP: {lan_ip}'
        
        print('='*50)
        print(f'=== MODO SERVIDOR ===')
        print(f'Este computador é o SERVIDOR.')
        print(f'IPs disponíveis:\n{ip_list_str}')
        print('='*50)

        # Exibir Popup com o IP para o usuário (pois o console fica oculto no exe)
        try:
            msg = (f"MODO SERVIDOR\n\n"
                   f"O IP deste computador parece ser:\n{lan_ip}\n\n"
                   f"Outros IPs possíveis:\n{ip_list_str}\n\n"
                   f"Configure os clientes com um desses IPs.")
            
            # 0x40 = MB_ICONINFORMATION
            ctypes.windll.user32.MessageBoxW(0, msg, "Informação de Conexão - Bellart", 0x40)
        except:
            pass

        server_already_running = is_up(LOCAL_URL)
        if server_already_running:
            print(f'[run_webview] Servidor já está disponível em {LOCAL_URL}.')
        else:
            print(f'[run_webview] Iniciando servidor em {LOCAL_URL}...')
            t = threading.Thread(target=run_server, daemon=True)
            t.start()
            start = time.time()
            # aguarda o servidor ficar disponível antes de abrir a janela
            while time.time() - start < 20:
                if is_up(LOCAL_URL):
                    print('[run_webview] Servidor disponível. Abrindo janela...')
                    break
                time.sleep(0.2)
            if not is_up(LOCAL_URL):
                print('[run_webview] Aviso: servidor não respondeu no tempo esperado. A janela pode abrir em branco.')

    try:
        # debug=True enables the developer tools (F12 or right click)
        api = Api()
        webview.create_window(window_title, target_url, width=1200, height=800, text_select=True, js_api=api)
        webview.start(debug=False)
    except Exception as e:
        import ctypes
        error_msg = f"Erro fatal ao iniciar Bellart:\n{e}"
        ctypes.windll.user32.MessageBoxW(0, error_msg, "Erro Bellart", 0x10)


if __name__ == '__main__':
    main()
