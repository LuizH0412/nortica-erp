from django.db import models


class CadastroSimples(models.Model):
    """
    Base dos cadastros auxiliares que só têm nome: função, setor, tipo de cliente, área, TAG...
    São geridos pela janela do "+" ao lado do campo (core/cadastros_simples.py).
    """

    artigo = "o"  # "a" para nomes femininos (função, área, TAG): usado nas mensagens

    nome = models.CharField("Nome", max_length=60, unique=True)
    # Desativado some das opções dos cadastros, mas continua onde já estava em uso
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        abstract = True
        ordering = ["nome"]

    def __str__(self):
        return self.nome
