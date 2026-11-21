from decimal import Decimal

from django.urls import reverse

from core.base_testes import COMUM, InstanciaTestCase

from .models import Grupo, Produto, Subgrupo, UnidadeMedida
from .validators import gtin_valido

EAN = "7891000100103"  # EAN-13 válido


class ProdutoTestCase(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=COMUM, empresas=[self.empresa]))
        self.grupo = Grupo.objects.create(nome="Bebidas")
        self.subgrupo = Subgrupo.objects.create(nome="Refrigerantes", grupo=self.grupo)
        self.un = UnidadeMedida.objects.get(nome="UN")

    def dados(self, **extra):
        dados = {
            "descricao": "Refrigerante Cola 2L", "grupo": self.grupo.pk, "subgrupo": self.subgrupo.pk,
            "unidade": self.un.pk, "preco_compra": "5,00", "tipo_margem": "percentual", "margem_lucro": "50,00",
            "preco_venda": "7,50", "comissao": "1,00", "vender": "on", "controlar_estoque": "on", "ativo": "on",
            "empresas": [self.empresa.pk],
        }
        dados.update(extra)
        return dados

    def cadastrar(self, **extra):
        return self.client.post(reverse("produto_criar"), self.dados(**extra))


class ProdutoTests(ProdutoTestCase):
    def test_cadastra(self):
        resposta = self.cadastrar(codigo_interno="ABC-1", codigo_barras=EAN, peso="1,250")
        p = Produto.objects.get()
        self.assertRedirects(resposta, reverse("produto_editar", args=[p.pk]), fetch_redirect_response=False)
        self.assertEqual((p.codigo_interno, p.codigo_barras, p.peso), ("ABC-1", EAN, Decimal("1.250")))
        self.assertEqual(p.codigo, str(p.pk))  # código resumido, sem zeros à esquerda
        self.assertEqual(p.altura, 0)  # opcional em branco vale zero

    def test_valores_no_formato_brasileiro(self):
        self.cadastrar(preco_compra="1.234,56", preco_venda="2.000,00")
        p = Produto.objects.get()
        self.assertEqual((p.preco_compra, p.preco_venda), (Decimal("1234.56"), Decimal("2000.00")))

    def test_preco_sugerido(self):
        p = Produto(preco_compra=Decimal("10"), margem_lucro=Decimal("35"))
        self.assertEqual(p.preco_sugerido, Decimal("13.50"))
        p.tipo_margem = Produto.TipoMargem.VALOR
        self.assertEqual(p.preco_sugerido, Decimal("45.00"))

    def test_codigo_de_barras_valida_e_nao_repete(self):
        self.assertTrue(gtin_valido(EAN))
        self.assertFalse(gtin_valido("7891000100104"))
        resposta = self.cadastrar(codigo_barras="7891000100104")
        self.assertIn("codigo_barras", resposta.context["form"].errors)
        self.cadastrar(codigo_barras=EAN)
        resposta = self.cadastrar(codigo_barras=EAN, descricao="Outro")
        self.assertFormError(resposta.context["form"], "codigo_barras", "Já existe um produto com este código de barras.")

    def test_codigo_interno_nao_repete_nem_com_outra_caixa(self):
        self.cadastrar(codigo_interno="abc-1")
        resposta = self.cadastrar(codigo_interno="ABC-1", descricao="Outro")
        self.assertFormError(resposta.context["form"], "codigo_interno", "Já existe um produto com este código interno.")

    def test_subgrupo_precisa_ser_do_grupo(self):
        outro = Grupo.objects.create(nome="Limpeza")
        resposta = self.cadastrar(grupo=outro.pk)
        self.assertIn("subgrupo", resposta.context["form"].errors)

    def test_precos_e_comissao_sao_opcionais(self):
        resposta = self.cadastrar(preco_compra="", margem_lucro="", preco_venda="", comissao="")
        p = Produto.objects.get()
        self.assertRedirects(resposta, reverse("produto_editar", args=[p.pk]), fetch_redirect_response=False)
        self.assertEqual((p.preco_compra, p.margem_lucro, p.preco_venda, p.comissao), (0, 0, 0, 0))
        form = self.client.get(reverse("produto_criar")).context["form"]
        for campo in ("preco_compra", "margem_lucro", "preco_venda", "comissao"):
            self.assertFalse(form.fields[campo].required)

    def test_clonar(self):
        self.cadastrar(codigo_interno="ABC-1", codigo_barras=EAN)
        origem = Produto.objects.get()
        form = self.client.get(reverse("produto_criar"), {"clonar": origem.pk}).context["form"]
        self.assertEqual(form.initial["descricao"], "Refrigerante Cola 2L (cópia)")
        self.assertEqual(form.initial["grupo"], self.grupo.pk)
        self.assertNotIn("codigo_barras", form.initial)
        self.assertNotIn("codigo_interno", form.initial)

    def test_lista_busca_por_codigo_descricao_e_barras(self):
        self.cadastrar(codigo_barras=EAN)
        p = Produto.objects.get()
        nomes = lambda q: [x.pk for x in self.client.get(reverse("produto_lista"), {"q": q}).context["produtos"]]
        self.assertEqual(nomes("cola"), [p.pk])
        self.assertEqual(nomes(EAN), [p.pk])
        self.assertEqual(nomes(p.codigo), [p.pk])
        self.assertEqual(nomes(f"{p.pk:07d}"), [p.pk])  # com zeros à esquerda também acha

    def test_excluir_e_excluir_selecionados(self):
        self.cadastrar()
        self.cadastrar(descricao="Outro")
        a, b = Produto.objects.order_by("pk")
        self.client.post(reverse("produto_excluir", args=[a.pk]))
        self.client.post(reverse("produto_excluir_selecionados"), {"selecionados": [b.pk]})
        self.assertFalse(Produto.objects.exists())


class SubgrupoJanelaTests(ProdutoTestCase):
    def test_subgrupo_fica_dentro_do_grupo(self):
        outro = Grupo.objects.create(nome="Limpeza")
        url = reverse("cadastro_simples_criar", args=["subgrupo"])
        self.assertTrue(self.client.post(url, {"nome": "Detergentes", "pai": outro.pk}).json()["ok"])
        # Mesmo nome em outro grupo pode; no mesmo grupo, não
        self.assertTrue(self.client.post(url, {"nome": "Detergentes", "pai": self.grupo.pk}).json()["ok"])
        self.assertEqual(self.client.post(url, {"nome": "detergentes", "pai": outro.pk}).status_code, 400)
        # Sem grupo (ou grupo inexistente) não cadastra
        self.assertEqual(self.client.post(url, {"nome": "Solto"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"nome": "Solto", "pai": 99999}).status_code, 400)

    def test_lista_so_do_grupo(self):
        Subgrupo.objects.create(nome="Sucos", grupo=self.grupo)
        Subgrupo.objects.create(nome="Velas", grupo=Grupo.objects.create(nome="Casa"))
        itens = self.client.get(reverse("cadastro_simples_lista", args=["subgrupo"]), {"pai": self.grupo.pk}).json()["itens"]
        self.assertEqual([i["nome"] for i in itens], ["Refrigerantes", "Sucos"])

    def test_unidades_padrao(self):
        self.assertTrue({"UN", "KG", "CX", "LT"} <= set(UnidadeMedida.objects.values_list("nome", flat=True)))


class MenuProdutosTests(ProdutoTestCase):
    def test_menu_e_paginas(self):
        self.assertContains(self.client.get(reverse("produto_lista")), "Novo produto")
        resposta = self.client.get(reverse("produto_vinculos_fiscais"))
        self.assertContains(resposta, "Novo vínculo")
        self.assertContains(resposta, 'class="group/prod" data-menu open')
        self.assertContains(self.client.get(reverse("produto_grupos")), 'class="group/prod" data-menu open')


