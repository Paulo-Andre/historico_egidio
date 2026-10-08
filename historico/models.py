from django.db import models


class Aluno(models.Model):
    codigo = models.PositiveIntegerField(unique=True, db_index=True)
    nome = models.CharField(max_length=255, db_index=True)
    matricula = models.CharField(max_length=50, blank=True)
    cpf = models.CharField(max_length=14, blank=True)
    curso = models.CharField(max_length=120, blank=True, default="ENSINO FUNDAMENTAL")
    uf = models.CharField(max_length=10, blank=True)
    pai = models.CharField(max_length=255, blank=True)
    mae = models.CharField(max_length=255, blank=True)
    nascimento = models.CharField(max_length=30, blank=True)
    naturalidade = models.CharField(max_length=120, blank=True)
    nacionalidade = models.CharField(max_length=120, blank=True)
    sexo = models.CharField(max_length=30, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ConfiguracaoAno(models.Model):
    ano = models.PositiveIntegerField(unique=True)
    ch_ingles = models.CharField(max_length=30, blank=True)
    ch_anual = models.CharField(max_length=30, blank=True)
    dias_letivos = models.CharField(max_length=30, blank=True)
    ch_sem_ingles = models.CharField(max_length=30, blank=True)
    media_minima = models.CharField(max_length=30, blank=True)
    escola = models.CharField(max_length=255, blank=True)
    municipio = models.CharField(max_length=120, default="MONTES CLAROS")
    uf = models.CharField(max_length=2, default="MG")

    class Meta:
        ordering = ["ano"]

    def __str__(self):
        return str(self.ano)


class RegistroAcademico(models.Model):
    aluno = models.ForeignKey(
        Aluno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_academicos",
    )
    nome_original = models.CharField(max_length=255, blank=True)
    ano = models.PositiveIntegerField(db_index=True)
    serie = models.PositiveSmallIntegerField(null=True, blank=True)
    turma = models.CharField(max_length=120, blank=True)
    faltas = models.CharField(max_length=40, blank=True)
    frequencia = models.CharField(max_length=30, blank=True)
    carga_horaria = models.CharField(max_length=30, blank=True)
    resultado = models.CharField(max_length=80, blank=True)
    escola = models.CharField(max_length=255, blank=True)
    municipio = models.CharField(max_length=120, default="MONTES CLAROS")
    uf = models.CharField(max_length=2, default="MG")
    linha_origem = models.PositiveIntegerField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["ano", "serie", "turma", "nome_original"]
        constraints = [
            models.UniqueConstraint(
                fields=["ano", "linha_origem"],
                name="uniq_registro_ano_linha",
            )
        ]

    def __str__(self):
        nome = self.aluno.nome if self.aluno_id else self.nome_original
        return f"{self.ano} - {nome}"


class Nota(models.Model):
    ARTE = "arte"
    CIENCIAS = "ciencias"
    EDUCACAO_FISICA = "educacao_fisica"
    EDUCACAO_RELIGIOSA = "educacao_religiosa"
    GEOGRAFIA = "geografia"
    HISTORIA = "historia"
    LINGUA_INGLESA = "lingua_inglesa"
    MATEMATICA = "matematica"
    LINGUA_PORTUGUESA = "lingua_portuguesa"

    COMPONENTES = [
        (ARTE, "Arte"),
        (CIENCIAS, "Ciências"),
        (EDUCACAO_FISICA, "Educação Física"),
        (EDUCACAO_RELIGIOSA, "Educação Religiosa"),
        (GEOGRAFIA, "Geografia"),
        (HISTORIA, "História"),
        (LINGUA_INGLESA, "Língua Inglesa"),
        (MATEMATICA, "Matemática"),
        (LINGUA_PORTUGUESA, "Língua Portuguesa/Literatura"),
    ]

    registro = models.ForeignKey(
        RegistroAcademico,
        on_delete=models.CASCADE,
        related_name="notas",
    )
    componente = models.CharField(max_length=40, choices=COMPONENTES)
    valor = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["registro", "componente"],
                name="uniq_nota_registro_componente",
            )
        ]

    def __str__(self):
        return f"{self.get_componente_display()}: {self.valor}"
