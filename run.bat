@echo off
REM Inicia o servidor local (mesmo comportamento que F5 no VS Code).
REM Use este ficheiro se o comando "python" abrir a Microsoft Store em vez do Python.
cd /d "%~dp0"
where py >nul 2>&1 && py -3 run.py %* && goto :eof
where python >nul 2>&1 && python run.py %* && goto :eof
echo Nao foi encontrado Python. Instale Python 3 ou use "py -3 run.py" nesta pasta.
pause
exit /b 1
