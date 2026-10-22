"""SQLite persistence, known official notices and transparent status calculations."""

import hashlib
import os
import re
import sqlite3
import threading
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Sao_Paulo')
DB_PATH = os.getenv('RADAR_DB', '/data/radar.sqlite3')
DB_LOCK = threading.RLock()

FIELDS = (
    'title',
    'agency',
    'position',
    'salary_min',
    'salary_max',
    'registration_start',
    'registration_end',
    'exam_date',
    'exam_cities',
    'work_cities',
    'state',
    'official_url',
    'apply_url',
    'notice_url',
    'discovery_url',
    'source',
    'confidence',
    'reviewed',
    'notes',
    'exam_in_sp',
    'work_in_sp',
    'national',
    'favorite',
    'applied',
    'dismissed',
    'status_override',
    'type',
    'observed_at',
)
DATE_FIELDS = ('registration_start', 'registration_end', 'exam_date')
URL_FIELDS = ('official_url', 'apply_url', 'notice_url', 'discovery_url')


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


def today():
    return datetime.now(TZ).date()


def ascii_fold(v):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(v or '')) if not unicodedata.combining(c)).lower()


def is_it(text):
    t = ascii_fold(text)
    words = (
        'tecnologia da informacao',
        'informatica',
        'desenvolvimento de sistemas',
        'desenvolvedor',
        'programador',
        'analista de sistemas',
        'engenharia de software',
        'software',
        'seguranca da informacao',
        'ciencia de dados',
        'cientista de dados',
        'infraestrutura de ti',
        'governanca de ti',
        'analista de ti',
        'tecnico de ti',
        'redes de computadores',
        'banco de dados',
        'computacao',
        'suporte tecnico',
        'sistemas da informacao',
        'cybersecurity',
        'data engineer',
        'sistemas de informacao',
    )
    return any(w in t for w in words) or bool(re.search(r'\bti\b', t))


def fingerprint(title, agency='', position='', official_url=''):
    # Official notice URL wins when available, otherwise stable normalized title+agency.
    raw = '|'.join((agency, title, position, official_url.strip().split('#')[0]))
    return hashlib.sha256(ascii_fold(raw).encode()).hexdigest()[:32]


