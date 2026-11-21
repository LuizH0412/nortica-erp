"""Recursos comuns das telas de lista (pesquisa) dos cadastros."""
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError

PARAMETRO_DESATIVADOS = "desativados"
PARAMETRO_ORDEM = "o"


class OrdenacaoMixin:
    """
    Colunas ordenáveis: clicar no título ordena crescente; clicar de novo, decrescente.

        class ProdutoListView(OrdenacaoMixin, ListView):
            ordenacoes = {"nome": "nome", "preco": "preco", "grupo": "grupo__nome"}

            def get_queryset(self):
                return self.ordenar(Produto.objects.all())

    No template, no lugar do <th>:
        {% include "partials/th_ordenar.html" with campo="nome" rotulo="Nome" %}
    """

    ordenacoes = {}  # chave usada na URL -> campo (ou lista de campos) do banco

    @property
    def ordem(self):
        valor = self.request.GET.get(PARAMETRO_ORDEM, "")
        return valor if valor.lstrip("-") in self.ordenacoes else ""

    def ordenar(self, qs):
        if not self.ordem:
            return qs
        campos = self.ordenacoes[self.ordem.lstrip("-")]
        campos = [campos] if isinstance(campos, str) else list(campos)
        sinal = "-" if self.ordem.startswith("-") else ""
        return qs.order_by(*[sinal + c for c in campos], "pk")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["ordem"] = self.ordem
        return contexto


class FiltroSituacaoMixin:
    """
    Para listas de cadastros que podem ser desativados (produto, cliente, funcionário...).

    - Por padrão a lista mostra só os ativos.
    - Com ?desativados=1 (interruptor "Só desativados" na pesquisa), mostra só os desativados.

    Uso, dentro do get_queryset da ListView:

        class ProdutoListView(FiltroSituacaoMixin, ListView):
            campo_ativo = "ativo"   # nome do campo booleano no model

            def get_queryset(self):
                return self.filtrar_situacao(Produto.objects.all())

    No template: {% include "partials/filtro_situacao.html" %} dentro do <form> da pesquisa.
    """

    campo_ativo = "ativo"

    @property
    def so_desativados(self):
        return self.request.GET.get(PARAMETRO_DESATIVADOS) == "1"

    def filtrar_situacao(self, qs):
        return qs.filter(**{self.campo_ativo: not self.so_desativados})

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["so_desativados"] = self.so_desativados
        return contexto


def excluir_selecionados(request, queryset, *, singular, plural, artigo="o", impedimento=None, excluir=None):
    """
    Botão "Excluir selecionados" das listas: exclui os registros marcados (checkbox name="selecionados").

    - impedimento(item): devolve o motivo para NÃO excluir aquele item (ou None para liberar)
    - excluir(item): como excluir (padrão: item.delete()); roda numa transação por item
    Exclui o que pode, explica o que ficou de fora e devolve quantos foram excluídos.
    """
    ids = [i for i in request.POST.getlist("selecionados") if i.isdigit()]
    itens = list(queryset.filter(pk__in=ids))
    if not itens:
        messages.warning(request, "Nenhum item selecionado.")
        return 0

    excluidos, recusados = 0, []
    for item in itens:
        nome = str(item)
        motivo = impedimento(item) if impedimento else None
        if motivo:
            recusados.append(f"{nome} ({motivo})")
            continue
        try:
            with transaction.atomic():
                (excluir or (lambda i: i.delete()))(item)
            excluidos += 1
        except ProtectedError:
            recusados.append(f"{nome} (já tem registros ligados; desative em vez de excluir)")

    if excluidos:
        sufixo = "s" if excluidos > 1 else ""
        messages.success(request, f"{excluidos} {plural if excluidos > 1 else singular} excluíd{artigo}{sufixo}.")
    if recusados:
        messages.warning(request, "Não foram excluídos: " + "; ".join(recusados) + ".")
    return excluidos
