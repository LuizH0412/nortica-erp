import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.forms import CadastroSimplesForm, DataInput, EstiloTailwindMixin, ValorField, ativos_ou
from empresas.models import Empresa
from fiscal.consultas import cests_da_ncm
from fiscal.models import Cest, Ncm

from .models import (
    UFS, DetalheFiscal, Fabricante, Grupo, Produto, Similar, Subgrupo, UnidadeMedida, VinculoFiscal,
)


def _valor(label, casas=2, maximo=None, **kwargs):
    """Número no jeito brasileiro (aceita "1.234,56")."""
    placeholder = "0," + "0" * casas
    campo = ValorField(label=label, min_value=0, max_value=maximo, decimal_places=casas, max_digits=12, **kwargs)
    campo.widget.attrs["placeholder"] = placeholder
    return campo


class ProdutoForm(EstiloTailwindMixin, forms.ModelForm):
    quantidade_caixa = _valor("Quantidade na caixa", casas=3, required=False)
    preco_compra = _valor("Preço de compra", required=False)
    margem_lucro = _valor("Margem de lucro", required=False)
    preco_venda = _valor("Preço de venda", required=False)
    comissao = _valor("Comissão (%)", maximo=100, required=False)
    limite_desconto = _valor("Limite de desconto (%)", maximo=100, required=False)
    peso = _valor("Peso (kg)", casas=3, required=False)
    altura = _valor("Altura (cm)", required=False)
    largura = _valor("Largura (cm)", required=False)
    comprimento = _valor("Comprimento (cm)", required=False)

    # Fica junto das outras configurações, invertido ("Desativado" ligado = produto inativo)
    desativado = forms.BooleanField(
        label="Desativado", required=False, help_text="Não aparece nas pesquisas nem nas vendas.",
    )

    # Aba "Empresa": marcadas = o produto aparece; desmarcadas viram empresas_ocultas
    empresas = forms.ModelMultipleChoiceField(
        label="Empresas", queryset=Empresa.objects.none(), widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Marque pelo menos uma empresa. Se o produto não vai aparecer em nenhuma, desative-o."},
    )

    class Meta:
        model = Produto
        fields = [
            "codigo_interno", "codigo_barras", "descricao",
            "grupo", "subgrupo", "fabricante", "similar", "unidade",
            "quantidade_caixa", "codigo_barras_caixa",
            "preco_compra", "tipo_margem", "margem_lucro", "preco_venda", "comissao", "limite_desconto",
            "peso", "altura", "largura", "comprimento",
            "observacao", "informacoes_adicionais",
            "vender", "controlar_estoque", "habilitar_grade", "agrupar_pedido", "combo",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
            "informacoes_adicionais": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        p = self.instance
        for campo in ("codigo_barras", "codigo_barras_caixa"):
            self.fields[campo].widget.attrs.update({"inputmode": "numeric", "data-mascara": "numeros"})
        self.fields["grupo"].empty_label = "Selecione"
        for campo in ("subgrupo", "fabricante", "similar"):
            self.fields[campo].empty_label = "Nenhum"
        self.fields["unidade"].empty_label = "Selecione"

        # Cadastros simples: só os ativos (+ o que o produto já usa)
        self.fields["grupo"].queryset = ativos_ou(Grupo.objects.all(), p.grupo_id)
        self.fields["fabricante"].queryset = ativos_ou(Fabricante.objects.all(), p.fabricante_id)
        self.fields["similar"].queryset = ativos_ou(Similar.objects.all(), p.similar_id)
        self.fields["unidade"].queryset = ativos_ou(UnidadeMedida.objects.all(), p.unidade_id)

        # Subgrupos do grupo escolhido (o da tela ou o já gravado)
        grupo = self.data.get(self.add_prefix("grupo")) or self.initial.get("grupo") or p.grupo_id
        grupo = int(grupo) if str(grupo or "").isdigit() else None
        self.fields["subgrupo"].queryset = ativos_ou(Subgrupo.objects.filter(grupo_id=grupo), p.subgrupo_id)

        self.initial.setdefault("desativado", not p.ativo if p.pk else not self.initial.get("ativo", True))

        # Empresas: só as ativas aparecem; produto novo vem com todas marcadas
        self.fields["empresas"].queryset = Empresa.objects.filter(ativa=True).order_by("unidade")
        if "empresas" not in self.initial:
            ocultas = set(p.empresas_ocultas.values_list("pk", flat=True)) if p.pk else set()
            self.initial["empresas"] = [e.pk for e in self.fields["empresas"].queryset if e.pk not in ocultas]

        # Produto novo: unidade "UN" já escolhida
        if not p.pk and "unidade" not in self.initial:
            un = UnidadeMedida.objects.filter(nome__iexact="UN", ativo=True).first()
            if un:
                self.initial["unidade"] = un.pk

    def _unico(self, campo, valor, mensagem):
        if valor and Produto.objects.filter(**{f"{campo}__iexact": valor}).exclude(pk=self.instance.pk).exists():
            raise ValidationError(mensagem)
        return valor

    def clean_codigo_interno(self):
        valor = self.cleaned_data["codigo_interno"].strip()
        return self._unico("codigo_interno", valor, "Já existe um produto com este código interno.")

    def clean_codigo_barras(self):
        valor = "".join(self.cleaned_data["codigo_barras"].split())
        return self._unico("codigo_barras", valor, "Já existe um produto com este código de barras.")

    def clean_codigo_barras_caixa(self):
        return "".join(self.cleaned_data["codigo_barras_caixa"].split())

    def clean(self):
        dados = super().clean()
        # Campos opcionais em branco valem zero
        for campo in ("preco_compra", "margem_lucro", "preco_venda", "comissao", "quantidade_caixa", "limite_desconto",
                      "peso", "altura", "largura", "comprimento"):
            if dados.get(campo) is None and campo not in self.errors:
                dados[campo] = 0
        self.instance.ativo = not dados.get("desativado", False)
        grupo, subgrupo = dados.get("grupo"), dados.get("subgrupo")
        if subgrupo and grupo and subgrupo.grupo_id != grupo.pk:
            self.add_error("subgrupo", "Este subgrupo não é do grupo escolhido.")
        return dados

    def _save_m2m(self):
        super()._save_m2m()
        # Ocultas = ativas desmarcadas + as desativadas que já estavam ocultas (essas não aparecem na tela)
        marcadas = {e.pk for e in self.cleaned_data["empresas"]}
        ativas = set(self.fields["empresas"].queryset.values_list("pk", flat=True))
        inativas_ocultas = set(self.instance.empresas_ocultas.exclude(pk__in=ativas).values_list("pk", flat=True))
        self.instance.empresas_ocultas.set((ativas - marcadas) | inativas_ocultas)


class AjusteRapidoForm(EstiloTailwindMixin, forms.Form):
    """Ajuste rápido: entrada soma no estoque, saída subtrai."""

    OPERACOES = [("entrada", "Entrada"), ("saida", "Saída")]

    data = forms.DateField(label="Data da operação", widget=DataInput(), initial=timezone.localdate,
                           error_messages={"required": "Informe a data da operação."})
    operacao = forms.ChoiceField(label="Operação", choices=OPERACOES, initial="entrada", widget=forms.RadioSelect)
    quantidade = _valor("Quantidade", casas=3, error_messages={"required": "Informe a quantidade."})

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "rapido")
        super().__init__(*args, **kwargs)
        self.fields["quantidade"].widget.attrs["autofocus"] = True  # a janela abre já na quantidade

    def clean_quantidade(self):
        quantidade = self.cleaned_data["quantidade"]
        if quantidade <= 0:
            raise ValidationError("A quantidade precisa ser maior que zero.")
        return quantidade

    @property
    def quantidade_com_sinal(self):
        q = self.cleaned_data["quantidade"]
        return q if self.cleaned_data["operacao"] == "entrada" else -q


