# ConectaServ — plano básico Hostinger (hospedagem compartilhada)

## Situação

A **hospedagem compartilhada básica** da Hostinger é feita para **WordPress, PHP e sites estáticos**.

O ConectaServ é **Python + Flask + SQLite**. Esse tipo de site **não roda** nesse plano, mesmo enviando todos os arquivos para `public_html`.

Ou seja: subir `app.py`, `templates`, etc. **não vai abrir o site** — o servidor não executa Flask como no seu PC.

---

## Suas opções (da mais barata à que fica na Hostinger)

### Opção 1 — Render.com (recomendado para orçamento zero/baixo)

- Tem plano **gratuito** para testes e demonstração.
- Suporta Flask.
- Você mantém a Hostinger só para **domínio** (opcional) ou usa o link `*.onrender.com`.

Guia: veja `DEPLOY_RENDER.md` nesta pasta.

**Prós:** barato, fácil, não precisa VPS.  
**Contras:** no gratuito o site “dorme” após inatividade; SQLite precisa de cuidado (backup).

---

### Opção 2 — PythonAnywhere (grátis para começar)

- Plano free permite **um** app Flask pequeno.
- Site: https://www.pythonanywhere.com

**Prós:** feito para Python.  
**Contras:** domínio próprio só em plano pago; limites de tráfego no free.

---

### Opção 3 — Upgrade na Hostinger para **VPS**

- É o único plano Hostinger em que Flask funciona de verdade.
- Guia: `DEPLOY_HOSTINGER.md`

**Prós:** tudo na mesma empresa, controle total.  
**Contras:** custo mensal maior que o plano básico (geralmente a partir de ~R$ 30–40/mês).

---

### Opção 4 — Manter ngrok só para apresentar

- O que você já faz com `python app.py` + ngrok.
- Serve para **mostrar o TCC/trabalho**, não para site 24h profissional.

---

## O que fazer com os arquivos que você já enviou na Hostinger

Na hospedagem compartilhada você pode:

1. **Deixar uma página simples** em `public_html/index.html` explicando: “Em breve” ou link para o site no Render.
2. **Usar o domínio** apontando para o Render (CNAME), se quiser URL bonita.
3. **Não apagar** o plano se usar só o domínio/e-mail — ou cancelar depois se não precisar.

---

## Resumo

| Onde | ConectaServ funciona? |
|------|------------------------|
| Hostinger básico (compartilhado) | Não |
| Hostinger VPS | Sim |
| Render / PythonAnywhere | Sim |
| Seu PC + ngrok | Sim (temporário) |

**Próximo passo sugerido:** seguir `DEPLOY_RENDER.md` (grátis) ou contratar **VPS** na Hostinger se quiser tudo lá.
