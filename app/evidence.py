"""Fail-closed proof checks. Official HTTPS + original edital + role-specific evidence.
No headline, salary band from a landing page or mere organizer domain is proof.
"""
import hashlib
import io
import ipaddress
import re
import socket
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from . import polite

# Exact hosts or government / public-school namespaces. No partial substring matches.
ORGANIZERS = frozenset({
    'www.vunesp.com.br','vunesp.com.br','documento.vunesp.com.br',
    'www.concursosfcc.com.br','concursosfcc.com.br',
    'conhecimento.fgv.br','portal.conhecimento.fgv.br','www.cebraspe.org.br','cebraspe.org.br',
    'www.ibam-concursos.org.br','ibam-concursos.org.br',
    'abcp.selecao.net.br', 'www.ibamsp-concursos.org.br',
})
EDU_HOSTS=('ifsp.edu.br','unicamp.br','usp.br','unesp.br','ufscar.br','unifesp.br','ufabc.edu.br','ufscar.edu.br')
MAX_BYTES = 12_000_000
UA = 'SpeedLoraConcursoRadar/2.0 (official-notice verification, 8 scans/day)'

def official_host(host):
    host = (host or '').lower().rstrip('.')
    return (host in ORGANIZERS or host.endswith(('.gov.br','.jus.br','.leg.br'))
            or any(host==ed or host.endswith('.'+ed) for ed in EDU_HOSTS))

def official_url(url):
    try:
        p=urlparse(str(url))
        return p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443) and official_host(p.hostname)
    except (ValueError, TypeError):
        return False

def guard_public(host):
    # Prevent server-side requests to internal/private addresses, including DNS rebinding.
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    for a in addresses:
        ip=ipaddress.ip_address(a[4][0])
        if not ip.is_global:
            raise ValueError('Destino de rede não público')

def fetch_official(url, session=None, *, pace=None):
    """Fetch a real official URL; refuse forbidden domains/redirects and obey 403/429.

    Injectable sessions default to unpaced for deterministic unit tests. Real
    worker and API traffic is paced and shares the persisted backoff table.
    """
    if not official_url(url): raise ValueError('Endereço fora dos domínios oficiais permitidos')
    if pace is None:
        pace = session is None
    client = session or requests.Session()
    current = url
    for redirects in range(5):
        if not official_url(current):
            raise ValueError('Redirecionamento para destino não oficial')
        host = urlparse(current).hostname
        if session is None:
            guard_public(host)
        from contextlib import nullcontext
        with polite.request_lane(host) if pace else nullcontext():
            response = client.get(current, headers={'User-Agent': UA, 'Accept': 'text/html,application/pdf;q=0.9,*/*;q=0.5'},
                                  timeout=(8, 25), allow_redirects=False, stream=True)
            if response.status_code in (403, 429):
                code = response.status_code
                retry = response.headers.get('Retry-After')
                response.close()
                # Tests may supply a fake session; keep 403/429 handling in tests
                # but do not mutate persisted limiter state for unpaced sessions.
                if pace:
                    raise polite.reject(host, code, retry)
                raise ValueError(f'HTTP {code}: acesso recusado pelo domínio oficial {host}')
            if response.status_code in (301, 302, 303, 307, 308):
                target = requests.compat.urljoin(response.url, response.headers.get('location', ''))
                response.close()
                if not official_url(target):
                    raise ValueError('Redirecionamento para destino não oficial')
                current = target
                continue
            try:
                response.raise_for_status()
                size = 0
                parts = []
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('Documento excede 12 MB')
                    parts.append(chunk)
                data = b''.join(parts)
                mime = response.headers.get('Content-Type', '').lower().split(';')[0]
                return response.url, data, mime
            finally:
                response.close()
    raise ValueError('Muitos redirecionamentos')

def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s or '')) if not unicodedata.combining(c)).lower()

def extract(url, raw, mime):
    if raw.startswith(b'%PDF'):
        reader=PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:raise ValueError('PDF protegido')
        if len(reader.pages)>500:raise ValueError('PDF muito longo')
        return '\n'.join((p.extract_text() or '') for p in reader.pages)[:1_000_000], 'pdf'
    if mime in ('text/html','application/xhtml+xml') or raw.lstrip().lower().startswith((b'<!doctype html',b'<html')):
        soup=BeautifulSoup(raw,'html.parser')
        for e in soup(['script','style','footer','nav','header']):e.decompose()
        return soup.get_text(' ',strip=True)[:1_000_000], 'html'
    raise ValueError('Tipo de documento não reconhecido')

@dataclass
class Proof:
    url: str
    sha256: str
    text: str
    kind: str
    role_excerpt: str

IT_KEYWORDS=('tecnologia da informacao','informatica','analista de sistemas','desenvolvimento de sistemas',
             'desenvolvedor','programador','software','ciencia de dados','infraestrutura de ti',
             'analista de ti','suporte tecnico','banco de dados','redes de computadores',
             'seguranca da informacao','computacao','engenheiro de dados','sistemas de informacao')

