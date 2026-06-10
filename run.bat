@echo off
REM Inicia o servidor local em http://127.0.0.1:5055/login (porta configurável no .env).
REM Duplo-clique neste ficheiro ou use F5 no VS Code.
REM Nao feche esta janela enquanto usa o site — fechar = ERR_CONNECTION_REFUSED nas abas.
cd /d "%~dp0"
if not exist "backend\requirements.txt" (
  echo ERRO: execute este ficheiro na pasta raiz do projeto ^(onde esta run.bat^).
  pause
  exit /b 1
)
set HOST=127.0.0.1
set PORT=5055
set FLASK_RELOADER=0
set FLASK_DEBUG=1
set OPEN_BROWSER=1
where py >nul 2>&1 && set PYRUN=py -3
if not defined PYRUN where python >nul 2>&1 && set PYRUN=python
if not defined PYRUN (
  echo Nao foi encontrado Python. Instale Python 3.11+.
  pause
  exit /b 1
)
%PYRUN% -c "import flask" 2>nul || (
  echo Instalando dependencias...
  %PYRUN% -m pip install -r "backend\requirements.txt"
  if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
  )
)
%PYRUN% run.py %*
if errorlevel 1 pause
exit /b %ERRORLEVEL%
