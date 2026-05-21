# 🔧 GUIA DE USO - PROPOSTAS E MENSAGENS

## ✅ O QUE FOI CORRIGIDO

### 1. **PROPOSTAS APARECEM EM DOIS LUGARES:**

#### Para EMPRESAS:
- Acesse: **Dashboard → Menu → "Meus Projetos"** ou **"Propostas Recebidas"**
- Na seção "Propostas Recebidas" você verá uma tabela com:
  - Projeto
  - Freelancer que enviou
  - Texto da proposta
  - Valor proposto
  - Prazo
  - Status (pendente/aceita/rejeitada)

#### Para FREELANCERS:
- Acesse: **Dashboard → Menu → Seção "Minhas Propostas"**
- Você verá uma tabela com todas as propostas que enviou:
  - Projeto
  - Empresa
  - Seu valor proposto
  - Seu prazo
  - Status

### 2. **MENSAGENS FUNCIONANDO:**

#### Para ENVIAR uma mensagem:
1. Vá ao **Perfil do Freelancer**
2. Clique no botão **"Enviar Mensagem"**
3. Digite sua mensagem
4. Clique **"Enviar Mensagem"**

#### Para VER suas mensagens recebidas:
1. Acesse seu **Dashboard**
2. Clique no card **"Mensagens"**
3. Todas as mensagens recebidas aparecem nessa página

---

## 🔗 ROTAS PRINCIPAIS

| Função | URL |
|--------|-----|
| Dashboard Empresa | `/dashboard-empresa` |
| Dashboard Freelancer | `/dashboard-freelancer` |
| Inbox de Mensagens | `/inbox` |
| Perfil Freelancer | `/freelancer/<id>` |
| Enviar Mensagem | `/contatar-freelancer/<id>` |

---

## 📝 VERIFICAÇÃO REALIZADA

Testei os dados no banco de dados:
- ✅ **3 Propostas existem** no banco
- ✅ **2 Propostas aparecem** no dashboard da empresa
- ✅ **Propostas aparecem** no dashboard do freelancer
- ✅ **1 Mensagem existe** no banco
- ✅ **Mensagem aparece** no inbox

---

## 🛠️ POSSÍVEIS SOLUÇÕES SE NÃO VER:

1. **Certifique-se de estar LOGADO**
   - Empresa: Login em `/login-empresa`
   - Freelancer: Login em `/login-freelancer`

2. **Verifique se tem propostas naquela conta**
   - Cada conta só vê propostas/mensagens relacionadas à ela

3. **Limpe o cache do navegador**
   - Pressione `F5` ou `Ctrl+Shift+R`

4. **Verifique o banco de dados**
   - As propostas precisam estar vinculadas ao seu ID de empresa

---

## 📊 ESTRUTURA DE DADOS

### Tabela de Propostas:
- `projeto_id` - Qual projeto
- `freelancer_id` - Qual freelancer
- `valor_proposto` - Valor sugerido
- `prazo_dias` - Prazo sugerido
- `proposta` - Texto da proposta
- `status` - pendente/aceita/rejeitada

### Tabela de Mensagens:
- `remetente_id` - Quem enviou
- `destinatario_id` - Quem recebeu
- `remetente_tipo` - 'empresa' ou 'freelancer'
- `destinatario_tipo` - 'empresa' ou 'freelancer'
- `mensagem` - Conteúdo da mensagem

---

## 🎯 PRÓXIMAS MELHORIAS

- [ ] Contador de mensagens não lidas
- [ ] Busca e filtro de propostas
- [ ] Respostas diretas no inbox
- [ ] Notificações de novas propostas/mensagens
