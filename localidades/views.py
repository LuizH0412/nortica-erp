from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse

from .models import Municipio, normalizar


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
