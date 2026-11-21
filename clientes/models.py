from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import CadastroSimples
from empresas.validators import validar_documento


class TipoCliente(CadastroSimples):
    class Meta(CadastroSimples.Meta):
        verbose_name = "tipo de cliente"
        verbose_name_plural = "tipos de cliente"


class Area(CadastroSimples):
    """Região ou rota de atendimento (ex.: Centro, Zona Norte, Rota 2)."""

    artigo = "a"

    class Meta(CadastroSimples.Meta):
        verbose_name = "área"
        verbose_name_plural = "áreas"


class Tag(CadastroSimples):
    """TAG de classificação: marcadores livres para agrupar clientes (VIP, Atacado...)."""

    artigo = "a"

    class Meta(CadastroSimples.Meta):
        verbose_name = "TAG"
        verbose_name_plural = "TAGs"


class Cliente(models.Model):
    """Cliente do Nexum. É compartilhado entre todas as empresas da instância."""

    class Pessoa(models.TextChoices):
        FISICA = "F", "Física"
        JURIDICA = "J", "Jurídica"

    class Contribuinte(models.TextChoices):
        # Códigos do "indicador da IE do destinatário" da NF-e
        CONTRIBUINTE = "1", "Contribuinte ICMS"
        ISENTO = "2", "Contribuinte isento"
        NAO_CONTRIBUINTE = "9", "Não contribuinte"

    class Finalidade(models.TextChoices):
        # Códigos do "indicador de consumidor final" da NF-e
        CONSUMIDOR_FINAL = "1", "Consumidor final"
        NORMAL = "0", "Normal (revenda/industrialização)"

    # Dados cadastrais
    pessoa = models.CharField("Pessoa", max_length=1, choices=Pessoa.choices, default=Pessoa.FISICA)
    documento = models.CharField("CPF/CNPJ", max_length=14, blank=True, validators=[validar_documento])
    inscricao_estadual = models.CharField("Inscrição estadual", max_length=20, blank=True)
    inscricao_municipal = models.CharField("Inscrição municipal", max_length=20, blank=True)
    contribuinte = models.CharField(
        "Contribuinte", max_length=1, choices=Contribuinte.choices, default=Contribuinte.NAO_CONTRIBUINTE,
        help_text="Situação do cliente perante o ICMS (vai na nota fiscal).",
    )
    razao_social = models.CharField("Razão social", max_length=150)
    nome_fantasia = models.CharField("Nome fantasia", max_length=150, blank=True)

    # Endereço principal
    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("Endereço", max_length=150, blank=True)
    numero = models.CharField("Número", max_length=10, blank=True)
    complemento = models.CharField("Complemento", max_length=80, blank=True)
    ponto_referencia = models.CharField("Ponto de referência", max_length=150, blank=True)
    bairro = models.CharField("Bairro", max_length=80, blank=True)
    municipio = models.ForeignKey(
        "localidades.Municipio", verbose_name="Cidade", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    # Classificação e atendimento
    area = models.ForeignKey(
        Area, verbose_name="Área", null=True, blank=True, on_delete=models.PROTECT, related_name="clientes",
    )
    atendente = models.ForeignKey(
        "funcionarios.Funcionario", verbose_name="Atendente", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="clientes_atendidos",
    )
    indicador_finalidade = models.CharField(
        "Indicador de finalidade", max_length=1, choices=Finalidade.choices, default=Finalidade.CONSUMIDOR_FINAL,
    )
    tipo_cliente = models.ForeignKey(
        TipoCliente, verbose_name="Tipo de cliente", null=True, blank=True,
        on_delete=models.PROTECT, related_name="clientes",
    )
    data_fundacao = models.DateField("Data de fundação / nascimento", null=True, blank=True)
    tags = models.ManyToManyField(Tag, verbose_name="TAGs de classificação", blank=True, related_name="clientes")

    bloqueado = models.BooleanField(
        "Bloqueado", default=False, help_text="Cliente bloqueado não pode fazer novas compras.",
    )
    # Financeiro
    limite_credito = models.DecimalField(
        "Limite para compra a prazo", max_digits=12, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Quanto o cliente pode ter em aberto comprando a prazo. Zero = sem limite liberado.",
    )
    ativo = models.BooleanField("Ativo", default=True)
    observacao = models.TextField("Observação", blank=True)

    cadastrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Cadastrado por", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+", editable=False,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["razao_social"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [
            models.UniqueConstraint(
                fields=["documento"], condition=~models.Q(documento=""), name="cliente_documento_unico",
                violation_error_message="Já existe um cliente com este CPF/CNPJ.",
            ),
        ]

    def __str__(self):
        return self.nome_exibicao

    @property
    def nome_exibicao(self):
        return self.nome_fantasia or self.razao_social

    @property
    def eh_pessoa_fisica(self):
        return self.pessoa == self.Pessoa.FISICA


class EnderecoCliente(models.Model):
    """Endereços além do principal (aba "Outros endereços")."""

    class Tipo(models.TextChoices):
        COBRANCA = "cobranca", "Cobrança"
        TRABALHO = "trabalho", "Trabalho"
        ENTREGA = "entrega", "Entrega"
        OUTRO = "outro", "Outro"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="enderecos")
    tipo = models.CharField("Tipo", max_length=10, choices=Tipo.choices, default=Tipo.COBRANCA)
    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("Endereço", max_length=150)
    numero = models.CharField("Número", max_length=10)
    complemento = models.CharField("Complemento", max_length=80, blank=True)
    ponto_referencia = models.CharField("Ponto de referência", max_length=150, blank=True)
    bairro = models.CharField("Bairro", max_length=80)
    municipio = models.ForeignKey(
        "localidades.Municipio", verbose_name="Cidade", on_delete=models.PROTECT, related_name="+",
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "pk"]
        verbose_name = "endereço do cliente"
        verbose_name_plural = "endereços do cliente"

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.logradouro}, {self.numero}"


