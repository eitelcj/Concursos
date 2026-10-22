"""Optional outbound email and Telegram digest. Never requires paid services."""

import smtplib
from email.message import EmailMessage

import requests

from . import config, database


def dispatch():
    with database.connection() as db:
        pending = [dict(r) for r in db.execute('SELECT * FROM alerts WHERE notified=0 ORDER BY id LIMIT 100')]
    if not pending:
        return {'sent': 0, 'reason': 'no pending events'}
    lines = [f'• {a["text"]}' for a in pending]
    body = f'{config.app_name()} — alertas pendentes\n\n' + '\n\n'.join(lines)
    sent_to = []
    mail = config.smtp()
    host, sender, to = mail['host'], mail['sender'], mail['to']
    if host and sender and to:
        msg = EmailMessage()
        msg['Subject'] = f'[{config.app_name()}] {len(pending)} aviso(s) de concurso'
        msg['From'] = sender
        msg['To'] = to
        msg.set_content(body)
        port = mail['port']
        with smtplib.SMTP_SSL(host, port, timeout=20) if port == 465 else smtplib.SMTP(host, port, timeout=20) as smtp:
            if port != 465 and mail['starttls']:
                smtp.starttls()
            if mail['username']:
                smtp.login(mail['username'], mail['password'])
            smtp.send_message(msg)
        sent_to.append('email')
    tg = config.telegram()
    token, chat = tg['token'], tg['chat_id']
    if token and chat:
        msg = f'🔔 {config.app_name()}\n\n' + '\n\n'.join(lines)
        # Telegram API text limit 4096; transmit chunks preserving boundaries.
        for i in range(0, len(msg), 3800):
            resp = requests.post(
                'https://api.telegram.org/bot' + token + '/sendMessage',
                json={'chat_id': chat, 'text': msg[i : i + 3800], 'disable_web_page_preview': True},
                timeout=20,
            )
            resp.raise_for_status()
        sent_to.append('telegram')
    if sent_to:
        with database.DB_LOCK, database.connection() as db:
            db.executemany('UPDATE alerts SET notified=1 WHERE id=?', [(a['id'],) for a in pending])
            db.commit()
    return {'sent': len(pending) if sent_to else 0, 'channels': sent_to}
