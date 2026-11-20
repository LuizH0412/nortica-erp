import json
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from localidades.models import Municipio, normalizar

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


class Command(BaseCommand):
    help = "Carrega (ou atualiza) a lista de municípios do IBGE."

    def handle(self, *args, **opcoes):
        try:
            requisicao = urllib.request.Request(URL, headers={"User-Agent": "Nexum/1.0"})
            with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                dados = json.loads(resposta.read().decode("utf-8"))
        except Exception as erro:
            raise CommandError(f"Não foi possível baixar a lista do IBGE: {erro}")

        municipios = []
        for item in dados:
            codigo = str(item["id"])
            uf = UF_POR_CODIGO.get(codigo[:2])
            if not uf:
                continue
            municipios.append(
                Municipio(
                    codigo_ibge=codigo, nome=item["nome"], uf=uf,
                    nome_busca=normalizar(item["nome"]),
                )
            )

        Municipio.objects.bulk_create(
            municipios,
            update_conflicts=True,
            unique_fields=["codigo_ibge"],
            update_fields=["nome", "uf", "nome_busca"],
        )
        self.stdout.write(self.style.SUCCESS(f"{len(municipios)} municípios carregados."))