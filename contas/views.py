from django.contrib import messages
from django.db.models import Count, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from core.listas import FiltroSituacaoMixin, OrdenacaoMixin, excluir_selecionados

from .forms import (
    AdicionarPerfilForm,
    PerfilForm,
    SenhaForm,
    UsuarioCriarForm,
    UsuarioForm,
    empresas_que_administra,
)
from .models import AcessoEmpresa, Perfil, Usuario
from .permissions import AdministradorMixin, administrador_requerido


def usuarios_visiveis():
    """Usuários que a tela de gestão mostra. O master nunca aparece."""
    return Usuario.objects.filter(master=False)


def acessos_do_usuario(usuario):
    return usuario.acessos.select_related("perfil", "empresa").order_by("empresa__unidade")


def contexto_acessos(request, usuario, voltar):
    """O que o quadro "Perfis de acesso" precisa para ser desenhado."""
    return {
        "usuario_acessos": usuario,
        "acessos": acessos_do_usuario(usuario),
        "form_perfil": AdicionarPerfilForm(usuario_logado=request.user, usuario=usuario),
        "voltar": voltar,
        "eh_o_proprio": usuario.pk == request.user.pk,
    }


def _voltar(request, padrao):
    destino = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


# ---------- Usuários ----------

class UsuarioListView(AdministradorMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    campo_ativo = "is_active"
    ordenacoes = {"codigo": "pk", "nome": ["first_name", "last_name"]}  # só Código e nome têm seta
    paginate_by = 20
    context_object_name = "usuarios"

    def get_queryset(self):
        qs = self.filtrar_situacao(usuarios_visiveis())
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            qs = qs.filter(
                Q(first_name__icontains=self.q)
                | Q(last_name__icontains=self.q)
                | Q(email__icontains=self.q)
            )
        qs = (
            qs.select_related("funcionario")
            .prefetch_related(Prefetch("acessos", queryset=AcessoEmpresa.objects.select_related("perfil", "empresa")))
            .order_by("first_name", "email")
        )
        return self.ordenar(qs)  # a coluna clicada, se houver, substitui a ordem padrão

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
        resposta = super().form_valid(form)
        messages.success(self.request, "Usuário criado. Agora adicione os perfis de acesso dele.")
        return resposta

    def get_success_url(self):
        return reverse("usuario_editar", args=[self.object.pk])


class UsuarioEditarView(UsuarioFormMixin, UpdateView):
    form_class = UsuarioForm
    extra_context = {"titulo": "Editar usuário"}

    def get_success_url(self):
        return reverse("usuario_editar", args=[self.object.pk])  # continua no cadastro

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(contexto_acessos(self.request, self.object, self.request.path))
        return contexto

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
        return redirect("usuario_editar", pk=usuario.pk)
    return render(request, "usuarios/senha.html", {"form": form, "usuario": usuario})


# ---------- Perfis de acesso do usuário (por empresa) ----------

@administrador_requerido
@require_POST
def usuario_acesso_adicionar(request, pk):
    usuario = get_object_or_404(usuarios_visiveis(), pk=pk)
    padrao = reverse("usuario_editar", args=[pk])
    if usuario.pk == request.user.pk:
        messages.error(request, "Você não pode alterar os seus próprios perfis de acesso.")
        return _voltar(request, padrao)
    form = AdicionarPerfilForm(request.POST, usuario_logado=request.user, usuario=usuario)
    if form.is_valid():
        form.salvar(usuario)
        messages.success(request, "Perfil de acesso adicionado.")
    else:
        erros = [e for lista in form.errors.values() for e in lista]
        messages.error(request, " ".join(erros))
    return _voltar(request, padrao)


@administrador_requerido
@require_POST
def usuario_acesso_remover(request, pk):
    usuario = get_object_or_404(usuarios_visiveis(), pk=pk)
    padrao = reverse("usuario_editar", args=[pk])
    if usuario.pk == request.user.pk:
        messages.error(request, "Você não pode alterar os seus próprios perfis de acesso.")
        return _voltar(request, padrao)
    ids = request.POST.getlist("acessos")
    # Só remove acessos de empresas em que quem está logado pode configurar
    removidos, _ = usuario.acessos.filter(
        pk__in=ids, empresa__in=empresas_que_administra(request.user)
    ).delete()
    if removidos:
        messages.success(request, f"{removidos} perfil(is) de acesso removido(s).")
    else:
        messages.warning(request, "Nenhum perfil selecionado.")
    return _voltar(request, padrao)


# ---------- Cadastro de perfis de acesso ----------

class PerfilListView(AdministradorMixin, OrdenacaoMixin, ListView):
    template_name = "perfis/lista.html"
    context_object_name = "perfis"
    ordenacoes = {"codigo": "pk", "nome": "nome"}  # só Código e nome têm seta

    def get_queryset(self):
        return self.ordenar(
            Perfil.objects.annotate(total_usuarios=Count("acessos__usuario", distinct=True))
        )


class PerfilFormMixin(AdministradorMixin):
    model = Perfil
    form_class = PerfilForm
    template_name = "perfis/form.html"

    def get_success_url(self):
        return reverse("perfil_editar", args=[self.object.pk])  # continua no cadastro


class PerfilCriarView(PerfilFormMixin, CreateView):
    extra_context = {"titulo": "Novo perfil de acesso"}

    def form_valid(self, form):
        messages.success(self.request, "Perfil de acesso cadastrado.")
        return super().form_valid(form)


class PerfilEditarView(PerfilFormMixin, UpdateView):
    extra_context = {"titulo": "Editar perfil de acesso"}

    def form_valid(self, form):
        messages.success(self.request, "Perfil de acesso atualizado.")
        return super().form_valid(form)


@administrador_requerido
@require_POST
def perfil_excluir(request, pk):
    perfil = get_object_or_404(Perfil, pk=pk)
    try:
        perfil.delete()
    except ProtectedError:
        messages.error(
            request,
            f"O perfil {perfil} está sendo usado por usuários. Tire o perfil deles antes de excluir.",
        )
        return redirect("perfil_editar", pk=pk)
    messages.success(request, f"Perfil {perfil} excluído.")
    return redirect("perfil_lista")


@administrador_requerido
@require_POST
def usuario_excluir_selecionados(request):
    def impedimento(usuario):
        return "é o seu próprio usuário" if usuario.pk == request.user.pk else None

    excluir_selecionados(request, usuarios_visiveis(), singular="usuário", plural="usuários",
                         impedimento=impedimento)
    return redirect("usuario_lista")


@administrador_requerido
@require_POST
def perfil_excluir_selecionados(request):
    def impedimento(perfil):
        total = perfil.acessos.values("usuario").distinct().count()
        return f"em uso por {total} usuário{'s' if total > 1 else ''}" if total else None

    excluir_selecionados(request, Perfil.objects.all(), singular="perfil de acesso", plural="perfis de acesso",
                         impedimento=impedimento)
    return redirect("perfil_lista")
