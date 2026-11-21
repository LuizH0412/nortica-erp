"""
Tabelas fiscais pequenas e estáveis (definidas na legislação), usadas nos vínculos fiscais.
As grandes ou que mudam com frequência (NCM, CEST, CFOP, cClassTrib) ficam no banco (fiscal.models).
"""

DOCUMENTOS = [("nfe", "NF-e"), ("nfce", "NFC-e")]

# CRT – Código de Regime Tributário (NF-e)
REGIMES = [
    ("1", "Simples Nacional"),
    ("2", "Simples Nacional – excesso de sublimite"),
    ("3", "Regime Normal"),
    ("4", "MEI (Simei)"),
]
REGIMES_SIMPLES = {"1", "4"}  # usam CSOSN no ICMS; os outros usam CST

UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
TODAS_UFS = "**"  # UF de destino "todas"

OPERACOES = [("entrada", "Entrada"), ("saida", "Saída")]

# SPED Fiscal, registro 0200, campo TIPO_ITEM
TIPOS_ITEM = [
    ("00", "00 - Mercadoria para revenda"),
    ("01", "01 - Matéria-prima"),
    ("02", "02 - Embalagem"),
    ("03", "03 - Produto em processo"),
    ("04", "04 - Produto acabado"),
    ("05", "05 - Subproduto"),
    ("06", "06 - Produto intermediário"),
    ("07", "07 - Material de uso e consumo"),
    ("08", "08 - Ativo imobilizado"),
    ("09", "09 - Serviços"),
    ("10", "10 - Outros insumos"),
    ("99", "99 - Outras"),
]

# ICMS – CST (Tabela B do Convênio s/nº de 1970), regime normal
CST_ICMS = [
    ("00", "00 - Tributada integralmente"),
    ("02", "02 - Tributação monofásica própria sobre combustíveis"),
    ("10", "10 - Tributada e com cobrança do ICMS por substituição tributária"),
    ("15", "15 - Tributação monofásica própria e com responsabilidade pela retenção sobre combustíveis"),
    ("20", "20 - Com redução de base de cálculo"),
    ("30", "30 - Isenta ou não tributada e com cobrança do ICMS por substituição tributária"),
    ("40", "40 - Isenta"),
    ("41", "41 - Não tributada"),
    ("50", "50 - Suspensão"),
    ("51", "51 - Diferimento"),
    ("53", "53 - Tributação monofásica sobre combustíveis com recolhimento diferido"),
    ("60", "60 - ICMS cobrado anteriormente por substituição tributária"),
    ("61", "61 - Tributação monofásica sobre combustíveis cobrada anteriormente"),
    ("70", "70 - Com redução de base de cálculo e cobrança do ICMS por substituição tributária"),
    ("90", "90 - Outras"),
]

# ICMS – CSOSN (Simples Nacional)
CSOSN = [
    ("101", "101 - Tributada pelo Simples Nacional com permissão de crédito"),
    ("102", "102 - Tributada pelo Simples Nacional sem permissão de crédito"),
    ("103", "103 - Isenção do ICMS no Simples Nacional para faixa de receita bruta"),
    ("201", "201 - Tributada pelo Simples Nacional com permissão de crédito e com cobrança do ICMS por ST"),
    ("202", "202 - Tributada pelo Simples Nacional sem permissão de crédito e com cobrança do ICMS por ST"),
    ("203", "203 - Isenção do ICMS no Simples Nacional para faixa de receita bruta e com cobrança do ICMS por ST"),
    ("300", "300 - Imune"),
    ("400", "400 - Não tributada pelo Simples Nacional"),
    ("500", "500 - ICMS cobrado anteriormente por substituição tributária ou por antecipação"),
    ("900", "900 - Outros"),
]

