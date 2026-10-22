from app import collectors, evidence, verification
from app import repository as repo

PAGE = 'https://www.gov.br/orgao/concurso-2026'
EDITAL = 'https://www.gov.br/orgao/arquivos/edital-abertura.html'
EDITAL_TEXT = (
    '<html><body><h1>EDITAL Nº 1/2026 – CONCURSO PÚBLICO</h1>'
    '<p>O órgão torna pública a abertura de concurso público para o cargo de Analista de Sistemas, '
    'área de tecnologia da informação, com lotação em Brasília/DF.</p>'
    '<p>Analista de Sistemas – remuneração inicial R$ 9.000,00 para jornada de 40 horas semanais.</p>'
    '<p>Período de inscrições: de 20 de outubro de 2026 a 18 de novembro de 2026, pela internet.</p>'
    '<p>A prova objetiva será realizada em 24/01/2027 em todas as 27 capitais do país.</p>'
    '<p>Demais regras, conteúdos programáticos e cronograma constam dos anexos deste edital.</p>'
    '</body></html>'
)


def fake_site(monkeypatch, pages):
    calls = []

    def fetch(url, session=None):
        calls.append(url)
        if url not in pages:
            raise ValueError('HTTP 404')
        return url, pages[url].encode(), 'text/html'

    monkeypatch.setattr(evidence, 'fetch_official', fetch)
    return calls


def new_item(**extra):
    data = {
        'title': 'Órgão 2026 — Analista de Sistemas',
        'agency': 'Órgão',
        'position': 'Analista de Sistemas',
        'official_url': PAGE,
        'notice_url': PAGE,
        'registration_start': '2026-10-20',
        'registration_end': '2026-11-18',
        'exam_date': '2027-01-24',
        'salary_min': 9000.0,
        'salary_max': 9000.0,
        'confidence': 'official',
        'reviewed': 1,
    }
    data.update(extra)
    oid, _ = repo.upsert(data)
    return oid


def test_finds_the_edital_linked_from_the_contest_page(monkeypatch):
    calls = fake_site(
        monkeypatch,
        {
            PAGE: f'<a href="/orgao/noticia">Notícia</a><a href="{EDITAL}">Edital de abertura</a>',
            EDITAL: EDITAL_TEXT,
        },
    )
    oid = new_item(exam_in_sp=1)
    item, warnings = verification.verify(oid)
    assert warnings == []
    assert item['document_verified'] and item['salary_verified']
    assert item['notice_url'] == EDITAL
    assert item['status'] == 'upcoming'
    assert calls == [PAGE, EDITAL]
    assert verification.last_result(oid)['ok']


def test_unsupported_fact_is_removed_instead_of_blocking(monkeypatch):
    fake_site(monkeypatch, {EDITAL: EDITAL_TEXT})
    oid = new_item(notice_url=EDITAL, official_url=EDITAL, salary_min=12000.0, salary_max=12000.0)
    item, warnings = verification.verify(oid)
    assert item['document_verified']
    assert warnings == ['salário mínimo', 'salário máximo']
    assert item['salary_min'] is None and not item['salary_verified']
    assert item['registration_end'] == '2026-11-18'
    assert '12000.0' in item['notes']


def test_failure_is_remembered_and_retried_later(monkeypatch):
    fake_site(monkeypatch, {PAGE: '<p>Sem edital publicado ainda.</p>'})
    oid = new_item()
    assert verification.auto_verify() == (0, 1)
    item = repo.fetch_one(oid)
    assert not item['document_verified']
    assert item['last_check']['ok'] is False
    # not retried right away
    assert not verification.due(item)


def test_auto_verify_skips_closed_and_non_it(monkeypatch):
    calls = fake_site(monkeypatch, {})
    new_item(title='Encerrado', registration_start='2026-09-01', registration_end='2026-10-01', exam_date=None)
    new_item(title='Sem TI', position='Auxiliar Administrativo')
    assert verification.auto_verify() == (0, 0)
    assert calls == []


def test_cebraspe_hashed_pdf_links_count_as_opening_edital():
    url = 'https://cdn.cebraspe.org.br/concursos/cgu_26_affc/arquivos/C7A60D15CB0D.pdf'
    assert evidence.official_url(url)
    assert collectors.notice_anchor('ED 1 CGU AFFC 2026 ABERTURA', url)
    assert not collectors.notice_anchor('ED 5 CGU AFFC 2026 RESULTADO FINAL', url)
    assert not collectors.notice_anchor('Faixa salarial', 'https://www.gov.br/salary.pdf')


def test_exam_in_all_capitals_includes_sao_paulo():
    text = 'As provas serão realizadas nas 27 capitais das unidades da federação.'
    assert evidence.location_supported(text, 'São Paulo', 'exam')
    assert not evidence.location_supported('Lotação em Brasília.', 'São Paulo', 'exam')
