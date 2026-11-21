from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("contas.urls")),
    path("", include("empresas.urls")),
    path("", include("funcionarios.urls")),
    path("", include("clientes.urls")),
    path("", include("produtos.urls")),
    path("", include("localidades.urls")),
    path("", include("fiscal.urls")),
]

# Em desenvolvimento o próprio Django entrega as fotos; em produção quem entrega é o servidor web
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
