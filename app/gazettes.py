"""IT contests found in official municipal gazettes through the Querido Diário public API.

Many contests organised by banks that refuse automated access (Vunesp, for example)
are published as an edital or an extract in the municipality's Diário Oficial.
Querido Diário (Open Knowledge Brasil) indexes those gazettes and offers a public
search API meant for this kind of use. Results are discoveries for review: the
gazette is not the edital, so nothing found here is marked as confirmed.
"""

import hashlib
import html
import json
import logging
import re
from datetime import timedelta
from urllib.parse import urlencode

from . import clock, evidence, polite, textnorm
from . import repository as repo

LOG = logging.getLogger('radar.gazettes')
# One simple query per IT term. A single query with operators made the public API
# answer HTTP 500, and narrow queries keep each search light for their servers.
TERMS = (
    'tecnologia da informação',
    'analista de sistemas',
    'informática',
    'desenvolvimento de sistemas',
    'ciência de dados',
    'segurança da informação',
    'programador',
    'banco de dados',
)
LOOKBACK_DAYS = 21
PAGE_SIZE = 20
MAX_NEW_PER_RUN = 25
# Publications about contests that are already over (or that are not openings).
SKIP = (
    'resultado',
    'homologacao',
    'homologa',
    'convocacao',
    'convoca ',
    'gabarito',
    'nomeacao',
    'nomear',
    'nomeia',
    'classificacao final',
    'posse',
    'exoneracao',
)
ROLE = re.compile(
    r'\b((?:analista|t[ée]cnico|assistente|auxiliar|agente|programador|desenvolvedor|especialista|engenheiro|'
    r'professor|tecn[óo]logo|operador)[^\n.;:()]{0,60}?'
    r'(?:inform[áa]tica|tecnologia da informa[çc][ãa]o|sistemas|\bti\b|dados|computa[çc][ãa]o|software|redes))',
    re.I,
)
LINK = re.compile(r'(?:https?://|www\.)[^\s<>"\')\],;]+', re.I)


def clean(text):
    text = re.sub(r'<[^>]+>', ' ', html.unescape(str(text or '')))
    return re.sub(r'\s+', ' ', text).strip()


def relevant(excerpt):
    """An excerpt about an IT contest that is open or about to open."""
    t = textnorm.fold(excerpt)
    if 'concurso' not in t and 'processo seletivo' not in t:
        return False
    if not textnorm.is_it(excerpt):
        return False
    if any(word in t for word in SKIP):
        return False
    return any(word in t for word in ('edital', 'abertura', 'inscri'))


def role_of(text):
    match = ROLE.search(text)
    if not match:
        return ''
    role = match.group(1).strip(' -–')
    return role[:1].upper() + role[1:]


def official_links(text):
    links = []
    for raw in LINK.findall(text):
        url = raw.rstrip('.')
        if url.lower().startswith('www.'):
            url = 'https://' + url
        url = 'https://' + url.split('://', 1)[1]
        if evidence.official_url(url) and url not in links:
            links.append(url)
    return links


def search_urls(source):
    since = (clock.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    base = source.url.split('?', 1)[0]
    for term in TERMS:
        params = {
            'querystring': f'"concurso público" "{term}"',
            'published_since': since,
            'excerpt_size': 500,
            'number_of_excerpts': 2,
            'size': PAGE_SIZE,
        }
        yield base + '?' + urlencode(params)


def fetch_gazettes(source, session):
    """Run every term; a failing search does not lose the others. Returns (gazettes, errors)."""
    found, errors, seen = [], [], set()
    for url in search_urls(source):
        try:
            _, raw, _ = evidence.fetch_official(url, session, data_api=True)
            data = json.loads(raw.decode('utf-8'))
        except polite.DomainCoolingDown:
            raise
        except json.JSONDecodeError:
            errors.append('resposta não é JSON')
            continue
        except Exception as err:
            # requests puts the whole (long) URL in the message; the term is enough.
            errors.append(str(err).split(' for url:')[0])
            continue
        for gazette in data.get('gazettes') or []:
            key = gazette.get('url') or gazette.get('txt_url')
            if key and key not in seen:
                seen.add(key)
                found.append(gazette)
    return found, errors


def scan_source(source, session=None):
    sid = repo.scan_start(source.name)
    found = added = 0
    try:
        results, errors = fetch_gazettes(source, session)
        if errors and len(errors) == len(TERMS):
            raise ValueError(f'API do Querido Diário falhou em todas as buscas: {errors[0]}')
        for gazette in results:
            uf = str(gazette.get('state_code') or '').upper()
            if source.uf and uf != source.uf:
                continue
            gazette_url = str(gazette.get('url') or gazette.get('txt_url') or '')
            if not gazette_url.startswith('https://'):
                continue
            excerpts = [clean(e) for e in gazette.get('excerpts') or []]
            hits = [e for e in excerpts if relevant(e)]
            if not hits:
                continue
            found += 1
            town = clean(gazette.get('territory_name')) or 'Município'
            date = str(gazette.get('date') or '')[:10]
            when = '/'.join(reversed(date.split('-'))) if date else ''
            text = ' '.join(hits)
            role = role_of(text)
            links = official_links(text)
            title = f'{town}/{uf} — concurso com vaga de TI (Diário Oficial de {when})'
            repo.upsert_candidate(gazette_url, source.name, title, '', state='gazette_ti', detail=hits[0][:300])
            if added >= MAX_NEW_PER_RUN:
                continue
            item = {
                'title': title,
                'agency': f'{town}/{uf}',
                'position': role,
                'state': uf if re.fullmatch(r'[A-Z]{2}', uf) else '',
                'source': source.name,
                'official_url': links[0] if links else gazette_url,
                'notice_url': next((u for u in links if u.lower().endswith('.pdf')), ''),
                'confidence': 'discovery',
                'reviewed': 0,
                'notes': (
                    f'Encontrado no Diário Oficial de {town}/{uf} de {when}, via Querido Diário. '
                    f'Trecho: “{hits[0][:400]}”. Diário: {gazette_url}. '
                    'Confira o edital oficial antes de se inscrever.'
                ),
                'fingerprint': hashlib.sha256(('gazette|' + gazette_url).encode()).hexdigest()[:32],
            }
            oid, created = repo.upsert(item)
            if created:
                added += 1
                repo.add_alert(
                    'new-gazette:' + item['fingerprint'],
                    'new',
                    f'Possível concurso de TI no Diário Oficial de {town}/{uf}: {role or "cargo a conferir"}.',
                    oid,
                )
        if errors:
            repo.scan_finish(
                sid,
                found,
                added,
                error=f'Cobertura PARCIAL: {len(errors)} de {len(TERMS)} buscas falharam ({errors[0]})',
            )
            return found, added, False
        repo.scan_finish(sid, found, added)
        return found, added, True
    except polite.DomainCoolingDown as ex:
        repo.scan_finish(sid, found, added, error=str(ex), state='blocked')
        return found, added, False
    except Exception as ex:
        LOG.warning('Querido Diário: %s', ex)
        repo.scan_finish(sid, found, added, error=str(ex))
        return found, added, False
