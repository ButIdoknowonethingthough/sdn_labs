@echo off
set HOST=127.0.0.1
set PORT=7860

echo Запуск FastAPI на http://%HOST%:%PORT%
python -m uvicorn app:app --host %HOST% --port %PORT%

pause