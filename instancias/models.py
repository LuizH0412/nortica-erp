from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Instancia(TenantMixin):
    """Uma instância do Nexum = um cliente da Nórtica com seu espaço isolado."""
    codigo = models.CharField(
        "Código do cliente", max_length=20, unique=True,
        help_text="Mesmo código do contrato no sistema de gestão da Nórtica.",
    )
    nome = models.CharField(max_length=150)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

    def __str__(self):
        return f"{self.codigo} · {self.nome}"


class Dominio(DomainMixin):
    pass