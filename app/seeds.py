"""Initial records carried over from v1.1. They stay pending until a notice is re-validated."""

import hashlib

from . import repository as repo


def seed_official():
    """Only records whose salient fields were checked against government/organizer pages 2026-10-16.
    Never clobber user edits on restarts. Exam date IFSP deliberately unset without primary confirmation.
    """
    seeds = [
        {
            'title': 'CGU 2026 — Auditor TI · Desenvolvimento de Sistemas',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Desenvolvimento de Sistemas',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'notice_url': 'https://www.gov.br/cgu/pt-br/acesso-a-informacao/concursos',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Desenvolvimento de Sistemas; outras 20 em Ciência de Dados e Infraestrutura. Prova em todas as capitais. Inscrição R$ 170; conferir retificações.',
        },
        {
            'title': 'CGU 2026 — Auditor TI · Ciência de Dados',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Ciência de Dados',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Ciência de Dados; lotação em Brasília; confirmar pré-requisitos no edital.',
        },
        {
            'title': 'CGU 2026 — Auditor TI · Infraestrutura',
            'agency': 'Controladoria-Geral da União (CGU)',
            'position': 'Auditor Federal de Finanças e Controle — TI / Infraestrutura de TI',
            'salary_min': 20000.0,
            'salary_max': 20000.0,
            'registration_start': '2026-10-10',
            'registration_end': '2026-11-04',
            'exam_date': '2026-12-13',
            'exam_cities': 'São Paulo/SP e demais capitais',
            'work_cities': 'Brasília/DF',
            'state': 'DF',
            'exam_in_sp': 1,
            'work_in_sp': 0,
            'national': 1,
            'reviewed': 1,
            'official_url': 'https://www.gov.br/cgu/pt-br/assuntos/noticias/2026/defeso-eleitoral/cgu-publica-edital-de-concurso-para-60-vagas-de-auditor-federal-de-financas-e-controle',
            'apply_url': 'https://www.cebraspe.org.br/concursos/CGU_26_AFFC',
            'source': 'CGU / Cebraspe (fonte oficial)',
            'confidence': 'official',
            'notes': '10 vagas em Infraestrutura de TI; lotação em Brasília.',
        },
        {
            'title': 'IFSP 183/2026 — Professor de Informática (Campus São Paulo)',
            'agency': 'Instituto Federal de São Paulo (IFSP)',
            'position': 'Professor EBTT — Informática',
            'salary_min': 6397.19,
            'salary_max': 7356.77,
            'registration_end': '2026-11-17',
            'exam_cities': 'Ver edital/convocação',
            'work_cities': 'São Paulo/SP',
            'state': 'SP',
            'exam_in_sp': 0,
            'work_in_sp': 1,
            'national': 0,
            'reviewed': 1,
            'confidence': 'official',
            'status_override': 'open',
            'official_url': 'https://spo.ifsp.edu.br/destaques/4723-edital-ifsp-%E2%80%94-concurso-p%C3%BAblico-para-contrata%C3%A7%C3%A3o-de-professores',
            'apply_url': 'https://concursopublico.ifsp.edu.br/editais/edital-1832026-docentes',
            'source': 'IFSP (fonte oficial)',
            'notes': 'Prazo até 17/11/2026 confirmado. Salário-base de acordo com página oficial, antes de adicionais/titulação. Início de inscrição e cidade exata da prova exigem checagem no edital. Site oficial confirma que as inscrições estão abertas; a marcação é válida apenas até o prazo de encerramento.',
        },
    ]
    for seed in seeds:
        # Distinguish different CGU specializations even though URL is identical.
        seed['fingerprint'] = hashlib.sha256(f'official2026|{seed["title"]}'.encode()).hexdigest()[:32]
        repo.upsert(seed)
