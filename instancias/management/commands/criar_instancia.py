import re
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from contas.models import Usuario
from instancias.models import Dominio, Instancia
from produtos.vinculos_padrao import configurar_vinculos_padrao, crt_do_regime

RESERVADOS = {"public", "www", "painel", "admin", "api", "suporte"}


class Command(BaseCommand):
    help = "Cria uma instância do Nexum: espaço isolado, endereço e usuário master."

    def add_arguments(self, parser):
        parser.add_argument("--codigo", required=True, help="Código do contrato, ex.: 001")
        parser.add_argument("--nome", required=True, help="Nome do cliente")
        parser.add_argument("--subdominio", required=True, help="Ex.: missmake")
        # Vínculos fiscais padrão: as configurações dependem da UF e do regime da empresa
        parser.add_argument("--uf", help="UF da empresa (ex.: MT) para configurar os vínculos fiscais padrão")
        parser.add_argument("--regime", help="Regime da empresa: simples, mei, presumido ou real")

    def handle(self, *args, **opcoes):
        codigo = opcoes["codigo"].strip()
        nome = opcoes["nome"].strip()
        sub = opcoes["subdominio"].strip().lower()

        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", sub) or sub in RESERVADOS:
            raise CommandError(
                "Subdomínio inválido ou reservado. Use letras minúsculas, números e hífen."
            )
        if bool(opcoes.get("uf")) != bool(opcoes.get("regime")):
            raise CommandError("Informe --uf e --regime juntos (ou nenhum dos dois).")
        if opcoes.get("regime"):
            try:
                crt_do_regime(opcoes["regime"])
            except ValueError as erro:
                raise CommandError(str(erro))
        if not settings.MASTER_EMAIL:
            raise CommandError("Defina MASTER_EMAIL no arquivo .env.")

        dominio = f"{sub}.{settings.DOMINIO_BASE}"
        if Instancia.objects.filter(codigo=codigo).exists():
            raise CommandError(f"Já existe uma instância com o código {codigo}.")
        if Dominio.objects.filter(domain=dominio).exists():
            raise CommandError(f"O endereço {dominio} já está em uso.")

        instancia = Instancia(schema_name=sub.replace("-", "_"), codigo=codigo, nome=nome)
        instancia.save()  # cria o espaço do cliente e aplica as migrações
        Dominio.objects.create(domain=dominio, tenant=instancia, is_primary=True)

        senha = secrets.token_urlsafe(18)
        with tenant_context(instancia):
            Usuario.objects.create_user(
                email=settings.MASTER_EMAIL,
                password=senha,
                first_name="Suporte Nexum",
                master=True,
                is_superuser=True,
            )
            criadas = configurar_vinculos_padrao(opcoes["uf"], opcoes["regime"]) if opcoes.get("uf") else None

        self.stdout.write(self.style.SUCCESS(f"\nInstância criada: {nome} (código {codigo})"))
        self.stdout.write(f"Endereço: {dominio}")
        self.stdout.write(f"E-mail:   {settings.MASTER_EMAIL}")
        self.stdout.write(f"Senha:    {senha}")
        if criadas is None:
            self.stdout.write(self.style.WARNING(
                "Vínculos fiscais padrão criados sem configuração. Depois rode: manage.py configurar_vinculos_padrao "
                f"--subdominio {sub} --uf <UF> --regime <simples|mei|presumido|real>"))
        else:
            self.stdout.write(f"Vínculos fiscais padrão: {criadas} configurações criadas ({opcoes['uf'].upper()}).")
        self.stdout.write(
            self.style.WARNING("Guarde a senha agora no gerenciador de senhas. Ela não será exibida de novo.")
        )