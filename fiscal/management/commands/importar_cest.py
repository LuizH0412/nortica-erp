import csv
import io
import re
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fiscal.models import Cest, CestNcm

# Convênio ICMS 142/2018 (itens vigentes) em dados abertos, extraído da página do Confaz
# (https://github.com/thiagogardev/icms-st-dados, licença MIT)
URL = "https://raw.githubusercontent.com/thiagogardev/icms-st-dados/HEAD/dados/conv142/itens_vigentes.csv"


class Command(BaseCommand):
    help = "Carrega (ou atualiza) a tabela de CEST vigente (Convênio ICMS 142/2018) e as NCMs de cada CEST."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", help="Usa um itens_vigentes.csv já baixado em vez de baixar.")

    def handle(self, *args, arquivo=None, **opcoes):
        try:
            if arquivo:
                texto = Path(arquivo).read_text(encoding="utf-8-sig")
            else:
                requisicao = urllib.request.Request(URL, headers={"User-Agent": "Nexum/1.0"})
                with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                    texto = resposta.read().decode("utf-8-sig")
            linhas = list(csv.DictReader(io.StringIO(texto)))
        except Exception as erro:
            raise CommandError(f"Não foi possível ler a tabela de CEST: {erro}")

        cests, ligacoes = {}, set()
        for linha in linhas:
            codigo = re.sub(r"\D", "", linha.get("cest", ""))
            if len(codigo) != 7:
                continue
            cests[codigo] = Cest(
                codigo=codigo, descricao=" ".join((linha.get("descricao") or "").split()),
                segmento=(linha.get("segmento") or "")[:150],
            )
            for ncm in (linha.get("ncms") or "").split(";"):
                ncm = re.sub(r"\D", "", ncm)
                if 2 <= len(ncm) <= 8:
                    ligacoes.add((codigo, ncm))
        if not cests:
            raise CommandError("A tabela veio vazia. Nada foi alterado.")

        with transaction.atomic():
            CestNcm.objects.all().delete()
            Cest.objects.exclude(codigo__in=cests.keys()).delete()
            Cest.objects.bulk_create(
                cests.values(), update_conflicts=True, unique_fields=["codigo"], update_fields=["descricao", "segmento"],
            )
            CestNcm.objects.bulk_create(CestNcm(cest_id=c, ncm=n) for c, n in sorted(ligacoes))
        self.stdout.write(self.style.SUCCESS(f"{len(cests)} CESTs e {len(ligacoes)} ligações com NCM carregadas."))
