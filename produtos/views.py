from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, ProtectedError, Q
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from contas.permissions import administrador_requerido
from empresas.models import Empresa
from core.listas import FiltroSituacaoMixin, OrdenacaoMixin, excluir_selecionados
from empresas.templatetags.formatos import quantidade

from .estoque import ETAPAS, com_saldo, definir_minimo, estoque_minimo, movimentar, organizar, saldo
from .forms import AjusteRapidoForm, DetalheFiscalForm, EstoqueMinimoForm, GrupoCompletoForm, ProdutoForm
from .models import DetalheFiscal, FotoProduto, Grupo, MovimentoEstoque, Produto


class ProdutoListView(LoginRequiredMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    paginate_by = 30
    template_name = "produtos/lista.html"
    context_object_name = "produtos"
    ordenacoes = {"codigo": "pk", "descricao": "descricao"}  # só Código e nome têm seta

    def get_queryset(self):
        qs = self.filtrar_situacao(Produto.objects.select_related("grupo", "subgrupo", "unidade"))
        empresa = getattr(self.request, "empresa_atual", None)
        qs = com_saldo(qs, empresa)
        # Aba "Empresa": produto oculto nesta empresa não aparece na lista dela
        if empresa is not None:
            qs = qs.exclude(empresas_ocultas=empresa)
        # Filtros: grupo e "só combos"
        self.grupo = self.request.GET.get("grupo", "")
        if self.grupo.isdigit():
            qs = qs.filter(grupo_id=int(self.grupo))
        self.so_combos = self.request.GET.get("combo") == "1"
        if self.so_combos:
            qs = qs.filter(combo=True)
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            filtro = (
                Q(descricao__icontains=self.q)
                | Q(codigo_interno__iexact=self.q)
                | Q(codigo_barras=self.q)
            )
            if self.q.isdigit():
                filtro |= Q(pk=int(self.q))  # pelo código do sistema (com ou sem zeros à esquerda)
            qs = qs.filter(filtro)
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            q=self.q, grupo_filtro=self.grupo, so_combos=self.so_combos,
            grupos=Grupo.objects.order_by("nome"),
            filtrando=bool(self.q or self.grupo or self.so_combos or self.so_desativados),
        )
        return contexto


# Na cópia, o que não pode repetir fica em branco
NAO_CLONAR = ("id", "codigo_interno", "codigo_barras", "codigo_barras_caixa")


@login_required
def produto_form(request, pk=None):
    produto = get_object_or_404(Produto, pk=pk) if pk else None
    initial = {}
    origem = None
    if produto is None and request.GET.get("clonar", "").isdigit():
        origem = Produto.objects.filter(pk=request.GET["clonar"]).first()
        if origem:
            initial = {k: v for k, v in model_to_dict(origem).items() if k not in NAO_CLONAR}
            initial["descricao"] = f"{origem.descricao} (cópia)"[:120]
            # A escolha de empresas é dado de cadastro: o clone vem com as mesmas marcadas
            ocultas = {e.pk for e in initial.pop("empresas_ocultas", [])}
            initial["empresas"] = list(Empresa.objects.filter(ativa=True).exclude(pk__in=ocultas).values_list("pk", flat=True))

    form = ProdutoForm(request.POST or None, instance=produto, initial=initial)
    if request.method == "POST" and form.is_valid():
        produto_salvo = form.save()
        clonar_de = request.POST.get("clonar_de", "")
        if not pk and clonar_de.isdigit():
            origem_post = Produto.objects.filter(pk=clonar_de).first()
            if origem_post:
                copiar_detalhes_fiscais(origem_post, produto_salvo)
        messages.success(
            request, f"Produto {produto_salvo.codigo} · {produto_salvo} {'atualizado' if pk else 'cadastrado'} com sucesso."
        )
        return redirect("produto_editar", pk=produto_salvo.pk)  # continua no cadastro
    contexto = {
        "form": form, "object": produto, "origem_clone": origem,
        "titulo": produto.descricao if produto else "Novo produto",
    }
    if produto:
        empresa = getattr(request, "empresa_atual", None)
        contexto.update(
            impedimento_exclusao=_impedimento_produto(produto),
            oculto_aqui=not produto.disponivel_na(empresa),
            empresas_fiscais=empresas_do_produto(produto),
            fotos=produto.fotos.all(),
            saldo=saldo(produto, empresa),
            minimo=estoque_minimo(produto, empresa),
            etapas_estoque=ETAPAS,
            rapido_form=AjusteRapidoForm(),
            minimo_form=EstoqueMinimoForm(initial={"estoque_minimo": estoque_minimo(produto, empresa)}),
            movimentos=produto.movimentos_estoque.filter(empresa=empresa).select_related("usuario")[:5],
        )
    # Aba "Detalhes fiscais": com uma empresa só, o formulário já vem aberto na própria aba
    if produto and len(contexto["empresas_fiscais"]) == 1:
        contexto.update(contexto_fiscal(produto, contexto["empresas_fiscais"][0][0]))
    return render(request, "produtos/form.html", contexto)


