import re
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import tenant_context

from contas.models import Usuario
from instancias.models import Dominio, Instancia

RESERVADOS = {"public", "www", "painel", "admin", "api", "suporte"}


class Command(BaseCommand):
    help = "Cria uma instância do Nexum: espaço isolado, endereço e usuário master."

    def add_arguments(self, parser):
        parser.add_argument("--codigo", required=True, help="Código do contrato, ex.: 001")
        parser.add_argument("--nome", required=True, help="Nome do cliente")
        parser.add_argument("--subdominio", required=True, help="Ex.: missmake")

    def handle(self, *args, **opcoes):
        codigo = opcoes["codigo"].strip()
        nome = opcoes["nome"].strip()
        sub = opcoes["subdominio"].strip().lower()

        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", sub) or sub in RESERVADOS:
            raise CommandError(
                "Subdomínio inválido ou reservado. Use letras minúsculas, números e hífen."
            )
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

        self.stdout.write(self.style.SUCCESS(f"\nInstância criada: {nome} (código {codigo})"))
        self.stdout.write(f"Endereço: {dominio}")
        self.stdout.write(f"E-mail:   {settings.MASTER_EMAIL}")
        self.stdout.write(f"Senha:    {senha}")
        self.stdout.write(
            self.style.WARNING("Guarde a senha agora no gerenciador de senhas. Ela não será exibida de novo.")
        )