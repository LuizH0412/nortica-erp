from django.urls import path

from . import cadastros_simples, views

urlpatterns = [
    path("", views.home, name="home"),

    # Janela de cadastros simples (função, setor, tipo de cliente...), aberta pelo "+"
    path("cadastros/<slug:tipo>/lista/", cadastros_simples.lista, name="cadastro_simples_lista"),
    path("cadastros/<slug:tipo>/salvar/", cadastros_simples.salvar, name="cadastro_simples_criar"),
    path("cadastros/<slug:tipo>/<int:pk>/salvar/", cadastros_simples.salvar, name="cadastro_simples_salvar"),
    path("cadastros/<slug:tipo>/<int:pk>/excluir/", cadastros_simples.excluir, name="cadastro_simples_excluir"),
]
