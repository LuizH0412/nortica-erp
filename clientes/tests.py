from django.urls import reverse

from core.base_testes import ADMIN, COMUM, InstanciaTestCase
from funcionarios.models import Funcao, Funcionario

from .models import Area, Cliente, Tag, TipoCliente

CNPJ = "11.222.333/0001-81"
CPF = "529.982.247-25"


class ClienteTestCase(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.usuario = self.criar_usuario(nivel=COMUM, empresas=[self.empresa])
        self.client.force_login(self.usuario)

    def dados(self, **extra):
        dados = {
            "pessoa": "J", "documento": CNPJ, "contribuinte": "1",
            "nome_fantasia": "Loja Azul", "razao_social": "Loja Azul Comércio LTDA",
            "indicador_finalidade": "1", "ativo": "on",
        }
        dados.update(extra)
        return dados

    def cadastrar(self, **extra):
        return self.client.post(reverse("cliente_criar"), self.dados(**extra))


class CadastroTests(ClienteTestCase):
    def test_usuario_comum_cadastra_cliente(self):
        resposta = self.cadastrar()
        c = Cliente.objects.get()
        # Salvar continua no cadastro (não volta para a lista)
        self.assertRedirects(resposta, reverse("cliente_editar", args=[c.pk]), fetch_redirect_response=False)
        self.assertEqual(c.documento, "11222333000181")
        self.assertEqual(c.cadastrado_por, self.usuario)

    def test_pessoa_fisica_com_cpf_sem_fantasia(self):
        self.cadastrar(pessoa="F", documento=CPF, nome_fantasia="", razao_social="Maria Souza")
        c = Cliente.objects.get()
        self.assertTrue(c.eh_pessoa_fisica)
        self.assertEqual(str(c), "Maria Souza")

    def test_documento_tem_que_combinar_com_a_pessoa(self):
        resposta = self.cadastrar(pessoa="F", documento=CNPJ)
        self.assertFormError(resposta.context["form"], "documento", "CPF inválido.")
        resposta = self.cadastrar(pessoa="J", documento=CPF)
        self.assertFormError(resposta.context["form"], "documento", "CNPJ inválido.")

    def test_documento_e_opcional_mas_nao_repete(self):
        self.cadastrar(documento="", razao_social="Sem documento")
        self.cadastrar(documento="", razao_social="Outro sem documento")
        self.assertEqual(Cliente.objects.count(), 2)
        self.cadastrar()
        resposta = self.cadastrar(razao_social="Outra")
        self.assertFormError(resposta.context["form"], "documento", "Já existe um cliente com este CPF/CNPJ.")

    def test_pessoa_juridica_exige_nome_fantasia(self):
        resposta = self.cadastrar(nome_fantasia="")
        self.assertFormError(resposta.context["form"], "nome_fantasia", "Informe o nome fantasia.")

    def test_tipo_consumidor_vem_marcado(self):
        form = self.client.get(reverse("cliente_criar")).context["form"]
        self.assertEqual(form.initial["tipo_cliente"], TipoCliente.objects.get(nome="Consumidor").pk)

    def test_tags_e_cadastros_simples_desativados(self):
        vip, antiga = Tag.objects.create(nome="VIP"), Tag.objects.create(nome="Antiga")
        self.cadastrar(tags=[vip.pk, antiga.pk])
        c = Cliente.objects.get()
        self.assertEqual(set(c.tags.all()), {vip, antiga})
        antiga.ativo = False
        antiga.save()
        # Novo cliente não vê a TAG desativada; quem já tem continua vendo
        self.assertNotIn(antiga, self.client.get(reverse("cliente_criar")).context["form"].fields["tags"].queryset)
        self.assertIn(antiga, self.client.get(reverse("cliente_editar", args=[c.pk])).context["form"].fields["tags"].queryset)

    def test_excluir(self):
        self.cadastrar()
        c = Cliente.objects.get()
        self.client.post(reverse("cliente_excluir", args=[c.pk]))
        self.assertFalse(Cliente.objects.exists())


class AtendenteTests(ClienteTestCase):
    def setUp(self):
        super().setUp()
        self.vendedor = Funcao.objects.get(nome="Vendedor")
        self.entregador = Funcao.objects.get(nome="Entregador")

    def test_ja_vem_quem_esta_cadastrando(self):
        eu = Funcionario.objects.create(nome="Alvarenga", funcao=self.vendedor, usuario=self.usuario)
        form = self.client.get(reverse("cliente_criar")).context["form"]
        self.assertEqual(form.initial["atendente"], eu.pk)

    def test_so_atendentes_e_vendedores_ativos(self):
        Funcionario.objects.create(nome="Ana", funcao=Funcao.objects.get(nome="Atendente"))
        Funcionario.objects.create(nome="Bruno", funcao=self.vendedor)
        Funcionario.objects.create(nome="Carlos", funcao=self.entregador)
        Funcionario.objects.create(nome="Davi", funcao=self.vendedor, ativo=False)
        form = self.client.get(reverse("cliente_criar")).context["form"]
        nomes = [f.nome for f in form.fields["atendente"].queryset]
        self.assertEqual(nomes, ["Ana", "Bruno"])


class ListaTests(ClienteTestCase):
    def test_busca_e_desativados(self):
        self.cadastrar()
        self.cadastrar(documento="", razao_social="Mercado Verde LTDA", nome_fantasia="Mercado Verde", ativo="")
        nomes = lambda **p: [c.nome_exibicao for c in self.client.get(reverse("cliente_lista"), p).context["clientes"]]
        self.assertEqual(nomes(), ["Loja Azul"])
        self.assertEqual(nomes(desativados="1"), ["Mercado Verde"])
        self.assertEqual(nomes(q="11.222.333"), ["Loja Azul"])
        self.assertEqual(nomes(q="verde"), [])


class CadastrosSimplesDoClienteTests(ClienteTestCase):
    def test_usuario_comum_gerencia_tipos_areas_e_tags(self):
        for tipo, modelo in (("tipo_cliente", TipoCliente), ("area", Area), ("tag", Tag)):
            with self.subTest(tipo):
                r = self.client.post(reverse("cadastro_simples_criar", args=[tipo]), {"nome": "Novo " + tipo}).json()
                self.assertTrue(r["ok"])
                self.assertTrue(modelo.objects.filter(nome="Novo " + tipo).exists())

    def test_mas_funcoes_continuam_so_para_configuracao(self):
        self.assertEqual(self.client.get(reverse("cadastro_simples_lista", args=["funcao"])).status_code, 403)

    def test_tag_em_uso_nao_exclui(self):
        vip = Tag.objects.create(nome="VIP")
        self.cadastrar(tags=[vip.pk])
        r = self.client.post(reverse("cadastro_simples_excluir", args=["tag", vip.pk]))
        self.assertEqual(r.status_code, 409)
        self.assertIn("1 cliente", r.json()["mensagem"])

    def test_tela_tem_os_botoes_de_gerenciar(self):
        resposta = self.client.get(reverse("cliente_criar"))
        self.assertContains(resposta, "data-gerenciar", count=3)
        self.assertContains(resposta, 'id="pilulas_tags"')


class MenuTests(InstanciaTestCase):
    def test_clientes_aparece_para_todos(self):
        empresa = self.criar_empresa()
        for nivel in (COMUM, ADMIN):
            with self.subTest(nivel):
                self.client.force_login(self.criar_usuario(nivel=nivel, empresas=[empresa]))
                self.assertContains(self.client.get(reverse("home")), reverse("cliente_lista"))


class OutrosEnderecosTests(ClienteTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.cliente = Cliente.objects.get()
        from localidades.models import Municipio
        self.cidade = Municipio.objects.create(codigo_ibge="9999901", nome="Cidade Teste", uf="MT")

    def endereco(self, **extra):
        dados = {
            "end-tipo": "entrega", "end-cep": "78053-500", "end-numero": "100",
            "end-logradouro": "Avenida Principal", "end-bairro": "Centro", "end-municipio": self.cidade.pk,
        }
        dados.update(extra)
        return dados

    def test_adiciona_e_volta_na_aba(self):
        resposta = self.client.post(reverse("cliente_endereco_novo", args=[self.cliente.pk]), self.endereco())
        self.assertRedirects(
            resposta, reverse("cliente_editar", args=[self.cliente.pk]) + "#enderecos", fetch_redirect_response=False
        )
        e = self.cliente.enderecos.get()
        self.assertEqual((e.tipo, e.cep, e.municipio), ("entrega", "78053500", self.cidade))

    def test_campos_obrigatorios_reabrem_a_janela(self):
        resposta = self.client.post(
            reverse("cliente_endereco_novo", args=[self.cliente.pk]),
            self.endereco(**{"end-numero": "", "end-municipio": ""}),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["abrir_endereco"])
        form = resposta.context["endereco_form"]
        self.assertIn("numero", form.errors)
        self.assertIn("municipio", form.errors)
        self.assertFalse(self.cliente.enderecos.exists())

    def test_edita_e_exclui(self):
        self.client.post(reverse("cliente_endereco_novo", args=[self.cliente.pk]), self.endereco())
        e = self.cliente.enderecos.get()
        self.client.post(
            reverse("cliente_endereco_editar", args=[self.cliente.pk, e.pk]),
            self.endereco(**{"end-tipo": "cobranca", "end-numero": "200"}),
        )
        e.refresh_from_db()
        self.assertEqual((e.tipo, e.numero), ("cobranca", "200"))
        self.client.post(reverse("cliente_endereco_excluir", args=[self.cliente.pk, e.pk]))
        self.assertFalse(self.cliente.enderecos.exists())

    def test_nao_mexe_em_endereco_de_outro_cliente(self):
        self.client.post(reverse("cliente_endereco_novo", args=[self.cliente.pk]), self.endereco())
        e = self.cliente.enderecos.get()
        self.cadastrar(documento="", razao_social="Outro cliente")
        outro = Cliente.objects.get(razao_social="Outro cliente")
        resposta = self.client.post(reverse("cliente_endereco_excluir", args=[outro.pk, e.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(self.cliente.enderecos.exists())

    def test_aba_lista_os_enderecos_e_tem_a_janela(self):
        self.client.post(reverse("cliente_endereco_novo", args=[self.cliente.pk]), self.endereco())
        resposta = self.client.get(reverse("cliente_editar", args=[self.cliente.pk]))
        self.assertContains(resposta, 'id="dialogo-endereco"')
        self.assertContains(resposta, "Avenida Principal, 100")
        self.assertContains(resposta, 'data-confirmar-titulo="Excluir endereço?"')

    def test_cliente_novo_pede_para_salvar_antes(self):
        resposta = self.client.get(reverse("cliente_criar"))
        self.assertContains(resposta, "Salve os dados cadastrais do cliente primeiro")
        self.assertNotContains(resposta, 'id="dialogo-endereco"')


class FinanceiroTests(ClienteTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.cliente = Cliente.objects.get()

    def test_resumo_calcula_disponivel_e_utilizacao(self):
        from decimal import Decimal
        from .financeiro import ResumoFinanceiro
        r = ResumoFinanceiro(cliente=self.cliente, limite=Decimal("1000"), em_aberto=Decimal("750"))
        self.assertEqual(r.disponivel, Decimal("250"))
        self.assertEqual(r.utilizacao, 75)
        self.assertEqual(ResumoFinanceiro(cliente=self.cliente, limite=Decimal("100"), em_aberto=Decimal("300")).disponivel, 0)
        self.assertEqual(ResumoFinanceiro(cliente=self.cliente).utilizacao, 0)

    def test_situacao(self):
        from .financeiro import ResumoFinanceiro
        self.assertEqual(ResumoFinanceiro(cliente=self.cliente).situacao, "em_dia")
        self.assertEqual(ResumoFinanceiro(cliente=self.cliente, parcelas_vencidas=2).situacao, "inadimplente")
        self.cliente.bloqueado = True
        self.assertEqual(ResumoFinanceiro(cliente=self.cliente).situacao, "bloqueado")

    def test_aba_mostra_limite_formatado(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(limite_credito=1500)
        resposta = self.client.get(reverse("cliente_editar", args=[self.cliente.pk]))
        self.assertContains(resposta, "Cliente em dia")
        self.assertContains(resposta, "R$ 1.500,00")

    def test_usuario_comum_ve_mas_nao_altera_credito(self):
        resposta = self.client.get(reverse("cliente_editar", args=[self.cliente.pk]))
        self.assertNotContains(resposta, 'id="dialogo-credito"')
        r = self.client.post(reverse("cliente_credito", args=[self.cliente.pk]), {"credito-limite_credito": "999"})
        self.assertEqual(r.status_code, 403)
        for nome in ("cliente_credito_painel", "cliente_credito_lancar"):
            with self.subTest(nome):
                metodo = self.client.get if nome.endswith("painel") else self.client.post
                self.assertEqual(metodo(reverse(nome, args=[self.cliente.pk])).status_code, 403)

    def test_administrador_altera_limite_e_bloqueio(self):
        admin = self.criar_usuario(nivel=ADMIN, empresas=[self.empresa])
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("cliente_editar", args=[self.cliente.pk])), 'id="dialogo-credito"')
        resposta = self.client.post(
            reverse("cliente_credito", args=[self.cliente.pk]),
            {"credito-limite_credito": "2.500,50", "credito-bloqueado": "on"},
        )
        self.assertEqual(resposta["HX-Trigger"], "credito-alterado")
        self.assertContains(resposta, "Limite de crédito atualizado.")
        self.cliente.refresh_from_db()
        self.assertEqual(str(self.cliente.limite_credito), "2500.50")
        self.assertTrue(self.cliente.bloqueado)
        self.assertContains(self.client.get(reverse("cliente_editar", args=[self.cliente.pk])), "Cliente bloqueado")

    def test_filtro_moeda(self):
        from empresas.templatetags.formatos import moeda
        self.assertEqual(moeda(1234.5), "R$ 1.234,50")
        self.assertEqual(moeda(0), "R$ 0,00")
        self.assertEqual(moeda(-10), "-R$ 10,00")


class GerenciarCreditoTests(ClienteTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.cliente = Cliente.objects.get()
        self.client.force_login(self.criar_usuario(nivel=ADMIN, empresas=[self.empresa]))

    def lancar(self, valor, pedido=""):
        return self.client.post(
            reverse("cliente_credito_lancar", args=[self.cliente.pk]),
            {"lancar-valor": valor, "lancar-pedido": pedido},
        )

    def test_lanca_credito_e_soma_no_saldo(self):
        from decimal import Decimal
        from .financeiro import saldo_credito
        from .models import MovimentoCredito
        resposta = self.lancar("10,00", pedido="123")
        self.assertEqual(resposta["HX-Trigger"], "credito-alterado")
        self.assertContains(resposta, "Crédito de R$ 10,00 lançado.")
        self.lancar("1.000,50")
        self.assertEqual(saldo_credito(self.cliente), Decimal("1010.50"))
        m = self.cliente.movimentos_credito.get(pedido="123")
        self.assertEqual(m.tipo, "C")
        self.assertIsNotNone(m.usuario)  # registra quem lançou
        # Débito (uso numa venda, no futuro) desconta do saldo
        MovimentoCredito.objects.create(cliente=self.cliente, tipo="D", valor=Decimal("0.50"))
        self.assertEqual(saldo_credito(self.cliente), Decimal("1010.00"))

    def test_valor_obrigatorio_e_positivo(self):
        for valor in ("", "0", "-5"):
            with self.subTest(valor=valor):
                resposta = self.lancar(valor)
                self.assertFalse(resposta.has_header("HX-Trigger"))
                self.assertTrue(resposta.context["lancar_form"].errors)
        self.assertFalse(self.cliente.movimentos_credito.exists())

    def test_painel_mostra_extrato_do_periodo(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import MovimentoCredito
        self.lancar("25,00")
        antigo = MovimentoCredito.objects.create(cliente=self.cliente, tipo="C", valor=5, descricao="Antigo")
        MovimentoCredito.objects.filter(pk=antigo.pk).update(criado_em=timezone.now() - timedelta(days=90))

        resposta = self.client.get(reverse("cliente_credito_painel", args=[self.cliente.pk]))
        extrato = resposta.context["extrato"]
        self.assertEqual(len(extrato.movimentos), 1)  # só o do mês atual
        self.assertEqual(str(extrato.saldo), "25.00")
        self.assertContains(resposta, "Crédito do cliente")
        self.assertContains(resposta, "R$ 30,00")  # saldo total (indicador) inclui o antigo

        hoje = timezone.localdate()
        resposta = self.client.get(
            reverse("cliente_credito_painel", args=[self.cliente.pk]),
            {"de": (hoje - timedelta(days=120)).isoformat(), "ate": hoje.isoformat()},
        )
        self.assertEqual(len(resposta.context["extrato"].movimentos), 2)

    def test_aba_financeiro_mostra_o_saldo_de_credito(self):
        self.lancar("40,00")
        resposta = self.client.get(reverse("cliente_editar", args=[self.cliente.pk]))
        self.assertEqual(str(resposta.context["financeiro"].saldo_credito_loja), "40.00")


class ContatosTests(ClienteTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.cliente = Cliente.objects.get()

    def contato(self, **extra):
        dados = {"con-tipo": "principal", "con-nome": "Maria", "con-ddd": "65", "con-telefone": "99681-5377", "con-email": ""}
        dados.update(extra)
        return self.client.post(reverse("cliente_contato_novo", args=[self.cliente.pk]), dados)

    def test_adiciona_e_volta_na_aba(self):
        resposta = self.contato(**{"con-email": "maria@loja.com"})
        self.assertRedirects(
            resposta, reverse("cliente_editar", args=[self.cliente.pk]) + "#contatos", fetch_redirect_response=False
        )
        c = self.cliente.contatos.get()
        self.assertEqual((c.ddd, c.telefone, c.telefone_formatado), ("65", "996815377", "(65) 99681-5377"))

    def test_valida_ddd_e_telefone(self):
        resposta = self.contato(**{"con-ddd": "6", "con-telefone": "1234"})
        form = resposta.context["contato_form"]
        self.assertEqual(form.errors["ddd"], ["DDD inválido."])
        self.assertIn("telefone", form.errors)
        self.assertTrue(resposta.context["abrir_contato"])
        self.assertFalse(self.cliente.contatos.exists())

    def test_campos_obrigatorios(self):
        form = self.contato(**{"con-nome": "", "con-ddd": "", "con-telefone": ""}).context["contato_form"]
        self.assertEqual(set(form.errors), {"nome", "ddd", "telefone"})

    def test_so_um_principal(self):
        self.contato(**{"con-nome": "Maria"})
        resposta = self.client.post(
            reverse("cliente_contato_novo", args=[self.cliente.pk]),
            {"con-tipo": "principal", "con-nome": "João", "con-ddd": "65", "con-telefone": "3333-4444"}, follow=True,
        )
        self.assertContains(resposta, "Maria passou para Outros")
        tipos = dict(self.cliente.contatos.values_list("nome", "tipo"))
        self.assertEqual(tipos, {"Maria": "outros", "João": "principal"})

    def test_edita_e_exclui(self):
        self.contato()
        c = self.cliente.contatos.get()
        self.client.post(
            reverse("cliente_contato_editar", args=[self.cliente.pk, c.pk]),
            {"con-tipo": "outros", "con-nome": "Maria Souza", "con-ddd": "65", "con-telefone": "3333-4444"},
        )
        c.refresh_from_db()
        self.assertEqual((c.nome, c.tipo, c.telefone), ("Maria Souza", "outros", "33334444"))
        self.client.post(reverse("cliente_contato_excluir", args=[self.cliente.pk, c.pk]))
        self.assertFalse(self.cliente.contatos.exists())

    def test_aba_lista_e_tem_a_janela(self):
        self.contato(**{"con-email": "maria@loja.com"})
        resposta = self.client.get(reverse("cliente_editar", args=[self.cliente.pk]))
        self.assertContains(resposta, 'id="dialogo-contato"')
        self.assertContains(resposta, "(65) 99681-5377")
        self.assertContains(resposta, "mailto:maria@loja.com")
        self.assertContains(resposta, 'data-confirmar-titulo="Excluir contato?"')

    def test_principal_aparece_primeiro(self):
        self.contato(**{"con-tipo": "outros", "con-nome": "Ana"})
        self.contato(**{"con-tipo": "principal", "con-nome": "Zeca"})
        self.assertEqual([c.nome for c in self.cliente.contatos.all()], ["Zeca", "Ana"])
