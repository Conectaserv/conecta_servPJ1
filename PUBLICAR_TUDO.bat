@echo off
chcp 65001 >nul
title ConectaServ - Publicar no GitHub
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBLICAR_TUDO.ps1"
pause