class GrupoTests(ProdutoTestCase):
    def test_cadastra_com_os_campos_e_volta_para_os_subgrupos(self):
        resposta = self.client.post(reverse("produto_grupo_criar"), {
            "nome": "Bebidas alcoólicas", "comissao": "2,50", "vender": "on", "ativo": "on", "restricao_idade": "on",
        })
        g = Grupo.objects.get(nome="Bebidas alcoólicas")
        self.assertRedirects(resposta, reverse("produto_grupo_editar", args=[g.pk]), fetch_redirect_response=False)
        self.assertEqual((g.comissao, g.vender, g.restricao_idade, g.hortifruti), (Decimal("2.50"), True, True, False))

    def test_nome_repetido(self):
        resposta = self.client.post(reverse("produto_grupo_criar"), {"nome": "bebidas", "vender": "on", "ativo": "on"})
        self.assertFormError(resposta.context["form"], "nome", "Já existe um grupo de produtos com este nome.")

    def test_janela_do_mais_nao_desliga_vender(self):
        """Renomear pelo + do produto mexe só no nome."""
        self.client.post(reverse("cadastro_simples_salvar", args=["grupo", self.grupo.pk]), {"nome": "Bebidas e sucos"})
        self.grupo.refresh_from_db()
        self.assertEqual(self.grupo.nome, "Bebidas e sucos")
        self.assertTrue(self.grupo.vender)

    def test_lista_mostra_subgrupos_e_filtra(self):
        Grupo.objects.create(nome="Antigo", ativo=False)
        resposta = self.client.get(reverse("produto_grupos"))
        grupos = list(resposta.context["grupos"])
        self.assertEqual([g.nome for g in grupos], ["Bebidas"])
        self.assertEqual(grupos[0].total_subgrupos, 1)
        busca = self.client.get(reverse("produto_grupos"), {"q": "refri"}).context["grupos"]
        self.assertEqual([g.nome for g in busca], ["Bebidas"])  # acha pelo subgrupo

    def test_edicao_lista_os_subgrupos(self):
        resposta = self.client.get(reverse("produto_grupo_editar", args=[self.grupo.pk]))
        self.assertContains(resposta, "Refrigerantes")
        self.assertContains(resposta, 'data-pai-campo="grupo_atual"')

    def test_nao_exclui_grupo_com_produtos(self):
        self.cadastrar()
        self.client.post(reverse("produto_grupo_excluir", args=[self.grupo.pk]))
        self.assertTrue(Grupo.objects.filter(pk=self.grupo.pk).exists())
        livre = Grupo.objects.create(nome="Livre")
        Subgrupo.objects.create(nome="Sub", grupo=livre)
        self.client.post(reverse("produto_grupo_excluir_selecionados"), {"selecionados": [livre.pk, self.grupo.pk]})
        self.assertFalse(Grupo.objects.filter(pk=livre.pk).exists())
        self.assertFalse(Subgrupo.objects.filter(nome="Sub").exists())  # subgrupos vão junto
        self.assertTrue(Grupo.objects.filter(pk=self.grupo.pk).exists())


class DesativadoTests(ProdutoTestCase):
    def test_desativado_fica_nas_configuracoes(self):
        self.cadastrar(desativado="on")
        p = Produto.objects.get()
        self.assertFalse(p.ativo)
        form = self.client.get(reverse("produto_editar", args=[p.pk])).context["form"]
        self.assertTrue(form.initial["desativado"])
        self.assertNotIn("ativo", form.fields)
        self.client.post(reverse("produto_editar", args=[p.pk]), self.dados())  # sem "desativado"
        p.refresh_from_db()
        self.assertTrue(p.ativo)


