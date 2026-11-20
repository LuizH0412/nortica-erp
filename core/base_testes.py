"""Base para testes que precisam de uma instância (schema de cliente)."""
from itertools import count

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from contas.models import AcessoEmpresa, Perfil, Usuario
from empresas.models import Empresa

_sequencia = count(1)
SENHA_TESTE = "senha-de-teste-123"

# Tipos de usuário para os testes
MASTER, ADMIN, COMUM = "master", "admin", "comum"


class InstanciaTestCase(TenantTestCase):
    """Cria um schema de teste, com um cliente HTTP apontando para o domínio dele."""

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.codigo = "teste"
        tenant.nome = "Instância de teste"

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)

    # ---------- Fábricas ----------

    def criar_empresa(self, unidade=None, ativa=True):
        n = next(_sequencia)
        return Empresa.objects.create(
            unidade=unidade or f"Unidade {n}",
            razao_social=f"Empresa {n} LTDA",
            documento=f"{n:014d}",  # não passa pelo validador; só precisa ser único
            ativa=ativa,
        )

    @staticmethod
    def perfil(nome):
        """Perfis padrão criados pela migração: "Administrador" e "Usuário"."""
        return Perfil.objects.get(nome=nome)

    def criar_usuario(self, nivel=COMUM, empresas=()):
        """
        nivel: MASTER (entra em tudo), ADMIN (perfil Administrador nas empresas)
        ou COMUM (perfil Usuário nas empresas).
        """
        n = next(_sequencia)
        usuario = Usuario.objects.create_user(
            email=f"usuario{n}@teste.com", password=SENHA_TESTE, master=(nivel == MASTER)
        )
        if nivel != MASTER:
            perfil = self.perfil("Administrador" if nivel == ADMIN else "Usuário")
            for empresa in empresas:
                AcessoEmpresa.objects.create(usuario=usuario, empresa=empresa, perfil=perfil)
        return usuario
