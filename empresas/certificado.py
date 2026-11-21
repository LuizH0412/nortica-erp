"""
Certificado digital A1 (.pfx/.p12) da empresa, usado para assinar e transmitir as notas à Sefaz.

- ler_certificado(arquivo, senha): abre o .pfx com a senha e devolve titular, CPF/CNPJ e validade.
- cifrar / decifrar: o arquivo e a senha ficam guardados criptografados no banco (nunca na pasta media/).
  A chave vem de CHAVE_CERTIFICADOS no .env (ou, se não houver, da SECRET_KEY). Se essa chave mudar,
  os certificados já guardados não abrem mais e precisam ser enviados de novo.
- carregar(certificado): devolve (chave_privada, certificado) prontos para assinar o XML (para a emissão).
"""
import base64
import hashlib
import re
from datetime import timezone as tz

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID
from django.conf import settings

TAMANHO_MAXIMO = 200 * 1024  # um A1 tem poucos KB
OID_CNPJ = "2.16.76.1.3.3"  # ICP-Brasil: CNPJ da pessoa jurídica titular (no "nome alternativo" do certificado)


class CertificadoInvalido(Exception):
    """Mensagem pronta para mostrar na tela."""


def _fernet():
    material = getattr(settings, "CHAVE_CERTIFICADOS", "") or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest()))


def cifrar(dados: bytes) -> bytes:
    return _fernet().encrypt(dados)


def decifrar(dados: bytes) -> bytes:
    try:
        return _fernet().decrypt(bytes(dados))
    except InvalidToken:
        raise CertificadoInvalido(
            "Não foi possível abrir o certificado guardado (a chave de criptografia mudou). Envie o certificado de novo."
        )


def _documento_do_certificado(certificado, titular):
    """CPF/CNPJ do titular: o CNPJ ICP-Brasil no nome alternativo, ou o número depois do ":" no nome."""
    try:
        alternativos = certificado.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        for nome in alternativos:
            if getattr(nome, "type_id", None) is not None and nome.type_id.dotted_string == OID_CNPJ:
                numeros = re.sub(r"\D", "", nome.value.decode("latin-1", "ignore"))
                if len(numeros) >= 14:
                    return numeros[-14:]
    except Exception:
        pass
    achado = re.search(r":(\d{14}|\d{11})\b", titular)
    return achado.group(1) if achado else ""


def ler_certificado(conteudo: bytes, senha: str):
    """{"titular", "documento", "emitido_em", "validade"} ou CertificadoInvalido."""
    if len(conteudo) > TAMANHO_MAXIMO:
        raise CertificadoInvalido("Arquivo grande demais para um certificado A1.")
    try:
        chave, certificado, _ = pkcs12.load_key_and_certificates(conteudo, (senha or "").encode())
    except ValueError:
        raise CertificadoInvalido("Senha incorreta, ou o arquivo não é um certificado A1 (.pfx/.p12).")
    if certificado is None or chave is None:
        raise CertificadoInvalido("O arquivo não tem o certificado e a chave privada (precisa ser um A1 completo).")
    nomes = certificado.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    titular = nomes[0].value if nomes else certificado.subject.rfc4514_string()
    return {
        "titular": titular[:200],
        "documento": _documento_do_certificado(certificado, titular),
        "emitido_em": certificado.not_valid_before_utc.astimezone(tz.utc),
        "validade": certificado.not_valid_after_utc.astimezone(tz.utc),
    }


def carregar(certificado_digital):
    """(chave_privada, certificado) do certificado guardado da empresa — para assinar o XML na emissão."""
    conteudo = decifrar(certificado_digital.arquivo_cifrado)
    senha = decifrar(certificado_digital.senha_cifrada).decode()
    chave, certificado, _ = pkcs12.load_key_and_certificates(conteudo, senha.encode())
    return chave, certificado