class FiltrosTests(ProdutoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar(descricao="Coca")
        self.cadastrar(descricao="Kit festa", combo="on")
        limpeza = Grupo.objects.create(nome="Limpeza")
        self.cadastrar(descricao="Sabão", grupo=limpeza.pk, subgrupo="")
        self.limpeza = limpeza

    def nomes(self, **params):
        return [p.descricao for p in self.client.get(reverse("produto_lista"), params).context["produtos"]]

    def test_grupo_e_combo(self):
        self.assertEqual(self.nomes(grupo=self.limpeza.pk), ["Sabão"])
        self.assertEqual(self.nomes(combo="1"), ["Kit festa"])
        self.assertEqual(self.nomes(grupo=self.grupo.pk, combo="1"), ["Kit festa"])

    def test_limpar_filtros_aparece_so_filtrando(self):
        self.assertNotContains(self.client.get(reverse("produto_lista")), "Limpar filtros")
        self.assertContains(self.client.get(reverse("produto_lista"), {"combo": "1"}), "Limpar filtros")

    def test_so_codigo_e_descricao_ordenam(self):
        resposta = self.client.get(reverse("produto_lista"), {"o": "preco"})
        self.assertEqual(resposta.context["ordem"], "")  # preço não ordena mais
        self.assertEqual(self.client.get(reverse("produto_lista"), {"o": "-descricao"}).context["ordem"], "-descricao")


class EstoqueTests(ProdutoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.produto = Produto.objects.get()

    def test_lista_mostra_saldo_da_empresa_atual(self):
        from .estoque import ajustar
        outra = self.criar_empresa()
        ajustar(self.produto, self.empresa, Decimal("12.5"))
        ajustar(self.produto, outra, Decimal("99"))
        produto = self.client.get(reverse("produto_lista")).context["produtos"][0]
        self.assertEqual(produto.saldo, Decimal("12.5"))
        self.assertContains(self.client.get(reverse("produto_lista")), "12,5")

    def test_organizar_sem_inconsistencia(self):
        from .estoque import movimentar
        from .models import MovimentoEstoque
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        movimentar(self.produto, self.empresa, Decimal("10"), MovimentoEstoque.Tipo.ENTRADA)
        movimentar(self.produto, self.empresa, Decimal("-4"), MovimentoEstoque.Tipo.SAIDA)
        r = self.client.post(reverse("produto_estoque_organizar", args=[self.produto.pk])).json()
        self.assertTrue(r["ok"])
        self.assertEqual(r["correcoes"], [])
        self.assertEqual(r["conferidas"][0]["saldo"], "6")
        ajustes = next(e for e in r["etapas"] if e["chave"] == "ajustes")
        self.assertEqual((ajustes["status"], ajustes["detalhe"]), ("ok", "2 movimentação(ões) conferida(s)."))
        vendas = next(e for e in r["etapas"] if e["chave"] == "vendas")
        self.assertEqual(vendas["status"], "inativo")  # módulo ainda não existe

    def test_organizar_corrige_saldo_errado(self):
        from .estoque import movimentar, saldo
        from .models import EstoqueProduto, MovimentoEstoque
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        movimentar(self.produto, self.empresa, Decimal("10"), MovimentoEstoque.Tipo.ENTRADA)
        EstoqueProduto.objects.filter(produto=self.produto).update(quantidade=Decimal("99"))  # saldo "estragado"
        outra = self.criar_empresa()
        EstoqueProduto.objects.create(produto=self.produto, empresa=outra, quantidade=Decimal("5"))  # sem movimentos
        r = self.client.post(reverse("produto_estoque_organizar", args=[self.produto.pk])).json()
        correcoes = {c["empresa"]: (c["antes"], c["depois"]) for c in r["correcoes"]}
        self.assertEqual(correcoes[self.empresa.unidade], ("99", "10"))
        self.assertEqual(correcoes[outra.unidade], ("5", "0"))
        self.assertEqual(saldo(self.produto, self.empresa), Decimal("10"))
        self.assertEqual(saldo(self.produto, outra), Decimal("0"))

    def test_organizar_aponta_movimento_incoerente(self):
        from .models import MovimentoEstoque
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        MovimentoEstoque.objects.create(
            produto=self.produto, empresa=self.empresa, tipo="entrada",
            quantidade=Decimal("5"), saldo_anterior=Decimal("0"), saldo_novo=Decimal("7"),
        )
        r = self.client.post(reverse("produto_estoque_organizar", args=[self.produto.pk])).json()
        self.assertEqual(len(r["incoerentes"]), 1)

    def test_organizar_so_para_configuracao_e_com_controle(self):
        url = reverse("produto_estoque_organizar", args=[self.produto.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        Produto.objects.filter(pk=self.produto.pk).update(controlar_estoque=False)
        r = self.client.post(url)
        self.assertEqual(r.status_code, 400)
        self.assertIn("não controla estoque", r.json()["mensagem"])

    def test_tela_tem_a_janela_com_as_etapas(self):
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        resposta = self.client.get(reverse("produto_editar", args=[self.produto.pk]))
        self.assertContains(resposta, 'id="dialogo-organizar"')
        for nome in ("Vendas", "Compras", "Ajustes", "Transferências", "Requisições", "Devoluções", "Composição", "NF-e"):
            self.assertContains(resposta, nome)


class AjusteRapidoTests(ProdutoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.produto = Produto.objects.get()
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        self.url = reverse("produto_estoque_rapido", args=[self.produto.pk])

    def rapido(self, operacao, qtd, data="2026-11-20"):
        return self.client.post(self.url, {"rapido-operacao": operacao, "rapido-quantidade": qtd, "rapido-data": data},
                                follow=True)

    def test_entrada_soma_e_saida_subtrai(self):
        from .estoque import saldo
        from .models import MovimentoEstoque
        self.rapido("entrada", "10")
        resposta = self.rapido("saida", "2,5")
        self.assertContains(resposta, "Saída de 2,5 UN: estoque 10 → 7,5.")
        self.assertEqual(saldo(self.produto, self.empresa), Decimal("7.5"))
        saida = MovimentoEstoque.objects.first()
        self.assertEqual((saida.tipo, saida.quantidade, str(saida.data_operacao)), ("saida", Decimal("-2.5"), "2026-11-20"))

    def test_saida_pode_deixar_negativo(self):
        from .estoque import saldo
        self.rapido("saida", "3")
        self.assertEqual(saldo(self.produto, self.empresa), Decimal("-3"))

    def test_quantidade_precisa_ser_maior_que_zero(self):
        from .models import MovimentoEstoque
        resposta = self.rapido("entrada", "0")
        self.assertContains(resposta, "A quantidade precisa ser maior que zero.")
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_tela_tem_os_botoes(self):
        resposta = self.client.get(reverse("produto_editar", args=[self.produto.pk]))
        self.assertContains(resposta, 'data-abrir-dialogo="dialogo-rapido"')
        self.assertContains(resposta, 'data-abrir-dialogo="dialogo-minimo"')


class EstoqueMinimoTests(ProdutoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar()
        self.produto = Produto.objects.get()

    def test_define_minimo_e_destaca_na_lista(self):
        from .estoque import ajustar, estoque_minimo
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa]))
        self.client.post(reverse("produto_estoque_minimo", args=[self.produto.pk]), {"minimo-estoque_minimo": "5"})
        self.assertEqual(estoque_minimo(self.produto, self.empresa), Decimal("5"))
        ajustar(self.produto, self.empresa, Decimal("2"))
        resposta = self.client.get(reverse("produto_lista"))
        self.assertContains(resposta, "Abaixo do estoque mínimo (5)")
        ajustar(self.produto, self.empresa, Decimal("8"))
        self.assertNotContains(self.client.get(reverse("produto_lista")), "Abaixo do estoque mínimo")

    def test_usuario_comum_nao_altera_minimo(self):
        r = self.client.post(reverse("produto_estoque_minimo", args=[self.produto.pk]), {"minimo-estoque_minimo": "5"})
        self.assertEqual(r.status_code, 403)


class ExclusaoComMovimentoTests(ProdutoTestCase):
    """Produto que já foi movimentado (ajuste, venda, nota...) não pode ser excluído, só desativado."""

    def setUp(self):
        super().setUp()
        from .estoque import movimentar
        from .models import MovimentoEstoque
        self.cadastrar()
        self.cadastrar(descricao="Nunca movimentado")
        self.movimentado, self.livre = Produto.objects.order_by("pk")
        movimentar(self.movimentado, self.empresa, Decimal("3"), MovimentoEstoque.Tipo.ENTRADA)

    def test_excluir_produto_movimentado_mostra_mensagem(self):
        r = self.client.post(reverse("produto_excluir", args=[self.movimentado.pk]), follow=True)
        self.assertTrue(Produto.objects.filter(pk=self.movimentado.pk).exists())
        self.assertContains(r, "movimentos de estoque e não pode ser excluído")
        self.assertContains(r, "Desative o produto em vez de excluir")

    def test_excluir_selecionados_pula_o_movimentado(self):
        r = self.client.post(
            reverse("produto_excluir_selecionados"), {"selecionados": [self.movimentado.pk, self.livre.pk]}, follow=True,
        )
        self.assertEqual(list(Produto.objects.values_list("pk", flat=True)), [self.movimentado.pk])
        self.assertContains(r, "movimentos de estoque")

    def test_banco_tambem_protege(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.movimentado.delete()

    def test_janela_de_confirmacao_ja_avisa(self):
        r = self.client.get(reverse("produto_editar", args=[self.movimentado.pk]))
        self.assertContains(r, "não poderá ser excluído")
        r = self.client.get(reverse("produto_editar", args=[self.livre.pk]))
        self.assertNotContains(r, "não poderá ser excluído")

    def test_saldo_sem_movimento_nao_impede(self):
        from .estoque import definir_minimo
        definir_minimo(self.livre, self.empresa, Decimal("2"))  # só o estoque mínimo, nenhum movimento
        self.client.post(reverse("produto_excluir", args=[self.livre.pk]))
        self.assertFalse(Produto.objects.filter(pk=self.livre.pk).exists())

    def test_empresa_com_movimento_nao_pode_ser_excluida(self):
        self.assertIn("movimentos de estoque", self.empresa.vinculos_que_impedem_exclusao())

    def test_clone_nao_leva_estoque_nem_movimentos(self):
        from .estoque import definir_minimo, estoque_minimo, saldo
        from .models import EstoqueProduto, MovimentoEstoque
        definir_minimo(self.movimentado, self.empresa, Decimal("2"))
        form = self.client.get(reverse("produto_criar"), {"clonar": self.movimentado.pk}).context["form"]
        dados = self.dados(descricao=form.initial["descricao"])
        self.client.post(reverse("produto_criar"), dados)
        clone = Produto.objects.latest("pk")
        self.assertNotEqual(clone.pk, self.movimentado.pk)
        self.assertEqual(clone.descricao, "Refrigerante Cola 2L (cópia)")
        self.assertEqual(clone.grupo, self.movimentado.grupo)
        self.assertEqual(clone.preco_venda, self.movimentado.preco_venda)
        self.assertFalse(MovimentoEstoque.objects.filter(produto=clone).exists())
        self.assertFalse(EstoqueProduto.objects.filter(produto=clone).exists())
        self.assertEqual(saldo(clone, self.empresa), Decimal("0"))
        self.assertEqual(estoque_minimo(clone, self.empresa), Decimal("0"))
        self.assertEqual(clone.vinculos_que_impedem_exclusao(), [])  # o clone é novo: pode ser excluído
        # e o original continua intacto
        self.assertEqual(saldo(self.movimentado, self.empresa), Decimal("3"))


class AbaEmpresaTests(ProdutoTestCase):
    """Aba "Empresa": em quais empresas o produto aparece (padrão: todas)."""

    def setUp(self):
        super().setUp()
        self.filial = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=COMUM, empresas=[self.empresa, self.filial]))
        self.client.post(reverse("trocar_empresa", args=[self.empresa.pk]))

    def test_produto_novo_vem_com_todas_marcadas(self):
        form = self.client.get(reverse("produto_criar")).context["form"]
        self.assertEqual(set(form.initial["empresas"]), {self.empresa.pk, self.filial.pk})
        r = self.client.get(reverse("produto_criar"))
        self.assertContains(r, 'data-aba="empresas"')
        self.assertContains(r, "Em quais empresas este produto aparece?")
        self.assertNotContains(r, "Produto/Empresa")

    def test_desmarcar_oculta_na_empresa(self):
        self.cadastrar(empresas=[self.filial.pk])
        produto = Produto.objects.get()
        self.assertEqual(list(produto.empresas_ocultas.all()), [self.empresa])
        self.assertFalse(produto.disponivel_na(self.empresa))
        self.assertTrue(produto.disponivel_na(self.filial))
        # Na empresa atual (oculto) não aparece na lista
        self.assertEqual(list(self.client.get(reverse("produto_lista")).context["produtos"]), [])
        self.assertNotContains(self.client.get(reverse("produto_lista")), "Ocultos nesta empresa")
        self.assertContains(self.client.get(reverse("produto_editar", args=[produto.pk])), "oculto em")
        # Na filial aparece
        self.client.post(reverse("trocar_empresa", args=[self.filial.pk]))
        self.assertEqual([x.pk for x in self.client.get(reverse("produto_lista")).context["produtos"]], [produto.pk])

    def test_marcar_de_novo_volta_a_mostrar(self):
        self.cadastrar(empresas=[self.filial.pk])
        produto = Produto.objects.get()
        self.client.post(reverse("produto_editar", args=[produto.pk]), self.dados(empresas=[self.empresa.pk, self.filial.pk]))
        self.assertFalse(produto.empresas_ocultas.exists())

    def test_precisa_de_pelo_menos_uma_empresa(self):
        r = self.cadastrar(empresas=[])
        self.assertFalse(Produto.objects.exists())
        self.assertContains(r, "Marque pelo menos uma empresa")

    def test_empresa_nova_ja_recebe_o_catalogo(self):
        self.cadastrar(empresas=[self.empresa.pk, self.filial.pk])
        produto = Produto.objects.get()
        nova = self.criar_empresa()
        self.assertTrue(produto.disponivel_na(nova))

    def test_empresa_desativada_mantem_a_marcacao(self):
        self.cadastrar(empresas=[self.empresa.pk])  # oculto na filial
        produto = Produto.objects.get()
        self.filial.ativa = False
        self.filial.save()
        self.client.post(reverse("produto_editar", args=[produto.pk]), self.dados())
        self.assertEqual(list(produto.empresas_ocultas.all()), [self.filial])

    def test_estoque_bloqueado_onde_esta_oculto(self):
        from .estoque import saldo
        self.client.force_login(self.criar_usuario(nivel="admin", empresas=[self.empresa, self.filial]))
        self.client.post(reverse("trocar_empresa", args=[self.empresa.pk]))
        self.cadastrar(empresas=[self.filial.pk])
        produto = Produto.objects.get()
        r = self.client.post(
            reverse("produto_estoque_rapido", args=[produto.pk]),
            {"rapido-data": "20/11/2026", "rapido-operacao": "entrada", "rapido-quantidade": "2"}, follow=True,
        )
        self.assertContains(r, "está oculto em")
        self.assertEqual(saldo(produto, self.empresa), Decimal("0"))

    def test_clone_leva_as_mesmas_empresas(self):
        self.cadastrar(empresas=[self.filial.pk])
        origem = Produto.objects.get()
        form = self.client.get(reverse("produto_criar"), {"clonar": origem.pk}).context["form"]
        self.assertEqual(form.initial["empresas"], [self.filial.pk])

    def test_excluir_empresa_nao_e_impedido_pela_marcacao(self):
        self.cadastrar(empresas=[self.empresa.pk])  # oculto na filial
        self.assertEqual(self.filial.vinculos_que_impedem_exclusao(), [])


class SalvarContinuaNoCadastroTests(ProdutoTestCase):
    def test_editar_produto_fica_na_tela_com_mensagem(self):
        self.cadastrar()
        p = Produto.objects.get()
        r = self.client.post(reverse("produto_editar", args=[p.pk]), self.dados(descricao="Cola 1L"), follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("produto_editar", args=[p.pk]))
        self.assertContains(r, "atualizado com sucesso")

    def test_editar_grupo_fica_na_tela(self):
        r = self.client.post(reverse("produto_grupo_editar", args=[self.grupo.pk]), {"nome": "Bebidas geladas", "comissao": "0"})
        self.assertRedirects(r, reverse("produto_grupo_editar", args=[self.grupo.pk]), fetch_redirect_response=False)


class ListaAtualizadaTests(ProdutoTestCase):
    """Os campos buscam a lista no banco de novo (grupo criado em outra aba aparece sem recarregar)."""

    def test_lista_json_traz_grupo_novo_e_filtra_ativos(self):
        url = reverse("cadastro_simples_lista", args=["grupo"])
        Grupo.objects.create(nome="Limpeza")
        Grupo.objects.create(nome="Antigo", ativo=False)
        nomes = {i["nome"] for i in self.client.get(url).json()["itens"]}
        self.assertTrue({"Bebidas", "Limpeza", "Antigo"} <= nomes)
        nomes = {i["nome"] for i in self.client.get(url, {"ativos": "1"}).json()["itens"]}
        self.assertNotIn("Antigo", nomes)

    def test_busca_digitavel_com_limite(self):
        url = reverse("cadastro_simples_lista", args=["grupo"])
        for n in range(5):
            Grupo.objects.create(nome=f"Limpeza {n}")
        r = self.client.get(url, {"q": "limp", "limite": "3", "ativos": "1"}).json()
        self.assertEqual(len(r["itens"]), 3)
        self.assertTrue(r["mais"])  # avisa que tem mais para refinar
        r = self.client.get(url, {"q": "limp", "limite": "10"}).json()
        self.assertEqual((len(r["itens"]), r["mais"]), (5, False))

    def test_filtro_de_grupo_da_lista_se_atualiza(self):
        self.assertContains(self.client.get(reverse("produto_lista")), "data-atualizar-url")


class DetalhesFiscaisTests(ProdutoTestCase):
    """Aba "Detalhes fiscais": dados fiscais do produto em cada empresa."""

    def setUp(self):
        super().setUp()
        from fiscal.models import Ncm
        from .models import VinculoFiscal
        Ncm.objects.create(codigo="61032200", descricao="De algodão")
        Ncm.objects.create(codigo="22021000", descricao="Águas, incluindo as águas minerais, adicionadas de açúcar")
        self.vinculo = VinculoFiscal.objects.create(nome="ICMS Tributado - PIS isento")
        self.cadastrar()
        self.produto = Produto.objects.get()
        self.url = reverse("produto_fiscal", args=[self.produto.pk, self.empresa.pk])

    def dados_fiscais(self, **extra):
        dados = {"fiscal-vinculo": self.vinculo.pk, "fiscal-origem": "0", "fiscal-ncm": "61032200",
                 "fiscal-cest": "", "fiscal-fcp": "2,00", "fiscal-especifico": ""}
        dados.update(extra)
        return dados

    def test_produto_novo_pede_para_salvar_antes(self):
        self.assertContains(self.client.get(reverse("produto_criar")), "Salve o produto primeiro")

    def test_uma_empresa_so_abre_o_formulario_na_aba(self):
        r = self.client.get(reverse("produto_editar", args=[self.produto.pk]))
        self.assertContains(r, 'id="form-fiscal"')
        self.assertContains(r, 'name="voltar" value="produto"')
        self.assertNotContains(r, "Detalhes fiscais</span>em breve")

    def test_varias_empresas_lista_para_escolher(self):
        filial = self.criar_empresa()
        oculta = self.criar_empresa()
        self.produto.empresas_ocultas.add(oculta)
        r = self.client.get(reverse("produto_editar", args=[self.produto.pk]))
        self.assertNotContains(r, 'id="form-fiscal"')
        self.assertContains(r, reverse("produto_fiscal", args=[self.produto.pk, filial.pk]))
        self.assertContains(r, reverse("produto_fiscal", args=[self.produto.pk, self.empresa.pk]))
        self.assertNotContains(r, reverse("produto_fiscal", args=[self.produto.pk, oculta.pk]))  # oculta não entra
        # Direto pelo endereço também não
        r = self.client.get(reverse("produto_fiscal", args=[self.produto.pk, oculta.pk]))
        self.assertRedirects(r, reverse("produto_editar", args=[self.produto.pk]) + "#empresas", fetch_redirect_response=False)

    def test_salva_e_continua_na_tela(self):
        from .models import DetalheFiscal
        r = self.client.post(self.url, self.dados_fiscais(**{"fiscal-cest": "03.002.00"}))
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        d = DetalheFiscal.objects.get(produto=self.produto, empresa=self.empresa)
        self.assertEqual((d.vinculo, d.ncm, d.cest, d.fcp), (self.vinculo, "61032200", "0300200", Decimal("2")))
        # A página mostra a NCM escolhida com a descrição
        self.assertContains(self.client.get(self.url), "61032200 - De algodão")

    def test_salvar_pela_aba_volta_para_o_produto(self):
        r = self.client.post(self.url, self.dados_fiscais(voltar="produto"))
        self.assertRedirects(r, reverse("produto_editar", args=[self.produto.pk]) + "#fiscal", fetch_redirect_response=False)

    def test_ncm_precisa_existir_e_cest_ter_7_numeros(self):
        r = self.client.post(self.url, self.dados_fiscais(**{"fiscal-ncm": "99999999", "fiscal-cest": "123"}))
        form = r.context["fiscal_form"]
        self.assertEqual(form.errors["ncm"], ["NCM não encontrada na tabela vigente."])
        self.assertEqual(form.errors["cest"], ["O CEST tem 7 números."])

    def test_combustivel_exige_anp_e_uf(self):
        r = self.client.post(self.url, self.dados_fiscais(**{"fiscal-especifico": "combustivel"}))
        form = r.context["fiscal_form"]
        self.assertTrue({"anp_codigo", "anp_descricao", "uf_consumo"} <= set(form.errors))
        self.assertTrue(form.erro_no_especifico)
        self.assertContains(r, "data-abrir-ao-carregar")  # a janela já abre mostrando o erro

    def test_combustivel_salva_e_voltar_para_nenhum_limpa(self):
        from .models import DetalheFiscal
        comb = {"fiscal-especifico": "combustivel", "fiscal-anp_codigo": "210203001", "fiscal-anp_descricao": "GLP",
                "fiscal-uf_consumo": "MG", "fiscal-glp_percentual": "100,0000", "fiscal-adrem_icms": "1,3900"}
        self.client.post(self.url, self.dados_fiscais(**comb))
        d = DetalheFiscal.objects.get()
        self.assertEqual((d.especifico, d.anp_codigo, d.uf_consumo, d.glp_percentual, d.adrem_icms),
                         ("combustivel", "210203001", "MG", Decimal("100"), Decimal("1.39")))
        self.client.post(self.url, self.dados_fiscais(**{**comb, "fiscal-especifico": ""}))
        d.refresh_from_db()
        self.assertEqual((d.especifico, d.anp_codigo, d.uf_consumo, d.glp_percentual), ("", "", "", 0))

    def test_unidade_tributavel_diferente_exige_unidade_e_fator(self):
        r = self.client.post(self.url, self.dados_fiscais(**{"fiscal-unidade_tributavel_diferente": "on"}))
        self.assertTrue({"unidade_tributavel", "fator_conversao"} <= set(r.context["fiscal_form"].errors))
        kg = UnidadeMedida.objects.get(nome="KG")
        self.client.post(self.url, self.dados_fiscais(**{
            "fiscal-unidade_tributavel_diferente": "on", "fiscal-unidade_tributavel": kg.pk, "fiscal-fator_conversao": "13",
        }))
        from .models import DetalheFiscal
        d = DetalheFiscal.objects.get()
        self.assertEqual((d.unidade_tributavel, d.fator_conversao), (kg, Decimal("13")))

    def test_clone_leva_os_detalhes_fiscais(self):
        from .models import DetalheFiscal
        self.client.post(self.url, self.dados_fiscais())
        r = self.client.get(reverse("produto_criar"), {"clonar": self.produto.pk})
        self.assertContains(r, f'name="clonar_de" value="{self.produto.pk}"')
        self.client.post(reverse("produto_criar"), self.dados(descricao="Cópia", clonar_de=self.produto.pk))
        clone = Produto.objects.get(descricao="Cópia")
        d = DetalheFiscal.objects.get(produto=clone)
        self.assertEqual((d.vinculo, d.ncm, d.fcp), (self.vinculo, "61032200", Decimal("2")))
        # O original continua com o seu
        self.assertEqual(DetalheFiscal.objects.filter(produto=self.produto).count(), 1)

    def test_detalhe_fiscal_nao_impede_excluir_produto_nem_empresa(self):
        self.client.post(self.url, self.dados_fiscais())
        self.assertEqual(self.produto.vinculos_que_impedem_exclusao(), [])
        self.assertEqual(self.empresa.vinculos_que_impedem_exclusao(), [])

    def test_buscas_de_ncm_e_vinculo(self):
        busca = lambda q: [i["id"] for i in self.client.get(reverse("ncm_busca"), {"q": q}).json()["itens"]]
        self.assertEqual(busca("6103"), ["61032200"])
        self.assertEqual(busca("6103.22"), ["61032200"])
        self.assertEqual(busca("agua acucar"), ["22021000"])  # sem acento também acha
        itens = self.client.get(reverse("cadastro_simples_lista", args=["vinculo_fiscal"]), {"ativos": "1"}).json()["itens"]
        self.assertIn("ICMS Tributado - PIS isento", [i["nome"] for i in itens])


class OlhoNoImpostoECestTests(ProdutoTestCase):
    """"De olho no imposto" vem da tabela do IBPT e o CEST vem da NCM (sem digitar)."""

    def setUp(self):
        super().setUp()
        from unittest import mock

        from django.utils import timezone

        from fiscal.models import AliquotaIbpt, Cest, CestNcm, Ncm
        from localidades.models import Municipio
        # Nenhum teste vai à internet: a consulta ao IBPT é simulada
        self.baixar = mock.patch("fiscal.consultas._baixar_ibpt", side_effect=OSError("sem internet nos testes"))
        self.baixar.start()
        self.addCleanup(self.baixar.stop)

        Ncm.objects.create(codigo="61032200", descricao="De algodão")
        Ncm.objects.create(codigo="22029900", descricao="Outras")
        Ncm.objects.create(codigo="84713012", descricao="Notebooks")  # sem CEST
        AliquotaIbpt.objects.create(
            ncm="61032200", uf="MG", nacional_federal=Decimal("13.45"), importados_federal=Decimal("33.60"),
            estadual=Decimal("18"), municipal=Decimal("0"), versao="26.2.B", fonte="IBPT", consultado_em=timezone.now(),
        )
        vestuario = Cest.objects.create(codigo="2805900", descricao="Vestuário e seus acessórios")
        CestNcm.objects.create(cest=vestuario, ncm="61")  # código parcial: vale para todo o capítulo 61
        for codigo, nome in (("0300800", "Outras águas minerais"), ("0301001", "Refrigerante em embalagem pet")):
            CestNcm.objects.create(cest=Cest.objects.create(codigo=codigo, descricao=nome), ncm="22029900")

        self.empresa.municipio = Municipio.objects.create(codigo_ibge="3106200", nome="Belo Horizonte", uf="MG")
        self.empresa.save()
        self.cadastrar()
        self.produto = Produto.objects.get()
        self.url = reverse("produto_fiscal", args=[self.produto.pk, self.empresa.pk])

    def salvar(self, **extra):
        dados = {"fiscal-origem": "0", "fiscal-ncm": "61032200", "fiscal-cest": "", "fiscal-especifico": ""}
        dados.update(extra)
        return self.client.post(self.url, dados)

    def detalhe(self):
        from .models import DetalheFiscal
        return DetalheFiscal.objects.get(produto=self.produto, empresa=self.empresa)

    def test_olho_no_imposto_calculado_pela_ncm_e_uf(self):
        self.salvar(**{"fiscal-olho_no_imposto": "99,00"})  # tentar mandar um valor não adianta
        d = self.detalhe()
        self.assertEqual((d.olho_federal, d.olho_estadual, d.olho_municipal, d.olho_no_imposto),
                         (Decimal("13.45"), Decimal("18"), Decimal("0"), Decimal("31.45")))
        self.assertEqual(d.olho_fonte, "IBPT 26.2.B · MG")
        self.assertContains(self.client.get(self.url), "31,45")

    def test_importado_usa_aliquota_federal_de_importados(self):
        self.salvar(**{"fiscal-origem": "1"})
        self.assertEqual(self.detalhe().olho_no_imposto, Decimal("51.60"))

    def test_sem_tabela_ou_sem_cidade_fica_zerado(self):
        self.salvar(**{"fiscal-ncm": "22029900"})  # não está na tabela guardada e não há internet
        d = self.detalhe()
        self.assertEqual((d.olho_no_imposto, d.olho_fonte), (Decimal("0"), ""))
        self.empresa.municipio = None
        self.empresa.save()
        self.salvar()
        self.assertEqual(self.detalhe().olho_no_imposto, Decimal("0"))

    def test_consulta_o_ibpt_e_guarda(self):
        from fiscal.models import AliquotaIbpt
        self.baixar.stop()
        from unittest import mock
        dados = {"version": "26.2.B", "source": "IBPT", "effectiveDate": "2026-09-20", "federalNationalRate": 10.5,
                 "federalImportedRate": 20, "stateRate": 18, "municipalRate": 0}
        with mock.patch("fiscal.consultas._baixar_ibpt", return_value=dados) as baixar:
            self.salvar(**{"fiscal-ncm": "22029900"})
            self.salvar(**{"fiscal-ncm": "22029900"})
        self.assertEqual(baixar.call_count, 1)  # a segunda vez usa o que guardou
        self.assertEqual(AliquotaIbpt.objects.get(ncm="22029900", uf="MG").nacional_federal, Decimal("10.50"))
        self.assertEqual(self.detalhe().olho_no_imposto, Decimal("28.50"))
        self.baixar.start()

    def test_previa_na_tela(self):
        url = reverse("produto_fiscal_olho", args=[self.produto.pk, self.empresa.pk])
        r = self.client.get(url, {"ncm": "61032200", "origem": "0"}).json()
        self.assertEqual((r["ok"], r["total"]), (True, "31,45"))
        self.assertIn("Federal 13,45%", r["detalhe"])
        r = self.client.get(url, {"ncm": "84713012"}).json()
        self.assertFalse(r["ok"])
        self.assertIn("não encontrada na tabela do IBPT", r["mensagem"])

    def test_campo_nao_e_editavel(self):
        r = self.client.get(self.url)
        self.assertNotContains(r, 'name="fiscal-olho_no_imposto"')
        self.assertContains(r, "Preenchido sozinho pela NCM")

    def test_cest_vem_da_ncm(self):
        busca = lambda ncm: [i["id"] for i in self.client.get(reverse("cest_busca"), {"pai": ncm}).json()["itens"]]
        self.assertEqual(busca("61032200"), ["2805900"])            # pelo capítulo (código parcial)
        self.assertEqual(busca("22029900"), ["0300800", "0301001"])  # dois possíveis
        self.assertEqual(busca("84713012"), [])                      # nenhum: não mostra nada
        self.assertEqual(busca(""), [])

    def test_cest_precisa_ser_da_ncm(self):
        r = self.salvar(**{"fiscal-cest": "0300800"})  # CEST de bebida numa NCM de roupa
        self.assertEqual(r.context["fiscal_form"].errors["cest"], ["Este CEST não é da NCM escolhida."])
        r = self.salvar(**{"fiscal-ncm": "", "fiscal-cest": "2805900"})
        self.assertEqual(r.context["fiscal_form"].errors["cest"], ["Escolha a NCM antes do CEST."])
        self.salvar(**{"fiscal-cest": "28.059.00"})
        self.assertEqual(self.detalhe().cest, "2805900")
        self.assertContains(self.client.get(self.url), "28.059.00 - Vestuário")


class FotosTests(ProdutoTestCase):
    """Aba "Fotos": envio, foto principal, descrição e exclusão (o arquivo sai do disco junto)."""

    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile

        from django.test import override_settings
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=pasta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.cadastrar()
        self.produto = Produto.objects.get()

    def arquivo(self, nome="foto.png", conteudo=None):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(nome, self.PNG if conteudo is None else conteudo)

    def enviar(self, *arquivos, **extra):
        dados = {"fotos": list(arquivos) or [self.arquivo()], **extra}
        return self.client.post(reverse("produto_fotos_enviar", args=[self.produto.pk]), dados, follow=True)

    def test_produto_novo_pede_para_salvar(self):
        self.assertContains(self.client.get(reverse("produto_criar")), "Salve o produto primeiro. Depois as fotos")

    def test_envia_varias_e_a_primeira_vira_principal(self):
        r = self.enviar(self.arquivo("a.png"), self.arquivo("b.jpg", self.JPG), descricao="Frente")
        self.assertContains(r, "2 fotos enviadas com sucesso.")
        self.assertEqual(r.redirect_chain[-1][0], reverse("produto_editar", args=[self.produto.pk]) + "#fotos")
        fotos = list(self.produto.fotos.order_by("pk"))
        self.assertEqual([f.principal for f in fotos], [True, False])
        self.assertEqual({f.descricao for f in fotos}, {"Frente"})
        # Cada instância na sua pasta, com nome aleatório e a extensão pelo conteúdo
        self.assertTrue(fotos[0].arquivo.name.startswith(f"{self.tenant.schema_name}/produtos/{self.produto.pk}/"))
        self.assertTrue(fotos[1].arquivo.name.endswith(".jpg"))

    def test_definir_como_principal_no_envio(self):
        self.enviar()
        self.enviar(self.arquivo("nova.png"), principal="1")
        principal = self.produto.fotos.get(principal=True)
        self.assertEqual(principal, self.produto.fotos.order_by("-pk").first())
        self.assertEqual(self.produto.fotos.filter(principal=True).count(), 1)

    def test_recusa_o_que_nao_e_imagem_e_arquivo_grande(self):
        r = self.enviar(self.arquivo("virus.png", b"MZ\x90\x00 isto nao e imagem"))
        self.assertContains(r, "virus.png: não é uma imagem JPG, PNG, WEBP ou GIF.")
        from . import fotos
        grande = self.arquivo("grande.png", self.PNG + b"\x00" * fotos.TAMANHO_MAXIMO)
        self.assertContains(self.enviar(grande), "grande.png: maior que 5 MB.")
        self.assertFalse(self.produto.fotos.exists())

    def test_limite_de_fotos(self):
        from unittest import mock
        with mock.patch("produtos.fotos.MAXIMO_POR_PRODUTO", 2):
            r = self.enviar(self.arquivo("1.png"), self.arquivo("2.png"), self.arquivo("3.png"))
        self.assertEqual(self.produto.fotos.count(), 2)
        self.assertContains(r, "3.png: passou do máximo de 2 fotos por produto.")

    def test_trocar_principal_editar_e_excluir(self):
        import os
        self.enviar(self.arquivo("a.png"), self.arquivo("b.png"))
        a, b = self.produto.fotos.order_by("pk")
        self.client.post(reverse("produto_foto_principal", args=[self.produto.pk, b.pk]))
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.principal, b.principal), (False, True))
        self.client.post(reverse("produto_foto_editar", args=[self.produto.pk, a.pk]), {"descricao": "Lateral"})
        a.refresh_from_db()
        self.assertEqual(a.descricao, "Lateral")
        caminho = b.arquivo.path
        self.assertTrue(os.path.exists(caminho))
        self.client.post(reverse("produto_foto_excluir", args=[self.produto.pk, b.pk]))
        self.assertFalse(os.path.exists(caminho))  # o arquivo saiu do disco
        a.refresh_from_db()
        self.assertTrue(a.principal)  # a outra virou a principal

    def test_galeria_na_aba(self):
        self.enviar(descricao="Embalagem")
        r = self.client.get(reverse("produto_editar", args=[self.produto.pk]))
        foto = self.produto.fotos.get()
        self.assertContains(r, foto.arquivo.url)
        self.assertContains(r, "Embalagem")
        self.assertContains(r, "Principal")

    def test_fotos_nao_impedem_excluir_o_produto_e_somem_junto(self):
        import os
        self.enviar()
        caminho = self.produto.fotos.get().arquivo.path
        self.assertEqual(self.produto.vinculos_que_impedem_exclusao(), [])
        self.client.post(reverse("produto_excluir", args=[self.produto.pk]))
        self.assertFalse(Produto.objects.exists())
        self.assertFalse(os.path.exists(caminho))

    def test_foto_de_outro_produto_nao_mexe(self):
        self.enviar()
        foto = self.produto.fotos.get()
        self.cadastrar(descricao="Outro")
        outro = Produto.objects.get(descricao="Outro")
        r = self.client.post(reverse("produto_foto_excluir", args=[outro.pk, foto.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(self.produto.fotos.exists())


class VinculosFiscaisTests(ProdutoTestCase):
    """Cadastros › Produtos › Vínculos fiscais."""

    def setUp(self):
        super().setUp()
        from fiscal.models import Cfop, ClassTrib, CstIbsCbs, Ncm
        from .models import VinculoFiscal
        for codigo, nome in (("1102", "Compra para comercialização"), ("2102", "Compra para comercialização (fora)"),
                             ("5102", "Venda de mercadoria adquirida"), ("6102", "Venda de mercadoria adquirida (fora)")):
            Cfop.objects.create(codigo=codigo, descricao=nome)
        cst = CstIbsCbs.objects.create(codigo="000", descricao="Tributação integral")
        ClassTrib.objects.create(codigo="000001", cst=cst, descricao="Situações tributadas integralmente")
        CstIbsCbs.objects.create(codigo="200", descricao="Alíquota reduzida")
        Ncm.objects.create(codigo="61032200", descricao="De algodão")
        self.vinculo = VinculoFiscal.objects.create(nome="ICMS Tributado - PIS isento")
        self.cadastrar()
        self.produto = Produto.objects.get()

    def configurar(self, **extra):
        dados = {"config-documento": "nfe", "config-uf_origem": "MT", "config-uf_destino": "**", "config-regime": "1"}
        dados.update(extra)
        return self.client.post(reverse("vinculo_configuracao_adicionar", args=[self.vinculo.pk]), dados, follow=True)

    def tributacao(self, config, operacao="saida", **extra):
        dados = {"cfop": "5102", "icms_cst": "102", "icms_aliquota": "0,00", "pis_cst": "49", "pis_aliquota": "0",
                 "cofins_cst": "49", "cofins_aliquota": "0", "ipi_cst": "", "ibscbs_cst": "000", "cclasstrib": "000001"}
        dados.update(extra)
        return self.client.post(reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, operacao]), dados)

    def test_lista_e_cadastro_continua_na_tela(self):
        self.assertContains(self.client.get(reverse("produto_vinculos_fiscais")), "ICMS Tributado - PIS isento")
        r = self.client.post(reverse("vinculo_criar"), {"nome": "Substituição tributária", "tipo_item": "00"})
        from .models import VinculoFiscal
        novo = VinculoFiscal.objects.get(nome="Substituição tributária")
        self.assertRedirects(r, reverse("vinculo_editar", args=[novo.pk]) + "#configuracoes", fetch_redirect_response=False)
        r = self.client.post(reverse("vinculo_criar"), {"nome": "substituição TRIBUTÁRIA", "tipo_item": "00"})
        self.assertFormError(r.context["form"], "nome", "Já existe um vínculo fiscal com esta descrição.")

    def test_so_um_padrao(self):
        from .models import VinculoFiscal
        outro = VinculoFiscal.objects.create(nome="Isento")
        self.client.post(reverse("vinculo_padrao", args=[self.vinculo.pk]))
        self.client.post(reverse("vinculo_padrao", args=[outro.pk]))
        self.assertEqual(list(VinculoFiscal.objects.filter(padrao=True)), [outro])
        self.client.post(reverse("vinculo_padrao", args=[outro.pk]))  # clicar de novo desliga
        self.assertFalse(VinculoFiscal.objects.filter(padrao=True).exists())

    def test_adicionar_configuracao_e_nao_repetir(self):
        r = self.configurar()
        self.assertContains(r, "adicionada")
        r = self.configurar()
        self.assertContains(r, "já tem uma configuração com o mesmo documento")
        self.assertEqual(self.vinculo.configuracoes.count(), 1)

    def test_nfce_e_so_saida_e_dentro_do_estado(self):
        self.configurar(**{"config-documento": "nfce", "config-uf_destino": ""})  # destino travado na tela
        config = self.vinculo.configuracoes.get()
        self.assertEqual((config.uf_destino, config.operacoes), ("MT", ["saida"]))
        r = self.client.get(reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "entrada"]))
        self.assertEqual(r.status_code, 404)
        r = self.tributacao(config, cfop="6102")
        self.assertIn("começa com 5.xxx", r.context["form"].errors["cfop"][0])

    def test_tributacao_salva_e_continua_na_tela(self):
        self.configurar()
        config = self.vinculo.configuracoes.get()
        r = self.tributacao(config)
        url = reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "saida"])
        self.assertRedirects(r, url, fetch_redirect_response=False)
        t = config.tributacao("saida")
        self.assertEqual((t.cfop, t.icms_cst, t.pis_cst, t.ibscbs_cst, t.cclasstrib), ("5102", "102", "49", "000", "000001"))
        self.assertContains(self.client.get(url), "5102 - Venda de mercadoria adquirida")

    def test_regras_da_tributacao(self):
        self.configurar(**{"config-regime": "3", "config-uf_destino": "MT"})  # regime normal, dentro do estado
        config = self.vinculo.configuracoes.get()
        r = self.tributacao(config, "entrada", cfop="2102", icms_cst="102", pis_cst="49")
        erros = r.context["form"].errors
        self.assertIn("começa com 1.xxx", erros["cfop"][0])             # entrada dentro do estado
        self.assertIn("icms_cst", erros)                                 # regime normal não usa CSOSN
        self.assertIn("pis_cst", erros)                                  # 49 é de saída
        r = self.tributacao(config, "saida", icms_cst="00", cclasstrib="000001", ibscbs_cst="200")
        self.assertEqual(r.context["form"].errors["cclasstrib"], ["Esta classificação não é do CST escolhido."])
        r = self.tributacao(config, "entrada", cfop="1102", icms_cst="00", icms_aliquota="17,00", pis_cst="50", cofins_cst="50")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(config.tributacao("entrada").icms_aliquota, Decimal("17"))

    def test_clonar_configuracao_e_vinculo(self):
        from .models import VinculoFiscal
        self.configurar()
        config = self.vinculo.configuracoes.get()
        self.tributacao(config)
        self.client.post(reverse("vinculo_configuracao_clonar", args=[self.vinculo.pk, config.pk]), {
            "config-documento": "nfce", "config-uf_origem": "MT", "config-uf_destino": "MT", "config-regime": "1"})
        nova = self.vinculo.configuracoes.get(documento="nfce")
        self.assertEqual(nova.tributacao("saida").cfop, "5102")
        self.vinculo.padrao = True
        self.vinculo.save()
        r = self.client.post(reverse("vinculo_clonar", args=[self.vinculo.pk]))
        copia = VinculoFiscal.objects.get(nome="ICMS Tributado - PIS isento (cópia)")
        self.assertRedirects(r, reverse("vinculo_editar", args=[copia.pk]), fetch_redirect_response=False)
        self.assertEqual(copia.configuracoes.count(), 2)
        self.assertFalse(copia.padrao)  # o padrão não vai para a cópia

    def test_ncm_vinculada_vale_para_produto_sem_vinculo(self):
        from .models import DetalheFiscal, VinculoFiscal, vinculo_do_produto
        r = self.client.post(reverse("vinculo_ncm_adicionar", args=[self.vinculo.pk]), {"ncm": "6103.22.00"}, follow=True)
        self.assertContains(r, "NCM 61032200 vinculada")
        outro = VinculoFiscal.objects.create(nome="Outro")
        r = self.client.post(reverse("vinculo_ncm_adicionar", args=[outro.pk]), {"ncm": "61032200"}, follow=True)
        self.assertContains(r, "já está no vínculo ICMS Tributado - PIS isento")
        DetalheFiscal.objects.create(produto=self.produto, empresa=self.empresa, ncm="61032200")
        self.assertEqual(vinculo_do_produto(self.produto, self.empresa), (self.vinculo, "ncm"))
        # Sem NCM vinculada, vale o padrão
        self.vinculo.ncms.all().delete()
        outro.padrao = True
        outro.save()
        self.assertEqual(vinculo_do_produto(self.produto, self.empresa), (outro, "padrao"))

    def test_vincular_produto_e_tirar(self):
        from .models import DetalheFiscal
        r = self.client.post(reverse("vinculo_produto_adicionar", args=[self.vinculo.pk]),
                             {"produto": self.produto.pk, "empresa": self.empresa.pk}, follow=True)
        self.assertContains(r, "vinculado em")
        d = DetalheFiscal.objects.get(produto=self.produto, empresa=self.empresa)
        self.assertEqual(d.vinculo, self.vinculo)
        self.assertContains(self.client.get(reverse("produto_vinculos_fiscais")), "ICMS Tributado")
        self.client.post(reverse("vinculo_produto_remover", args=[self.vinculo.pk, d.pk]))
        d.refresh_from_db()
        self.assertIsNone(d.vinculo)

    def test_nao_exclui_vinculo_com_produto(self):
        from .models import DetalheFiscal, VinculoFiscal
        DetalheFiscal.objects.create(produto=self.produto, empresa=self.empresa, vinculo=self.vinculo)
        r = self.client.post(reverse("vinculo_excluir", args=[self.vinculo.pk]), follow=True)
        self.assertContains(r, "tem 1 produto e não pode ser excluído")
        livre = VinculoFiscal.objects.create(nome="Livre")
        self.client.post(reverse("vinculo_excluir_selecionados"), {"selecionados": [livre.pk, self.vinculo.pk]})
        self.assertFalse(VinculoFiscal.objects.filter(pk=livre.pk).exists())
        self.assertTrue(VinculoFiscal.objects.filter(pk=self.vinculo.pk).exists())  # tem produto: ficou

    def test_nfce_saida_sem_ipi_e_com_campos_de_icms_e_pis_cofins(self):
        self.configurar(**{"config-documento": "nfce"})
        config = self.vinculo.configuracoes.get()
        url = reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "saida"])
        r = self.client.get(url)
        self.assertNotContains(r, 'name="ipi_cst"')    # NFC-e não tem IPI
        self.assertNotContains(r, 'name="exige_gta"')  # nem Guia de Trânsito Animal
        for nome in ("icms_zerar_base", "icms_acrescimo", "icms_modalidade_base", "icms_reducao_base",
                     "icms_diferimento", "pis_cofins_grupo", "pis_cofins_natureza"):
            self.assertContains(r, f'name="{nome}"')
        self.tributacao(config, pis_cst="07", cofins_cst="07", pis_cofins_grupo="4.3.14", pis_cofins_natureza="101",
                        icms_modalidade_base="3", icms_reducao_base="10,5000", icms_diferimento="0", icms_acrescimo="2,00")
        t = config.tributacao("saida")
        self.assertEqual((t.pis_cofins_grupo, t.pis_cofins_natureza, t.icms_reducao_base, t.icms_acrescimo),
                         ("4.3.14", "101", Decimal("10.5"), Decimal("2")))

    def test_entrada_de_nfe_so_com_o_que_se_aplica(self):
        self.configurar()
        config = self.vinculo.configuracoes.get()
        r = self.client.get(reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "entrada"]))
        for nome in ("cfop", "icms_cst", "icms_aliquota", "pis_cst", "pis_aliquota", "cofins_cst", "cofins_aliquota",
                     "ipi_cst", "ipi_aliquota", "exige_gta"):
            self.assertContains(r, f'name="{nome}"')
        for nome in ("icms_zerar_base", "icms_modalidade_base", "icms_reducao_base", "icms_diferimento", "icms_acrescimo",
                     "pis_cofins_grupo", "pis_cofins_natureza", "ibscbs_cst", "cclasstrib"):
            self.assertNotContains(r, f'name="{nome}"')
        r = self.tributacao(config, "entrada", cfop="1102", icms_cst="102", pis_cst="98", cofins_cst="98",
                            ipi_cst="03", exige_gta="on")
        self.assertEqual(r.status_code, 302)
        t = config.tributacao("entrada")
        self.assertEqual((t.cfop, t.ipi_cst, t.exige_gta, t.ibscbs_cst), ("1102", "03", True, ""))

    def test_nfe_saida_tem_icms_st_e_enquadramento(self):
        self.configurar(**{"config-regime": "3"})
        config = self.vinculo.configuracoes.get()
        url = reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "saida"])
        r = self.client.get(url)
        for nome in ("icms_st_modalidade", "icms_st_mva", "icms_st_aliquota", "icms_st_reducao_base",
                     "icms_st_valor_pauta", "icms_st_somar_ipi", "ipi_enquadramento"):
            self.assertContains(r, f'name="{nome}"')
        self.assertContains(r, 'value="999"')  # enquadramento padrão
        self.tributacao(config, icms_cst="10", icms_aliquota="17,00", icms_st_modalidade="4", icms_st_mva="40,00",
                        icms_st_aliquota="17,00", icms_st_somar_ipi="on", ipi_cst="50", ipi_aliquota="5,00",
                        ipi_enquadramento="")
        t = config.tributacao("saida")
        self.assertEqual((t.icms_st_modalidade, t.icms_st_mva, t.icms_st_aliquota, t.icms_st_somar_ipi, t.ipi_enquadramento),
                         ("4", Decimal("40"), Decimal("17"), True, "999"))
        r = self.tributacao(config, icms_cst="00", ipi_enquadramento="12")
        self.assertIn("ipi_enquadramento", r.context["form"].errors)
        # Entrada e NFC-e não têm
        r = self.client.get(reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "entrada"]))
        self.assertNotContains(r, 'name="icms_st_mva"')
        self.assertNotContains(r, 'name="ipi_enquadramento"')

    def test_zerar_base_zera_a_aliquota(self):
        self.configurar(**{"config-regime": "3"})
        config = self.vinculo.configuracoes.get()
        self.tributacao(config, icms_cst="00", icms_aliquota="17,00", icms_zerar_base="on")
        t = config.tributacao("saida")
        self.assertTrue(t.icms_zerar_base)
        self.assertEqual(t.icms_aliquota, 0)

    def test_natureza_da_receita(self):
        self.configurar()
        config = self.vinculo.configuracoes.get()
        r = self.tributacao(config, pis_cofins_natureza="12")
        self.assertEqual(r.context["form"].errors["pis_cofins_natureza"], ["A natureza da receita tem 3 dígitos."])
        r = self.tributacao(config, pis_cofins_natureza="101")
        self.assertIn("pis_cofins_grupo", r.context["form"].errors)
        # NF-e continua com IPI
        self.assertContains(self.client.get(reverse("vinculo_tributacao", args=[self.vinculo.pk, config.pk, "saida"])),
                            'name="ipi_cst"')

    def test_buscas(self):
        cfops = lambda **p: [i["id"] for i in self.client.get(reverse("cfop_busca"), p).json()["itens"]]
        self.assertEqual(cfops(digitos="5,6"), ["5102", "6102"])
        self.assertEqual(cfops(digitos="1", q="comercializa"), ["1102"])
        classes = lambda cst: [i["id"] for i in self.client.get(reverse("cclasstrib_busca"), {"pai": cst}).json()["itens"]]
        self.assertEqual((classes("000"), classes("200"), classes("")), (["000001"], [], []))
        produtos = self.client.get(reverse("produto_busca"), {"q": "cola"}).json()["itens"]
        self.assertEqual([i["id"] for i in produtos], [self.produto.pk])


