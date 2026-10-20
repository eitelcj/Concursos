"""FastAPI: private single-admin radar, hard gate for verified documents."""
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI,HTTPException,Request,BackgroundTasks
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.middleware.gzip import GZipMiddleware
from . import core,collectors,auth,evidence,polite

BASE=Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app):
    core.init_db()
    if not auth.password_configured():
        raise RuntimeError(f'Defina RADAR_PASSWORD com pelo menos {auth.MIN_PASSWORD_LENGTH} caracteres no .env (sem valor de exemplo)')
    core.seed_official()  # v1.1 retained; NEW documentary gate requires reconfirmation.
    collectors.deadline_alerts()
    yield

app=FastAPI(title='SpeedLora Concurso Radar',version='2.0.2',lifespan=lifespan,
  docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(GZipMiddleware,minimum_size=800)

PUBLIC={'/healthz','/','/favicon.ico','/api/auth/login','/api/auth/status','/static/style.css','/static/app.js','/static/favicon.svg','/static/favicon.ico','/static/brand-symbol.png','/static/speedlora-logo.svg'}

@app.middleware('http')
async def gate(request:Request,call_next):
    path=request.url.path
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('origin')
        if origin and urlparse(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Origem bloqueada'},status_code=403)
        if request.headers.get('content-type','').split(';')[0] != 'application/json':
            return JSONResponse({'detail':'Apenas application/json'},status_code=415)
    session=auth.validate_session(request.cookies.get(auth.COOKIE))
    request.state.session=session
    if path not in PUBLIC and not session:
        return JSONResponse({'detail':'Autenticação necessária'},status_code=401)
    if path not in PUBLIC and request.method in ('POST','PUT','PATCH','DELETE'):
        if not auth.csrf_valid(session,request.headers.get('X-CSRF-Token','')):
            return JSONResponse({'detail':'CSRF inválido'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    return response

@app.get('/healthz')
def health():return {'service':'ok','date':core.today().isoformat()}

@app.get('/')
def index():return FileResponse(BASE/'static/index.html')

@app.get('/favicon.ico')
def classic_favicon():
    return FileResponse(BASE/'static/favicon.ico')

@app.get('/static/{filename}')
def static(filename:str):
    if filename not in ('app.js','style.css','favicon.svg','favicon.ico','brand-symbol.png','speedlora-logo.svg'):raise HTTPException(404)
    return FileResponse(BASE/'static'/filename)

@app.get('/api/auth/status')
def status(request:Request):
    s=request.state.session
    return {'authenticated':bool(s),'mfa_enabled':auth.mfa_enabled(),
            'csrf':auth.setting('never_return_csrf') if False else None} if not s else {'authenticated':True,'mfa_enabled':auth.mfa_enabled(),
            'csrf': request.cookies.get('radar_csrf','')}

@app.post('/api/auth/login')
async def login(request:Request):
    data=await request.json();password=str(data.get('password',''));code=str(data.get('code',''))
    ip=request.client.host if request.client else 'unknown'
    if not auth.can_attempt(ip):raise HTTPException(429,'Muitas tentativas. Aguarde 15 minutos.')
    if not auth.password_ok(password):
        auth.failed(ip);raise HTTPException(401,'Senha inválida')
    if auth.mfa_enabled() and not code:
        return {'mfa_required':True}
    if auth.mfa_enabled() and not auth.mfa_check(code,True):
        auth.failed(ip);raise HTTPException(401,'Código MFA inválido')
    auth.successful(ip)
    token,csrf=auth.new_session()
    response=JSONResponse({'authenticated':True,'mfa_enabled':auth.mfa_enabled(),'csrf':csrf})
    secure=os.getenv('RADAR_COOKIE_SECURE','1')=='1'
    response.set_cookie(auth.COOKIE,token,max_age=7*86400,httponly=True,samesite='strict',secure=secure,path='/')
    # Only accessible to same-origin JS. CSRF cookie is NOT an authentication credential.
    response.set_cookie('radar_csrf',csrf,max_age=7*86400,httponly=False,samesite='strict',secure=secure,path='/')
    return response

@app.post('/api/auth/logout')
def logout(request:Request):
    auth.logout(request.cookies.get(auth.COOKIE))
    response=JSONResponse({'ok':True})
    response.delete_cookie(auth.COOKIE,path='/')
    response.delete_cookie('radar_csrf',path='/')
    return response

@app.post('/api/auth/mfa/setup')
async def mfa_setup(request:Request):
    data=await request.json()
    if auth.mfa_enabled():raise HTTPException(409,'MFA já ativado')
    if not auth.password_ok(str(data.get('password',''))):raise HTTPException(403,'Confirme sua senha')
    try:return auth.begin_mfa()
    except ValueError as e:raise HTTPException(422,str(e))

@app.post('/api/auth/mfa/confirm')
async def mfa_confirm(request:Request):
    data=await request.json()
    try:codes=auth.finish_mfa(data.get('code',''))
    except ValueError as e:raise HTTPException(422,str(e))
    return {'active':True,'recovery_codes':codes}

@app.post('/api/auth/mfa/disable')
async def mfa_disable(request:Request):
    data=await request.json()
    if not auth.disable_mfa(str(data.get('password','')),str(data.get('code',''))):
        raise HTTPException(403,'Senha/código inválidos')
    return {'active':False}

@app.get('/api/opportunities')
def opportunities():return {'items':core.query_opportunities(),'as_of':core.now()}

@app.get('/api/opportunities/{oid}')
def opportunity(oid:int):
    item=core.fetch_one(oid)
    if not item:raise HTTPException(404)
    return item

@app.post('/api/opportunities',status_code=201)
async def add_opportunity(request:Request):
    data=await request.json()
    if not isinstance(data,dict):raise HTTPException(422)
    if not data.get('title') or not evidence.official_url(data.get('official_url','')) or not evidence.official_url(data.get('notice_url','')):
        raise HTTPException(422,'Informe título, página oficial e link HTTPS de edital em domínio oficial')
    # Never allow manual flags to circumvent technical verification.
    data['confidence']='discovery';data['reviewed']=0;data['status_override']=None
    data['source']='Cadastro manual (verificação pendente)'
    try:oid,_=core.upsert(data,enrich_only=False)
    except (ValueError,TypeError) as e:raise HTTPException(422,str(e))
    return core.fetch_one(oid)

@app.patch('/api/opportunities/{oid}')
async def edit_opportunity(oid:int,request:Request):
    data=await request.json()
    if not isinstance(data,dict):raise HTTPException(422)
    for k in ('official_url','notice_url','apply_url'):
        if k in data and data[k] and not evidence.official_url(data[k]):
            raise HTTPException(422,f'{k} não é endereço oficial permitido')
    try:ok=core.update_opportunity(oid,data)
    except (ValueError,TypeError) as e:raise HTTPException(422,str(e))
    if not ok:raise HTTPException(404)
    return core.fetch_one(oid)

@app.post('/api/opportunities/{oid}/verify')
def verify(oid:int):
    item=core.fetch_one(oid)
    if not item:raise HTTPException(404)
    url=item.get('notice_url') or ''
    if not evidence.official_url(url):raise HTTPException(422,'Informe link direto do edital oficial primeiro')
    if not item.get('position') or not core.is_it(item['position']):
        raise HTTPException(422,'Informe o cargo de TI específico')
    try:
        proof=evidence.notice_proof(url,position=item['position'])
        evidence.check_assertions(proof,item)
        core.record_proof(oid,proof,item)
    except Exception as e:
        raise HTTPException(422,'Conferência documental reprovada: '+str(e))
    return core.fetch_one(oid)

@app.get('/api/candidates')
def candidates():return {'items':core.candidates()}

@app.get('/api/alerts')
def alerts():return {'items':core.get_alerts()}

@app.get('/api/sources')
def sources():
    host_state=polite.snapshot()
    return {'health':core.source_health(),'cron':'A cada 3 horas (00, 03, 06, 09, 12, 15, 18, 21 BRT)',
            'running':collectors.LOCK.locked(),'configured':len(collectors.SOURCES),
            'catalog':[{'name':s.name,'url':s.url,'mode':s.mode, 'pacing':host_state.get(polite.hostname(s.url),{})} for s in collectors.SOURCES],
            'notifications_configured':bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID') or os.getenv('SMTP_HOST') and os.getenv('ALERT_EMAIL_TO'))}

@app.post('/api/scan',status_code=202)
def scan_now(background_tasks:BackgroundTasks):
    if collectors.LOCK.locked() or (auth.setting('scan_lease_until') or '')>core.now():raise HTTPException(409,'Coleta já em execução')
    background_tasks.add_task(collectors.run_all)
    return {'queued':True}

@app.get('/api/export.csv')
def export_csv():
    rows=core.query_opportunities()
    fields=['title','agency','position','status','salary_min','salary_max','salary_verified','registration_start',
        'registration_end','exam_date','exam_cities','work_cities','official_url','notice_url','apply_url','document_verified','favorite','applied','notes']
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="concursos-ti.csv"'})
