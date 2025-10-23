from django.contrib.auth.models import Group
from .models import Produto

def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    is_admin = request.user.is_superuser or request.user.groups.filter(name__iexact='ADMIN').exists()
    pertence_geral = request.user.groups.filter(name__iexact='Geral').exists()

    user_groups = request.user.groups.all()
    setores = Group.objects.all() if is_admin else user_groups

    hub_info = [
        {
            'nome_setor': s.name,
            'total_produtos': Produto.objects.filter(setor_responsavel=s).count()
        }
        for s in setores
    ]

    return {
        'is_admin': is_admin,
        'pertence_geral': pertence_geral,
        'hub_info': hub_info,
    }
