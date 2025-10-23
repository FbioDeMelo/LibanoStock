from .models import Notificacao
from django.utils import timezone

def checar_estoque(produto):
    """
    Verifica se o estoque do produto está abaixo do limite e cria notificação.
    """
    # garante que quantidade seja inteiro
    quantidade = int(produto.quantidade)

    if quantidade <= 2:  # limite de alerta
        Notificacao.objects.get_or_create(
            produto=produto,
            mensagem=f"Estoque baixo: {produto.nome} ({quantidade} unidades)",
            vista=False,
            criado_em=timezone.now()
        )
