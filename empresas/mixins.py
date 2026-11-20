from django.contrib import messages
from django.shortcuts import redirect


class EmpresaAtualMixin:
    """
    Para views baseadas em classe de models que herdam de DadoDaEmpresa.

        class ProdutoListView(LoginRequiredMixin, EmpresaAtualMixin, ListView):
            model = Produto

    - Listagem, edição e exclusão só enxergam registros da empresa atual
      (um pk de outra filial dá 404).
    - Ao criar, o registro é gravado na empresa atual.
    - Sem empresa atual (ex.: master num sistema sem empresas), volta ao início.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request, "empresa_atual", None) is None:
            messages.warning(request, "Cadastre ou escolha uma empresa antes de continuar.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().da_empresa(self.request.empresa_atual)

    def form_valid(self, form):
        if form.instance.pk is None:
            form.instance.empresa = self.request.empresa_atual
        return super().form_valid(form)