class VinculosPadraoTests(ProdutoTestCase):
    """Os 3 vínculos que todo sistema novo recebe, com as configurações pela UF e pelo regime."""

    def configs(self):
        from .models import ConfiguracaoFiscal
        return ConfiguracaoFiscal.objects.select_related("vinculo")

    def test_toda_instancia_ja_tem_os_tres_vinculos(self):
        from .models import VinculoFiscal
        from .vinculos_padrao import NOMES
        self.assertEqual(set(VinculoFiscal.objects.values_list("nome", flat=True)) & set(NOMES), set(NOMES))
        self.assertFalse(VinculoFiscal.objects.filter(padrao=True).exists())  # nenhum vem como padrão

    def test_regime_normal(self):
        from .vinculos_padrao import configurar_vinculos_padrao
        self.assertEqual(configurar_vinculos_padrao("mt", "presumido"), 6)  # 3 vínculos x (NF-e + NFC-e)
        st = self.configs().get(vinculo__nome="ICMS cobrado anteriormente por substituição", documento="nfe")
        self.assertEqual((st.uf_origem, st.uf_destino, st.regime), ("MT", "**", "3"))
        saida, entrada = st.tributacao("saida"), st.tributacao("entrada")
        self.assertEqual((saida.cfop, saida.icms_cst, saida.pis_cst, saida.cofins_cst, saida.ipi_cst, saida.ibscbs_cst, saida.exige_gta),
                         ("6403", "60", "07", "07", "53", "", False))
        self.assertEqual((entrada.cfop, entrada.icms_cst, entrada.pis_cst, entrada.cofins_cst, entrada.ipi_cst),
                         ("1102", "", "99", "99", "03"))
        nfce = self.configs().get(vinculo__nome="ICMS cobrado anteriormente por substituição", documento="nfce")
        self.assertEqual((nfce.uf_destino, nfce.tributacoes.count()), ("MT", 1))  # NFC-e: só saída, interna
        self.assertEqual((nfce.tributacao("saida").cfop, nfce.tributacao("saida").ipi_cst), ("5403", ""))
        tributado = self.configs().get(vinculo__nome="ICMS Tributado - PIS Isento", documento="nfce").tributacao("saida")
        self.assertEqual((tributado.cfop, tributado.icms_cst, tributado.icms_aliquota), ("5102", "00", 0))
        isento = self.configs().get(vinculo__nome="ICMS Isento - PIS Isento", documento="nfe").tributacao("saida")
        self.assertEqual((isento.cfop, isento.icms_cst), ("6102", "40"))

    def test_simples_e_mei_usam_csosn(self):
        from .vinculos_padrao import configurar_vinculos_padrao
        configurar_vinculos_padrao("SP", "mei")
        cst = lambda nome: self.configs().get(vinculo__nome=nome, documento="nfe").tributacao("saida").icms_cst
        self.assertEqual((cst("ICMS cobrado anteriormente por substituição"), cst("ICMS Tributado - PIS Isento"),
                          cst("ICMS Isento - PIS Isento")), ("500", "102", "103"))
        self.assertEqual(self.configs().first().regime, "4")

    def test_nao_duplica_nem_altera_o_que_existe(self):
        from .vinculos_padrao import configurar_vinculos_padrao
        configurar_vinculos_padrao("MT", "simples")
        t = self.configs().get(vinculo__nome="ICMS Tributado - PIS Isento", documento="nfe").tributacao("saida")
        t.icms_cst = "101"
        t.save()
        self.assertEqual(configurar_vinculos_padrao("MT", "simples"), 0)
        t.refresh_from_db()
        self.assertEqual(t.icms_cst, "101")

    def test_regime_ou_uf_invalidos(self):
        from .vinculos_padrao import configurar_vinculos_padrao
        with self.assertRaises(ValueError):
            configurar_vinculos_padrao("MT", "lucro")
        with self.assertRaises(ValueError):
            configurar_vinculos_padrao("MTX", "simples")

    def test_tributacao_padrao_passa_na_validacao_da_tela(self):
        """O que a geração grava é aceito pela tela (CFOP/CST/PIS/IPI válidos para cada situação)."""
        from fiscal.models import Cfop
        from .forms_vinculos import TributacaoFiscalForm
        from .vinculos_padrao import configurar_vinculos_padrao
        for codigo in ("1102", "5102", "5403", "6102", "6403"):
            Cfop.objects.get_or_create(codigo=codigo, defaults={"descricao": codigo})
        configurar_vinculos_padrao("MT", "simples")
        configurar_vinculos_padrao("MT", "real")
        from django.forms.models import model_to_dict
        for config in self.configs():
            for t in config.tributacoes.all():
                dados = {k: ("on" if v is True else "" if v in (None, False) else str(v).replace(".", ","))
                         for k, v in model_to_dict(t).items()}
                form = TributacaoFiscalForm(dados, instance=t, configuracao=config, operacao=t.operacao)
                self.assertTrue(form.is_valid(), f"{config} {t.operacao}: {form.errors.as_data()}")
