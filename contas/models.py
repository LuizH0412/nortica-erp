from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UsuarioManager(BaseUserManager):
    """O login é pelo e-mail (sem nome de usuário)."""

    use_in_migrations = True

    def _criar(self, email, password, **campos):
        if not email:
            raise ValueError("Informe o e-mail.")
        usuario = self.model(email=self.normalize_email(email).lower(), **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **campos):
        campos.setdefault("is_staff", False)
        campos.setdefault("is_superuser", False)
        return self._criar(email, password, **campos)

    def create_superuser(self, email, password=None, **campos):
        campos.setdefault("is_staff", True)
        campos.setdefault("is_superuser", True)
        campos.setdefault("master", True)
        return self._criar(email, password, **campos)

    def get_by_natural_key(self, email):
        # No login, maiúsculas e minúsculas não importam
        return self.get(email__iexact=email)


class Usuario(AbstractUser):
    username = None
    email = models.EmailField(
        "E-mail", unique=True,
        error_messages={"unique": "Já existe um usuário com este e-mail."},
    )
    # O master (suporte da Nórtica) entra em todas as empresas com todas as permissões
    master = models.BooleanField("Master", default=False, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def nome_exibicao(self):
        return self.get_full_name() or self.email

    @property
    def eh_master(self):
        return self.master

    def perfil_na(self, empresa):
        """Perfil de acesso desta pessoa na empresa (None se não tiver acesso)."""
        if empresa is None:
            return None
        acesso = self.acessos.select_related("perfil").filter(empresa=empresa).first()
        return acesso.perfil if acesso else None


class Perfil(models.Model):
    """Conjunto de permissões que se dá a um usuário dentro de uma empresa."""

    nome = models.CharField(
        "Nome", max_length=60, unique=True,
        error_messages={"unique": "Já existe um perfil com este nome."},
    )
    pode_configurar = models.BooleanField(
        "Acessa as configurações", default=False,
        help_text="Empresas, funcionários, usuários e perfis de acesso.",
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "perfil de acesso"
        verbose_name_plural = "perfis de acesso"

    def __str__(self):
        return self.nome


class AcessoEmpresa(models.Model):
    """Em qual empresa a pessoa entra e com qual perfil. Um perfil por empresa."""

    usuario = models.ForeignKey(
        Usuario, verbose_name="Usuário", on_delete=models.CASCADE, related_name="acessos",
    )
    empresa = models.ForeignKey(
        "empresas.Empresa", verbose_name="Empresa", on_delete=models.CASCADE, related_name="acessos",
    )
    perfil = models.ForeignKey(
        Perfil, verbose_name="Perfil", on_delete=models.PROTECT, related_name="acessos",
    )

    class Meta:
        ordering = ["empresa__unidade"]
        verbose_name = "acesso à empresa"
        verbose_name_plural = "acessos às empresas"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "empresa"], name="um_perfil_por_empresa"),
        ]

    def __str__(self):
        return f"{self.usuario} · {self.perfil} em {self.empresa.unidade}"
