"""
Tabelas oficiais usadas na parte fiscal (compartilhadas por todas as instâncias, como os municípios).

- NCM (Nomenclatura Comum do Mercosul): `manage.py importar_ncm` (Siscomex).
- CEST (Convênio ICMS 142/2018) e as NCMs de cada um: `manage.py importar_cest`.
- Carga tributária aproximada do IBPT ("De olho no imposto"): consultada por NCM e UF quando precisa
  e guardada aqui (veja fiscal/ibpt.py).
"""
from django.db import models

from localidades.models import normalizar


class Ncm(models.Model):
    codigo = models.CharField("Código", max_length=8, primary_key=True)  # só números (ex.: 61032200)
    descricao = models.CharField("Descrição", max_length=600)
    descricao_busca = models.CharField(max_length=600, editable=False)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "NCM"
        verbose_name_plural = "NCMs"

    def save(self, *args, **kwargs):
        self.descricao_busca = normalizar(self.descricao)
        super().save(*args, **kwargs)

    @property
    def codigo_formatado(self):
        c = self.codigo
        return f"{c[:4]}.{c[4:6]}.{c[6:]}"

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class Cest(models.Model):
    """Código Especificador da Substituição Tributária (Convênio ICMS 142/2018, itens vigentes)."""

    codigo = models.CharField("Código", max_length=7, primary_key=True)  # só números (ex.: 0300800)
    descricao = models.TextField("Descrição")
    segmento = models.CharField("Segmento", max_length=150, blank=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "CEST"
        verbose_name_plural = "CESTs"

    @property
    def codigo_formatado(self):
        c = self.codigo
        return f"{c[:2]}.{c[2:5]}.{c[5:]}"

    def __str__(self):
        descricao = self.descricao if len(self.descricao) <= 110 else self.descricao[:107].rstrip() + "..."
        return f"{self.codigo_formatado} - {descricao}"


class CestNcm(models.Model):
    """
    NCMs de cada CEST, como estão na norma. Pode ser um código parcial ("3917", "2202.99"),
    que vale para todas as NCMs que começam com ele.
    """

    cest = models.ForeignKey(Cest, on_delete=models.CASCADE, related_name="ncms")
    ncm = models.CharField("NCM/SH", max_length=8, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cest", "ncm"], name="cest_ncm_unico")]

    def __str__(self):
        return f"{self.cest_id} ← {self.ncm}"


class AliquotaIbpt(models.Model):
    """Carga tributária aproximada (Lei 12.741/2012) de uma NCM numa UF, conforme a tabela do IBPT."""

    ncm = models.CharField(max_length=8)
    uf = models.CharField(max_length=2)
    nacional_federal = models.DecimalField(max_digits=7, decimal_places=2)
    importados_federal = models.DecimalField(max_digits=7, decimal_places=2)
    estadual = models.DecimalField(max_digits=7, decimal_places=2)
    municipal = models.DecimalField(max_digits=7, decimal_places=2)
    versao = models.CharField(max_length=20, blank=True)
    vigencia_inicio = models.DateField(null=True, blank=True)
    fonte = models.CharField(max_length=80, blank=True)
    consultado_em = models.DateTimeField()

    class Meta:
        verbose_name = "alíquota IBPT"
        verbose_name_plural = "alíquotas IBPT"
        constraints = [models.UniqueConstraint(fields=["ncm", "uf"], name="ibpt_ncm_uf_unico")]

    def __str__(self):
        return f"{self.ncm}/{self.uf} ({self.versao})"


class Cfop(models.Model):
    """CFOP – Código Fiscal de Operações e Prestações (tabela do Portal da NF-e)."""

    codigo = models.CharField("Código", max_length=4, primary_key=True)  # só números (ex.: 5102)
    descricao = models.CharField("Descrição", max_length=400)
    usa_nfe = models.BooleanField("Pode ser usado em NF-e", default=True)
    devolucao = models.BooleanField("Devolução", default=False)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "CFOP"
        verbose_name_plural = "CFOPs"

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class CstIbsCbs(models.Model):
    """CST do IBS/CBS (reforma tributária), da calculadora oficial da Receita Federal."""

    codigo = models.CharField("Código", max_length=3, primary_key=True)
    descricao = models.CharField("Descrição", max_length=200)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "CST do IBS/CBS"
        verbose_name_plural = "CSTs do IBS/CBS"

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class ClassTrib(models.Model):
    """cClassTrib – classificação tributária do IBS/CBS (cada uma pertence a um CST)."""

    codigo = models.CharField("Código", max_length=6, primary_key=True)
    cst = models.ForeignKey(CstIbsCbs, on_delete=models.CASCADE, related_name="classificacoes")
    descricao = models.TextField("Descrição")

    class Meta:
        ordering = ["codigo"]
        verbose_name = "classificação tributária (cClassTrib)"
        verbose_name_plural = "classificações tributárias (cClassTrib)"

    def __str__(self):
        descricao = self.descricao if len(self.descricao) <= 110 else self.descricao[:107].rstrip() + "..."
        return f"{self.codigo} - {descricao}"
