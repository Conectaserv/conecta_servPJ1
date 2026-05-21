"""
Envio de e-mails do ConectaServ.
Configure as variáveis de ambiente SMTP_* no servidor de produção.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_configurado():
    return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_FROM'))


def enviar_email(destinatario, assunto, corpo_texto, corpo_html=None):
    """
    Envia e-mail via SMTP. Retorna (sucesso: bool, mensagem: str).
    Sem SMTP configurado, apenas registra no console (modo desenvolvimento).
    """
    if not destinatario:
        return False, 'Destinatário não informado.'

    if not _smtp_configurado():
        print(f'[EMAIL-DEV] Para: {destinatario}')
        print(f'[EMAIL-DEV] Assunto: {assunto}')
        print(f'[EMAIL-DEV] Corpo:\n{corpo_texto}')
        return True, 'E-mail registrado em modo desenvolvimento (configure SMTP_HOST e SMTP_FROM em produção).'

    host = os.environ.get('SMTP_HOST')
    port = int(os.environ.get('SMTP_PORT', '587'))
    usuario = os.environ.get('SMTP_USER', '')
    senha = os.environ.get('SMTP_PASS', '')
    remetente = os.environ.get('SMTP_FROM')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario
    msg.attach(MIMEText(corpo_texto, 'plain', 'utf-8'))
    if corpo_html:
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if os.environ.get('SMTP_TLS', '1') == '1':
                server.starttls()
            if usuario and senha:
                server.login(usuario, senha)
            server.sendmail(remetente, [destinatario], msg.as_string())
        return True, 'E-mail enviado com sucesso.'
    except Exception as exc:
        print(f'[EMAIL-ERRO] {exc}')
        return False, f'Falha ao enviar e-mail: {exc}'


def enviar_email_proposta_aceita(freelancer_email, freelancer_nome, projeto_titulo, prazo_dias, valor, empresa_nome, empresa_email, empresa_telefone):
    """Notifica o freelancer que a proposta foi aceita."""
    assunto = f'ConectaServ — Proposta aceita: {projeto_titulo}'
    corpo = f"""Olá, {freelancer_nome}!

Sua proposta foi ACEITA pela empresa {empresa_nome} no projeto "{projeto_titulo}".

Detalhes do serviço:
- Valor acordado: R$ {valor}
- Prazo do serviço: {prazo_dias} dias

Contato da empresa responsável:
- E-mail: {empresa_email}
- Telefone: {empresa_telefone or 'Não informado'}

Acesse sua área no ConectaServ para ver os termos de responsabilidade e privacidade do serviço.

Atenciosamente,
Equipe ConectaServ
"""
    html = f"""<html><body style="font-family: Arial, sans-serif;">
<h2>Proposta aceita!</h2>
<p>Olá, <strong>{freelancer_nome}</strong>!</p>
<p>Sua proposta foi aceita pela empresa <strong>{empresa_nome}</strong> no projeto <strong>{projeto_titulo}</strong>.</p>
<ul>
<li><strong>Valor:</strong> R$ {valor}</li>
<li><strong>Prazo:</strong> {prazo_dias} dias</li>
</ul>
<h3>Contato da empresa</h3>
<ul>
<li><strong>E-mail:</strong> {empresa_email}</li>
<li><strong>Telefone:</strong> {empresa_telefone or 'Não informado'}</li>
</ul>
<p>Acesse o ConectaServ para ver os termos completos do serviço.</p>
</body></html>"""
    return enviar_email(freelancer_email, assunto, corpo, html)
