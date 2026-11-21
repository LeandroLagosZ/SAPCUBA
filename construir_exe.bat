@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  Construyendo SAPCUBA.exe  -  Sistema de Apertura de Cuentas
echo ============================================================
echo.

set "PY_CMD="
set "VENV="
py -3.12 --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3.12"
  set "VENV=.venv-build-py312"
)
if not defined PY_CMD (
  py -3.13 --version >nul 2>nul
  if not errorlevel 1 (
    set "PY_CMD=py -3.13"
    set "VENV=.venv-build-py313"
  )
)
if not defined PY_CMD (
  echo No se encontro Python 3.12 ni 3.13 de 64 bits.
  echo Python 3.14 no es compatible con psycopg2-binary 2.9.10.
  echo Instala Python 3.12 de 64 bits y vuelve a ejecutar este archivo.
  goto :error
)

if not exist "%VENV%\Scripts\python.exe" (
  %PY_CMD% -m venv "%VENV%" || goto :error
)
call "%VENV%\Scripts\activate.bat" || goto :error
python -m pip install --upgrade pip >nul || goto :error
python -m pip install -r backend\requirements.txt pyinstaller || goto :error

echo.
echo [1/2] Descargando PostgreSQL portatil (solo la primera vez)...
python scripts\obtener_postgres.py || goto :error

echo.
echo [2/2] Creando SAPCUBA.exe ...
pyinstaller --noconfirm --clean --onefile --noconsole --name SAPCUBA --icon recursos\sapcuba.ico ^
  --version-file recursos\version.txt ^
  --paths backend ^
  --add-data "frontend;frontend" --add-data "db;db" --add-data "pginstall;pginstall" ^
  backend\sapcuba.py || goto :error

if not exist salida mkdir salida
copy /y dist\SAPCUBA.exe salida\ >nul

echo.
echo ============================================================
echo  LISTO:  salida\SAPCUBA.exe
echo  Doble clic para usarlo. No necesita instalar nada mas.
echo ============================================================
pause
exit /b 0

:error
echo.
echo OCURRIO UN ERROR. 
pause
exit /b 1
