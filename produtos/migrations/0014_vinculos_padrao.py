"""Vínculos fiscais que toda instância já recebe prontos (as configurações vêm de produtos/vinculos_padrao.py)."""
from django.db import migrations

VINCULOS_PADRAO = [
    "ICMS cobrado anteriormente por substituição",
    "ICMS Tributado - PIS Isento",
    "ICMS Isento - PIS Isento",
]


def criar(apps, schema_editor):
    VinculoFiscal = apps.get_model("produtos", "VinculoFiscal")
    for nome in VINCULOS_PADRAO:
        if not VinculoFiscal.objects.filter(nome__iexact=nome).exists():
            VinculoFiscal.objects.create(nome=nome, tipo_item="00")


class Migration(migrations.Migration):

    dependencies = [
        ("produtos", "0013_icms_st_e_enquadramento_ipi"),
    ]

    operations = [
        # Desfazer não apaga nada: os vínculos podem já estar em uso
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
