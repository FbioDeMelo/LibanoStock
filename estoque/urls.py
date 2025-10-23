from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy
urlpatterns = [
    # Login
    path('', auth_views.LoginView.as_view(
        template_name='estoque/login.html'
    ), name='login'),

    path('logout/', views.logout_view, name='logout'),


    # Hub de setores
    path('estoque/', views.index, name='index'),

    # Adicionar usuários/produtos
    path('adicionar_usuario/', views.adicionar_usuario, name='adicionar_usuario'),
    path('adicionar_produto/', views.adicionar_produto, name='adicionar_produto'),

    # Produtos detalhados por setor
    path('produtos/<str:setor>/', views.produtos_setor, name='produtos_setor'),

    # Usuários
    path('gerenciar_usuarios/', views.gerenciar_usuarios, name='gerenciar_usuarios'),

    # Estoque / movimentações
    path('retirar_item/<int:produto_id>/', views.retirar_item, name='retirar_item'),
    path('movimentacoes/', views.movimentacoes, name='movimentacoes'),
    path('movimentacoes/exportar/', views.exportar_movimentacoes, name='exportar_movimentacoes'),

    # Gráficos
    path('graficos/', views.dashboard_graficos, name='dashboard_graficos'),
    path('exportar_graficos/', views.exportar_graficos_csv, name='exportar_graficos_csv'),

    # Protocolo
    path('protocolo/', views.protocolo_create, name='protocolo_create'),

    # Colaboradores
    path("colaboradores/", views.lista_colaboradores, name="lista_colaboradores"),
    path("colaborador/<int:colaborador_id>/exportar/", views.exportar_colaborador, name="exportar_colaborador"),
    path("colaborador/adicionar/", views.colaborador_create, name="colaborador_create"),

    # Busca
    path("buscar_colaboradores/", views.buscar_colaboradores, name="buscar_colaboradores"),
    path("buscar_produtos/", views.buscar_produtos, name="buscar_produtos"),
    path('verifica_patrimonio/', views.verifica_patrimonio, name='verifica_patrimonio'),
    path("patrimonios/", views.lista_patrimonios, name="lista_patrimonios"),
    path('notificacoes/', views.notificacoes, name='notificacoes'),
    path('marcar_vista/', views.marcar_vista, name='marcar_vista'),
    path('atualizar-avatar/', views.atualizar_avatar, name='atualizar_avatar'),
    path('solicitar-compra/', views.solicitar_compra, name='solicitar_compra'),
path('gerenciar-solicitacoes/', views.gerenciar_solicitacoes, name='gerenciar_solicitacoes'),
    path('produto/<int:produto_id>/', views.produto_qr_view, name='produto_qr_view'),

]
from estoque import views  # importe a view de erro do seu app

handler404 = 'estoque.views.pagina_nao_encontrada'
# Para servir arquivos estáticos em modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
