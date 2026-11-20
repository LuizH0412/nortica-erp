from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from contas.permissions import AdministradorMixin, administrador_requerido
from contas.views import contexto_acessos
from core.listas import FiltroSituacaoMixin, OrdenacaoMixin

from .forms import FuncionarioForm, UsuarioFuncionarioForm
from .models import Funcionario


class FuncionarioListView(AdministradorMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    ordenacoes = {
        "nome": "nome", "funcao": "funcao__nome", "setor": "setor__nome",
        "cpf": "cpf", "acesso": "usuario__email", "situacao": "ativo",
    }
    paginate_by = 30
    template_name = "funcionarios/lista.html"
    context_object_name = "funcionarios"

    def get_queryset(self):
        qs = self.filtrar_situacao(Funcionario.objects.select_related("funcao", "setor", "usuario"))
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            qs = qs.filter(
                Q(nome__icontains=self.q)
                | Q(cpf__icontains=self.q)
                | Q(usuario__email__icontains=self.q)
            )
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto


def url_aba_usuario(funcionario):
    return reverse("funcionario_editar", args=[funcionario.pk]) + "#usuario"


def _pagina(request, funcionario, form=None, usuario_form=None):
    """Desenha a tela do funcionário (as duas abas)."""
    usuario = funcionario.usuario if funcionario else None
    contexto = {
        "form": form or FuncionarioForm(instance=funcionario, usuario_logado=request.user),
        "object": funcionario,
        "titulo": f"Funcionário · {funcionario.nome}" if funcionario else "Novo funcionário",
    }
    if funcionario:
        contexto["usuario_form"] = usuario_form or UsuarioFuncionarioForm(usuario=usuario)
        contexto["eh_o_proprio"] = bool(usuario and usuario.pk == request.user.pk)
        if usuario:
            contexto.update(contexto_acessos(request, usuario, url_aba_usuario(funcionario)))
    return render(request, "funcionarios/form.html", contexto)


@administrador_requerido
def funcionario_form(request, pk=None):
    """Aba "Dados cadastrais": cadastro e edição do funcionário."""
    funcionario = get_object_or_404(Funcionario.objects.select_related("usuario"), pk=pk) if pk else None
    if request.method != "POST":
        return _pagina(request, funcionario)

    form = FuncionarioForm(request.POST, instance=funcionario, usuario_logado=request.user)
    if not form.is_valid():
        return _pagina(request, funcionario, form=form)
    with transaction.atomic():
        funcionario = form.save()
        funcionario.sincronizar_usuario()
    if pk:
        messages.success(request, "Funcionário atualizado com sucesso.")
        return redirect("funcionario_lista")
    messages.success(request, "Funcionário cadastrado. Se ele for usar o sistema, configure o usuário.")
    return redirect(url_aba_usuario(funcionario))


@administrador_requerido
@require_POST
def funcionario_usuario(request, pk):
    """Aba "Usuário": cria ou atualiza o login (e-mail e senha) do funcionário."""
    funcionario = get_object_or_404(Funcionario.objects.select_related("usuario"), pk=pk)
    form = UsuarioFuncionarioForm(request.POST, usuario=funcionario.usuario)
    if not form.is_valid():
        return _pagina(request, funcionario, usuario_form=form)
    novo = funcionario.usuario is None
    with transaction.atomic():
        form.salvar(funcionario)
    if novo:
        messages.success(request, "Usuário criado. Agora adicione os perfis de acesso dele.")
    else:
        messages.success(request, "Usuário atualizado.")
    return redirect(url_aba_usuario(funcionario))


@administrador_requerido
@require_POST
def funcionario_desvincular(request, pk):
    """Tira o usuário do funcionário: o login fica bloqueado e sem perfis."""
    funcionario = get_object_or_404(Funcionario.objects.select_related("usuario"), pk=pk)
    usuario = funcionario.usuario
    if usuario is None:
        return redirect(url_aba_usuario(funcionario))
    if usuario.pk == request.user.pk:
        messages.error(request, "Você não pode desvincular o seu próprio usuário.")
        return redirect(url_aba_usuario(funcionario))
    with transaction.atomic():
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        usuario.acessos.all().delete()
        funcionario.usuario = None
        funcionario.save(update_fields=["usuario"])
    messages.success(
        request, f"Usuário {usuario.email} desvinculado e bloqueado. Ele continua na lista de usuários."
    )
    return redirect(url_aba_usuario(funcionario))


@administrador_requerido
def funcionario_excluir(request, pk):
    funcionario = get_object_or_404(Funcionario.objects.select_related("usuario"), pk=pk)
    if funcionario.usuario_id and funcionario.usuario_id == request.user.pk:
        messages.error(request, "Você não pode excluir o seu próprio cadastro.")
        return redirect("funcionario_editar", pk=pk)
    if request.method == "POST":
        nome, usuario = funcionario.nome, funcionario.usuario
        with transaction.atomic():
            funcionario.delete()
            if usuario:
                usuario.delete()  # o acesso ao sistema pertence ao funcionário
        messages.success(request, f"Funcionário {nome} excluído.")
        return redirect("funcionario_lista")
    return render(request, "funcionarios/excluir.html", {"funcionario": funcionario})
