# Publicar ConectaServ no Render (plano gratuito)

Funciona com **hospedagem compartilhada Hostinger básica** no bolso: o site roda no Render; a Hostinger pode ficar só com domínio depois.

---

## 1. Preparar conta

1. Crie conta em https://render.com  
2. (Opcional) Conta no GitHub para deploy automático.

---

## 2. Subir o código no GitHub (recomendado)

No seu PC, na pasta do projeto:

```powershell
cd "C:\Users\Gabriel_0)\Desktop\conecta_servPJ1"
git init
git add app.py wsgi.py textos_pt.py requirements.txt templates static database utils deploy .gitignore .env.example DEPLOY_*.md
git commit -m "ConectaServ para deploy"
```

Crie repositório no GitHub (privado ou público) e:

```powershell
git remote add origin https://github.com/SEU_USUARIO/conectaserv.git
git push -u origin main
```

**Não** commite `.env`, `.secret_key` nem `conecta_serv.db` com dados sensíveis se o repo for público.

Para levar o banco com cadastros em repo **privado**, pode incluir `database/conecta_serv.db` no commit.

---

## 3. Criar Web Service no Render

1. Dashboard → **New +** → **Web Service**  
2. Conecte o repositório GitHub do projeto  
3. Configuração:

| Campo | Valor |
|--------|--------|
| Name | `conectaserv` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --bind 0.0.0.0:$PORT wsgi:application` |
| Instance type | **Free** |

4. **Environment Variables** (Environment):

| Key | Value |
|-----|--------|
| `SECRET_KEY` | gere uma chave longa (igual no `.env.example`) |
| `FLASK_ENV` | `production` |
| `PYTHON_VERSION` | `3.11.0` (ou 3.12) |

SMTP (opcional, para e-mails):

```
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=587
SMTP_USER=email@seudominio.com
SMTP_PASS=...
SMTP_FROM=noreply@seudominio.com
SMTP_TLS=1
```

5. **Create Web Service** — aguarde o build (5–15 min na primeira vez).

6. URL final: `https://conectaserv.onrender.com` (ou o nome que escolheu).

---

## 4. Banco SQLite no Render (importante)

No plano **grátis**, o disco pode ser **apagado** em alguns redeploys.

- Para **teste/TCC:** aceitável; faça backup do `.db` no PC.  
- Para **produção séria:** use VPS Hostinger ou plano pago Render com disco persistente / PostgreSQL.

Após o primeiro deploy, teste cadastro e login. Se o banco sumir após redeploy, envie de novo `conecta_serv.db` ou rode migração.

---

## 5. Usar seu domínio da Hostinger no Render

No painel Render → seu serviço → **Settings** → **Custom Domains** → adicione `www.seudominio.com`.

Na Hostinger (DNS do domínio):

- Tipo **CNAME**  
- Nome: `www`  
- Aponta para: o endereço que o Render mostrar (ex. `conectaserv.onrender.com`)

Para raiz `@`, a Hostinger costuma pedir registro **A** ou ALIAS — siga o que o Render indicar na tela.

---

## 6. Limitações do plano gratuito Render

- Site **hiberna** após ~15 min sem visitas → primeira abertura demora ~30–60 s.  
- HTTPS incluso.  
- Bom para entrega acadêmica e MVP.

---

## 7. Se preferir ficar 100% na Hostinger

Única forma: **upgrade para VPS** e seguir `DEPLOY_HOSTINGER.md`.

---

Dúvidas comuns: build falhou → veja **Logs** no Render; erro 502 → confira se `Start Command` é `gunicorn wsgi:application`.
