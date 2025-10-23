from django.shortcuts import render, redirect, get_object_or_404
from .models import Produto
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from .forms import UsuarioForm, ProdutoForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Movimentacao
import csv
import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.db.models import Sum
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator

# -------------------- View do Estoque --------------------
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from .models import Produto, Notificacao
import json

@login_required(login_url='login')
def index(request):
    user = request.user
    user_groups = user.groups.all()

    # Verifica se é admin
    is_admin = user.groups.filter(name__iexact='ADMIN').exists() or user.is_superuser
    pertence_geral = user.groups.filter(name__iexact='Geral').exists()

    # 🔹 Se for admin, mostra todos os setores EXCETO o "ADMIN"
    # 🔹 Se não for, mostra apenas os setores do usuário
    if is_admin:
        setores = Group.objects.exclude(name__iexact='ADMIN')
    else:
        setores = user_groups

    # 🔹 Monta o hub de informações por setor
    hub_info = []
    total_produtos = 0
    for setor in setores:
        produtos_setor = Produto.objects.filter(setor_responsavel=setor)
        total = produtos_setor.count()
        total_produtos += total
        hub_info.append({
            'nome_setor': setor.name,
            'total_produtos': total
        })

    # 🔹 Se for admin, adiciona um "setor virtual" ADMIN somando tudo
    if is_admin:
        hub_info.append({
            'nome_setor': 'ADMIN (Total Geral)',
            'total_produtos': total_produtos
        })

    # 🔹 Monta os dados para o gráfico (Chart.js)
    if is_admin:
        chart_labels = [s['nome_setor'] for s in hub_info]
        chart_data = [s['total_produtos'] for s in hub_info]
    else:
        chart_labels = []
        chart_data = []

    # 🔹 Notificações (corrigido: antes essa variável não existia)
    if is_admin:
        notificacoes = Notificacao.objects.filter(vista=False).order_by('-criado_em')
    else:
        notificacoes = Notificacao.objects.filter(
            vista=False,
            setor__in=user_groups
        ).order_by('-criado_em')

    # 🔹 Renderiza o template
    return render(request, 'estoque/index.html', {
        'hub_info': hub_info,
        'is_admin': is_admin,
        'pertence_geral': pertence_geral,
        'total_produtos': total_produtos,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'notificacoes': notificacoes,
    })
# -------------------- Função para verificar se é ADMIN --------------------
def is_admin(user):
    return user.groups.filter(name='ADMIN').exists() or user.is_superuser

# -------------------- View para Adicionar Usuário --------------------
@login_required(login_url='login')
@user_passes_test(is_admin)
def adicionar_usuario(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            usuario = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['senha']
            )
            grupo = form.cleaned_data['grupo']
            usuario.groups.add(grupo)
            return redirect('index')
    else:
        form = UsuarioForm()

    # 🔹 monta o contexto principal
    context = {
        'form': form,
    }
    # 🔹 adiciona o contexto do sidebar
    context.update(get_sidebar_context(request))

    return render(request, 'estoque/adicionar_usuario.html', context)
from .utils import checar_estoque

@login_required(login_url='login')
def adicionar_produto(request):
    is_admin = request.user.groups.filter(name='ADMIN').exists() or request.user.is_superuser

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        quantidade_str = request.POST.get('quantidade', '0')

        # ✅ Converte quantidade para inteiro, tratando erro se não for número
        try:
            quantidade = int(quantidade_str)
        except ValueError:
            quantidade = 0

        if quantidade <= 0:
            messages.error(request, "Quantidade inválida!")
            return redirect('adicionar_produto')

        if is_admin:
            setor_id = request.POST.get('setor_responsavel')
            setor = Group.objects.get(id=setor_id) if setor_id else None
        else:
            setor = request.user.groups.first()

        if not setor:
            messages.error(request, "Setor inválido!")
            return redirect('adicionar_produto')

        existente = Produto.objects.filter(
            nome__icontains=nome,
            setor_responsavel=setor
        ).first()

        if existente:
            existente.quantidade += quantidade
            existente.observacoes = request.POST.get('observacoes', existente.observacoes)
            existente.save()
            produto = existente
        else:
            produto = Produto.objects.create(
                nome=nome,
                quantidade=quantidade,
                setor_responsavel=setor,
                observacoes=request.POST.get('observacoes', '')
            )

        # registra movimentação de ENTRADA
        Movimentacao.objects.create(
            produto=produto,
            usuario=request.user,
            tipo='entrada',
            quantidade=quantidade,
            observacao='Cadastro ou incremento via form'
        )

        # ✅ Checa estoque e cria notificação se necessário
        from .utils import checar_estoque
        checar_estoque(produto)

        messages.success(request, f"Produto '{produto.nome}' adicionado com sucesso!")
        return redirect('index')

    form = ProdutoForm(user=request.user)
    return render(request, 'estoque/adicionar_produto.html', {
        'form': form,
        'is_admin': is_admin,
    })

