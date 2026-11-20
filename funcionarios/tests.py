from django.urls import reverse
from django_tenants.test.client import TenantClient

from contas.models import AcessoEmpresa, Usuario
from core.base_testes import ADMIN, SENHA_TESTE, InstanciaTestCase

from .models import Funcao, Funcionario, Setor

SENHA_NOVA = "Acesso-Forte-2026"


class FuncionarioTestCase(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.admin = self.criar_usuario(nivel=ADMIN, empresas=[self.empresa])
        self.client.force_login(self.admin)
        self.funcao = Funcao.objects.get(nome="Vendedor")  # função padrão (migração)

    def dados(self, **extra):
        dados = {
            "nome": "Maria Souza",
            "funcao": self.funcao.pk,
            "cpf": "529.982.247-25",
            "desconto_maximo": "10,00",
            "comissao": "2,50",
            "ativo": "on",
        }
        dados.update(extra)
        return dados

    def criar_funcionario(self, **extra):
        self.client.post(reverse("funcionario_criar"), self.dados(**extra))
        return Funcionario.objects.get(nome=extra.get("nome", "Maria Souza"))

    def salvar_usuario(self, funcionario, email="maria@loja.com", senha=SENHA_NOVA):
        return self.client.post(
            reverse("funcionario_usuario", args=[funcionario.pk]),
            {"email": email, "password1": senha, "password2": senha},
        )


class CadastroTests(FuncionarioTestCase):
    def test_cadastra_e_abre_a_aba_usuario(self):
        resposta = self.client.post(reverse("funcionario_criar"), self.dados())
        f = Funcionario.objects.get()
        self.assertRedirects(
            resposta, reverse("funcionario_editar", args=[f.pk]) + "#usuario",
            fetch_redirect_response=False,
        )
        self.assertEqual(f.cpf, "52998224725")
        self.assertEqual(str(f.desconto_maximo), "10.00")
        self.assertIsNone(f.usuario)

    def test_desconto_e_comissao_em_branco_valem_zero(self):
        f = self.criar_funcionario(desconto_maximo="", comissao="")
        self.assertEqual(f.desconto_maximo, 0)
        self.assertEqual(f.comissao, 0)

    def test_cpf_invalido_e_repetido(self):
        resposta = self.client.post(reverse("funcionario_criar"), self.dados(cpf="111.111.111-11"))
        self.assertFormError(resposta.context["form"], "cpf", "CPF inválido.")
        self.criar_funcionario()
        resposta = self.client.post(reverse("funcionario_criar"), self.dados(nome="Outra"))
        self.assertFormError(resposta.context["form"], "cpf", "Já existe um funcionário com este CPF.")

    def test_supervisor_precisa_de_cartao_que_fica_protegido(self):
        resposta = self.client.post(reverse("funcionario_criar"), self.dados(supervisor="on"))
        self.assertFormError(resposta.context["form"], "cartao", "Informe o número do cartão do supervisor.")
        f = self.criar_funcionario(supervisor="on", cartao="123456")
        self.assertNotEqual(f.cartao_supervisor, "123456")
        self.assertTrue(f.confere_cartao("123456"))
        self.assertFalse(f.confere_cartao("654321"))

    def test_demissao_antes_da_admissao(self):
        resposta = self.client.post(
            reverse("funcionario_criar"),
            self.dados(data_admissao="2026-05-10", data_demissao="2026-01-01"),
        )
        self.assertIn("data_demissao", resposta.context["form"].errors)


class UsuarioDoFuncionarioTests(FuncionarioTestCase):
    def setUp(self):
        super().setUp()
        self.funcionario = self.criar_funcionario()

    def test_cria_usuario_que_so_entra_depois_de_ganhar_perfil(self):
        self.salvar_usuario(self.funcionario, email="Maria@Loja.com")
        self.funcionario.refresh_from_db()
        usuario = self.funcionario.usuario
        self.assertEqual(usuario.email, "maria@loja.com")
        self.assertEqual(usuario.first_name, "Maria Souza")

        # Sem perfil: entra, mas cai em "sem acesso"
        outro = TenantClient(self.tenant)
        outro.post(reverse("login"), {"username": "MARIA@loja.com", "password": SENHA_NOVA})
        self.assertRedirects(outro.get(reverse("home")), reverse("sem_acesso"), fetch_redirect_response=False)

        # Com perfil na empresa: entra normalmente
        self.client.post(
            reverse("usuario_acesso_adicionar", args=[usuario.pk]),
            {"perfil": self.perfil("Usuário").pk, "empresas": [self.empresa.pk]},
        )
        self.assertEqual(outro.get(reverse("home")).status_code, 200)

    def test_usuario_novo_precisa_de_senha(self):
        resposta = self.salvar_usuario(self.funcionario, senha="")
        self.assertIn("password1", resposta.context["usuario_form"].errors)
        self.assertIsNone(Funcionario.objects.get(pk=self.funcionario.pk).usuario)

    def test_aceita_qualquer_login_e_qualquer_senha(self):
        resposta = self.salvar_usuario(self.funcionario, email="Maria", senha="123")
        self.assertEqual(resposta.status_code, 302)
        usuario = Funcionario.objects.get(pk=self.funcionario.pk).usuario
        self.assertEqual(usuario.email, "maria")
        AcessoEmpresa.objects.create(usuario=usuario, empresa=self.empresa, perfil=self.perfil("Usuário"))
        outro = TenantClient(self.tenant)
        self.assertTrue(outro.login(username="MARIA", password="123"))

    def test_senhas_diferentes_ainda_sao_recusadas(self):
        resposta = self.client.post(
            reverse("funcionario_usuario", args=[self.funcionario.pk]),
            {"email": "maria", "password1": "123", "password2": "124"},
        )
        self.assertFormError(resposta.context["usuario_form"], "password2", "As senhas não conferem.")

    def test_email_repetido(self):
        resposta = self.salvar_usuario(self.funcionario, email=self.admin.email)
        self.assertFormError(resposta.context["usuario_form"], "email", "Já existe um usuário com este e-mail.")

    def test_editar_sem_senha_mantem_a_senha(self):
        self.salvar_usuario(self.funcionario)
        self.salvar_usuario(self.funcionario, email="maria.souza@loja.com", senha="")
        usuario = Usuario.objects.get(email="maria.souza@loja.com")
        self.assertTrue(usuario.check_password(SENHA_NOVA))

    def test_desativar_funcionario_bloqueia_o_usuario(self):
        self.salvar_usuario(self.funcionario)
        dados = self.dados()
        del dados["ativo"]
        self.client.post(reverse("funcionario_editar", args=[self.funcionario.pk]), dados)
        self.assertFalse(Usuario.objects.get(email="maria@loja.com").is_active)

    def test_desvincular_bloqueia_e_tira_os_perfis(self):
        self.salvar_usuario(self.funcionario)
        usuario = Usuario.objects.get(email="maria@loja.com")
        AcessoEmpresa.objects.create(usuario=usuario, empresa=self.empresa, perfil=self.perfil("Usuário"))
        self.client.post(reverse("funcionario_desvincular", args=[self.funcionario.pk]))
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.acessos.exists())
        self.assertIsNone(Funcionario.objects.get(pk=self.funcionario.pk).usuario)

    def test_ninguem_desvincula_ou_exclui_a_si_mesmo(self):
        self.funcionario.usuario = self.admin
        self.funcionario.save()
        self.client.post(reverse("funcionario_desvincular", args=[self.funcionario.pk]))
        self.assertEqual(Funcionario.objects.get(pk=self.funcionario.pk).usuario, self.admin)
        resposta = self.client.get(reverse("funcionario_excluir", args=[self.funcionario.pk]))
        self.assertEqual(resposta.status_code, 302)

    def test_excluir_funcionario_remove_o_usuario(self):
        self.salvar_usuario(self.funcionario)
        self.client.post(reverse("funcionario_excluir", args=[self.funcionario.pk]))
        self.assertFalse(Funcionario.objects.exists())
        self.assertFalse(Usuario.objects.filter(email="maria@loja.com").exists())

    def test_aba_usuario_mostra_perfis(self):
        self.salvar_usuario(self.funcionario)
        resposta = self.client.get(reverse("funcionario_editar", args=[self.funcionario.pk]))
        self.assertContains(resposta, "Dados do usuário")
        self.assertContains(resposta, "Perfis de acesso e permissões para as empresas")
        self.assertContains(resposta, "depois que você adicionar os perfis")


