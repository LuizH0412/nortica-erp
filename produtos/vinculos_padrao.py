"""
Vínculos fiscais que todo sistema novo já recebe prontos.

- Os 3 vínculos (só o nome) nascem com a instância (migração 0014_vinculos_padrao).
- As configurações e a tributação dependem da UF e do regime da empresa: quem gera o sistema chama
  configurar_vinculos_padrao(uf, regime) — hoje o comando criar_instancia (--uf/--regime) ou
  configurar_vinculos_padrao; no futuro, o sistema interno da Nortica, ao gerar a instância já com a empresa.

Cada vínculo ganha duas configurações:
  NF-e  da UF da empresa para todas as UFs (entrada e saída)
  NFC-e dentro da UF da empresa (saída)

O CFOP de saída da NF-e "para todas" é o interestadual (6.xxx); na emissão para a própria UF ele vira 5.xxx.
Empresas cadastradas depois não recebem nada automaticamente: o técnico configura (ou clona) à mão.
"""
from django.db import transaction

from fiscal.tabelas import REGIMES_SIMPLES, TODAS_UFS

from .models import ConfiguracaoFiscal, TributacaoFiscal, VinculoFiscal

# Nomes aceitos no comando (além do próprio CRT, que é o que a empresa guarda). MEI usa a tributação do Simples.
CRT_DO_REGIME = {"simples": "1", "sublimite": "2", "normal": "3", "presumido": "3", "real": "3", "mei": "4"}

# Entrada (compra) igual em todos: CST/CSOSN do ICMS em branco
ENTRADA = {"cfop": "1102", "icms_cst": "", "pis_cst": "99", "cofins_cst": "99", "ipi_cst": "03"}

# Saída: PIS/COFINS 07 e IPI 53 (a NFC-e não tem IPI); IBS/CBS em branco; alíquota de ICMS 0 (o técnico preenche)
SAIDA = {"pis_cst": "07", "cofins_cst": "07"}
IPI_SAIDA = "53"

# nome -> {regime: (CST/CSOSN do ICMS, CFOP NF-e, CFOP NFC-e)}
VINCULOS = [
    ("ICMS cobrado anteriormente por substituição", {
        "normal": ("60", "6403", "5403"),
        "simples": ("500", "6403", "5403"),
    }),
    ("ICMS Tributado - PIS Isento", {
        "normal": ("00", "6102", "5102"),
        "simples": ("102", "6102", "5102"),
    }),
    ("ICMS Isento - PIS Isento", {
        "normal": ("40", "6102", "5102"),
        "simples": ("103", "6102", "5102"),
    }),
]
NOMES = [nome for nome, _ in VINCULOS]


def crt_do_regime(regime):
    """Aceita o CRT (1 a 4, como a empresa guarda) ou o nome (simples, sublimite, normal, presumido, real, mei)."""
    regime = str(regime or "").strip().lower()
    if regime in {"1", "2", "3", "4"}:
        return regime
    if regime not in CRT_DO_REGIME:
        raise ValueError(f"Regime desconhecido: {regime!r}. Use o CRT (1 a 4) ou simples, sublimite, normal, mei.")
    return CRT_DO_REGIME[regime]


@transaction.atomic
def configurar_vinculos_padrao(uf, regime):
    """
    Cria (se ainda não existirem) os 3 vínculos padrão com as configurações NF-e e NFC-e da UF e do regime.
    O que já existe não é alterado. Devolve quantas configurações foram criadas.
    """
    uf = str(uf or "").strip().upper()
    if len(uf) != 2:
        raise ValueError(f"UF inválida: {uf!r}.")
    crt = crt_do_regime(regime)
    tipo = "simples" if crt in REGIMES_SIMPLES else "normal"

    criadas = 0
    for nome, regras in VINCULOS:
        icms_cst, cfop_nfe, cfop_nfce = regras[tipo]
        vinculo = VinculoFiscal.objects.filter(nome__iexact=nome).first() or VinculoFiscal.objects.create(nome=nome)

        nfe, nova = ConfiguracaoFiscal.objects.get_or_create(
            vinculo=vinculo, documento="nfe", uf_origem=uf, uf_destino=TODAS_UFS, regime=crt,
        )
        if nova:
            criadas += 1
            TributacaoFiscal.objects.create(configuracao=nfe, operacao="entrada", **ENTRADA)
            TributacaoFiscal.objects.create(configuracao=nfe, operacao="saida", cfop=cfop_nfe, icms_cst=icms_cst,
                                            ipi_cst=IPI_SAIDA, **SAIDA)

        nfce, nova = ConfiguracaoFiscal.objects.get_or_create(
            vinculo=vinculo, documento="nfce", uf_origem=uf, uf_destino=uf, regime=crt,
        )
        if nova:
            criadas += 1
            TributacaoFiscal.objects.create(configuracao=nfce, operacao="saida", cfop=cfop_nfce, icms_cst=icms_cst, **SAIDA)
    return criadas
