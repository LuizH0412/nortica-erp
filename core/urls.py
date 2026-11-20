from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Escolha e troca de empresa
    path("entrar-empresa/", views.escolher_empresa, name="escolher_empresa"),
    path("trocar-empresa/<int:pk>/", views.trocar_empresa, name="trocar_empresa"),
    path("sem-acesso/", views.sem_acesso, name="sem_acesso"),

    # Empresas
    path("empresas/", views.EmpresaListView.as_view(), name="empresa_lista"),
    path("empresas/nova/", views.EmpresaCriarView.as_view(), name="empresa_criar"),
    path("empresas/<int:pk>/editar/", views.EmpresaEditarView.as_view(), name="empresa_editar"),
    path("empresas/<int:pk>/excluir/", views.empresa_excluir, name="empresa_excluir"),
    path("empresas/consulta/cnpj/", views.consulta_cnpj, name="consulta_cnpj"),
    path("empresas/consulta/cep/", views.consulta_cep, name="consulta_cep"),
    path("localidades/municipios/", views.municipio_busca, name="municipio_busca"),

    # Usuários
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path("usuarios/novo/", views.UsuarioCriarView.as_view(), name="usuario_criar"),
    path("usuarios/<int:pk>/editar/", views.UsuarioEditarView.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/senha/", views.usuario_senha, name="usuario_senha"),

    
]