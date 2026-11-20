from django.urls import reverse

from contas.models import Usuario
from funcionarios.models import Funcao, Funcionario

from .base_testes import ADMIN, MASTER, InstanciaTestCase


class HomeTests(InstanciaTestCase):
    def test_visitante_vai_para_o_login(self):
        resposta = self.client.get(reverse("home"))
        self.assertRedirects(
            resposta, f"{reverse('login')}?next=/", fetch_redirect_response=False
        )

    def test_usuario_com_empresa_ve_a_home(self):
        empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(empresas=[empresa]))
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)


class FiltroDesativadosTests(InstanciaTestCase):
    """Desativados somem da pesquisa; o interruptor "Só desativados" mostra só eles."""

    def setUp(self):
        super().setUp()
        self.matriz = self.criar_empresa(unidade="Matriz")
        self.criar_empresa(unidade="Filial Fechada", ativa=False)
        self.admin = self.criar_usuario(nivel=ADMIN, empresas=[self.matriz])
        self.client.force_login(self.admin)

    def nomes(self, url_nome, contexto, campo, **params):
        resposta = self.client.get(reverse(url_nome), params)
        return [getattr(o, campo) for o in resposta.context[contexto]]

    def test_funcionarios(self):
        funcao = Funcao.objects.get(nome="Vendedor")  # função padrão (migração)
        Funcionario.objects.create(nome="Ana", funcao=funcao)
        Funcionario.objects.create(nome="Bruno", funcao=funcao, ativo=False)
        self.assertEqual(self.nomes("funcionario_lista", "funcionarios", "nome"), ["Ana"])
        self.assertEqual(
            self.nomes("funcionario_lista", "funcionarios", "nome", desativados="1"), ["Bruno"]
        )
        # A busca por texto continua valendo junto com o filtro
        self.assertEqual(
            self.nomes("funcionario_lista", "funcionarios", "nome", desativados="1", q="ana"), []
        )

    def test_empresas(self):
        self.assertEqual(self.nomes("empresa_lista", "empresas", "unidade"), ["Matriz"])
        self.assertEqual(
            self.nomes("empresa_lista", "empresas", "unidade", desativados="1"), ["Filial Fechada"]
        )

    def test_usuarios_bloqueados(self):
        bloqueado = self.criar_usuario()
        Usuario.objects.filter(pk=bloqueado.pk).update(is_active=False)
        ativos = self.nomes("usuario_lista", "usuarios", "email")
        self.assertIn(self.admin.email, ativos)
        self.assertNotIn(bloqueado.email, ativos)
        self.assertEqual(
            self.nomes("usuario_lista", "usuarios", "email", desativados="1"), [bloqueado.email]
        )

    def test_interruptor_aparece_marcado(self):
        resposta = self.client.get(reverse("funcionario_lista"), {"desativados": "1"})
        self.assertContains(resposta, 'name="desativados" value="1" class="peer sr-only"\n           checked')


class OrdenacaoTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=ADMIN, empresas=[empresa]))
        funcao = Funcao.objects.get(nome="Vendedor")  # função padrão (migração)
        for nome in ("Carla", "Ana", "Bruno"):
            Funcionario.objects.create(nome=nome, funcao=funcao)

    def nomes(self, **params):
        resposta = self.client.get(reverse("funcionario_lista"), params)
        return [f.nome for f in resposta.context["funcionarios"]]

    def test_crescente_e_decrescente(self):
        self.assertEqual(self.nomes(o="nome"), ["Ana", "Bruno", "Carla"])
        self.assertEqual(self.nomes(o="-nome"), ["Carla", "Bruno", "Ana"])

    def test_coluna_desconhecida_e_ignorada(self):
        self.assertEqual(self.nomes(o="senha"), ["Ana", "Bruno", "Carla"])

    def test_link_da_coluna_inverte_e_mantem_a_busca(self):
        resposta = self.client.get(reverse("funcionario_lista"), {"o": "nome", "q": "a"})
        self.assertContains(resposta, "?o=-nome&amp;q=a")


class ConfirmacaoPadraoTests(InstanciaTestCase):
    """Exclusões usam a janela de confirmação do Nexum (data-confirmar), não o confirm() do navegador."""

    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=MASTER))

    def test_funcionario_pede_confirmacao_e_avisa_do_acesso(self):
        f = Funcionario.objects.create(nome="Ana", funcao=Funcao.objects.get(nome="Vendedor"))
        resposta = self.client.get(reverse("funcionario_editar", args=[f.pk]))
        self.assertContains(resposta, 'data-confirmar-titulo="Excluir funcionário?"')
        self.assertNotContains(resposta, "confirm(")

    def test_empresa_sem_registros_pede_confirmacao(self):
        resposta = self.client.get(reverse("empresa_editar", args=[self.empresa.pk]))
        self.assertContains(resposta, 'data-confirmar-titulo="Excluir empresa?"')

    def test_menu_liga_a_confirmacao_em_todas_as_telas(self):
        self.assertContains(self.client.get(reverse("home")), "Nexum.confirmacoes()")
