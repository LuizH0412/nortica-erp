from .models import Empresa

SESSAO_CHAVE = "empresa_id"


def sistema_multiloja():
    """Multiloja = mais de uma empresa ativa no sistema."""
    return Empresa.objects.filter(ativa=True).count() > 1


def empresas_do_usuario(usuario):
    """
    Empresas em que a pessoa pode entrar: as ativas onde ela tem um perfil de acesso.
    O master vê todas, inclusive as desativadas.
    """
    if usuario.eh_master:
        return Empresa.objects.all()
    return Empresa.objects.filter(ativa=True, acessos__usuario=usuario).distinct()


def pode_configurar(request):
    """Master, ou perfil na empresa atual que acessa as configurações."""
    usuario = request.user
    if not usuario.is_authenticated:
        return False
    if usuario.eh_master:
        return True
    perfil = getattr(request, "perfil_atual", None)
    return bool(perfil and perfil.pode_configurar)


def resolver_empresa(request):
    """Descobre a empresa atual. Devolve (empresa, precisa_escolher)."""
    disponiveis = empresas_do_usuario(request.user)

    # 1) a que já está na sessão, se ainda for válida
    escolhida = request.session.get(SESSAO_CHAVE)
    if escolhida:
        empresa = disponiveis.filter(pk=escolhida).first()
        if empresa:
            return empresa, False

    # 2) sistema com uma loja só: entra direto
    if not sistema_multiloja():
        return disponiveis.filter(ativa=True).first(), False

    # 3) multiloja: depende de quantas a pessoa pode acessar
    total = disponiveis.count()
    if total == 0:
        return None, False
    if total == 1:
        return disponiveis.first(), False
    return None, True