@login_required(login_url='login')
def produtos_setor(request, setor):
    user_groups = request.user.groups.all()
    is_admin = request.user.groups.filter(name='ADMIN').exists() or request.user.is_superuser

    # só deixa acessar se o usuário tem permissão
    if not is_admin and setor not in [g.name for g in user_groups]:
        return redirect('index')

    if is_admin and setor == 'todos':
        produtos_qs = Produto.objects.all().order_by('nome')
    else:
        produtos_qs = Produto.objects.filter(setor_responsavel__name=setor).order_by('nome')

    # === PAGINAÇÃO ===
    paginator = Paginator(produtos_qs, 15)  # 15 produtos por página
    page_number = request.GET.get('page')
    produtos_page = paginator.get_page(page_number)

    # Prepara hub_info para a sidebar
    if is_admin:
        setores = Group.objects.exclude(name__iexact='ADMIN')

    else:
        setores = user_groups

    hub_info = []
    for s in setores:
        produtos_setor_qs = Produto.objects.filter(setor_responsavel=s)
        hub_info.append({
            'nome_setor': s.name,
            'total_produtos': produtos_setor_qs.count()
        })

    context = {
        'produtos': produtos_page,  # <<< passa a página, não o queryset inteiro
        'setor': setor,
        'is_admin': is_admin,
        'hub_info': hub_info,
        'setores': setores,  # para o filtro do template
    }
    return render(request, 'estoque/produtos.html', context)


# -------------------- View para Gerenciar Usuários --------------------
@login_required(login_url='login')
@user_passes_test(is_admin)
def gerenciar_usuarios(request):
    # ------------------ POST (edição via modal) ------------------
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        usuario = get_object_or_404(User, id=user_id)

        # Atualiza campos diretamente do POST
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')

        senha = request.POST.get('senha')
        if senha:
            usuario.set_password(senha)  # altera apenas se preenchido

        usuario.save()

        # Atualiza grupo
        grupo_id = request.POST.get('grupo')
        grupo = get_object_or_404(Group, id=grupo_id)
        usuario.groups.clear()
        usuario.groups.add(grupo)

        return redirect('gerenciar_usuarios')

    # ------------------ GET (exibir lista) ------------------
    usuarios = User.objects.all()
    grupos = Group.objects.all()

    # Contexto para sidebar (mantendo padrão)
    user_groups = request.user.groups.all()
    is_admin_flag = request.user.groups.filter(name='ADMIN').exists() or request.user.is_superuser

    if is_admin_flag:
        setores = Group.objects.exclude(name__iexact='ADMIN')

    else:
        setores = user_groups

    hub_info = []
    for s in setores:
        produtos_setor = Produto.objects.filter(setor_responsavel=s)
        hub_info.append({
            'nome_setor': s.name,
            'total_produtos': produtos_setor.count()
        })

    context = {
        'usuarios': usuarios,
        'groups': grupos,
        'is_admin': is_admin_flag,
        'hub_info': hub_info,
    }

    return render(request, 'estoque/gerenciar_usuarios.html', context)


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)  # encerra a sessão
    return redirect('login')  # redireciona para a página de login


@login_required(login_url='login')
@require_POST
def retirar_item(request, produto_id):
    try:
        quantidade = int(request.POST.get('quantidade', 0))
        produto = Produto.objects.get(id=produto_id)

        # verifica se o usuário pode mexer nesse produto
        is_admin = request.user.groups.filter(name='ADMIN').exists() or request.user.is_superuser
        if not is_admin and produto.setor_responsavel not in request.user.groups.all():
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        if quantidade <= 0:
            return JsonResponse({'error': 'Quantidade inválida'}, status=400)

        if quantidade > produto.quantidade:
            return JsonResponse({'error': 'Quantidade maior que o estoque atual'}, status=400)

        # atualiza a quantidade
        produto.quantidade -= quantidade
        produto.save()

        # registra a movimentação
        from .models import Movimentacao
        Movimentacao.objects.create(
            produto=produto,
            usuario=request.user,
            quantidade=quantidade,  # sempre positivo
            tipo='saida',
            observacao=request.POST.get('observacao', '')
        )

        return JsonResponse({'success': True, 'nova_quantidade': produto.quantidade})

    except Produto.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Quantidade inválida'}, status=400)


    
