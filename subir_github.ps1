# ConectaServ — envia o projeto para o GitHub com pastas corretas
# Uso: clique com botao direito -> Executar com PowerShell
# Ou no PowerShell: cd pasta do projeto; .\subir_github.ps1

$ErrorActionPreference = "Stop"
$pasta = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $pasta

Write-Host "Pasta do projeto: $pasta" -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git nao instalado. Instale: https://git-scm.com/download/win" -ForegroundColor Red
    Write-Host "Depois execute este script de novo."
    pause
    exit 1
}

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

git add app.py wsgi.py textos_pt.py requirements.txt render.yaml .gitignore .env.example
git add templates static database utils deploy
git add DEPLOY_*.md PASSO_A_PASSO_RENDER.md 2>$null

# Nao enviar segredos nem lixo
git reset HEAD .env .secret_key 2>$null
git reset HEAD database/*.backup* database/*.db-shm database/*.db-wal 2>$null

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nada novo para enviar (ja esta commitado?)." -ForegroundColor Yellow
} else {
    git commit -m "ConectaServ - estrutura para deploy Render"
    Write-Host "Commit criado com pastas templates/, static/, database/, utils/" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== PROXIMO PASSO (copie a URL do SEU repositorio no GitHub) ===" -ForegroundColor Yellow
Write-Host ""
Write-Host 'git remote add origin https://github.com/SEU_USUARIO/conectaserv.git'
Write-Host "git push -u origin main"
Write-Host ""
Write-Host "Troque SEU_USUARIO pelo seu login do GitHub."
Write-Host "Na primeira vez o GitHub pede login (navegador ou token)."
Write-Host ""
pause
