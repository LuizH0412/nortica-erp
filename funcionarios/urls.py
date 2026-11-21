from django.urls import path

from . import views

urlpatterns = [
    path("funcionarios/", views.FuncionarioListView.as_view(), name="funcionario_lista"),
    path("funcionarios/novo/", views.funcionario_form, name="funcionario_criar"),
    path("funcionarios/<int:pk>/editar/", views.funcionario_form, name="funcionario_editar"),
    path("funcionarios/<int:pk>/excluir/", views.funcionario_excluir, name="funcionario_excluir"),
    path("funcionarios/excluir-selecionados/", views.funcionario_excluir_selecionados, name="funcionario_excluir_selecionados"),
    path("funcionarios/<int:pk>/usuario/", views.funcionario_usuario, name="funcionario_usuario"),
    path("funcionarios/<int:pk>/usuario/desvincular/", views.funcionario_desvincular, name="funcionario_desvincular"),
]
