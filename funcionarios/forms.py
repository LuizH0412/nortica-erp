import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from contas.forms import conferir_senhas, email_em_uso
from contas.models import Usuario
from core.forms import CadastroSimplesForm, DataInput, EstiloTailwindMixin
from empresas.models import UFS
from empresas.validators import cpf_valido, limpar_documento
from localidades.models import Municipio

from .models import Funcao, Funcionario, Setor


def campo_percentual(label, help_text=""):
    # Em branco vale 0
    return forms.DecimalField(
        label=label, help_text=help_text, localize=True, required=False,
        min_value=0, max_value=100, max_digits=5, decimal_places=2,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0,00"}),
    )


class FuncionarioForm(EstiloTailwindMixin, forms.ModelForm):
    cpf = forms.CharField(label="CPF", max_length=14, required=False)
    cep = forms.CharField(label="CEP", max_length=9, required=False)
    # UF serve só para filtrar a busca de cidade; quem fica gravado é o município
    uf = forms.ChoiceField(label="UF", choices=[("", "UF")] + UFS, required=False)
    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.all(), required=False, widget=forms.HiddenInput
    )
    desconto_maximo = campo_percentual("Desconto máximo (%)", "Maior desconto que pode dar numa venda.")
    comissao = campo_percentual("Comissão (%)")
    cartao = forms.CharField(
        label="Número do cartão do supervisor", required=False, max_length=64,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
    )

    class Meta:
        model = Funcionario
        fields = [
            "nome", "funcao", "setor",
            "cpf", "rg", "data_admissao", "data_demissao",
            "cep", "logradouro", "numero", "complemento", "bairro", "municipio",
            "ponto_referencia",
            "desconto_maximo", "comissao", "supervisor",
            "observacao", "ativo",
        ]
        widgets = {
            "data_admissao": DataInput(),
            "data_demissao": DataInput(),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario_logado=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcao"].empty_label = "Selecione"
        self.fields["setor"].empty_label = "Nenhum"
        self.fields["cpf"].widget.attrs["data-mascara"] = "cpf"
        self.fields["cep"].widget.attrs["data-mascara"] = "cep"
        if self.instance.pk and self.instance.municipio_id:
            self.initial["uf"] = self.instance.municipio.uf
        if self.instance.tem_cartao:
            self.fields["cartao"].help_text = "Já cadastrado. Preencha só para trocar."
        # Quem edita o próprio cadastro não pode se desativar
        if usuario_logado and self.instance.pk and self.instance.usuario_id == usuario_logado.pk:
            self.fields["ativo"].disabled = True
        # Só funções/setores ativos aparecem; o que o funcionário já usa continua na lista
        for campo, atual in (("funcao", self.instance.funcao_id), ("setor", self.instance.setor_id)):
            qs = self.fields[campo].queryset
            self.fields[campo].queryset = qs.filter(Q(ativo=True) | Q(pk=atual)) if atual else qs.filter(ativo=True)

    def clean_cpf(self):
        cpf = limpar_documento(self.cleaned_data.get("cpf"))
        if not cpf:
            return ""
        if not cpf_valido(cpf):
            raise ValidationError("CPF inválido.")
        repetido = Funcionario.objects.filter(cpf=cpf).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise ValidationError("Já existe um funcionário com este CPF.")
        return cpf

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep", ""))

    def clean_desconto_maximo(self):
        return self.cleaned_data.get("desconto_maximo") or Decimal("0")

    def clean_comissao(self):
        return self.cleaned_data.get("comissao") or Decimal("0")

    def clean(self):
        dados = super().clean()
        admissao, demissao = dados.get("data_admissao"), dados.get("data_demissao")
        if admissao and demissao and demissao < admissao:
            self.add_error("data_demissao", "A demissão não pode ser antes da admissão.")
        if dados.get("supervisor") and not dados.get("cartao") and not self.instance.tem_cartao:
            self.add_error("cartao", "Informe o número do cartão do supervisor.")
        return dados

    def save(self, commit=True):
        funcionario = super().save(commit=False)
        if not funcionario.supervisor:
            funcionario.definir_cartao("")
        elif self.cleaned_data.get("cartao"):
            funcionario.definir_cartao(self.cleaned_data["cartao"])
        if commit:
            funcionario.save()
        return funcionario


class UsuarioFuncionarioForm(EstiloTailwindMixin, forms.Form):
    """Aba "Usuário": e-mail e senha de login do funcionário."""

    # Livre: aceita qualquer texto como login e qualquer senha (só não pode repetir o login)
    email = forms.CharField(label="E-mail", max_length=254)
    password1 = forms.CharField(
        label="Senha", required=False, strip=False, widget=forms.PasswordInput
    )
    password2 = forms.CharField(
        label="Redigite a senha", required=False, strip=False, widget=forms.PasswordInput
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario:
            self.initial["email"] = usuario.email
            self.fields["password1"].label = "Nova senha"
            self.fields["password1"].help_text = "Preencha só se quiser trocar a senha."
            self.fields["password2"].label = "Redigite a nova senha"
        else:
            # Usuário novo: senha obrigatória (o asterisco aparece no rótulo)
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_em_uso(email, exceto=self.usuario):
            raise ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean(self):
        dados = super().clean()
        dados["senha"] = conferir_senhas(self, usuario=self.usuario, validar_forca=False)
        return dados

    def salvar(self, funcionario):
        """Cria (ou atualiza) o usuário e liga ao funcionário."""
        dados = self.cleaned_data
        usuario = self.usuario or Usuario()
        usuario.email = dados["email"]
        usuario.first_name = funcionario.nome[:150]
        usuario.last_name = ""
        # Funcionário desativado não entra no sistema
        usuario.is_active = funcionario.ativo
        if dados.get("senha"):
            usuario.set_password(dados["senha"])
        usuario.save()
        if funcionario.usuario_id != usuario.pk:
            funcionario.usuario = usuario
            funcionario.save(update_fields=["usuario"])
        return usuario


class FuncaoForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Funcao


class SetorForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Setor
