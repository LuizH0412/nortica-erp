from django.urls import path

from . import views

urlpatterns = [
    path("clientes/", views.ClienteListView.as_view(), name="cliente_lista"),
    path("clientes/novo/", views.cliente_form, name="cliente_criar"),
    path("clientes/<int:pk>/editar/", views.cliente_form, name="cliente_editar"),
    path("clientes/<int:pk>/excluir/", views.cliente_excluir, name="cliente_excluir"),

    # Aba "Financeiro"
    path("clientes/<int:pk>/credito/", views.cliente_credito_painel, name="cliente_credito_painel"),
    path("clientes/<int:pk>/credito/limite/", views.cliente_credito, name="cliente_credito"),
    path("clientes/<int:pk>/credito/lancar/", views.cliente_credito_lancar, name="cliente_credito_lancar"),

    # Aba "Outros endereços"
    path("clientes/<int:pk>/enderecos/novo/", views.cliente_endereco_salvar, name="cliente_endereco_novo"),
    path("clientes/<int:pk>/enderecos/<int:endereco_pk>/editar/", views.cliente_endereco_salvar, name="cliente_endereco_editar"),
    path("clientes/<int:pk>/enderecos/<int:endereco_pk>/excluir/", views.cliente_endereco_excluir, name="cliente_endereco_excluir"),
]
