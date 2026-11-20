from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse

from localidades.models import Municipio, normalizar

from . import consultas

from .empresas import SESSAO_CHAVE, empresas_do_usuario, resolver_empresa
from .forms import EmpresaForm, SenhaForm, UsuarioCriarForm, UsuarioForm
from .models import Empresa, Usuario
from .permissions import (
    AdministradorMixin,
    MasterMixin,
    administrador_requerido,
    master_requerido,
)


@login_required
def home(request):
    return render(request, "home.html")


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
    request.session[SESSAO_CHAVE] = empresa.pk
    return redirect("home")  # a troca sempre leva ao início


@login_required
def sem_acesso(request):
    return render(request, "sem_acesso.html")


# ---------- Empresas ----------

class EmpresaListView(AdministradorMixin, ListView):
    queryset = Empresa.objects.select_related("municipio")
    template_name = "empresas/lista.html"
    context_object_name = "empresas"


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


# ---------- Usuários ----------

def usuarios_visiveis():
    """Usuários que a tela de gestão mostra. O master nunca aparece."""
    return Usuario.objects.exclude(nivel=Usuario.Nivel.MASTER)


class UsuarioListView(AdministradorMixin, ListView):
    paginate_by = 20
    context_object_name = "usuarios"

    def get_queryset(self):
        qs = usuarios_visiveis()
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            qs = qs.filter(
                Q(first_name__icontains=self.q)
                | Q(last_name__icontains=self.q)
                | Q(username__icontains=self.q)
                | Q(email__icontains=self.q)
            )
        return qs.order_by("first_name", "username")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto

    def get_template_names(self):
        # Busca ao vivo: o HTMX pede só a tabela, não a página inteira
        if self.request.headers.get("HX-Request"):
            return ["usuarios/_tabela.html"]
        return ["usuarios/lista.html"]


class UsuarioFormMixin(AdministradorMixin):
    template_name = "usuarios/form.html"
    success_url = reverse_lazy("usuario_lista")

    def get_queryset(self):
        return usuarios_visiveis()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario_logado"] = self.request.user
        return kwargs


class UsuarioCriarView(UsuarioFormMixin, CreateView):
    form_class = UsuarioCriarForm
    extra_context = {"titulo": "Novo usuário"}

    def form_valid(self, form):
        messages.success(self.request, "Usuário criado com sucesso.")
        return super().form_valid(form)


class UsuarioEditarView(UsuarioFormMixin, UpdateView):
    form_class = UsuarioForm
    extra_context = {"titulo": "Editar usuário"}

    def form_valid(self, form):
        messages.success(self.request, "Usuário atualizado com sucesso.")
        return super().form_valid(form)


@administrador_requerido
def usuario_senha(request, pk):
    usuario = get_object_or_404(usuarios_visiveis(), pk=pk)
    form = SenhaForm(usuario, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Senha redefinida com sucesso.")
        return redirect("usuario_lista")
    return render(request, "usuarios/senha.html", {"form": form, "usuario": usuario})


# ---------- Consultas e busca de cidade ----------

@administrador_requerido
def consulta_cnpj(request):
    try:
        dados = consultas.consultar_cnpj(request.GET.get("documento", ""))
    except consultas.ConsultaErro as erro:
        return JsonResponse({"ok": False, "mensagem": str(erro)})
    return JsonResponse({"ok": True, "dados": dados})


@administrador_requerido
def consulta_cep(request):
    try:
        dados = consultas.consultar_cep(request.GET.get("cep", ""))
    except consultas.ConsultaErro as erro:
        return JsonResponse({"ok": False, "mensagem": str(erro)})
    return JsonResponse({"ok": True, "dados": dados})


@login_required
def municipio_busca(request):
    termo = normalizar(request.GET.get("q", ""))
    uf = request.GET.get("uf", "").strip().upper()
    if len(termo) < 2:
        return JsonResponse({"resultados": []})
    qs = Municipio.objects.filter(nome_busca__contains=termo)
    if uf:
        qs = qs.filter(uf=uf)
    qs = qs.annotate(
        ordem=Case(
            When(nome_busca__startswith=termo, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("ordem", "nome")[:15]
    return JsonResponse(
        {"resultados": [{"id": m.pk, "nome": m.nome, "uf": m.uf} for m in qs]}
    )