import pytest
from datetime import date
from app import core,evidence

def sample(**changes):
 d=dict(title='Concurso municipal TI',agency='Prefeitura',position='Analista de Sistemas',
  official_url='https://www.gov.br/edital', notice_url='https://www.gov.br/edital-abertura.pdf',
  confidence='official',reviewed=1,registration_start='2026-10-01',registration_end='2026-10-20',
  salary_min=8000,exam_in_sp=1,work_cities='Brasília/DF',national=1)
 d.update(changes);return d

def test_seed_preserved_but_pending():
 core.seed_official();core.seed_official()
 items=core.query_opportunities()
 assert len(items)==4
 assert all(i['status']=='verify' and not i['document_verified'] for i in items)
 assert all(i['eligible_sp'] for i in items)

def test_legacy_unverified_never_open():
 oid,_=core.upsert(sample())
 assert core.fetch_one(oid)['status']=='verify'
 assert not core.fetch_one(oid)['salary_highlight']

def test_cannot_upgrade_by_edit():
 oid,_=core.upsert(sample())
 assert core.update_opportunity(oid,{'confidence':'official','reviewed':1,'status_override':'open'})
 assert core.fetch_one(oid)['status']=='verify'

def test_proof_is_gate():
 oid,_=core.upsert(sample())
 p=evidence.Proof('https://www.gov.br/edital.pdf','c'*64,'editais','pdf','analista de sistemas')
 core.record_proof(oid,p,sample())
 item=core.fetch_one(oid)
 assert item['status']=='open' and item['salary_highlight']
 assert item['eligible_sp'] and item['national']
 assert item['proof']['sha256']=='c'*64

def test_factual_edit_revokes_proof():
 oid,_=core.upsert(sample());p=evidence.Proof('https://www.gov.br/edital.pdf','a'*64,'','pdf','analista')
 core.record_proof(oid,p,sample());core.update_opportunity(oid,{'salary_min':20000})
 assert core.fetch_one(oid)['status']=='verify'

def test_favorite_preserves_proof():
 oid,_=core.upsert(sample());p=evidence.Proof('https://www.gov.br/edital.pdf','a'*64,'','pdf','analista')
 core.record_proof(oid,p,sample());core.update_opportunity(oid,{'favorite':1,'applied':1})
 assert core.fetch_one(oid)['document_verified'] and core.fetch_one(oid)['favorite']

def test_dedup_preserves_notes():
 oid,created=core.upsert(sample());assert created
 core.update_opportunity(oid,{'notes':'Anotação particular'})
 _,created=core.upsert(sample());assert not created
 assert core.fetch_one(oid)['notes']=='Anotação particular'

def test_manual_confidence_does_not_override_gate():
 item=sample(document_verified=False,status_override='open')
 assert core.compute_status(item,date(2026,10,16))=='verify'
 item['document_verified']=True
 assert core.compute_status(item,date(2026,10,16))=='open'
 assert core.compute_status(item,date(2026,10,21))=='closed'

def test_inclusive_dates():
 i=sample(document_verified=True)
 assert core.compute_status(i,date(2026,10,1))=='open'
 assert core.compute_status(i,date(2026,10,20))=='open'
 assert core.compute_status(i,date(2026,10,21))=='closed'
 assert core.compute_status(i,date(2026,9,30))=='upcoming'

def test_salary_threshold_verified_only():
 for value,expected in [(6999.99,False),(7000,True),(7356.77,True),(10000,True)]:
  i=sample(salary_min=value,salary_verified=True,document_verified=True)
  assert core.present(i,date(2026,10,16))['salary_highlight'] is expected
  i['salary_verified']=False
  assert not core.present(i,date(2026,10,16))['salary_highlight']

def test_reject_bad_date_and_url():
 with pytest.raises(ValueError):core.upsert(sample(registration_end='26/10/2026'))
 with pytest.raises(ValueError):core.upsert(sample(notice_url='javascript:bad'))

def test_candidate_unique():
 core.upsert_candidate('https://www.gov.br/edital','gov','Edital',state='pending')
 core.upsert_candidate('https://www.gov.br/edital','gov','Edital',state='edital_ti')
 assert len(core.candidates())==1 and core.candidates()[0]['state']=='edital_ti'
