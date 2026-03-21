"""
scripts/build_electron.py
Script de build completo para gerar o instalador Electron + Python.

Execute na raiz do projeto:
    python scripts/build_electron.py

O que faz:
  1. Baixa o Python embeddable (sem instalação) para python-dist/
  2. Instala as dependências do projeto no Python embeddable
  3. Copia o backend para python-dist/
  4. Roda npm install + electron-builder para gerar o .exe instalador
"""

import os
import sys
import stat
import shutil
import subprocess
import urllib.request
import zipfile


def force_remove(path):
    """Remove diretório mesmo com arquivos somente-leitura (necessário no Windows)."""
    def on_error(func, fpath, exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass
    shutil.rmtree(path, onerror=on_error)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIST = os.path.join(ROOT, 'python-dist')
PYTHON_EMBED_URL = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip'
PYTHON_EMBED_ZIP = os.path.join(PYTHON_DIST, 'python-embed.zip')
PYTHON_DIR = os.path.join(PYTHON_DIST, 'python')
GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'


def p(msg):
    print(f'\n  {msg}')


def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT)
    if result.returncode != 0:
        print(f'\n  ❌ Erro ao executar: {cmd}')
        sys.exit(1)


def step1_download_python():
    p('📥 Baixando Python embeddable 3.11...')
    os.makedirs(PYTHON_DIST, exist_ok=True)
    if not os.path.exists(PYTHON_EMBED_ZIP):
        urllib.request.urlretrieve(PYTHON_EMBED_URL, PYTHON_EMBED_ZIP)
    p('📦 Extraindo Python...')
    if os.path.exists(PYTHON_DIR):
        force_remove(PYTHON_DIR)
    os.makedirs(PYTHON_DIR)
    with zipfile.ZipFile(PYTHON_EMBED_ZIP, 'r') as z:
        z.extractall(PYTHON_DIR)

    # Habilitar importação de pacotes no Python embeddable
    pth_files = [f for f in os.listdir(PYTHON_DIR) if f.endswith('._pth')]
    for pth in pth_files:
        pth_path = os.path.join(PYTHON_DIR, pth)
        with open(pth_path, 'r') as f:
            content = f.read()
        # Descomentar import site
        content = content.replace('#import site', 'import site')
        with open(pth_path, 'w') as f:
            f.write(content)
    p('✅ Python embeddable pronto')


def step2_install_pip():
    p('📥 Instalando pip no Python embeddable...')
    get_pip = os.path.join(PYTHON_DIR, 'get-pip.py')
    urllib.request.urlretrieve(GET_PIP_URL, get_pip)
    python_exe = os.path.join(PYTHON_DIR, 'python.exe')
    run(f'"{python_exe}" get-pip.py', cwd=PYTHON_DIR)
    os.remove(get_pip)
    p('✅ pip instalado')


def step3_install_deps():
    p('📦 Instalando dependências no Python embeddable...')
    python_exe = os.path.join(PYTHON_DIR, 'python.exe')
    pip_exe = os.path.join(PYTHON_DIR, 'Scripts', 'pip.exe')
    deps = ['fastapi', 'uvicorn', 'segno', 'reportlab']
    run(f'"{pip_exe}" install {" ".join(deps)} --no-warn-script-location', cwd=PYTHON_DIR)
    p('✅ Dependências instaladas')


def step4_copy_backend():
    p('📁 Copiando backend para python-dist...')
    # Copiar run.py
    shutil.copy(os.path.join(ROOT, 'run.py'), os.path.join(PYTHON_DIST, 'run.py'))
    # Copiar pasta app/
    app_dst = os.path.join(PYTHON_DIST, 'app')
    if os.path.exists(app_dst):
        force_remove(app_dst)
    shutil.copytree(os.path.join(ROOT, 'app'), app_dst)
    # Copiar frontend/
    fe_dst = os.path.join(PYTHON_DIST, 'frontend')
    if os.path.exists(fe_dst):
        force_remove(fe_dst)
    shutil.copytree(os.path.join(ROOT, 'frontend'), fe_dst)
    p('✅ Backend copiado')


def step5_npm_install():
    p('📦 Instalando dependências Node.js...')
    run('npm install', cwd=ROOT)
    p('✅ npm install concluído')


def step6_build_electron():
    p('🔨 Gerando instalador Electron...')
    run('npm run build:installer', cwd=ROOT)
    p('✅ Instalador gerado em dist-electron/')


def main():
    print('=' * 60)
    print('  Bellart ERP — Build Electron + Python')
    print('=' * 60)

    confirm = input('\n  Isso vai demorar alguns minutos. Continuar? [s/N] ').strip().lower()
    if confirm != 's':
        print('  Cancelado.')
        sys.exit(0)

    step1_download_python()
    step2_install_pip()
    step3_install_deps()
    step4_copy_backend()
    step5_npm_install()
    step6_build_electron()

    print('\n' + '=' * 60)
    print('  ✅ Build concluído!')
    print('  📁 Instalador em: dist-electron/')
    print('=' * 60)


if __name__ == '__main__':
    main()