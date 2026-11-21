import json
import urllib.request
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fiscal.models import ClassTrib, CstIbsCbs

# Dados abertos da calculadora oficial da reforma tributária (Receita Federal)
URL = ("https://piloto-cbs.tributos.gov.br/servico/calculadora-consumo/api/calculadora/dados-abertos/"
       "situacoes-tributarias/cbs-ibs?data={data}")


class Command(BaseCommand):
    help = "Carrega (ou atualiza) os CSTs do IBS/CBS e as classificações tributárias (cClassTrib) vigentes."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", help="Usa um JSON já baixado da calculadora em vez de baixar.")

    def handle(self, *args, arquivo=None, **opcoes):
        try:
            if arquivo:
                dados = json.loads(Path(arquivo).read_text(encoding="utf-8-sig"))
            else:
                requisicao = urllib.request.Request(URL.format(data=date.today().isoformat()),
                                                    headers={"User-Agent": "Nexum/1.0"})
                with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
        except Exception as erro:
            raise CommandError(f"Não foi possível ler a tabela do IBS/CBS: {erro}")

        csts, classes = [], []
        for item in dados:
            codigo = str(item.get("codigo", "")).strip()
            if len(codigo) != 3:
                continue
            csts.append(CstIbsCbs(codigo=codigo, descricao=" ".join(str(item.get("descricao", "")).split())[:200]))
            for c in item.get("classificacoesTributarias") or []:
                cc = str(c.get("codigo", "")).strip()
                if len(cc) == 6:
                    classes.append(ClassTrib(codigo=cc, cst_id=codigo, descricao=" ".join(str(c.get("descricao", "")).split())))
        if not csts:
            raise CommandError("A tabela veio vazia. Nada foi alterado.")
        with transaction.atomic():
            CstIbsCbs.objects.bulk_create(csts, update_conflicts=True, unique_fields=["codigo"], update_fields=["descricao"])
            ClassTrib.objects.bulk_create(
                classes, update_conflicts=True, unique_fields=["codigo"], update_fields=["cst", "descricao"],
            )
            ClassTrib.objects.exclude(codigo__in=[c.codigo for c in classes]).delete()
        self.stdout.write(self.style.SUCCESS(f"{len(csts)} CSTs e {len(classes)} classificações (cClassTrib) carregados."))
