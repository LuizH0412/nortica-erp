from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, tenant_context

from produtos.vinculos_padrao import configurar_vinculos_padrao


class Command(BaseCommand):
    help = ("Cria nos 3 vínculos fiscais padrão as configurações NF-e (UF -> todas) e NFC-e (interna) "
            "com a tributação padrão. Não mexe no que já existe.")

    def add_arguments(self, parser):
        parser.add_argument("--subdominio", required=True, help="Instância (ex.: missmake)")
        parser.add_argument("--uf", required=True, help="UF da empresa (ex.: MT)")
        parser.add_argument("--regime", required=True, help="simples, mei, presumido ou real")

    def handle(self, *args, subdominio, uf, regime, **opcoes):
        instancia = get_tenant_model().objects.filter(schema_name=subdominio.strip().lower().replace("-", "_")).first()
        if not instancia:
            raise CommandError(f"Instância {subdominio} não encontrada.")
        try:
            with tenant_context(instancia):
                criadas = configurar_vinculos_padrao(uf, regime)
        except ValueError as erro:
            raise CommandError(str(erro))
        self.stdout.write(self.style.SUCCESS(f"{criadas} configuração(ões) criada(s) nos vínculos padrão de {instancia.nome}."))
