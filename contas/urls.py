from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Usuários
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path("usuarios/novo/", views.UsuarioCriarView.as_view(), name="usuario_criar"),
    path("usuarios/<int:pk>/editar/", views.UsuarioEditarView.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/senha/", views.usuario_senha, name="usuario_senha"),
    path("usuarios/<int:pk>/perfis/adicionar/", views.usuario_acesso_adicionar, name="usuario_acesso_adicionar"),
    path("usuarios/<int:pk>/perfis/remover/", views.usuario_acesso_remover, name="usuario_acesso_remover"),

    # Perfis de acesso
    path("perfis/", views.PerfilListView.as_view(), name="perfil_lista"),
    path("perfis/novo/", views.PerfilCriarView.as_view(), name="perfil_criar"),
    path("perfis/<int:pk>/editar/", views.PerfilEditarView.as_view(), name="perfil_editar"),
    path("perfis/<int:pk>/excluir/", views.perfil_excluir, name="perfil_excluir"),
]