class EstoqueMinimoForm(EstiloTailwindMixin, forms.Form):
    estoque_minimo = _valor("Estoque mínimo", casas=3, required=False)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "minimo")
        super().__init__(*args, **kwargs)
        self.fields["estoque_minimo"].widget.attrs["autofocus"] = True


class GrupoForm(CadastroSimplesForm):
    """Janela do "+" (só nome e ativo — não mexe em vender, comissão etc.)."""

    class Meta(CadastroSimplesForm.Meta):
        model = Grupo


class GrupoCompletoForm(GrupoForm):
    """Tela de cadastro de grupo (Cadastros › Produtos › Grupos)."""

    comissao = _valor("Comissão (%)", maximo=100, required=False)

    class Meta(GrupoForm.Meta):
        fields = ["nome", "comissao", "vender", "ativo", "hortifruti", "restricao_idade"]

    def clean_comissao(self):
        return self.cleaned_data.get("comissao") or 0


class SubgrupoForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Subgrupo


class FabricanteForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Fabricante


class SimilarForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Similar


class UnidadeMedidaForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = UnidadeMedida


# ---------- Fiscal ----------

class VinculoFiscalForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = VinculoFiscal


# Campos da janela "Produto específico" (se der erro neles, a janela já abre)
CAMPOS_ESPECIFICO = [
    "especifico", "anp_codigo", "anp_descricao", "glp_percentual", "gas_natural_importado", "valor_partida",
    "gas_natural_nacional", "codif", "quantidade_combustivel", "uf_consumo", "cide_base", "cide_aliquota", "cide_valor",
    "unidade_tributavel_diferente", "unidade_tributavel", "fator_conversao",
    "adrem_icms", "adrem_retencao", "adrem_anterior", "reducao_adrem", "motivo_reducao_adrem", "biodiesel_percentual",
]
CAMPOS_COMBUSTIVEL = [c for c in CAMPOS_ESPECIFICO if c not in (
    "especifico", "unidade_tributavel_diferente", "unidade_tributavel", "fator_conversao",
)]


