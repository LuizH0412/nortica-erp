"""
Troca o "nível" global do usuário por perfis de acesso por empresa.

- Cria os perfis padrão "Administrador" (acessa as configurações) e "Usuário".
- Quem era nível master vira master.
- Quem era administrador/comum ganha, em cada empresa que podia acessar,
  o perfil equivalente.
"""
import django.db.models.deletion
from django.db import migrations, models


def converter(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    Perfil = apps.get_model("contas", "Perfil")
    AcessoEmpresa = apps.get_model("contas", "AcessoEmpresa")

    administrador, _ = Perfil.objects.get_or_create(
        nome="Administrador", defaults={"pode_configurar": True}
    )
    comum, _ = Perfil.objects.get_or_create(nome="Usuário", defaults={"pode_configurar": False})

    for usuario in Usuario.objects.all():
        if usuario.nivel == "master":
            usuario.master = True
            usuario.save(update_fields=["master"])
            continue
        perfil = administrador if usuario.nivel == "administrador" else comum
        for empresa in usuario.empresas_permitidas.all():
            AcessoEmpresa.objects.get_or_create(
                usuario=usuario, empresa=empresa, defaults={"perfil": perfil}
            )


def desfazer(apps, schema_editor):
    Usuario = apps.get_model("contas", "Usuario")
    AcessoEmpresa = apps.get_model("contas", "AcessoEmpresa")
    for usuario in Usuario.objects.all():
        if usuario.master:
            usuario.nivel = "master"
        else:
            acessos = AcessoEmpresa.objects.filter(usuario=usuario).select_related("perfil")
            admin = any(a.perfil.pode_configurar for a in acessos)
            usuario.nivel = "administrador" if admin else "comum"
            usuario.empresas_permitidas.set([a.empresa_id for a in acessos])
        usuario.save()


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0002_login_por_email"),
        ("empresas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="master",
            field=models.BooleanField(default=False, editable=False, verbose_name="Master"),
        ),
        migrations.CreateModel(
            name="Perfil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(
                    error_messages={"unique": "Já existe um perfil com este nome."},
                    max_length=60, unique=True, verbose_name="Nome",
                )),
                ("pode_configurar", models.BooleanField(
                    default=False, help_text="Empresas, funcionários, usuários e perfis de acesso.",
                    verbose_name="Acessa as configurações",
                )),
            ],
            options={
                "verbose_name": "perfil de acesso",
                "verbose_name_plural": "perfis de acesso",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="AcessoEmpresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("empresa", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="acessos",
                    to="empresas.empresa", verbose_name="Empresa",
                )),
                ("perfil", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="acessos",
                    to="contas.perfil", verbose_name="Perfil",
                )),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="acessos",
                    to="contas.usuario", verbose_name="Usuário",
                )),
            ],
            options={
                "verbose_name": "acesso à empresa",
                "verbose_name_plural": "acessos às empresas",
                "ordering": ["empresa__unidade"],
                "constraints": [
                    models.UniqueConstraint(fields=("usuario", "empresa"), name="um_perfil_por_empresa"),
                ],
            },
        ),
        migrations.RunPython(converter, desfazer),
        migrations.RemoveField(model_name="usuario", name="empresas_permitidas"),
        migrations.RemoveField(model_name="usuario", name="nivel"),
    ]
