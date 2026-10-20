# SpeedLora Concurso Radar v2.0.2 — editais oficiais de TI

Monitor **privado** de concursos públicos de tecnologia, priorizando Campinas/Jundiaí/Itatiba/estado de São Paulo; também considera concursos federais cuja prova possa ser feita em SP mesmo que a lotação seja em outro estado. Salários **a partir de R$ 7 mil** recebem destaque **somente quando o valor do cargo estiver confirmado pelo edital**. Editais abaixo disso permanecem visíveis.

**Princípio do projeto:** não há Google Notícias, PCI Concursos, blogs nem agregadores na coleta. A lista de fontes contém exclusivamente sites de órgãos e bancas, e **fonte oficial acessível não significa edital validado**. Um concurso só recebe a indicação de confirmado se houver documento oficial de abertura legível, cargo específico e evidência por campo. A descoberta automática conservadora não confirma salários ou datas por inferência.

**Estado de entrega:** projeto pronto para executar e testar localmente com FastAPI, SQLite, coleta a cada 3h, painel responsivo, senha única, MFA TOTP opcional e Compose. **A captura dos sites externos e o Docker ainda precisam de homologação real na máquina/VPS**, conforme `docs/REGRESSAO.md`. Não prometa zero concursos perdidos.

## 1. Iniciar localmente com Docker

Requer Docker Engine ou Docker Desktop com Compose.

