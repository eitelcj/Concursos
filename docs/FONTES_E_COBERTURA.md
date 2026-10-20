# Catálogo de fontes: oficiais, mas não necessariamente cobertas por completo

Somente sites de órgãos/bancas oficiais constam na configuração `app/collectors.py`. Nenhum feed Google, PCI, cursinho ou notícia compõe a coleta.

| Fonte | Tipo na v2 | Regra de cobertura |
|---|---|---|
| Vunesp — inscrições abertas | Catálogo de concursos | Descoberta de detalhes e links de edital; páginas com JS/paginação podem ficar parciais |
| Vunesp — próximos | Catálogo de concursos | Mesmo controle; `https://www.vunesp.com.br/busca/concurso/proximo` |
| FGV Conhecimento | Catálogo de concursos | Links de detalhe e documentos de abertura; cobertura real depende do HTML publicado |
| Fundação Carlos Chagas | Catálogo de concursos | Seletor por vagas/concursos + edital; falha se não houver links processáveis |
| IBAM | Listagem de concursos e cargos | Inspeciona blocos por certame, sem fundir concursos do mesmo endereço |
| ABCP | Catálogo de concursos | Exige link de abertura e documento legível |
| Cebraspe — CGU | Página oficial específica | **Não** cobre os demais concursos do Cebraspe; página pode depender de JavaScript |
| IFSP — Edital 183/2026 | Página oficial específica | **Não** cobre todos os IFs; requer PDF/link de abertura |
| Prefeitura de Campinas | Vigia de página institucional | Monitora mudanças; **não** cataloga automaticamente todos os editais municipais |
| Diário Oficial do Estado de SP | Vigia de página institucional | Monitora mudanças; **não** lê integralmente o DOE nem extrai cada edital |

**TOTAL: 10 configurações oficiais, sendo seis catálogos, duas páginas de concursos específicos e dois monitores genéricos de alterações.** Isso **não representa 10 coletores exaustivos**. Uma fonte só é saudável quando a coleta chega ao documento com sucesso; apenas ler a página inicial não permite concluir que cobriu todos os concursos.

## Quais concursos ainda podem escapar?

- Prefeituras e câmaras da região de Campinas que contratam banca própria ou publicam só em PDF no diário municipal.
- Concursos de TI incluídos em editais de dezenas de cargos, em tabelas complexas ou digitalizadas.
- Links carregados via JavaScript e paginação “mostrar mais” da Vunesp.
- Concursos nacionais cuja prova em São Paulo está em outro anexo não lido automaticamente.
- Retificações publicadas em canais diversos da página principal rastreada.

**Por isso a versão 2 é conservadora:** exibe explicitamente a cobertura parcial e a lista de candidatos, não simula certeza ou afirma “nenhum concurso disponível”. Para chegar mais perto do objetivo de não perder oportunidades, deverão ser homologados e expandidos **adaptadores por órgão/município** e todos os paginadores oficiais, com testes reais em cada atualização de layout.

## Política para novas fontes

Adicionar uma fonte exige (a) comprovação do domínio oficial e relação banca–órgão quando aplicável; (b) link direto de edital de abertura; (c) teste de extração de cargo de TI; (d) teste de pagamento/inscrições e retificações; (e) teste da paginação; (f) teste de erro visível quando o site mudar. Não inserir um portal só porque menciona concursos.

## Políticas de acesso v2.0.2

Uma resposta HTTP 403 é tratada como uma decisão do portal. Não é convertida em "fonte íntegra" apenas porque sua URL foi localizada em um buscador. O Radar cancela futuras requisições automáticas ao mesmo domínio por 12 horas e registra o motivo. Para 429, o `Retry-After` é respeitado. Ambos ficam visíveis em **Fontes**. Durante uma pausa, use a URL oficial fornecida pela própria fonte, sem redeirecionar o usuário a terceiros não oficiais.

O paralelismo se limita a domínios independentes. Não se tenta contornar bloqueio com IP alternativo, proxies rotativos, disfarce de navegador ou alteração artificial de identidade. A cobertura real continua dependendo da política e da disponibilidade de cada fonte; **nenhuma garantia de 100% dos editais**.
