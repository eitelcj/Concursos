# Regressão v2 — 16/10/2026

## Comandos efetivamente executados

| Teste | Resultado | Evidência / alcance |
|---|---|---|
| `python -m pytest -q` | **PASS — 56/56** | Testes unitários e TestClient API, com PDFs e páginas simulados |
| `node --check static/app.js` | **PASS** | Validação sintática do JavaScript |
| `python scripts/check_config.py` | **PASS** | Estrutura/allowlist/fontes/worker; não testa rede externa |
| API real Uvicorn `GET /healthz` | **PASS (200)** | Processo local isolado, porta temporária |
| API real Uvicorn `GET /api/opportunities` não autenticado | **PASS (401)** | Sessão obrigatória |
| Navegador Playwright/Chromium local | **BLOQUEADO** | Ambiente retornou `ERR_BLOCKED_BY_ADMINISTRATOR`; sem homologação visual |
| Build/inicialização real `docker compose up` | **NÃO EXECUTADO** | Docker/daemon não disponíveis neste ambiente |
| Varredura HTTP completa nas bancas | **NÃO EXECUTADA** | Rede externa inacessível para os processos Python executáveis no ambiente |
| E-mails/Telegram reais | **NÃO EXECUTADO** | Exige conta/canal e credenciais próprios |

## Casos automatizados (56)

- Listas de domínios oficiais por hostname (bloqueio de falsos subdomínios/URLs HTTP; Vunesp e `documento.vunesp.com.br`).
- Redirecionamento para domínio externo bloqueado, PDF/HTML de edital de abertura, documento falso, notícias e arquivo sem área de TI rejeitados.
- Extração PDF por `pypdf`; contexto de cargo TI; rejeição de salário de cargo diferente, além de salário ausente e do limite R$7 mil.
- Início/fim de inscrição, último dia válido, calendário de prazos e prova em SP + lotação fora do estado.
- Migração lógica das quatro oportunidades iniciais: preservação sem garantia documental automática.
- Edição de dados que revoga aprovação, preservação ao favoritar, deduplicação e campos persistentes.
- Edital modificado/retificado revoga confirmação e dispara alerta.
- HTTP 200/401, login sem nome de usuário, logout, cookies, proteção CSRF e validação de origem, endpoint privado.
- TOTP MFA/QR/códigos de recuperação de uso único, recusa de códigos errados e bloqueio por força bruta.
- Fonte com erro registrada como falha; vigia detecta alterações; exclusiva de coleta SQLite; janelas de 3 horas.

## Migração REAL v1.1 → v2 validada

Foi criado um banco SQLite temporário usando **o código da v1.1 extraído do ZIP anterior**, inseridos os quatro registros iniciais e configurados `favorite=1`, `applied=1` e uma anotação no primeiro registro. Em seguida a v2 executou `init_db()` e `seed_official()` sobre o mesmo arquivo: **PASS**, os quatro registros, favorito, inscrição e anotação sobreviveram, e o status anterior foi reduzido a `verify` até validação documental. Não foi alterado o banco de nenhum projeto real.

## Correções adicionais após a bateria de testes

- Foram adicionados dois testes para limitar a uma nova tentativa por janela de 3h e impedir varreduras repetidas sem fim quando páginas oficiais falharem.
- Foram adicionados três testes de regressão para editais IBAM distintos na mesma página, exclusão de retificações e cobertura parcial quando nenhum edital pode ser obtido.
- Identidade de novos concursos vinculada ao **URL do edital** e não à URL de uma página geral (o IBAM publica vários certames na mesma listagem).
- Alterações de documentos na listagem IBAM agrupadas numa única inspeção, para não causar falsos alertas a cada bloco.
- Retificações/suspensões não são escolhidas como edital inicial.
- Quando um catálogo não consegue localizar edital de abertura, a coleta é marcada **parcial**, não sucesso enganoso.
- Valores, local de prova/trabalho e datas de registros herdados sem prova são ocultados como “A confirmar” no card.
- `status_override='open'` legado é eliminado depois da validação documental; abertura depende das datas comprovadas.

## Itens obrigatórios de homologação real (ainda pendentes)

1. Subir Docker e verificar serviços API/worker, volume/porta e logs.
2. Executar coleta real em cada site oficial e comparar com as páginas/retificações visíveis em navegador normal.
3. Validar páginas com JavaScript/paginação: Vunesp, Cebraspe e sites de municípios; **não há garantia de captura integral**.
4. Validar cargo e salário dentro de edital verdadeiro de TI; salário de outro cargo nunca pode aparecer.
5. Confirmar que concurso nacional com prova em SP/lotação DF passa no filtro SP após prova documental.
6. Verificar 3 ciclos do worker (uma varredura real, avanço de 3h, retry com fonte temporariamente indisponível) e botão manual.
7. Homologar temas e mobile no navegador real, login/MFA, backup e restart do Docker.
8. Conferir que os quatro registros legados e seus favoritos/inscritos permanecem, mas inicialmente são “a verificar”.

**Parecer técnico:** regressão de código **PASS** com as limitações descritas; **não há evidência para declarar produção, cobertura de todos os editais, coleta ponta a ponta nem mobile visual PASS.** Essas etapas exigem a execução na máquina/VPS com internet e navegador.


## Hotfix v2.0.1 — senhas de 7 caracteres (16/10/2026)

- Backend: mínimo de 7 caracteres compartilhado entre inicialização e autenticação.
- Frontend: `minlength=7`.
- Documentação, exemplo de configuração e casos-limite revisados.
- A senha ainda precisa ser definida pelo administrador; valor de exemplo não autoriza inicialização.
- A configuração existente de `.env`, dados SQLite, MFA e serviços Docker não é alterada automaticamente.

**Regressão do hotfix:** 61/61 testes automatizados PASS; execução real do Uvicorn em loopback com senha de exatamente 7 caracteres: `GET /healthz = 200` e `POST /api/auth/login = 200`, sessão criada. Build Docker neste ambiente não testado; validar o Compose na máquina Windows.


## v2.0.2 — correção 403/429, fila, menu e marca (17/10/2026)

**Resultado automatizado:** 67/67 testes pytest PASS (61 anteriores + 6 novos). Testados:

- 403 bloqueia por 12h, registra cooldown no SQLite e impede uma segunda requisição ao site;
- 429 respeita `Retry-After` em segundos/data HTTP e aplica 3h quando ausente;
- requisições simultâneas ao mesmo hostname são serializadas;
- fila executa fontes distintas em paralelo;
- resposta `blocked` aparece no diagnóstico e não é promovida a OK;
- HTML inclui a marca compartilhada e CSS mantém conteúdo alinhado ao topo no desktop/mobile.

**Outras verificações:** código JS sintaticamente válido (`node --check`), CSS aceito por `tinycss2` (98 regras, nenhum erro), `healthz` HTTP 200 em API local. O navegador automatizado Chromium retornou `ERR_BLOCKED_BY_ADMINISTRATOR` ao tentar acessar o servidor local deste ambiente: **visual desktop/mobile não homologado**. Não foi realizada coleta ponta a ponta contra Vunesp ou demais fontes no Docker do usuário, nem build Docker neste ambiente.

**Não houve alteração destrutiva de esquema:** somente `host_pacing` foi adicionada com `CREATE TABLE IF NOT EXISTS`. O mesmo banco e volume continuam válidos; o limite da senha segue 7 caracteres, e sessões/MFA não foram migrados ou reiniciados por esta alteração.
