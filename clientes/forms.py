import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.forms import CadastroSimplesForm, DataInput, EstiloTailwindMixin, ValorField
from empresas.models import UFS
from empresas.validators import cnpj_valido, cpf_valido, limpar_documento
from funcionarios.models import Funcionario
from localidades.models import Municipio

from .models import Area, Cliente, EnderecoCliente, Tag, TipoCliente

# Quem pode ser atendente de um cliente
FUNCOES_ATENDENTE = ("atendente", "vendedor")


def atendentes_possiveis(incluir=None):
    """Funcionários ativos com função Atendente ou Vendedor (+ quem já estiver no cadastro)."""
    filtro = Q(ativo=True) & (Q(funcao__nome__iexact=FUNCOES_ATENDENTE[0]) | Q(funcao__nome__iexact=FUNCOES_ATENDENTE[1]))
    if incluir:
        filtro |= Q(pk=incluir)
    return Funcionario.objects.filter(filtro).order_by("nome")


def ativos_ou(queryset, *atuais):
    """Só os itens ativos de um cadastro simples, mais os que o registro já usa."""
    atuais = [a for a in atuais if a]
    filtro = Q(ativo=True) | Q(pk__in=atuais) if atuais else Q(ativo=True)
    return queryset.filter(filtro)


class ClienteForm(EstiloTailwindMixin, forms.ModelForm):
    documento = forms.CharField(label="CPF/CNPJ", max_length=18, required=False)
    cep = forms.CharField(label="CEP", max_length=9, required=False)
    # UF serve só para filtrar a busca de cidade; quem fica gravado é o município
    uf = forms.ChoiceField(label="UF", choices=[("", "UF")] + UFS, required=False)
    municipio = forms.ModelChoiceField(queryset=Municipio.objects.all(), required=False, widget=forms.HiddenInput)
    tags = forms.ModelMultipleChoiceField(
        label="TAGs de classificação", queryset=Tag.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Cliente
        fields = [
            "pessoa", "documento", "inscricao_estadual", "inscricao_municipal", "contribuinte",
            "nome_fantasia", "razao_social",
            "cep", "logradouro", "numero", "complemento", "ponto_referencia", "bairro", "municipio",
            "area", "atendente", "indicador_finalidade", "tipo_cliente", "data_fundacao",
            "bloqueado", "ativo", "tags", "observacao",
        ]
        widgets = {
            "data_fundacao": DataInput(),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, funcionario_logado=None, **kwargs):
        super().__init__(*args, **kwargs)
        cliente = self.instance
        self.fields["documento"].widget.attrs["data-mascara"] = "documento"
        self.fields["cep"].widget.attrs["data-mascara"] = "cep"
        self.fields["nome_fantasia"].required = False  # obrigatório só para pessoa jurídica (veja clean)
        self.fields["area"].empty_label = "Nenhuma"
        self.fields["tipo_cliente"].empty_label = "Nenhum"
        self.fields["atendente"].empty_label = "Nenhum"
        if cliente.pk and cliente.municipio_id:
            self.initial["uf"] = cliente.municipio.uf

        # Cadastros simples: só os ativos (+ o que o cliente já usa)
        self.fields["area"].queryset = ativos_ou(Area.objects.all(), cliente.area_id)
        self.fields["tipo_cliente"].queryset = ativos_ou(TipoCliente.objects.all(), cliente.tipo_cliente_id)
        tags_atuais = list(cliente.tags.values_list("pk", flat=True)) if cliente.pk else []
        self.fields["tags"].queryset = ativos_ou(Tag.objects.all(), *tags_atuais)

        # Atendente: num cadastro novo, já vem quem está cadastrando
        atual = cliente.atendente_id
        if not cliente.pk and funcionario_logado is not None:
            self.initial.setdefault("atendente", funcionario_logado.pk)
            atual = atual or funcionario_logado.pk
        self.fields["atendente"].queryset = atendentes_possiveis(incluir=atual)

        # Tipo de cliente padrão num cadastro novo
        if not cliente.pk and "tipo_cliente" not in self.initial:
            padrao = TipoCliente.objects.filter(nome__iexact="Consumidor", ativo=True).first()
            if padrao:
                self.initial["tipo_cliente"] = padrao.pk

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep", ""))

    def clean(self):
        dados = super().clean()
        pessoa = dados.get("pessoa")
        documento = limpar_documento(dados.get("documento"))
        dados["documento"] = documento
        if documento:
            if pessoa == Cliente.Pessoa.FISICA and not (len(documento) == 11 and cpf_valido(documento)):
                self.add_error("documento", "CPF inválido.")
            elif pessoa == Cliente.Pessoa.JURIDICA and not (len(documento) == 14 and cnpj_valido(documento)):
                self.add_error("documento", "CNPJ inválido.")
            elif Cliente.objects.filter(documento=documento).exclude(pk=self.instance.pk).exists():
                self.add_error("documento", "Já existe um cliente com este CPF/CNPJ.")
        if pessoa == Cliente.Pessoa.JURIDICA and not dados.get("nome_fantasia"):
            self.add_error("nome_fantasia", "Informe o nome fantasia.")
        return dados


class EnderecoClienteForm(EstiloTailwindMixin, forms.ModelForm):
    """Janela "Adicione um endereço" da aba Outros endereços (prefixo "end" nos campos)."""

    PREFIXO = "end"

    cep = forms.CharField(label="CEP", max_length=9, required=False)
    uf = forms.ChoiceField(label="UF", choices=[("", "UF")] + UFS, required=False)
    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.all(), widget=forms.HiddenInput,
        error_messages={"required": "Escolha a cidade na lista que aparece enquanto você digita."},
    )

    class Meta:
        model = EnderecoCliente
        fields = ["tipo", "cep", "numero", "logradouro", "ponto_referencia", "municipio", "bairro", "complemento"]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", self.PREFIXO)
        super().__init__(*args, **kwargs)
        self.fields["cep"].widget.attrs["data-mascara"] = "cep"
        if self.instance.pk and self.instance.municipio_id:
            self.initial["uf"] = self.instance.municipio.uf

    def clean_cep(self):
        return re.sub(r"\D", "", self.cleaned_data.get("cep", ""))


class CreditoClienteForm(EstiloTailwindMixin, forms.ModelForm):
    """Janela "Gerenciar crédito" da aba Financeiro."""

    limite_credito = ValorField(
        label="Limite para compra a prazo", required=False, min_value=0, max_digits=12, decimal_places=2,
        help_text="Quanto o cliente pode ter em aberto comprando a prazo. Zero = sem limite liberado.",
    )

    class Meta:
        model = Cliente
        fields = ["limite_credito", "bloqueado"]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "credito")  # não colide com os campos da aba Dados cadastrais
        super().__init__(*args, **kwargs)

    def clean_limite_credito(self):
        return self.cleaned_data.get("limite_credito") or 0


class LancarCreditoForm(EstiloTailwindMixin, forms.Form):
    """Lança crédito para o cliente usar na loja (janela "Gerenciar crédito")."""

    pedido = forms.CharField(label="Pedido", max_length=30, required=False,
                             widget=forms.TextInput(attrs={"placeholder": "Opcional"}))
    valor = ValorField(label="Valor", min_value=Decimal("0.01"), max_digits=12, decimal_places=2,
                       error_messages={"required": "Informe o valor do crédito."})

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "lancar")
        super().__init__(*args, **kwargs)


class TipoClienteForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = TipoCliente


class AreaForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Area


class TagForm(CadastroSimplesForm):
    class Meta(CadastroSimplesForm.Meta):
        model = Tag
