from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from core.models import CadastroSimples
from fiscal.tabelas import (
    DOCUMENTOS, GRUPOS_NATUREZA_RECEITA, MODALIDADES_BC, MODALIDADES_BC_ST, OPERACOES, REGIMES, REGIMES_SIMPLES,
    TIPOS_ITEM, TODAS_UFS,
)
from fiscal.tabelas import UFS as UFS_FISCAIS

from .validators import validar_gtin

POSITIVO = [MinValueValidator(Decimal("0"))]
PERCENTUAL = [MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))]


class Grupo(CadastroSimples):
    comissao = models.DecimalField(
        "Comissão (%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=PERCENTUAL,
        help_text="Comissão padrão dos produtos deste grupo.",
    )
    vender = models.BooleanField("Vender", default=True, help_text="Produtos deste grupo aparecem nas vendas.")
    hortifruti = models.BooleanField(
        "Hortifruti", default=False, help_text="Frutas, verduras e legumes (normalmente vendidos por peso).",
    )
    restricao_idade = models.BooleanField(
        "Restrição de idade", default=False, help_text="Venda só para maiores de 18 anos (ex.: bebidas alcoólicas).",
    )

    class Meta(CadastroSimples.Meta):
        verbose_name = "grupo de produtos"
        verbose_name_plural = "grupos de produtos"


class Subgrupo(CadastroSimples):
    """Subgrupo dentro de um grupo (ex.: Bebidas › Refrigerantes). O nome repete entre grupos."""

    pai_campo = "grupo"

    nome = models.CharField("Nome", max_length=60)
    grupo = models.ForeignKey(Grupo, verbose_name="Grupo", on_delete=models.CASCADE, related_name="subgrupos")

    class Meta(CadastroSimples.Meta):
        verbose_name = "subgrupo"
        verbose_name_plural = "subgrupos"
        constraints = [models.UniqueConstraint(fields=["grupo", "nome"], name="subgrupo_unico_no_grupo")]


class Fabricante(CadastroSimples):
    class Meta(CadastroSimples.Meta):
        verbose_name = "fabricante"
        verbose_name_plural = "fabricantes"


class Similar(CadastroSimples):
    """Família de produtos que substituem um ao outro (ex.: "Refrigerante cola 2L" de várias marcas)."""

    class Meta(CadastroSimples.Meta):
        verbose_name = "similar"
        verbose_name_plural = "similares"


class UnidadeMedida(CadastroSimples):
    artigo = "a"

    class Meta(CadastroSimples.Meta):
        verbose_name = "unidade de medida"
        verbose_name_plural = "unidades de medida"


