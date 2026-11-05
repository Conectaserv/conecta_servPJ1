const API = '/api/v1';
const view = document.getElementById('mView');
const sub = document.getElementById('mSub');
const SLOGAN = 'Conecta você. Resolve para você.';

function user() {
    try { return JSON.parse(localStorage.getItem('cs_user') || 'null'); } catch { return null; }
}
function token() { return localStorage.getItem('cs_token') || ''; }
function headers() {
    const h = { 'Content-Type': 'application/json' };
    if (token()) h.Authorization = 'Bearer ' + token();
    return h;
}
async function lerJson(r) {
    const texto = await r.text();
    try {
        return JSON.parse(texto);
    } catch {
        return { ok: false, erro: r.status === 404
            ? 'Servidor desatualizado. Feche o app, atualize a página e tente de novo.'
            : 'Não foi possível concluir. Código ' + r.status };
    }
}
async function get(path) {
    const r = await fetch(API + path, { headers: headers() });
    return lerJson(r);
}
async function post(path, body) {
    const r = await fetch(API + path, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
    return lerJson(r);
}

function respostaLocal(msg) {
    const t = (msg || '').toLowerCase();
    if (/oi\b|ol[aá]|bom dia|boa tarde|boa noite/.test(t)) {
        return 'Olá! Eu sou a assistente do ConectaServ. Conecta você. Resolve para você. Posso explicar como criar conta, publicar projeto ou enviar proposta.';
    }
    if (/cadastr|criar conta|abrir conta|registrar|como.*conta|cpf|cnpj/.test(t)) {
        return 'Para criar sua conta: 1) Toque em Cadastrar no topo. 2) Escolha Sou freelancer, se quer trabalhar, ou Sou empresa, se quer publicar. 3) Preencha nome, e-mail e uma senha com no mínimo 6 caracteres. 4) Freelancer coloca o CPF com 11 números. Empresa coloca o CNPJ com 14 números. 5) Informe o telefone e toque em Criar conta. 6) Depois toque em Já tenho conta e entre com o mesmo e-mail e a mesma senha.';
    }
    if (/entrar|login|senha/.test(t) && !/mostrar|olho/.test(t)) {
        return 'Toque em Entrar, escolha empresa ou profissional e informe e-mail e senha. O olho ao lado da senha mostra o que você digitou.';
    }
    if (/projeto|publicar|escolher|trabalhar|clicar/.test(t)) {
        return 'Para trabalhar: abra a aba Projetos e toque no card. Depois toque em Quero trabalhar neste projeto. Se ainda não tiver conta, toque em Cadastrar e escolha Sou freelancer.';
    }
    if (/proposta/.test(t)) {
        return 'Com conta de profissional, abra um projeto e envie valor, prazo e como você vai fazer o trabalho. A empresa escolhe uma proposta.';
    }
    if (/seguro|privacidade|dados/.test(t)) {
        return 'Sua senha é protegida. Nunca envie senha ou cartão neste chat.';
    }
    if (/custa|grátis|gratis|preço|preco/.test(t)) {
        return 'Usar a plataforma não tem mensalidade. O valor de cada trabalho é o combinado na proposta.';
    }
    if (/instalar|celular|app/.test(t)) {
        return 'No navegador do celular, use Adicionar à tela inicial para abrir o ConectaServ como aplicativo.';
    }
    return '';
}

async function cadastrarNaPlataforma(role, dados) {
    const api = role === 'empresa'
        ? await post('/auth/cadastro-empresa', dados)
        : await post('/auth/cadastro-freelancer', dados);
    if (api && api.ok) return api;

    const form = new URLSearchParams();
    if (role === 'empresa') {
        form.set('nome_empresa', dados.nome_empresa);
        form.set('cnpj', dados.cnpj);
        form.set('email', dados.email);
        form.set('senha', dados.senha);
        form.set('telefone', dados.telefone || '');
        form.set('setor', 'Tecnologia');
        form.set('descricao', '');
    } else {
        form.set('nome_completo', dados.nome_completo);
        form.set('cpf', dados.cpf);
        form.set('email', dados.email);
        form.set('senha', dados.senha);
        form.set('telefone', dados.telefone || '11999999999');
        form.set('cidade', 'São Paulo');
        form.set('estado', 'SP');
        form.set('especialidade', 'Tecnologia');
        form.set('habilidades', '');
        form.set('biografia', '');
        form.set('hourly_rate', '0');
    }
    const url = role === 'empresa' ? '/cadastro-empresa' : '/cadastro-freelancer';
    const r = await fetch(url, { method: 'POST', body: form, credentials: 'same-origin', redirect: 'follow' });
    const html = await r.text();
    const ok = /sucesso|Cadastro salvo|conta criada|Ir para o login/i.test(html);
    const duplicado = /já cadastrad|ja cadastrad|já está cadastrad/i.test(html);
    if (ok) return { ok: true };
    if (/CNPJ inválido|14 números/i.test(html)) {
        return { ok: false, erro: 'CNPJ precisa ter 14 números. Exemplo: 12345678000199' };
    }
    if (/CPF já|11 números/i.test(html)) {
        return { ok: false, erro: 'CPF precisa ter 11 números. Exemplo: 12345678901' };
    }
    if (duplicado) return { ok: false, erro: 'Este e-mail ou documento já possui conta. Tente entrar.' };
    if (api && api.erro && !/desatualizado|404/i.test(api.erro)) return api;
    return { ok: false, erro: 'Não foi possível cadastrar. Confira os dados e tente de novo.' };
}
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function money(v) {
    const n = Number(v || 0);
    return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
function ligarOlho() {
    document.querySelectorAll('[data-eye]').forEach((btn) => {
        btn.onclick = (e) => {
            e.preventDefault();
            const alvo = document.getElementById(btn.getAttribute('data-eye'));
            if (!alvo) return;
            alvo.type = alvo.type === 'password' ? 'text' : 'password';
            const icone = btn.querySelector('i');
            if (icone) {
                icone.classList.toggle('fa-eye');
                icone.classList.toggle('fa-eye-slash');
            }
        };
    });
}

function saveUser(data) {
    localStorage.setItem('cs_token', data.token);
    localStorage.setItem('cs_user', JSON.stringify(data.user));
}
function logout() {
    localStorage.removeItem('cs_token');
    localStorage.removeItem('cs_user');
    go('conta');
}

const screens = {
    async home() {
        view.innerHTML = `
            <div class="m-hero">
                <h1>${SLOGAN}</h1>
                <p>Encontre profissionais de tecnologia e feche projetos com acompanhamento até a entrega.</p>
            </div>
            <div class="kpis" id="kpis">
                <div class="kpi"><strong>…</strong><span>projetos abertos</span></div>
                <div class="kpi"><strong>…</strong><span>freelancers</span></div>
            </div>
            <button class="btn btn-p" data-go="projetos">Buscar projetos</button>
            ${user() ? '' : '<button class="btn btn-p" data-go="cadastro">Criar conta</button>'}
            <button class="btn btn-g" data-go="conta">${user() ? 'Meu painel' : 'Entrar'}</button>
            <button class="btn btn-g" data-go="talentos">Ver freelancers</button>
            <h3 style="margin:16px 0 8px">Projetos em destaque</h3>
            <div id="destaque"></div>`;
        try {
            const [p, f] = await Promise.all([get('/projetos'), get('/freelancers')]);
            document.getElementById('kpis').innerHTML = `
                <div class="kpi"><strong>${(p.projetos||[]).length}</strong><span>projetos abertos</span></div>
                <div class="kpi"><strong>${(f.freelancers||[]).length}</strong><span>freelancers</span></div>`;
            document.getElementById('destaque').innerHTML = (p.projetos||[]).slice(0, 3).map(cardProjeto).join('')
                || '<p class="muted">Nenhum projeto aberto no momento.</p>';
            view.querySelectorAll('[data-id]').forEach((el) => el.onclick = () => go('projeto', el.dataset.id));
        } catch {
            document.getElementById('kpis').innerHTML = '<div class="kpi"><strong>—</strong><span>sem conexão</span></div>';
        }
        view.querySelectorAll('[data-go]').forEach((b) => b.onclick = () => go(b.dataset.go));
    },

    async projetos() {
        view.innerHTML = '<p class="muted">Carregando projetos…</p>';
        try {
            const data = await get('/projetos');
            const list = data.projetos || [];
            view.innerHTML = (user()?.role === 'empresa' ? '<button class="btn btn-p" id="novo">Publicar projeto</button>' : '')
                + (list.length ? list.map(cardProjeto).join('') : '<p class="muted">Nenhum projeto aberto.</p>');
            const novo = document.getElementById('novo');
            if (novo) novo.onclick = () => go('criar');
            view.querySelectorAll('[data-id]').forEach((el) => el.onclick = () => go('projeto', el.dataset.id));
        } catch {
            view.innerHTML = '<p class="err">Não foi possível carregar os projetos.</p>';
        }
    },

    async projeto(id) {
        view.innerHTML = '<p class="muted">Carregando…</p>';
        const data = await get('/projeto/' + id);
        if (!data.ok) { view.innerHTML = '<p class="err">Projeto não encontrado.</p>'; return; }
        const p = data.projeto;
        const u = user();
        view.innerHTML = `
            <button class="back" data-go="projetos">← Projetos</button>
            <article class="card">
                <span class="chip">${esc(p.categoria)}</span>
                <h3>${esc(p.titulo)}</h3>
                <p class="muted">${esc(p.nome_empresa)} · ${esc(p.status)}</p>
                <p>${esc(p.descricao)}</p>
                <p><strong>${money(p.presupuesto)}</strong> · prazo ${esc(p.prazo || 'a combinar')}</p>
            </article>
            <div id="acoes"></div>`;
        const acoes = document.getElementById('acoes');
        if (u?.role === 'freelancer' && p.status === 'aberto') {
            acoes.innerHTML = '<button type="button" class="btn btn-p" id="prop">Quero trabalhar neste projeto</button>';
            document.getElementById('prop').onclick = () => go('proposta', id);
        } else if (u?.role === 'empresa' && p.status !== 'aberto') {
            acoes.innerHTML = '<button type="button" class="btn btn-p" id="ws">Abrir acompanhamento</button>';
            document.getElementById('ws').onclick = () => go('workspace', id);
        } else if (!u && (p.status === 'aberto' || !p.status)) {
            acoes.innerHTML = `
                <button type="button" class="btn btn-p" id="quero">Quero trabalhar neste projeto</button>
                <button type="button" class="btn btn-g" id="entrarProjeto">Já tenho conta</button>
                <p class="muted">Crie uma conta de freelancer para enviar sua proposta.</p>`;
            document.getElementById('quero').onclick = () => { sessionStorage.setItem('cs_escolha', id); go('cadastro'); };
            document.getElementById('entrarProjeto').onclick = () => { sessionStorage.setItem('cs_escolha', id); go('conta'); };
        } else if (u?.role === 'empresa') {
            acoes.innerHTML = '<p class="muted">Este projeto é para freelancers enviarem proposta.</p>';
        }
        view.querySelector('.back').onclick = () => go('projetos');
    },

    async talentos() {
        view.innerHTML = '<p class="muted">Carregando profissionais…</p>';
        try {
            const data = await get('/freelancers');
            const list = data.freelancers || [];
            view.innerHTML = list.length ? list.map((f) => `
                <article class="card" data-fid="${f.id}">
                    <span class="chip">${esc(f.especialidade || 'Tecnologia')}</span>
                    <h3>${esc(f.nome_completo)}</h3>
                    <p class="muted">${esc(f.cidade || '')} ${esc(f.estado || '')} · nota ${esc(f.nota_media || 0)}</p>
                    <p>${esc((f.habilidades || '').slice(0, 120))}</p>
                </article>`).join('') : '<p class="muted">Nenhum freelancer cadastrado.</p>';
            view.querySelectorAll('[data-fid]').forEach((el) => el.onclick = () => go('freelancer', el.dataset.fid));
        } catch {
            view.innerHTML = '<p class="err">Não foi possível carregar os talentos.</p>';
        }
    },

    async freelancer(id) {
        const data = await get('/freelancer/' + id);
        if (!data.ok) { view.innerHTML = '<p class="err">Perfil não encontrado.</p>'; return; }
        const f = data.freelancer;
        view.innerHTML = `
            <button class="back">← Talentos</button>
            <div class="card">
                <h3>${esc(f.nome_completo)}</h3>
                <p class="muted">${esc(f.especialidade)} · nota ${esc(f.nota_media || 0)}</p>
                <p>${esc(f.biografia || 'Sem biografia.')}</p>
                <p><strong>Habilidades:</strong> ${esc(f.habilidades || '—')}</p>
                <p>${f.hourly_rate ? 'Valor/hora: ' + money(f.hourly_rate) : ''}</p>
            </div>`;
        view.querySelector('.back').onclick = () => go('talentos');
    },

    chat() {
        view.innerHTML = `
            <div class="chat-box">
                <div class="chat-log" id="log"></div>
                <div class="ask-row">
                    <button type="button" data-q="Como criar uma conta?">Criar conta</button>
                    <button type="button" data-q="Como escolher um projeto?">Escolher projeto</button>
                    <button type="button" data-q="Como enviar uma proposta?">Enviar proposta</button>
                </div>
                <form class="chat-form" id="cf">
                    <input id="ci" placeholder="Escreva sua pergunta" maxlength="800" autocomplete="off">
                    <button type="submit" class="btn btn-p">Enviar</button>
                </form>
            </div>`;
        const log = document.getElementById('log');
        const bubble = (t, cls) => {
            const d = document.createElement('div');
            d.className = 'bub ' + cls;
            d.textContent = t;
            log.appendChild(d);
            log.scrollTop = log.scrollHeight;
        };
        async function falar(msg) {
            bubble(msg, 'me');
            let texto = respostaLocal(msg);
            if (!texto) {
                try {
                    const data = await post('/chat', { mensagem: msg, sessao_id: localStorage.getItem('cs_chat') || '', canal: 'mobile' });
                    if (data.sessao_id) localStorage.setItem('cs_chat', data.sessao_id);
                    texto = (data.resposta || '').trim();
                } catch {
                    texto = '';
                }
            }
            bubble(texto || 'Posso ajudar a criar conta, escolher um projeto e enviar proposta. Toque em uma sugestão acima.', 'bot');
        }
        bubble('Olá! Eu sou a assistente do ConectaServ. Toque em uma pergunta ou escreva a sua.', 'bot');
        view.querySelectorAll('[data-q]').forEach((b) => b.onclick = () => falar(b.dataset.q));
        document.getElementById('cf').onsubmit = (e) => {
            e.preventDefault();
            const input = document.getElementById('ci');
            const msg = input.value.trim();
            if (!msg) return;
            input.value = '';
            falar(msg);
        };
    },

    cadastro() {
        view.innerHTML = `
            <h2 style="margin-bottom:8px">Criar conta</h2>
            <form id="cfrm" class="card">
                <select id="crole">
                    <option value="freelancer">Sou freelancer — quero trabalhar</option>
                    <option value="empresa">Sou empresa — quero publicar</option>
                </select>
                <input id="cnome" placeholder="Nome completo ou nome da empresa" required>
                <input id="cemail" type="email" placeholder="E-mail" required>
                <div class="pwd">
                    <input id="csenha" type="password" placeholder="Senha (mínimo 6 caracteres)" required minlength="6">
                    <button type="button" class="eye" data-eye="csenha" aria-label="Mostrar senha"><i class="fas fa-eye"></i></button>
                </div>
                <input id="cdoc" placeholder="CPF com 11 números ou CNPJ com 14" required>
                <input id="ctel" placeholder="Telefone">
                <button type="submit" class="btn btn-p">Criar conta</button>
                <p class="err" id="ce"></p>
                <button type="button" class="btn btn-g" id="irLogin">Já tenho conta</button>
            </form>`;
        ligarOlho();
        document.getElementById('irLogin').onclick = () => go('conta');
        document.getElementById('cfrm').onsubmit = onCadastro;
    },

    async conta() {
        const u = user();
        if (!u) {
            view.innerHTML = `
                <div class="tabs-mini">
                    <button class="on" data-m="login">Entrar</button>
                    <button data-m="cad">Cadastrar</button>
                </div>
                <div id="box"></div>`;
            const box = document.getElementById('box');
            const showLogin = () => {
                box.innerHTML = `
                    <form id="lf" class="card">
                        <select id="role">
                            <option value="empresa">Empresa</option>
                            <option value="freelancer">Freelancer</option>
                        </select>
                        <input id="email" type="email" placeholder="E-mail" required>
                        <div class="pwd">
                            <input id="senha" type="password" placeholder="Senha (mín. 6)" required minlength="6">
                            <button type="button" class="eye" data-eye="senha" aria-label="Mostrar senha"><i class="fas fa-eye"></i></button>
                        </div>
                        <button class="btn btn-p">Entrar</button>
                        <p class="err" id="le"></p>
                    </form>`;
                ligarOlho();
                document.getElementById('lf').onsubmit = onLogin;
            };
            view.querySelectorAll('[data-m]').forEach((b) => b.onclick = () => {
                if (b.dataset.m === 'cad') { go('cadastro'); return; }
                view.querySelectorAll('[data-m]').forEach((x) => x.classList.toggle('on', x === b));
                showLogin();
            });
            showLogin();
            return;
        }
        if (u.role === 'empresa') return screens.painelEmpresa();
        return screens.painelFreelancer();
    },

    async painelEmpresa() {
        const u = user();
        view.innerHTML = `
            <div class="m-hero">
                <h1>${esc(u.nome || 'Empresa')}</h1>
                <p>Conta empresa · ${esc(u.email || '')}</p>
            </div>
            <div class="kpis" id="kpis"></div>
            <button class="btn btn-p" data-go="criar">Publicar projeto</button>
            <h3 style="margin:16px 0 8px">Propostas recebidas</h3>
            <div id="props"></div>
            <h3 style="margin:16px 0 8px">Meus projetos</h3>
            <div id="meus"></div>
            <button class="btn btn-g" id="out">Sair</button>`;
        document.getElementById('out').onclick = logout;
        view.querySelector('[data-go]').onclick = () => go('criar');
        try {
            const [ind, props, projs] = await Promise.all([
                get('/empresa/indicadores'), get('/empresa/propostas'), get('/empresa/projetos'),
            ]);
            const i = ind.indicadores || {};
            document.getElementById('kpis').innerHTML = `
                <div class="kpi"><strong>${i.publicados||0}</strong><span>publicados</span></div>
                <div class="kpi"><strong>${i.em_andamento||0}</strong><span>em andamento</span></div>
                <div class="kpi"><strong>${i.concluidos||0}</strong><span>concluídos</span></div>
                <div class="kpi"><strong>${i.propostas_recebidas||0}</strong><span>propostas</span></div>`;
            document.getElementById('props').innerHTML = (props.propostas||[]).map((p) => `
                <div class="card">
                    <h3>${esc(p.projeto_titulo)}</h3>
                    <p>${esc(p.freelancer_nome)} · ${money(p.valor_proposto)} · ${esc(p.prazo_dias)} dias</p>
                    <p class="muted">${esc(p.status)}</p>
                    ${p.status === 'pendente' ? `<button class="btn btn-p btn-s aceitar" data-pid="${p.id}">Aceitar</button>` : ''}
                    ${p.status === 'aceita' ? `<button class="btn btn-g btn-s ws" data-pr="${p.projeto_id}">Acompanhar</button>` : ''}
                </div>`).join('') || '<p class="muted">Nenhuma proposta ainda.</p>';
            document.getElementById('meus').innerHTML = (projs.projetos||[]).map((p) => `
                <div class="card" data-id="${p.id}">
                    <span class="chip">${esc(p.status)}</span>
                    <h3>${esc(p.titulo)}</h3>
                </div>`).join('') || '<p class="muted">Publique seu primeiro projeto.</p>';
            view.querySelectorAll('.aceitar').forEach((b) => b.onclick = async (ev) => {
                ev.stopPropagation();
                const r = await post('/proposta/' + b.dataset.pid + '/aceitar', {});
                if (r.ok) go('workspace', r.projeto_id); else alert(r.erro || 'Erro');
            });
            view.querySelectorAll('.ws').forEach((b) => b.onclick = (ev) => { ev.stopPropagation(); go('workspace', b.dataset.pr); });
            view.querySelectorAll('#meus [data-id]').forEach((el) => el.onclick = () => go('projeto', el.dataset.id));
        } catch {
            document.getElementById('kpis').innerHTML = '<p class="err">Faça login novamente.</p>';
        }
    },

    async painelFreelancer() {
        const u = user();
        view.innerHTML = `
            <div class="m-hero">
                <h1>${esc(u.nome || 'Freelancer')}</h1>
                <p>Conta freelancer · ${esc(u.email || '')}</p>
            </div>
            <button class="btn btn-p" data-go="projetos">Buscar projetos</button>
            <h3 style="margin:16px 0 8px">Minhas propostas</h3>
            <div id="props"></div>
            <button class="btn btn-g" id="out">Sair</button>`;
        document.getElementById('out').onclick = logout;
        view.querySelector('[data-go]').onclick = () => go('projetos');
        const data = await get('/freelancer/propostas');
        document.getElementById('props').innerHTML = (data.propostas||[]).map((p) => `
            <div class="card">
                <h3>${esc(p.projeto_titulo)}</h3>
                <p>${esc(p.nome_empresa)} · ${money(p.valor_proposto)}</p>
                <p class="muted">${esc(p.status)}</p>
                ${p.status === 'aceita' ? `<button class="btn btn-p btn-s ws" data-pr="${p.projeto_id}">Acompanhar</button>` : ''}
            </div>`).join('') || '<p class="muted">Você ainda não enviou propostas.</p>';
        view.querySelectorAll('.ws').forEach((b) => b.onclick = () => go('workspace', b.dataset.pr));
    },

    criar() {
        if (user()?.role !== 'empresa') { go('conta'); return; }
        view.innerHTML = `
            <button class="back">← Voltar</button>
            <form id="nf" class="card">
                <h3>Novo projeto</h3>
                <input id="titulo" placeholder="Título" required>
                <textarea id="desc" placeholder="Descrição" required></textarea>
                <input id="cat" placeholder="Categoria (ex.: Desenvolvimento Web)">
                <input id="orc" type="number" step="0.01" placeholder="Orçamento (R$)">
                <input id="prazo" placeholder="Prazo (data ou dias)">
                <button class="btn btn-p">Publicar</button>
                <p class="err" id="ne"></p>
            </form>`;
        view.querySelector('.back').onclick = () => go('conta');
        document.getElementById('nf').onsubmit = async (e) => {
            e.preventDefault();
            const r = await post('/projetos', {
                titulo: document.getElementById('titulo').value,
                descricao: document.getElementById('desc').value,
                categoria: document.getElementById('cat').value || 'Outros',
                orcamento: document.getElementById('orc').value,
                prazo: document.getElementById('prazo').value,
            });
            if (!r.ok) { document.getElementById('ne').textContent = r.erro; return; }
            go('projeto', r.projeto_id);
        };
    },

    proposta(id) {
        if (user()?.role !== 'freelancer') { go('conta'); return; }
        view.innerHTML = `
            <button class="back">← Voltar</button>
            <form id="pf" class="card">
                <h3>Enviar proposta</h3>
                <input id="valor" type="number" step="0.01" placeholder="Valor (R$)" required>
                <input id="prazo" type="number" placeholder="Prazo em dias" required>
                <textarea id="txt" placeholder="Como você vai executar o projeto" required></textarea>
                <button class="btn btn-p">Enviar</button>
                <p class="err" id="pe"></p>
            </form>`;
        view.querySelector('.back').onclick = () => go('projeto', id);
        document.getElementById('pf').onsubmit = async (e) => {
            e.preventDefault();
            const r = await post('/projeto/' + id + '/proposta', {
                valor: document.getElementById('valor').value,
                prazo: document.getElementById('prazo').value,
                proposta: document.getElementById('txt').value,
            });
            if (!r.ok) { document.getElementById('pe').textContent = r.erro; return; }
            go('conta');
        };
    },

    async workspace(id) {
        const data = await get('/projeto/' + id);
        if (!data.ok) { view.innerHTML = '<p class="err">Projeto não encontrado.</p>'; return; }
        const p = data.projeto;
        view.innerHTML = `
            <button class="back">← Voltar</button>
            <div class="m-hero">
                <h1>${esc(p.titulo)}</h1>
                <p>${esc(p.etapa_label || p.etapa || p.status)} · ${esc(p.progresso || 0)}%</p>
            </div>
            <h3>Tarefas</h3>
            ${(data.tarefas||[]).map((t) => `<div class="card"><strong>${esc(t.titulo)}</strong><p class="muted">${esc(t.status)}</p></div>`).join('') || '<p class="muted">Sem tarefas.</p>'}
            <h3 style="margin-top:12px">Histórico</h3>
            ${(data.historico||[]).slice(0,8).map((h) => `<p class="muted">${esc(h.evento)} — ${esc(h.detalhe || '')}</p>`).join('') || '<p class="muted">Sem eventos.</p>'}`;
        view.querySelector('.back').onclick = () => go('conta');
    },

    async notificacoes() {
        view.innerHTML = '<p class="muted">Carregando avisos…</p>';
        const data = await get('/notificacoes');
        const itens = data.itens || [];
        view.innerHTML = `
            <button class="back">← Voltar</button>
            <h2>Notificações</h2>
            ${itens.length ? itens.map((n) => `
                <article class="card">
                    <strong>${esc(n.titulo)}</strong>
                    <p>${esc(n.mensagem)}</p>
                    <p class="muted">${esc(n.data_criacao || '')}</p>
                </article>`).join('') : '<p class="muted">Nenhuma mensagem nova. O sino acende quando empresa ou freelancer receber uma mensagem.</p>'}`;
        view.querySelector('.back').onclick = () => go('conta');
        if (user()) await post('/notificacoes/lidas', {});
        atualizarSino();
    },
};

function cardProjeto(p) {
    return `<button type="button" class="card card-tap" data-id="${p.id}">
        <span class="chip">${esc(p.categoria)}</span>
        <h3>${esc(p.titulo)}</h3>
        <p class="muted">${esc((p.descricao || '').slice(0, 110))}</p>
        <p><strong>${money(p.presupuesto)}</strong> · ${esc(p.nome_empresa || '')}</p>
        <span class="escolher">Escolher este projeto</span>
    </button>`;
}

async function onLogin(e) {
    e.preventDefault();
    const le = document.getElementById('le');
    le.textContent = '';
    const data = await post('/auth/login', {
        email: document.getElementById('email').value,
        senha: document.getElementById('senha').value,
        role: document.getElementById('role').value,
    });
    if (!data.ok) { le.textContent = data.erro || 'Não foi possível entrar'; return; }
    saveUser(data);
    const escolha = sessionStorage.getItem('cs_escolha');
    sessionStorage.removeItem('cs_escolha');
    if (escolha && data.user && data.user.role === 'freelancer') go('proposta', escolha);
    else go('conta');
}

async function onCadastro(e) {
    e.preventDefault();
    const ce = document.getElementById('ce');
    const btn = e.target.querySelector('button[type="submit"], .btn-p');
    ce.className = 'err';
    ce.textContent = 'Salvando...';
    if (btn) btn.disabled = true;
    try {
        const role = document.getElementById('crole').value;
        const payload = {
            email: document.getElementById('cemail').value,
            senha: document.getElementById('csenha').value,
            telefone: document.getElementById('ctel').value,
        };
        const data = await cadastrarNaPlataforma(role, role === 'empresa'
            ? { ...payload, nome_empresa: document.getElementById('cnome').value, cnpj: document.getElementById('cdoc').value }
            : { ...payload, nome_completo: document.getElementById('cnome').value, cpf: document.getElementById('cdoc').value });
        if (!data.ok) {
            ce.textContent = data.erro || 'Não foi possível cadastrar';
            return;
        }
        ce.className = 'ok';
        ce.textContent = 'Conta criada. Agora entre com o mesmo e-mail e senha.';
        setTimeout(() => go('conta'), 700);
    } catch (err) {
        ce.textContent = 'Falha de conexão. Confira se o servidor está ligado no PC.';
    } finally {
        if (btn) btn.disabled = false;
    }
}

const titulos = {
    home: SLOGAN,
    projetos: 'Projetos abertos',
    talentos: 'Freelancers',
    chat: 'Assistente ConectaServ',
    conta: 'Sua conta',
    cadastro: 'Criar conta',
    criar: 'Novo projeto',
    proposta: 'Proposta',
    projeto: 'Detalhes',
    workspace: 'Acompanhamento',
    freelancer: 'Perfil',
    notificacoes: 'Notificações',
};

async function atualizarSino() {
    const btn = document.getElementById('mSino');
    const badge = document.getElementById('mSinoN');
    if (!btn) return;
    if (!user()) { btn.hidden = true; return; }
    btn.hidden = false;
    const data = await get('/notificacoes');
    const n = Number(data.nao_lidas || 0);
    if (!badge) return;
    badge.hidden = n < 1;
    badge.textContent = n > 9 ? '9+' : String(n);
}

function go(tab, id) {
    document.querySelectorAll('.m-tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    sub.textContent = titulos[tab] || SLOGAN;
    const criar = document.getElementById('mCriarConta');
    if (criar) criar.hidden = !!user();
    atualizarSino();
    const fn = screens[tab];
    if (fn) fn(id);
}

document.querySelectorAll('.m-tabbar button').forEach((b) => {
    b.onclick = () => go(b.dataset.tab);
});
const criarConta = document.getElementById('mCriarConta');
if (criarConta) criarConta.onclick = () => go('cadastro');
const sino = document.getElementById('mSino');
if (sino) sino.onclick = () => go('notificacoes');
go('home');
setInterval(atualizarSino, 20000);

let deferred;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e;
    const btn = document.getElementById('mInstall');
    btn.hidden = false;
    btn.onclick = async () => {
        deferred.prompt();
        await deferred.userChoice;
        btn.hidden = true;
    };
});
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
}
