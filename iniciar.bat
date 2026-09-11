@echo off
title Controle Financeiro
cd /d "%~dp0"
echo ========================================================
echo       INICIANDO SISTEMA DE CONTROLE FINANCEIRO
echo ========================================================
echo Acessivel no navegador em: http://127.0.0.1:5000
echo Pressione CTRL+C na janela para encerrar.
echo.
venv\Scripts\python.exe app.py
pause
