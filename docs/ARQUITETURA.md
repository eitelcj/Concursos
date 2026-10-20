# Arquitetura v2 — visibilidade sem certeza inventada

```text
Browser (SoftLight / SpeedLora; senha única e TOTP opcional)
  | HTTPS, sessão com cookie HttpOnly + CSRF
  v
FastAPI (1 worker) ----------------------- SQLite (volume persistente)
  |  |                                      |- opportunities v1.1
  |  +--- /api/... privado                  |- notice_evidence (URL/hash/data/cargo)
  |                                         |- scan_candidates (pendências)
  +--- gatilho manual                       |- notice_watches / scan_runs
         \                                  |- favorites/applied/alerts/sessions
          +-> LEASE SQLite <--- radar-worker (processo independente)
                                   | 00,03,06,09,12,15,18,21 (BRT)
                                   | erro -> até um retry 15 min/janela; sem falso sucesso
                                   v
                         Fontes OFICIAIS HTTPS
                         | catálogo ou página específica
                         v
                     Links de editais candidatos
                         | allowlist domínio / anti-redirecionamento
                         | PDF/HTML legível e edital de abertura
                         | cargo TI presente
                         v
                       PENDENTE (sem dados inferidos)
                         | usuário confirma dados do cargo
                         | validação no servidor: edital + cargo + datas + salário
                         | hash SHA256 do arquivo + data + trecho
                         v
                       CONFIRMADO -> calendário -> aberto/próximo/encerrado
                         |
                   alertas e filtros por estado, SP e R$7.000+
```

Não roda navegador/headless para driblar JavaScript, login de banca, restrições antibot ou CAPTCHA. Arquivos PDF escaneados sem camada textual não são validados automaticamente. Erros ficam persistidos por fonte.

## Dados de confiança

- Registro legado da v1.1 não tem `notice_evidence`. Ele é preservado, mas `document_verified=False` e `status=verify` até revalidação.
- Um documento pode ter cargo de TI, sem sustentar a remuneração exibida em um **outro** cargo do mesmo edital; a checagem exige que o valor esteja junto ao cargo.
- A data e a cidade só recebem validação quando aparecem no contexto relevante. Campo ausente fica pendente.
- Editar cargo, link, salário, prazos ou localização **revoga** a prova anterior; favorito e inscrição marcada não revogam.
- Novo documento de retificação/suspensão identificado em uma página oficial ou alteração do hash do edital revoga a aprovação anterior e cria alerta.
- `source_health` registra o resultado do coletor; um site acessível **não demonstra que todos os editais foram encontrados**.

## Segurança e implantação

`RADAR_PASSWORD` exclusiva com mínimo de 7 caracteres. MFA TOTP opcional; segredos cifrados com chave Fernet exclusiva. Sessão de 7 dias com hash armazenado no banco, cookie HttpOnly/SameSite/secure no HTTPS, proteção CSRF, limitação de logins por IP, CSP e logout. Proxy HTTPS obrigatório para acesso externo. Uma única instância de worker; lock SQLite compartilhado entre API e worker. Volume único persistente com migração não destrutiva das tabelas existentes.

## Fila e limites (v2.0.2)

O `collectors.run_all` processa a fila de fontes por `ThreadPoolExecutor` (padrão 3 workers). A camada `app/polite.py` garante serialização por domínio via `threading.Lock`, reserva slots no banco SQLite compartilhado (`host_pacing`) e usa cooldown persistente para 403/429. O worker mantém agenda de três horas e limita tentativas por slot. A API e worker compartilham o lease de varredura. Nenhuma thread consulta a mesma origem ao mesmo tempo no mesmo processo. Em processos distintos, as reservas são serializadas pelo SQLite.

Cenários que continuam exigindo verificação: divergência entre política do portal e coleta automatizada, documentação que depende de JS, paginação que não é visível no HTML e páginas oficiais indisponíveis.
