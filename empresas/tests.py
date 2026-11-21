from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from core.base_testes import MASTER, InstanciaTestCase

from .models import Empresa
from .selecao import SESSAO_CHAVE, empresas_do_usuario, resolver_empresa, sistema_multiloja
from .validators import cnpj_valido, cpf_valido, limpar_documento, validar_documento


class ValidadoresTests(SimpleTestCase):
    def test_limpar_documento_tira_mascara_e_poe_maiusculas(self):
        self.assertEqual(limpar_documento("11.222.333/0001-81"), "11222333000181")
        self.assertEqual(limpar_documento("12.abc.345/01de-35"), "12ABC34501DE35")
        self.assertEqual(limpar_documento(None), "")

    def test_cpf(self):
        self.assertTrue(cpf_valido("52998224725"))
        self.assertFalse(cpf_valido("52998224724"))  # dígito errado
        self.assertFalse(cpf_valido("11111111111"))  # todos iguais
        self.assertFalse(cpf_valido("5299822472"))   # curto

    def test_cnpj_numerico(self):
        self.assertTrue(cnpj_valido("11222333000181"))
        self.assertTrue(cnpj_valido("06220266000126"))
        self.assertFalse(cnpj_valido("11222333000182"))
        self.assertFalse(cnpj_valido("00000000000000"))

    def test_cnpj_alfanumerico(self):
        # Exemplo oficial da Receita Federal para o CNPJ alfanumérico
        self.assertTrue(cnpj_valido("12ABC34501DE35"))
        self.assertFalse(cnpj_valido("12ABC34501DE36"))
        self.assertFalse(cnpj_valido("12ABC34501DEAB"))  # dígitos verificadores são sempre números

    def test_validar_documento(self):
        validar_documento("529.982.247-25")
        validar_documento("11.222.333/0001-81")
        for invalido in ("529.982.247-24", "11.222.333/0001-82", "123"):
            with self.subTest(invalido=invalido), self.assertRaises(ValidationError):
                validar_documento(invalido)


class ResolverEmpresaTests(InstanciaTestCase):
    def requisicao(self, usuario, sessao=None):
        return SimpleNamespace(user=usuario, session=sessao or {})

    def test_uma_empresa_entra_direto(self):
        empresa = self.criar_empresa()
        usuario = self.criar_usuario(empresas=[empresa])
        self.assertFalse(sistema_multiloja())
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (empresa, False))

    def test_empresa_inativa_nao_torna_o_sistema_multiloja(self):
        empresa = self.criar_empresa()
        self.criar_empresa(ativa=False)
        self.assertFalse(sistema_multiloja())
        usuario = self.criar_usuario(empresas=[empresa])
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (empresa, False))

    def test_uma_empresa_sem_acesso(self):
        self.criar_empresa()
        usuario = self.criar_usuario()
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (None, False))

    def test_multiloja_com_acesso_a_uma(self):
        a = self.criar_empresa()
        self.criar_empresa()
        usuario = self.criar_usuario(empresas=[a])
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (a, False))

    def test_multiloja_com_acesso_a_varias_precisa_escolher(self):
        a, b = self.criar_empresa(), self.criar_empresa()
        usuario = self.criar_usuario(empresas=[a, b])
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (None, True))

    def test_multiloja_sem_acesso(self):
        self.criar_empresa()
        self.criar_empresa()
        usuario = self.criar_usuario()
        self.assertEqual(resolver_empresa(self.requisicao(usuario)), (None, False))

    def test_usa_a_empresa_da_sessao(self):
        a, b = self.criar_empresa(), self.criar_empresa()
        usuario = self.criar_usuario(empresas=[a, b])
        resultado = resolver_empresa(self.requisicao(usuario, {SESSAO_CHAVE: b.pk}))
        self.assertEqual(resultado, (b, False))

    def test_ignora_sessao_com_empresa_sem_acesso(self):
        a, b, c = self.criar_empresa(), self.criar_empresa(), self.criar_empresa()
        usuario = self.criar_usuario(empresas=[a, b])
        resultado = resolver_empresa(self.requisicao(usuario, {SESSAO_CHAVE: c.pk}))
        self.assertEqual(resultado, (None, True))

    def test_empresas_do_usuario(self):
        ativa = self.criar_empresa()
        inativa = self.criar_empresa(ativa=False)
        comum = self.criar_usuario(empresas=[ativa, inativa])
        master = self.criar_usuario(nivel=MASTER)
        self.assertQuerySetEqual(empresas_do_usuario(comum), [ativa])
        self.assertQuerySetEqual(
            empresas_do_usuario(master), [ativa, inativa], ordered=False
        )


