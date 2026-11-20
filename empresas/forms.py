import re

from django import forms

from core.forms import EstiloTailwindMixin
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

    class Meta:
        model = Empresa
        fields = [
            "unidade", "razao_social", "nome_fantasia", "documento",
            "inscricao_estadual", "inscricao_municipal",
            "cep", "logradouro", "numero", "complemento", "bairro", "municipio",
            "telefone", "email", "nome_nos_documentos",
            "regime_tributario", "ativa",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["documento"].widget.attrs["data-mascara"] = "documento"
        self.fields["cep"].widget.attrs["data-mascara"] = "cep"
        self.fields["telefone"].widget.attrs["data-mascara"] = "telefone"
        if self.instance.pk and self.instance.municipio_id:
            self.initial["uf"] = self.instance.municipio.uf

    def clean_documento(self):
        return limpar_documento(self.cleaned_data["documento"])

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep", ""))

    def clean_telefone(self):
        return re.sub(r"\D", "", self.cleaned_data.get("telefone", ""))