def connection():
    p = Path(DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=20000')
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_db():
    with DB_LOCK, connection() as db:
        db.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, agency TEXT NOT NULL DEFAULT '', position TEXT NOT NULL DEFAULT '',
            salary_min REAL, salary_max REAL, registration_start TEXT, registration_end TEXT,
            exam_date TEXT, exam_cities TEXT NOT NULL DEFAULT '', work_cities TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '', official_url TEXT NOT NULL DEFAULT '',
            apply_url TEXT NOT NULL DEFAULT '', notice_url TEXT NOT NULL DEFAULT '',
            discovery_url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
            confidence TEXT NOT NULL DEFAULT 'discovery', reviewed INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '', exam_in_sp INTEGER NOT NULL DEFAULT 0,
            work_in_sp INTEGER NOT NULL DEFAULT 0, national INTEGER NOT NULL DEFAULT 0,
            favorite INTEGER NOT NULL DEFAULT 0, applied INTEGER NOT NULL DEFAULT 0,
            dismissed INTEGER NOT NULL DEFAULT 0, status_override TEXT,
            type TEXT NOT NULL DEFAULT 'concurso', observed_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_seen TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_end ON opportunities(registration_end);
          CREATE INDEX IF NOT EXISTS idx_confidence ON opportunities(confidence);
          CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS host_pacing (
            host TEXT PRIMARY KEY, next_at REAL NOT NULL DEFAULT 0,
            blocked_until REAL NOT NULL DEFAULT 0, last_status INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
          );
          CREATE TABLE IF NOT EXISTS notice_evidence (
            opportunity_id INTEGER PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,
            notice_url TEXT NOT NULL, sha256 TEXT NOT NULL, checked_at TEXT NOT NULL,
            role_excerpt TEXT NOT NULL, validated_dates TEXT NOT NULL DEFAULT '',
            validated_salary INTEGER NOT NULL DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS notice_watches (
            page_url TEXT PRIMARY KEY, document_links TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS scan_candidates (
            id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL, source TEXT NOT NULL,
            title TEXT NOT NULL, notice_url TEXT NOT NULL DEFAULT '', state TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL,last_seen TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY, csrf_hash TEXT NOT NULL, expires_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS login_failures (
            ip TEXT PRIMARY KEY, attempts INTEGER NOT NULL, blocked_until TEXT, updated_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
            source TEXT NOT NULL, state TEXT NOT NULL, found INTEGER NOT NULL DEFAULT 0,
            added INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT ''
          );
          CREATE TABLE IF NOT EXISTS watched_pages (
            url TEXT PRIMARY KEY, label TEXT NOT NULL, digest TEXT NOT NULL DEFAULT '',
            checked_at TEXT, changed_at TEXT, error TEXT NOT NULL DEFAULT ''
          );
          CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, unique_key TEXT UNIQUE NOT NULL,
            opportunity_id INTEGER, kind TEXT NOT NULL, text TEXT NOT NULL,
            created_at TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
          );
        """)
        db.commit()


def validate(data, partial=False):
    if not partial and not (data.get('title') or '').strip():
        raise ValueError('Nome/título é obrigatório')
    for k in DATE_FIELDS:
        if data.get(k):
            try:
                date.fromisoformat(data[k])
            except (ValueError, TypeError):
                raise ValueError(f'{k} deve estar no formato YYYY-MM-DD') from None
    for k in URL_FIELDS:
        if data.get(k) and not str(data[k]).startswith(('https://', 'http://')):
            raise ValueError(f'{k} deve começar por https:// ou http://')
    for k in ('salary_min', 'salary_max'):
        if data.get(k) is not None and (not isinstance(data[k], (int, float)) or data[k] < 0):
            raise ValueError(f'{k} deve ser número não negativo')
    if data.get('confidence') is not None and data['confidence'] not in ('official', 'reported', 'discovery'):
        raise ValueError('Origem de confiança inválida')
    if data.get('status_override') and data['status_override'] not in ('announced', 'suspended', 'cancelled', 'open'):
        raise ValueError('Status manual inválido')


def upsert(data, *, enrich_only=True):
    """New discoveries never overwrite already reviewed details or verified dates."""
    validate(data)
    fp = data.get('fingerprint') or fingerprint(
        data['title'], data.get('agency', ''), data.get('position', ''), data.get('official_url', '')
    )
    stamp = now()
    with DB_LOCK, connection() as db:
        previous = db.execute('SELECT * FROM opportunities WHERE fingerprint=?', (fp,)).fetchone()
        if previous:
            payload = {}
            if not enrich_only or not previous['reviewed']:
                for key in FIELDS:
                    if key in data and data[key] is not None and (not enrich_only or previous[key] in (None, '', 0)):
                        payload[key] = data[key]
            payload['last_seen'] = stamp
            if payload:
                payload['updated_at'] = stamp
            keys = list(payload)
            db.execute(
                f'UPDATE opportunities SET {", ".join(k + "=?" for k in keys)} WHERE fingerprint=?',
                [payload[k] for k in keys] + [fp],
            )
            db.commit()
            return previous['id'], False
        values = {k: data[k] for k in FIELDS if k in data}
        values.update(fingerprint=fp, created_at=stamp, updated_at=stamp, last_seen=stamp)
        keys = list(values)
        cur = db.execute(
            f'INSERT INTO opportunities ({", ".join(keys)}) VALUES ({", ".join("?" for _ in keys)})',
            list(values.values()),
        )
        db.commit()
        return cur.lastrowid, True


def fetch_one(oid):
    with connection() as db:
        row = db.execute('SELECT * FROM opportunities WHERE id=?', (oid,)).fetchone()
    return present(attach_proof(dict(row))) if row else None


def compute_status(item, reference=None):
    reference = reference or today()
    if not item.get('document_verified'):
        return 'verify'
    if item.get('status_override') in ('announced', 'suspended', 'cancelled'):
        return item['status_override']
    if item.get('status_override') == 'open' and item.get('confidence') == 'official' and item.get('reviewed'):
        end = item.get('registration_end')
        return 'closed' if end and date.fromisoformat(end) < reference else 'open'
    start, end = item.get('registration_start'), item.get('registration_end')
    # Unverified scraped hints may not pretend to be officially open.
    if item.get('confidence') != 'official' or not item.get('reviewed'):
        return 'verify'
    if end and date.fromisoformat(end) < reference:
        return 'closed'
    if start and date.fromisoformat(start) > reference:
        return 'upcoming'
    if start and end and date.fromisoformat(start) <= reference <= date.fromisoformat(end):
        return 'open'
    return 'verify'


def present(item, reference=None):
    reference = reference or today()
    item['status'] = compute_status(item, reference)
    item['days_left'] = (
        (date.fromisoformat(item['registration_end']) - reference).days
        if item.get('registration_end') and item['status'] in ('open', 'upcoming')
        else None
    )
    item['eligible_sp'] = bool(item.get('exam_in_sp') or item.get('work_in_sp'))
    item['salary_highlight'] = (
        bool(item.get('salary_verified')) and max(item.get('salary_max') or 0, item.get('salary_min') or 0) >= 7000
    )
    item['priority'] = (
        3 if item['status'] == 'open' else 2 if item['status'] == 'upcoming' else 1 if item['status'] == 'verify' else 0
    )
    return item


def query_opportunities(include_dismissed=True):
    with connection() as db:
        rows = db.execute('SELECT * FROM opportunities').fetchall()
    result = [present(attach_proof(dict(r))) for r in rows if include_dismissed or not r['dismissed']]
    return sorted(
        result,
        key=lambda r: (
            -int(r['favorite']),
            -r['priority'],
            r['days_left'] if r['days_left'] is not None else 9999,
            -int(r['salary_highlight']),
            -r['id'],
        ),
    )


def update_opportunity(oid, payload):
    # Any edits to evidence-bearing facts revoke the proof instead of keeping a false 'confirmed' badge.
    restricted = {
        'confidence',
        'reviewed',
        'status_override',
        'official_url',
        'notice_url',
        'apply_url',
        'registration_start',
        'registration_end',
        'exam_date',
        'position',
        'salary_min',
        'salary_max',
        'exam_cities',
        'work_cities',
        'exam_in_sp',
        'work_in_sp',
        'national',
    }
    filtered = {k: v for k, v in payload.items() if k in FIELDS and k not in ('confidence', 'reviewed')}
    if not filtered:
        raise ValueError('Nenhum campo válido')
    validate(filtered, partial=True)
    with DB_LOCK, connection() as db:
        existing = db.execute('SELECT * FROM opportunities WHERE id=?', (oid,)).fetchone()
        if not existing:
            return False
        revoke = any(k in restricted and filtered[k] != existing[k] for k in filtered)
        filtered['updated_at'] = now()
        db.execute(
            f'UPDATE opportunities SET {", ".join(k + "=?" for k in filtered)} WHERE id=?',
            list(filtered.values()) + [oid],
        )
        if revoke:
            db.execute('DELETE FROM notice_evidence WHERE opportunity_id=?', (oid,))
            db.execute("UPDATE opportunities SET reviewed=0,confidence='discovery' WHERE id=?", (oid,))
        db.commit()
    return True


def scan_start(source):
    with DB_LOCK, connection() as db:
        cur = db.execute('INSERT INTO scan_runs(started_at,source,state) VALUES (?, ?, ?)', (now(), source, 'running'))
        db.commit()
        return cur.lastrowid


def scan_finish(run_id, found=0, added=0, error='', state=None):
    with DB_LOCK, connection() as db:
        db.execute(
            'UPDATE scan_runs SET finished_at=?, found=?, added=?, error=?, state=? WHERE id=?',
            (now(), found, added, error[:1200], state or ('failed' if error else 'ok'), run_id),
        )
        db.commit()


def source_health():
    with connection() as db:
        rows = db.execute(
            'SELECT s.* FROM scan_runs s JOIN (SELECT source, MAX(id) AS id FROM scan_runs GROUP BY source) l ON s.id=l.id ORDER BY s.source'
        ).fetchall()
        return [dict(r) for r in rows]


def add_alert(key, kind, msg, oid=None):
    with DB_LOCK, connection() as db:
        cur = db.execute(
            'INSERT OR IGNORE INTO alerts (unique_key,kind,text,opportunity_id,created_at) VALUES (?,?,?,?,?)',
            (key, kind, msg, oid, now()),
        )
        db.commit()
        return bool(cur.rowcount)


def get_alerts(limit=100):
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT ?', (limit,))]


def seed_official():
    """Only records whose salient fields were checked against government/organizer pages 2026-10-16.
    Never clobber user edits on restarts. Exam date IFSP deliberately unset without primary confirmation.
    """
    seeds = [
        {
            'title': 'CGU 2026 — Auditor TI · Desenvolvimento de Sistemas',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Desenvolvimento de Sistemas',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'notice_url': 'https://www.gov.br/cgu/pt-br/acesso-a-informacao/concursos',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Desenvolvimento de Sistemas; outras 20 em Ciência de Dados e Infraestrutura. Prova em todas as capitais. Inscrição R$ 170; conferir retificações.',
        },
        {
            'title': 'CGU 2026 — Auditor TI · Ciência de Dados',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Ciência de Dados',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Ciência de Dados; lotação em Brasília; confirmar pré-requisitos no edital.',
        },
        {
            'title': 'CGU 2026 — Auditor TI · Infraestrutura',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Infraestrutura de TI',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Infraestrutura de TI; lotação em Brasília.',
        },
        {
            'title': 'IFSP 183/2026 — Professor de Informática (Campus São Paulo)',
            'agency': 'Instituto Federal de São Paulo (IFSP)',
            'position': 'Professor EBTT — Informática',
            'salary_min': 6397.19,
            'salary_max': 7356.77,
            'registration_end': '2026-11-17',
            'exam_cities': 'Ver edital/convocação',
            'work_cities': 'São Paulo/SP',
            'state': 'SP',
            'exam_in_sp': 0,
            'work_in_sp': 1,
            'national': 0,
            'reviewed': 1,
            'confidence': 'official',
            'status_override': 'open',
            'official_url': 'https://spo.ifsp.edu.br/destaques/4723-edital-ifsp-%E2%80%94-concurso-p%C3%BAblico-para-contrata%C3%A7%C3%A3o-de-professores',
            'apply_url': 'https://concursopublico.ifsp.edu.br/editais/edital-1832026-docentes',
            'source': 'IFSP (fonte oficial)',
            'notes': 'Prazo até 17/11/2026 confirmado. Salário-base de acordo com página oficial, antes de adicionais/titulação. Início de inscrição e cidade exata da prova exigem checagem no edital. Site oficial confirma que as inscrições estão abertas; a marcação é válida apenas até o prazo de encerramento.',
        },
    ]
    for seed in seeds:
        # Distinguish different CGU specializations even though URL is identical.
        seed['fingerprint'] = hashlib.sha256(f'official2026|{seed["title"]}'.encode()).hexdigest()[:32]
        upsert(seed)


def attach_proof(item):
    with connection() as db:
        row = db.execute('SELECT * FROM notice_evidence WHERE opportunity_id=?', (item['id'],)).fetchone()
    item['document_verified'] = bool(row)
    item['salary_verified'] = bool(row and row['validated_salary'])
    item['proof'] = (
        {k: row[k] for k in ('notice_url', 'sha256', 'checked_at', 'role_excerpt', 'validated_dates')} if row else None
    )
    return item


def record_proof(oid, proof, details):
    # Only the dedicated verification endpoint may establish confirmed status.
    with DB_LOCK, connection() as db:
        old = db.execute('SELECT id FROM opportunities WHERE id=?', (oid,)).fetchone()
        if old is None:
            raise ValueError('Concurso não encontrado')
        dates = ','.join(k for k in DATE_FIELDS if details.get(k))
        salary = int(any(details.get(k) is not None for k in ('salary_min', 'salary_max')))
        db.execute(
            """INSERT INTO notice_evidence(opportunity_id,notice_url,sha256,checked_at,role_excerpt,validated_dates,validated_salary)
                     VALUES(?,?,?,?,?,?,?) ON CONFLICT(opportunity_id) DO UPDATE SET
                     notice_url=excluded.notice_url,sha256=excluded.sha256,checked_at=excluded.checked_at,
                     role_excerpt=excluded.role_excerpt,validated_dates=excluded.validated_dates,validated_salary=excluded.validated_salary""",
            (oid, proof.url, proof.sha256, now(), proof.role_excerpt, dates, salary),
        )
        db.execute(
            "UPDATE opportunities SET confidence='official',reviewed=1,notice_url=?,updated_at=?,status_override=CASE WHEN status_override='open' THEN NULL ELSE status_override END WHERE id=?",
            (proof.url, now(), oid),
        )
        db.commit()


def upsert_candidate(url, source, title, notice_url='', state='pending', detail=''):
    with DB_LOCK, connection() as db:
        db.execute(
            """INSERT INTO scan_candidates(url,source,title,notice_url,state,detail,first_seen,last_seen)
           VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET notice_url=excluded.notice_url,
           state=excluded.state, detail=excluded.detail, last_seen=excluded.last_seen""",
            (url, source, title[:240], notice_url, state, detail[:500], now(), now()),
        )
        db.commit()


def candidates():
    with connection() as db:
        return [dict(r) for r in db.execute('SELECT * FROM scan_candidates ORDER BY last_seen DESC LIMIT 200')]
