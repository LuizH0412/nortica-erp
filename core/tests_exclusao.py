"""Botão "Excluir selecionados" das listas."""
from django.urls import reverse

from clientes.models import Cliente
from contas.models import Perfil, Usuario
from empresas.models import Empresa
from funcionarios.models import Funcao, Funcionario

from .base_testes import ADMIN, COMUM, MASTER, InstanciaTestCase


class ExcluirSelecionadosTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.admin = self.criar_usuario(nivel=ADMIN, empresas=[self.empresa])
        self.client.force_login(self.admin)

    def excluir(self, rota, *objetos, follow=True):
        return self.client.post(reverse(rota), {"selecionados": [o.pk for o in objetos]}, follow=follow)

    def test_todas_as_listas_tem_o_botao(self):
        for rota in ("funcionario_lista", "usuario_lista", "perfil_lista", "cliente_lista"):
            with self.subTest(rota):
                resposta = self.client.get(reverse(rota))
                self.assertContains(resposta, "data-excluir-selecionados")
                self.assertContains(resposta, 'id="form-selecionados"')

    def test_clientes(self):
        a = Cliente.objects.create(razao_social="A")
        b = Cliente.objects.create(razao_social="B")
        c = Cliente.objects.create(razao_social="C")
        resposta = self.excluir("cliente_excluir_selecionados", a, b)
        self.assertEqual(list(Cliente.objects.all()), [c])
        self.assertContains(resposta, "2 clientes excluídos.")

    def test_funcionarios_nao_exclui_o_proprio_e_leva_o_acesso(self):
        funcao = Funcao.objects.get(nome="Vendedor")
        eu = Funcionario.objects.create(nome="Eu", funcao=funcao, usuario=self.admin)
        outro_usuario = self.criar_usuario()
        outro = Funcionario.objects.create(nome="Outro", funcao=funcao, usuario=outro_usuario)
        resposta = self.excluir("funcionario_excluir_selecionados", eu, outro)
        self.assertEqual(list(Funcionario.objects.all()), [eu])
        self.assertFalse(Usuario.objects.filter(pk=outro_usuario.pk).exists())
        self.assertContains(resposta, "Eu (é o seu próprio cadastro)")

    def test_usuarios_nao_exclui_o_proprio_nem_o_master(self):
        master = self.criar_usuario(nivel=MASTER)
        outro = self.criar_usuario()
        self.excluir("usuario_excluir_selecionados", self.admin, master, outro)
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(Usuario.objects.filter(pk=master.pk).exists())  # master nem aparece na lista
        self.assertFalse(Usuario.objects.filter(pk=outro.pk).exists())

    def test_perfis_em_uso_ficam(self):
        livre = Perfil.objects.create(nome="Temporário")
        em_uso = self.perfil("Administrador")
        resposta = self.excluir("perfil_excluir_selecionados", livre, em_uso)
        self.assertFalse(Perfil.objects.filter(pk=livre.pk).exists())
        self.assertTrue(Perfil.objects.filter(pk=em_uso.pk).exists())
        self.assertContains(resposta, "em uso por 1 usuário")

    def test_empresas_so_master_e_sem_vinculos(self):
        livre = self.criar_empresa(ativa=False)
        self.assertEqual(self.excluir("empresa_excluir_selecionados", livre, follow=False).status_code, 403)
        self.client.force_login(self.criar_usuario(nivel=MASTER))
        self.assertContains(self.client.get(reverse("empresa_lista")), "data-excluir-selecionados")
        self.excluir("empresa_excluir_selecionados", livre)
        self.assertFalse(Empresa.objects.filter(pk=livre.pk).exists())

    def test_sem_nada_marcado(self):
        resposta = self.client.post(reverse("cliente_excluir_selecionados"), follow=True)
        self.assertContains(resposta, "Nenhum item selecionado.")

    def test_usuario_comum_nao_exclui_funcionarios(self):
        self.client.force_login(self.criar_usuario(nivel=COMUM, empresas=[self.empresa]))
        f = Funcionario.objects.create(nome="X", funcao=Funcao.objects.get(nome="Vendedor"))
        self.assertEqual(self.excluir("funcionario_excluir_selecionados", f, follow=False).status_code, 403)
        self.assertTrue(Funcionario.objects.filter(pk=f.pk).exists())


class ColunaCodigoTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=MASTER))

    def test_todas_as_listas_tem_codigo_ordenavel(self):
        for rota in ("empresa_lista", "funcionario_lista", "usuario_lista", "perfil_lista", "cliente_lista"):
            with self.subTest(rota):
                resposta = self.client.get(reverse(rota), {"o": "-codigo"})
                self.assertContains(resposta, 'title="Ordenar por código"')
                self.assertEqual(resposta.context["ordem"], "-codigo")

    def test_codigo_na_linha_e_ordem_decrescente(self):
        a = Cliente.objects.create(razao_social="Primeiro")
        b = Cliente.objects.create(razao_social="Segundo")
        resposta = self.client.get(reverse("cliente_lista"), {"o": "-codigo"})
        self.assertEqual([c.pk for c in resposta.context["clientes"]], [b.pk, a.pk])
        self.assertContains(resposta, f'class="block px-4 py-3">{a.pk}</a></td>')
