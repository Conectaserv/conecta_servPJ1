/**
 * ConectaServ - JavaScript Principal
 * Plataforma de marketplace para freelancers de tecnologia
 */

// Configuracoes de acessibilidade
let tamanhoFonte = 100;
let altoContraste = false;

// Inicializacao
document.addEventListener('DOMContentLoaded', function() {
    inicializarMenu();
    inicializarFormularios();
    carregarConfiguracoesAcessibilidade();
});

/**
 * Menu mobile
 */
function inicializarMenu() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navMenu = document.querySelector('.nav-menu');
    
    if (menuToggle && navMenu) {
        menuToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
        });
    }
}

/**
 * Formularios
 */
function inicializarFormularios() {
    // Validacao de formularios
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validarFormulario(form)) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Validacao em tempo real
    const inputs = document.querySelectorAll('.form-control[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validarCampo(this);
        });
    });
}

/**
 * Validar formulario completo
 */
function validarFormulario(form) {
    let valido = true;
    const inputs = form.querySelectorAll('.form-control[required]');
    
    inputs.forEach(input => {
        if (!validarCampo(input)) {
            valido = false;
        }
    });
    
    return valido;
}

/**
 * Validar campo individual
 */
function validarCampo(campo) {
    const valor = campo.value.trim();
    let valido = true;
    let mensagem = '';
    
    // Verificar se esta vazio
    if (campo.hasAttribute('required') && !valor) {
        valido = false;
        mensagem = 'Este campo e obrigatorio';
    }
    
    // Validar email
    if (campo.type === 'email' && valor) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(valor)) {
            valido = false;
            mensagem = 'Email invalido';
        }
    }
    
    // Validar CPF
    if (campo.name === 'cpf' && valor) {
        if (!validarCPF(valor)) {
            valido = false;
            mensagem = 'CPF invalido';
        }
    }
    
    // Validar CNPJ
    if (campo.name === 'cnpj' && valor) {
        if (!validarCNPJ(valor)) {
            valido = false;
            mensagem = 'CNPJ invalido';
        }
    }
    
    // Validar senha
    if (campo.type === 'password' && valor) {
        if (valor.length < 6) {
            valido = false;
            mensagem = 'Senha deve ter pelo menos 6 caracteres';
        }
    }
    
    // Mostrar resultado
    const grupo = campo.closest('.form-group');
    if (grupo) {
        let erroEl = grupo.querySelector('.erro-mensagem');
        
        if (!valido) {
            campo.classList.add('erro');
            if (!erroEl) {
                erroEl = document.createElement('span');
                erroEl.className = 'erro-mensagem';
                erroEl.style.color = '#E74C3C';
                erroEl.style.fontSize = '0.875rem';
                grupo.appendChild(erroEl);
            }
            erroEl.textContent = mensagem;
        } else {
            campo.classList.remove('erro');
            if (erroEl) {
                erroEl.remove();
            }
        }
    }
    
    return valido;
}

/**
 * Validar CPF
 */
function validarCPF(cpf) {
    cpf = cpf.replace(/[^\d]/g, '');
    
    if (cpf.length !== 11) return false;
    
    // Verificar digitos repetidos
    if (/^(\d)\1+$/.test(cpf)) return false;
    
    // Validar digitos verificadores
    let soma = 0;
    for (let i = 0; i < 9; i++) {
        soma += parseInt(cpf[i]) * (10 - i);
    }
    
    let digito1 = 11 - (soma % 11);
    if (digito1 > 9) digito1 = 0;
    
    if (parseInt(cpf[9]) !== digito1) return false;
    
    soma = 0;
    for (let i = 0; i < 10; i++) {
        soma += parseInt(cpf[i]) * (11 - i);
    }
    
    let digito2 = 11 - (soma % 11);
    if (digito2 > 9) digito2 = 0;
    
    return parseInt(cpf[10]) === digito2;
}

/**
 * Validar CNPJ
 */
function validarCNPJ(cnpj) {
    cnpj = cnpj.replace(/[^\d]/g, '');
    
    if (cnpj.length !== 14) return false;
    
    // Verificar digitos repetidos
    if (/^(\d)\1+$/.test(cnpj)) return false;
    
    // Validar digitos verificadores
    let soma = 0;
    let peso = 2;
    
    for (let i = 11; i >= 0; i--) {
        soma += parseInt(cnpj[i]) * peso;
        peso = peso === 9 ? 2 : peso + 1;
    }
    
    let digito1 = soma % 11;
    if (digito1 < 2) digito1 = 0;
    else digito1 = 11 - digito1;
    
    if (parseInt(cnpj[12]) !== digito1) return false;
    
    soma = 0;
    peso = 2;
    
    for (let i = 12; i >= 0; i--) {
        soma += parseInt(cnpj[i]) * peso;
        peso = peso === 9 ? 2 : peso + 1;
    }
    
    let digito2 = soma % 11;
    if (digito2 < 2) digito2 = 0;
    else digito2 = 11 - digito2;
    
    return parseInt(cnpj[13]) === digito2;
}

/**
 * Acessibilidade - Aumentar fonte
 */
function aumentarFonte() {
    if (tamanhoFonte < 150) {
        tamanhoFonte += 10;
        document.body.style.fontSize = tamanhoFonte + '%';
        localStorage.setItem('tamanhoFonte', tamanhoFonte);
    }
}

/**
 * Acessibilidade - Diminuir fonte
 */
function diminuirFonte() {
    if (tamanhoFonte > 70) {
        tamanhoFonte -= 10;
        document.body.style.fontSize = tamanhoFonte + '%';
        localStorage.setItem('tamanhoFonte', tamanhoFonte);
    }
}

