@echo off
TITLE Configurando Firewall para Bellart
echo ========================================================
echo   LIBERANDO PORTA 8765 NO FIREWALL DO WINDOWS
echo ========================================================
echo.
echo Este script deve ser executado como ADMINISTRADOR.
echo.
echo Verificando regras existentes...
netsh advfirewall firewall show rule name="Bellart Server" >nul
if not errorlevel 1 (
    echo A regra "Bellart Server" ja existe. Removendo para recriar e garantir que esta correta...
    netsh advfirewall firewall delete rule name="Bellart Server"
)

echo Adicionando regra de entrada TCP na porta 8765...
netsh advfirewall firewall add rule name="Bellart Server" dir=in action=allow protocol=TCP localport=8765

echo.
if %errorlevel% EQU 0 (
    echo SUCESSO! O Firewall foi configurado.
    echo Agora os outros computadores devem conseguir conectar.
) else (
    echo ERRO! Falha ao configurar o firewall.
    echo Verifique se voce clicou com o botao direito e escolheu "Executar como administrador".
)
echo.
pause
