from django import forms

from .models import Aluno, ConfiguracaoAno


UF_CHOICES = [
    ("", "Selecione..."),
    ("AC", "AC — Acre"),
    ("AL", "AL — Alagoas"),
    ("AP", "AP — Amapá"),
    ("AM", "AM — Amazonas"),
    ("BA", "BA — Bahia"),
    ("CE", "CE — Ceará"),
    ("DF", "DF — Distrito Federal"),
    ("ES", "ES — Espírito Santo"),
    ("GO", "GO — Goiás"),
    ("MA", "MA — Maranhão"),
    ("MT", "MT — Mato Grosso"),
    ("MS", "MS — Mato Grosso do Sul"),
    ("MG", "MG — Minas Gerais"),
    ("PA", "PA — Pará"),
    ("PB", "PB — Paraíba"),
    ("PR", "PR — Paraná"),
    ("PE", "PE — Pernambuco"),
    ("PI", "PI — Piauí"),
    ("RJ", "RJ — Rio de Janeiro"),
    ("RN", "RN — Rio Grande do Norte"),
    ("RS", "RS — Rio Grande do Sul"),
    ("RO", "RO — Rondônia"),
    ("RR", "RR — Roraima"),
    ("SC", "SC — Santa Catarina"),
    ("SP", "SP — São Paulo"),
    ("SE", "SE — Sergipe"),
    ("TO", "TO — Tocantins"),
]

SEXO_CHOICES = [
    ("", "Selecione..."),
    ("FEMININO", "Feminino"),
    ("MASCULINO", "Masculino"),
]

CURSO_CHOICES = [
    ("", "Selecione..."),
    ("ENSINO FUNDAMENTAL", "Ensino Fundamental"),
]


class AlunoCadastroForm(forms.ModelForm):
    uf = forms.ChoiceField(
        choices=UF_CHOICES,
        required=False,
        label="UF de nascimento",
    )
    sexo = forms.ChoiceField(
        choices=SEXO_CHOICES,
        required=False,
        label="Sexo",
    )
    curso = forms.ChoiceField(
        choices=CURSO_CHOICES,
        required=False,
        label="Curso",
    )

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
            "pai": "Nome do pai",
            "mae": "Nome da mãe",
            "nascimento": "Data de nascimento",
            "naturalidade": "Naturalidade",
            "nacionalidade": "Nacionalidade",
            "observacao_historico": "Observações do histórico",
            "ativo": "Aluno ativo",
        }
        widgets = {
            "observacao_historico": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Observações que devem constar no histórico",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Preserva valores antigos/importados que eventualmente não estejam
        # na lista padronizada, sem impedir a edição do cadastro.
        if self.instance and self.instance.pk:
            if self.instance.uf and self.instance.uf not in dict(self.fields["uf"].choices):
                self.fields["uf"].choices = list(self.fields["uf"].choices) + [
                    (self.instance.uf, self.instance.uf)
                ]
            if (
                self.instance.sexo
                and self.instance.sexo not in dict(self.fields["sexo"].choices)
            ):
                self.fields["sexo"].choices = list(self.fields["sexo"].choices) + [
                    (self.instance.sexo, self.instance.sexo)
                ]
            if (
                self.instance.curso
                and self.instance.curso not in dict(self.fields["curso"].choices)
            ):
                self.fields["curso"].choices = list(self.fields["curso"].choices) + [
                    (self.instance.curso, self.instance.curso)
                ]

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



class ConfiguracaoAnoForm(forms.ModelForm):
    uf = forms.ChoiceField(
        choices=UF_CHOICES,
        required=False,
        label="UF",
    )

    class Meta:
        model = ConfiguracaoAno
        fields = [
            "ano",
            "media_minima",
            "ch_anual",
            "dias_letivos",
            "ch_ingles",
            "ch_sem_ingles",
            "data_conclusao",
            "escola",
            "municipio",
            "uf",
        ]
        labels = {
            "ano": "Ano letivo",
            "media_minima": "Mínimo para aprovação",
            "ch_anual": "Carga horária anual",
            "dias_letivos": "Dias letivos",
            "ch_ingles": "Carga horária de Inglês",
            "ch_sem_ingles": "Carga horária sem Inglês",
            "data_conclusao": "Data de conclusão",
            "escola": "Escola",
            "municipio": "Município",
            "uf": "UF",
        }
        widgets = {
            "ano": forms.NumberInput(attrs={"min": 1900, "max": 2100}),
            "media_minima": forms.TextInput(
                attrs={"placeholder": "Ex.: 60 ou 0,60"}
            ),
            "ch_anual": forms.TextInput(
                attrs={"placeholder": "Ex.: 800 ou 833:20"}
            ),
            "dias_letivos": forms.TextInput(attrs={"placeholder": "Ex.: 200"}),
            "ch_ingles": forms.TextInput(attrs={"placeholder": "Ex.: 66:40"}),
            "ch_sem_ingles": forms.TextInput(attrs={"placeholder": "Ex.: 766:40"}),
            "data_conclusao": forms.TextInput(
                attrs={"placeholder": "DD/MM/AAAA"}
            ),
            "municipio": forms.TextInput(attrs={"placeholder": "MONTES CLAROS"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            atual = self.instance.uf
            if atual and atual not in dict(self.fields["uf"].choices):
                self.fields["uf"].choices = list(self.fields["uf"].choices) + [
                    (atual, atual)
                ]

    def clean_ano(self):
        ano = self.cleaned_data["ano"]
        if ano < 1900 or ano > 2100:
            raise forms.ValidationError("Informe um ano entre 1900 e 2100.")
        return ano
