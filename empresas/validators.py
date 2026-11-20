import re

from django.core.exceptions import ValidationError

PESOS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
PESOS_2 = [6] + PESOS_1


def limpar_documento(valor):
    """Tira a máscara e mantém letras e números, em maiúsculas."""
    return re.sub(r"[^0-9A-Za-z]", "", valor or "").upper()


def _digito_cnpj(base, pesos):
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj):
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj) or cnpj == cnpj[0] * 14:
        return False
    d1 = _digito_cnpj(cnpj[:12], PESOS_1)
    d2 = _digito_cnpj(cnpj[:12] + d1, PESOS_2)
    return cnpj[12:] == d1 + d2


def cpf_valido(cpf):
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(cpf[n]):
            return False
    return True


def validar_documento(valor):
    doc = limpar_documento(valor)
    if len(doc) == 11:
        if not cpf_valido(doc):
            raise ValidationError("CPF inválido.")
    elif len(doc) == 14:
        if not cnpj_valido(doc):
            raise ValidationError("CNPJ inválido.")
    else:
        raise ValidationError("Informe um CPF (11 números) ou um CNPJ (14 caracteres).")


def validar_cpf(valor):
    if not cpf_valido(limpar_documento(valor)):
        raise ValidationError("CPF inválido.")
