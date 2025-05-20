@echo off
set HOST=127.0.0.1
set PORT=7860

echo Установка необходимых зависимостей...
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn jinja2 asyncssh

if %ERRORLEVEL% neq 0 (
    echo Ошибка при установке зависимостей
    pause
    exit /b %ERRORLEVEL%
)

echo Запуск FastAPI на http://%HOST%:%PORT%
python -m uvicorn app:app --host %HOST% --port %PORT% --reload

pause
