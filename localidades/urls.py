from django.urls import path

from . import views

urlpatterns = [
    path("localidades/municipios/", views.municipio_busca, name="municipio_busca"),
]
