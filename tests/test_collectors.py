from datetime import datetime

from app import collectors, evidence
from app import repository as repo
from app.worker import slot


def test_catalog_has_only_official_sources():
    assert len(collectors.SOURCES) >= 8
    assert all(evidence.official_url(s.url) for s in collectors.SOURCES)
    assert not any('google' in s.url or 'pciconcursos' in s.url for s in collectors.SOURCES)


def test_detail_selectors():
    s = collectors.SOURCES[0]
    assert collectors.looks_detail(s, 'Saiba Mais', 'https://www.vunesp.com.br/CMIH2601')
    assert not collectors.looks_detail(s, 'Sobre nós', 'https://www.vunesp.com.br/institucional')


def test_official_notice_selector():
    assert collectors.notice_anchor('Edital de Abertura', 'https://www.gov.br/a.pdf')
    assert not collectors.notice_anchor('Resultado final', 'https://www.gov.br/b.pdf')
    assert not collectors.notice_anchor('Faixa salarial', 'https://www.gov.br/salary.pdf')


def test_html_has_only_allowed_links():
    html = '<a href="https://evil.com/edital.pdf">ED</a><a href="/CMIH2601">IT</a>'
    assert list(collectors.hrefs(html, 'https://www.vunesp.com.br')) == [('IT', 'https://www.vunesp.com.br/CMIH2601')]


def test_worker_slot_time():
    assert slot(datetime(2026, 10, 16, 0, 0)) == '2026-10-16:0'
    assert slot(datetime(2026, 10, 16, 2, 59)) == '2026-10-16:0'
    assert slot(datetime(2026, 10, 16, 3, 0)) == '2026-10-16:1'
    assert slot(datetime(2026, 10, 16, 21, 0)) == '2026-10-16:7'


def test_scan_lease_exclusive():
    assert collectors.claim_lease() is True
    assert collectors.claim_lease() is False
    collectors.release_lease()
    assert collectors.claim_lease() is True
    collectors.release_lease()


def test_source_failure_clearly_reported(monkeypatch):
    def bad(*a, **kw):
        raise ValueError('Fonte indisponível')

    monkeypatch.setattr(evidence, 'fetch_official', bad)
    f, a, ok = collectors.scan_source(collectors.SOURCES[0])
    assert (f, a, ok) == (0, 0, False)
    assert repo.source_health()[0]['state'] == 'failed'


def test_watched_page_change():
    collectors.watch_page(
        'Orgão', 'https://www.gov.br/orgao', '<html><main>' + 'texto oficial ' * 30 + '</main></html>'
    )
    collectors.watch_page(
        'Orgão', 'https://www.gov.br/orgao', '<html><main>' + 'texto modificado ' * 30 + '</main></html>'
    )
    assert any(a['kind'] == 'site_changed' for a in repo.get_alerts())


def test_deadline_only_proven():
    repo.upsert(
        {
            'title': 'Incompleto',
            'position': 'Analista de Sistemas',
            'official_url': 'https://www.gov.br/a',
            'registration_start': '2026-10-01',
            'registration_end': '2026-10-16',
            'confidence': 'official',
            'reviewed': 1,
        }
    )
    collectors.deadline_alerts(reference=repo.date(2026, 10, 16))
    assert not any(x['kind'] == 'deadline' for x in repo.get_alerts())
