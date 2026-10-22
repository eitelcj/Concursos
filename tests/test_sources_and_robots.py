from pathlib import Path

import pytest

from app import robots, sources

ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, status, text=''):
        self.status_code = status
        self.text = text


class FakeSession:
    def __init__(self, status, text=''):
        self.status, self.text, self.calls = status, text, 0

    def get(self, url, **_):
        self.calls += 1
        return FakeResponse(self.status, self.text)


@pytest.fixture(autouse=True)
def clean_robots_cache():
    robots.clear()
    yield
    robots.clear()


def test_repository_sources_file_is_valid():
    loaded = sources.load(ROOT / 'sources.yaml')
    assert len(loaded) == 11
    assert all(s.url.startswith('https://') for s in loaded)
    assert any(s.mode == 'watch' and s.uf == 'SP' for s in loaded)


def test_invalid_entries_are_refused_with_a_clear_message():
    cases = {
        'sem nome': {'sources': [{'url': 'https://www.gov.br/x'}]},
        'url não oficial': {'sources': [{'name': 'x', 'url': 'https://exemplo.com.br/'}]},
        'modo errado': {'sources': [{'name': 'x', 'url': 'https://www.gov.br/', 'mode': 'scrape'}]},
        'nome repetido': {
            'sources': [{'name': 'x', 'url': 'https://www.gov.br/'}, {'name': 'x', 'url': 'https://www.gov.br/'}]
        },
        'uf inválida': {'sources': [{'name': 'x', 'url': 'https://www.gov.br/', 'uf': 'Sao Paulo'}]},
        'sem lista': {'fontes': []},
    }
    for data in cases.values():
        with pytest.raises(sources.SourceError):
            sources.parse(data)


def test_disabled_source_is_kept_but_not_active():
    data = {
        'sources': [
            {'name': 'a', 'url': 'https://www.gov.br/'},
            {'name': 'b', 'url': 'https://www.gov.br/', 'enabled': False},
        ]
    }
    parsed = sources.parse(data)
    assert len(parsed) == 2
    assert [s.name for s in sources.active(parsed)] == ['a']


def test_robots_missing_file_allows_and_disallow_blocks():
    robots.check('https://www.gov.br/concursos', FakeSession(404))
    robots.clear()  # same host: the cached answer would otherwise hide the new rule
    blocked = FakeSession(200, 'User-agent: *\nDisallow: /concursos\n')
    with pytest.raises(robots.RobotsBlocked):
        robots.check('https://www.gov.br/concursos', blocked)


def test_robots_agent_specific_rule_wins():
    text = 'User-agent: RadarPublicSector\nDisallow: /\n\nUser-agent: *\nAllow: /\n'
    with pytest.raises(robots.RobotsBlocked):
        robots.check('https://www.gov.br/editais', FakeSession(200, text))


def test_robots_unreachable_is_conservative_and_cached():
    session = FakeSession(503)
    with pytest.raises(robots.RobotsBlocked):
        robots.check('https://www.gov.br/a', session, now=1000)
    with pytest.raises(robots.RobotsBlocked):
        robots.check('https://www.gov.br/b', session, now=1001)
    assert session.calls == 1  # cached for the host
