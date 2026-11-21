import re

from django import forms

from core.forms import EstiloTailwindMixin, ValorField
from localidades.models import Municipio

from .models import UFS, Empresa
from .validators import limpar_documento


class EmpresaForm(EstiloTailwindMixin, forms.ModelForm):
    documento = forms.CharField(label="CPF/CNPJ", max_length=18)
    cep = forms.CharField(label="CEP", max_length=9, required=False)
    telefone = forms.CharField(label="Telefone", max_length=15, required=False)
    # UF serve só para filtrar a busca de cidade; quem fica gravado é o município
    uf = forms.ChoiceField(label="UF", choices=[("", "UF")] + UFS, required=False)
    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.all(), required=False, widget=forms.HiddenInput
    )
    aliquota_credito = ValorField(label="Alíquota de crédito (%)", min_value=0, max_value=100, decimal_places=2,
                                  max_digits=5, required=False,
                                  help_text="Simples Nacional: percentual de crédito de ICMS informado na nota (pCredSN).")

    class Meta:
        model = Empresa
        fields = [
            "unidade", "razao_social", "nome_fantasia", "documento",
            "inscricao_estadual", "inscricao_municipal",
            "cep", "logradouro", "numero", "complemento", "bairro", "municipio",
            "telefone", "email", "nome_nos_documentos",
            "regime_tributario", "aliquota_credito", "tipo_inventario", "deduzir_icms_base_pis_cofins", "ativa",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["documento"].widget.attrs["data-mascara"] = "documento"
        self.fields["cep"].widget.attrs["data-mascara"] = "cep"
        self.fields["telefone"].widget.attrs["data-mascara"] = "telefone"
        if self.instance.pk and self.instance.municipio_id:
            self.initial["uf"] = self.instance.municipio.uf
        self.fields["tipo_inventario"].required = False  # sem escolha: contábil
        self.fields["regime_tributario"].choices = [("", "Selecione")] + list(Empresa._meta.get_field("regime_tributario").choices)

    def clean_tipo_inventario(self):
        return self.cleaned_data.get("tipo_inventario") or Empresa.TipoInventario.CONTABIL

    def clean_aliquota_credito(self):
        return self.cleaned_data.get("aliquota_credito") or 0

    def clean_documento(self):
        return limpar_documento(self.cleaned_data["documento"])

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep", ""))

    def clean_telefone(self):
        return re.sub(r"\D", "", self.cleaned_data.get("telefone", ""))
