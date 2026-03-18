import os
import zipfile
import sys
import io

# Tenta importar configurações para pegar os caminhos corretos
try:
    from db import BASE_DIR
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
except ImportError:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

def verificar_backup():
    print("=== VERIFICADOR DE INTEGRIDADE DE BACKUP ===")
    print(f"Diretório Base: {BASE_DIR}")
    print(f"Diretório Uploads: {UPLOAD_DIR}")
    print("-" * 50)

    db_path = os.path.join(BASE_DIR, 'bellart.db')
    
    # 1. Verificar existência dos arquivos originais
    print("1. Verificando arquivos no disco:")
    if os.path.exists(db_path):
        size = os.path.getsize(db_path) / 1024
        print(f"   [OK] Banco de dados encontrado ({size:.2f} KB)")
    else:
        print("   [ERRO] Banco de dados NÃO encontrado!")
    
    files_count = 0
    if os.path.exists(UPLOAD_DIR):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            files_count += len(files)
        print(f"   [OK] Pasta de uploads encontrada com {files_count} arquivos.")
    else:
        print("   [AVISO] Pasta de uploads não existe (nenhuma foto salva?).")

    print("-" * 50)

    # 2. Simular Criação do ZIP
    print("2. Simulando criação do arquivo de Backup...")
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            # Adiciona DB
            if os.path.exists(db_path):
                z.write(db_path, arcname='bellart.db')
            
            # Adiciona Uploads
            if os.path.isdir(UPLOAD_DIR):
                for root, dirs, files in os.walk(UPLOAD_DIR):
                    for f in files:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, UPLOAD_DIR)
                        z.write(full, arcname=os.path.join('uploads', rel))
        
        # 3. Analisar o ZIP gerado
        print("3. Analisando conteúdo do ZIP gerado:")
        zip_size = buf.tell() / 1024
        buf.seek(0)
        
        with zipfile.ZipFile(buf, 'r') as z:
            names = z.namelist()
            has_db = 'bellart.db' in names
            uploads_in_zip = [n for n in names if n.startswith('uploads/')]
            
            if has_db:
                print("   [OK] bellart.db está presente no arquivo.")
            else:
                print("   [ERRO] bellart.db NÃO está no arquivo!")
                
            print(f"   [INFO] Total de arquivos de upload no ZIP: {len(uploads_in_zip)}")
            
            if len(uploads_in_zip) == files_count:
                print("   [OK] Contagem de arquivos de upload bate com o disco.")
            else:
                print(f"   [ALERTA] Diferença na contagem de arquivos (Disco: {files_count} vs ZIP: {len(uploads_in_zip)})")

        print("-" * 50)
        print(f"RESULTADO: O backup gerado teria {zip_size:.2f} KB.")
        
        if has_db and (files_count == 0 or len(uploads_in_zip) > 0):
            print("CONCLUSÃO: O sistema de backup está pronto e seguro.")
        else:
            print("CONCLUSÃO: Há problemas potenciais no backup. Verifique os erros acima.")

    except Exception as e:
        print(f"ERRO CRÍTICO AO TESTAR BACKUP: {e}")
        import traceback
        traceback.print_exc()

    input("\nPressione ENTER para sair.")

if __name__ == '__main__':
    verificar_backup()
