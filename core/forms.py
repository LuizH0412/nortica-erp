import re

from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from localidades.models import Municipio

from .models import UFS, Empresa, Usuario
from .validators import limpar_documento

CLASSE_INPUT = (
    "mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 "
    "focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/30"
)
CLASSE_CHECK = "mt-0.5 h-4 w-4 rounded border-line accent-primary"


class EstiloTailwindMixin:
    """Aplica o visual do Nexum em todos os campos do formulário."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                campo.widget.attrs["class"] = CLASSE_CHECK
            else:
                campo.widget.attrs["class"] = CLASSE_INPUT

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


class UsuarioForm(EstiloTailwindMixin, forms.ModelForm):
    empresas_permitidas = forms.ModelMultipleChoiceField(
        label="Empresas que pode acessar",
        queryset=Empresa.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Usuario
        fields = [
            "first_name", "last_name", "username", "email",
            "nivel", "is_active", "empresas_permitidas",
        ]
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "username": "Usuário (login)",
            "email": "E-mail",
            "nivel": "Perfil",
            "is_active": "Ativo",
        }

    def __init__(self, *args, usuario_logado=None, **kwargs):
        super().__init__(*args, **kwargs)
        # O master nunca é criado nem atribuído por esta tela
        self.fields["nivel"].choices = [
            (Usuario.Nivel.ADMINISTRADOR, "Administrador"),
            (Usuario.Nivel.COMUM, "Usuário"),
        ]
        # Evita a pessoa se trancar para fora do próprio sistema
        if usuario_logado and self.instance.pk == usuario_logado.pk:
            for nome in ("is_active", "nivel", "empresas_permitidas"):
                self.fields[nome].disabled = True


class UsuarioCriarForm(UsuarioForm):
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Com uma única empresa ativa, ela já vem marcada
        ativas = list(Empresa.objects.filter(ativa=True)[:2])
        if len(ativas) == 1:
            self.initial.setdefault("empresas_permitidas", [ativas[0].pk])

    def clean(self):
        dados = super().clean()
        p1, p2 = dados.get("password1"), dados.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "As senhas não conferem.")
            else:
                try:
                    validate_password(p1)
                except ValidationError as erro:
                    self.add_error("password1", erro)
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
            self.save_m2m()  # grava as empresas marcadas
        return usuario


class SenhaForm(EstiloTailwindMixin, SetPasswordForm):
    pass