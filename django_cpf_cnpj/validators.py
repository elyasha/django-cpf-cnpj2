from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

import re


# ---------------------------------------------------------------------------
# CPF helpers
# ---------------------------------------------------------------------------

def last_digits_cpf(value):
    v1, v2 = 0, 0
    for i, d in enumerate(map(int, value[:-2][::-1])):
        v1 += d * (9 - (i % 10))
        v2 += d * (9 - (i + 1) % 10)

    v1 = (v1 % 11) % 10
    v2 = ((v2 + v1 * 9) % 11) % 10

    return v1, v2


def is_valid_cpf(value):
    if not isinstance(value, str) and not isinstance(value, int):
        return False

    value = re.sub(r'\D', '', str(value)).zfill(11)
    if len(re.sub(r'([0-9])\1+', r'\1', value)) == 1 or len(value) != 11:
        return False

    v1, v2 = last_digits_cpf(value)

    if v1 != int(value[-2]) or v2 != int(value[-1]):
        return False

    return True


def cpf_generator(value):
    value = re.sub(r'\D', '', str(value)).zfill(9)[:9]

    v1, v2 = last_digits_cpf(value + 'xx')

    new = value + str(v1) + str(v2)

    if not is_valid_cpf(new):
        new = None

    return new


def cpf_random_generator():
    import random

    candidate = str(random.randint(1, 999999998))
    while not cpf_generator(candidate):
        candidate = str(random.randint(1, 999999998))

    return cpf_generator(candidate)


def validate_cpf(value):
    if not is_valid_cpf(value):
        raise ValidationError(
            _('({value}) is not valid cpf.').format(value=value)
        )


# ---------------------------------------------------------------------------
# CNPJ helpers  —  suporte a CNPJ alfanumérico (Receita Federal 2026)
#
# Regras do novo algoritmo:
#   • Os 12 primeiros caracteres (raiz + ordem) podem ser 0-9 ou A-Z.
#   • Os 2 últimos caracteres (dígitos verificadores) são SEMPRE 0-9.
#   • Cada caractere é convertido para inteiro:
#       dígitos  → seu próprio valor (0-9)
#       letras   → A=10, B=11, …, Z=35
#   • Os pesos são os mesmos do algoritmo numérico clássico.
#   • CNPJs puramente numéricos continuam válidos com o novo algoritmo.
# ---------------------------------------------------------------------------

# Alfabeto permitido para os 12 primeiros caracteres
_CNPJ_ALPHA = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
_CNPJ_CHAR_VALUE = {c: i for i, c in enumerate(_CNPJ_ALPHA)}

_WEIGHTS_V1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_V2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3)


def _cnpj_char_to_int(c: str) -> int:
    """Converte um caractere alfanumérico de CNPJ para seu valor inteiro."""
    try:
        return _CNPJ_CHAR_VALUE[c.upper()]
    except KeyError:
        raise ValueError(f"Caractere inválido para CNPJ alfanumérico: {c!r}")


def _normalize_cnpj(value: str) -> Optional[str]:
    """
    Remove máscara (pontos, barra, hífen) e normaliza para maiúsculas.
    Retorna None se o resultado não tiver 14 caracteres ou contiver
    caracteres fora do alfabeto permitido.
    """
    # Remove separadores comuns: . / -
    cleaned = re.sub(r'[.\-/]', '', str(value)).upper().strip()

    if len(cleaned) != 14:
        return None

    # Os 12 primeiros podem ser alfanuméricos; os 2 últimos devem ser dígitos
    if not all(c in _CNPJ_CHAR_VALUE for c in cleaned[:12]):
        return None
    if not cleaned[12:].isdigit():
        return None

    return cleaned


def last_digits_cnpj(value: str):
    """
    Calcula os dois dígitos verificadores de um CNPJ (numérico ou
    alfanumérico).

    *value* deve conter os 12 primeiros caracteres já normalizados
    (sem máscara, maiúsculos).  Os dígitos verificadores já existentes
    no final, caso presentes, são ignorados — apenas os 12 primeiros
    caracteres são usados.
    """
    root = value[:12]
    nums = [_cnpj_char_to_int(c) for c in root]

    v1 = sum(w * n for w, n in zip(_WEIGHTS_V1, nums)) % 11
    v1 = 0 if v1 < 2 else 11 - v1

    v2 = sum(w * n for w, n in zip(_WEIGHTS_V2, nums)) % 11 + v1 * 2
    v2 = v2 % 11
    v2 = 0 if v2 < 2 else 11 - v2

    return v1, v2


