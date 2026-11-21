from django.apps import AppConfig


class ProdutosConfig(AppConfig):
    name = "produtos"
    verbose_name = "Produtos"

    def ready(self):
        from core.cadastros_simples import registrar

        from . import forms, models

        uso = ("produto", "produtos")
        registrar("grupo", models.Grupo, forms.GrupoForm, relacao="produtos", uso=uso)
        registrar("subgrupo", models.Subgrupo, forms.SubgrupoForm, relacao="produtos", uso=uso, pai="grupo")
        registrar("fabricante", models.Fabricante, forms.FabricanteForm, relacao="produtos", uso=uso)
        registrar("similar", models.Similar, forms.SimilarForm, relacao="produtos", uso=uso)
        registrar("unidade", models.UnidadeMedida, forms.UnidadeMedidaForm, relacao="produtos", uso=uso)
        registrar("vinculo_fiscal", models.VinculoFiscal, forms.VinculoFiscalForm, relacao="detalhes",
                  uso=("detalhe fiscal", "detalhes fiscais"))
