from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from contas.permissions import (
    AdministradorMixin,
    MasterMixin,
    administrador_requerido,
    master_requerido,
)
from core.listas import FiltroSituacaoMixin, OrdenacaoMixin, excluir_selecionados

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
    ordenacoes = {"codigo": "pk", "unidade": "unidade", "empresa": ["nome_fantasia", "razao_social"]}  # só Código e nome têm seta
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
    extra_context = {"titulo": "Nova empresa"}

    def get_success_url(self):
        return reverse("empresa_editar", args=[self.object.pk])  # continua no cadastro

    def form_valid(self, form):
        messages.success(self.request, "Empresa cadastrada com sucesso.")
        return super().form_valid(form)


class EmpresaEditarView(AdministradorMixin, UpdateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "empresas/form.html"
    extra_context = {"titulo": "Editar empresa"}

    def get_success_url(self):
        return reverse("empresa_editar", args=[self.object.pk])  # continua no cadastro

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        # Sem registros ligados, o "Excluir" pede só a confirmação; com registros, abre a página que explica
        if self.request.user.eh_master:
            contexto["impedimentos_exclusao"] = self.object.vinculos_que_impedem_exclusao()
        from .models import CertificadoDigital
        contexto["certificado"] = CertificadoDigital.objects.filter(empresa=self.object).first()
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


@master_requerido
@require_POST
def empresa_excluir_selecionados(request):
    def impedimento(empresa):
        vinculos = empresa.vinculos_que_impedem_exclusao()
        return "já tem " + ", ".join(vinculos) if vinculos else None

    excluir_selecionados(request, Empresa.objects.all(), singular="empresa", plural="empresas",
                         artigo="a", impedimento=impedimento)
    return redirect("empresa_lista")


# ---------- Certificado digital (aba Fiscal) ----------

def _voltar_fiscal(pk):
    return redirect(reverse("empresa_editar", args=[pk]) + "#fiscal")


@administrador_requerido
@require_POST
def empresa_certificado_enviar(request, pk):
    from .certificado import CertificadoInvalido, cifrar, ler_certificado
    from .models import CertificadoDigital

    empresa = get_object_or_404(Empresa, pk=pk)
    arquivo = request.FILES.get("certificado")
    senha = request.POST.get("senha", "")
    if not arquivo or not senha:
        messages.error(request, "Escolha o arquivo do certificado (.pfx ou .p12) e informe a senha.")
        return _voltar_fiscal(pk)
    if not arquivo.name.lower().endswith((".pfx", ".p12")):
        messages.error(request, "O certificado A1 é um arquivo .pfx ou .p12.")
        return _voltar_fiscal(pk)
    conteudo = arquivo.read()
    try:
        dados = ler_certificado(conteudo, senha)
    except CertificadoInvalido as erro:
        messages.error(request, str(erro))
        return _voltar_fiscal(pk)

    from django.utils import timezone
    if dados["validade"] <= timezone.now():
        messages.error(request, f"Este certificado venceu em {timezone.localtime(dados['validade']):%d/%m/%Y}.")
        return _voltar_fiscal(pk)
    # O certificado tem que ser da empresa (a filial pode usar o da matriz: mesmo CNPJ base)
    doc_empresa, doc_cert = empresa.documento, dados["documento"]
    if doc_cert and doc_empresa:
        mesma = doc_cert[:8] == doc_empresa[:8] if len(doc_empresa) == 14 and len(doc_cert) == 14 else doc_cert == doc_empresa
        if not mesma:
            messages.error(request, f"O certificado é de outro CPF/CNPJ ({doc_cert}), não de {empresa.nome_exibicao}.")
            return _voltar_fiscal(pk)

    CertificadoDigital.objects.update_or_create(empresa=empresa, defaults={
        "descricao": dados["titular"][:120],  # a descrição é o nome que vem no certificado
        "nome_arquivo": arquivo.name[:150],
        "arquivo_cifrado": cifrar(conteudo), "senha_cifrada": cifrar(senha.encode()),
        "titular": dados["titular"], "documento": doc_cert,
        "emitido_em": dados["emitido_em"], "validade": dados["validade"], "enviado_por": request.user,
    })
    messages.success(request, f"Certificado de {dados['titular']} adicionado. Vale até "
                              f"{timezone.localtime(dados['validade']):%d/%m/%Y}.")
    return _voltar_fiscal(pk)


@administrador_requerido
@require_POST
def empresa_certificado_excluir(request, pk):
    empresa = get_object_or_404(Empresa, pk=pk)
    from .models import CertificadoDigital
    CertificadoDigital.objects.filter(empresa=empresa).delete()
    messages.success(request, "Certificado digital excluído.")
    return _voltar_fiscal(pk)
