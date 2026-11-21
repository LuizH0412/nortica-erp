from django.urls import path

from . import views

urlpatterns = [
    # Escolha e troca de empresa
    path("entrar-empresa/", views.escolher_empresa, name="escolher_empresa"),
    path("trocar-empresa/<int:pk>/", views.trocar_empresa, name="trocar_empresa"),
    path("sem-acesso/", views.sem_acesso, name="sem_acesso"),

    # Cadastro de empresas
    path("empresas/", views.EmpresaListView.as_view(), name="empresa_lista"),
    path("empresas/nova/", views.EmpresaCriarView.as_view(), name="empresa_criar"),
    path("empresas/<int:pk>/editar/", views.EmpresaEditarView.as_view(), name="empresa_editar"),
    path("empresas/<int:pk>/excluir/", views.empresa_excluir, name="empresa_excluir"),
    path("empresas/<int:pk>/certificado/", views.empresa_certificado_enviar, name="empresa_certificado_enviar"),
    path("empresas/<int:pk>/certificado/excluir/", views.empresa_certificado_excluir, name="empresa_certificado_excluir"),
    path("empresas/excluir-selecionados/", views.empresa_excluir_selecionados, name="empresa_excluir_selecionados"),
    path("empresas/consulta/cnpj/", views.consulta_cnpj, name="consulta_cnpj"),
    path("empresas/consulta/cep/", views.consulta_cep, name="consulta_cep"),
]
