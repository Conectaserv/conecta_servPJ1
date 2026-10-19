const API = '/api/v1';
const view = document.getElementById('mView');
const sub = document.getElementById('mSub');

function user() {
    try { return JSON.parse(localStorage.getItem('cs_user') || 'null'); } catch { return null; }
}
function token() { return localStorage.getItem('cs_token') || ''; }
function headers(extra) {
    const h = { 'Content-Type': 'application/json', ...(extra || {}) };
    if (token()) h.Authorization = 'Bearer ' + token();
    return h;
}

async function get(path) {
    const r = await fetch(API + path, { headers: headers() });
    return r.json();
}
async function post(path, body) {
    const r = await fetch(API + path, { method: 'POST', headers: headers(), body: JSON.stringify(body) });
    return r.json();
}

function esc(s) {
    return String(s || '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const screens = {
    async home() {
        let health = {};
        try { health = await get('/health'); } catch { health = {}; }
        view.innerHTML = `
            <div class="m-hero">
                <h1>Conecte empresas e talentos</h1>
                <p>Mesmo visual do site 2.0. Dados vêm da API ${esc(health.servico || 'ConectaServ')}.</p>
            </div>
            <div class="kpis" id="kpis"><div class="kpi"><strong>…</strong><span>carregando</span></div></div>
            <div class="card">
                <span class="chip">Como usar</span>
                <h3>Site + app juntos</h3>
                <p class="muted">Cadastre no site, entre aqui com o mesmo e-mail. Projetos, chat e painel compartilham o banco.</p>
                <button class="btn btn-p" data-go="projetos">Ver projetos abertos</button>
                <button class="btn btn-g" data-go="chat">Falar com o chatbot</button>
            </div>`;
        try {
            const [p, f] = await Promise.all([get('/projetos'), get('/freelancers')]);
            document.getElementById('kpis').innerHTML = `
                <div class="kpi"><strong>${(p.projetos||[]).length}</strong><span>projetos abertos</span></div>
                <div class="kpi"><strong>${(f.freelancers||[]).length}</strong><span>freelancers</span></div>`;
        } catch {
            document.getElementById('kpis').innerHTML = '<div class="kpi"><strong>—</strong><span>API offline</span></div>';
        }
        view.querySelectorAll('[data-go]').forEach((b) => b.onclick = () => go(b.dataset.go));
    },

    async projetos() {
        view.innerHTML = '<p class="muted">Carregando projetos…</p>';
        try {
            const data = await get('/projetos');
            const list = data.projetos || [];
            view.innerHTML = list.length ? list.map((p) => `
                <article class="card">
                    <span class="chip">${esc(p.categoria)}</span>
                    <h3>${esc(p.titulo)}</h3>
                    <p class="muted">${esc((p.descricao || '').slice(0, 140))}</p>
                    <p><strong>R$ ${esc(p.presupuesto || 0)}</strong> · ${esc(p.nome_empresa)}</p>
                </article>`).join('') : '<p class="muted">Nenhum projeto aberto agora.</p>';
        } catch {
            view.innerHTML = '<p class="err">Não foi possível carregar. Confira se o servidor está no ar.</p>';
        }
    },

    chat() {
        const sid = localStorage.getItem('cs_chat') || '';
        view.innerHTML = `
            <div class="chat-log" id="log"></div>
            <form class="row" id="cf">
                <input id="ci" placeholder="Pergunte à assistente…" maxlength="800">
                <button class="btn btn-p" style="width:auto;padding:11px 16px">Enviar</button>
            </form>`;
        const log = document.getElementById('log');
        function bubble(t, cls) {
            const d = document.createElement('div');
            d.className = 'bub ' + cls;
            d.textContent = t;
            log.appendChild(d);
            log.scrollTop = log.scrollHeight;
        }
        bubble('Olá! Sou a mesma assistente do site. Posso falar de cadastro, painel, workspace e API.', 'bot');
        document.getElementById('cf').onsubmit = async (e) => {
            e.preventDefault();
            const input = document.getElementById('ci');
            const msg = input.value.trim();
            if (!msg) return;
            bubble(msg, 'me');
            input.value = '';
            try {
                const data = await post('/chat', { mensagem: msg, sessao_id: localStorage.getItem('cs_chat') || sid, canal: 'mobile' });
                if (data.sessao_id) localStorage.setItem('cs_chat', data.sessao_id);
                bubble(data.resposta || data.erro, 'bot');
            } catch {
                bubble('Falha ao falar com /api/v1/chat', 'bot');
            }
        };
    },

    async conta() {
        const u = user();
        if (u) {
            let extra = '';
            if (u.role === 'empresa') {
                try {
                    const ind = await get('/empresa/indicadores');
                    const i = ind.indicadores || {};
                    extra = `<div class="kpis">
                        <div class="kpi"><strong>${i.publicados||0}</strong><span>publicados</span></div>
                        <div class="kpi"><strong>${i.em_andamento||0}</strong><span>andamento</span></div>
                        <div class="kpi"><strong>${i.concluidos||0}</strong><span>concluídos</span></div>
                        <div class="kpi"><strong>${i.propostas_recebidas||0}</strong><span>propostas</span></div>
                    </div>`;
                } catch { extra = '<p class="muted">Indicadores indisponíveis.</p>'; }
            }
            view.innerHTML = `
                <div class="m-hero">
                    <h1>${esc(u.nome || u.email)}</h1>
                    <p>Perfil: ${esc(u.role)} · sincronizado com o site</p>
                </div>
                ${extra}
                <button class="btn btn-g" id="out">Sair</button>`;
            document.getElementById('out').onclick = () => {
                localStorage.removeItem('cs_token');
                localStorage.removeItem('cs_user');
                go('conta');
            };
            return;
        }
        view.innerHTML = `
            <div class="m-hero"><h1>Entrar no app</h1><p>Use a mesma conta do site.</p></div>
            <form id="lf" class="card">
                <select id="role">
                    <option value="empresa">Empresa</option>
                    <option value="freelancer">Freelancer</option>
                </select>
                <input id="email" type="email" placeholder="E-mail" required>
                <input id="senha" type="password" placeholder="Senha" required>
                <button class="btn btn-p">Entrar</button>
                <p class="err" id="le"></p>
                <p class="muted">Ainda não tem conta? Cadastre-se no site e volte aqui.</p>
            </form>`;
        document.getElementById('lf').onsubmit = async (e) => {
            e.preventDefault();
            const le = document.getElementById('le');
            le.textContent = '';
            try {
                const data = await post('/auth/login', {
                    email: document.getElementById('email').value,
                    senha: document.getElementById('senha').value,
                    role: document.getElementById('role').value,
                });
                if (!data.ok) { le.textContent = data.erro || 'Falha no login'; return; }
                localStorage.setItem('cs_token', data.token);
                localStorage.setItem('cs_user', JSON.stringify(data.user));
                go('conta');
            } catch {
                le.textContent = 'API indisponível';
            }
        };
    },
};

function go(tab) {
    document.querySelectorAll('.m-tabbar button').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
    const nomes = { home: 'O mesmo design. A mesma API.', projetos: 'Projetos abertos', chat: 'Chatbot da API', conta: 'Sua conta' };
    sub.textContent = nomes[tab] || '';
    screens[tab]();
}

document.querySelectorAll('.m-tabbar button').forEach((b) => {
    b.onclick = () => go(b.dataset.tab);
});
go('home');

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