```bash
cp .env.example .env
# Troque RADAR_PASSWORD por uma senha longa e única (mínimo 7 caracteres).
# PARA HTTP LOCAL (localhost) use RADAR_COOKIE_SECURE=0 no .env.
# PARA VPS ATRÁS DE HTTPS use RADAR_COOKIE_SECURE=1.
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

**Painel:** http://localhost:8765 — a entrada pede **apenas a senha**, sem nome de usuário. Se o login local não persistir, confira que `RADAR_COOKIE_SECURE=0` está definido para seu HTTP local. Nunca use `0` em produção HTTPS.

Serviços: `concurso-radar` (API e UI, porta local `127.0.0.1:8765`), `radar-worker` (coleta) e volume persistente `concurso_radar_data` (SQLite). Evite `docker compose down -v` para não apagar o banco.

**Inicialização:** quatro oportunidades iniciais da versão 1.1 (três especialidades CGU e IFSP) continuam preservadas. Por segurança, **não são automaticamente consideradas validadas na v2**: aparecerão como “a verificar” até uma validação de edital original. Todos os favoritos, inscrições marcadas e anotações persistem se for reutilizado o **mesmo volume da v1.1**.


**Senha com 7 caracteres:** a validação do backend e o formulário aceitam no mínimo 7 caracteres (não exigem letras maiúsculas ou caracteres especiais). Por segurança, prefira uma senha maior, especialmente ao expor o sistema na VPS, e ative o MFA. Se a API estiver `unhealthy`, confira se `RADAR_PASSWORD` em `.env` não está com `SUBSTITUA-...` e reinicie o Compose (`docker compose up -d --build --force-recreate`); preserve `.env` e o volume.

## 2. Segurança: senha + MFA opcional

O login usa uma senha única, bloqueio por repetidas tentativas e sessão protegida por cookie `HttpOnly`, `SameSite=Strict` por até 7 dias. Não há criação de usuários. Após entrar, vá em **Configurações → MFA**.

Para habilitar Google Authenticator ou outro app TOTP, gere uma chave Fernet exclusiva e configure **antes** de iniciar o serviço:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie para `RADAR_MFA_ENCRYPTION_KEY` em `.env` e reinicie o Compose. No painel, informe a senha, escaneie o QR Code, confirme o código de seis dígitos e **salve os oito códigos de recuperação**. Para desativar MFA, é exigida senha + código válido. Guarde a chave Fernet junto dos backups; perdê-la impede a leitura da configuração de MFA atual. Nunca copie `.env` nem segredos do Life para o Radar.

**VPS:** passe pelo seu proxy reverso com HTTPS. A API não deve ser publicada diretamente na internet. Veja `docs/DEPLOY_VPS.md`.

## 3. Como a validação de um concurso funciona

O Radar usa níveis distintos:

1. **Fonte consultada:** domínio oficial permitido respondeu, mas pode não ter havido edital detectado. A cobertura fica como parcial/falha se não houver documento acessível.
2. **Edital inicial encontrado:** documento obtido diretamente de órgão/banca em HTTPS, identificado como edital de abertura e contendo termos de TI. Entra como oportunidade/candidato **sem confirmar cargo individual, remuneração nem prazo**.
3. **Concurso confirmado:** no painel, edite o registro com o cargo específico e os campos do documento. Pressione **Validar edital**: o servidor busca novamente o documento, confirma a estrutura, o cargo, os prazos mencionados em contexto e, se fornecido, **salário junto ao cargo**, registra o SHA-256 e a data. Se a evidência faltar, mantém **A verificar** e informa o motivo.
4. **Aberto/Em breve/Encerrado:** só é calculado sobre registro documentado. A situação aberta requer **datas de início e fim confirmadas**, não manchete, faixa salarial geral ou página de inscrição isolada. Um edital retificado ou alterado invalida a conferência anterior até nova revisão.

A confirmação documental automática é **conservadora, não substitui a leitura humana integral e não prova assinatura digital**. PDFs digitalizados/ilegíveis e editais cujo texto esteja em anexos separados podem exigir revisão manual; o sistema não lhes concede confirmação indevida. Consulte `docs/CRITERIOS_DE_VALIDACAO.md`.

## 4. Varreduras e painel

Worker independente com agendamento no fuso `America/Sao_Paulo`: **00h, 03h, 06h, 09h, 12h, 15h, 18h, 21h**. Após reiniciar, ele executa se ainda não completou a janela atual. Falhas de fonte provocam **no máximo uma nova tentativa** após 15 minutos por janela de 3 horas (configurável), sem registrar falso sucesso nem bombardear portais indisponíveis. Trava SQLite impede varreduras concorrentes de worker e botão manual.

No painel: **Concursos** (status, filtro SP/nacional, R$7k+, busca, favoritos, inscritos), **Alertas** (editais novos, mudanças, prazos), **Fontes** (sucesso/falha, candidaturas a conferir, links oficiais), **Configurações** (MFA e tema). Temas: **SoftLight** e **SpeedLora**, inspirados nas definições do Life fornecido. A interface não exibe datas/cidades/salários como fatos se a validação não passou.

**Fontes oficiais configuradas:** Vunesp (abertos e próximos), FGV, FCC, IBAM, ABCP, Cebraspe (página específica CGU), IFSP (página específica), Prefeitura de Campinas e Diário Oficial do Estado de SP. As duas últimas são **vigias de alteração de páginas**, não extratores completos de editais. Alguns sites usam JavaScript/paginação e podem aparecer como **cobertura parcial**, nunca como monitoramento pleno fictício. Lista/limites em `docs/FONTES_E_COBERTURA.md`.

**Alertas externos:** Telegram ou SMTP opcionais por variáveis `.env.example`. Sem credenciais, os avisos ficam apenas no painel.

## 5. Comandos e testes

Sem Docker (venv Python 3.12+):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export RADAR_DB="$PWD/data/radar.sqlite3"
export RADAR_PASSWORD="troque-por-uma-senha-longa-unica"
export RADAR_COOKIE_SECURE=0
python -m pytest -q
python scripts/check_config.py
uvicorn app.main:app --host 127.0.0.1 --port 8765
# Em outro terminal, usando o mesmo RADAR_DB:
python -m app.worker
```

O worker NÃO roda automaticamente dentro do processo da API: é um processo/contêiner separado. Teste a API publicamente apenas em `/healthz`; as rotas `/api/...` exigem sessão. Não existe endpoint aberto `/docs`.

No painel, entre, clique **Verificar agora** e confira a aba **Fontes** até o término. Se todas as fontes tiverem falhado, não interprete “nenhum concurso” como ausência de concursos reais.

## 6. Backup e migração v1.1 → v2

Antes de atualizar o volume da v1.1, crie um backup do banco e guarde-o fora da VPS. Exemplo com o serviço v1.1 ainda ativo:

