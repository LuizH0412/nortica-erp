"""Unidades de medida que toda instância já recebe prontas (siglas usadas na nota fiscal)."""
from django.db import migrations

UNIDADES_PADRAO = ["UN", "KG", "G", "LT", "ML", "MT", "M2", "M3", "CX", "PC", "PAR", "DZ", "FD", "KIT", "SC"]


def criar(apps, schema_editor):
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")
    for nome in UNIDADES_PADRAO:
        if not UnidadeMedida.objects.filter(nome__iexact=nome).exists():
            UnidadeMedida.objects.create(nome=nome)


class Migration(migrations.Migration):

    dependencies = [
        ("produtos", "0001_initial"),
    ]

    operations = [
        # Desfazer não apaga nada: as unidades podem já estar em uso
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
