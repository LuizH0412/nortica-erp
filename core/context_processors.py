from .empresas import empresas_do_usuario, sistema_multiloja


def empresa(request):
    if not request.user.is_authenticated:
        return {}
    contexto = {"empresa_atual": getattr(request, "empresa_atual", None), "empresas_troca": []}
    if sistema_multiloja():
        disponiveis = empresas_do_usuario(request.user)
        if disponiveis.count() > 1:
            contexto["empresas_troca"] = list(disponiveis)
    return contexto