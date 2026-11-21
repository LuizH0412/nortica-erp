import csv
import io
import re
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fiscal.models import Cfop

# Tabela de CFOP do Portal da NF-e (código, descrição resumida e indicadores), versionada em
# https://github.com/thiagovalim/sis-referencias
URL = "https://raw.githubusercontent.com/thiagovalim/sis-referencias/HEAD/dados/cfop.csv"


class Command(BaseCommand):
    help = "Carrega (ou atualiza) a tabela de CFOP."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", help="Usa um cfop.csv já baixado em vez de baixar.")

    def handle(self, *args, arquivo=None, **opcoes):
        try:
            if arquivo:
                texto = Path(arquivo).read_text(encoding="utf-8-sig")
            else:
                requisicao = urllib.request.Request(URL, headers={"User-Agent": "Nexum/1.0"})
                with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                    texto = resposta.read().decode("utf-8-sig")
            linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))[1:]
        except Exception as erro:
            raise CommandError(f"Não foi possível ler a tabela de CFOP: {erro}")

        cfops = {}
        for linha in linhas:
            if len(linha) < 2:
                continue
            codigo = re.sub(r"\D", "", linha[0])
            if len(codigo) != 4:
                continue
            cfops[codigo] = Cfop(
                codigo=codigo, descricao=" ".join(linha[1].split())[:400],
                usa_nfe=(linha[2].strip() != "0") if len(linha) > 2 else True,
                devolucao=(linha[5].strip() == "1") if len(linha) > 5 else False,
            )
        if not cfops:
            raise CommandError("A tabela veio vazia. Nada foi alterado.")
        with transaction.atomic():
            Cfop.objects.bulk_create(
                cfops.values(), update_conflicts=True, unique_fields=["codigo"],
                update_fields=["descricao", "usa_nfe", "devolucao"],
            )
        self.stdout.write(self.style.SUCCESS(f"{len(cfops)} CFOPs carregados."))
