import sqlite3
import os
import shutil
import time
import sys

# Tenta importar configurações do db.py
try:
    from db import BASE_DIR, init_db, migrate_ml_split
except ImportError:
    # Fallback se rodar fora do ambiente normal
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    def init_db(conn): pass
    def migrate_ml_split(conn): pass

CURRENT_DB = os.path.join(BASE_DIR, 'bellart.db')
BACKUP_DB = os.path.join(BASE_DIR, f'bellart_antes_importacao_{int(time.time())}.db')

def main():
    print("=== FERRAMENTA DE IMPORTAÇÃO DE DADOS BELLART (MÉTODO SEGURO) ===")
    print("Este script substitui o banco atual pelo banco antigo e atualiza a estrutura.")
    print("-" * 50)

    # 1. Encontrar o arquivo de origem
    source_db = None
    candidates = ['banco_externo.db', 'bellart_antigo.db', 'importar.db']
    
    # Se passado via argumento (arrastar e soltar)
    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]) and sys.argv[1].endswith('.db'):
            source_db = sys.argv[1]

    if not source_db:
        for c in candidates:
            p = os.path.join(BASE_DIR, c)
            if os.path.exists(p):
                source_db = p
                break
    
    if not source_db:
        print("ERRO: Nenhum banco de dados encontrado para importar.")
        print("Por favor, coloque o arquivo do outro computador nesta pasta")
        print("e renomeie-o para 'banco_externo.db', ou arraste o arquivo sobre este script.")
        input("Pressione ENTER para sair...")
        return

    print(f"Fonte de dados encontrada: {source_db}")
    
    # 2. Backup do banco atual
    if os.path.exists(CURRENT_DB):
        print(f"Criando backup do banco atual em: {os.path.basename(BACKUP_DB)}...")
        shutil.copy(CURRENT_DB, BACKUP_DB)
    else:
        print("Banco atual não existe, será criado um novo.")

    # 3. Substituição e Migração
    try:
        confirm = input("ATENÇÃO: O banco atual será SUBSTITUÍDO pelo arquivo importado. Continuar? (S/N): ")
        if confirm.lower() != 's':
            print("Operação cancelada.")
            return

        print("Substituindo arquivo do banco de dados...")
        # Fechar qualquer conexão pendente (se houver, mas aqui estamos em script isolado)
        if os.path.exists(CURRENT_DB):
            os.remove(CURRENT_DB)
        shutil.copy(source_db, CURRENT_DB)
        
        print("Atualizando estrutura do banco de dados (Migração)...")
        conn = sqlite3.connect(CURRENT_DB)
        
        # Executa as rotinas de inicialização e migração do db.py
        # Isso cria colunas faltantes (ml_mode, unidade, etc) e tabelas faltantes
        # sem apagar os dados existentes.
        init_db(conn)
        
        # Executa migração específica do Mercado Livre (split Classico/Premium)
        migrate_ml_split(conn)
        
        conn.close()
        
        print("\nSUCESSO! Banco de dados atualizado e estruturado.")
        
        # 4. Importação de Fotos (Uploads)
        print("-" * 50)
        print("Verificando fotos e imagens...")
        
        # Tenta achar a pasta 'web/uploads' ou 'uploads' ao lado do banco de origem
        src_dir = os.path.dirname(source_db)
        src_uploads = os.path.join(src_dir, 'web', 'uploads')
        if not os.path.exists(src_uploads):
            src_uploads = os.path.join(src_dir, 'uploads')
        
        # Destino correto (conforme app_web.py e db.py)
        real_dest_uploads = os.path.join(BASE_DIR, 'uploads')
        
        if os.path.exists(src_uploads):
            print(f"Pasta de imagens encontrada em: {src_uploads}")
            if not os.path.exists(real_dest_uploads):
                os.makedirs(real_dest_uploads)
            
            count_imgs = 0
            for item in os.listdir(src_uploads):
                s = os.path.join(src_uploads, item)
                d = os.path.join(real_dest_uploads, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
                    count_imgs += 1
            print(f"Importadas {count_imgs} imagens para {real_dest_uploads}.")
        else:
            print("AVISO: Pasta de imagens (uploads) não encontrada junto ao banco de origem.")
            print("As fotos dos produtos podem não aparecer.")
            print("Certifique-se de copiar a pasta 'uploads' ou 'web/uploads' do outro computador para cá.")

        print("-" * 50)
        print("Backup de segurança salvo em:", os.path.basename(BACKUP_DB))

    except Exception as e:
        print(f"\nERRO CRÍTICO DURANTE MIGRAÇÃO: {e}")
        import traceback
        traceback.print_exc()
        print("Tente restaurar o backup se algo deu errado.")

    input("\nPressione ENTER para encerrar.")

if __name__ == '__main__':
    main()
