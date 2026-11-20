from django.apps import AppConfig


class ClientesConfig(AppConfig):
    name = "clientes"
    verbose_name = "Clientes"

    def ready(self):
        from core.cadastros_simples import registrar

        from .forms import AreaForm, TagForm, TipoClienteForm
        from .models import Area, Tag, TipoCliente

        # Qualquer usuário que cadastra clientes pode gerir estes (não só quem acessa as configurações)
        uso = ("cliente", "clientes")
        registrar("tipo_cliente", TipoCliente, TipoClienteForm, relacao="clientes", uso=uso)
        registrar("area", Area, AreaForm, relacao="clientes", uso=uso)
        registrar("tag", Tag, TagForm, relacao="clientes", uso=uso)
