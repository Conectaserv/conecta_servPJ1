(function () {
    const panel = document.getElementById('csChatPanel');
    const body = document.getElementById('csChatBody');
    const form = document.getElementById('csChatForm');
    const input = document.getElementById('csChatInput');
    const toggle = document.getElementById('csChatToggle');
    const closeBtn = document.getElementById('csChatClose');
    if (!panel || !form) return;

    const KEY = 'cs_chat_sessao';
    let sessao = localStorage.getItem(KEY) || '';

    function addBubble(texto, origem) {
        const el = document.createElement('div');
        el.className = 'cs-bubble ' + origem;
        el.textContent = texto;
        body.appendChild(el);
        body.scrollTop = body.scrollHeight;
    }

    function abrir() {
        panel.hidden = false;
        panel.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
        if (!body.dataset.ready) {
            addBubble('Olá! Sou a assistente do ConectaServ 2.0. Pergunte sobre cadastro, propostas, painel, workspace ou o app.', 'bot');
            body.dataset.ready = '1';
        }
        input.focus();
    }

    function fechar() {
        panel.classList.remove('is-open');
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', function () {
        if (panel.hidden) abrir();
        else fechar();
    });
    closeBtn.addEventListener('click', fechar);

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const mensagem = (input.value || '').trim();
        if (!mensagem) return;
        addBubble(mensagem, 'usuario');
        input.value = '';
        addBubble('Digitando…', 'bot typing');
        const typing = body.lastElementChild;
        try {
            const resp = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ mensagem: mensagem, sessao_id: sessao, canal: 'web' }),
            });
            const data = await resp.json();
            if (data.sessao_id) {
                sessao = data.sessao_id;
                localStorage.setItem(KEY, sessao);
            }
            typing.remove();
            addBubble(data.resposta || data.erro || 'Sem resposta.', 'bot');
        } catch (err) {
            typing.remove();
            addBubble('Não consegui falar com a API agora. Tente de novo.', 'bot');
        }
    });
})();
