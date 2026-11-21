from django.urls import path

from . import views

urlpatterns = [
    path("fiscal/ncm/", views.ncm_busca, name="ncm_busca"),
    path("fiscal/cest/", views.cest_busca, name="cest_busca"),
    path("fiscal/cfop/", views.cfop_busca, name="cfop_busca"),
    path("fiscal/cclasstrib/", views.cclasstrib_busca, name="cclasstrib_busca"),
]
