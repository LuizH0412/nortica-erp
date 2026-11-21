"""Formulários do cadastro de vínculos fiscais (Cadastros › Produtos › Vínculos fiscais)."""
import re

from django import forms
from django.core.exceptions import ValidationError

from core.forms import EstiloTailwindMixin, ValorField
from fiscal.models import Cfop, ClassTrib, CstIbsCbs
from fiscal.tabelas import (
    GRUPOS_NATUREZA_RECEITA, TODAS_UFS, cst_icms_do_regime, cst_ipi_da_operacao, cst_pis_cofins_da_operacao,
    primeiros_digitos_cfop,
)

from .forms import _valor
from .models import ConfiguracaoFiscal, TributacaoFiscal, VinculoFiscal


class VinculoFiscalForm(EstiloTailwindMixin, forms.ModelForm):
    desativado = forms.BooleanField(label="Desativado", required=False,
                                    help_text="Some das opções no cadastro do produto, mas continua onde já está em uso.")

    class Meta:
        model = VinculoFiscal
        fields = ["nome", "tipo_item", "padrao"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].widget.attrs["placeholder"] = "Ex.: ICMS Tributado - PIS isento"
        self.initial.setdefault("desativado", not self.instance.ativo if self.instance.pk else False)

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if VinculoFiscal.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Já existe um vínculo fiscal com esta descrição.")
        return nome

    def clean(self):
        dados = super().clean()
        self.instance.ativo = not dados.get("desativado", False)
        if dados.get("padrao") and dados.get("desativado"):
            self.add_error("padrao", "Um vínculo desativado não pode ser o padrão.")
        return dados

    def save(self, commit=True):
        vinculo = super().save(commit)
        if commit and vinculo.padrao:
            VinculoFiscal.objects.exclude(pk=vinculo.pk).filter(padrao=True).update(padrao=False)  # só um padrão
        return vinculo


class ConfiguracaoFiscalForm(EstiloTailwindMixin, forms.ModelForm):
    """Janela "Adicionar configuração" (e "Clonar"): documento, UF de origem, UF de destino e regime."""

    class Meta:
        model = ConfiguracaoFiscal
        fields = ["documento", "uf_origem", "uf_destino", "regime"]

    def __init__(self, *args, vinculo=None, empresa=None, **kwargs):
        kwargs.setdefault("prefix", "config")
        super().__init__(*args, **kwargs)
        if vinculo is not None:
            self.instance.vinculo = vinculo
        # Sugestão: a UF e o regime da empresa atual
        municipio = getattr(empresa, "municipio", None)
        if municipio and not self.is_bound:
            self.initial.setdefault("uf_origem", municipio.uf)
        if empresa is not None and not self.is_bound and empresa.regime_tributario:
            self.initial.setdefault("regime", empresa.regime_tributario)  # a empresa já guarda o CRT
        self.initial.setdefault("uf_destino", TODAS_UFS)
        self.fields["uf_destino"].required = False  # na NFC-e o campo fica travado (é a própria UF de origem)

    def clean(self):
        dados = super().clean()
        if dados.get("documento") == "nfce" and dados.get("uf_origem"):
            # NFC-e é venda ao consumidor presente: sempre dentro do estado
            dados["uf_destino"] = dados["uf_origem"]
        elif not dados.get("uf_destino"):
            self.add_error("uf_destino", "Escolha a UF de destino.")
        chave = {k: dados.get(k) for k in ("documento", "uf_origem", "uf_destino", "regime")}
        if all(chave.values()) and self.instance.vinculo_id and ConfiguracaoFiscal.objects.filter(
                vinculo_id=self.instance.vinculo_id, **chave).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este vínculo já tem uma configuração com o mesmo documento, UFs e regime.")
        return dados


def _opcao_atual(modelo, codigo):
    """[("", "Nenhum"), (codigo, "codigo - descrição")] para os campos de busca (a lista vem do banco)."""
    opcoes = [("", "Nenhum")]
    if codigo:
        item = modelo.objects.filter(pk=codigo).first()
        opcoes.append((codigo, str(item) if item else codigo))
    return opcoes


# Só na saída (a NF-e de entrada não tem): detalhes da base do ICMS, natureza da receita e IBS/CBS
CAMPOS_SO_SAIDA = ("icms_zerar_base", "icms_acrescimo", "icms_modalidade_base", "icms_reducao_base", "icms_diferimento",
                   "pis_cofins_grupo", "pis_cofins_natureza", "ibscbs_cst", "cclasstrib")
