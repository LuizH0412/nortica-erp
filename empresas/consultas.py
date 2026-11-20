import json
import re
import urllib.error
import urllib.request

from django.core.cache import cache
from django.core.exceptions import ValidationError

from localidades.models import Municipio, normalizar

from .validators import limpar_documento, validar_documento

BRASILAPI = "https://brasilapi.com.br/api"


class ConsultaErro(Exception):
    """Erro com mensagem já pronta para mostrar à pessoa."""


def _buscar_json(url):
    requisicao = urllib.request.Request(
        url, headers={"User-Agent": "Nexum/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=6) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code in (400, 404):
            return None
        if erro.code == 429:
            raise ConsultaErro(
                "Foram feitas consultas demais em pouco tempo. Aguarde um minuto e tente "
                "de novo, ou preencha os dados manualmente."
            )
        raise ConsultaErro(
            "O serviço de consulta está com problemas agora. Você pode preencher os dados "
            "manualmente e tentar a busca mais tarde."
        )
    except (OSError, ValueError):
        raise ConsultaErro(
            "Não conseguimos consultar agora porque o serviço não respondeu. Você pode "
            "preencher os dados manualmente e tentar a busca mais tarde."
        )


def _municipio_dict(municipio):
    if not municipio:
        return None
    return {"id": municipio.pk, "nome": municipio.nome, "uf": municipio.uf}


def consultar_cnpj(documento):
    cnpj = limpar_documento(documento)
    if not cnpj:
        raise ConsultaErro("Digite o CNPJ antes de buscar.")
    if len(cnpj) == 11:
        raise ConsultaErro(
            "A busca automática funciona só para CNPJ. Para CPF, preencha os dados manualmente."
        )
    try:
        validar_documento(cnpj)
    except ValidationError:
        raise ConsultaErro("Esse CNPJ não parece válido. Confira os números e tente novamente.")

    chave = f"consulta:cnpj:{cnpj}"
    dados = cache.get(chave)
    if dados is None:
        b = _buscar_json(f"{BRASILAPI}/cnpj/v1/{cnpj}")
        if not b:
            raise ConsultaErro(
                "Não encontramos esse CNPJ na base da Receita. Se a empresa é muito recente, "
                "ela pode demorar a aparecer. Você pode preencher os dados manualmente."
            )
        tipo = (b.get("descricao_tipo_de_logradouro") or "").strip()
        rua = (b.get("logradouro") or "").strip()
        codigo = str(b.get("codigo_municipio_ibge") or "")
        municipio = Municipio.objects.filter(pk=codigo).first() if codigo else None
        dados = {
            "razao_social": (b.get("razao_social") or "").strip(),
            "nome_fantasia": (b.get("nome_fantasia") or "").strip(),
            "cep": re.sub(r"\D", "", b.get("cep") or ""),
            "logradouro": f"{tipo} {rua}".strip(),
            "numero": (b.get("numero") or "").strip(),
            "complemento": (b.get("complemento") or "").strip(),
            "bairro": (b.get("bairro") or "").strip(),
            "telefone": re.sub(r"\D", "", b.get("ddd_telefone_1") or "")[:11],
            "email": (b.get("email") or "").strip().lower(),
            "municipio": _municipio_dict(municipio),
        }
        cache.set(chave, dados, 60 * 60)
    return dados


def consultar_cep(cep):
    cep = re.sub(r"\D", "", cep or "")
    if len(cep) != 8:
        raise ConsultaErro("Digite o CEP completo, com 8 números.")

    chave = f"consulta:cep:{cep}"
    dados = cache.get(chave)
    if dados is None:
        b = _buscar_json(f"{BRASILAPI}/cep/v1/{cep}")
        if not b:
            raise ConsultaErro(
                "Não encontramos esse CEP. Confira os números ou preencha o endereço manualmente."
            )
        uf = (b.get("state") or "").upper()
        municipio = Municipio.objects.filter(
            uf=uf, nome_busca=normalizar(b.get("city") or "")
        ).first()
        dados = {
            "logradouro": (b.get("street") or "").strip(),
            "bairro": (b.get("neighborhood") or "").strip(),
            "uf": uf,
            "municipio": _municipio_dict(municipio),
        }
        cache.set(chave, dados, 24 * 60 * 60)
    return dados