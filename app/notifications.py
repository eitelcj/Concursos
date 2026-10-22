"""Optional outbound email and Telegram digest. Never requires paid services."""

import os
import smtplib
from email.message import EmailMessage

import requests

from . import core


def dispatch():
    with core.connection() as db:
        pending = [dict(r) for r in db.execute('SELECT * FROM alerts WHERE notified=0 ORDER BY id LIMIT 100')]
    if not pending:
        return {'sent': 0, 'reason': 'no pending events'}
    lines = [f'• {a["text"]}' for a in pending]
    body = 'SpeedLora Concurso Radar — alertas pendentes\n\n' + '\n\n'.join(lines)
    sent_to = []
    host, sender, to = (os.getenv(k, '') for k in ('SMTP_HOST', 'ALERT_EMAIL_FROM', 'ALERT_EMAIL_TO'))
    if host and sender and to:
        msg = EmailMessage()
        msg['Subject'] = f'[Concurso Radar] {len(pending)} aviso(s) de concurso'
        msg['From'] = sender
        msg['To'] = to
        msg.set_content(body)
        port = int(os.getenv('SMTP_PORT', '587'))
        with smtplib.SMTP_SSL(host, port, timeout=20) if port == 465 else smtplib.SMTP(host, port, timeout=20) as smtp:
            if port != 465 and os.getenv('SMTP_STARTTLS', '1') == '1':
                smtp.starttls()
            if os.getenv('SMTP_USERNAME'):
                smtp.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD', ''))
            smtp.send_message(msg)
        sent_to.append('email')
    token, chat = os.getenv('TELEGRAM_BOT_TOKEN', ''), os.getenv('TELEGRAM_CHAT_ID', '')
    if token and chat:
        msg = '🔔 Concurso Radar\n\n' + '\n\n'.join(lines)
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
        with core.DB_LOCK, core.connection() as db:
            db.executemany('UPDATE alerts SET notified=1 WHERE id=?', [(a['id'],) for a in pending])
            db.commit()
    return {'sent': len(pending) if sent_to else 0, 'channels': sent_to}