# Só na NF-e de saída: ICMS substituição tributária e o enquadramento do IPI
CAMPOS_SO_NFE_SAIDA = ("icms_st_modalidade", "icms_st_mva", "icms_st_aliquota", "icms_st_reducao_base",
                       "icms_st_valor_pauta", "icms_st_somar_ipi", "ipi_enquadramento")


class TributacaoFiscalForm(EstiloTailwindMixin, forms.ModelForm):
    """Tributação de entrada ou de saída de uma configuração do vínculo."""

    cfop = forms.CharField(label="CFOP", max_length=5, widget=forms.Select,
                           error_messages={"required": "Escolha o CFOP."})
    icms_cst = forms.ChoiceField(label="CST/CSOSN", error_messages={"required": "Escolha o CST/CSOSN do ICMS."})
    pis_cst = forms.ChoiceField(label="PIS", error_messages={"required": "Escolha o CST do PIS."})
    cofins_cst = forms.ChoiceField(label="COFINS", error_messages={"required": "Escolha o CST da COFINS."})
    ipi_cst = forms.ChoiceField(label="Situação", required=False)
    ibscbs_cst = forms.ChoiceField(label="Código de situação tributária (CST)", required=False)
    cclasstrib = forms.CharField(label="Classificação tributária (cClassTrib)", required=False, widget=forms.Select)

    class Meta:
        model = TributacaoFiscal
        fields = ["cfop", "icms_cst", "icms_aliquota", "icms_zerar_base", "icms_acrescimo", "icms_modalidade_base",
                  "icms_reducao_base", "icms_diferimento",
                  "icms_st_modalidade", "icms_st_mva", "icms_st_aliquota", "icms_st_reducao_base", "icms_st_valor_pauta",
                  "icms_st_somar_ipi",
                  "pis_cofins_grupo", "pis_cofins_natureza", "pis_cst", "pis_aliquota", "cofins_cst", "cofins_aliquota",
                  "ipi_cst", "ipi_aliquota", "ipi_enquadramento", "exige_gta", "ibscbs_cst", "cclasstrib"]

    def __init__(self, *args, configuracao, operacao, **kwargs):
        super().__init__(*args, **kwargs)
        self.configuracao, self.operacao = configuracao, operacao
        t = self.instance

        self.fields["icms_cst"].choices = [("", "Selecione")] + cst_icms_do_regime(configuracao.regime)
        self.fields["icms_cst"].label = "CSOSN" if configuracao.usa_csosn else "CST"
        if operacao == "entrada":  # na compra o CST/CSOSN pode ficar em branco
            self.fields["icms_cst"].required = False
            self.fields["icms_cst"].choices = [("", "Nenhum")] + cst_icms_do_regime(configuracao.regime)
        pis_cofins = [("", "Selecione")] + cst_pis_cofins_da_operacao(operacao)
        self.fields["pis_cst"].choices = pis_cofins
        self.fields["cofins_cst"].choices = pis_cofins
        self.fields["ipi_cst"].choices = [("", "Não se aplica")] + cst_ipi_da_operacao(operacao)
        self.fields["ibscbs_cst"].choices = [("", "Nenhum")] + [(c.codigo, str(c)) for c in CstIbsCbs.objects.all()]

        # Campos de busca: aqui só o escolhido; a lista vem do banco enquanto a pessoa digita
        def atual(nome, valor_salvo):
            return re.sub(r"\D", "", (self.data.get(self.add_prefix(nome)) if self.is_bound else valor_salvo) or "")
        self.fields["cfop"].widget.choices = _opcao_atual(Cfop, atual("cfop", t.cfop))
        self.fields["cclasstrib"].widget.choices = _opcao_atual(ClassTrib, atual("cclasstrib", t.cclasstrib))

        self.fields["pis_cofins_grupo"].choices = [("", "Nenhum")] + GRUPOS_NATUREZA_RECEITA  # (saída)
        self.fields["icms_modalidade_base"].required = False  # sem escolha: 3 - Valor da operação
        self.fields["pis_cofins_natureza"].widget.attrs.update(
            {"inputmode": "numeric", "data-mascara": "numeros", "maxlength": "3", "placeholder": "3 dígitos"})

        self.fields["icms_st_modalidade"].required = False  # sem escolha: 4 - Margem de valor agregado
        self.fields["ipi_enquadramento"].required = False   # sem escolha: 999
        self.fields["ipi_enquadramento"].widget.attrs.update(
            {"inputmode": "numeric", "data-mascara": "numeros", "maxlength": "3"})
        for nome in ("icms_aliquota", "icms_acrescimo", "icms_reducao_base", "icms_diferimento",
                     "icms_st_mva", "icms_st_aliquota", "icms_st_reducao_base", "icms_st_valor_pauta",
                     "pis_aliquota", "cofins_aliquota", "ipi_aliquota"):
            modelo = TributacaoFiscal._meta.get_field(nome)
            maximo = 100 if any(getattr(v, "limit_value", None) == 100 for v in modelo.validators) else None
            campo = _valor(modelo.verbose_name, casas=modelo.decimal_places, maximo=maximo, required=False)
            campo.help_text = modelo.help_text
            campo.widget.attrs["class"] = self.fields[nome].widget.attrs.get("class", "")
            self.fields[nome] = campo

        # Cada situação só mostra o que se aplica a ela
        fora = set()
        if operacao == "entrada":  # NF-e de entrada: CST e alíquota do ICMS e do PIS/COFINS, IPI e GTA
            fora |= set(CAMPOS_SO_SAIDA)
        if operacao == "entrada" or configuracao.documento == "nfce":
            fora |= set(CAMPOS_SO_NFE_SAIDA)
        if configuracao.documento == "nfce":  # NFC-e não tem IPI nem GTA
            fora |= {"ipi_cst", "ipi_aliquota", "exige_gta"}
        for nome in fora:
            self.fields.pop(nome, None)

    def _tem(self, *nomes):
        return all(n in self.fields for n in nomes)

    @property
    def tem_ipi(self):
        return self._tem("ipi_cst")

    @property
    def tem_detalhes_icms(self):
        return self._tem("icms_zerar_base")

    @property
    def tem_st(self):
        return self._tem("icms_st_modalidade")

    @property
    def tem_natureza(self):
        return self._tem("pis_cofins_grupo")

    @property
    def tem_ibscbs(self):
        return self._tem("ibscbs_cst")

    @property
    def tem_gta(self):
        return self._tem("exige_gta")

    @property
    def digitos_cfop(self):
        c = self.configuracao
        if c.documento == "nfce":
            return ("5",)  # NFC-e: venda dentro do estado
        return primeiros_digitos_cfop(self.operacao, c.uf_origem, c.uf_destino)

    def clean_cfop(self):
        cfop = re.sub(r"\D", "", self.cleaned_data.get("cfop") or "")
        if len(cfop) != 4:
            raise ValidationError("Escolha o CFOP.")
        if Cfop.objects.exists() and not Cfop.objects.filter(pk=cfop).exists():
            raise ValidationError("CFOP não encontrado na tabela.")
        if cfop[0] not in self.digitos_cfop:
            esperado = " ou ".join(f"{d}.xxx" for d in self.digitos_cfop)
            raise ValidationError(f"Para esta configuração o CFOP começa com {esperado}.")
        return cfop

    def clean_cclasstrib(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cclasstrib") or "")

    def clean(self):
        dados = super().clean()
        for nome, campo in self.fields.items():
            if isinstance(campo, ValorField) and dados.get(nome) is None and nome not in self.errors:
                dados[nome] = 0
        cst, classe = dados.get("ibscbs_cst"), dados.get("cclasstrib")
        if classe and not cst:
            self.add_error("cclasstrib", "Escolha o CST do IBS/CBS antes da classificação.")
        elif classe and ClassTrib.objects.exists() and not ClassTrib.objects.filter(pk=classe, cst_id=cst).exists():
            self.add_error("cclasstrib", "Esta classificação não é do CST escolhido.")
        if self.tem_ipi and not dados.get("ipi_cst"):
            dados["ipi_aliquota"] = 0
        if self.tem_detalhes_icms:
            if not dados.get("icms_modalidade_base"):
                dados["icms_modalidade_base"] = "3"  # valor da operação
            if dados.get("icms_zerar_base"):
                dados["icms_aliquota"] = 0  # base e alíquota zeradas
        if self.tem_st:
            if not dados.get("icms_st_modalidade"):
                dados["icms_st_modalidade"] = "4"  # margem de valor agregado
            enquadramento = re.sub(r"\D", "", dados.get("ipi_enquadramento") or "") or "999"
            if len(enquadramento) != 3:
                self.add_error("ipi_enquadramento", "O enquadramento do IPI tem 3 dígitos (999 = tributação normal).")
            dados["ipi_enquadramento"] = enquadramento
        if self.tem_natureza:
            natureza = re.sub(r"\D", "", dados.get("pis_cofins_natureza") or "")
            if natureza and len(natureza) != 3:
                self.add_error("pis_cofins_natureza", "A natureza da receita tem 3 dígitos.")
            elif natureza and not dados.get("pis_cofins_grupo"):
                self.add_error("pis_cofins_grupo", "Escolha o grupo (tabela) da natureza da receita.")
            dados["pis_cofins_natureza"] = natureza
        return dados
