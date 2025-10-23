from .models import Notificacao
from django.db.models.signals import post_save
from django.dispatch import receiver
from estoque.models import *

@receiver(post_save, sender=Produto)
def checar_estoque(sender,instance, created, **kwargs):

    if instance.quantidade <= 2:
        notif = Notificacao.objects.filter(produto=instance,vista=False).first()
        if not notif:
            Notificacao.objects.create(
                produto=instance,
                setor=instance.setor_responsavel,
                mensagem=f"Produto {instance} atingiu quantidade mínima ({instance.quantidade})"
            )
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def criar_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)