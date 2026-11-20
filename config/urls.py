from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("contas.urls")),
    path("", include("empresas.urls")),
    path("", include("funcionarios.urls")),
    path("", include("clientes.urls")),
    path("", include("localidades.urls")),
]
