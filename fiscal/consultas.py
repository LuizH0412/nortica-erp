"""
Consultas fiscais usadas no cadastro do produto:

- cests_da_ncm(ncm): os CESTs cujo NCM/SH (completo ou parcial) abrange a NCM.
- carga_tributaria(ncm, uf, origem): "De olho no imposto" (federal + estadual + municipal) pela tabela do IBPT.

A tabela do IBPT é consultada na CDN pública da NFe.io (https://github.com/nfe/ibpt), que republica a
tabela oficial por NCM e UF, e fica guardada em AliquotaIbpt. Uma consulta vale por VALIDADE; sem internet,
usa o que já estiver guardado.
"""
import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from .models import AliquotaIbpt, Cest

URL_IBPT = "https://ibpt.nfe.io/ncm/{uf}/{ncm}.json"
VALIDADE = timedelta(days=7)

# Origens com conteúdo de importação: usam a alíquota federal de importados
ORIGENS_IMPORTADAS = {"1", "2", "3", "6", "7", "8"}


def cests_da_ncm(ncm):
    ncm = "".join(c for c in (ncm or "") if c.isdigit())
    if len(ncm) != 8:
        return Cest.objects.none()
    prefixos = [ncm[:k] for k in range(2, 9)]
    return Cest.objects.filter(ncms__ncm__in=prefixos).distinct().order_by("codigo")


def _baixar_ibpt(ncm, uf):
    """Dados da CDN (dict) ou None se a NCM não estiver na tabela. Erros de rede sobem como exceção."""
    requisicao = urllib.request.Request(URL_IBPT.format(uf=uf.lower(), ncm=ncm), headers={"User-Agent": "Nexum/1.0"})
    try:
        with urllib.request.urlopen(requisicao, timeout=6) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code in (403, 404):
            return None
        raise


def aliquota_ibpt(ncm, uf):
    """AliquotaIbpt da NCM na UF (consulta a tabela se o guardado estiver velho) ou None."""
    guardada = AliquotaIbpt.objects.filter(ncm=ncm, uf=uf).first()
    if guardada and timezone.now() - guardada.consultado_em < VALIDADE:
        return guardada
    try:
        dados = _baixar_ibpt(ncm, uf)
    except Exception:
        return guardada  # sem internet: fica com o que já tinha
    if not dados:
        if guardada:
            guardada.delete()  # saiu da tabela
        return None
    vigencia = dados.get("effectiveDate")
    try:
        vigencia = date.fromisoformat(vigencia) if vigencia else None
    except ValueError:
        vigencia = None
    aliquota, _ = AliquotaIbpt.objects.update_or_create(
        ncm=ncm, uf=uf,
        defaults={
            "nacional_federal": Decimal(str(dados.get("federalNationalRate") or 0)),
            "importados_federal": Decimal(str(dados.get("federalImportedRate") or 0)),
            "estadual": Decimal(str(dados.get("stateRate") or 0)),
            "municipal": Decimal(str(dados.get("municipalRate") or 0)),
            "versao": str(dados.get("version") or "")[:20],
            "vigencia_inicio": vigencia,
            "fonte": str(dados.get("source") or "IBPT")[:80],
            "consultado_em": timezone.now(),
        },
    )
    return aliquota


def carga_tributaria(ncm, uf, origem):
    """{"federal", "estadual", "municipal", "total", "fonte"} ou None (sem NCM, sem UF ou fora da tabela)."""
    if not ncm or not uf:
        return None
    a = aliquota_ibpt(ncm, uf)
    if a is None:
        return None
    federal = a.importados_federal if str(origem) in ORIGENS_IMPORTADAS else a.nacional_federal
    return {
        "federal": federal, "estadual": a.estadual, "municipal": a.municipal,
        "total": federal + a.estadual + a.municipal,
        "fonte": f"IBPT {a.versao} · {uf}".strip(),
    }
