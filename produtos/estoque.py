"""Estoque dos produtos: saldo por empresa e ajustes (Organizar estoque)."""
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import EstoqueProduto, MovimentoEstoque

ZERO = Decimal("0")


def saldo(produto, empresa):
    if empresa is None:
        return ZERO
    registro = EstoqueProduto.objects.filter(produto=produto, empresa=empresa).first()
    return registro.quantidade if registro else ZERO


def estoque_minimo(produto, empresa):
    if empresa is None:
        return ZERO
    registro = EstoqueProduto.objects.filter(produto=produto, empresa=empresa).first()
    return registro.estoque_minimo if registro else ZERO


def com_saldo(queryset, empresa):
    """Anota "saldo" e "minimo" (estoque na empresa informada) em cada produto da consulta."""
    registros = EstoqueProduto.objects.filter(produto=OuterRef("pk"), empresa=empresa)
    decimal = DecimalField(max_digits=14, decimal_places=3)
    return queryset.annotate(
        saldo=Coalesce(Subquery(registros.values("quantidade")[:1]), Value(ZERO), output_field=decimal),
        minimo=Coalesce(Subquery(registros.values("estoque_minimo")[:1]), Value(ZERO), output_field=decimal),
    )


@transaction.atomic
def ajustar(produto, empresa, novo_saldo, usuario=None, motivo=""):
    """Organizar estoque: deixa o saldo igual ao contado e registra a diferença."""
    registro, _ = EstoqueProduto.objects.select_for_update().get_or_create(produto=produto, empresa=empresa)
    anterior = registro.quantidade
    registro.quantidade = novo_saldo
    registro.save(update_fields=["quantidade", "atualizado_em"])
    return MovimentoEstoque.objects.create(
        produto=produto, empresa=empresa, tipo=MovimentoEstoque.Tipo.AJUSTE,
        quantidade=novo_saldo - anterior, saldo_anterior=anterior, saldo_novo=novo_saldo,
        motivo=motivo, usuario=usuario,
    )


@transaction.atomic
def movimentar(produto, empresa, quantidade, tipo, usuario=None, motivo="", data=None):
    """Ajuste rápido: soma (entrada, quantidade positiva) ou subtrai (saída, negativa) do saldo."""
    registro, _ = EstoqueProduto.objects.select_for_update().get_or_create(produto=produto, empresa=empresa)
    anterior = registro.quantidade
    registro.quantidade = anterior + quantidade
    registro.save(update_fields=["quantidade", "atualizado_em"])
    campos = {"data_operacao": data} if data else {}
    return MovimentoEstoque.objects.create(
        produto=produto, empresa=empresa, tipo=tipo, quantidade=quantidade,
        saldo_anterior=anterior, saldo_novo=registro.quantidade, motivo=motivo, usuario=usuario, **campos,
    )


def definir_minimo(produto, empresa, valor):
    registro, _ = EstoqueProduto.objects.get_or_create(produto=produto, empresa=empresa)
    registro.estoque_minimo = valor
    registro.save(update_fields=["estoque_minimo", "atualizado_em"])
    return registro


# ---------- Organizar estoque: confere tudo o que mexe no estoque e corrige o saldo ----------

# Partes do sistema que movimentam estoque. Cada uma entra aqui quando o módulo existir:
# a função recebe o produto e devolve os movimentos dela (ou None se o módulo ainda não existe).
ETAPAS = [
    ("vendas", "Vendas"),
    ("compras", "Compras"),
    ("ajustes", "Ajustes"),
    ("transferencias", "Transferências"),
    ("requisicoes", "Requisições"),
    ("devolucoes", "Devoluções"),
    ("composicao", "Composição"),
    ("nfe", "NF-e"),
]
TIPOS_DOS_AJUSTES = [MovimentoEstoque.Tipo.AJUSTE, MovimentoEstoque.Tipo.ENTRADA, MovimentoEstoque.Tipo.SAIDA]


def _movimentos_da_etapa(produto, etapa):
    if etapa == "ajustes":
        return produto.movimentos_estoque.filter(tipo__in=TIPOS_DOS_AJUSTES).select_related("empresa")
    return None  # módulo ainda não existe


@transaction.atomic
def organizar(produto):
    """
    Recalcula o saldo do produto em cada empresa a partir das movimentações de todas as etapas,
    corrige o saldo gravado quando estiver diferente e aponta movimentações incoerentes.
    """
    calculado = {}          # empresa_id -> saldo calculado
    empresas = {}           # empresa_id -> empresa
    etapas = []
    incoerentes = []

    for chave, nome in ETAPAS:
        movimentos = _movimentos_da_etapa(produto, chave)
        if movimentos is None:
            etapas.append({"chave": chave, "nome": nome, "status": "inativo", "detalhe": "Módulo ainda não ativo."})
            continue
        total = 0
        for m in movimentos:
            total += 1
            empresas[m.empresa_id] = m.empresa
            calculado[m.empresa_id] = calculado.get(m.empresa_id, ZERO) + m.quantidade
            if m.saldo_anterior + m.quantidade != m.saldo_novo:
                incoerentes.append(m)
        detalhe = f"{total} movimentação(ões) conferida(s)." if total else "Nenhuma movimentação."
        etapas.append({"chave": chave, "nome": nome, "status": "ok", "detalhe": detalhe})

    # Saldos gravados (inclusive de empresas sem movimentação, que devem ficar em zero)
    registros = {r.empresa_id: r for r in EstoqueProduto.objects.select_for_update().filter(produto=produto)
                 .select_related("empresa")}
    for empresa_id, registro in registros.items():
        empresas.setdefault(empresa_id, registro.empresa)

    correcoes, conferidas = [], []
    for empresa_id, empresa in empresas.items():
        esperado = calculado.get(empresa_id, ZERO)
        registro = registros.get(empresa_id)
        gravado = registro.quantidade if registro else ZERO
        if gravado != esperado:
            if registro is None:
                registro = EstoqueProduto(produto=produto, empresa=empresa)
            registro.quantidade = esperado
            registro.save()
            correcoes.append({"empresa": empresa.unidade, "antes": gravado, "depois": esperado})
        else:
            conferidas.append({"empresa": empresa.unidade, "saldo": esperado})

    return {
        "etapas": etapas,
        "correcoes": correcoes,
        "conferidas": conferidas,
        "incoerentes": [
            {"data": m.criado_em, "tipo": m.get_tipo_display(), "empresa": m.empresa.unidade} for m in incoerentes
        ],
    }
