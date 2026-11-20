from django.apps import AppConfig


class FuncionariosConfig(AppConfig):
    name = "funcionarios"
    verbose_name = "Funcionários"

    def ready(self):
        from core.cadastros_simples import registrar

        from .forms import FuncaoForm, SetorForm
        from .models import Funcao, Setor

        uso = ("funcionário", "funcionários")
        registrar("funcao", Funcao, FuncaoForm, relacao="funcionarios", uso=uso, so_configuracao=True)
        registrar("setor", Setor, SetorForm, relacao="funcionarios", uso=uso, so_configuracao=True)
