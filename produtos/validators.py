from django.core.exceptions import ValidationError


def gtin_valido(codigo):
    """Código de barras GTIN (EAN-8, UPC-12, EAN-13, DUN-14) com dígito verificador correto."""
    if not codigo.isdigit() or len(codigo) not in (8, 12, 13, 14):
        return False
    corpo, digito = codigo[:-1], int(codigo[-1])
    # Da direita para a esquerda, pesos 3, 1, 3, 1...
    soma = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(corpo)))
    return (10 - soma % 10) % 10 == digito


def validar_gtin(valor):
    if valor and not gtin_valido(valor):
        raise ValidationError(
            "Código de barras inválido: confira os números (8, 12, 13 ou 14 dígitos, com o verificador)."
        )