```bash
docker compose exec concurso-radar python -c "import sqlite3; a=sqlite3.connect('/data/radar.sqlite3'); b=sqlite3.connect('/data/backup-before-v2.sqlite3'); a.backup(b); b.close(); a.close()"
# Em seguida copie o arquivo de backup para fora do contêiner e da VPS.
```

Pelo mesmo nome de volume **`concurso_radar_data`**, a versão 2 cria tabelas adicionais sem recriar oportunidades; dados, favoritos e inscrições são preservados. Não modifique a configuração de volumes nem execute `down -v`. Mais detalhes e rollback em `docs/DEPLOY_VPS.md`.

## 7. Responsabilidades e limitações

- O sistema **não realiza inscrições** nem armazena CPF/senhas das bancas; os links levam aos sites oficiais.
- É possível perder vagas se a fonte usar páginas dinâmicas, exigir CAPTCHA, publicar PDF não extraível, encerrar inscrição entre varreduras ou mudar a estrutura. A tela Fontes deve denunciar isso; não há garantia de cobertura total.
- Confirme sempre retificações, inscrições, isenções, exigência de formação e cidades de prova diretamente no edital antes de tomar decisões.
- Documentação adicional: `docs/ARQUITETURA.md`, `docs/CRITERIOS_DE_VALIDACAO.md`, `docs/FONTES_E_COBERTURA.md`, `docs/DEPLOY_VPS.md`, `docs/REGRESSAO.md`.

## Coleta educada, fila e bloqueios (v2.0.2)

- O worker continua rodando **a cada 3 horas**, no horário de São Paulo.
- A fila consulta até **3 fontes/domínios distintos ao mesmo tempo**; requisições para o mesmo domínio são **serializadas** com intervalo mínimo de 8 segundos (configurável).
- `403 Forbidden`: o Radar **interrompe o acesso ao domínio por 12 horas**. Não insiste, não troca de identidade, não usa proxy ou CAPTCHA automático. Abas de fontes mostram **ACESSO SUSPENSO** e próximo horário de tentativa.
- `429 Too Many Requests`: segue `Retry-After` (em segundos ou data HTTP). Sem cabeçalho, suspende por 3 horas.
- Bloqueios são salvos no SQLite e compartilhados pela API e worker Docker. O botão **Verificar agora** não ignora o bloqueio: continua outras fontes, mas não faz requisições ao domínio pausado.
- Essas medidas **reduzem o risco** de bloqueios; **não garantem remover 403** quando o portal decide não permitir coleta automatizada. Use o link oficial no painel quando a fonte estiver indisponível.
- Variáveis opcionais: `RADAR_SOURCE_WORKERS=3`, `RADAR_DOMAIN_INTERVAL_SECONDS=8`. Evite aumentar velocidade por domínio.

## Identidade e navegação

Marca e ícone original do SpeedLora Life reutilizados **apenas como arquivos estáticos públicos** (`static/brand-symbol.png`, `favicon.ico`). Corrigido o alinhamento do conteúdo nas páginas curtas: o painel inicia no topo, inclusive na aba Configurações. Layout mobile conserva navegação horizontal sem aumentar o espaço vertical.

### Atualizar a partir da versão anterior

1. Faça backup do volume Docker antes de atualizar.
2. Extraia a v2.0.2 e substitua apenas os arquivos versionados. **Preserve seu `.env`** e nunca substitua seu banco por um banco vazio.
3. Mantenha os serviços e o nome do volume Compose: `concurso_radar_data`.
4. Execute `docker compose up -d --build --force-recreate` (sem `down -v`).
5. Consulte `docker compose ps`, abra `http://localhost:8765/healthz` e teste menu, favicon, login e página Fontes.
6. Vunesp pode permanecer suspensa após novo 403. É uma decisão do domínio, não uma falha do container.

### Inspeção visual no seu Windows (opcional)

Com Python local, `pip install playwright` e `python -m playwright install chromium`, rode `python scripts/visual_regression.py --url http://127.0.0.1:8765 --password SUA_SENHA` para testar o menu no desktop e mobile. **Não coloque uma senha real em histórico de terminal compartilhado**. Idealmente use uma cópia local de teste com senha temporária. Este teste abre o navegador local; o ambiente da elaboração bloqueou esse tipo de acesso e não houve homologação visual automática aqui.
