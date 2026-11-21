"""O regime da empresa passa a ser o CRT da nota (igual aos vínculos fiscais)."""
from django.db import migrations, models

DE_PARA = {"simples": "1", "mei": "4", "presumido": "3", "real": "3"}


def converter(apps, schema_editor):
    Empresa = apps.get_model("empresas", "Empresa")
    for antigo, crt in DE_PARA.items():
        Empresa.objects.filter(regime_tributario=antigo).update(regime_tributario=crt)


def desfazer(apps, schema_editor):
    Empresa = apps.get_model("empresas", "Empresa")
    for crt, antigo in (("1", "simples"), ("4", "mei"), ("3", "presumido"), ("2", "simples")):
        Empresa.objects.filter(regime_tributario=crt).update(regime_tributario=antigo)


class Migration(migrations.Migration):

    dependencies = [
        ("empresas", "0002_fiscal_tributario"),
    ]

    operations = [
        migrations.RunPython(converter, desfazer),
        migrations.AlterField(
            model_name="empresa",
            name="regime_tributario",
            field=models.CharField(
                blank=True,
                choices=[("1", "Simples Nacional"), ("2", "Simples Nacional – excesso de sublimite"),
                         ("3", "Regime Normal"), ("4", "MEI (Simei)")],
                help_text="O mesmo código da nota fiscal (CRT), usado também nos vínculos fiscais.",
                max_length=15, verbose_name="Regime tributário",
            ),
        ),
    ]