class EscolhaDeEmpresaTests(InstanciaTestCase):
    """Fluxo pelo middleware: redirecionamentos e troca de empresa."""

    def test_sem_empresa_vai_para_sem_acesso(self):
        self.criar_empresa()
        self.client.force_login(self.criar_usuario())
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("sem_acesso"),
            fetch_redirect_response=False,
        )

    def test_varias_empresas_pede_para_escolher_e_troca(self):
        a, b = self.criar_empresa(), self.criar_empresa()
        self.client.force_login(self.criar_usuario(empresas=[a, b]))
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("escolher_empresa"),
            fetch_redirect_response=False,
        )
        self.client.post(reverse("trocar_empresa", args=[b.pk]))
        resposta = self.client.get(reverse("home"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["empresa_atual"], b)

    def test_nao_troca_para_empresa_sem_acesso(self):
        a, b = self.criar_empresa(), self.criar_empresa()
        self.client.force_login(self.criar_usuario(empresas=[a]))
        resposta = self.client.post(reverse("trocar_empresa", args=[b.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertNotIn(SESSAO_CHAVE, self.client.session)


class BuscaDeEmpresasTests(InstanciaTestCase):
    def setUp(self):
        super().setUp()
        self.matriz = Empresa.objects.create(
            unidade="Matriz", razao_social="Softcom Tecnologia LTDA",
            nome_fantasia="Softcom", documento="06220266000126",
        )
        self.filial = Empresa.objects.create(
            unidade="Filial Centro", razao_social="Loja Azul Comércio LTDA",
            nome_fantasia="Loja Azul", documento="11222333000181",
        )
        self.client.force_login(self.criar_usuario(nivel=MASTER))
        # Com duas empresas ativas o sistema pede para escolher uma antes
        self.client.post(reverse("trocar_empresa", args=[self.matriz.pk]))

    def buscar(self, q, **extra):
        resposta = self.client.get(reverse("empresa_lista"), {"q": q, **extra})
        return [e.unidade for e in resposta.context["empresas"]]

    def test_busca_por_unidade_nome_e_razao_social(self):
        self.assertEqual(self.buscar("centro"), ["Filial Centro"])
        self.assertEqual(self.buscar("softcom"), ["Matriz"])
        self.assertEqual(self.buscar("comércio"), ["Filial Centro"])

    def test_busca_por_cnpj_com_ou_sem_mascara(self):
        self.assertEqual(self.buscar("06.220.266/0001-26"), ["Matriz"])
        self.assertEqual(self.buscar("11222333"), ["Filial Centro"])

    def test_busca_respeita_o_filtro_de_desativadas(self):
        self.filial.ativa = False
        self.filial.save()
        self.assertEqual(self.buscar("loja"), [])
        self.assertEqual(self.buscar("loja", desativados="1"), ["Filial Centro"])


class SeletorDeEmpresaTests(InstanciaTestCase):
    """Topo da tela: mostra a unidade atual e troca de empresa sem sair do sistema."""

    def test_uma_empresa_so_indica_sem_lista(self):
        matriz = self.criar_empresa(unidade="MATRIZ")
        self.client.force_login(self.criar_usuario(empresas=[matriz]))
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, 'title="Empresa atual"')
        self.assertContains(resposta, "MATRIZ")
        self.assertNotContains(resposta, "data-dropdown")

    def test_varias_empresas_lista_e_troca(self):
        matriz = self.criar_empresa(unidade="MATRIZ")
        filial = self.criar_empresa(unidade="FILIAL CENTRO")
        self.client.force_login(self.criar_usuario(empresas=[matriz, filial]))
        self.client.post(reverse("trocar_empresa", args=[matriz.pk]))

        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "Empresa atual: MATRIZ")
        self.assertContains(resposta, reverse("trocar_empresa", args=[filial.pk]))
        self.assertEqual(resposta.context["empresa_atual"], matriz)

        resposta = self.client.post(reverse("trocar_empresa", args=[filial.pk]), follow=True)
        self.assertEqual(resposta.context["empresa_atual"], filial)
        self.assertContains(resposta, "Você está agora na empresa FILIAL CENTRO.")
        self.assertContains(resposta, "Empresa atual: FILIAL CENTRO")

    def test_lista_so_empresas_que_a_pessoa_acessa(self):
        matriz, filial = self.criar_empresa(unidade="MATRIZ"), self.criar_empresa(unidade="FILIAL")
        outra = self.criar_empresa(unidade="SEM ACESSO")
        self.client.force_login(self.criar_usuario(empresas=[matriz, filial]))
        self.client.post(reverse("trocar_empresa", args=[matriz.pk]))
        resposta = self.client.get(reverse("home"))
        self.assertNotContains(resposta, reverse("trocar_empresa", args=[outra.pk]))


class FiscalTributarioTests(InstanciaTestCase):
    """Aba Fiscal da empresa: regime, alíquota de crédito, tipo de inventário e dedução do ICMS."""

    def test_salva_os_campos_fiscais(self):
        from core.base_testes import MASTER
        empresa = self.criar_empresa()
        self.client.force_login(self.criar_usuario(nivel=MASTER))
        self.client.post(reverse("trocar_empresa", args=[empresa.pk]))
        dados = {
            "unidade": empresa.unidade, "razao_social": "Empresa Fiscal LTDA", "documento": "11.222.333/0001-81",
            "nome_nos_documentos": "fantasia", "ativa": "on",
            "regime_tributario": "1", "aliquota_credito": "1,25", "tipo_inventario": "fisico",
            "deduzir_icms_base_pis_cofins": "on",
        }
        r = self.client.post(reverse("empresa_editar", args=[empresa.pk]), dados)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        empresa.refresh_from_db()
        self.assertEqual((empresa.regime_tributario, empresa.aliquota_credito, empresa.tipo_inventario,
                          empresa.deduzir_icms_base_pis_cofins), ("1", Decimal("1.25"), "fisico", True))
        # Sem tipo de inventário e sem alíquota: contábil e zero
        dados.update(tipo_inventario="", aliquota_credito="", deduzir_icms_base_pis_cofins="")
        self.client.post(reverse("empresa_editar", args=[empresa.pk]), dados)
        empresa.refresh_from_db()
        self.assertEqual((empresa.tipo_inventario, empresa.aliquota_credito, empresa.deduzir_icms_base_pis_cofins),
                         ("contabil", 0, False))
        r = self.client.get(reverse("empresa_editar", args=[empresa.pk]))
        self.assertContains(r, "Fiscal / tributário")


def gerar_pfx(nome="EMPRESA TESTE LTDA:11222333000181", senha="1234", dias=365, inicio_dias=-1):
    """Certificado A1 de teste (autoassinado), no formato da ICP-Brasil: "RAZÃO SOCIAL:CNPJ"."""
    from datetime import datetime, timedelta
    from datetime import timezone as tz

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeito = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    agora = datetime.now(tz.utc)
    certificado = (
        x509.CertificateBuilder().subject_name(sujeito).issuer_name(sujeito).public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora + timedelta(days=inicio_dias)).not_valid_after(agora + timedelta(days=dias))
        .sign(chave, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"teste", chave, certificado, None, serialization.BestAvailableEncryption(senha.encode()),
    )


class CertificadoDigitalTests(InstanciaTestCase):
    """Aba Fiscal da empresa: certificado digital A1."""

    def setUp(self):
        super().setUp()
        self.empresa = self.criar_empresa()
        Empresa.objects.filter(pk=self.empresa.pk).update(documento="11222333000181")
        self.empresa.refresh_from_db()
        self.client.force_login(self.criar_usuario(nivel=MASTER))
        self.client.post(reverse("trocar_empresa", args=[self.empresa.pk]))
        self.url = reverse("empresa_certificado_enviar", args=[self.empresa.pk])

    def enviar(self, conteudo=None, senha="1234", nome="cert.pfx"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        arquivo = SimpleUploadedFile(nome, gerar_pfx() if conteudo is None else conteudo)
        return self.client.post(self.url, {"certificado": arquivo, "senha": senha}, follow=True)

    def test_envia_mostra_e_guarda_criptografado(self):
        from .certificado import carregar
        from .models import CertificadoDigital
        pfx = gerar_pfx()
        r = self.enviar(pfx)
        self.assertContains(r, "Certificado de EMPRESA TESTE LTDA:11222333000181 adicionado")
        self.assertEqual(r.redirect_chain[-1][0], reverse("empresa_editar", args=[self.empresa.pk]) + "#fiscal")
        c = CertificadoDigital.objects.get(empresa=self.empresa)
        self.assertEqual((c.titular, c.documento, c.descricao),
                         ("EMPRESA TESTE LTDA:11222333000181", "11222333000181", "EMPRESA TESTE LTDA:11222333000181"))
        # Nada em texto puro: nem o arquivo nem a senha
        self.assertNotEqual(bytes(c.arquivo_cifrado), pfx)
        self.assertNotIn(b"1234", bytes(c.senha_cifrada))
        chave, certificado = carregar(c)  # mas dá para abrir na hora de assinar
        self.assertIsNotNone(chave)
        pagina = self.client.get(reverse("empresa_editar", args=[self.empresa.pk]))
        self.assertContains(pagina, "EMPRESA TESTE LTDA:11222333000181")
        self.assertContains(pagina, "Válido")
        self.assertNotContains(pagina, 'id="cert-senha"')  # com certificado, o formulário de envio some
        self.assertNotContains(self.client.get(reverse("empresa_editar", args=[self.criar_empresa().pk])), 'name="descricao"')

    def test_senha_errada_vencido_e_de_outro_cnpj(self):
        from .models import CertificadoDigital
        self.assertContains(self.enviar(senha="errada"), "Senha incorreta")
        self.assertContains(self.enviar(gerar_pfx(dias=-1, inicio_dias=-400)), "Este certificado venceu em")
        self.assertContains(self.enviar(gerar_pfx(nome="OUTRA LTDA:99888777000166")), "é de outro CPF/CNPJ (99888777000166)")
        self.assertContains(self.enviar(nome="cert.txt"), "arquivo .pfx ou .p12")
        self.assertContains(self.enviar(b"isto nao e certificado"), "Senha incorreta, ou o arquivo não é um certificado A1")
        self.assertFalse(CertificadoDigital.objects.exists())

    def test_filial_usa_o_da_matriz_e_aviso_de_vencimento(self):
        Empresa.objects.filter(pk=self.empresa.pk).update(documento="11222333000262")  # filial: mesmo CNPJ base
        self.enviar(gerar_pfx(dias=10))
        pagina = self.client.get(reverse("empresa_editar", args=[self.empresa.pk]))
        self.assertContains(pagina, "Vence em ")

    def test_excluir_e_nao_impede_excluir_empresa(self):
        from .models import CertificadoDigital
        self.enviar()
        self.assertEqual(self.empresa.vinculos_que_impedem_exclusao(), [])
        self.client.post(reverse("empresa_certificado_excluir", args=[self.empresa.pk]))
        self.assertFalse(CertificadoDigital.objects.exists())

    def test_so_quem_configura(self):
        from core.base_testes import COMUM
        self.client.force_login(self.criar_usuario(nivel=COMUM, empresas=[self.empresa]))
        from .models import CertificadoDigital
        self.assertEqual(self.enviar().status_code, 403)
        self.assertFalse(CertificadoDigital.objects.exists())
