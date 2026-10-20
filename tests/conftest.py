import pytest
from app import core

@pytest.fixture(autouse=True)
def isolated_db(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',str(tmp_path/'radar.sqlite3'))
    monkeypatch.setenv('RADAR_PASSWORD','Very-Strong-Password-TEST-1234')
    monkeypatch.setenv('RADAR_COOKIE_SECURE','0')
    monkeypatch.setenv('RADAR_MFA_ENCRYPTION_KEY','pjkUsvLXBbFH15KG_tAgBbB8x9MDE5c7qVmU2_XgEuI=')
    core.init_db()
