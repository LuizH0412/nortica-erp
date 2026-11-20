from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.forms import EstiloTailwindMixin
from empresas.models import Empresa

from .models import AcessoEmpresa, Perfil, Usuario


def email_em_uso(email, exceto=None):
    """Já existe outro usuário com este e-mail? (sem diferenciar maiúsculas)"""
    qs = Usuario.objects.filter(email__iexact=(email or "").strip())
    if exceto is not None and exceto.pk:
        qs = qs.exclude(pk=exceto.pk)
    return qs.exists()


def conferir_senhas(form, campo1="password1", campo2="password2", usuario=None, validar_forca=True):
    """
    Confere se as duas senhas batem. Com validar_forca, também exige uma senha forte
    (tamanho mínimo, não comum, não só números...).
    """
    p1, p2 = form.cleaned_data.get(campo1), form.cleaned_data.get(campo2)
    if not (p1 or p2):
        return None
    if p1 != p2:
        form.add_error(campo2, "As senhas não conferem.")
        return None
    if not validar_forca:
        return p1
    try:
        validate_password(p1, usuario)
    except ValidationError as erro:
        form.add_error(campo1, erro)
        return None
    return p1


def empresas_que_administra(usuario):
    """Empresas em que a pessoa pode dar ou tirar acessos (onde ela acessa as configurações)."""
    if usuario.eh_master:
        return Empresa.objects.all()
    return Empresa.objects.filter(
        acessos__usuario=usuario, acessos__perfil__pode_configurar=True
    ).distinct()


class UsuarioForm(EstiloTailwindMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "is_active"]
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "email": "E-mail (login)",
            "is_active": "Ativo",
        }

    def __init__(self, *args, usuario_logado=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Evita a pessoa se trancar para fora do próprio sistema
        if usuario_logado and self.instance.pk == usuario_logado.pk:
            self.fields["is_active"].disabled = True
        # Quem é funcionário tem o nome mantido pelo cadastro de funcionário
        self.funcionario = getattr(self.instance, "funcionario", None) if self.instance.pk else None
        if self.funcionario:
            for nome in ("first_name", "last_name"):
                self.fields[nome].disabled = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_em_uso(email, exceto=self.instance):
            raise ValidationError("Já existe um usuário com este e-mail.")
        return email


class UsuarioCriarForm(UsuarioForm):
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)

    def clean(self):
        dados = super().clean()
        conferir_senhas(self)
        return dados

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
        return usuario


class SenhaForm(EstiloTailwindMixin, SetPasswordForm):
    pass


class AdicionarPerfilForm(EstiloTailwindMixin, forms.Form):
    """
    Dá um perfil ao usuário em uma ou mais empresas.
    Só oferece empresas em que ele ainda NÃO tem perfil (é um perfil por empresa);
    para trocar, remove-se o perfil atual e adiciona-se o novo.
    """

    perfil = forms.ModelChoiceField(label="Perfil", queryset=Perfil.objects.all(), empty_label="Selecione")
    empresas = forms.ModelMultipleChoiceField(
        label="Empresas", queryset=Empresa.objects.none(), widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Marque ao menos uma empresa.",
            "invalid_choice": "Escolha só empresas em que a pessoa ainda não tem perfil de acesso.",
        },
    )

    def __init__(self, *args, usuario_logado, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        possiveis = empresas_que_administra(usuario_logado)
        # Empresas em que a pessoa já tem perfil: aparecem travadas na janela, só para informar
        self.ja_vinculadas = []
        if usuario is not None:
            self.ja_vinculadas = list(
                usuario.acessos.select_related("empresa", "perfil")
                .filter(empresa__in=possiveis).order_by("empresa__unidade")
            )
            possiveis = possiveis.exclude(acessos__usuario=usuario)
        self.fields["empresas"].queryset = possiveis
        # Com uma única empresa possível, ela já vem marcada
        livres = list(possiveis[:2])
        if len(livres) == 1:
            self.initial["empresas"] = [livres[0].pk]

    @property
    def tem_empresas_livres(self):
        return self.fields["empresas"].queryset.exists()

    def salvar(self, usuario):
        perfil = self.cleaned_data["perfil"]
        AcessoEmpresa.objects.bulk_create(
            [AcessoEmpresa(usuario=usuario, empresa=e, perfil=perfil) for e in self.cleaned_data["empresas"]]
        )


class PerfilForm(EstiloTailwindMixin, forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ["nome", "pode_configurar"]
