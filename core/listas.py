"""Recursos comuns das telas de lista (pesquisa) dos cadastros."""

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
