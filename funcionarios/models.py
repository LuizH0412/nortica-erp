from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import CadastroSimples
from empresas.validators import validar_cpf

PERCENTUAL = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]


class Funcao(CadastroSimples):
    artigo = "a"

    class Meta(CadastroSimples.Meta):
        verbose_name = "função"
        verbose_name_plural = "funções"


class Setor(CadastroSimples):
    class Meta(CadastroSimples.Meta):
        verbose_name = "setor"
        verbose_name_plural = "setores"


class Funcionario(models.Model):
    """
    Funcionário do cliente. É compartilhado entre todas as empresas da instância;
    em quais empresas ele entra no sistema é definido no usuário de acesso.
    """

    nome = models.CharField("Nome", max_length=150)
    funcao = models.ForeignKey(
        Funcao, verbose_name="Função", on_delete=models.PROTECT, related_name="funcionarios",
    )
    setor = models.ForeignKey(
        Setor, verbose_name="Setor", null=True, blank=True,
        on_delete=models.PROTECT, related_name="funcionarios",
    )

    # Dados pessoais
    cpf = models.CharField("CPF", max_length=11, blank=True, validators=[validar_cpf])
    rg = models.CharField("RG", max_length=20, blank=True)
    data_admissao = models.DateField("Data de admissão", null=True, blank=True)
    data_demissao = models.DateField("Data de demissão", null=True, blank=True)

    # Endereço
    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("Endereço", max_length=150, blank=True)
    numero = models.CharField("Número", max_length=10, blank=True)
    complemento = models.CharField("Complemento", max_length=80, blank=True)
    bairro = models.CharField("Bairro", max_length=80, blank=True)
    municipio = models.ForeignKey(
        "localidades.Municipio", verbose_name="Cidade", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )
    ponto_referencia = models.CharField("Ponto de referência", max_length=150, blank=True)

    # Vendas
    desconto_maximo = models.DecimalField(
        "Desconto máximo (%)", max_digits=5, decimal_places=2,
        default=Decimal("0"), validators=PERCENTUAL,
        help_text="Maior desconto que pode dar numa venda.",
    )
    comissao = models.DecimalField(
        "Comissão (%)", max_digits=5, decimal_places=2,
        default=Decimal("0"), validators=PERCENTUAL,
    )
    supervisor = models.BooleanField(
        "Supervisor", default=False,
        help_text="Pode autorizar operações de outros funcionários com o cartão.",
    )
    # Guardado como hash, igual a uma senha: o sistema só confere, nunca mostra
    cartao_supervisor = models.CharField("Cartão do supervisor", max_length=128, blank=True)

    observacao = models.TextField("Observação", blank=True)
    ativo = models.BooleanField("Ativo", default=True)

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="Usuário de acesso", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="funcionario",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "funcionário"
        verbose_name_plural = "funcionários"
        constraints = [
            models.UniqueConstraint(
                fields=["cpf"], condition=~models.Q(cpf=""), name="funcionario_cpf_unico",
            ),
        ]

    def __str__(self):
        return self.nome

    def sincronizar_usuario(self):
        """O usuário de acesso leva o nome do funcionário e só entra se ele estiver ativo."""
        usuario = self.usuario
        if usuario is None:
            return
        usuario.first_name, usuario.last_name = self.nome[:150], ""
        usuario.is_active = self.ativo
        usuario.save(update_fields=["first_name", "last_name", "is_active"])

    @property
    def tem_cartao(self):
        return bool(self.cartao_supervisor)

    def definir_cartao(self, numero):
        self.cartao_supervisor = make_password(numero) if numero else ""

    def confere_cartao(self, numero):
        return bool(self.supervisor and self.cartao_supervisor and numero) and check_password(
            numero, self.cartao_supervisor
        )