class LoginTests(InstanciaTestCase):
    def test_login_por_email_ignora_maiusculas(self):
        empresa = self.criar_empresa()
        usuario = self.criar_usuario(empresas=[empresa])
        self.assertTrue(self.client.login(username=usuario.email.upper(), password=SENHA_TESTE))

    def test_usuario_comum_nao_acessa_funcionarios(self):
        empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(empresas=[empresa]))
        for nome in ("funcionario_lista", "funcionario_criar"):
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
        self.assertEqual(self.client.post(reverse("cadastro_simples_criar", args=["funcao"]), {"nome": "X"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("cadastro_simples_lista", args=["funcao"])).status_code, 403)


class FuncoesPadraoTests(InstanciaTestCase):
    def test_instancia_ja_vem_com_as_funcoes_padrao(self):
        nomes = set(Funcao.objects.values_list("nome", flat=True))
        self.assertTrue({"Vendedor", "Atendente", "Entregador"} <= nomes)

    def test_aparecem_no_cadastro_de_funcionario(self):
        empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=ADMIN, empresas=[empresa]))
        resposta = self.client.get(reverse("funcionario_criar"))
        for nome in ("Vendedor", "Atendente", "Entregador"):
            self.assertContains(resposta, f">{nome}</option>")


class JanelaDeFuncoesESetoresTests(FuncionarioTestCase):
    """Janela aberta pelo "+": pesquisa, cadastra, renomeia, ativa/desativa e exclui (JSON)."""

    def url(self, nome, tipo="funcao", pk=None):
        return reverse(nome, args=[tipo] if pk is None else [tipo, pk])

    def lista(self, tipo="funcao", q=""):
        return self.client.get(self.url("cadastro_simples_lista", tipo), {"q": q}).json()["itens"]

    def test_lista_e_pesquisa(self):
        nomes = [i["nome"] for i in self.lista()]
        self.assertTrue({"Vendedor", "Atendente", "Entregador"} <= set(nomes))
        self.assertEqual([i["nome"] for i in self.lista(q="entreg")], ["Entregador"])

    def test_lista_mostra_quantos_usam(self):
        self.criar_funcionario()
        vendedor = next(i for i in self.lista() if i["nome"] == "Vendedor")
        self.assertEqual(vendedor["uso"], 1)

    def test_cadastra_ja_ativo_e_recusa_repetido(self):
        r = self.client.post(self.url("cadastro_simples_criar"), {"nome": "Caixa"}).json()
        self.assertTrue(r["ok"])
        self.assertTrue(Funcao.objects.get(nome="Caixa").ativo)
        r = self.client.post(self.url("cadastro_simples_criar"), {"nome": "caixa"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["mensagem"], "Já existe uma função com este nome.")

    def test_renomeia_sem_mudar_se_esta_ativo(self):
        r = self.client.post(self.url("cadastro_simples_salvar", pk=self.funcao.pk), {"nome": "Vendedor Externo"}).json()
        self.assertEqual(r["item"]["nome"], "Vendedor Externo")
        self.funcao.refresh_from_db()
        self.assertTrue(self.funcao.ativo)

    def test_desativa_e_some_das_opcoes_mas_fica_em_quem_usa(self):
        f = self.criar_funcionario()
        r = self.client.post(self.url("cadastro_simples_salvar", pk=self.funcao.pk), {"ativo": "0"}).json()
        self.assertFalse(r["item"]["ativo"])
        self.funcao.refresh_from_db()
        self.assertEqual(self.funcao.nome, "Vendedor")
        self.assertNotContains(self.client.get(reverse("funcionario_criar")), ">Vendedor</option>")
        self.assertContains(self.client.get(reverse("funcionario_editar", args=[f.pk])), ">Vendedor</option>")

    def test_exclui_sem_uso(self):
        caixa = Funcao.objects.create(nome="Caixa")
        r = self.client.post(self.url("cadastro_simples_excluir", pk=caixa.pk)).json()
        self.assertTrue(r["ok"])
        self.assertFalse(Funcao.objects.filter(pk=caixa.pk).exists())

    def test_nao_exclui_em_uso(self):
        self.criar_funcionario()
        r = self.client.post(self.url("cadastro_simples_excluir", pk=self.funcao.pk))
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()["em_uso"])
        self.assertTrue(Funcao.objects.filter(pk=self.funcao.pk).exists())

    def test_setores_funcionam_igual(self):
        r = self.client.post(self.url("cadastro_simples_criar", "setor"), {"nome": "Loja"}).json()
        self.client.post(self.url("cadastro_simples_excluir", "setor", r["item"]["id"]))
        self.assertFalse(Setor.objects.exists())

    def test_tipo_invalido_nao_existe(self):
        self.assertEqual(self.client.get("/cadastros/senha/lista/").status_code, 404)

    def test_tela_do_funcionario_tem_a_janela(self):
        resposta = self.client.get(reverse("funcionario_criar"))
        self.assertContains(resposta, 'id="gerenciador"')
        self.assertContains(resposta, "data-gerenciar", count=2)
