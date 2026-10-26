@echo off
rem ---------------------------------------------------------------------------
rem  Construit Mue pour Windows :
rem    dist\Mue\Mue.exe            (version portable)
rem    dist\Mue-Setup-x.y.z.exe    (installeur, si Inno Setup 6 est installé)
rem  Prérequis : Python 3.11+ (python.org, case « Add to PATH » cochée).
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creation de l'environnement virtuel...
    %PY% -m venv .venv || goto :error
)
call ".venv\Scripts\activate.bat"

echo [2/5] Installation des dependances...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt pyinstaller || goto :error

echo [3/5] Recuperation de FFmpeg...
python tools\prepare_ffmpeg.py || goto :error

echo [4/5] Compilation avec PyInstaller...
pyinstaller --noconfirm --clean mue.spec || goto :error

echo [5/5] Installeur...
set "ISCC="
for %%I in (iscc.exe) do set "ISCC=%%~$PATH:I"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC (
    "%ISCC%" /Q installer.iss || goto :error
    echo.
    echo  OK : installeur dans dist\
) else (
    echo  Inno Setup 6 non trouve : pas d'installeur, mais la version portable est prete.
    echo  ^(https://jrsoftware.org/isdl.php pour generer Mue-Setup.exe^)
)
echo.
echo  Version portable : dist\Mue\Mue.exe  ^(lance-le puis "Ajouter au clic droit"^)
echo.
pause
exit /b 0

:error
echo.
echo  *** Echec de la construction ***
pause
exit /b 1