/**
 * Acessibilidade - Alternar contraste
 */
function alternarContraste() {
    altoContraste = !altoContraste;
    
    if (altoContraste) {
        document.body.classList.add('alto-contraste');
    } else {
        document.body.classList.remove('alto-contraste');
    }
    
    localStorage.setItem('altoContraste', altoContraste);
}

/**
 * Carregar configuracoes de acessibilidade
 */
function carregarConfiguracoesAcessibilidade() {
    const tamanhoSalvo = localStorage.getItem('tamanhoFonte');
    if (tamanhoSalvo) {
        tamanhoFonte = parseInt(tamanhoSalvo);
        document.body.style.fontSize = tamanhoFonte + '%';
    }
    
    const contrasteSalvo = localStorage.getItem('altoContraste');
    if (contrasteSalvo === 'true') {
        altoContraste = true;
        document.body.classList.add('alto-contraste');
    }
}

/**
 * Busca em tempo real
 */
function buscarTempoReal(campo, url) {
    const termo = campo.value.trim();
    
    if (termo.length >= 3) {
        // Debounce de 300ms
        clearTimeout(window.buscaTimeout);
        window.buscaTimeout = setTimeout(function() {
            window.location.href = url + '?q=' + encodeURIComponent(termo);
        }, 300);
    }
}

/**
 * Confirmar acao
 */
function confirmarAcao(mensagem) {
    return confirm(mensagem || 'Tem certeza que deseja continuar?');
}

/**
 * Mostrar/esconder senha
 */
function toggleSenha(campoId) {
    const campo = document.getElementById(campoId);
    if (campo) {
        if (campo.type === 'password') {
            campo.type = 'text';
        } else {
            campo.type = 'password';
        }
    }
}

/**
 * Formatacao de valores monetarios
 */
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(valor);
}

/**
 * Formatacao de data
 */
function formatarData(data) {
    return new Intl.DateTimeFormat('pt-BR').format(new Date(data));
}

/**
 * Formatacao de telefone
 */
function formatarTelefone(telefone) {
    telefone = telefone.replace(/\D/g, '');
    
    if (telefone.length === 11) {
        return '(' + telefone.substring(0, 2) + ') ' + telefone.substring(2, 7) + '-' + telefone.substring(7);
    } else if (telefone.length === 10) {
        return '(' + telefone.substring(0, 2) + ') ' + telefone.substring(2, 6) + '-' + telefone.substring(6);
    }
    
    return telefone;
}

/**
 * Mascara para telefone
 */
function mascaraTelefone(campo) {
    campo.addEventListener('input', function(e) {
        let valor = e.target.value.replace(/\D/g, '');
        
        if (valor.length > 10) {
            valor = valor.substring(0, 11);
        }
        
        if (valor.length >= 10) {
            valor = valor.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
        } else if (valor.length >= 6) {
            valor = valor.replace(/(\d{2})(\d{4})/, '($1) $2');
        }
        
        e.target.value = valor;
    });
}

/**
 * Mascara para CPF
 */
function mascaraCPF(campo) {
    campo.addEventListener('input', function(e) {
        let valor = e.target.value.replace(/\D/g, '');
        
        if (valor.length > 11) {
            valor = valor.substring(0, 11);
        }
        
        if (valor.length >= 9) {
            valor = valor.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
        } else if (valor.length >= 6) {
            valor = valor.replace(/(\d{3})(\d{3})(\d{3})/, '$1.$2.$3');
        } else if (valor.length >= 3) {
            valor = valor.replace(/(\d{3})(\d{3})/, '$1.$2');
        }
        
        e.target.value = valor;
    });
}

/**
 * Mascara para CNPJ
 */
function mascaraCNPJ(campo) {
    campo.addEventListener('input', function(e) {
        let valor = e.target.value.replace(/\D/g, '');
        
        if (valor.length > 14) {
            valor = valor.substring(0, 14);
        }
        
        if (valor.length >= 12) {
            valor = valor.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
        } else if (valor.length >= 8) {
            valor = valor.replace(/(\d{2})(\d{3})(\d{3})(\d{4})/, '$1.$2.$3/$4');
        }
        
        e.target.value = valor;
    });
}

/**
 * Mascara para moeda
 */
function mascaraMoeda(campo) {
    campo.addEventListener('input', function(e) {
        let valor = e.target.value.replace(/\D/g, '');
        
        valor = (valor / 100).toFixed(2);
        valor = valor.replace('.', ',');
        valor = valor.replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
        
        e.target.value = valor;
    });
}

/**
 * Inicializar mascaras
 */
function inicializarMascaras() {
    const telefones = document.querySelectorAll('input[type="tel"]');
    telefones.forEach(telefone => mascaraTelefone(telefone));
    
    const cpfs = document.querySelectorAll('input[name="cpf"]');
    cpfs.forEach(cpf => mascaraCPF(cpf));
    
    const cnpjs = document.querySelectorAll('input[name="cnpj"]');
    cnpjs.forEach(cnpj => mascaraCNPJ(cnpjs));
    
    const valores = document.querySelectorAll('input[name="presupuesto"], input[name="hourly_rate"], input[name="valor"]');
    valores.forEach(valor => mascaraMoeda(valor));
}

// Exportar funcoes para uso global
window.aumentarFonte = aumentarFonte;
window.dimuiruirFonte = diminuirFonte;
window.alternarContraste = alternarContraste;
window.confirmarAcao = confirmarAcao;
window.toggleSenha = toggleSenha;
window.formatarMoeda = formatarMoeda;
window.formatarData = formatarData;
window.formatarTelefone = formatarTelefone;
window.inicializarMascaras = inicializarMascaras;
window.buscarTempoReal = buscarTempoReal;