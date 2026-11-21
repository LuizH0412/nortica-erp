import re

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from localidades.models import normalizar

from .consultas import cests_da_ncm
from .models import Ncm


@login_required
def ncm_busca(request):
    """Busca de NCM para o campo digitável: pelo código (com ou sem pontos) ou pela descrição."""
    termo = request.GET.get("q", "").strip()
    limite = request.GET.get("limite", "")
    limite = min(int(limite), 100) if limite.isdigit() and int(limite) > 0 else 50
    numeros = re.sub(r"[\s.]", "", termo)
    if numeros.isdigit():
        qs = Ncm.objects.filter(codigo__startswith=numeros)
    elif termo:
        qs = Ncm.objects.all()
        for palavra in normalizar(termo).split():
            qs = qs.filter(descricao_busca__contains=palavra)
    else:
        qs = Ncm.objects.all()
    itens = list(qs.order_by("codigo")[: limite + 1])
    return JsonResponse({
        "itens": [{"id": n.codigo, "nome": str(n), "ativo": True} for n in itens[:limite]],
        "mais": len(itens) > limite,
    })


@login_required
def cest_busca(request):
    """CESTs da NCM (?pai=<ncm>) para o campo digitável. Sem NCM ou sem CEST para ela: lista vazia."""
    qs = cests_da_ncm(request.GET.get("pai", ""))
    termo = request.GET.get("q", "").strip()
    numeros = re.sub(r"[\s.]", "", termo)
    if numeros.isdigit():
        qs = qs.filter(codigo__startswith=numeros)
    elif termo:
        for palavra in termo.split():
            qs = qs.filter(descricao__icontains=palavra)
    itens = list(qs[:101])
    return JsonResponse({
        "itens": [{"id": c.codigo, "nome": str(c), "ativo": True} for c in itens[:100]],
        "mais": len(itens) > 100,
    })


@login_required
def cfop_busca(request):
    """
    CFOPs para o campo digitável. ?digitos=5,6 limita pelo primeiro dígito (entrada/saída, dentro/fora do estado);
    ?nfce=1 só os que servem para NFC-e (venda a consumidor dentro do estado: 5.xxx).
    """
    from .models import Cfop

    qs = Cfop.objects.all()
    digitos = [d for d in request.GET.get("digitos", "").split(",") if d.isdigit()]
    if digitos:
        filtro = Q()
        for d in digitos:
            filtro |= Q(codigo__startswith=d)
        qs = qs.filter(filtro)
    termo = request.GET.get("q", "").strip()
    numeros = re.sub(r"[\s.]", "", termo)
    if numeros.isdigit():
        qs = qs.filter(codigo__startswith=numeros)
    elif termo:
        for palavra in termo.split():
            qs = qs.filter(descricao__icontains=palavra)
    itens = list(qs[:61])
    return JsonResponse({"itens": [{"id": c.codigo, "nome": str(c), "ativo": True} for c in itens[:60]], "mais": len(itens) > 60})


@login_required
def cclasstrib_busca(request):
    """Classificações tributárias (cClassTrib) do CST do IBS/CBS escolhido (?pai=<cst>)."""
    from .models import ClassTrib

    cst = request.GET.get("pai", "").strip()
    qs = ClassTrib.objects.filter(cst_id=cst) if cst else ClassTrib.objects.none()
    termo = request.GET.get("q", "").strip()
    if termo.isdigit():
        qs = qs.filter(codigo__startswith=termo)
    elif termo:
        for palavra in termo.split():
            qs = qs.filter(descricao__icontains=palavra)
    itens = list(qs[:101])
    return JsonResponse({"itens": [{"id": c.codigo, "nome": str(c), "ativo": True} for c in itens[:100]], "mais": len(itens) > 100})
