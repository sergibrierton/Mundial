@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   MUNDIAL STUDIO
echo ============================================================
echo.

REM --- Buscar Python ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [ERROR] No se ha encontrado Python.
  echo.
  echo   Instalalo desde:  https://www.python.org/downloads/
  echo   IMPORTANTE: marca la casilla "Add Python to PATH" al instalar.
  echo.
  pause
  exit /b 1
)

REM --- Crear entorno virtual la primera vez ---
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Creando entorno ^(solo la primera vez^)...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [ERROR] No se pudo crear el entorno. & pause & exit /b 1 )
)

call ".venv\Scripts\activate.bat"

REM --- Instalar dependencias la primera vez ---
if not exist ".venv\.instalado" (
  echo [2/2] Instalando dependencias ^(puede tardar unos minutos^)...
  python -m pip install --upgrade pip >nul
  pip install -r requirements.txt
  if errorlevel 1 ( echo [ERROR] Fallo la instalacion de dependencias. & pause & exit /b 1 )
  echo ok> ".venv\.instalado"
  echo.
  echo   Dependencias instaladas correctamente.
  echo.
)

echo Abriendo Mundial Studio en el navegador...
echo (para cerrar, cierra esta ventana)
echo.
python app.py

pause
