"""Tipo de cliente que toda instância já recebe pronto."""
from django.db import migrations

TIPOS_PADRAO = ["Consumidor"]


def criar(apps, schema_editor):
    TipoCliente = apps.get_model("clientes", "TipoCliente")
    for nome in TIPOS_PADRAO:
        if not TipoCliente.objects.filter(nome__iexact=nome).exists():
            TipoCliente.objects.create(nome=nome)


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0001_initial"),
    ]

    operations = [
        # Desfazer não apaga nada: o tipo pode já estar em uso
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