class MovimentoCredito(models.Model):
    """
    Crédito do cliente na loja (ex.: devolução, adiantamento). Entrada = crédito; saída = débito
    (uso do crédito numa venda, quando o módulo de vendas existir). Saldo = créditos - débitos.
    """

    class Tipo(models.TextChoices):
        CREDITO = "C", "Crédito"
        DEBITO = "D", "Débito"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="movimentos_credito")
    tipo = models.CharField("Tipo", max_length=1, choices=Tipo.choices, default=Tipo.CREDITO)
    valor = models.DecimalField(
        "Valor", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
    )
    pedido = models.CharField("Pedido", max_length=30, blank=True)
    descricao = models.CharField("Descrição", max_length=150, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Lançado por", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    criado_em = models.DateTimeField("Data", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "movimento de crédito"
        verbose_name_plural = "movimentos de crédito"

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.valor} para {self.cliente}"

    @property
    def valor_com_sinal(self):
        return self.valor if self.tipo == self.Tipo.CREDITO else -self.valor


class ContatoCliente(models.Model):
    """Contatos do cliente (aba "Contatos"). Só um pode ser o principal."""

    class Tipo(models.TextChoices):
        PRINCIPAL = "principal", "Principal"
        OUTROS = "outros", "Outros"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contatos")
    tipo = models.CharField("Tipo", max_length=10, choices=Tipo.choices, default=Tipo.PRINCIPAL)
    nome = models.CharField("Contato", max_length=100, help_text="Nome da pessoa ou do setor.")
    ddd = models.CharField("DDD", max_length=2)
    telefone = models.CharField("Telefone", max_length=9)
    email = models.EmailField("E-mail", blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # O principal sempre primeiro; depois por nome
        ordering = [
            models.Case(models.When(tipo="principal", then=models.Value(0)), default=models.Value(1)),
            "nome",
        ]
        verbose_name = "contato do cliente"
        verbose_name_plural = "contatos do cliente"

    def __str__(self):
        return f"{self.nome} ({self.telefone_formatado})"

    @property
    def telefone_formatado(self):
        t = self.telefone
        numero = f"{t[:-4]}-{t[-4:]}" if len(t) >= 8 else t
        return f"({self.ddd}) {numero}"

    @property
    def eh_principal(self):
        return self.tipo == self.Tipo.PRINCIPAL