def is_valid_cnpj(value) -> bool:
    """
    Valida CNPJ numérico *ou* alfanumérico.

    Aceita strings com ou sem máscara (XX.XXX.XXX/XXXX-XX).
    Rejeita CNPJs com todos os 14 caracteres iguais (sequências inválidas).
    """
    if not isinstance(value, (str, int)):
        return False

    normalized = _normalize_cnpj(str(value))
    if normalized is None:
        return False

    # Rejeita sequências triviais (ex.: "00000000000000", "AAAAAAAAAAAAAA")
    if len(set(normalized)) == 1:
        return False

    v1, v2 = last_digits_cnpj(normalized)

    if v1 != int(normalized[12]) or v2 != int(normalized[13]):
        return False

    return True


def cnpj_generator(value) -> Optional[str]:
    """
    Gera um CNPJ válido a partir dos 12 primeiros caracteres fornecidos.

    *value* pode ser numérico ou alfanumérico (com ou sem máscara).
    Retorna None se os caracteres de entrada forem inválidos.
    """
    cleaned = re.sub(r'[.\-/]', '', str(value)).upper().strip()
    # Preenche com zeros à esquerda se necessário, até 12 caracteres
    cleaned = cleaned.zfill(12)[:12]

    if not all(c in _CNPJ_CHAR_VALUE for c in cleaned):
        return None

    v1, v2 = last_digits_cnpj(cleaned)
    new = cleaned + str(v1) + str(v2)

    return new if is_valid_cnpj(new) else None


def cnpj_random_generator(alpha: bool = False) -> str:
    """
    Gera um CNPJ aleatório válido.

    Args:
        alpha: Se True, gera um CNPJ alfanumérico (raiz pode conter letras).
               Se False (padrão), gera um CNPJ puramente numérico.
    """
    import random

    charset = _CNPJ_ALPHA if alpha else '0123456789'

    while True:
        candidate = ''.join(random.choices(charset, k=12))
        result = cnpj_generator(candidate)
        if result:
            return result


def validate_cnpj(value):
    if not is_valid_cnpj(value):
        raise ValidationError(
            _('({value}) is not valid cnpj.').format(value=value)
        )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # --- CPF ---
    assert not is_valid_cpf('00000000000')
    assert cpf_generator('000.001') == '00000000191'
    assert cpf_generator('999.999.998') == '99999999808'
    assert is_valid_cpf(cpf_random_generator())
    print('CPF: OK')

    # --- CNPJ numérico (compatibilidade retroativa) ---
    assert not is_valid_cnpj('0' * 14)
    assert cnpj_generator('000.001') == '00000000000191'
    assert is_valid_cnpj(cnpj_random_generator())
    print('CNPJ numérico: OK')

    # --- CNPJ alfanumérico ---
    # Geração e validação de round-trip
    for _ in range(10):
        c = cnpj_random_generator(alpha=True)
        assert is_valid_cnpj(c), f"CNPJ alfanumérico inválido gerado: {c}"

    # Exemplo fixo: raiz com letras, dígitos verificadores calculados
    sample_root = 'A1B2C3D4E5F6'
    v1, v2 = last_digits_cnpj(sample_root)
    sample_cnpj = sample_root + str(v1) + str(v2)
    assert is_valid_cnpj(sample_cnpj), f"Falha na validação: {sample_cnpj}"

    # Mascara deve ser aceita
    masked = f'{sample_cnpj[:2]}.{sample_cnpj[2:5]}.{sample_cnpj[5:8]}/{sample_cnpj[8:12]}-{sample_cnpj[12:]}'
    assert is_valid_cnpj(masked), f"Falha com máscara: {masked}"

    # Caractere inválido deve retornar False
    assert not is_valid_cnpj('A1B2C3D4E5F!12')

    print('CNPJ alfanumérico: OK')
    print(f'Exemplo CNPJ alfanumérico: {sample_cnpj}  (mascarado: {masked})')
    print(f'CNPJ aleatório alfanumérico: {cnpj_random_generator(alpha=True)}')