@login_required(login_url='login')
@user_passes_test(is_admin)
def movimentacoes(request):
    user = request.user

    # 🔹 Busca movimentações (todas)
    movs = Movimentacao.objects.select_related('produto', 'usuario', 'produto__setor_responsavel').order_by('-data')

    # 🔹 Filtros de busca
    usuario = request.GET.get('usuario')
    produto = request.GET.get('produto')
    tipo = request.GET.get('tipo')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if usuario:
        movs = movs.filter(usuario__username__icontains=usuario)
    if produto:
        movs = movs.filter(produto__nome__icontains=produto)
    if tipo:
        movs = movs.filter(tipo=tipo)
    if data_inicio:
        movs = movs.filter(data__date__gte=data_inicio)
    if data_fim:
        movs = movs.filter(data__date__lte=data_fim)

    # 🔹 Controle de acesso: limita o que aparece na sidebar
    is_superuser = user.is_superuser
    is_admin_group = user.groups.filter(name__iexact='ADMIN').exists()

    # === SIDEBAR / HUB INFO ===
    hub_info = []

    if is_superuser:
        # Superusuário → vê todos os setores normalmente (exceto o ADMIN)
        setores = Group.objects.exclude(name__iexact='ADMIN')
        for s in setores:
            total = Produto.objects.filter(setor_responsavel=s).count()
            hub_info.append({
                'nome_setor': s.name,
                'total_produtos': total
            })
        # E adiciona o total geral (estoque "todos")
        total_geral = sum(s['total_produtos'] for s in hub_info)
        hub_info.append({'nome_setor': 'todos', 'total_produtos': total_geral})

    elif is_admin_group:
        # Usuário ADMIN comum → vê só o "todos"
        total_geral = Produto.objects.exclude(setor_responsavel__name__iexact='ADMIN').count()
        hub_info.append({'nome_setor': 'todos', 'total_produtos': total_geral})

    else:
        # Usuário de setor normal → vê apenas seus grupos
        setores = user.groups.all()
        for s in setores:
            total = Produto.objects.filter(setor_responsavel=s).count()
            hub_info.append({'nome_setor': s.name, 'total_produtos': total})

    # === PAGINAÇÃO ===
    paginator = Paginator(movs, 10)
    page_number = request.GET.get('page')
    movs_page = paginator.get_page(page_number)

    # === CONTEXTO ===
    context = {
        'movimentacoes': movs_page,
        'hub_info': hub_info,
        'is_superuser': is_superuser,
        'is_admin_group': is_admin_group,
    }

    return render(request, 'estoque/movimentacoes.html', context)

@login_required(login_url='login')
@user_passes_test(is_admin)
def exportar_movimentacoes(request):
    movs = Movimentacao.objects.select_related('produto','usuario').order_by('-data')

    # aplica os mesmos filtros do form
    usuario = request.GET.get('usuario')
    produto = request.GET.get('produto')
    tipo = request.GET.get('tipo')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if usuario:
        movs = movs.filter(usuario__username__icontains=usuario)
    if produto:
        movs = movs.filter(produto__nome__icontains=produto)
    if tipo:
        movs = movs.filter(tipo=tipo)
    if data_inicio:
        movs = movs.filter(data__date__gte=data_inicio)
    if data_fim:
        movs = movs.filter(data__date__lte=data_fim)

    # Cria CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="movimentacoes.csv"'

    writer = csv.writer(response)
    writer.writerow(['Data', 'Usuário', 'Produto', 'Tipo', 'Quantidade', 'Observação'])
    for mov in movs:
        writer.writerow([mov.data.strftime("%d/%m/%Y %H:%M"), mov.usuario.username, mov.produto.nome, mov.get_tipo_display(), mov.quantidade, mov.observacao])

    return response
from django.db.models.functions import TruncMonth, TruncDay
from django.db.models import Count
from django.utils import timezone
from datetime import datetime, timedelta, date, time
import calendar
from .models import Produto, Movimentacao, Setor 
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')  # redireciona para login se não for admin
def dashboard_graficos(request, periodo='all'):
    """
    Tela de gráficos do Admin com total de produtos por setor.
    """

    # Consulta: total de produtos por setor
    produtos_por_setor = (
        Produto.objects
        .values('setor_responsavel__name')
        .annotate(total=Sum('quantidade'))
        .order_by('setor_responsavel__name')
    )

    # Gerando dados para Chart.js
    chart_labels = [p['setor_responsavel__name'] for p in produtos_por_setor]
    chart_data = [p['total'] for p in produtos_por_setor]

    hoje = timezone.now().date()

    # Determina data inicial e função de trunc
    if periodo == "7":
        inicio = hoje - timedelta(days=7)
        trunc_func = TruncDay
    elif periodo == "30":
        inicio = hoje - timedelta(days=30)
        trunc_func = TruncDay
    elif periodo == "mes":
        inicio = hoje.replace(day=1)
        trunc_func = TruncDay
    else:
        inicio = None
        trunc_func = TruncMonth

    def aplicar_filtro(queryset, campo="data"):
        if inicio:
            filtro = {f"{campo}__gte": inicio}
            return queryset.filter(**filtro)
        return queryset

    def gerar_dados_linha(queryset, campo="data"):
        queryset = queryset.filter(**{f"{campo}__isnull": False})
        qs = aplicar_filtro(queryset, campo=campo)\
            .annotate(data_trunc=trunc_func(campo))\
            .values("data_trunc")\
            .annotate(total=Count("id"))\
            .order_by("data_trunc")

        labels, valores = [], []
        for item in qs:
            data = item["data_trunc"]
            if periodo == "all":
                labels.append(f"{calendar.month_abbr[data.month]} {data.year}")
            else:
                labels.append(data.strftime("%d/%m"))
            valores.append(item["total"])
        return labels, valores

    moviment_label, moviment_values = gerar_dados_linha(Movimentacao.objects)

    # Contexto para o template (sidebar precisa de is_admin e hub_info)
    context = {
        'is_admin': True,  # porque esse view é só admin
        'hub_info': Setor.objects.all(),  # ou a lógica para os setores do usuário
        'produtos_por_setor': produtos_por_setor,
        'labels_json': json.dumps(chart_labels),
        'data_json': json.dumps(chart_data),
        'movimentacoes_valores': json.dumps(moviment_values),
        'movimentacoes_meses': json.dumps(moviment_label),
    }

    return render(request, 'estoque/graficos.html', context)

