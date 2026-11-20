import re
import unicodedata

from django.db import models


def normalizar(texto):
    """Minúsculas, sem acento e sem espaços sobrando. Usado nas buscas."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


class Municipio(models.Model):
    codigo_ibge = models.CharField(max_length=7, primary_key=True)
    nome = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    nome_busca = models.CharField(max_length=100, editable=False)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "municípios"
        indexes = [models.Index(fields=["uf", "nome_busca"]), models.Index(fields=["nome_busca"])]

    def save(self, *args, **kwargs):
        self.nome_busca = normalizar(self.nome)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome}/{self.uf}"