from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator


def administrador_requerido(view):
    """Só deixa passar master e administradores."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        usuario = request.user
        if not usuario.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not usuario.eh_administrador:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def master_requerido(view):
    """Só deixa passar o usuário master."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.eh_master:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


class AdministradorMixin:
    """Para views baseadas em classe."""
    @method_decorator(administrador_requerido)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class MasterMixin:
    @method_decorator(master_requerido)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)