"""Text normalisation and IT vocabulary shared by collectors, evidence checks and search."""

import re
import unicodedata


def fold(value):
    """Lower-case and strip accents: 'Informática' -> 'informatica'."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')) if not unicodedata.combining(c)).lower()


def is_it(text):
    """True when a cargo/description clearly belongs to IT."""
    t = fold(text)
    words = (
        'tecnologia da informacao',
        'informatica',
        'desenvolvimento de sistemas',
        'desenvolvedor',
        'programador',
        'analista de sistemas',
        'engenharia de software',
        'software',
        'seguranca da informacao',
        'ciencia de dados',
        'cientista de dados',
        'infraestrutura de ti',
        'governanca de ti',
        'analista de ti',
        'tecnico de ti',
        'redes de computadores',
        'banco de dados',
        'computacao',
        'suporte tecnico',
        'sistemas da informacao',
        'cybersecurity',
        'data engineer',
        'sistemas de informacao',
    )
    return any(w in t for w in words) or bool(re.search(r'\bti\b', t))