@login_required(login_url='login')
@user_passes_test(is_admin)
def exportar_graficos_csv(request):
    """
    Exporta os dados de produtos por setor em CSV.
    """
    produtos_por_setor = Produto.objects.values('setor_responsavel__name') \
                                        .annotate(total=Sum('quantidade')) \
                                        .order_by('setor_responsavel__name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="estoque_setores.csv"'

    writer = csv.writer(response)
    writer.writerow(['Setor', 'Total de Produtos'])

    for item in produtos_por_setor:
        writer.writerow([item['setor_responsavel__name'], item['total']])

    return response

def listar_produtos(request):
    produtos = Produto.objects.all()
    setores = Group.objects.exclude(name__iexact='ADMIN')
 # pega todos os setores
    return render(request, 'estoque/listar_produtos.html', {
        'produtos': produtos,
        'setores': setores,
    })

from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Protocolo, Produto, Colaborador, Setor

@login_required(login_url='login')
def protocolo_create(request):
    if request.method == 'POST':
        colaborador_nome = request.POST.get('colaborador')
        produto_nome = request.POST.get('produto')
        patrimonio = request.POST.get('patrimonio')

        # Pega objetos reais
        try:
            colaborador = Colaborador.objects.get(nome=colaborador_nome)
        except Colaborador.DoesNotExist:
            messages.error(request, "Colaborador não encontrado!")
            return redirect('protocolo_create')

        try:
            produto = Produto.objects.get(nome=produto_nome)
        except Produto.DoesNotExist:
            messages.error(request, "Produto não encontrado!")
            return redirect('protocolo_create')

        # Checa estoque
        if produto.quantidade <= 0:
            messages.error(request, "Estoque insuficiente!")
            return redirect('protocolo_create')

        # Debita estoque
        produto.quantidade -= 1
        produto.save()

        # Cria protocolo
        Protocolo.objects.create(
            colaborador=colaborador,
            item=produto,
            patrimonio=patrimonio
        )

        messages.success(request, "Item registrado e debitado do estoque!")
        return redirect('protocolo_create')

    # Contexto da sidebar
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name='ADMIN').exists()
    pertence_geral = user.groups.filter(name__iexact='Geral').exists()

    # Monta hub_info para o sidebar (nome_setor + total_produtos)
    setores = Setor.objects.all()
    hub_info = [
        {
            'nome_setor': s.nome_setor,
            'total_produtos': Produto.objects.filter(setor_responsavel__name=s.nome_setor).count()
        }
        for s in setores
    ]

    context = {
        'is_admin': is_admin,
        'hub_info': hub_info,
        'pertence_geral': pertence_geral,
    }

    return render(request, 'estoque/protocolo.html', context)


from .forms import ColaboradorForm

def colaborador_create(request):
    if request.method == 'POST':
        form = ColaboradorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Colaborador cadastrado com sucesso!')
            return redirect('colaborador_create')
    else:
        form = ColaboradorForm()

    # ✅ adiciona contexto da sidebar
    context = {'form': form}
    context.update(get_sidebar_context(request))

    return render(request, 'estoque/colaborador_form.html', context)


from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from .models import Colaborador, Protocolo

from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def lista_colaboradores(request):
    query = request.GET.get('q', '')
    colaboradores = Colaborador.objects.all()

    if query:
        colaboradores = colaboradores.filter(
            Q(nome__icontains=query) | Q(codigo__icontains=query)
        )

    paginator = Paginator(colaboradores, 15)
    page_number = request.GET.get('page')
    colaboradores_page = paginator.get_page(page_number)

    # ✅ adiciona contexto da sidebar
    context = {'colaboradores': colaboradores_page}
    context.update(get_sidebar_context(request))

    return render(request, 'estoque/lista_colaboradores.html', context)