def notice_proof(url, *, session=None, position=''):
    # PDFs are preferred. Explicitly titled official edital HTML is acceptable only if text is substantive.
    resolved,raw,mime=fetch_official(url,session)
    text,kind=extract(resolved,raw,mime)
    norm=fold(text)
    if len(norm)<350:raise ValueError('Edital sem texto legível; revisão manual obrigatória')
    if not ('edital' in norm and ('concurso publico' in norm or 'processo seletivo publico' in norm)):
        raise ValueError('O arquivo não demonstra ser edital de concurso público')
    opening=bool(re.search(r'edital\s+(?:n[ºo°.]?\s*0?1\b|de\s+abertura|de\s+inscricoes|0?1\s*/\s*20\d\d)',norm[:5000]))
    if not opening:
        raise ValueError('Não foi comprovado que o documento seja o edital inicial de abertura')
    if kind=='html' and 'edital' not in urlparse(resolved).path.lower():
        raise ValueError('Página HTML não identifica documento edital no endereço')
    if not any(w in norm for w in IT_KEYWORDS):
        raise ValueError('Edital sem cargo de TI identificável')
    # Position-specific gate. Reject when role absent, do not borrow salary of a different job.
    if position:
        pos=fold(position)
        significant=[w for w in re.findall(r'[a-z]{4,}',pos) if w not in ('cargo','concurso','publico','federal','superior','controle','especialidade')]
        if not significant:
            raise ValueError('Cargo pouco específico para validação')
        # Require nearby words of the actual role; a single generic IT keyword elsewhere is insufficient.
        windows=[norm[max(0,m.start()-100):m.end()+240] for m in re.finditer(re.escape(significant[0]),norm)]
        if not any(sum(w in window for w in significant[:6]) >= min(2,len(significant)) for window in windows):
            raise ValueError('Cargo/especialidade específicos não encontrados juntos no edital')
    hits=[m for m in re.finditer('|'.join(map(re.escape,IT_KEYWORDS)),norm)]
    excerpt=norm[max(0,hits[0].start()-130):hits[0].end()+220] if hits else ''
    return Proof(resolved,hashlib.sha256(raw).hexdigest(),text,kind,excerpt[:350])

def date_supported(text, iso, kind='registration_end'):
    if not iso:return True
    y,m,d=iso.split('-')
    content=fold(text)
    for match in re.finditer(r'(?<!\d)'+re.escape(d)+'[./-]'+re.escape(m)+'[./-]'+re.escape(y)+r'(?!\d)',content):
        around=content[max(0,match.start()-500):match.end()+500]
        context=('inscri','periodo de inscricao','cronograma') if kind.startswith('registration') else ('prova','cronograma')
        if any(word in around for word in context):return True
    return False

def money_supported_near_role(text, salary, role):
    if salary is None:return True
    # Must find the salary on the same extracted line as the specific job.
    # This intentionally rejects edital-wide salary bands.
    if not role:return False
    rolewords=[w for w in re.findall('[a-z]{4,}',fold(role)) if w not in ('cargo','concurso','publico','especialidade','superior')]
    if not rolewords:return False
    br=f'{salary:,.2f}'.replace(',','_').replace('.',',').replace('_','.')
    variants=(br,br.replace('.',''),f'{salary:.2f}')
    for line in fold(text).splitlines():
        for variant in variants:
            for m in re.finditer(re.escape(variant),line):
                # Nearby role, not any other role elsewhere in a long sentence.
                previous=line[max(0,m.start()-140):m.start()]
                if sum(w in previous for w in rolewords[:5])<min(2,len(rolewords)):
                    continue
                # If another explicitly labeled cargo occurs AFTER the target role,
                # we cannot attribute the salary with confidence.
                first=previous.rfind(rolewords[0])
                if first<0:continue
                intervening=previous[first+len(rolewords[0]):]
                if re.search(r'\bcargo\s+[a-z]{4,}',intervening):continue
                return True
    return False

def location_supported(text, city, kind):
    if not city:return True
    norm=fold(text)
    tokens=[t for t in re.findall(r'[a-z]{4,}',fold(city)) if t not in ('regiao','estado','brasil','cidade')]
    if not tokens:return False
    flags=('local de prova','cidades de realizacao','aplicacao da prova','provas serao','prova objetiva') if kind=='exam' else ('lotacao','local de trabalho','localidade','unidade de exercicio','municipio')
    for m in re.finditer(re.escape(tokens[0]),norm):
        window=norm[max(0,m.start()-250):m.end()+250]
        if any(f in window for f in flags):return True
    return False

def check_assertions(proof, data):
    for k in ('registration_start','registration_end','exam_date'):
        if data.get(k) and not date_supported(proof.text,data[k],k):
            raise ValueError(f'{k}: data não localizada no documento. Anexe retificação oficial ou deixe em branco.')
    if data.get('exam_in_sp') and not location_supported(proof.text,'São Paulo','exam'):
        raise ValueError('Prova em SP ainda não demonstrada no edital')
    if data.get('work_in_sp') and not location_supported(proof.text,'São Paulo','work'):
        raise ValueError('Trabalho em SP ainda não demonstrado no edital')
    for k in ('salary_min','salary_max'):
        if data.get(k) is not None and not money_supported_near_role(proof.text,float(data[k]),data.get('position','')):
            raise ValueError(f'{k}: remuneração não comprovada junto ao cargo de TI no edital')
