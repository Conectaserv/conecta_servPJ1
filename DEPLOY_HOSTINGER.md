# Publicar o ConectaServ na Hostinger

O ConectaServ é um site **Flask + SQLite**. Na Hostinger isso funciona de forma confiável apenas em **VPS** (Ubuntu), não no plano de hospedagem compartilhada só para PHP/WordPress.

Documentação Hostinger: [Flask no Ubuntu (VPS)](https://www.hostinger.com/support/10725412-how-to-install-flask-on-ubuntu-24-04/)

---

## 1. Qual plano você precisa?

| Plano | ConectaServ |
|--------|-------------|
| Hospedagem compartilhada / WordPress | Não recomendado (sem Python/Flask estável) |
| **VPS Hostinger** | Sim — use este |

Se ainda não tiver VPS, contrate um na Hostinger (Ubuntu 22.04 ou 24.04).

---

## 2. O que enviar para o servidor

Envie a pasta do projeto **sem** arquivos sensíveis de desenvolvimento:

**Incluir:**
- `app.py`, `wsgi.py`, `textos_pt.py`, `requirements.txt`
- pasta `database/` (com `database.py` e, se quiser manter dados, `conecta_serv.db`)
- pasta `templates/`, `static/`, `utils/`

**Não enviar (criar no servidor):**
- `.env` — crie no VPS com `SECRET_KEY` e SMTP
- `.secret_key` — use só `SECRET_KEY` no `.env` em produção

**Opcional não enviar:** `test_*.py`, `check_*.py`, `temp_app.py`, `*.html` de teste na raiz.

---

## 3. Enviar arquivos (escolha um método)

### A) File Manager / FTP (hPanel do VPS)

1. No hPanel → VPS → **SSH/SFTP** ou **File Manager**
2. Crie `/var/www/conectaserv`
3. Envie o ZIP do projeto e extraia lá

### B) SFTP (FileZilla)

- Host: IP do VPS  
- Usuário/senha: do painel Hostinger  
- Pasta remota: `/var/www/conectaserv`

### C) Git (se usar repositório)

```bash
cd /var/www
sudo git clone SEU_REPOSITORIO conectaserv
sudo chown -R www-data:www-data conectaserv
```

---

## 4. Configurar no VPS (SSH)

Conecte por SSH (terminal do hPanel ou PuTTY):

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx

cd /var/www/conectaserv
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt

# Permissão para o SQLite gravar
sudo mkdir -p database
sudo chown -R www-data:www-data /var/www/conectaserv
sudo chmod -R 775 database
```

### Arquivo `.env` em produção

```bash
sudo nano /var/www/conectaserv/.env
```

Exemplo:

```env
SECRET_KEY=coloque_uma_chave_longa_aleatoria_aqui
FLASK_ENV=production

SMTP_HOST=smtp.hostinger.com
SMTP_PORT=587
SMTP_USER=email@seudominio.com
SMTP_PASS=senha_do_email
SMTP_FROM=noreply@seudominio.com
SMTP_TLS=1
```

Gere uma chave forte no PC: `python -c "import secrets; print(secrets.token_hex(32))"`

### Banco de dados

- Se enviou `database/conecta_serv.db` do seu PC, os cadastros vão junto.
- Se não enviou, na primeira execução o `inicializar_banco()` cria tabelas vazias.

---

## 5. Gunicorn + systemd (site sempre ligado)

```bash
sudo cp /var/www/conectaserv/deploy/conectaserv.service.example /etc/systemd/system/conectaserv.service
# Ajuste User/Group/caminhos se mudou a pasta

sudo systemctl daemon-reload
sudo systemctl enable conectaserv
sudo systemctl start conectaserv
sudo systemctl status conectaserv
```

Teste local no VPS:

```bash
curl -I http://127.0.0.1:8000
```

---

## 6. Nginx + domínio

```bash
sudo cp /var/www/conectaserv/deploy/nginx-conectaserv.conf.example /etc/nginx/sites-available/conectaserv
sudo nano /etc/nginx/sites-available/conectaserv
# Troque SEU_DOMINIO pelo domínio real

sudo ln -s /etc/nginx/sites-available/conectaserv /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

No **hPanel Hostinger** → Domínios → aponte o domínio para o **IP do VPS** (registro A).

SSL (HTTPS): no hPanel use **SSL** do domínio ou:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seudominio.com -d www.seudominio.com
```

---

## 7. Firewall

Na Hostinger VPS, libere portas **80** e **443** (painel de firewall do VPS).

---

## 8. Checklist pós-deploy

- [ ] Site abre em `https://seudominio.com`
- [ ] Login empresa/freelancer funciona
- [ ] Cadastro grava (pasta `database/` com permissão de escrita)
- [ ] Botão **Libras** / VLibras (precisa de internet no servidor e no visitante)
- [ ] E-mails de proposta (se configurou SMTP no `.env`)
- [ ] `SECRET_KEY` fixa no `.env` (senão usuários deslogam ao reiniciar)

---

## 9. Atualizar o site depois

```bash
cd /var/www/conectaserv
# envie arquivos novos ou git pull
sudo ./venv/bin/pip install -r requirements.txt
sudo systemctl restart conectaserv
```

**Importante:** faça backup de `database/conecta_serv.db` antes de cada atualização.

---

## 10. Problemas comuns

| Problema | Solução |
|----------|---------|
| 502 Bad Gateway | `sudo systemctl status conectaserv` — Gunicorn parado? |
| database is locked | Não abra o `.db` no HeidiSQL no servidor; reinicie o serviço |
| Sessão cai sempre | Defina `SECRET_KEY` no `.env` |
| CSS não carrega | Confira `location /static/` no Nginx |
| Só funciona no IP:5000 | Falta Nginx; não use `python app.py` em produção |

---

## 11. Alternativa sem VPS

Se você só tem hospedagem compartilhada, opções:

1. **Contratar VPS Hostinger** (recomendado para este projeto)
2. Usar **Render / Railway / PythonAnywhere** (outro provedor, também com guia parecido)
3. Manter **ngrok** só para demonstração (não é hospedagem definitiva)

---

Dúvidas: informe se seu plano é **VPS** ou **compartilhado** e o **domínio** (ex.: `conectaserv.com.br`) para ajustar os comandos exatos.
