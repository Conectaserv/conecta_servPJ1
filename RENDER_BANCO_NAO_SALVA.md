# Por que cadastros novos “somem” no Render (plano grátis)

## O problema (não é bug do seu código)

No **Render Free**, o disco do servidor é **temporário**. O arquivo `conecta_serv.db` **perde alterações** quando:

- o site fica **15 minutos sem visitas** e “dorme”;
- o Render **reinicia** o serviço;
- você faz um **novo deploy**.

O cadastro até **parece** que funcionou (mensagem de sucesso), mas depois o servidor volta com a cópia **antiga** do banco que veio do GitHub no último deploy.

Por isso, depois de entregar o projeto, logins novos **não ficam salvos** no site online.

---

## Solução recomendada: disco persistente (Render pago)

Custo aproximado: plano **Starter** do Web Service + disco pequeno (alguns dólares/mês).

### Passo a passo no Render

1. Dashboard → serviço **conecta-servpj1** (ou o seu nome)
2. **Settings** → **Instance Type** → mude de **Free** para **Starter** (pago)
3. Ainda em **Settings** → **Disks** → **Add disk**
   - **Mount path:** `/var/data`
   - **Size:** 1 GB (mínimo)
4. **Environment** → adicione:

   | Key | Value |
   |-----|--------|
   | `DATABASE_PATH` | `/var/data/conecta_serv.db` |

5. **Manual Deploy** → Deploy latest commit (com o código novo que lê `DATABASE_PATH`)

Na primeira subida, o sistema **copia** o `conecta_serv.db` do GitHub para `/var/data/`. Depois disso, **todos os cadastros novos ficam gravados** nesse disco.

### Atualizar o banco com dados do seu PC (uma vez)

Se você tem cadastros só no PC:

1. No GitHub Desktop: commit + push de `database/conecta_serv.db` (Desktop)
2. Deploy no Render
3. Se o disco persistente já existia vazio, apague o serviço de disco e redeploy, **ou** peça suporte — o mais simples é deploy **depois** de adicionar o disco, com o `.db` já atualizado no GitHub.

---

## Alternativa sem pagar Render

| Opção | Observação |
|--------|------------|
| Só testar no **PC** (`python app.py`) | Banco em `Desktop\...\database\conecta_serv.db` |
| **Postgres** gratuito (Neon, Supabase) | Exige adaptar o código (não está pronto hoje) |
| Após cada teste: **push do .db** + deploy | Funciona, mas é manual e fácil esquecer |

---

## O que mudou no código

- `database/database.py` lê `DATABASE_PATH` do ambiente.
- Com disco em `/var/data`, os cadastros **persistem** após reinício.

---

## Resumo para o TCC / entrega

- Site no ar: **https://conecta-servpj1.onrender.com**
- Plano **grátis**: bom para **demonstração**, ruim para **produção com cadastros reais**.
- Para o professor/usuários cadastrarem de verdade: **Starter + disco** ou banco **Postgres**.
