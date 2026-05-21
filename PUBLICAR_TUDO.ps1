# ConectaServ — prepara Git e envia para GitHub (pastas corretas)
$ErrorActionPreference = "Stop"
$Pasta = $PSScriptRoot
Set-Location $Pasta

$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) {
    $git = (Get-Command git -ErrorAction SilentlyContinue).Source
}
if (-not $git) {
    Write-Host "Git nao encontrado. Execute de novo apos instalar o Git." -ForegroundColor Red
    exit 1
}

Write-Host "=== ConectaServ — publicar no GitHub ===" -ForegroundColor Cyan
Write-Host "Pasta: $Pasta`n"

# Atualizar .gitignore
@'
.env
.secret_key
__pycache__/
*.pyc
venv/
.venv/
database/*.db-journal
database/*.db-wal
database/*.db-shm
*.backup*
*.msi
test_*.py
check_*.py
temp_app.py
app_broken.py
dashboard_*_output.html
'@ | Set-Content -Path (Join-Path $Pasta ".gitignore") -Encoding UTF8

if (-not (Test-Path (Join-Path $Pasta ".git"))) {
    & $git init
    & $git branch -M main
}

& $git add app.py wsgi.py textos_pt.py requirements.txt render.yaml .gitignore .env.example
& $git add templates static database utils deploy
& $git add DEPLOY_*.md PASSO_A_PASSO_RENDER.md PUBLICAR_TUDO.ps1 PUBLICAR_TUDO.bat subir_github.ps1 2>$null

& $git reset HEAD .env .secret_key 2>$null
Get-ChildItem database -Filter "*.backup*" -ErrorAction SilentlyContinue | ForEach-Object { & $git reset HEAD $_.FullName 2>$null }
Get-ChildItem database -Filter "*.msi" -ErrorAction SilentlyContinue | ForEach-Object { & $git reset HEAD $_.FullName 2>$null }

$status = & $git status --porcelain
if ($status) {
    & $git -c user.email="conectaserv@local" -c user.name="ConectaServ" commit -m "ConectaServ: projeto completo para Render"
    Write-Host "`nCommit OK — pastas templates/, static/, database/, utils/" -ForegroundColor Green
} else {
    Write-Host "`nRepositorio ja commitado (sem mudancas novas)." -ForegroundColor Yellow
}

Write-Host "`n--- Estrutura que vai para o GitHub ---" -ForegroundColor Cyan
& $git ls-files | Select-Object -First 40
$total = (& $git ls-files | Measure-Object).Count
Write-Host "... total: $total arquivos`n"

$usuario = Read-Host "Digite seu usuario do GitHub (ex: gabriel123)"
if (-not $usuario.Trim()) {
    Write-Host "Cancelado — rode o script de novo com o usuario." -ForegroundColor Yellow
    exit 0
}

$remoteUrl = "https://github.com/$($usuario.Trim())/conectaserv.git"
$remotes = & $git remote 2>$null
if ($remotes -contains "origin") {
    & $git remote set-url origin $remoteUrl
} else {
    & $git remote add origin $remoteUrl
}

Write-Host "`nEnviando para: $remoteUrl" -ForegroundColor Cyan
Write-Host "O navegador pode abrir para voce fazer LOGIN no GitHub (uma vez).`n"

& $git push -u origin main 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSe falhou:" -ForegroundColor Yellow
    Write-Host "1) Crie o repositorio vazio no GitHub: https://github.com/new"
    Write-Host "   Nome: conectaserv   (sem README)"
    Write-Host "2) Rode este arquivo de novo: PUBLICAR_TUDO.bat"
    Write-Host "`nOU instale GitHub Desktop e clique Publish:"
    Write-Host "https://desktop.github.com"
    exit 1
}

Write-Host "`n=== SUCESSO no GitHub! ===" -ForegroundColor Green
Write-Host "Abra: https://github.com/$($usuario.Trim())/conectaserv"
Write-Host "`nProximo: Render.com -> New Web Service -> repo conectaserv"
Write-Host "Start Command: gunicorn --bind 0.0.0.0:`$PORT wsgi:application"
Write-Host "Variavel SECRET_KEY no painel do Render (veja PASSO_A_PASSO_RENDER.md)"
