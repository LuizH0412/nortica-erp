from django.shortcuts import redirect

from .selecao import pode_configurar, resolver_empresa

ISENTAS = {"login", "logout", "escolher_empresa", "trocar_empresa", "sem_acesso"}


class EmpresaAtualMiddleware:
    """
    Descobre a empresa atual da sessão e o perfil da pessoa nela:
    request.empresa_atual, request.perfil_atual e request.pode_configurar.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa_atual = None
        request.perfil_atual = None
        request.pode_configurar = False
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        empresa, precisa_escolher = resolver_empresa(request)
        request.empresa_atual = empresa
        request.perfil_atual = request.user.perfil_na(empresa)
        request.pode_configurar = pode_configurar(request)
        if request.resolver_match.url_name in ISENTAS:
            return None
        if precisa_escolher:
            return redirect("escolher_empresa")
        if empresa is None and not request.user.eh_master:
            return redirect("sem_acesso")
        return None
