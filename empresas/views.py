from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from contas.permissions import (
    AdministradorMixin,
    MasterMixin,
    master_requerido,
)
from core.listas import FiltroSituacaoMixin, OrdenacaoMixin

from . import consultas
from .forms import EmpresaForm
from .models import Empresa
from .selecao import SESSAO_CHAVE, empresas_do_usuario, resolver_empresa
from .validators import limpar_documento


# ---------- Escolha e troca de empresa ----------

@login_required
def escolher_empresa(request):
    _, precisa_escolher = resolver_empresa(request)
    if not precisa_escolher:
        return redirect("home")
    return render(
        request, "empresas/escolher.html",
        {"empresas": empresas_do_usuario(request.user)},
    )


@login_required
@require_POST
def trocar_empresa(request, pk):
    empresa = get_object_or_404(empresas_do_usuario(request.user), pk=pk)
    trocou = request.session.get(SESSAO_CHAVE) != empresa.pk
    request.session[SESSAO_CHAVE] = empresa.pk
    if trocou:
        messages.success(request, f"Você está agora na empresa {empresa.unidade}.")
    return redirect("home")  # a troca sempre leva ao início


@login_required
def sem_acesso(request):
    return render(request, "sem_acesso.html")


# ---------- Cadastro de empresas ----------

class EmpresaListView(AdministradorMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    campo_ativo = "ativa"
    ordenacoes = {
        "unidade": "unidade", "empresa": ["nome_fantasia", "razao_social"],
        "documento": "documento", "cidade": "municipio__nome", "situacao": "ativa",
    }
    template_name = "empresas/lista.html"
    context_object_name = "empresas"

    def get_queryset(self):
        qs = self.filtrar_situacao(Empresa.objects.select_related("municipio"))
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            filtro = (
                Q(unidade__icontains=self.q)
                | Q(razao_social__icontains=self.q)
                | Q(nome_fantasia__icontains=self.q)
            )
            # CPF/CNPJ: aceita com ou sem pontos, barra e traço
            documento = limpar_documento(self.q)
            if documento:
                filtro |= Q(documento__icontains=documento)
            qs = qs.filter(filtro)
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto


class EmpresaCriarView(MasterMixin, CreateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"
    success_url = reverse_lazy("empresa_lista")
    extra_context = {"titulo": "Nova empresa"}

    def form_valid(self, form):
        messages.success(self.request, "Empresa cadastrada com sucesso.")
        return super().form_valid(form)


class EmpresaEditarView(AdministradorMixin, UpdateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"
    success_url = reverse_lazy("empresa_lista")
    extra_context = {"titulo": "Editar empresa"}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Sem registros ligados, o "Excluir" pede só a confirmação; com registros, abre a página que explica
        if self.request.user.eh_master:
            contexto["impedimentos_exclusao"] = self.object.vinculos_que_impedem_exclusao()
        return contexto

    def form_valid(self, form):
        messages.success(self.request, "Empresa atualizada com sucesso.")
        return super().form_valid(form)


@master_requerido
def empresa_excluir(request, pk):
    empresa = get_object_or_404(Empresa, pk=pk)
    impedimentos = empresa.vinculos_que_impedem_exclusao()
    if request.method == "POST" and not impedimentos:
        nome = str(empresa)
        try:
            empresa.delete()
        except ProtectedError:
            messages.error(
                request,
                "Esta empresa tem registros ligados a ela. Desative-a em vez de excluir.",
            )
            return redirect("empresa_lista")
        messages.success(request, f"Empresa {nome} excluída.")
        return redirect("empresa_lista")
    return render(
        request, "empresas/excluir.html",
        {"empresa": empresa, "impedimentos": impedimentos},
    )


# ---------- Consultas externas (CNPJ e CEP) ----------

@login_required
def consulta_cnpj(request):
    try:
        dados = consultas.consultar_cnpj(request.GET.get("documento", ""))
    except consultas.ConsultaErro as erro:
        return JsonResponse({"ok": False, "mensagem": str(erro)})
    return JsonResponse({"ok": True, "dados": dados})


@login_required
def consulta_cep(request):
    try:
        dados = consultas.consultar_cep(request.GET.get("cep", ""))
    except consultas.ConsultaErro as erro:
        return JsonResponse({"ok": False, "mensagem": str(erro)})
    return JsonResponse({"ok": True, "dados": dados})
