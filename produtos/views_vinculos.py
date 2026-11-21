"""Cadastros › Produtos › Vínculos fiscais: lista, cadastro, configurações, tributação, NCMs e produtos."""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from core.listas import FiltroSituacaoMixin, OrdenacaoMixin, excluir_selecionados
from empresas.models import Empresa
from fiscal.models import Ncm

from .forms_vinculos import ConfiguracaoFiscalForm, TributacaoFiscalForm, VinculoFiscalForm
from .models import ConfiguracaoFiscal, DetalheFiscal, Produto, TributacaoFiscal, VinculoFiscal, VinculoNcm


def _voltar(vinculo_pk, aba):
    return redirect(reverse("vinculo_editar", args=[vinculo_pk]) + f"#{aba}")


# ---------- Lista ----------

class VinculoListView(LoginRequiredMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    paginate_by = 30
    template_name = "produtos/vinculos_lista.html"
    context_object_name = "vinculos"
    ordenacoes = {"codigo": "pk", "nome": "nome"}  # só Código e descrição têm seta

    def get_queryset(self):
        qs = self.filtrar_situacao(VinculoFiscal.objects.annotate(
            total_produtos=Count("detalhes__produto", distinct=True),
            total_configuracoes=Count("configuracoes", distinct=True),
            total_ncms=Count("ncms", distinct=True),
        ))
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            filtro = Q(nome__icontains=self.q)
            if self.q.isdigit():
                filtro |= Q(pk=int(self.q)) | Q(ncms__ncm__startswith=self.q)
            qs = qs.filter(filtro).distinct()
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto


@login_required
@require_POST
def vinculo_padrao(request, pk):
    """Interruptor "Vínculo padrão" da lista: liga neste (desliga nos outros) ou desliga."""
    vinculo = get_object_or_404(VinculoFiscal, pk=pk)
    if vinculo.padrao:
        vinculo.padrao = False
        vinculo.save(update_fields=["padrao"])
        messages.success(request, f"{vinculo} deixou de ser o vínculo padrão.")
    elif not vinculo.ativo:
        messages.error(request, f"{vinculo} está desativado e não pode ser o padrão.")
    else:
        with transaction.atomic():
            VinculoFiscal.objects.filter(padrao=True).update(padrao=False)
            vinculo.padrao = True
            vinculo.save(update_fields=["padrao"])
        messages.success(request, f"{vinculo} agora é o vínculo padrão.")
    return redirect(request.POST.get("voltar") or "produto_vinculos_fiscais")


# ---------- Cadastro ----------

@login_required
def vinculo_form(request, pk=None):
    vinculo = get_object_or_404(VinculoFiscal, pk=pk) if pk else None
    form = VinculoFiscalForm(request.POST or None, instance=vinculo)
    if request.method == "POST" and form.is_valid():
        vinculo = form.save()
        messages.success(request, f"Vínculo fiscal {vinculo} {'atualizado' if pk else 'cadastrado'} com sucesso.")
        if not pk:  # novo: já abre nas configurações para preencher a tributação
            return _voltar(vinculo.pk, "configuracoes")
        return redirect("vinculo_editar", pk=vinculo.pk)  # continua no cadastro

    contexto = {"form": form, "object": vinculo, "titulo": vinculo.nome if vinculo else "Novo vínculo fiscal"}
    if vinculo:
        empresa_atual = getattr(request, "empresa_atual", None)
        empresas = Empresa.objects.filter(ativa=True).order_by("unidade")
        filtro_empresa = request.GET.get("empresa", "")
        empresa_filtro = empresas.filter(pk=filtro_empresa).first() if filtro_empresa.isdigit() else empresa_atual
        detalhes = (DetalheFiscal.objects.filter(vinculo=vinculo).select_related("produto", "empresa")
                    .order_by("empresa__unidade", "produto__descricao"))
        if empresa_filtro:
            detalhes = detalhes.filter(empresa=empresa_filtro)
        ncms = list(vinculo.ncms.all())
        descricoes = dict(Ncm.objects.filter(pk__in=[n.ncm for n in ncms]).values_list("codigo", "descricao"))
        configuracoes = list(vinculo.configuracoes.prefetch_related("tributacoes"))
        for c in configuracoes:  # [(operação, tributação ou None)] para os cartões de entrada/saída
            por_operacao = {t.operacao: t for t in c.tributacoes.all()}
            c.itens = [(op, por_operacao.get(op)) for op in c.operacoes]
        contexto.update(
            configuracoes=configuracoes,
            config_form=ConfiguracaoFiscalForm(vinculo=vinculo, empresa=empresa_atual),
            ncms=[(n, descricoes.get(n.ncm, "")) for n in ncms],
            produtos_vinculados=detalhes[:200],
            total_produtos=DetalheFiscal.objects.filter(vinculo=vinculo).values("produto").distinct().count(),
            empresas=empresas, empresa_filtro=empresa_filtro,
        )
    return render(request, "produtos/vinculo_form.html", contexto)


def _impedimento_vinculo(vinculo):
    total = DetalheFiscal.objects.filter(vinculo=vinculo).values("produto").distinct().count()
    return f"tem {total} produto{'s' if total > 1 else ''}" if total else None


@login_required
@require_POST
def vinculo_excluir(request, pk):
    vinculo = get_object_or_404(VinculoFiscal, pk=pk)
    motivo = _impedimento_vinculo(vinculo)
    if motivo:
        messages.error(request, f"O vínculo {vinculo} {motivo} e não pode ser excluído. Desative-o em vez de excluir.")
        return redirect("vinculo_editar", pk=pk)
    nome = str(vinculo)
    vinculo.delete()  # configurações, tributações e NCMs vão junto
    messages.success(request, f"Vínculo fiscal {nome} excluído.")
    return redirect("produto_vinculos_fiscais")


@login_required
@require_POST
def vinculo_excluir_selecionados(request):
    excluir_selecionados(request, VinculoFiscal.objects.all(), singular="vínculo fiscal", plural="vínculos fiscais",
                         impedimento=_impedimento_vinculo)
    return redirect("produto_vinculos_fiscais")


@login_required
@require_POST
def vinculo_clonar(request, pk):
    """Cópia do vínculo com as configurações e a tributação (sem os produtos, as NCMs e o "padrão")."""
    origem = get_object_or_404(VinculoFiscal, pk=pk)
    nome, n = f"{origem.nome} (cópia)", 2
    while VinculoFiscal.objects.filter(nome__iexact=nome).exists():
        nome, n = f"{origem.nome} (cópia {n})", n + 1
    campos = TributacaoFiscal.campos_copiaveis()
    with transaction.atomic():
        copia = VinculoFiscal.objects.create(nome=nome[:100], tipo_item=origem.tipo_item, ativo=origem.ativo)
        for config in origem.configuracoes.prefetch_related("tributacoes"):
            nova = ConfiguracaoFiscal.objects.create(
                vinculo=copia, documento=config.documento, uf_origem=config.uf_origem,
                uf_destino=config.uf_destino, regime=config.regime,
            )
            for t in config.tributacoes.all():
                TributacaoFiscal.objects.create(configuracao=nova, operacao=t.operacao,
                                                **{c: getattr(t, c) for c in campos})
    messages.success(request, f"Vínculo copiado como “{copia}”. Revise a descrição e salve.")
    return redirect("vinculo_editar", pk=copia.pk)


# ---------- Configurações (documento + UFs + regime) ----------

def _erros(form):
    return " ".join(e for lista in form.errors.values() for e in lista)


@login_required
@require_POST
def configuracao_adicionar(request, pk):
    vinculo = get_object_or_404(VinculoFiscal, pk=pk)
    form = ConfiguracaoFiscalForm(request.POST, vinculo=vinculo)
    if form.is_valid():
        config = form.save()
        messages.success(request, f"Configuração {config} adicionada. Agora preencha a tributação.")
    else:
        messages.error(request, _erros(form))
    return _voltar(pk, "configuracoes")


@login_required
@require_POST
def configuracao_clonar(request, pk, config_pk):
    """Copia a tributação para uma configuração nova (outro documento, UF ou regime)."""
    origem = get_object_or_404(ConfiguracaoFiscal, pk=config_pk, vinculo_id=pk)
    form = ConfiguracaoFiscalForm(request.POST, vinculo=origem.vinculo)
    if not form.is_valid():
        messages.error(request, _erros(form))
        return _voltar(pk, "configuracoes")
    campos = TributacaoFiscal.campos_copiaveis()
    with transaction.atomic():
        nova = form.save()
        for t in origem.tributacoes.all():
            if t.operacao in nova.operacoes:  # NFC-e não tem entrada
                TributacaoFiscal.objects.create(configuracao=nova, operacao=t.operacao,
                                                **{c: getattr(t, c) for c in campos})
    messages.success(request, f"Configuração copiada para {nova}. Confira o CFOP e o CST, que podem mudar.")
    return _voltar(pk, "configuracoes")


@login_required
@require_POST
def configuracao_excluir(request, pk, config_pk):
    config = get_object_or_404(ConfiguracaoFiscal, pk=config_pk, vinculo_id=pk)
    nome = str(config)
    config.delete()
    messages.success(request, f"Configuração {nome} excluída.")
    return _voltar(pk, "configuracoes")


@login_required
def tributacao_form(request, pk, config_pk, operacao):
    config = get_object_or_404(ConfiguracaoFiscal.objects.select_related("vinculo"), pk=config_pk, vinculo_id=pk)
    if operacao not in config.operacoes:
        raise Http404
    tributacao = config.tributacao(operacao) or TributacaoFiscal(configuracao=config, operacao=operacao)
    form = TributacaoFiscalForm(request.POST or None, instance=tributacao, configuracao=config, operacao=operacao)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Tributação de {'entrada' if operacao == 'entrada' else 'saída'} salva com sucesso.")
        return redirect("vinculo_tributacao", pk=pk, config_pk=config_pk, operacao=operacao)  # continua na tela
    return render(request, "produtos/vinculo_tributacao.html", {
        "vinculo": config.vinculo, "config": config, "operacao": operacao, "form": form, "tributacao": tributacao,
        "titulo": f"{config.vinculo} · {'Entrada' if operacao == 'entrada' else 'Saída'}",
    })


# ---------- NCMs vinculadas ----------

@login_required
@require_POST
def vinculo_ncm_adicionar(request, pk):
    vinculo = get_object_or_404(VinculoFiscal, pk=pk)
    ncm = re.sub(r"\D", "", request.POST.get("ncm", ""))
    outro = VinculoNcm.objects.filter(ncm=ncm).select_related("vinculo").first()
    if len(ncm) != 8:
        messages.error(request, "Escolha a NCM.")
    elif Ncm.objects.exists() and not Ncm.objects.filter(pk=ncm).exists():
        messages.error(request, "NCM não encontrada na tabela vigente.")
    elif outro:
        messages.error(request, f"A NCM {ncm} já está no vínculo {outro.vinculo}." if outro.vinculo_id != vinculo.pk
                       else f"A NCM {ncm} já está neste vínculo.")
    else:
        VinculoNcm.objects.create(vinculo=vinculo, ncm=ncm)
        messages.success(request, f"NCM {ncm} vinculada. Produtos dessa NCM sem vínculo escolhido passam a usar {vinculo}.")
    return _voltar(pk, "ncms")


@login_required
@require_POST
def vinculo_ncm_remover(request, pk, ncm_pk):
    item = get_object_or_404(VinculoNcm, pk=ncm_pk, vinculo_id=pk)
    item.delete()
    messages.success(request, f"NCM {item.ncm} desvinculada.")
    return _voltar(pk, "ncms")


# ---------- Produtos vinculados ----------

@login_required
@require_POST
def vinculo_produto_adicionar(request, pk):
    vinculo = get_object_or_404(VinculoFiscal, pk=pk)
    produto = Produto.objects.filter(pk=request.POST.get("produto") or 0).first()
    empresa = Empresa.objects.filter(pk=request.POST.get("empresa") or 0, ativa=True).first()
    if not produto or not empresa:
        messages.error(request, "Escolha o produto e a empresa.")
    elif not produto.disponivel_na(empresa):
        messages.error(request, f"{produto} está oculto em {empresa.unidade} (aba Empresa do produto).")
    else:
        detalhe, _ = DetalheFiscal.objects.get_or_create(produto=produto, empresa=empresa)
        anterior = detalhe.vinculo
        detalhe.vinculo = vinculo
        detalhe.save()
        aviso = f" (antes estava em {anterior})" if anterior and anterior != vinculo else ""
        messages.success(request, f"{produto.codigo} · {produto} vinculado em {empresa.unidade}{aviso}.")
    url = reverse("vinculo_editar", args=[pk])
    if empresa:
        url += f"?empresa={empresa.pk}"
    return redirect(url + "#produtos")


@login_required
@require_POST
def vinculo_produto_remover(request, pk, detalhe_pk):
    detalhe = get_object_or_404(DetalheFiscal.objects.select_related("produto", "empresa"), pk=detalhe_pk, vinculo_id=pk)
    detalhe.vinculo = None
    detalhe.save()
    messages.success(request, f"{detalhe.produto} saiu do vínculo em {detalhe.empresa.unidade}.")
    return redirect(reverse("vinculo_editar", args=[pk]) + f"?empresa={detalhe.empresa_id}#produtos")


@login_required
def produto_busca(request):
    """Produtos para o campo digitável (código, descrição, código interno ou de barras)."""
    termo = request.GET.get("q", "").strip()
    qs = Produto.objects.filter(ativo=True)
    if termo:
        filtro = Q(descricao__icontains=termo) | Q(codigo_interno__iexact=termo) | Q(codigo_barras=termo)
        if termo.isdigit():
            filtro |= Q(pk=int(termo))
        qs = qs.filter(filtro)
    itens = list(qs.order_by("descricao")[:51])

    def nome(p):
        partes = [p.codigo, p.descricao] + ([p.codigo_barras] if p.codigo_barras else [])
        return " · ".join(partes)
    return JsonResponse({"itens": [{"id": p.pk, "nome": nome(p), "ativo": True} for p in itens[:50]], "mais": len(itens) > 50})
