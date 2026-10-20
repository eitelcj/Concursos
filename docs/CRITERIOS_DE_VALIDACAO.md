# Portão documental — o que é (e não é) um concurso válido

## Regras não negociáveis

1. **Emissor primário reconhecível:** órgão público ou banca organizadora com domínio HTTPS oficial (por exemplo, gov.br, jus.br, leg.br, universidade pública ou domínios explicitamente permitidos). Domínio parecido, encurtador, post, blog, portal de cursos, agregador e notícia **não são aceitos**. Redirecionamento externo é bloqueado.
2. **Edital de abertura real:** download de documento acessível, identificado como edital original (não resultado, notícia, homologação, anexo aleatório ou retificação isolada). PDF deve permitir extração de texto; HTML só é aceito quando a própria URL é de edital e o corpo demonstra conteúdo substantivo de edital. PDF ilegível => pendência, não confirmação.
3. **Concurso público:** documento deve apresentar contexto de concurso público ou processo seletivo público. O sistema não deve misturar **licitação pública** (contratação de empresas) com concurso de vagas para pessoas.
4. **Cargo TI:** precisa existir no edital. Uma listagem genérica com “diversos cargos” não demonstra vaga de TI. Dados a confirmar por cargo específico, não por faixa de salário de todos os cargos.
5. **Inscrições:** abertura e encerramento exigem datas explícitas do documento próximas a termos como “inscrições”/“cronograma”. Sem as **duas** datas, não mostrar “Inscrições abertas” só por notícia ou botão da banca. Vencido o prazo confirmado => encerrado, até haver retificação oficial.
6. **Salário:** atribuir somente valores vinculados ao **cargo específico de TI**, nunca salário máximo do edital geral ou bônus sem fonte. Valor de R$7.000 é prioridade visual somente depois de prova documental.
7. **Prova x lotação:** cidade da prova e cidade de trabalho são fatos separados. Concurso em Brasília pode ser elegível se a prova em SP estiver documentada. Não inferir local da prova pela sede do órgão.
8. **Retificações:** novos documentos, erratas, suspensões e alterações podem substituir inscrições, prova, cargo, salário ou vaga. Detectada mudança no documento oficial ou novos links de retificação, revogar a aprovação anterior e pedir conferência humana.
9. **Rastreabilidade:** cada confirmação guarda link, SHA-256 do documento, timestamp da conferência e trecho que demonstra área de TI. Isso prova qual conteúdo foi lido, **não constitui validação jurídica nem assinatura criptográfica do edital**.
10. **Falhar de forma segura:** timeout, redirecionamento duvidoso, HTML mudado, CAPTCHA, erro no PDF, página sem link de edital, cargo/especialidade ambíguos, várias linhas salariais e informações conflitantes são **pendência/falha visível**, nunca “OK” ou “aberto” presumido.

## O que a implementação garante e o que não garante

**Implementado:** allowlist de domínios oficiais + checagem HTTPS, limites de tamanho, bloqueio de redirecionamentos não oficiais, verificação de contexto do edital, presença de TI, cargo específico, datas, valor salarial próximo ao cargo, hash e revogação por edição/alteração de documento, rastreamento por fonte, estado de pendência e alertas.

**Não automatizado integralmente:** extração semântica de quadros complexos e anexos de cargos, conferência de assinatura/autenticidade jurídica, OCR de PDFs escaneados, navegação avançada em JS/paginação oculta, comparação semântica de **todas** as retificações e checagem de requisitos pessoais/diplomas. Dados aprovados devem ser revistos antes da inscrição, especialmente onde o cargo possui tabela complexa.

## Exemplo

Edital contém “Analista de Sistemas R$ 6.500” e “Procurador R$ 17.000”. O sistema **não** deve destacar Analista como R$17 mil. Se o PDF não permitir associar R$6.500 com Analista sem ambiguidade, o campo de salário permanece pendente.

Edital contém “Provas nas capitais” sem mencionar explicitamente São Paulo. O algoritmo conservador não marca SP automaticamente; exige prova documental específica. O operador consulta o edital/retificação e atualiza ou deixa pendente.

## Avaliação prática para homologação

Use um edital verdadeiro de TI de órgão/banca permitidos e percorra o editor, conferindo link direto, cargo exato, início/fim, cidade de prova, cidade de exercício e valores. Clique **Validar edital**. Depois altere o salário: aprovação deve ser revogada. Teste editar o link para blog externo: API deve rejeitar. Verifique a aba Fontes após varredura: fontes inacessíveis precisam aparecer como falha/sem cobertura. Esse teste com sites reais **ainda depende do ambiente local/VPS**.
