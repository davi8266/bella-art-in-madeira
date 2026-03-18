@echo off
echo Gerando executavel do Bellart...
echo.
pip install pyinstaller Pillow
python -c "from PIL import Image; Image.open('static/logo.png').save('static/logo.ico')"
pyinstaller --noconfirm --onefile --windowed --name "Bellart" --add-data "web;web" --add-data "static;static" --icon "static/logo.ico" run_webview.py
echo.
echo Executavel gerado com sucesso em dist/Bellart.exe