# PIS e COFINS – CST (saída: 01 a 49 e 99; entrada: 50 a 99)
_CREDITO = {
    "0": "Vinculada Exclusivamente a Receita Tributada no Mercado Interno",
    "1": "Vinculada Exclusivamente a Receita Não Tributada no Mercado Interno",
    "2": "Vinculada Exclusivamente a Receita de Exportação",
    "3": "Vinculada a Receitas Tributadas e Não-Tributadas no Mercado Interno",
    "4": "Vinculada a Receitas Tributadas no Mercado Interno e de Exportação",
    "5": "Vinculada a Receitas Não-Tributadas no Mercado Interno e de Exportação",
    "6": "Vinculada a Receitas Tributadas e Não-Tributadas no Mercado Interno, e de Exportação",
}
CST_PIS_COFINS = [
    ("01", "01 - Operação Tributável com Alíquota Básica"),
    ("02", "02 - Operação Tributável com Alíquota Diferenciada"),
    ("03", "03 - Operação Tributável com Alíquota por Unidade de Medida de Produto"),
    ("04", "04 - Operação Tributável Monofásica – Revenda a Alíquota Zero"),
    ("05", "05 - Operação Tributável por Substituição Tributária"),
    ("06", "06 - Operação Tributável a Alíquota Zero"),
    ("07", "07 - Operação Isenta da Contribuição"),
    ("08", "08 - Operação sem Incidência da Contribuição"),
    ("09", "09 - Operação com Suspensão da Contribuição"),
    ("49", "49 - Outras Operações de Saída"),
    *[(f"5{k}", f"5{k} - Operação com Direito a Crédito – {v}") for k, v in _CREDITO.items()],
    *[(f"6{k}", f"6{k} - Operação de Aquisição com Crédito Presumido – {v}") for k, v in _CREDITO.items()],
    ("67", "67 - Crédito Presumido – Outras Operações"),
    ("70", "70 - Operação de Aquisição sem Direito a Crédito"),
    ("71", "71 - Operação de Aquisição com Isenção"),
    ("72", "72 - Operação de Aquisição com Suspensão"),
    ("73", "73 - Operação de Aquisição a Alíquota Zero"),
    ("74", "74 - Operação de Aquisição sem Incidência da Contribuição"),
    ("75", "75 - Operação de Aquisição por Substituição Tributária"),
    ("98", "98 - Outras Operações de Entrada"),
    ("99", "99 - Outras Operações"),
]

# IPI – CST (entrada: 00 a 49; saída: 50 a 99)
CST_IPI = [
    ("00", "00 - Entrada com recuperação de crédito"),
    ("01", "01 - Entrada tributada com alíquota zero"),
    ("02", "02 - Entrada isenta"),
    ("03", "03 - Entrada não-tributada"),
    ("04", "04 - Entrada imune"),
    ("05", "05 - Entrada com suspensão"),
    ("49", "49 - Outras entradas"),
    ("50", "50 - Saída tributada"),
    ("51", "51 - Saída tributada com alíquota zero"),
    ("52", "52 - Saída isenta"),
    ("53", "53 - Saída não-tributada"),
    ("54", "54 - Saída imune"),
    ("55", "55 - Saída com suspensão"),
    ("99", "99 - Outras saídas"),
]


def cst_icms_do_regime(regime):
    """Simples Nacional (e MEI) usam CSOSN; os outros regimes usam CST."""
    return CSOSN if regime in REGIMES_SIMPLES else CST_ICMS


def cst_pis_cofins_da_operacao(operacao):
    if operacao == "saida":
        return [c for c in CST_PIS_COFINS if int(c[0]) < 50 or c[0] == "99"]
    return [c for c in CST_PIS_COFINS if int(c[0]) >= 50]


def cst_ipi_da_operacao(operacao):
    return [c for c in CST_IPI if (int(c[0]) >= 50) == (operacao == "saida")]


def primeiros_digitos_cfop(operacao, uf_origem, uf_destino):
    """Primeiro dígito do CFOP: 1/5 dentro do estado, 2/6 fora; destino "todas" aceita os dois."""
    entrada = operacao == "entrada"
    if uf_destino == TODAS_UFS:
        return ("1", "2") if entrada else ("5", "6")
    if uf_destino == uf_origem:
        return ("1",) if entrada else ("5",)
    return ("2",) if entrada else ("6",)


# ICMS – modalidade de determinação da base de cálculo (modBC)
MODALIDADES_BC = [
    ("0", "0 - Margem de valor agregado (%)"),
    ("1", "1 - Pauta (valor)"),
    ("2", "2 - Preço tabelado máximo (valor)"),
    ("3", "3 - Valor da operação"),
]

# ICMS ST – modalidade de determinação da base de cálculo da substituição tributária (modBCST)
MODALIDADES_BC_ST = [
    ("0", "0 - Preço tabelado ou máximo sugerido"),
    ("1", "1 - Lista negativa (valor)"),
    ("2", "2 - Lista positiva (valor)"),
    ("3", "3 - Lista neutra (valor)"),
    ("4", "4 - Margem de valor agregado (%)"),
    ("5", "5 - Pauta (valor)"),
    ("6", "6 - Valor da operação"),
]

# PIS/COFINS – grupo da natureza da receita (EFD-Contribuições, tabelas 4.3.10 a 4.3.16).
# A natureza (3 dígitos) é o código dentro da tabela; vale para receitas com CST 02 a 09.
GRUPOS_NATUREZA_RECEITA = [
    ("4.3.10", "4.3.10 - Incidência monofásica – alíquotas diferenciadas"),
    ("4.3.11", "4.3.11 - Incidência monofásica – alíquotas por unidade de medida"),
    ("4.3.12", "4.3.12 - Substituição tributária"),
    ("4.3.13", "4.3.13 - Alíquota zero"),
    ("4.3.14", "4.3.14 - Isenção"),
    ("4.3.15", "4.3.15 - Sem incidência"),
    ("4.3.16", "4.3.16 - Suspensão"),
]
