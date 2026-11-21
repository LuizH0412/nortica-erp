from django.urls import path

from . import views

urlpatterns = [
    path("clientes/", views.ClienteListView.as_view(), name="cliente_lista"),
    path("clientes/novo/", views.cliente_form, name="cliente_criar"),
    path("clientes/<int:pk>/editar/", views.cliente_form, name="cliente_editar"),
    path("clientes/<int:pk>/excluir/", views.cliente_excluir, name="cliente_excluir"),
    path("clientes/excluir-selecionados/", views.cliente_excluir_selecionados, name="cliente_excluir_selecionados"),

    # Aba "Financeiro"
    path("clientes/<int:pk>/credito/", views.cliente_credito_painel, name="cliente_credito_painel"),
    path("clientes/<int:pk>/credito/limite/", views.cliente_credito, name="cliente_credito"),
    path("clientes/<int:pk>/credito/lancar/", views.cliente_credito_lancar, name="cliente_credito_lancar"),

    # Aba "Contatos"
    path("clientes/<int:pk>/contatos/novo/", views.cliente_contato_salvar, name="cliente_contato_novo"),
    path("clientes/<int:pk>/contatos/<int:contato_pk>/editar/", views.cliente_contato_salvar, name="cliente_contato_editar"),
    path("clientes/<int:pk>/contatos/<int:contato_pk>/excluir/", views.cliente_contato_excluir, name="cliente_contato_excluir"),

    # Aba "Outros endereços"
    path("clientes/<int:pk>/enderecos/novo/", views.cliente_endereco_salvar, name="cliente_endereco_novo"),
    path("clientes/<int:pk>/enderecos/<int:endereco_pk>/editar/", views.cliente_endereco_salvar, name="cliente_endereco_editar"),
    path("clientes/<int:pk>/enderecos/<int:endereco_pk>/excluir/", views.cliente_endereco_excluir, name="cliente_endereco_excluir"),
]
