"""
Fotos do produto: o que pode ser enviado.

O tipo é conferido pelo conteúdo do arquivo (assinatura), não pelo nome: um ".jpg" que não é imagem é recusado.
"""
from django.core.exceptions import ValidationError

TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB por foto
MAXIMO_POR_PRODUTO = 20
FORMATOS = "JPG, PNG, WEBP ou GIF"


def _tipo_pelo_conteudo(inicio):
    if inicio.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if inicio.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if inicio[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if inicio[:4] == b"RIFF" and inicio[8:12] == b"WEBP":
        return ".webp"
    return None


def validar_foto(arquivo):
    """Confere tamanho e tipo; devolve a extensão certa para gravar. Erro: ValidationError com a mensagem."""
    nome = arquivo.name
    if arquivo.size > TAMANHO_MAXIMO:
        raise ValidationError(f"{nome}: maior que 5 MB.")
    if arquivo.size == 0:
        raise ValidationError(f"{nome}: arquivo vazio.")
    arquivo.seek(0)
    extensao = _tipo_pelo_conteudo(arquivo.read(16))
    arquivo.seek(0)
    if extensao is None:
        raise ValidationError(f"{nome}: não é uma imagem {FORMATOS}.")
    return extensao
