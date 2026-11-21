from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from fiscal.tabelas import REGIMES

from .validators import validar_documento

UFS = [(u, u) for u in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()]


class Empresa(models.Model):
    class TipoInventario(models.TextChoices):
        CONTABIL = "contabil", "Contábil"
        FISICO = "fisico", "Físico"

    class NomeDocumento(models.TextChoices):
        FANTASIA = "fantasia", "Nome fantasia"
        RAZAO = "razao", "Razão social"

    unidade = models.CharField(
        "Unidade", max_length=60, unique=True,
        error_messages={"unique": "Já existe uma empresa com esta unidade."},
        help_text='Nome desta unidade. Ex.: "Matriz", "Filial", "Filial 3".',
    )

    # Dados cadastrais
    razao_social = models.CharField("Razão social", max_length=150)
    nome_fantasia = models.CharField("Nome fantasia", max_length=150, blank=True)
    documento = models.CharField(
        "CPF/CNPJ", max_length=14, unique=True, validators=[validar_documento],
        error_messages={"unique": "Já existe uma empresa com este CPF/CNPJ."},
    )
    inscricao_estadual = models.CharField("Inscrição estadual", max_length=20, blank=True)
    inscricao_municipal = models.CharField("Inscrição municipal", max_length=20, blank=True)

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

    # Contatos
    telefone = models.CharField("Telefone", max_length=11, blank=True)
    email = models.EmailField("E-mail", blank=True)

    # Documentos
    nome_nos_documentos = models.CharField(
        "Nome nos documentos", max_length=10, choices=NomeDocumento.choices,
        default=NomeDocumento.FANTASIA,
        help_text="Nome que sai nos impressos. Sem nome fantasia, usa a razão social.",
    )

    # Fiscal
    regime_tributario = models.CharField(
        "Regime tributário", max_length=15, choices=REGIMES, blank=True,
        help_text="O mesmo código da nota fiscal (CRT), usado também nos vínculos fiscais.",
    )
    aliquota_credito = models.DecimalField(
        "Alíquota de crédito (%)", max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Simples Nacional: percentual de crédito de ICMS informado na nota (pCredSN).",
    )
    tipo_inventario = models.CharField(
        "Tipo de inventário", max_length=10, choices=TipoInventario.choices, default=TipoInventario.CONTABIL,
    )
    deduzir_icms_base_pis_cofins = models.BooleanField(
        "Deduzir ICMS da base do PIS/COFINS", default=False,
        help_text="Exclui o ICMS da base de cálculo do PIS e da COFINS (Tema 69 do STF).",
    )

    ativa = models.BooleanField("Empresa ativa", default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["unidade"]

    @property
    def nome_exibicao(self):
        return self.nome_fantasia or self.razao_social

    @property
    def nome_para_documentos(self):
        if self.nome_nos_documentos == self.NomeDocumento.FANTASIA and self.nome_fantasia:
            return self.nome_fantasia
        return self.razao_social

    @property
    def eh_pessoa_fisica(self):
        return len(self.documento) == 11

    @property
    def codigo_municipio_ibge(self):
        return self.municipio_id

    def __str__(self):
        return f"{self.nome_exibicao} · {self.unidade}"

    def vinculos_que_impedem_exclusao(self):
        """Nomes do que já está ligado a esta empresa. Vazio = pode excluir."""
        # O acesso dos usuários, os saldos (sem movimentação) e a marcação de
        # "produto oculto nesta empresa" somem junto com a empresa
        ignorar = {"acessos", "estoques_produtos", "produtos_ocultos", "detalhes_fiscais_produtos", "certificado"}
        encontrados = []
        for rel in self._meta.related_objects:
            nome = rel.get_accessor_name()
            if nome in ignorar:
                continue
            if rel.many_to_many:
                existe = getattr(self, nome).exists()
            else:
                existe = rel.related_model._base_manager.filter(
                    **{rel.field.name: self}
                ).exists()
            if existe:
                encontrados.append(str(rel.related_model._meta.verbose_name_plural))
        return encontrados


# ---------- Padrão para dados que pertencem a uma empresa ----------

class DadoDaEmpresaQuerySet(models.QuerySet):
    def da_empresa(self, empresa):
        """Só os registros da empresa informada."""
        return self.filter(empresa=empresa)


class DadoDaEmpresa(models.Model):
    """
    Base para todo registro que pertence a uma empresa (matriz/filial):
    produtos, clientes, vendas, lançamentos etc.

        class Produto(DadoDaEmpresa):
            nome = models.CharField(max_length=100)

    - A empresa não aparece nos formulários (editable=False): quem preenche é a
      view, com a empresa atual da sessão (veja empresas.mixins.EmpresaAtualMixin).
    - PROTECT impede excluir uma empresa que já tem dados; a tela de exclusão
      lista esses vínculos (Empresa.vinculos_que_impedem_exclusao).
    - Nas consultas fora das views use Model.objects.da_empresa(empresa).
    """

    empresa = models.ForeignKey(
        "empresas.Empresa", verbose_name="Empresa", on_delete=models.PROTECT,
        editable=False, related_name="%(app_label)s_%(class)s_set",
    )

    objects = DadoDaEmpresaQuerySet.as_manager()

    class Meta:
        abstract = True


# ---------- Certificado digital ----------

class CertificadoDigital(models.Model):
    """
    Certificado A1 da empresa (aba Fiscal). O arquivo e a senha ficam criptografados no banco
    (veja empresas/certificado.py) — nunca na pasta media/, que é pública.
    """

    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="certificado")
    descricao = models.CharField("Descrição", max_length=120)
    nome_arquivo = models.CharField("Arquivo", max_length=150, blank=True)
    arquivo_cifrado = models.BinaryField(editable=False)
    senha_cifrada = models.BinaryField(editable=False)
    titular = models.CharField("Empresa registrada", max_length=200)
    documento = models.CharField("CPF/CNPJ do certificado", max_length=14, blank=True)
    emitido_em = models.DateTimeField("Data de aquisição")
    validade = models.DateTimeField("Data de validade")
    enviado_em = models.DateTimeField(auto_now_add=True)
    enviado_por = models.ForeignKey(
        "contas.Usuario", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )

    AVISO_DIAS = 30  # a partir de quantos dias antes de vencer a tela avisa

    class Meta:
        verbose_name = "certificado digital"
        verbose_name_plural = "certificados digitais"

    def __str__(self):
        return f"{self.titular} (vence em {self.validade:%d/%m/%Y})"

    @property
    def dias_para_vencer(self):
        from django.utils import timezone
        return (self.validade - timezone.now()).days

    @property
    def vencido(self):
        from django.utils import timezone
        return self.validade <= timezone.now()

    @property
    def vencendo(self):
        return not self.vencido and self.dias_para_vencer <= self.AVISO_DIAS
