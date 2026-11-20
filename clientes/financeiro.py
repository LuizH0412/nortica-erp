"""
Resumo financeiro do cliente (aba "Financeiro").

Hoje só o limite de crédito e o bloqueio existem de verdade. Valores em aberto, vencidos,
parcelas e compras vêm dos módulos de vendas e contas a receber, que ainda não existem:
quando existirem, é só preencher em resumo_financeiro() — a tela já está pronta para mostrar.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

ZERO = Decimal("0")


@dataclass
class ResumoFinanceiro:
    cliente: object
    limite: Decimal = ZERO
    em_aberto: Decimal = ZERO
    vencido: Decimal = ZERO
    parcelas_vencidas: int = 0
    saldo_credito_loja: Decimal = ZERO
    ultima_compra: date | None = None
    parcelas_em_aberto: list = field(default_factory=list)
    ultimas_compras: list = field(default_factory=list)
    # Enquanto vendas/contas a receber não existem, a tela avisa que os valores ainda não são calculados
    modulos_disponiveis: bool = False

    @property
    def disponivel(self):
        return max(self.limite - self.em_aberto, ZERO)

    @property
    def utilizacao(self):
        """Percentual do limite em uso (0 a 100)."""
        if self.limite <= 0:
            return 0
        return int(min(self.em_aberto / self.limite * 100, 100))

    @property
    def situacao(self):
        """em_dia | inadimplente | bloqueado"""
        if self.cliente.bloqueado:
            return "bloqueado"
        if self.parcelas_vencidas:
            return "inadimplente"
        return "em_dia"


def saldo_credito(cliente):
    """Crédito do cliente na loja: créditos - débitos."""
    from .models import MovimentoCredito

    totais = cliente.movimentos_credito.aggregate(
        creditos=Sum("valor", filter=Q(tipo=MovimentoCredito.Tipo.CREDITO)),
        debitos=Sum("valor", filter=Q(tipo=MovimentoCredito.Tipo.DEBITO)),
    )
    return (totais["creditos"] or ZERO) - (totais["debitos"] or ZERO)


@dataclass
class Extrato:
    de: date
    ate: date
    movimentos: list
    creditos: Decimal
    debitos: Decimal

    @property
    def saldo(self):
        return self.creditos - self.debitos


def periodo_padrao(hoje=None):
    """Do primeiro ao último dia do mês atual."""
    hoje = hoje or timezone.localdate()
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    return hoje.replace(day=1), hoje.replace(day=ultimo)


def extrato_credito(cliente, de, ate):
    """Movimentações de crédito do período (datas inclusivas)."""
    from .models import MovimentoCredito

    movimentos = list(
        cliente.movimentos_credito.select_related("usuario")
        .filter(criado_em__date__gte=de, criado_em__date__lte=ate)
    )
    creditos = sum((m.valor for m in movimentos if m.tipo == MovimentoCredito.Tipo.CREDITO), ZERO)
    debitos = sum((m.valor for m in movimentos if m.tipo == MovimentoCredito.Tipo.DEBITO), ZERO)
    return Extrato(de=de, ate=ate, movimentos=movimentos, creditos=creditos, debitos=debitos)


def resumo_financeiro(cliente):
    return ResumoFinanceiro(
        cliente=cliente, limite=cliente.limite_credito, saldo_credito_loja=saldo_credito(cliente),
    )
