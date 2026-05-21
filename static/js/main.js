// ConectaServ - Main JavaScript
// Funcionalidades gerais da plataforma

document.addEventListener('DOMContentLoaded', function() {
    console.log('ConectaServ iniciado');
    
    // Acessibilidade - Botões de zoom
    setupAccessibility();
    
    // Menu responsivo
    setupMobileMenu();
    
    // Validações de formulário
    setupFormValidation();
});

// ==================== ACESSIBILIDADE ====================

function setupAccessibility() {
    const btnAPlus = document.querySelector('.btn-a-plus');
    const btnAMinus = document.querySelector('.btn-a-minus');
    const btnContrast = document.querySelector('.btn-contrast');
    
    if (btnAPlus) {
        btnAPlus.addEventListener('click', function() {
            increaseFontSize();
        });
    }
    
    if (btnAMinus) {
        btnAMinus.addEventListener('click', function() {
            decreaseFontSize();
        });
    }
    
    if (btnContrast) {
        btnContrast.addEventListener('click', function() {
            toggleContrast();
        });
    }
    
    // Restaurar preferências salvas
    restoreAccessibilityPreferences();
}

function increaseFontSize() {
    let currentSize = parseFloat(localStorage.getItem('fontSize')) || 16;
    if (currentSize < 24) {
        currentSize += 2;
        document.body.style.fontSize = currentSize + 'px';
        localStorage.setItem('fontSize', currentSize);
    }
}

function decreaseFontSize() {
    let currentSize = parseFloat(localStorage.getItem('fontSize')) || 16;
    if (currentSize > 12) {
        currentSize -= 2;
        document.body.style.fontSize = currentSize + 'px';
        localStorage.setItem('fontSize', currentSize);
    }
}

function toggleContrast() {
    const body = document.body;
    const hasContrast = body.classList.contains('high-contrast');
    
    if (hasContrast) {
        body.classList.remove('high-contrast');
        localStorage.setItem('contrast', 'false');
    } else {
        body.classList.add('high-contrast');
        localStorage.setItem('contrast', 'true');
    }

    syncContrastToggle();
}

function restoreAccessibilityPreferences() {
    const savedFontSize = localStorage.getItem('fontSize');
    if (savedFontSize) {
        document.body.style.fontSize = savedFontSize + 'px';
    }
    
    const savedContrast = localStorage.getItem('contrast');
    if (savedContrast === 'true') {
        document.body.classList.add('high-contrast');
    }

    syncContrastToggle();
}

function aumentarFonte() {
    increaseFontSize();
}

function diminuirFonte() {
    decreaseFontSize();
}

function alternarContraste() {
    toggleContrast();
}

function syncContrastToggle() {
    const toggle = document.querySelector('#altoContrasteToggle');
    if (toggle) {
        toggle.checked = document.body.classList.contains('high-contrast');
    }
}

/**
 * Abre o painel do VLibras (tradutor para Libras).
 * Aguarda o widget carregar se o usuário clicar antes do script externo.
 */
function abrirVLibras() {
    function clicarBotao() {
        const btn = document.querySelector('[vw-access-button]');
        if (btn) {
            btn.click();
            return true;
        }
        return false;
    }

    if (clicarBotao()) return;

    let tentativas = 0;
    const intervalo = setInterval(function () {
        if (clicarBotao() || ++tentativas >= 25) {
            clearInterval(intervalo);
        }
    }, 200);
}

window.aumentarFonte = aumentarFonte;
window.diminuirFonte = diminuirFonte;
window.alternarContraste = alternarContraste;
window.abrirVLibras = abrirVLibras;

// ==================== MENU RESPONSIVO ====================

function setupMobileMenu() {
    const menuToggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('nav');
    
    if (menuToggle && nav) {
        menuToggle.addEventListener('click', function() {
            nav.classList.toggle('active');
        });
        
        // Fechar menu ao clicar em um link
        const navLinks = nav.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                nav.classList.remove('active');
            });
        });
    }
}

// ==================== VALIDAÇÕES DE FORMULÁRIO ====================

function setupFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(form)) {
                e.preventDefault();
            }
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const inputs = form.querySelectorAll('input, textarea, select');
    
    inputs.forEach(input => {
        if (input.hasAttribute('required') && !input.value.trim()) {
            showFieldError(input, 'Este campo é obrigatório');
            isValid = false;
        } else if (input.type === 'email' && input.value && !isValidEmail(input.value)) {
            showFieldError(input, 'Email inválido');
            isValid = false;
        } else if (input.type === 'tel' && input.value && !isValidPhone(input.value)) {
            showFieldError(input, 'Telefone inválido');
            isValid = false;
        } else {
            clearFieldError(input);
        }
    });
    
    return isValid;
}

function showFieldError(field, message) {
    field.classList.add('error');
    let errorDiv = field.nextElementSibling;
    
    if (!errorDiv || !errorDiv.classList.contains('error-message')) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        field.parentNode.insertBefore(errorDiv, field.nextSibling);
    }
    
    errorDiv.textContent = message;
}

function clearFieldError(field) {
    field.classList.remove('error');
    let errorDiv = field.nextElementSibling;
    
    if (errorDiv && errorDiv.classList.contains('error-message')) {
        errorDiv.remove();
    }
}

function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

function isValidPhone(phone) {
    const regex = /^\(?[0-9]{2}\)?[\s-]?[0-9]{4,5}[\s-]?[0-9]{4}$/;
    return regex.test(phone.replace(/\D/g, ''));
}

// ==================== UTILITÁRIOS ====================

function formatCurrency(value) {
    return 'R$ ' + parseFloat(value).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
}

// Exportar funções para uso global
window.ConectaServ = {
    formatCurrency,
    formatDate,
    validateForm
};
