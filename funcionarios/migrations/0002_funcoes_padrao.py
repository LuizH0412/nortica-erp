"""Funções que toda instância já recebe prontas no cadastro de funcionário."""
from django.db import migrations

FUNCOES_PADRAO = ["Vendedor", "Atendente", "Entregador"]


def criar(apps, schema_editor):
    Funcao = apps.get_model("funcionarios", "Funcao")
    for nome in FUNCOES_PADRAO:
        # Sem diferenciar maiúsculas: se o cliente já criou "vendedor", não duplica
        if not Funcao.objects.filter(nome__iexact=nome).exists():
            Funcao.objects.create(nome=nome)


class Migration(migrations.Migration):

    dependencies = [
        ("funcionarios", "0001_initial"),
    ]

    operations = [
        # Desfazer não apaga nada: as funções podem já estar em uso
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
