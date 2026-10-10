from django import forms

from .models import Aluno


class AlunoCadastroForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = [
            "codigo",
            "nome",
            "matricula",
            "cpf",
            "curso",
            "identidade",
            "orgao_expedidor",
            "data_conclusao",
            "data_expedicao",
            "uf",
            "pai",
            "mae",
            "nascimento",
            "naturalidade",
            "nacionalidade",
            "sexo",
            "observacao_historico",
            "ativo",
        ]
        labels = {
            "codigo": "Código do aluno",
            "nome": "Nome completo",
            "matricula": "Matrícula",
            "cpf": "CPF",
            "curso": "Curso",
            "identidade": "Carteira de identidade",
            "orgao_expedidor": "Órgão expedidor / Estado",
            "data_conclusao": "Data de conclusão",
            "data_expedicao": "Data de expedição",
            "uf": "UF de nascimento",
            "pai": "Nome do pai",
            "mae": "Nome da mãe",
            "nascimento": "Data de nascimento",
            "naturalidade": "Naturalidade",
            "nacionalidade": "Nacionalidade",
            "sexo": "Sexo",
            "observacao_historico": "Observações do histórico",
            "ativo": "Aluno ativo",
        }
        widgets = {
            "observacao_historico": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Observações que devem constar no histórico"}
            ),
        }

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"]
        if codigo <= 0:
            raise forms.ValidationError("Informe um código maior que zero.")
        return codigo

    def clean_nome(self):
        nome = (self.cleaned_data.get("nome") or "").strip()
        if not nome:
            raise forms.ValidationError("Informe o nome completo do aluno.")
        return nome
