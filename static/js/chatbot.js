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

    function ensinar(msg) {
        const t = (msg || '').toLowerCase();
        if (/cadastr|criar conta|abrir conta|registrar|como.*conta|cpf|cnpj/.test(t)) {
            return 'Para criar sua conta no aplicativo: 1) Toque em Cadastrar no topo. 2) Escolha Sou freelancer, se quer trabalhar, ou Sou empresa, se quer publicar. 3) Preencha nome, e-mail e uma senha com no mínimo 6 caracteres. 4) Freelancer coloca o CPF com 11 números. Empresa coloca o CNPJ com 14 números. 5) Informe o telefone e toque em Criar conta. 6) Depois toque em Já tenho conta e entre com o mesmo e-mail e a mesma senha. No computador: menu Cadastrar, escolha Freelancer ou Empresa, preencha o formulário e depois use Entrar.';
        }
        if (/entrar|login|senha/.test(t)) {
            return 'Depois de criar a conta, toque em Já tenho conta ou em Entrar. Escolha freelancer ou empresa e use o mesmo e-mail e a mesma senha do cadastro.';
        }
        return '';
    }

    function abrir() {
        panel.hidden = false;
        panel.classList.add('is-open');
        toggle.setAttribute('aria-expanded', 'true');
        if (!body.dataset.ready) {
            addBubble('Olá! Eu ensino você a usar o ConectaServ. Toque em Como me cadastrar ou escreva sua pergunta.', 'bot');
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
    if (closeBtn) closeBtn.addEventListener('click', fechar);
    document.querySelectorAll('[data-pergunta]').forEach(function (botao) {
        botao.addEventListener('click', function () {
            input.value = botao.getAttribute('data-pergunta');
            form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
        });
    });

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const mensagem = (input.value || '').trim();
        if (!mensagem) return;
        addBubble(mensagem, 'usuario');
        input.value = '';
        const aula = ensinar(mensagem);
        if (aula) {
            addBubble(aula, 'bot');
            return;
        }
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
