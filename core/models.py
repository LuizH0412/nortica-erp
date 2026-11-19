from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Nivel(models.TextChoices):
        MASTER = "master", "Master"
        ADMINISTRADOR = "administrador", "Administrador"
        COMUM = "comum", "Usuário"

    nivel = models.CharField(max_length=20, choices=Nivel.choices, default=Nivel.COMUM)

    @property
    def eh_master(self):
        return self.nivel == self.Nivel.MASTER

    @property
    def eh_administrador(self):
        return self.nivel in (self.Nivel.MASTER, self.Nivel.ADMINISTRADOR)