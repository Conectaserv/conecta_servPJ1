# Inicia o servidor Flask e o ngrok em duas janelas separadas
# Use este script a partir da pasta do projeto.

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "Pasta oficial: $projectPath"
Write-Host "Banco HeidiSQL: $projectPath\database\conecta_serv.db"
Write-Host "Iniciando a aplicacao Flask..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectPath'; python app.py"

Start-Sleep -Seconds 2

Write-Host "Iniciando o túnel ngrok..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectPath'; ngrok http 5000"

Write-Host "Dois terminais foram abertos: um para Flask e outro para ngrok."
Write-Host "Copie o endereço HTTPS exibido no terminal do ngrok para compartilhar."