def exportar_colaborador(request, colaborador_id):
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    protocolos = Protocolo.objects.filter(colaborador=colaborador)

    conteudo = f"Colaborador: {colaborador.nome} ({colaborador.codigo})\n\nItens vinculados:\n"
    for p in protocolos:
        conteudo += f"- {p.item} | Patrimônio: {p.patrimonio} | Data: {p.data.strftime('%d/%m/%Y %H:%M')}\n"

    response = HttpResponse(conteudo, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="colaborador_{colaborador.id}.txt"'
    return response
# Função que retorna os dados comuns da sidebar
def get_sidebar_context(request):
    user_groups = request.user.groups.all()
    is_admin = request.user.groups.filter(name__iexact='ADMIN').exists() or request.user.is_superuser
    pertence_geral = request.user.groups.filter(name__iexact='Geral').exists()

    if is_admin:
        setores = Group.objects.exclude(name__iexact='ADMIN')
    else:
        setores = user_groups

    hub_info = []
    for s in setores:
        total_produtos = Produto.objects.filter(setor_responsavel=s).count()
        hub_info.append({
            'nome_setor': s.name,
            'total_produtos': total_produtos
        })

    return {
        'is_admin': is_admin,
        'hub_info': hub_info,
        'pertence_geral': pertence_geral,
    }

from django.http import JsonResponse
from .models import Colaborador, Produto

def buscar_colaboradores(request):
    termo = request.GET.get('q', '')
    colaboradores = Colaborador.objects.filter(nome__icontains=termo)[:10]

    results = [{"id": c.id, "nome": c.nome, "codigo": c.codigo} for c in colaboradores]
    return JsonResponse(results, safe=False)

def buscar_produtos(request):
    termo = request.GET.get('q', '')
    produtos = Produto.objects.filter(nome__icontains=termo)[:10]

    results = [{"id": p.id, "nome": p.nome, "quantidade": p.quantidade} for p in produtos]
    return JsonResponse(results, safe=False)
from django.http import JsonResponse
from .models import Protocolo

def verifica_patrimonio(request):
    patrimonio = request.GET.get('patrimonio', '').strip()
    tipo = request.GET.get('tipo', 'A')  # 'A' como padrão se não vier nada

    if not patrimonio:
        return JsonResponse({'exists': False})

    exists = Protocolo.objects.filter(patrimonio=patrimonio, tipo=tipo).exists()
    return JsonResponse({'exists': exists})

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from .models import Protocolo, Produto

@login_required
def lista_patrimonios(request):
    user = request.user

    # 🔹 Busca todos os protocolos (patrimônios)
    patrimonios_list = Protocolo.objects.select_related("item", "colaborador").all().order_by("-data")

    # 🔹 Filtro de busca
    termo = request.GET.get('q', '').strip()
    if termo:
        patrimonios_list = patrimonios_list.filter(
            Q(item__nome__icontains=termo) |
            Q(patrimonio__icontains=termo) |
            Q(colaborador__nome__icontains=termo)
        )

    # 🔹 Paginação
    paginator = Paginator(patrimonios_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 🔹 Contexto comum
    is_admin = user.is_superuser or user.groups.filter(name__iexact="ADMIN").exists()
    pertence_geral = user.groups.filter(name__iexact="Geral").exists()
    user_groups = user.groups.all()

    # 🔹 Se for admin → mostra todos os setores (exceto o ADMIN)
    # 🔹 Senão → mostra apenas os grupos do usuário
    if is_admin:
        setores = Group.objects.exclude(name__iexact="ADMIN")
    else:
        setores = user_groups

    # 🔹 Monta hub_info para a sidebar
    hub_info = []
    total_geral = 0
    for s in setores:
        count = Produto.objects.filter(setor_responsavel=s).count()
        total_geral += count
        hub_info.append({
            "nome_setor": s.name,
            "total_produtos": count,
        })

    # 🔹 Se for admin, adiciona o “setor virtual” ADMIN → redireciona para 'todos'
    if is_admin:
        hub_info.append({
            "nome_setor": "todos",  # este nome será usado como link correto
            "total_produtos": total_geral,
        })

    # 🔹 Renderiza o template
    context = {
        'patrimonios': page_obj,
        'q': termo,
        'is_admin': is_admin,
        'pertence_geral': pertence_geral,
        'hub_info': hub_info,
        'pagina_atual': 'lista_patrimonios',
    }

    return render(request, "estoque/lista_patrimonios.html", context)


    from .utils import checar_estoque
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Notificacao
from django.utils import timezone

@login_required
def notificacoes(request):
    user = request.user
    is_admin = user.groups.filter(name='ADMIN').exists() or user.is_superuser

    if is_admin:
        # Admin vê todas as notificações não vistas
        notifs = Notificacao.objects.filter(vista=False).order_by('-criado_em')
    else:
        # Usuário normal vê apenas notificações do seu setor
        grupos = user.groups.all()
        notifs = Notificacao.objects.filter(vista=False, setor__in=grupos).order_by('-criado_em')

    data = []
    for n in notifs:
        data.append({
            'id': n.id,
            'mensagem': n.mensagem,
            'produto': n.produto.nome,
            'setor': n.setor.name if n.setor else '',
            'criado_em': n.criado_em.strftime('%d/%m/%Y %H:%M')
        })

    return JsonResponse({'notificacoes': data})
@login_required
def marcar_vista(request):
    notif_id = request.POST.get('id')
    try:
        notif = Notificacao.objects.get(id=notif_id)
        # só marca como vista se for admin ou do setor correto
        if request.user.groups.filter(name='ADMIN').exists() or notif.setor in request.user.groups.all():
            notif.vista = True
            notif.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Sem permissão'})
    except Notificacao.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notificação não encontrada'})
# views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from estoque.models import Profile

@login_required
def atualizar_avatar(request):
    if request.method == 'POST':
        avatar_url = request.POST.get('avatar')
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile.avatar_url = avatar_url
        profile.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método inválido'})

from django.shortcuts import render

def pagina_nao_encontrada(request, exception=None):
    return render(request, 'estoque/404.html', status=404)
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import SolicitacaoCompraForm
from .models import SolicitacaoCompra, Produto
from django.core.paginator import Paginator


@login_required
def solicitar_compra(request):
    user = request.user
    setor = user.groups.first()

    if request.method == 'POST':
        form = SolicitacaoCompraForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.solicitante = user
            solicitacao.setor = setor
            solicitacao.save()

            # 🔹 Envio de e-mail em HTML
            assunto = f"🛒 Nova Solicitação de Compra - {setor.name}"

            html_corpo = f"""
<html>
<body style="margin: 0; padding: 20px; font-family: 'Segoe UI', Arial, Helvetica, sans-serif; color: #2d3748; background: white; line-height: 1.6;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.15);">
    <tr>
      <td>
        
        <!-- Header com Logo -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="background: black; padding: 30px 20px 20px; text-align: center;">
              <div style="background: black; padding: 12px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <img src="http://libanoeducacional.ddns.net:9283/media/avatars/libanoAvatar.png" 
                     alt="Líbano Educacional" 
                     width="80" 
                     height="80"
                     style="width: 80px; height: 80px; display: block; margin: 0 auto; border-radius: 8px;">
              </div>
              <h1 style="color: #ffffff; margin: 20px 0 0 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
                🛒 Nova Solicitação de Compra
              </h1>
              <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0; font-size: 15px;">
                Aguardando sua análise e aprovação
              </p>
            </td>
          </tr>
        </table>
        
        <!-- Corpo do conteúdo -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding: 30px 25px;">
              
              <!-- Card de Informações -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 25px;">
                <tr>
                  <td style="padding: 25px;">
                    
                    <!-- Solicitante -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 16px;">
                      <tr>
                        <td width="50" style="padding: 8px 0; vertical-align: top;">
                          <div style="background: #ea005f; width: 36px; height: 36px; border-radius: 8px; text-align: center;">
                            <span style="color: white; font-size: 16px; line-height: 36px;">👤</span>
                          </div>
                        </td>
                        <td style="padding: 8px 0;">
                          <div style="font-weight: 600; color: #4a5568; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">SOLICITANTE</div>
                          <div style="color: #1a202c; font-size: 15px; font-weight: 600;">{user.get_full_name() or user.username}</div>
                        </td>
                      </tr>
                    </table>
                    
                    <!-- Setor -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 16px;">
                      <tr>
                        <td width="50" style="padding: 8px 0; vertical-align: top;">
                          <div style="background: #3182ce; width: 36px; height: 36px; border-radius: 8px; text-align: center;">
                            <span style="color: white; font-size: 16px; line-height: 36px;">🏢</span>
                          </div>
                        </td>
                        <td style="padding: 8px 0;">
                          <div style="font-weight: 600; color: #4a5568; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">SETOR</div>
                          <div style="color: #1a202c; font-size: 15px;">{setor.name}</div>
                        </td>
                      </tr>
                    </table>
                    
                    <!-- Produto -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 16px;">
                      <tr>
                        <td width="50" style="padding: 8px 0; vertical-align: top;">
                          <div style="background: #38a169; width: 36px; height: 36px; border-radius: 8px; text-align: center;">
                            <span style="color: white; font-size: 16px; line-height: 36px;">📦</span>
                          </div>
                        </td>
                        <td style="padding: 8px 0;">
                          <div style="font-weight: 600; color: #4a5568; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">PRODUTO SOLICITADO</div>
                          <div style="color: #1a202c; font-size: 15px;">{solicitacao.nome_produto}</div>
                        </td>
                      </tr>
                    </table>
                    
                    <!-- Quantidade -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 16px;">
                      <tr>
                        <td width="50" style="padding: 8px 0; vertical-align: top;">
                          <div style="background: #dd6b20; width: 36px; height: 36px; border-radius: 8px; text-align: center;">
                            <span style="color: white; font-size: 16px; line-height: 36px;">🔢</span>
                          </div>
                        </td>
                        <td style="padding: 8px 0;">
                          <div style="font-weight: 600; color: #4a5568; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">QUANTIDADE</div>
                          <div style="color: #dd6b20; font-size: 15px; font-weight: 700;">{solicitacao.quantidade} unidades</div>
                        </td>
                      </tr>
                    </table>
                    
                    <!-- Justificativa -->
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="50" style="padding: 8px 0; vertical-align: top;">
                          <div style="background: #e53e3e; width: 36px; height: 36px; border-radius: 8px; text-align: center;">
                            <span style="color: white; font-size: 16px; line-height: 36px;">📝</span>
                          </div>
                        </td>
                        <td style="padding: 8px 0;">
                          <div style="font-weight: 600; color: #4a5568; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">JUSTIFICATIVA</div>
                          <div style="color: #1a202c; font-size: 14px; line-height: 1.5; background: white; padding: 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
                            {solicitacao.justificativa or '<span style="color: #a0aec0; font-style: italic;">Não informada</span>'}
                          </div>
                        </td>
                      </tr>
                    </table>
                    
                  </td>
                </tr>
              </table>

              <!-- Card de Ação -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: linear-gradient(135deg, #fed7d7 0%, #feebc8 100%); border: 1px solid #fbd38d; border-radius: 12px; margin-bottom: 25px;">
                <tr>
                  <td style="padding: 20px; text-align: center;">
                    <div style="color: #dd6b20; font-size: 28px; margin-bottom: 8px;">⚡</div>
                    <h3 style="color: #c05621; margin: 0 0 8px 0; font-size: 16px; font-weight: 700;">
                      Ação Necessária
                    </h3>
                    <p style="color: #744210; margin: 0; font-size: 14px;">
                      Esta solicitação precisa da sua análise no sistema
                    </p>
                  </td>
                </tr>
              </table>
              
              <!-- Botão de ação -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 25px;">
                <tr>
                  <td align="center">
                    <a href="http://182.16.0.230:8000/estoque/"
                       style="display: inline-block; background: #ea005f; color: white; padding: 16px 35px; text-decoration: none; border-radius: 10px; font-weight: 700; font-size: 15px; text-align: center; box-shadow: 0 4px 15px rgba(234, 0, 95, 0.3);">
                       🔍 Analisar Solicitação
                    </a>
                    <p style="color: #718096; font-size: 13px; margin: 12px 0 0 0; line-height: 1.5;">
                      Clique para acessar o sistema e processar esta solicitação
                    </p>
                  </td>
                </tr>
              </table>
              
              <!-- Informações adicionais -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #edf2f7; border-radius: 8px; margin-bottom: 20px;">
                <tr>
                  <td style="padding: 15px; text-align: center;">
                    <p style="color: #4a5568; margin: 0; font-size: 13px; font-weight: 500;">
                      📅 <strong>Data e Hora:</strong> {solicitacao.data_criacao.strftime('%d/%m/%Y às %H:%M') if hasattr(solicitacao, 'data_criacao') else 'Data não disponível'}
                    </p>
                  </td>
                </tr>
              </table>
              
              <!-- Rodapé -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top: 1px solid #e2e8f0; padding-top: 20px;">
                <tr>
                  <td align="center">
                    <p style="font-size: 12px; color: #718096; margin: 0 0 8px 0; line-height: 1.5;">
                      🚀 Enviado automaticamente pelo Sistema de Compras
                    </p>
                    <p style="font-size: 14px; color: #2d3748; margin: 0; font-weight: 700;">
                      Líbano Educacional
                    </p>
                    <p style="font-size: 11px; color: #a0aec0; margin: 12px 0 0 0;">
                      📩 Esta é uma mensagem automática. Por favor, responda a este e-mail para autorizar o pedido de compra.
                    </p>
                  </td>
                </tr>
              </table>
              
            </td>
          </tr>
        </table>
        
      </td>
    </tr>
  </table>
</body>
</html>
            """

            email = EmailMultiAlternatives(
                subject=assunto,
                body=(
                    "Nova solicitação de compra registrada.\n"
                    "Acesse o sistema para aprovar ou negar:\n"
                    f"{getattr(settings, 'SITE_URL', '#')}/admin/solicitacoes/"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=['fabio.fernandes@libanoeducacional.com.br'],
                cc=['fabio.fernandes@libanoeducacional.com.br'],
            )
            email.attach_alternative(html_corpo, "text/html")
            email.send(fail_silently=False)

            messages.success(request, "Solicitação enviada com sucesso!")
            return redirect('solicitar_compra')
    else:
        form = SolicitacaoCompraForm()

    # 🔹 Paginação (15 por página)
    solicitacoes_list = SolicitacaoCompra.objects.filter(solicitante=user).order_by('-data_solicitacao')
    paginator = Paginator(solicitacoes_list, 15)
    page_number = request.GET.get('page')
    solicitacoes = paginator.get_page(page_number)

    return render(request, 'estoque/solicitar_compra.html', {
        'form': form,
        'solicitacoes': solicitacoes,
    })


@login_required
def atualizar_estoque(request, solicitacao_id):
    if not request.user.groups.filter(name__iexact='ADMIN').exists():
        messages.error(request, "Acesso negado.")
        return redirect('index')

    solicitacao = SolicitacaoCompra.objects.get(id=solicitacao_id)
    produto, created = Produto.objects.get_or_create(
        nome=solicitacao.nome_produto,
        defaults={'quantidade': solicitacao.quantidade, 'setor_responsavel': solicitacao.setor},
    )
    if not created:
        produto.quantidade += solicitacao.quantidade
        produto.save()

    solicitacao.status = 'CONCLUÍDA'
    solicitacao.save()

    messages.success(request, "Estoque atualizado com sucesso.")
    return redirect('admin_solicitacoes')
import csv
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.core.mail import EmailMessage
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from .models import SolicitacaoCompra, Produto


@login_required
def gerenciar_solicitacoes(request):
    user = request.user

    # 🔒 Apenas ADMIN e GERAL podem acessar
    if not (user.is_superuser or user.groups.filter(name__iexact='GERAL').exists()):
        return HttpResponseForbidden("Você não tem permissão para acessar esta página.")

    # 📊 Buscar todas as solicitações
    solicitacoes = SolicitacaoCompra.objects.all().order_by('-data_solicitacao')

    # --- 🔍 FILTROS ---
    status = request.GET.get('status')
    setor = request.GET.get('setor')
    busca = request.GET.get('busca')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if status and status != 'TODOS':
        solicitacoes = solicitacoes.filter(status=status)

    if setor and setor != 'TODOS':
        solicitacoes = solicitacoes.filter(setor__name__icontains=setor)

    if busca:
        solicitacoes = solicitacoes.filter(
            Q(nome_produto__icontains=busca) |
            Q(solicitante__username__icontains=busca)
        )

    if data_inicio:
        solicitacoes = solicitacoes.filter(data_solicitacao__date__gte=data_inicio)

    if data_fim:
        solicitacoes = solicitacoes.filter(data_solicitacao__date__lte=data_fim)

    # --- PAGINAÇÃO (20 por página) ---
    paginator = Paginator(solicitacoes, 20)
    page_number = request.GET.get('page')
    solicitacoes = paginator.get_page(page_number)

    # 📨 Ações (Aprovar / Negar / Concluir)
    if request.method == 'POST':
        solicitacao_id = request.POST.get('id')
        acao = request.POST.get('acao')
        observacao = request.POST.get('observacao', '')

        solicitacao = SolicitacaoCompra.objects.get(id=solicitacao_id)

        # --- ✅ Aprovar solicitação ---
        if acao == 'aprovar':
            solicitacao.status = 'APROVADA'
            solicitacao.observacao_admin = observacao
            solicitacao.data_atualizacao = timezone.now()
            solicitacao.save()

            # E-mail de aprovação
            EmailMessage(
                subject=f"Sua solicitação foi APROVADA - {solicitacao.nome_produto}",
                body=(
                    f"A solicitação do produto '{solicitacao.nome_produto}' foi aprovada.\n"
                    f"Quantidade: {solicitacao.quantidade}\n"
                    f"Observação: {observacao or '---'}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[solicitacao.solicitante.email],
            ).send(fail_silently=True)

            messages.success(request, f"Solicitação '{solicitacao.nome_produto}' aprovada com sucesso!")

        # --- ❌ Negar solicitação ---
        elif acao == 'negar':
            solicitacao.status = 'NEGADA'
            solicitacao.observacao_admin = observacao
            solicitacao.data_atualizacao = timezone.now()
            solicitacao.save()

            # E-mail de negação
            EmailMessage(
                subject=f"Sua solicitação foi NEGADA - {solicitacao.nome_produto}",
                body=(
                    f"A solicitação do produto '{solicitacao.nome_produto}' foi negada pelo setor de compras.\n"
                    f"Motivo: {observacao or 'Não informado.'}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[solicitacao.solicitante.email],
            ).send(fail_silently=True)

            messages.warning(request, f"Solicitação '{solicitacao.nome_produto}' foi negada.")

        # --- 📦 Concluir e atualizar estoque ---
        elif acao == 'concluir':
            solicitacao.status = 'CONCLUÍDA'
            solicitacao.observacao_admin = observacao
            solicitacao.data_atualizacao = timezone.now()
            solicitacao.save()

            produto, created = Produto.objects.get_or_create(
                nome=solicitacao.nome_produto,
                defaults={'quantidade': solicitacao.quantidade, 'setor_responsavel': solicitacao.setor}
            )
            if not created:
                produto.quantidade += solicitacao.quantidade
                produto.save()

            # E-mail de conclusão
            EmailMessage(
                subject=f"Solicitação CONCLUÍDA - {solicitacao.nome_produto}",
                body=(
                    f"O produto '{solicitacao.nome_produto}' foi adicionado ao estoque.\n"
                    f"Quantidade: {solicitacao.quantidade}\n"
                    f"Status final: CONCLUÍDA"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[solicitacao.solicitante.email],
            ).send(fail_silently=True)

            messages.success(request, f"Estoque atualizado e solicitação marcada como concluída!")

        return redirect('gerenciar_solicitacoes')
# --- 🧾 Exportar CSV ---
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="solicitacoes_compras.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Solicitante', 'Setor', 'Produto', 'Quantidade', 'Status', 'Justificativa', 'Observação Admin', 'Data Solicitação', 'Última Atualização'])

        for s in solicitacoes:
            writer.writerow([
                s.id,
                s.solicitante.username,
                s.setor.name if s.setor else '',
                s.nome_produto,
                s.quantidade,
                s.status,
                s.justificativa or '',
                s.observacao_admin or '',
                s.data_solicitacao.strftime('%d/%m/%Y %H:%M'),
                s.data_atualizacao.strftime('%d/%m/%Y %H:%M') if s.data_atualizacao else '',
            ])

        return response
    # 🔚 Renderiza página com filtros e paginação
    return render(request, 'estoque/gerenciar_solicitacoes.html', {
        'solicitacoes': solicitacoes,
        'status_atual': status or 'TODOS',
        'setor_atual': setor or 'TODOS',
        'busca': busca or '',
        'data_inicio': data_inicio or '',
        'data_fim': data_fim or '',
    })


