from decimal import Decimal

from django import forms
from django.db.models import Q

CLASSE_INPUT = (
    "mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 "
    "focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/30"
)
CLASSE_CHECK = "mt-0.5 h-4 w-4 rounded border-line accent-primary"


class ValorField(forms.DecimalField):
    """
    Valor em reais digitado do jeito brasileiro: aceita "2.500,50", "2500,50" e "2500.50".
    Mostra o valor com vírgula ("2500,50").
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("localize", True)
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "0,00"}))
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        # Sempre com as casas decimais do campo ("0" vira "0,00"), também nos cadastros novos
        if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool) and self.decimal_places is not None:
            value = Decimal(str(value)).quantize(Decimal(1).scaleb(-self.decimal_places))
        return super().prepare_value(value)

    def to_python(self, value):
        if isinstance(value, str) and "," in value:
            value = value.strip().replace(".", "").replace(",", ".")  # ponto = milhar, vírgula = decimal
        return super().to_python(value)


class DataInput(forms.DateInput):
    """Campo de data com o calendário do navegador."""
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs, format="%Y-%m-%d")


class EstiloTailwindMixin:
    """Aplica o visual do Nexum em todos os campos do formulário."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                campo.widget.attrs["class"] = CLASSE_CHECK
            else:
                campo.widget.attrs["class"] = CLASSE_INPUT


class CadastroSimplesForm(EstiloTailwindMixin, forms.ModelForm):
    """Função, setor, tipo de cliente...: só o nome e se está ativo. Nome não se repete (nem com outra caixa)."""

    class Meta:
        fields = ["nome", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cadastro que pertence a outro (ex.: subgrupo -> grupo): o pai vem do POST como "pai"
        self.pai_campo = getattr(self._meta.model, "pai_campo", None)
        if self.pai_campo and not self.instance.pk and self.data.get("pai"):
            setattr(self.instance, f"{self.pai_campo}_id", int(self.data["pai"]))

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        modelo = self._meta.model
        repetidos = modelo.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if self.pai_campo:
            repetidos = repetidos.filter(**{f"{self.pai_campo}_id": getattr(self.instance, f"{self.pai_campo}_id")})
        if repetidos.exists():
            um = "uma" if modelo.artigo == "a" else "um"
            raise forms.ValidationError(f"Já existe {um} {modelo._meta.verbose_name} com este nome.")
        return nome


def ativos_ou(queryset, *atuais):
    """Só os itens ativos de um cadastro simples, mais os que o registro já usa."""
    atuais = [a for a in atuais if a]
    filtro = Q(ativo=True) | Q(pk__in=atuais) if atuais else Q(ativo=True)
    return queryset.filter(filtro)
