@echo off
setlocal
set "LOCAL_PY=%~dp0.venv\Scripts\python.exe"
if exist "%LOCAL_PY%" (
  "%LOCAL_PY%" -m awscli %*
) else (
  python -m awscli %*
)