@administrador_requerido
@require_POST
def produto_estoque_organizar(request, pk):
    """Organizar estoque: confere tudo o que mexe no estoque do produto e corrige o saldo (JSON)."""
    produto = get_object_or_404(Produto, pk=pk)
    if not produto.controlar_estoque:
        return JsonResponse({"ok": False, "mensagem": "Este produto não controla estoque."}, status=400)
    r = organizar(produto)
    return JsonResponse({
        "ok": True,
        "etapas": r["etapas"],
        "correcoes": [
            {"empresa": c["empresa"], "antes": quantidade(c["antes"]), "depois": quantidade(c["depois"])}
            for c in r["correcoes"]
        ],
        "conferidas": [{"empresa": c["empresa"], "saldo": quantidade(c["saldo"])} for c in r["conferidas"]],
        "incoerentes": [
            {"data": timezone.localtime(m["data"]).strftime("%d/%m/%Y %H:%M"), "tipo": m["tipo"], "empresa": m["empresa"]}
            for m in r["incoerentes"]
        ],
        "unidade": str(produto.unidade),
    })


def _impedimento_produto(produto):
    """Motivo para não excluir (produto já movimentado/ligado a outros registros) ou None."""
    vinculos = produto.vinculos_que_impedem_exclusao()
    return f"tem {', '.join(vinculos)}" if vinculos else None


