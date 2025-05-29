@echo off
chcp 65001 >nul
set HOST=127.0.0.1
set PORT=7860

echo Хотите установить необходимые зависимости? (Y/N)
set /p installDeps=

if /I "%installDeps%"=="Y" (
    echo Установка необходимых зависимостей...
    python -m pip install --upgrade pip
    python -m pip install fastapi uvicorn jinja2 asyncssh

    if %ERRORLEVEL% neq 0 (
        echo Ошибка при установке зависимостей
        pause
        exit /b %ERRORLEVEL%
    )
) else (
    echo Пропущена установка зависимостей.
)

echo.
echo Хотите запустить веб-приложение? (Y/N)
set /p runApp=

if /I "%runApp%"=="Y" (
    echo Запуск FastAPI на http://%HOST%:%PORT%
    python -m uvicorn app:app --host %HOST% --port %PORT% --reload
) else (
    echo Запуск приложения отменён.
)

pause
