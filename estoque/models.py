from django.db import models
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.core.files import File
from django.conf import settings
from io import BytesIO
import qrcode

class Produto(models.Model):
    nome = models.CharField(max_length=100)  # Nome do produto
    quantidade = models.IntegerField(default=0)  # Quantidade em estoque
    setor_responsavel = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    data_entrada = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True, null=True)
    qrcode_imagem = models.ImageField(upload_to='qrcodes/', blank=True, null=True)

    class Meta:
        unique_together = ('nome', 'setor_responsavel')
        verbose_name_plural = "Produtos"

    def __str__(self):
        return f"{self.nome} ({self.quantidade})"

    def save(self, *args, **kwargs):
        """Salva o produto e gera o QR code, se ainda não existir."""
        criando = self.pk is None  # verifica se é um novo produto
        super().save(*args, **kwargs)

        # Só gera QR se for novo ou se não existir ainda
        if criando or not self.qrcode_imagem:
            qr_data = f"http://182.16.0.251:8000/produto/{self.id}/"  #altere sempre que rodar em outro dia
            qr = qrcode.make(qr_data)

            buffer = BytesIO()
            qr.save(buffer, format='PNG')
            file_name = f'qrcode_produto_{self.id}.png'
            self.qrcode_imagem.save(file_name, File(buffer), save=False)
            buffer.close()
            super().save(update_fields=['qrcode_imagem'])



class Movimentacao(models.Model):
    TIPO_CHOICES = (
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
    )

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField()
    data = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.produto.nome} ({self.quantidade})"


class Setor(models.Model):
    nome_setor = models.CharField(max_length=100, default='Sem Nome')

    def __str__(self):
        return self.nome_setor

class Colaborador(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

class Protocolo(models.Model):
    TIPO_CHOICES = [
        ('A', 'Antigo (sem zeros)'),
        ('B', 'Novo (com zeros)'),
    ]

    colaborador = models.ForeignKey(Colaborador, on_delete=models.CASCADE)
    item = models.ForeignKey(Produto, on_delete=models.CASCADE)
    item_nome = models.CharField(max_length=100, blank=True, null=True)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES, default='A')
    patrimonio = models.CharField(max_length=50)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tipo', 'patrimonio')

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.patrimonio} ({self.item_nome or self.item})"

# =========================
# Notificações
# =========================
from django.db import models
from django.contrib.auth.models import Group
from .models import Produto  # ajuste se necessário

class Notificacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, null=True)  # deixa opcional
    setor = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)
    mensagem = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    vista = models.BooleanField(default=False)  # caso já tenha mudado 'lida' para 'vista'

    def __str__(self):
        return f"{self.produto} - {self.mensagem}"

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.produto.nome} - {'Vista' if self.vista else 'Nova'}"
# models.py
from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar_url = models.URLField(
        max_length=500,
        default='https://cdn-icons-png.flaticon.com/512/149/149071.png'#mude a img padrão do avatar
    )

    def __str__(self):
        return self.user.username
from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from .models import Produto  # se estiver no mesmo app, pode remover esse import circular depois

STATUS_CHOICES = [
    ('PENDENTE', 'Pendente'),
    ('APROVADA', 'Aprovada'),
    ('CONCLUÍDA', 'Concluída'),
    ('NEGADA', 'Negada'),
]

class SolicitacaoCompra(models.Model):
    solicitante = models.ForeignKey(User, on_delete=models.CASCADE)
    setor = models.ForeignKey(Group, on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True, blank=True)
    nome_produto = models.CharField(max_length=120)
    quantidade = models.PositiveIntegerField(default=1)
    justificativa = models.TextField(blank=True, null=True)
    data_solicitacao = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    observacao_admin = models.TextField(blank=True, null=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome_produto} - {self.status}"