@login_required
@require_POST
def produto_excluir(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    nome = str(produto)
    motivo = _impedimento_produto(produto)
    if motivo:
        messages.error(
            request, f"O produto {produto.codigo} · {nome} {motivo} e não pode ser excluído. "
                     "Desative o produto em vez de excluir."
        )
        return redirect("produto_editar", pk=pk)
    try:
        produto.delete()
    except ProtectedError:  # rede de segurança: algo ligado ao produto que a checagem não pegou
        messages.error(request, f"O produto {nome} já tem registros no sistema e não pode ser excluído. "
                                "Desative o produto em vez de excluir.")
        return redirect("produto_editar", pk=pk)
    messages.success(request, f"Produto {nome} excluído.")
    return redirect("produto_lista")


@login_required
@require_POST
def produto_excluir_selecionados(request):
    excluir_selecionados(
        request, Produto.objects.all(), singular="produto", plural="produtos", impedimento=_impedimento_produto,
    )
    return redirect("produto_lista")


def _pode_mexer_no_estoque(request, produto):
    """Mensagem do motivo se não der para mexer no estoque agora (ou None)."""
    if getattr(request, "empresa_atual", None) is None:
        return "Escolha uma empresa para mexer no estoque."
    if not produto.controlar_estoque:
        return "Este produto não controla estoque."
    if not produto.disponivel_na(request.empresa_atual):
        return f"Este produto está oculto em {request.empresa_atual.unidade} (aba Empresa do cadastro)."
    return None


@administrador_requerido
@require_POST
def produto_estoque_rapido(request, pk):
    """Ajuste rápido: entrada (soma) ou saída (subtrai) na empresa atual."""
    produto = get_object_or_404(Produto, pk=pk)
    form = AjusteRapidoForm(request.POST)
    motivo = _pode_mexer_no_estoque(request, produto)
    if motivo:
        messages.error(request, motivo)
    elif not form.is_valid():
        messages.error(request, " ".join(e for lista in form.errors.values() for e in lista))
    else:
        entrada = form.cleaned_data["operacao"] == "entrada"
        mov = movimentar(
            produto, request.empresa_atual, form.quantidade_com_sinal,
            MovimentoEstoque.Tipo.ENTRADA if entrada else MovimentoEstoque.Tipo.SAIDA,
            usuario=request.user, motivo="Ajuste rápido", data=form.cleaned_data["data"],
        )
        messages.success(
            request, f"{'Entrada' if entrada else 'Saída'} de {quantidade(form.cleaned_data['quantidade'])} "
                     f"{produto.unidade}: estoque {quantidade(mov.saldo_anterior)} → {quantidade(mov.saldo_novo)}."
        )
    return redirect("produto_editar", pk=pk)


@administrador_requerido
@require_POST
def produto_estoque_minimo(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    form = EstoqueMinimoForm(request.POST)
    motivo = _pode_mexer_no_estoque(request, produto)
    if motivo:
        messages.error(request, motivo)
    elif not form.is_valid():
        messages.error(request, " ".join(e for lista in form.errors.values() for e in lista))
    else:
        valor = form.cleaned_data["estoque_minimo"] or 0
        definir_minimo(produto, request.empresa_atual, valor)
        messages.success(request, f"Estoque mínimo em {request.empresa_atual.unidade}: {quantidade(valor)} {produto.unidade}.")
    return redirect("produto_editar", pk=pk)


# ---------- Grupos (Cadastros › Produtos › Grupos) ----------

class GrupoListView(LoginRequiredMixin, FiltroSituacaoMixin, OrdenacaoMixin, ListView):
    paginate_by = 30
    template_name = "produtos/grupos_lista.html"
    context_object_name = "grupos"
    ordenacoes = {"codigo": "pk", "nome": "nome"}  # só Código e nome têm seta

    def get_queryset(self):
        qs = self.filtrar_situacao(Grupo.objects.annotate(total_subgrupos=Count("subgrupos")))
        self.q = self.request.GET.get("q", "").strip()
        if self.q:
            qs = qs.filter(Q(nome__icontains=self.q) | Q(subgrupos__nome__icontains=self.q)).distinct()
        return self.ordenar(qs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.q
        return contexto


@login_required
def grupo_form(request, pk=None):
    grupo = get_object_or_404(Grupo, pk=pk) if pk else None
    form = GrupoCompletoForm(request.POST or None, instance=grupo)
    if request.method == "POST" and form.is_valid():
        grupo = form.save()
        messages.success(request, f"Grupo {grupo} {'atualizado' if pk else 'cadastrado'} com sucesso.")
        return redirect("produto_grupo_editar", pk=grupo.pk)  # continua no cadastro
    return render(request, "produtos/grupo_form.html", {
        "form": form, "object": grupo, "titulo": grupo.nome if grupo else "Novo grupo",
        "subgrupos": grupo.subgrupos.annotate(total=Count("produtos")).order_by("-ativo", "nome") if grupo else [],
        "total_produtos": grupo.produtos.count() if grupo else 0,
    })


def _impedimento_grupo(grupo):
    total = grupo.produtos.count()
    return f"tem {total} produto{'s' if total > 1 else ''}" if total else None


@login_required
@require_POST
def grupo_excluir(request, pk):
    grupo = get_object_or_404(Grupo, pk=pk)
    motivo = _impedimento_grupo(grupo)
    if motivo:
        messages.error(request, f"O grupo {grupo} {motivo}. Desative o grupo em vez de excluir.")
        return redirect("produto_grupo_editar", pk=pk)
    nome = str(grupo)
    grupo.delete()  # os subgrupos vão junto
    messages.success(request, f"Grupo {nome} excluído.")
    return redirect("produto_grupos")


@login_required
@require_POST
def grupo_excluir_selecionados(request):
    excluir_selecionados(request, Grupo.objects.all(), singular="grupo", plural="grupos", impedimento=_impedimento_grupo)
    return redirect("produto_grupos")


# ---------- Telas ainda sem print de referência ----------

TELAS = {}


@login_required
def em_construcao(request, tela):
    titulo, descricao = TELAS[tela]
    return render(request, "produtos/em_construcao.html", {"titulo": titulo, "descricao": descricao})


# ---------- Aba "Detalhes fiscais" (por empresa) ----------

def empresas_do_produto(produto):
    """Empresas ativas onde o produto aparece (aba "Empresa"), com o detalhe fiscal de cada uma (ou None)."""
    detalhes = {d.empresa_id: d for d in produto.detalhes_fiscais.select_related("vinculo")}
    empresas = Empresa.objects.filter(ativa=True).exclude(pk__in=produto.empresas_ocultas.values("pk")).order_by("unidade")
    return [(e, detalhes.get(e.pk)) for e in empresas]


def _detalhe_fiscal(produto, empresa):
    return DetalheFiscal.objects.filter(produto=produto, empresa=empresa).first() or DetalheFiscal(
        produto=produto, empresa=empresa,
    )


def contexto_fiscal(produto, empresa, form=None):
    """O que o formulário fiscal precisa (na página própria ou embutido na aba)."""
    form = form or DetalheFiscalForm(instance=_detalhe_fiscal(produto, empresa))
    return {"fiscal_form": form, "fiscal_empresa": empresa}


def copiar_detalhes_fiscais(origem, destino):
    """Clonar produto: os detalhes fiscais são dado de cadastro e vão para a cópia (em cada empresa)."""
    campos = DetalheFiscal.campos_copiaveis()
    for d in origem.detalhes_fiscais.all():
        if destino.disponivel_na(d.empresa):
            DetalheFiscal.objects.update_or_create(
                produto=destino, empresa=d.empresa, defaults={c: getattr(d, c) for c in campos},
            )


@login_required
def produto_fiscal(request, pk, empresa_pk):
    produto = get_object_or_404(Produto.objects.select_related("unidade"), pk=pk)
    empresa = get_object_or_404(Empresa, pk=empresa_pk, ativa=True)
    if not produto.disponivel_na(empresa):
        messages.error(request, f"O produto está oculto em {empresa.unidade}. Marque a empresa na aba Empresa.")
        return redirect(reverse("produto_editar", args=[pk]) + "#empresas")

    form = DetalheFiscalForm(request.POST or None, instance=_detalhe_fiscal(produto, empresa))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Detalhes fiscais de {produto} em {empresa.unidade} salvos com sucesso.")
        if request.POST.get("voltar") == "produto":  # salvou pela aba (empresa única): continua no produto
            return redirect(reverse("produto_editar", args=[pk]) + "#fiscal")
        return redirect("produto_fiscal", pk=pk, empresa_pk=empresa.pk)  # continua no cadastro
    return render(request, "produtos/fiscal.html", {
        "object": produto, "titulo": produto.descricao, "empresas_fiscais": empresas_do_produto(produto),
        **contexto_fiscal(produto, empresa, form),
    })


@login_required
def produto_fiscal_olho(request, pk, empresa_pk):
    """Prévia do "De olho no imposto" para a NCM/origem escolhidas na tela (JSON)."""
    from fiscal.consultas import carga_tributaria

    produto = get_object_or_404(Produto, pk=pk)
    empresa = get_object_or_404(Empresa.objects.select_related("municipio"), pk=empresa_pk)
    ncm = "".join(c for c in request.GET.get("ncm", "") if c.isdigit())
    if not ncm:
        return JsonResponse({"ok": False, "mensagem": "Escolha a NCM para calcular."})
    if not empresa.municipio_id:
        return JsonResponse({"ok": False, "mensagem": f"Cadastre a cidade de {empresa.unidade} para calcular."})
    carga = carga_tributaria(ncm, empresa.municipio.uf, request.GET.get("origem", "0"))
    if carga is None:
        return JsonResponse({"ok": False, "mensagem": f"NCM {ncm} não encontrada na tabela do IBPT ({empresa.municipio.uf})."})
    p = lambda v: f"{v:.2f}".replace(".", ",")
    return JsonResponse({
        "ok": True, "produto": produto.pk, "total": p(carga["total"]),
        "detalhe": f"Federal {p(carga['federal'])}% · Estadual {p(carga['estadual'])}% · Municipal {p(carga['municipal'])}%",
        "fonte": carga["fonte"],
        "partes": {k: float(carga[k]) for k in ("federal", "estadual", "municipal")},
    })


# ---------- Aba "Fotos" ----------

def _voltar_fotos(pk):
    return redirect(reverse("produto_editar", args=[pk]) + "#fotos")


@login_required
@require_POST
def produto_fotos_enviar(request, pk):
    """Envia uma ou várias fotos de uma vez (com a mesma descrição)."""
    from django.core.exceptions import ValidationError
    from django.core.files.base import ContentFile

    from .fotos import MAXIMO_POR_PRODUTO, validar_foto

    produto = get_object_or_404(Produto, pk=pk)
    arquivos = request.FILES.getlist("fotos")
    if not arquivos:
        messages.error(request, "Escolha pelo menos uma foto para enviar.")
        return _voltar_fotos(pk)
    vagas = MAXIMO_POR_PRODUTO - produto.fotos.count()
    if vagas <= 0:
        messages.error(request, f"O produto já tem {MAXIMO_POR_PRODUTO} fotos (o máximo). Exclua alguma para enviar outra.")
        return _voltar_fotos(pk)

    descricao = request.POST.get("descricao", "").strip()[:200]
    enviadas, erros = [], []
    for arquivo in arquivos:
        if len(enviadas) >= vagas:
            erros.append(f"{arquivo.name}: passou do máximo de {MAXIMO_POR_PRODUTO} fotos por produto.")
            continue
        try:
            extensao = validar_foto(arquivo)
        except ValidationError as erro:
            erros.extend(erro.messages)
            continue
        foto = FotoProduto(produto=produto, descricao=descricao)
        foto.arquivo.save(f"foto{extensao}", ContentFile(arquivo.read()), save=False)
        foto.save()
        enviadas.append(foto)

    if enviadas:
        # A primeira foto do produto já vira a principal; ou a pessoa pediu
        if request.POST.get("principal") or not produto.fotos.filter(principal=True).exists():
            enviadas[0].tornar_principal()
        total = len(enviadas)
        messages.success(request, f"{total} foto{'s' if total > 1 else ''} enviada{'s' if total > 1 else ''} com sucesso.")
    for erro in erros:
        messages.error(request, erro)
    return _voltar_fotos(pk)


@login_required
@require_POST
def produto_foto_principal(request, pk, foto_pk):
    foto = get_object_or_404(FotoProduto, pk=foto_pk, produto_id=pk)
    foto.tornar_principal()
    messages.success(request, "Foto principal alterada.")
    return _voltar_fotos(pk)


@login_required
@require_POST
def produto_foto_editar(request, pk, foto_pk):
    foto = get_object_or_404(FotoProduto, pk=foto_pk, produto_id=pk)
    foto.descricao = request.POST.get("descricao", "").strip()[:200]
    foto.save(update_fields=["descricao"])
    messages.success(request, "Descrição da foto salva.")
    return _voltar_fotos(pk)


@login_required
@require_POST
def produto_foto_excluir(request, pk, foto_pk):
    foto = get_object_or_404(FotoProduto, pk=foto_pk, produto_id=pk)
    era_principal = foto.principal
    foto.delete()  # o arquivo sai do disco junto
    proxima = FotoProduto.objects.filter(produto_id=pk).first()
    if era_principal and proxima:
        proxima.tornar_principal()  # sempre fica uma principal enquanto houver foto
    messages.success(request, "Foto excluída.")
    return _voltar_fotos(pk)
