from django.urls import path

from . import views, views_vinculos as vinculos

urlpatterns = [
    path("produtos/", views.ProdutoListView.as_view(), name="produto_lista"),
    path("produtos/novo/", views.produto_form, name="produto_criar"),
    path("produtos/<int:pk>/editar/", views.produto_form, name="produto_editar"),
    path("produtos/<int:pk>/fiscal/<int:empresa_pk>/", views.produto_fiscal, name="produto_fiscal"),
    path("produtos/<int:pk>/fotos/enviar/", views.produto_fotos_enviar, name="produto_fotos_enviar"),
    path("produtos/<int:pk>/fotos/<int:foto_pk>/principal/", views.produto_foto_principal, name="produto_foto_principal"),
    path("produtos/<int:pk>/fotos/<int:foto_pk>/editar/", views.produto_foto_editar, name="produto_foto_editar"),
    path("produtos/<int:pk>/fotos/<int:foto_pk>/excluir/", views.produto_foto_excluir, name="produto_foto_excluir"),
    path("produtos/<int:pk>/fiscal/<int:empresa_pk>/olho/", views.produto_fiscal_olho, name="produto_fiscal_olho"),
    path("produtos/<int:pk>/excluir/", views.produto_excluir, name="produto_excluir"),
    path("produtos/excluir-selecionados/", views.produto_excluir_selecionados, name="produto_excluir_selecionados"),
    path("produtos/<int:pk>/estoque/organizar/", views.produto_estoque_organizar, name="produto_estoque_organizar"),
    path("produtos/<int:pk>/estoque/rapido/", views.produto_estoque_rapido, name="produto_estoque_rapido"),
    path("produtos/<int:pk>/estoque/minimo/", views.produto_estoque_minimo, name="produto_estoque_minimo"),

    # Grupos
    path("produtos/grupos/", views.GrupoListView.as_view(), name="produto_grupos"),
    path("produtos/grupos/novo/", views.grupo_form, name="produto_grupo_criar"),
    path("produtos/grupos/<int:pk>/editar/", views.grupo_form, name="produto_grupo_editar"),
    path("produtos/grupos/<int:pk>/excluir/", views.grupo_excluir, name="produto_grupo_excluir"),
    path("produtos/grupos/excluir-selecionados/", views.grupo_excluir_selecionados, name="produto_grupo_excluir_selecionados"),

    # Vínculos fiscais
    path("produtos/vinculos-fiscais/", vinculos.VinculoListView.as_view(), name="produto_vinculos_fiscais"),
    path("produtos/vinculos-fiscais/novo/", vinculos.vinculo_form, name="vinculo_criar"),
    path("produtos/vinculos-fiscais/<int:pk>/editar/", vinculos.vinculo_form, name="vinculo_editar"),
    path("produtos/vinculos-fiscais/<int:pk>/excluir/", vinculos.vinculo_excluir, name="vinculo_excluir"),
    path("produtos/vinculos-fiscais/excluir-selecionados/", vinculos.vinculo_excluir_selecionados,
         name="vinculo_excluir_selecionados"),
    path("produtos/vinculos-fiscais/<int:pk>/padrao/", vinculos.vinculo_padrao, name="vinculo_padrao"),
    path("produtos/vinculos-fiscais/<int:pk>/clonar/", vinculos.vinculo_clonar, name="vinculo_clonar"),
    path("produtos/vinculos-fiscais/<int:pk>/configuracoes/adicionar/", vinculos.configuracao_adicionar,
         name="vinculo_configuracao_adicionar"),
    path("produtos/vinculos-fiscais/<int:pk>/configuracoes/<int:config_pk>/clonar/", vinculos.configuracao_clonar,
         name="vinculo_configuracao_clonar"),
    path("produtos/vinculos-fiscais/<int:pk>/configuracoes/<int:config_pk>/excluir/", vinculos.configuracao_excluir,
         name="vinculo_configuracao_excluir"),
    path("produtos/vinculos-fiscais/<int:pk>/configuracoes/<int:config_pk>/<str:operacao>/", vinculos.tributacao_form,
         name="vinculo_tributacao"),
    path("produtos/vinculos-fiscais/<int:pk>/ncms/adicionar/", vinculos.vinculo_ncm_adicionar, name="vinculo_ncm_adicionar"),
    path("produtos/vinculos-fiscais/<int:pk>/ncms/<int:ncm_pk>/remover/", vinculos.vinculo_ncm_remover,
         name="vinculo_ncm_remover"),
    path("produtos/vinculos-fiscais/<int:pk>/produtos/adicionar/", vinculos.vinculo_produto_adicionar,
         name="vinculo_produto_adicionar"),
    path("produtos/vinculos-fiscais/<int:pk>/produtos/<int:detalhe_pk>/remover/", vinculos.vinculo_produto_remover,
         name="vinculo_produto_remover"),
    path("produtos/busca/", vinculos.produto_busca, name="produto_busca"),
]
