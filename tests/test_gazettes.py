import json

from app import evidence, gazettes, sources
from app import repository as repo

SOURCE = sources.Source(
    name='Querido Diário — teste', url='https://api.queridodiario.org.br/gazettes', mode='gazette_search'
)


def gazette(town, uf, url, *excerpts):
    return {
        'territory_id': '3550308',
        'territory_name': town,
        'state_code': uf,
        'date': '2026-10-14',
        'url': url,
        'txt_url': url.replace('.pdf', '.txt'),
        'excerpts': list(excerpts),
    }


RESPONSE = {
    'total_gazettes': 3,
    'gazettes': [
        gazette(
            'Campinas',
            'SP',
            'https://data.queridodiario.ok.org.br/3509502/2026-10-14/a.pdf',
            'EXTRATO DO EDITAL DE ABERTURA DO <b>CONCURSO PÚBLICO</b> 01/2026. Cargo: Analista de Sistemas, '
            'vencimento R$ 6.500,00. Inscrições de 20/10/2026 a 18/11/2026 em www.vunesp.com.br/PCAM2601.',
        ),
        gazette(
            'Sorocaba',
            'SP',
            'https://data.queridodiario.ok.org.br/3552205/2026-10-13/b.pdf',
            'HOMOLOGAÇÃO do resultado final do concurso público para Técnico em Informática.',
        ),
        gazette(
            'Natal',
            'RN',
            'https://data.queridodiario.ok.org.br/2408102/2026-10-12/c.pdf',
            'Edital de abertura de concurso público com vagas para Técnico em Informática. Inscrições abertas.',
        ),
    ],
}


def fake_api(monkeypatch, payload):
    calls = []

    def fetch(url, session=None, *, pace=None, data_api=False):
        calls.append((url, data_api))
        return url, json.dumps(payload).encode(), 'application/json'

    monkeypatch.setattr(evidence, 'fetch_official', fetch)
    return calls


def test_finds_it_contests_in_municipal_gazettes(monkeypatch):
    calls = fake_api(monkeypatch, RESPONSE)
    found, added, ok = gazettes.scan_source(SOURCE)
    assert (found, added, ok) == (2, 2, True)
    assert len(calls) == len(gazettes.TERMS) and all(data_api for _, data_api in calls)
    assert 'querystring=%22concurso+p%C3%BAblico%22+%22tecnologia' in calls[0][0]
    assert 'published_since=2026-09-24' in calls[0][0] and '%7C' not in calls[0][0] and '%28' not in calls[0][0]
    items = {i['agency']: i for i in repo.query_opportunities()}
    campinas = items['Campinas/SP']
    assert campinas['position'] == 'Analista de Sistemas'
    assert campinas['official_url'] == 'https://www.vunesp.com.br/PCAM2601'
    assert campinas['status'] == 'verify' and campinas['confidence'] == 'discovery'
    assert 'Querido Diário' in campinas['notes']
    assert 'Sorocaba/SP' not in items  # results/homologations are not openings
    assert items['Natal/RN']['position'] == 'Técnico em Informática'
    # second run: nothing new, no duplicates
    assert gazettes.scan_source(SOURCE)[:2] == (2, 0)


def test_uf_filter(monkeypatch):
    fake_api(monkeypatch, RESPONSE)
    only_sp = sources.Source(name='QD SP', url=SOURCE.url, mode='gazette_search', uf='SP')
    assert gazettes.scan_source(only_sp)[:2] == (1, 1)


def test_api_is_allowed_only_for_gazette_search():
    assert evidence.data_api_url('https://api.queridodiario.org.br/gazettes')
    assert not evidence.official_url('https://api.queridodiario.org.br/gazettes')
    ok = sources.parse({'sources': [{'name': 'QD', 'url': SOURCE.url, 'mode': 'gazette_search'}]})
    assert ok[0].mode == 'gazette_search'
    for bad in (
        {'name': 'QD', 'url': SOURCE.url, 'mode': 'catalog'},
        {'name': 'X', 'url': 'https://www.gov.br/x', 'mode': 'gazette_search'},
    ):
        try:
            sources.parse({'sources': [bad]})
        except sources.SourceError:
            continue
        raise AssertionError(bad)


def test_bad_json_is_reported(monkeypatch):
    monkeypatch.setattr(evidence, 'fetch_official', lambda url, session=None, **k: (url, b'<html>', 'text/html'))
    assert gazettes.scan_source(SOURCE)[2] is False
    assert 'JSON' in repo.source_health()[0]['error']


def test_one_failing_search_keeps_the_others(monkeypatch):
    def fetch(url, session=None, *, pace=None, data_api=False):
        if 'programador' in url:
            raise ValueError('500 Server Error: Internal Server Error for url: x')
        return url, json.dumps(RESPONSE).encode(), 'application/json'

    monkeypatch.setattr(evidence, 'fetch_official', fetch)
    found, added, ok = gazettes.scan_source(SOURCE)
    assert (found, added, ok) == (2, 2, False)
    error = repo.source_health()[0]['error']
    assert error.startswith('Cobertura PARCIAL: 1 de 8') and 'for url' not in error
