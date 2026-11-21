from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from contas.permissions import administrador_requerido
from core.listas import FiltroSituacaoMixin, OrdenacaoMixin, excluir_selecionados
from empresas.templatetags.formatos import moeda
from empresas.validators import limpar_documento

from .financeiro import extrato_credito, periodo_padrao, resumo_financeiro
from .forms import (
    ClienteForm,
    ContatoClienteForm,
    CreditoClienteForm,
    EnderecoClienteForm,
    LancarCreditoForm,
)
from .models import Cliente, ContatoCliente, MovimentoCredito


class ClienteListView(LoginRequiredMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    paginate_by = 30
    template_name = "clientes/lista.html"
    context_object_name = "clientes"
    ordenacoes = {"codigo": "pk", "nome": ["nome_fantasia", "razao_social"]}  # só Código e nome têm seta

    def get_queryset(self):
        qs = self.filtrar_situacao(
            Cliente.objects.select_related("municipio", "tipo_cliente", "atendente")
        )
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            filtro = Q(razao_social__icontains=self.q) | Q(nome_fantasia__icontains=self.q)
            documento = limpar_documento(self.q)
            if documento:
                filtro |= Q(documento__icontains=documento)
            qs = qs.filter(filtro)
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto


def url_aba_enderecos(cliente):
    return reverse("cliente_editar", args=[cliente.pk]) + "#enderecos"


def _dados_enderecos(cliente):
    """Endereços em JSON para a janela de edição já abrir preenchida."""
    return [
        {
            "id": e.pk, "tipo": e.tipo, "cep": e.cep, "numero": e.numero, "logradouro": e.logradouro,
            "ponto_referencia": e.ponto_referencia, "bairro": e.bairro, "complemento": e.complemento,
            "municipio": e.municipio_id, "municipio_nome": e.municipio.nome, "uf": e.municipio.uf,
        }
        for e in cliente.enderecos.select_related("municipio")
    ]


def _pagina(request, cliente, form=None, endereco_form=None, endereco_acao=None,
            contato_form=None, contato_acao=None):
    """Desenha a tela do cliente (todas as abas)."""
    contexto = {
        "form": form or ClienteForm(
            instance=cliente, funcionario_logado=getattr(request.user, "funcionario", None)
        ),
        "object": cliente,
        "titulo": cliente.nome_exibicao if cliente else "Novo cliente",
    }
    if cliente:
        contexto.update(
            enderecos=cliente.enderecos.select_related("municipio"),
            enderecos_dados=_dados_enderecos(cliente),
            endereco_form=endereco_form or EnderecoClienteForm(),
            # Com erro na janela, a página volta com ela aberta
            endereco_acao=endereco_acao or reverse("cliente_endereco_novo", args=[cliente.pk]),
            abrir_endereco=endereco_form is not None,
            financeiro=resumo_financeiro(cliente),
            contatos=cliente.contatos.all(),
            contatos_dados=[
                {"id": c.pk, "tipo": c.tipo, "nome": c.nome, "ddd": c.ddd, "telefone": c.telefone, "email": c.email}
                for c in cliente.contatos.all()
            ],
            contato_form=contato_form or ContatoClienteForm(),
            contato_acao=contato_acao or reverse("cliente_contato_novo", args=[cliente.pk]),
            abrir_contato=contato_form is not None,
        )
    return render(request, "clientes/form.html", contexto)


@login_required
def cliente_form(request, pk=None):
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    if request.method != "POST":
        return _pagina(request, cliente)
    form = ClienteForm(
        request.POST, instance=cliente, funcionario_logado=getattr(request.user, "funcionario", None)
    )
    if not form.is_valid():
        return _pagina(request, cliente, form=form)
    with transaction.atomic():
        novo = form.instance.pk is None
        if novo:
            form.instance.cadastrado_por = request.user
        cliente = form.save()
    messages.success(request, f"Cliente {cliente} {'cadastrado' if novo else 'atualizado'} com sucesso.")
    return redirect("cliente_editar", pk=cliente.pk)  # continua no cadastro


# ---------- Aba "Outros endereços" ----------

@login_required
@require_POST
def cliente_endereco_salvar(request, pk, endereco_pk=None):
    cliente = get_object_or_404(Cliente, pk=pk)
    endereco = get_object_or_404(cliente.enderecos, pk=endereco_pk) if endereco_pk else None
    form = EnderecoClienteForm(request.POST, instance=endereco)
    if not form.is_valid():
        acao = request.path
        return _pagina(request, cliente, endereco_form=form, endereco_acao=acao)
    form.instance.cliente = cliente
    form.save()
    messages.success(request, "Endereço atualizado." if endereco else "Endereço adicionado.")
    return redirect(url_aba_enderecos(cliente))


@login_required
@require_POST
def cliente_endereco_excluir(request, pk, endereco_pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    get_object_or_404(cliente.enderecos, pk=endereco_pk).delete()
    messages.success(request, "Endereço excluído.")
    return redirect(url_aba_enderecos(cliente))


# ---------- Aba "Contatos" ----------

def url_aba_contatos(cliente):
    return reverse("cliente_editar", args=[cliente.pk]) + "#contatos"


@login_required
@require_POST
def cliente_contato_salvar(request, pk, contato_pk=None):
    cliente = get_object_or_404(Cliente, pk=pk)
    contato = get_object_or_404(cliente.contatos, pk=contato_pk) if contato_pk else None
    form = ContatoClienteForm(request.POST, instance=contato)
    if not form.is_valid():
        return _pagina(request, cliente, contato_form=form, contato_acao=request.path)
    with transaction.atomic():
        form.instance.cliente = cliente
        contato = form.save()
        mensagem = "Contato atualizado." if contato_pk else "Contato adicionado."
        # Só um contato principal: o anterior passa para "Outros"
        if contato.eh_principal:
            anteriores = cliente.contatos.filter(tipo=ContatoCliente.Tipo.PRINCIPAL).exclude(pk=contato.pk)
            nomes = list(anteriores.values_list("nome", flat=True))
            if nomes:
                anteriores.update(tipo=ContatoCliente.Tipo.OUTROS)
                mensagem += f" Agora ele é o principal; {', '.join(nomes)} passou para Outros."
    messages.success(request, mensagem)
    return redirect(url_aba_contatos(cliente))


@login_required
@require_POST
def cliente_contato_excluir(request, pk, contato_pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    get_object_or_404(cliente.contatos, pk=contato_pk).delete()
    messages.success(request, "Contato excluído.")
    return redirect(url_aba_contatos(cliente))


# ---------- Aba "Financeiro": janela "Gerenciar crédito" (só quem acessa as configurações) ----------

def _data(texto, padrao):
    try:
        return date.fromisoformat(texto) if texto else padrao
    except ValueError:
        return padrao


def _painel_credito(request, cliente, limite_form=None, lancar_form=None, aviso=None, alterado=False):
    """Conteúdo da janela: indicadores, extrato do período, lançar crédito e limite."""
    de_padrao, ate_padrao = periodo_padrao()
    de = _data(request.GET.get("de"), de_padrao)
    ate = _data(request.GET.get("ate"), ate_padrao)
    if de > ate:
        de, ate = ate, de
    resposta = render(request, "clientes/_credito_painel.html", {
        "object": cliente,
        "financeiro": resumo_financeiro(cliente),
        "extrato": extrato_credito(cliente, de, ate),
        "limite_form": limite_form or CreditoClienteForm(instance=cliente),
        "lancar_form": lancar_form or LancarCreditoForm(),
        "aviso": aviso,
    })
    if alterado:
        resposta["HX-Trigger"] = "credito-alterado"  # ao fechar a janela, a aba Financeiro se atualiza
    return resposta


@administrador_requerido
def cliente_credito_painel(request, pk):
    return _painel_credito(request, get_object_or_404(Cliente, pk=pk))


@administrador_requerido
@require_POST
def cliente_credito_lancar(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = LancarCreditoForm(request.POST)
    if not form.is_valid():
        return _painel_credito(request, cliente, lancar_form=form)
    valor = form.cleaned_data["valor"]
    pedido = form.cleaned_data["pedido"].strip()
    MovimentoCredito.objects.create(
        cliente=cliente, tipo=MovimentoCredito.Tipo.CREDITO, valor=valor, pedido=pedido,
        descricao="Crédito lançado manualmente", usuario=request.user,
    )
    return _painel_credito(request, cliente, aviso=f"Crédito de {moeda(valor)} lançado.", alterado=True)


@administrador_requerido
@require_POST
def cliente_credito(request, pk):
    """Limite de crédito e bloqueio."""
    cliente = get_object_or_404(Cliente, pk=pk)
    form = CreditoClienteForm(request.POST, instance=cliente)
    if not form.is_valid():
        return _painel_credito(request, cliente, limite_form=form)
    form.save()
    return _painel_credito(request, cliente, aviso="Limite de crédito atualizado.", alterado=True)


@login_required
@require_POST
def cliente_excluir(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    nome = str(cliente)
    try:
        cliente.delete()
    except ProtectedError:
        messages.error(request, f"{nome} já tem registros no sistema. Desative o cliente em vez de excluir.")
        return redirect("cliente_editar", pk=pk)
    messages.success(request, f"Cliente {nome} excluído.")
    return redirect("cliente_lista")


@login_required
@require_POST
def cliente_excluir_selecionados(request):
    excluir_selecionados(request, Cliente.objects.all(), singular="cliente", plural="clientes")
    return redirect("cliente_lista")
