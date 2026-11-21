import json
import re
import urllib.request
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from fiscal.models import Ncm
from localidades.models import normalizar

URL = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json?perfil=PUBLICO"


def limpar_descricao(texto):
    """Tira os traços de nível da tabela ("-- De algodão" -> "De algodão") e o ponto final."""
    texto = re.sub(r"<[^>]+>", "", texto or "")
    texto = re.sub(r"^[\s\-–]+", "", texto)
    return " ".join(texto.split()).rstrip(".:;")[:600]


class Command(BaseCommand):
    help = "Carrega (ou atualiza) a tabela de NCM vigente do Siscomex (Portal Único)."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", help="Usa um JSON já baixado do Siscomex em vez de baixar.")

    def handle(self, *args, arquivo=None, **opcoes):
        try:
            if arquivo:
                bruto = Path(arquivo).read_bytes()
            else:
                requisicao = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Nexum)"})
                with urllib.request.urlopen(requisicao, timeout=120) as resposta:
                    bruto = resposta.read()
            dados = json.loads(bruto.decode("utf-8-sig"))
        except Exception as erro:
            raise CommandError(f"Não foi possível ler a tabela de NCM: {erro}")

        hoje = date.today()
        ncms = {}
        for item in dados.get("Nomenclaturas", []):
            codigo = re.sub(r"\D", "", item.get("Codigo", ""))
            if len(codigo) != 8:
                continue  # capítulos, posições e subposições: só o código completo vai para o cadastro
            fim = item.get("Data_Fim") or "31/12/9999"
            try:
                if datetime.strptime(fim, "%d/%m/%Y").date() < hoje:
                    continue  # NCM extinta
            except ValueError:
                pass
            descricao = limpar_descricao(item.get("Descricao"))
            ncms[codigo] = Ncm(codigo=codigo, descricao=descricao, descricao_busca=normalizar(descricao))

        if not ncms:
            raise CommandError("A tabela veio vazia. Nada foi alterado.")
        Ncm.objects.bulk_create(
            ncms.values(), update_conflicts=True, unique_fields=["codigo"], update_fields=["descricao", "descricao_busca"],
        )
        Ncm.objects.exclude(codigo__in=ncms.keys()).delete()  # o que saiu da tabela vigente
        self.stdout.write(self.style.SUCCESS(f"{len(ncms)} NCMs carregadas ({dados.get('Ato', '')})."))
