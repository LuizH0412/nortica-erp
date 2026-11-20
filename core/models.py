from django.contrib.auth.models import AbstractUser
from django.db import models
from .validators import validar_cnpj, validar_documento


class Usuario(AbstractUser):
    class Nivel(models.TextChoices):
        MASTER = "master", "Master"
        ADMINISTRADOR = "administrador", "Administrador"
        COMUM = "comum", "Usuário"

    nivel = models.CharField(max_length=20, choices=Nivel.choices, default=Nivel.COMUM)
    empresas_permitidas = models.ManyToManyField(
        "Empresa", blank=True, related_name="usuarios",
        verbose_name="Empresas que pode acessar",
    )

    @property
    def eh_master(self):
        return self.nivel == self.Nivel.MASTER

    @property
    def eh_administrador(self):
        return self.nivel in (self.Nivel.MASTER, self.Nivel.ADMINISTRADOR)

UFS = [(u, u) for u in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()]


class Empresa(models.Model):
    class Regime(models.TextChoices):
        MEI = "mei", "MEI"
        SIMPLES = "simples", "Simples Nacional"
        PRESUMIDO = "presumido", "Lucro Presumido"
        REAL = "real", "Lucro Real"

    class NomeDocumento(models.TextChoices):
        FANTASIA = "fantasia", "Nome fantasia"
        RAZAO = "razao", "Razão social"

    unidade = models.CharField(
        "Unidade", max_length=60, unique=True,
        error_messages={"unique": "Já existe uma empresa com esta unidade."},
        help_text='Nome desta unidade. Ex.: "Matriz", "Filial", "Filial 3".',
    )

    # Dados cadastrais
    razao_social = models.CharField("Razão social", max_length=150)
    nome_fantasia = models.CharField("Nome fantasia", max_length=150, blank=True)
    documento = models.CharField(
        "CPF/CNPJ", max_length=14, unique=True, validators=[validar_documento],
        error_messages={"unique": "Já existe uma empresa com este CPF/CNPJ."},
    )
    inscricao_estadual = models.CharField("Inscrição estadual", max_length=20, blank=True)
    inscricao_municipal = models.CharField("Inscrição municipal", max_length=20, blank=True)

    # Endereço
    cep = models.CharField("CEP", max_length=8, blank=True)
    logradouro = models.CharField("Endereço", max_length=150, blank=True)
    numero = models.CharField("Número", max_length=10, blank=True)
    complemento = models.CharField("Complemento", max_length=80, blank=True)
    bairro = models.CharField("Bairro", max_length=80, blank=True)
    municipio = models.ForeignKey(
        "localidades.Municipio", verbose_name="Cidade", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    # Contatos
    telefone = models.CharField("Telefone", max_length=11, blank=True)
    email = models.EmailField("E-mail", blank=True)

    # Documentos
    nome_nos_documentos = models.CharField(
        "Nome nos documentos", max_length=10, choices=NomeDocumento.choices,
        default=NomeDocumento.FANTASIA,
        help_text="Nome que sai nos impressos. Sem nome fantasia, usa a razão social.",
    )

    # Fiscal
    regime_tributario = models.CharField(
        "Regime tributário", max_length=15, choices=Regime.choices, blank=True
    )

    ativa = models.BooleanField("Empresa ativa", default=True)

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["unidade"]

    @property
    def nome_exibicao(self):
        return self.nome_fantasia or self.razao_social

    @property
    def nome_para_documentos(self):
        if self.nome_nos_documentos == self.NomeDocumento.FANTASIA and self.nome_fantasia:
            return self.nome_fantasia
        return self.razao_social

    @property
    def eh_pessoa_fisica(self):
        return len(self.documento) == 11

    @property
    def codigo_municipio_ibge(self):
        return self.municipio_id

    def __str__(self):
        return f"{self.nome_exibicao} · {self.unidade}"

    def vinculos_que_impedem_exclusao(self):
        """Nomes do que já está ligado a esta empresa. Vazio = pode excluir."""
        ignorar = {"usuarios"}  # o acesso dos usuários some junto com a empresa
        encontrados = []
        for rel in self._meta.related_objects:
            nome = rel.get_accessor_name()
            if nome in ignorar:
                continue
            if rel.many_to_many:
                existe = getattr(self, nome).exists()
            else:
                existe = rel.related_model._base_manager.filter(
                    **{rel.field.name: self}
                ).exists()
            if existe:
                encontrados.append(str(rel.related_model._meta.verbose_name_plural))
        return encontrados