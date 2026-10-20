"""Password-only UI, optional encrypted TOTP MFA, server-side sessions and throttling."""
import base64
import hashlib
import hmac
import io
import os
import secrets
import time
from datetime import datetime,timedelta

import qrcode
from cryptography.fernet import Fernet,InvalidToken
from . import core

COOKIE='radar_session'
DAYS=7
MIN_PASSWORD_LENGTH=7

def password_configured():
    real=os.getenv('RADAR_PASSWORD','')
    return len(real)>=MIN_PASSWORD_LENGTH and 'SUBSTITUA' not in real.upper()

def digest(s):return hashlib.sha256(s.encode()).hexdigest()

def password_ok(password):
    real=os.getenv('RADAR_PASSWORD','')
    return bool(password_configured() and hmac.compare_digest(digest(password),digest(real)))

def fernet():
    raw=os.getenv('RADAR_MFA_ENCRYPTION_KEY','')
    if not raw:raise ValueError('Configure RADAR_MFA_ENCRYPTION_KEY antes de ativar MFA')
    try:return Fernet(raw.encode())
    except (ValueError,TypeError) as ex:raise ValueError('Chave Fernet inválida') from ex

def setting(key):
    with core.connection() as db:
        r=db.execute('SELECT value FROM app_settings WHERE key=?',(key,)).fetchone()
    return r['value'] if r else ''

def put(key,val):
    with core.DB_LOCK,core.connection() as db:
        db.execute('INSERT INTO app_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,val))
        db.commit()

def delete(key):
    with core.DB_LOCK,core.connection() as db:
        db.execute('DELETE FROM app_settings WHERE key=?',(key,));db.commit()

def mfa_enabled():return bool(setting('mfa_secret'))

def totp(secret, at=None):
    t=int((at if at is not None else time.time())//30)
    key=base64.b32decode(secret,casefold=True)
    raw=hmac.new(key,t.to_bytes(8,'big'),hashlib.sha1).digest()
    index=raw[-1]&15
    return str((int.from_bytes(raw[index:index+4],'big')&0x7fffffff)%1_000_000).zfill(6)

def check_totp(secret,code):
    if not isinstance(code,str) or not code.isdigit() or len(code)!=6:return False
    t=time.time()
    return any(hmac.compare_digest(totp(secret,t+30*n),code) for n in (-1,0,1))

def mfa_check(code,consume_recovery=False):
    enc=setting('mfa_secret')
    if not enc:return True
    secret=fernet().decrypt(enc.encode()).decode()
    if check_totp(secret,str(code)):return True
    if not consume_recovery:return False
    key=digest(str(code).strip().upper())
    with core.DB_LOCK,core.connection() as db:
        val=db.execute("SELECT value FROM app_settings WHERE key='mfa_recovery'").fetchone()
        saved=val[0].split(',') if val else []
        if key in saved:
            saved.remove(key)
            db.execute("UPDATE app_settings SET value=? WHERE key='mfa_recovery'",(','.join(saved),));db.commit();return True
    return False

def begin_mfa():
    secret=base64.b32encode(secrets.token_bytes(20)).decode().strip('=')
    put('mfa_pending',fernet().encrypt(secret.encode()).decode())
    uri=f'otpauth://totp/SpeedLora%20Concurso%20Radar:admin?secret={secret}&issuer=SpeedLora%20Concurso%20Radar&algorithm=SHA1&digits=6&period=30'
    img=qrcode.make(uri)
    file=io.BytesIO();img.save(file,format='PNG')
    return {'secret':secret,'qr':'data:image/png;base64,'+base64.b64encode(file.getvalue()).decode()}

def finish_mfa(code):
    enc=setting('mfa_pending')
    if not enc:raise ValueError('Configuração MFA não iniciada')
    secret=fernet().decrypt(enc.encode()).decode()
    if not check_totp(secret,str(code)):raise ValueError('Código inválido ou expirado')
    codes=['-'.join((secrets.token_hex(4).upper(),secrets.token_hex(4).upper())) for _ in range(8)]
    put('mfa_recovery',','.join(digest(c) for c in codes))
    put('mfa_secret',enc)
    delete('mfa_pending')
    return codes

def disable_mfa(password,code):
    if not password_ok(password) or not mfa_check(str(code),True):return False
    delete('mfa_secret');delete('mfa_pending');delete('mfa_recovery')
    return True

def can_attempt(ip):
    with core.connection() as db:r=db.execute('SELECT * FROM login_failures WHERE ip=?',(ip,)).fetchone()
    return not (r and r['blocked_until'] and r['blocked_until']>core.now())

def failed(ip):
    with core.DB_LOCK,core.connection() as db:
        row=db.execute('SELECT * FROM login_failures WHERE ip=?',(ip,)).fetchone()
        attempts=(row['attempts'] if row else 0)+1
        if row and (datetime.fromisoformat(core.now())-datetime.fromisoformat(row['updated_at'])).total_seconds()>900:
            attempts=1
        blocked=(datetime.now(core.TZ)+timedelta(minutes=15)).isoformat(timespec='seconds') if attempts>=5 else None
        db.execute('''INSERT INTO login_failures(ip,attempts,blocked_until,updated_at) VALUES(?,?,?,?)
          ON CONFLICT(ip) DO UPDATE SET attempts=excluded.attempts,blocked_until=excluded.blocked_until,updated_at=excluded.updated_at''',
          (ip,attempts,blocked,core.now()))
        db.commit()

def successful(ip):
    with core.DB_LOCK,core.connection() as db:
        db.execute('DELETE FROM login_failures WHERE ip=?',(ip,));db.commit()

def new_session():
    token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
    exp=(datetime.now(core.TZ)+timedelta(days=DAYS)).isoformat(timespec='seconds')
    with core.DB_LOCK,core.connection() as db:
        db.execute('INSERT INTO auth_sessions(token_hash,csrf_hash,expires_at) VALUES (?,?,?)',(digest(token),digest(csrf),exp))
        db.execute('DELETE FROM auth_sessions WHERE expires_at<?',(core.now(),))
        db.commit()
    return token,csrf

def validate_session(token):
    if not token:return None
    with core.connection() as db:
        row=db.execute('SELECT * FROM auth_sessions WHERE token_hash=?',(digest(token),)).fetchone()
    return row if row and row['expires_at']>core.now() else None

def logout(token):
    if token:
        with core.DB_LOCK,core.connection() as db:
            db.execute('DELETE FROM auth_sessions WHERE token_hash=?',(digest(token),));db.commit()

def csrf_valid(session,csrf):
    return bool(session and csrf and hmac.compare_digest(session['csrf_hash'],digest(csrf)))
