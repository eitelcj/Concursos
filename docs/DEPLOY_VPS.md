# Subida local/VPS com Docker — sem alterar Life/Research/English

**Escopo:** esta entrega contém somente o Radar; nenhum arquivo da VPS nem da stack do Life foi alterado. O Life de referência usa uma stack central em `/var/www/speedlora-stack`. A integração abaixo é uma proposta conservadora; não presuma que a porta, hostname, rede ou certificados estejam livres sem conferir o ambiente real.

## Pré-requisitos

- Docker Engine/Compose operantes, VPS com acesso externo **de saída** aos sites das bancas; DNS confiável.
- HTTPS público via Nginx/Caddy/Traefik existente; rota do domínio dedicado para `127.0.0.1:8765`.
- Credencial longa e única no `.env`, `RADAR_COOKIE_SECURE=1`, chave Fernet **distinta do Life** se for usar MFA.
- Espaço no volume para banco; backups seguros fora da VPS. Firewall bloqueando porta 8765 da interface pública.
- Não importar credenciais ou arquivos `.env` do Life (podem conter segredos particulares).

## Teste local antes do primeiro deploy

```bash
cp .env.example .env
# senha segura, RADAR_COOKIE_SECURE=0 em http://localhost
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=150 concurso-radar radar-worker
curl -fsS http://127.0.0.1:8765/healthz
```

Entre com a senha, ative/desative MFA com QR Code e códigos de recuperação, clique `Verificar agora`, espere a varredura e veja **Fontes**. Confirme em ao menos 3 bancas o link verdadeiro do edital e a associação salário–cargo. Cuidado: uma aba “Fontes” vazia ou cheia de erros significa **sem cobertura**, não “nenhum concurso”.

## Integração à stack central

1. Defina um hostname próprio, por exemplo `radar.speedlora.com`, apenas após DNS/SSL configurados. É um **exemplo**, não uma alteração de DNS feita pelo projeto.
2. Verifique quais portas e redes o Life/Research/English já utilizam (`docker compose ps` e `ss -lntp`). O Compose isolado do Radar fixa loopback `127.0.0.1:8765:8765`, que é seguro **somente se 8765 estiver livre**.
3. Copie a pasta do Radar para diretório próprio (`/opt/speedlora-concurso-radar` é exemplo). Defina `.env` na VPS com permissão restrita e NÃO versionado.
4. Se a stack central do Life é o orquestrador único, adapte os **dois serviços** `concurso-radar` e `radar-worker` para sua rede/reverse proxy existente, preservando `RADAR_DB=/data/radar.sqlite3` e `concurso_radar_data` como volume próprio. Não misture volumes.
5. Crie a rota HTTPS do proxy para a porta do Radar e configure `RADAR_COOKIE_SECURE=1`. Não exponha container/banco diretamente ao público.
6. Realize primeiro teste de autenticação, MFA, renovação da sessão, logout, CSS/mobile, varredura real, alertas e persistência; só depois considere a entrega homologada na VPS.

## Migração da v1.1

1. **Faça backup online consistente da v1.1** com a API SQLite `backup()` e transfira o arquivo para fora da VPS.
2. Anote `docker volume ls` e `docker compose config`: se seu projeto Compose mudou de diretório, o volume físico pode mudar de nome por causa do prefixo. Utilize explicitamente o volume existente ou restaure o backup no novo volume. Não presuma que `concurso_radar_data` sem prefixo é sempre o mesmo volume físico.
3. Pare o Compose antigo com `docker compose down`, **nunca `down -v`**.
4. Inicie a v2 usando **o volume correto**. `core.init_db()` adiciona tabelas de evidência, sessões e controle de fontes sem recriar `opportunities`.
5. Verifique registros, IDs, favoritos, inscrições e notas após subir. Registros antigos continuam existentes, mas não terão selo de edital confirmado até serem revalidados. Refaça o login.
6. Para rollback, pare a v2 sem `-v`, restaure o backup SQLite e use as imagens/configurações da v1.1. Não mantenha v1.1 e v2 escrevendo no mesmo banco simultaneamente.

## Backup recomendado

Dentro do contêiner que tenha acesso ao volume:

```bash
docker compose exec concurso-radar python -c "import sqlite3; a=sqlite3.connect('/data/radar.sqlite3'); b=sqlite3.connect('/data/backup.sqlite3'); a.backup(b); b.close(); a.close()"
```

**Copie `/data/backup.sqlite3` para armazenamento externo**; essa etapa depende de descobrir o ID real do contêiner com `docker compose ps -q concurso-radar` e usar `docker cp`. Não inclua `.env`, chave MFA, tokens SMTP/Telegram nem backup do banco no ZIP público.

## Controles de aceite em produção

- `GET /healthz` 200; `GET /api/opportunities` 401 sem login.
- Login senha apenas; ativar MFA exige senha, QR/TOTP; novo login exige TOTP; logout encerra sessão; recuperação é de uso único.
- Interface móvel sem corte em 320/375/768/1024px e temas SoftLight/SpeedLora (ainda requer teste visual).
- Coleta mostra falhas reais; roda na inicialização e no intervalo das 3h; a falha não marca sucesso.
- CSV, filtros, favoritos, inscritos, alertas, edição e revalidação funcionam.
- `docker compose down` + `up -d` preservam dados; `down -v` apaga e deve ser proibido na operação comum.
- Proxy HTTPS e cookies seguros; sem `http://` público nem `RADAR_COOKIE_SECURE=0` em produção.
