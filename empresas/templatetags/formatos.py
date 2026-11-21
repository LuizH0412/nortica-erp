from django import template

register = template.Library()


@register.filter
def documento(valor):
    v = valor or ""
    if len(v) == 11:
        return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"
    if len(v) == 14:
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
    return v

@register.filter
def moeda(valor):
    """1234.5 -> "R$ 1.234,50" (sempre no formato brasileiro)."""
    from decimal import Decimal, InvalidOperation
    try:
        numero = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    sinal = "-" if numero < 0 else ""
    texto = f"{abs(numero):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sinal}R$ {texto}"


@register.filter
def quantidade(valor):
    """12.500 -> "12,5"; 3.000 -> "3"; 1234.25 -> "1.234,25" (até 3 casas, sem zeros sobrando)."""
    from decimal import Decimal, InvalidOperation
    try:
        numero = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    texto = f"{numero:,.3f}".rstrip("0").rstrip(".")
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter
def ha_quanto(data):
    """ "há 5 minutos" / "agora mesmo" (sem o estranho "há 0 minutos")."""
    from django.utils import timezone
    from django.utils.timesince import timesince

    if not data:
        return ""
    if (timezone.now() - data).total_seconds() < 60:
        return "agora mesmo"
    return f"há {timesince(data)}"