class DetalheFiscalForm(EstiloTailwindMixin, forms.ModelForm):
    """Detalhes fiscais do produto numa empresa (aba "Detalhes fiscais")."""

    ncm = forms.CharField(label="NCM", required=False, widget=forms.Select)
    cest = forms.CharField(label="CEST", required=False, max_length=9, widget=forms.Select)  # aceita "03.002.00"

    class Meta:
        model = DetalheFiscal
        fields = ["vinculo", "origem", "ncm", "cest", "codigo_beneficio", "fcp"] + CAMPOS_ESPECIFICO

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "fiscal")
        super().__init__(*args, **kwargs)
        d = self.instance

        self.fields["vinculo"].queryset = ativos_ou(VinculoFiscal.objects.all(), d.vinculo_id)
        self.fields["vinculo"].empty_label = "Nenhum"
        self.fields["unidade_tributavel"].queryset = ativos_ou(UnidadeMedida.objects.all(), d.unidade_tributavel_id)
        self.fields["unidade_tributavel"].empty_label = "Selecione"
        self.fields["motivo_reducao_adrem"].choices = [("", "Selecione")] + list(DetalheFiscal.MotivoReducaoAdRem.choices)
        self.fields["uf_consumo"].choices = [("", "Selecione")] + UFS

        # NCM: campo de busca (a lista vem do banco enquanto a pessoa digita); aqui só o escolhido
        atual = self.data.get(self.add_prefix("ncm")) if self.is_bound else d.ncm
        atual = re.sub(r"\D", "", atual or "")
        opcoes = [("", "Nenhum")]
        if atual:
            ncm = Ncm.objects.filter(pk=atual).first()
            opcoes.append((atual, str(ncm) if ncm else atual))
        self.fields["ncm"].widget.choices = opcoes

        # CEST: só os da NCM escolhida (a lista vem do banco); aqui só o escolhido
        atual = self.data.get(self.add_prefix("cest")) if self.is_bound else d.cest
        atual = re.sub(r"\D", "", atual or "")
        opcoes = [("", "Nenhum")]
        if atual:
            cest = Cest.objects.filter(pk=atual).first()
            opcoes.append((atual, str(cest) if cest else atual))
        self.fields["cest"].widget.choices = opcoes

        # Números no jeito brasileiro ("1.234,56"); em branco vale zero
        for nome, campo in list(self.fields.items()):
            modelo = DetalheFiscal._meta.get_field(nome)
            if isinstance(modelo, models.DecimalField):
                maximo = 100 if any(getattr(v, "limit_value", None) == 100 for v in modelo.validators) else None
                novo = _valor(modelo.verbose_name, casas=modelo.decimal_places, maximo=maximo, required=False)
                novo.help_text = modelo.help_text
                novo.widget.attrs["class"] = campo.widget.attrs.get("class", "")
                self.fields[nome] = novo

        self.fields["anp_codigo"].widget.attrs.update({"inputmode": "numeric", "data-mascara": "numeros"})
        self.fields["anp_codigo"].widget.attrs["placeholder"] = "9 números"

    def clean_ncm(self):
        ncm = re.sub(r"\D", "", self.cleaned_data.get("ncm") or "")
        if not ncm:
            return ""
        if len(ncm) != 8:
            raise ValidationError("A NCM tem 8 números.")
        if Ncm.objects.exists() and not Ncm.objects.filter(pk=ncm).exists():
            raise ValidationError("NCM não encontrada na tabela vigente.")
        return ncm

    def clean_cest(self):
        cest = re.sub(r"\D", "", self.cleaned_data.get("cest") or "")
        if cest and len(cest) != 7:
            raise ValidationError("O CEST tem 7 números.")
        return cest

    def clean(self):
        dados = super().clean()
        for nome, campo in self.fields.items():
            if isinstance(campo, ValorField) and dados.get(nome) is None and nome not in self.errors:
                dados[nome] = 0

        # CEST tem que ser um dos da NCM (Convênio ICMS 142/2018)
        cest, ncm = dados.get("cest"), dados.get("ncm")
        if cest and "ncm" not in self.errors:
            if not ncm:
                self.add_error("cest", "Escolha a NCM antes do CEST.")
            elif Cest.objects.exists() and not cests_da_ncm(ncm).filter(pk=cest).exists():
                self.add_error("cest", "Este CEST não é da NCM escolhida.")

        if dados.get("especifico") == DetalheFiscal.Especifico.COMBUSTIVEL:
            codigo = re.sub(r"\D", "", dados.get("anp_codigo") or "")
            dados["anp_codigo"] = codigo
            if len(codigo) != 9:
                self.add_error("anp_codigo", "Informe o código ANP (9 números).")
            if not (dados.get("anp_descricao") or "").strip():
                self.add_error("anp_descricao", "Informe a descrição do produto ANP.")
            if not dados.get("uf_consumo"):
                self.add_error("uf_consumo", "Informe a UF de consumo.")
        else:
            # Sem tipo específico, os dados de combustível não valem: limpa para não ficar lixo guardado
            for nome in CAMPOS_COMBUSTIVEL:
                vazio = DetalheFiscal._meta.get_field(nome).get_default()
                dados[nome] = vazio
                setattr(self.instance, nome, vazio)

        if dados.get("unidade_tributavel_diferente"):
            if not dados.get("unidade_tributavel"):
                self.add_error("unidade_tributavel", "Escolha a unidade tributável.")
            if not dados.get("fator_conversao"):
                self.add_error("fator_conversao", "Informe o fator de conversão (maior que zero).")
        else:
            dados["unidade_tributavel"] = None
            dados["fator_conversao"] = 0
        return dados

    def save(self, commit=True):
        self.instance.calcular_olho_no_imposto()  # "De olho no imposto" vem da tabela do IBPT
        return super().save(commit)

    @property
    def vinculo_automatico(self):
        """Sem vínculo escolhido, qual vale: o da NCM ou o padrão ("" se nenhum)."""
        from .models import VinculoNcm
        ncm = self.instance.ncm
        pela_ncm = VinculoNcm.objects.filter(ncm=ncm, vinculo__ativo=True).select_related("vinculo").first() if ncm else None
        if pela_ncm:
            return f"{pela_ncm.vinculo} (pela NCM)"
        padrao = VinculoFiscal.objects.filter(padrao=True, ativo=True).first()
        return f"{padrao} (vínculo padrão)" if padrao else ""

    @property
    def total_cests(self):
        ncm = self.cleaned_data.get("ncm") if hasattr(self, "cleaned_data") else self.instance.ncm
        return cests_da_ncm(ncm or self.instance.ncm).count()

    @property
    def erro_no_especifico(self):
        return any(nome in self.errors for nome in CAMPOS_ESPECIFICO)
