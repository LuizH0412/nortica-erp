from django.urls import reverse

from core.base_testes import ADMIN, COMUM, MASTER, InstanciaTestCase
from empresas.selecao import SESSAO_CHAVE

from .forms import UsuarioForm
from .models import AcessoEmpresa, Perfil


class PermissoesTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()

    def entrar_como(self, nivel):
        usuario = self.criar_usuario(nivel=nivel, empresas=[self.empresa])
        self.client.force_login(usuario)
        return usuario

    def status(self, nome, *args):
        return self.client.get(reverse(nome, args=args)).status_code

    def test_visitante_vai_para_o_login(self):
        for nome in ("empresa_lista", "usuario_lista", "perfil_lista"):
            with self.subTest(nome):
                self.assertEqual(self.status(nome), 302)

    def test_perfil_sem_configuracoes_nao_acessa_cadastros(self):
        self.entrar_como(COMUM)
        for nome, args in [
            ("empresa_lista", ()),
            ("empresa_editar", (self.empresa.pk,)),
            ("empresa_criar", ()),
            ("usuario_lista", ()),
            ("usuario_criar", ()),
            ("perfil_lista", ()),
            ("funcionario_lista", ()),
        ]:
            with self.subTest(nome):
                self.assertEqual(self.status(nome, *args), 403)

    def test_administrador_gerencia_mas_nao_cria_nem_exclui_empresa(self):
        self.entrar_como(ADMIN)
        self.assertEqual(self.status("empresa_lista"), 200)
        self.assertEqual(self.status("perfil_lista"), 200)
        self.assertEqual(self.status("empresa_criar"), 403)
        self.assertEqual(self.status("empresa_excluir", self.empresa.pk), 403)

    def test_master_cria_e_exclui_empresa(self):
        self.entrar_como(MASTER)
        self.assertEqual(self.status("empresa_criar"), 200)
        self.assertEqual(self.status("empresa_excluir", self.empresa.pk), 200)

    def test_master_nao_aparece_na_gestao_de_usuarios(self):
        master = self.criar_usuario(nivel=MASTER)
        self.entrar_como(ADMIN)
        self.assertEqual(self.status("usuario_senha", master.pk), 404)
        self.assertEqual(self.status("usuario_editar", master.pk), 404)

    def test_permissao_segue_a_empresa_atual(self):
        """Administrador na matriz e Usuário na filial."""
        filial = self.criar_empresa()
        usuario = self.criar_usuario(nivel=ADMIN, empresas=[self.empresa])
        AcessoEmpresa.objects.create(usuario=usuario, empresa=filial, perfil=self.perfil("Usuário"))
        self.client.force_login(usuario)

        self.client.post(reverse("trocar_empresa", args=[self.empresa.pk]))
        self.assertEqual(self.status("usuario_lista"), 200)

        self.client.post(reverse("trocar_empresa", args=[filial.pk]))
        self.assertEqual(self.client.session[SESSAO_CHAVE], filial.pk)
        self.assertEqual(self.status("usuario_lista"), 403)

    def test_sem_perfil_nenhum_vai_para_sem_acesso(self):
        self.client.force_login(self.criar_usuario())
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("sem_acesso"), fetch_redirect_response=False
        )


class PerfisDoUsuarioTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.matriz = self.criar_empresa()
        self.admin = self.criar_usuario(nivel=ADMIN, empresas=[self.matriz])
        self.client.force_login(self.admin)
        self.pessoa = self.criar_usuario()

    def adicionar(self, usuario, perfil, empresas):
        return self.client.post(
            reverse("usuario_acesso_adicionar", args=[usuario.pk]),
            {"perfil": perfil.pk, "empresas": [e.pk for e in empresas]},
        )

    def test_adiciona_perfil(self):
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        self.assertEqual(self.pessoa.perfil_na(self.matriz).nome, "Usuário")

    def test_nao_aceita_segundo_perfil_na_mesma_empresa(self):
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        resposta = self.adicionar(self.pessoa, self.perfil("Administrador"), [self.matriz])
        self.assertEqual(self.pessoa.acessos.count(), 1)
        self.assertEqual(self.pessoa.perfil_na(self.matriz).nome, "Usuário")  # não trocou
        mensagens = [str(m) for m in resposta.wsgi_request._messages]
        self.assertIn("Escolha só empresas em que a pessoa ainda não tem perfil de acesso.", mensagens)

    def test_pedido_misturado_nao_grava_nada(self):
        """Uma empresa nova + uma que já tem perfil: recusa tudo, sem gravar pela metade."""
        filial = self.criar_empresa()
        AcessoEmpresa.objects.create(usuario=self.admin, empresa=filial, perfil=self.perfil("Administrador"))
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz, filial])
        self.assertIsNone(self.pessoa.perfil_na(filial))

    def test_janela_mostra_empresa_ja_vinculada_travada(self):
        filial = self.criar_empresa(unidade="Filial Centro")
        AcessoEmpresa.objects.create(usuario=self.admin, empresa=filial, perfil=self.perfil("Administrador"))
        self.client.post(reverse("trocar_empresa", args=[self.matriz.pk]))  # duas empresas: escolhe uma
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        form = self.client.get(reverse("usuario_editar", args=[self.pessoa.pk])).context["form_perfil"]
        self.assertEqual(list(form.fields["empresas"].queryset), [filial])
        self.assertEqual([a.empresa for a in form.ja_vinculadas], [self.matriz])
        self.assertTrue(form.tem_empresas_livres)

    def test_sem_empresas_livres_o_botao_fica_desligado(self):
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        resposta = self.client.get(reverse("usuario_editar", args=[self.pessoa.pk]))
        self.assertFalse(resposta.context["form_perfil"].tem_empresas_livres)
        self.assertContains(resposta, "já tem perfil em todas as empresas")

    def test_nao_da_acesso_em_empresa_que_nao_administra(self):
        filial = self.criar_empresa()
        self.adicionar(self.pessoa, self.perfil("Administrador"), [filial])
        self.assertFalse(self.pessoa.acessos.exists())

    def test_ninguem_mexe_nos_proprios_perfis(self):
        self.adicionar(self.admin, self.perfil("Usuário"), [self.matriz])
        self.assertEqual(self.admin.perfil_na(self.matriz).nome, "Administrador")
        acesso = self.admin.acessos.get()
        self.client.post(reverse("usuario_acesso_remover", args=[self.admin.pk]), {"acessos": [acesso.pk]})
        self.assertTrue(self.admin.acessos.exists())

    def test_remove_selecionados(self):
        filial = self.criar_empresa()
        AcessoEmpresa.objects.create(usuario=self.admin, empresa=filial, perfil=self.perfil("Administrador"))
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz, filial])
        ids = list(self.pessoa.acessos.values_list("pk", flat=True))
        self.client.post(reverse("usuario_acesso_remover", args=[self.pessoa.pk]), {"acessos": ids})
        self.assertFalse(self.pessoa.acessos.exists())

    def test_tela_do_usuario_mostra_os_perfis(self):
        self.adicionar(self.pessoa, self.perfil("Usuário"), [self.matriz])
        resposta = self.client.get(reverse("usuario_editar", args=[self.pessoa.pk]))
        self.assertContains(resposta, "Perfis de acesso e permissões para as empresas")
        self.assertContains(resposta, self.matriz.unidade)


class CadastroDePerfisTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=ADMIN, empresas=[self.empresa]))

    def test_cria_perfil(self):
        self.client.post(reverse("perfil_criar"), {"nome": "Caixa"})
        perfil = Perfil.objects.get(nome="Caixa")
        self.assertFalse(perfil.pode_configurar)

    def test_nao_exclui_perfil_em_uso(self):
        em_uso = self.perfil("Administrador")
        self.client.post(reverse("perfil_excluir", args=[em_uso.pk]))
        self.assertTrue(Perfil.objects.filter(pk=em_uso.pk).exists())
        livre = Perfil.objects.create(nome="Temporário")
        self.client.post(reverse("perfil_excluir", args=[livre.pk]))
        self.assertFalse(Perfil.objects.filter(pk=livre.pk).exists())


class UsuarioFormTests(InstanciaTestCase):
    def test_pessoa_nao_se_desativa(self):
        admin = self.criar_usuario(nivel=ADMIN)
        form = UsuarioForm(instance=admin, usuario_logado=admin)
        self.assertTrue(form.fields["is_active"].disabled)

    def test_pode_desativar_outra_pessoa(self):
        admin, outro = self.criar_usuario(nivel=ADMIN), self.criar_usuario()
        form = UsuarioForm(instance=outro, usuario_logado=admin)
        self.assertFalse(form.fields["is_active"].disabled)
