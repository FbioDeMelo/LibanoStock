from django import forms
from django.contrib.auth.models import User, Group
from .models import Produto
from .models import Protocolo, Colaborador, Produto

class UsuarioForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput)
    grupo = forms.ModelChoiceField(queryset=Group.objects.all(), empty_label="Selecione o setor")

    class Meta:
        model = User
        fields = ['username', 'email', 'senha', 'grupo']

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'quantidade', 'observacoes', 'setor_responsavel']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Se não for ADMIN, só deixa o próprio setor e bloqueia o campo
            if not user.groups.filter(name='ADMIN').exists() and not user.is_superuser:
                self.fields['setor_responsavel'].queryset = user.groups.all()
                self.fields['setor_responsavel'].initial = user.groups.first()
                self.fields['setor_responsavel'].disabled = True
from django import forms
from .models import Protocolo, Produto

class ProtocoloForm(forms.ModelForm):
    class Meta:
        model = Protocolo
        fields = ['colaborador', 'item', 'patrimonio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Agora item é um queryset de Produto (FK), não strings
        self.fields['item'].queryset = Produto.objects.filter(quantidade__gt=0)
        
        self.fields['colaborador'].widget.attrs.update({'class': 'form-control'})
        self.fields['patrimonio'].widget.attrs.update({'class': 'form-control'})
        self.fields['item'].widget.attrs.update({'class': 'form-control'})
from django import forms
from .models import Colaborador

class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = ['codigo', 'nome']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
        }   
from django import forms
from .models import SolicitacaoCompra

class SolicitacaoCompraForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoCompra
        fields = ['nome_produto', 'quantidade', 'justificativa']
        widgets = {
            'justificativa': forms.Textarea(attrs={'rows': 3}),
        }

