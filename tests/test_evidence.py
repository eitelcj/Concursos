import pytest
from app import evidence

@pytest.mark.parametrize('url,expected',[
 ('https://www.vunesp.com.br/CMIH2601',True),('https://documento.vunesp.com.br/documento/stream/7',True),
 ('https://conhecimento.fgv.br/concursos/dataprev26',True),('https://www.cebraspe.org.br/concursos/a',True),
 ('https://abcp.selecao.net.br/concursos/1',True),('https://www.gov.br/cgu',True),
 ('https://sao-paulo.gov.br/edital',True),('https://concursopublico.ifsp.edu.br/',True),
 ('https://www.vunesp.com.br.evil.com/a',False),('https://vunesp.com.br@evil.org/a',False),
 ('http://www.vunesp.com.br/',False),('https://evil.com/edital.pdf',False),
 ('https://127.0.0.1/admin',False),('file:///etc/passwd',False),('javascript:alert(1)',False)
])
def test_official_domain_rules(url,expected):
 assert evidence.official_url(url) is expected

def test_notice_requires_real_context():
 good=('EDITAL Nº 1 DE ABERTURA - CONCURSO PÚBLICO. Vagas: Analista de Sistemas. '
       'Inscrições das 01/10/2026 até 20/10/2026. '
       'Prova objetiva em 13/12/2026. Cargo Analista de Sistemas R$ 9.800,00. ')*8
 class FakeResponse:
  url='https://www.gov.br/edital'
  status_code=200
  headers={'Content-Type':'text/html'}
  def raise_for_status(self): pass
  def iter_content(self,n):yield ('<html>'+good+'</html>').encode()
  def close(self):pass
 class FakeSession:
  def get(self,url,**kwargs):return FakeResponse()
 p=evidence.notice_proof('https://www.gov.br/edital',session=FakeSession(),position='Analista de Sistemas')
 assert p.role_excerpt and p.sha256
 assert evidence.date_supported(p.text,'2026-10-20')
 assert evidence.money_supported_near_role(p.text,9800,'Analista de Sistemas')
 evidence.check_assertions(p,{'position':'Analista de Sistemas','salary_min':9800,'registration_end':'2026-10-20'})
 with pytest.raises(ValueError):evidence.check_assertions(p,{'position':'Analista de Sistemas','registration_end':'2027-11-20'})
 with pytest.raises(ValueError):evidence.check_assertions(p,{'position':'Analista de Sistemas','salary_min':12000})

def test_salary_from_other_role_not_valid():
 txt='Concurso publico edital. Cargo Analista de Sistemas R$ 5.000,00. '+'x'*900+' Cargo Procurador R$ 20.000,00.'
 assert not evidence.money_supported_near_role(txt,20000,'Analista de Sistemas')
 assert evidence.money_supported_near_role(txt,5000,'Analista de Sistemas')

@pytest.mark.parametrize('bad',[
 'Edital para concurso de professor de matemática. '*30,
 'Notícia sem edital: informatica concurso e vagas '*30,
 'edital sem texto e TI',
])
def test_notice_gates(bad):
 class R:
  url='https://www.gov.br/edital';headers={'Content-Type':'text/html'};status_code=200
  def raise_for_status(self):pass
  def iter_content(self,_):yield ('<html>'+bad+'</html>').encode()
  def close(self):pass
 class S:
  def get(self,*a,**k):return R()
 with pytest.raises(ValueError):evidence.notice_proof('https://www.gov.br/edital',session=S(),position='Analista de Sistemas')

def test_redirect_outside_official_blocked():
 class R:
  url='https://www.gov.br/edital';status_code=302;headers={'location':'https://evil.com/edital'}
  def close(self):pass
 class S:
  def get(self,*a,**k):return R()
 with pytest.raises(ValueError,match='Redirecionamento'):evidence.fetch_official('https://www.gov.br/edital',S())
