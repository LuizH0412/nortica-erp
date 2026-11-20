"""
Janela de gestão dos cadastros simples (aberta pelo "+" ao lado de um campo).

Cada app registra os seus no AppConfig.ready():

    registrar("funcao", Funcao, FuncaoForm, relacao="funcionarios",
              uso=("funcionário", "funcionários"), so_configuracao=True)

- relacao: nome do relacionamento reverso que diz quem usa o item (para contar e impedir exclusão)
- uso: como chamar quem usa, no singular e plural (para as mensagens)
- so_configuracao: só quem acessa as configurações pode gerir (senão, qualquer usuário logado)

Tudo responde em JSON: pesquisar, cadastrar, renomear, ativar/desativar e excluir.
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

REGISTRO = {}


def registrar(tipo, modelo, form, *, relacao, uso, so_configuracao=False):
    REGISTRO[tipo] = {
        "modelo": modelo, "form": form, "relacao": relacao,
        "uso": uso, "so_configuracao": so_configuracao,
    }


def _cfg(request, tipo):
    cfg = REGISTRO.get(tipo)
    if cfg is None:
        raise Http404
    if cfg["so_configuracao"] and not getattr(request, "pode_configurar", False):
        raise PermissionDenied
    return cfg


def _em_uso(cfg, item):
    return getattr(item, cfg["relacao"]).count()


def _item_json(item, uso):
    return {"id": item.pk, "nome": item.nome, "ativo": item.ativo, "uso": uso}


@login_required
def lista(request, tipo):
    cfg = _cfg(request, tipo)
    qs = cfg["modelo"].objects.annotate(total=Count(cfg["relacao"])).order_by("-ativo", "nome")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(nome__icontains=q)
    return JsonResponse({"itens": [_item_json(i, i.total) for i in qs[:200]]})


@login_required
@require_POST
def salvar(request, tipo, pk=None):
    """Sem pk cadastra (já nasce ativo); com pk altera o nome e/ou se está ativo."""
    cfg = _cfg(request, tipo)
    item = get_object_or_404(cfg["modelo"], pk=pk) if pk else None
    ativo = request.POST.get("ativo", "1" if (item is None or item.ativo) else "")
    dados = {
        "nome": request.POST.get("nome", item.nome if item else ""),
        "ativo": "on" if ativo in ("1", "on", "true") else "",
    }
    form = cfg["form"](dados, instance=item)
    if not form.is_valid():
        mensagem = " ".join(e for lista_erros in form.errors.values() for e in lista_erros)
        return JsonResponse({"ok": False, "mensagem": mensagem}, status=400)
    item = form.save()
    return JsonResponse({"ok": True, "item": _item_json(item, _em_uso(cfg, item))})


@login_required
@require_POST
def excluir(request, tipo, pk):
    cfg = _cfg(request, tipo)
    item = get_object_or_404(cfg["modelo"], pk=pk)
    uso = _em_uso(cfg, item)
    if uso:
        singular, plural = cfg["uso"]
        return JsonResponse({
            "ok": False, "em_uso": True,
            "mensagem": f"{item.nome} está em uso por {uso} {singular if uso == 1 else plural}. "
                        "Desative para não aparecer mais nas opções.",
        }, status=409)
    item.delete()
    return JsonResponse({"ok": True})