class Produto(models.Model):
    """Produto do catálogo único (compartilhado entre as empresas da instância)."""

    class TipoMargem(models.TextChoices):
        PERCENTUAL = "percentual", "Percentual"
        VALOR = "valor", "Valor (R$)"

    # Identificação
    codigo_interno = models.CharField(
        "Código interno", max_length=30, blank=True,
        help_text="Código que a empresa usa para identificar o produto.",
    )
    codigo_barras = models.CharField("Código de barras", max_length=14, blank=True, validators=[validar_gtin])
    descricao = models.CharField("Descrição", max_length=120)

    # Classificação
    grupo = models.ForeignKey(Grupo, verbose_name="Grupo", on_delete=models.PROTECT, related_name="produtos")
    subgrupo = models.ForeignKey(
        Subgrupo, verbose_name="Subgrupo", null=True, blank=True, on_delete=models.PROTECT, related_name="produtos",
    )
    fabricante = models.ForeignKey(
        Fabricante, verbose_name="Fabricante", null=True, blank=True, on_delete=models.PROTECT, related_name="produtos",
    )
    similar = models.ForeignKey(
        Similar, verbose_name="Similar", null=True, blank=True, on_delete=models.PROTECT, related_name="produtos",
        help_text="Produtos do mesmo similar podem substituir um ao outro.",
    )
    unidade = models.ForeignKey(
        UnidadeMedida, verbose_name="Unidade de medida", on_delete=models.PROTECT, related_name="produtos",
    )

    # Caixa
    quantidade_caixa = models.DecimalField(
        "Quantidade na caixa", max_digits=12, decimal_places=3, default=Decimal("0"), validators=POSITIVO,
    )
    codigo_barras_caixa = models.CharField(
        "Código de barras da caixa", max_length=14, blank=True, validators=[validar_gtin],
    )

    # Preços
    preco_compra = models.DecimalField(
        "Preço de compra", max_digits=12, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
    )
    tipo_margem = models.CharField(
        "Tipo de margem", max_length=10, choices=TipoMargem.choices, default=TipoMargem.PERCENTUAL,
    )
    margem_lucro = models.DecimalField(
        "Margem de lucro", max_digits=12, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
    )
    preco_venda = models.DecimalField(
        "Preço de venda", max_digits=12, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
    )
    comissao = models.DecimalField(
        "Comissão (%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=PERCENTUAL,
    )
    limite_desconto = models.DecimalField(
        "Limite de desconto (%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=PERCENTUAL,
    )

    # Medidas (frete e nota fiscal)
    peso = models.DecimalField("Peso (kg)", max_digits=10, decimal_places=3, default=Decimal("0"), validators=POSITIVO)
    altura = models.DecimalField("Altura (cm)", max_digits=10, decimal_places=2, default=Decimal("0"), validators=POSITIVO)
    largura = models.DecimalField("Largura (cm)", max_digits=10, decimal_places=2, default=Decimal("0"), validators=POSITIVO)
    comprimento = models.DecimalField(
        "Comprimento (cm)", max_digits=10, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
    )

    observacao = models.TextField("Observação", blank=True)
    informacoes_adicionais = models.TextField(
        "Informações adicionais", blank=True, help_text="Sai na nota fiscal junto com o produto.",
    )

    # Configurações do produto
    vender = models.BooleanField("Vender", default=True, help_text="Aparece nas vendas.")
    controlar_estoque = models.BooleanField("Controlar estoque", default=True)
    habilitar_grade = models.BooleanField("Habilitar grade", default=False, help_text="Variações de tamanho e cor.")
    agrupar_pedido = models.BooleanField(
        "Agrupar pedido", default=True, help_text="Soma a quantidade quando o produto é lançado de novo no pedido.",
    )
    combo = models.BooleanField("Combo", default=False, help_text="Produto formado por outros produtos.")
    ativo = models.BooleanField("Ativo", default=True)

    # Aba "Empresa": o produto aparece em todas as empresas, menos nestas.
    # Guardar as ocultas (e não as liberadas) faz uma empresa nova já nascer com o catálogo inteiro.
    empresas_ocultas = models.ManyToManyField(
        "empresas.Empresa", verbose_name="Oculto nas empresas", blank=True, related_name="produtos_ocultos",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["descricao"]
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        constraints = [
            models.UniqueConstraint(
                fields=["codigo_interno"], condition=~models.Q(codigo_interno=""), name="produto_codigo_interno_unico",
                violation_error_message="Já existe um produto com este código interno.",
            ),
            models.UniqueConstraint(
                fields=["codigo_barras"], condition=~models.Q(codigo_barras=""), name="produto_codigo_barras_unico",
                violation_error_message="Já existe um produto com este código de barras.",
            ),
        ]

    def __str__(self):
        return self.descricao

    def vinculos_que_impedem_exclusao(self):
        """
        Tudo o que já está ligado a este produto (movimentações de estoque e, no futuro,
        vendas, notas fiscais, compras…). Vazio = pode excluir.
        Qualquer modelo novo que aponte para Produto entra aqui sozinho.
        """
        # Saldo/estoque mínimo e detalhes fiscais são do próprio cadastro: somem junto com ele
        ignorar = {"estoques", "detalhes_fiscais", "fotos"}
        encontrados = []
        for rel in self._meta.related_objects:
            nome = rel.get_accessor_name()
            if nome in ignorar:
                continue
            if rel.many_to_many:
                existe = getattr(self, nome).exists()
            else:
                existe = rel.related_model._base_manager.filter(**{rel.field.name: self}).exists()
            if existe:
                encontrados.append(str(rel.related_model._meta.verbose_name_plural))
        return encontrados

    def disponivel_na(self, empresa):
        """O produto aparece nesta empresa? (aba "Empresa" do cadastro)"""
        return empresa is None or not self.empresas_ocultas.filter(pk=empresa.pk).exists()

    @property
    def codigo(self):
        """Código do sistema (ex.: 165)."""
        return str(self.pk) if self.pk else ""

    @property
    def preco_sugerido(self):
        """Preço de compra + margem (percentual sobre o custo ou valor fixo)."""
        if self.tipo_margem == self.TipoMargem.VALOR:
            return (self.preco_compra + self.margem_lucro).quantize(Decimal("0.01"))
        return (self.preco_compra * (1 + self.margem_lucro / 100)).quantize(Decimal("0.01"))


# ---------- Estoque (saldo por empresa) ----------

class EstoqueProduto(models.Model):
    """Saldo do produto em cada empresa (o catálogo é único, o estoque é de cada empresa)."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="estoques")
    empresa = models.ForeignKey("empresas.Empresa", on_delete=models.CASCADE, related_name="estoques_produtos")
    quantidade = models.DecimalField("Quantidade", max_digits=14, decimal_places=3, default=Decimal("0"))
    estoque_minimo = models.DecimalField(
        "Estoque mínimo", max_digits=14, decimal_places=3, default=Decimal("0"), validators=POSITIVO,
        help_text="Abaixo disso o produto aparece em destaque na lista.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "estoque do produto"
        verbose_name_plural = "estoques dos produtos"
        constraints = [models.UniqueConstraint(fields=["produto", "empresa"], name="um_saldo_por_empresa")]

    def __str__(self):
        return f"{self.produto} em {self.empresa.unidade}: {self.quantidade}"


class MovimentoEstoque(models.Model):
    """Histórico de tudo que mexe no saldo (hoje: ajustes; depois: compras, vendas, transferências)."""

    class Tipo(models.TextChoices):
        AJUSTE = "ajuste", "Ajuste de estoque"
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saída"

    # PROTECT: produto ou empresa com movimentação de estoque não pode ser excluído (só desativado)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="movimentos_estoque")
    empresa = models.ForeignKey("empresas.Empresa", on_delete=models.PROTECT, related_name="movimentos_estoque")
    tipo = models.CharField("Tipo", max_length=10, choices=Tipo.choices)
    quantidade = models.DecimalField("Quantidade", max_digits=14, decimal_places=3, help_text="Positiva entra, negativa sai.")
    saldo_anterior = models.DecimalField("Saldo anterior", max_digits=14, decimal_places=3)
    saldo_novo = models.DecimalField("Saldo novo", max_digits=14, decimal_places=3)
    motivo = models.CharField("Motivo", max_length=150, blank=True)
    data_operacao = models.DateField("Data da operação", default=timezone.localdate)
    usuario = models.ForeignKey(
        "contas.Usuario", verbose_name="Feito por", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    criado_em = models.DateTimeField("Data", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "movimento de estoque"
        verbose_name_plural = "movimentos de estoque"


# ---------- Fiscal ----------

class VinculoFiscal(CadastroSimples):
    """
    Vínculo fiscal (Cadastros › Produtos › Vínculos fiscais): a tributação usada por vários produtos.

    Tem uma ou mais configurações (documento + UF de origem + UF de destino + regime), cada uma com a
    tributação de entrada e a de saída (CFOP, ICMS, PIS/COFINS, IPI, IBS/CBS).
    Produtos entram no vínculo pela aba "Detalhes fiscais" (ou pela tela do vínculo); NCMs vinculadas
    fazem o vínculo valer para os produtos daquela NCM que não têm vínculo escolhido.
    """

    nome = models.CharField("Descrição", max_length=100, unique=True)
    tipo_item = models.CharField("Tipo do item", max_length=2, choices=TIPOS_ITEM, default="00",
                                 help_text="SPED Fiscal (registro 0200).")
    padrao = models.BooleanField(
        "Vínculo padrão", default=False,
        help_text="Usado pelos produtos sem vínculo escolhido e sem vínculo pela NCM. Só um vínculo pode ser o padrão.",
    )

    class Meta(CadastroSimples.Meta):
        verbose_name = "vínculo fiscal"
        verbose_name_plural = "vínculos fiscais"


UFS = [(u, u) for u in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()]


class DetalheFiscal(models.Model):
    """Aba "Detalhes fiscais": os dados fiscais do produto em cada empresa."""

    class Origem(models.TextChoices):
        # Origem da mercadoria (NF-e, campo orig)
        NACIONAL = "0", "0 - Nacional"
        ESTRANGEIRA_DIRETA = "1", "1 - Estrangeira – Importação direta"
        ESTRANGEIRA_INTERNO = "2", "2 - Estrangeira – Adquirida no mercado interno"
        NACIONAL_40 = "3", "3 - Nacional, com Conteúdo de Importação superior a 40% e inferior ou igual a 70%"
        NACIONAL_PPB = "4", "4 - Nacional, produzida conforme os processos produtivos básicos (PPB)"
        NACIONAL_ATE_40 = "5", "5 - Nacional, com Conteúdo de Importação inferior ou igual a 40%"
        ESTRANGEIRA_DIRETA_CAMEX = "6", "6 - Estrangeira – Importação direta, sem similar nacional (lista CAMEX)"
        ESTRANGEIRA_INTERNO_CAMEX = "7", "7 - Estrangeira – Adquirida no mercado interno, sem similar nacional (lista CAMEX)"
        NACIONAL_70 = "8", "8 - Nacional, com Conteúdo de Importação superior a 70%"

    class Especifico(models.TextChoices):
        NENHUM = "", "Nenhum"
        COMBUSTIVEL = "combustivel", "Combustível"

    class MotivoReducaoAdRem(models.TextChoices):
        TRANSPORTE_COLETIVO = "1", "1 - Transporte coletivo de passageiros"
        OUTROS = "9", "9 - Outros"

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="detalhes_fiscais")
    empresa = models.ForeignKey("empresas.Empresa", on_delete=models.CASCADE, related_name="detalhes_fiscais_produtos")
    vinculo = models.ForeignKey(
        VinculoFiscal, verbose_name="Vínculo fiscal", null=True, blank=True, on_delete=models.PROTECT, related_name="detalhes",
    )

    # Informações fiscais gerais
    origem = models.CharField("Origem", max_length=1, choices=Origem.choices, default=Origem.NACIONAL)
    ncm = models.CharField("NCM", max_length=8, blank=True)
    cest = models.CharField("CEST", max_length=7, blank=True)
    codigo_beneficio = models.CharField(
        "Código benefício", max_length=10, blank=True, help_text="Código de benefício fiscal da UF (cBenef).",
    )
    fcp = models.DecimalField(
        "Fundo de Combate à Pobreza (%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=PERCENTUAL,
    )
    # "De olho no imposto" (Lei 12.741/2012): calculado pela tabela do IBPT a partir da NCM, da origem e
    # da UF da empresa. Não é digitado.
    olho_no_imposto = models.DecimalField(
        "De olho no imposto (%)", max_digits=7, decimal_places=2, default=Decimal("0"), editable=False,
        help_text="Carga tributária aproximada que sai no cupom (Lei 12.741/2012).",
    )
    olho_federal = models.DecimalField("Federal (%)", max_digits=7, decimal_places=2, default=Decimal("0"), editable=False)
    olho_estadual = models.DecimalField("Estadual (%)", max_digits=7, decimal_places=2, default=Decimal("0"), editable=False)
    olho_municipal = models.DecimalField("Municipal (%)", max_digits=7, decimal_places=2, default=Decimal("0"), editable=False)
    olho_fonte = models.CharField("Fonte da carga tributária", max_length=60, blank=True, editable=False)

    def calcular_olho_no_imposto(self):
        """Preenche o "De olho no imposto" pela tabela do IBPT (zera se não der para calcular)."""
        from fiscal.consultas import carga_tributaria

        municipio = getattr(self.empresa, "municipio", None)
        carga = carga_tributaria(self.ncm, municipio.uf if municipio else "", self.origem)
        if carga is None:
            self.olho_no_imposto = self.olho_federal = self.olho_estadual = self.olho_municipal = Decimal("0")
            self.olho_fonte = ""
            return None
        self.olho_federal, self.olho_estadual, self.olho_municipal = carga["federal"], carga["estadual"], carga["municipal"]
        self.olho_no_imposto = carga["total"]
        self.olho_fonte = carga["fonte"][:60]
        return carga

    # Produto específico (NF-e)
    especifico = models.CharField("Tipo", max_length=15, choices=Especifico.choices, blank=True, default="")
    anp_codigo = models.CharField("Código produto ANP", max_length=9, blank=True)
    anp_descricao = models.CharField("Descrição do produto ANP", max_length=95, blank=True)
    glp_percentual = models.DecimalField("GLP (%)", max_digits=7, decimal_places=4, default=Decimal("0"), validators=PERCENTUAL)
    gas_natural_nacional = models.DecimalField(
        "Gás natural nacional (%)", max_digits=7, decimal_places=4, default=Decimal("0"), validators=PERCENTUAL,
    )
    gas_natural_importado = models.DecimalField(
        "Gás natural importado (%)", max_digits=7, decimal_places=4, default=Decimal("0"), validators=PERCENTUAL,
    )
    valor_partida = models.DecimalField("Valor de partida", max_digits=13, decimal_places=2, default=Decimal("0"), validators=POSITIVO)
    codif = models.CharField("Código de autorização (CODIF)", max_length=21, blank=True)
    quantidade_combustivel = models.DecimalField(
        "Qtd. combustível", max_digits=16, decimal_places=4, default=Decimal("0"), validators=POSITIVO,
        help_text="Quantidade faturada à temperatura ambiente (qTemp).",
    )
    uf_consumo = models.CharField("UF de consumo", max_length=2, choices=UFS, blank=True)
    cide_base = models.DecimalField("BC da CIDE", max_digits=16, decimal_places=4, default=Decimal("0"), validators=POSITIVO)
    cide_aliquota = models.DecimalField("Alíquota CIDE", max_digits=15, decimal_places=4, default=Decimal("0"), validators=POSITIVO)
    cide_valor = models.DecimalField("Valor CIDE", max_digits=13, decimal_places=2, default=Decimal("0"), validators=POSITIVO)

    # Unidade tributável
    unidade_tributavel_diferente = models.BooleanField("Unidade tributável diferente da comercial", default=False)
    unidade_tributavel = models.ForeignKey(
        UnidadeMedida, verbose_name="Unidade tributável", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    fator_conversao = models.DecimalField(
        "Fator de conversão", max_digits=15, decimal_places=4, default=Decimal("0"), validators=POSITIVO,
        help_text="Quantas unidades tributáveis há em 1 unidade comercial.",
    )

    # Tributação monofásica (combustíveis)
    adrem_icms = models.DecimalField(
        "Alíquota ad rem ICMS (R$)", max_digits=13, decimal_places=4, default=Decimal("0"), validators=POSITIVO,
    )
    adrem_retencao = models.DecimalField(
        "Alíquota ad rem com retenção (R$)", max_digits=13, decimal_places=4, default=Decimal("0"), validators=POSITIVO,
    )
    adrem_anterior = models.DecimalField(
        "Alíquota ad rem retida anteriormente (R$)", max_digits=13, decimal_places=4, default=Decimal("0"), validators=POSITIVO,
    )
    reducao_adrem = models.DecimalField(
        "Percentual de redução da alíquota ad rem", max_digits=5, decimal_places=2, default=Decimal("0"),
        validators=PERCENTUAL,
    )
    motivo_reducao_adrem = models.CharField(
        "Motivo da redução do ad rem", max_length=1, choices=MotivoReducaoAdRem.choices, blank=True,
    )
    biodiesel_percentual = models.DecimalField(
        "Percentual biodiesel", max_digits=7, decimal_places=4, default=Decimal("0"), validators=PERCENTUAL,
        help_text="Percentual do biodiesel na mistura com o diesel (pBio).",
    )

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "detalhe fiscal do produto"
        verbose_name_plural = "detalhes fiscais dos produtos"
        constraints = [models.UniqueConstraint(fields=["produto", "empresa"], name="um_detalhe_fiscal_por_empresa")]

    def __str__(self):
        return f"{self.produto} em {self.empresa.unidade}"

    @classmethod
    def campos_copiaveis(cls):
        """O que o "Clonar produto" copia (tudo menos a ligação produto/empresa)."""
        fora = {"id", "produto", "empresa", "atualizado_em"}
        return [f.attname for f in cls._meta.concrete_fields if f.name not in fora]


# ---------- Fotos ----------

def caminho_foto(foto, nome_original):
    """media/<instância>/produtos/<produto>/<aleatório>.<ext>: cada instância na sua pasta, sem nome previsível."""
    from django.db import connection

    extensao = Path(nome_original).suffix.lower() or ".jpg"
    return f"{connection.schema_name}/produtos/{foto.produto_id}/{uuid4().hex}{extensao}"


class FotoProduto(models.Model):
    """Aba "Fotos": fotos do produto (uma é a principal, que aparece primeiro)."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="fotos")
    arquivo = models.FileField("Foto", upload_to=caminho_foto, max_length=200)
    descricao = models.CharField("Descrição", max_length=200, blank=True)
    principal = models.BooleanField("Foto principal", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-principal", "pk"]
        verbose_name = "foto do produto"
        verbose_name_plural = "fotos dos produtos"
        constraints = [
            models.UniqueConstraint(fields=["produto"], condition=models.Q(principal=True), name="uma_foto_principal"),
        ]

    def __str__(self):
        return self.descricao or f"Foto {self.pk} de {self.produto}"

    def tornar_principal(self):
        FotoProduto.objects.filter(produto_id=self.produto_id, principal=True).exclude(pk=self.pk).update(principal=False)
        if not self.principal:
            self.principal = True
            self.save(update_fields=["principal"])


@receiver(post_delete, sender=FotoProduto)
def _apagar_arquivo_da_foto(sender, instance, **kwargs):
    """Foto excluída (ou produto excluído): o arquivo sai do disco também."""
    if instance.arquivo:
        instance.arquivo.delete(save=False)


# ---------- Vínculo fiscal: configurações e tributação ----------

class ConfiguracaoFiscal(models.Model):
    """Uma situação do vínculo: documento (NF-e/NFC-e), UF de origem, UF de destino e regime tributário."""

    vinculo = models.ForeignKey(VinculoFiscal, on_delete=models.CASCADE, related_name="configuracoes")
    documento = models.CharField("Documento", max_length=4, choices=DOCUMENTOS)
    uf_origem = models.CharField("UF de origem", max_length=2, choices=[(u, u) for u in UFS_FISCAIS])
    uf_destino = models.CharField("UF de destino", max_length=2,
                                  choices=[(TODAS_UFS, "Todas")] + [(u, u) for u in UFS_FISCAIS])
    regime = models.CharField("Regime tributário", max_length=1, choices=REGIMES)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["documento", "uf_origem", "uf_destino", "regime", "pk"]
        verbose_name = "configuração fiscal"
        verbose_name_plural = "configurações fiscais"
        constraints = [models.UniqueConstraint(
            fields=["vinculo", "documento", "uf_origem", "uf_destino", "regime"], name="configuracao_fiscal_unica",
            violation_error_message="Este vínculo já tem uma configuração com o mesmo documento, UFs e regime.",
        )]

    def __str__(self):
        return f"{self.get_documento_display()} · {self.uf_origem} → {self.get_uf_destino_display()} · {self.get_regime_display()}"

    @property
    def usa_csosn(self):
        return self.regime in REGIMES_SIMPLES

    @property
    def operacoes(self):
        """NFC-e é só venda (saída); NF-e tem entrada e saída."""
        return ["saida"] if self.documento == "nfce" else ["entrada", "saida"]

    def tributacao(self, operacao):
        return self.tributacoes.filter(operacao=operacao).first()


class TributacaoFiscal(models.Model):
    """A tributação de uma configuração do vínculo, na entrada (compra) ou na saída (venda)."""

    configuracao = models.ForeignKey(ConfiguracaoFiscal, on_delete=models.CASCADE, related_name="tributacoes")
    operacao = models.CharField("Operação", max_length=7, choices=OPERACOES)

    cfop = models.CharField("CFOP", max_length=4, blank=True)
    icms_cst = models.CharField("CST/CSOSN", max_length=3, blank=True)
    icms_aliquota = models.DecimalField("Alíquota de ICMS (%)", max_digits=5, decimal_places=2, default=Decimal("0"),
                                        validators=PERCENTUAL)
    icms_zerar_base = models.BooleanField(
        "Zerar base e alíquota de ICMS", default=False,
        help_text="A nota sai com base de cálculo e alíquota do ICMS zeradas.",
    )
    icms_acrescimo = models.DecimalField(
        "Acréscimo na base (%)", max_digits=7, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
        help_text="Percentual somado à base de cálculo do ICMS.",
    )
    icms_modalidade_base = models.CharField("Modalidade da base", max_length=1, choices=MODALIDADES_BC, default="3")
    icms_reducao_base = models.DecimalField(
        "Redução da base (%)", max_digits=7, decimal_places=4, default=Decimal("0"), validators=PERCENTUAL,
    )
    icms_diferimento = models.DecimalField(
        "Diferimento (%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=PERCENTUAL,
    )
    # ICMS substituição tributária (NF-e de saída)
    icms_st_modalidade = models.CharField("Modalidade da base ST", max_length=1, choices=MODALIDADES_BC_ST, default="4")
    icms_st_mva = models.DecimalField(
        "MVA (%)", max_digits=7, decimal_places=2, default=Decimal("0"), validators=POSITIVO,
        help_text="Margem de valor agregado: percentual somado ao valor da operação para chegar à base da ST.",
    )
    icms_st_aliquota = models.DecimalField("Alíquota ST (%)", max_digits=5, decimal_places=2, default=Decimal("0"),
                                           validators=PERCENTUAL)
    icms_st_reducao_base = models.DecimalField("Redução da base ST (%)", max_digits=7, decimal_places=4,
                                               default=Decimal("0"), validators=PERCENTUAL)
    icms_st_valor_pauta = models.DecimalField("Valor de pauta (R$)", max_digits=13, decimal_places=4,
                                              default=Decimal("0"), validators=POSITIVO)
    icms_st_somar_ipi = models.BooleanField("Somar IPI à base de cálculo", default=False,
                                            help_text="O valor do IPI entra na base da substituição tributária.")
    pis_cst = models.CharField("CST do PIS", max_length=2, blank=True)
    pis_aliquota = models.DecimalField("Alíquota do PIS (%)", max_digits=7, decimal_places=4, default=Decimal("0"),
                                       validators=PERCENTUAL)
    cofins_cst = models.CharField("CST da COFINS", max_length=2, blank=True)
    cofins_aliquota = models.DecimalField("Alíquota da COFINS (%)", max_digits=7, decimal_places=4, default=Decimal("0"),
                                          validators=PERCENTUAL)
    pis_cofins_grupo = models.CharField(
        "Grupo", max_length=6, choices=GRUPOS_NATUREZA_RECEITA, blank=True,
        help_text="Tabela da natureza da receita na EFD-Contribuições (para CST 02 a 09).",
    )
    pis_cofins_natureza = models.CharField(
        "Natureza da receita", max_length=3, blank=True,
        help_text="Código de 3 dígitos da tabela do grupo (EFD-Contribuições).",
    )
    ipi_cst = models.CharField("Situação do IPI", max_length=2, blank=True)
    ipi_aliquota = models.DecimalField("Alíquota do IPI (%)", max_digits=5, decimal_places=2, default=Decimal("0"),
                                       validators=PERCENTUAL)
    ipi_enquadramento = models.CharField(
        "Enquadramento", max_length=3, default="999",
        help_text="Código de enquadramento legal do IPI (cEnq). 999 = tributação normal.",
    )
    exige_gta = models.BooleanField("Exige Guia de Trânsito Animal (GTA)", default=False)
    ibscbs_cst = models.CharField("CST do IBS/CBS", max_length=3, blank=True)
    cclasstrib = models.CharField("Classificação tributária (cClassTrib)", max_length=6, blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "tributação"
        verbose_name_plural = "tributações"
        constraints = [models.UniqueConstraint(fields=["configuracao", "operacao"], name="uma_tributacao_por_operacao")]

    def __str__(self):
        return f"{self.configuracao} · {self.get_operacao_display()}"

    @property
    def preenchida(self):
        return bool(self.cfop and self.icms_cst)

    @classmethod
    def campos_copiaveis(cls):
        fora = {"id", "configuracao", "operacao", "atualizado_em"}
        return [f.attname for f in cls._meta.concrete_fields if f.name not in fora]


class VinculoNcm(models.Model):
    """NCM vinculada: produtos desta NCM sem vínculo escolhido usam este vínculo."""

    vinculo = models.ForeignKey(VinculoFiscal, on_delete=models.CASCADE, related_name="ncms")
    ncm = models.CharField("NCM", max_length=8)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ncm"]
        verbose_name = "NCM do vínculo"
        verbose_name_plural = "NCMs dos vínculos"
        constraints = [models.UniqueConstraint(
            fields=["ncm"], name="ncm_em_um_vinculo_so",
            violation_error_message="Esta NCM já está vinculada a outro vínculo fiscal.",
        )]

    def __str__(self):
        return f"{self.ncm} → {self.vinculo}"


def vinculo_do_produto(produto, empresa):
    """
    Qual vínculo fiscal vale para o produto na empresa (e por quê):
    o escolhido nos detalhes fiscais → o da NCM do produto → o vínculo padrão.
    Devolve (vinculo, origem) com origem "produto", "ncm" ou "padrao"; ou (None, None).
    """
    detalhe = DetalheFiscal.objects.filter(produto=produto, empresa=empresa).select_related("vinculo").first()
    if detalhe and detalhe.vinculo_id:
        return detalhe.vinculo, "produto"
    if detalhe and detalhe.ncm:
        pela_ncm = VinculoNcm.objects.filter(ncm=detalhe.ncm, vinculo__ativo=True).select_related("vinculo").first()
        if pela_ncm:
            return pela_ncm.vinculo, "ncm"
    padrao = VinculoFiscal.objects.filter(padrao=True, ativo=True).first()
    return (padrao, "padrao") if padrao else (None, None)
