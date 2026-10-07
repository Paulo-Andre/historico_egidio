from django.db import models

class Aluno(models.Model):
    codigo=models.PositiveIntegerField(unique=True, db_index=True)
    nome=models.CharField(max_length=255, db_index=True)
    uf=models.CharField(max_length=10, blank=True)
    pai=models.CharField(max_length=255, blank=True)
    mae=models.CharField(max_length=255, blank=True)
    nascimento=models.CharField(max_length=30, blank=True)
    naturalidade=models.CharField(max_length=120, blank=True)
    nacionalidade=models.CharField(max_length=120, blank=True)
    sexo=models.CharField(max_length=30, blank=True)
    def __str__(self): return f'{self.codigo} - {self.nome}'

class ParametroAno(models.Model):
    ano=models.PositiveIntegerField(unique=True)
    ch_ingles=models.CharField(max_length=30, blank=True)
    ch_anual=models.CharField(max_length=30, blank=True)
    dias_letivos=models.CharField(max_length=30, blank=True)
    ch_sem_ingles=models.CharField(max_length=30, blank=True)
    media=models.CharField(max_length=30, blank=True)
    escola=models.CharField(max_length=255, blank=True)
    def __str__(self): return str(self.ano)

class AbaExcel(models.Model):
    nome=models.CharField(max_length=120, unique=True)
    ordem=models.PositiveIntegerField(default=0)
    visivel=models.BooleanField(default=True)
    max_linha=models.PositiveIntegerField(default=1)
    max_coluna=models.PositiveIntegerField(default=1)
    def __str__(self): return self.nome

class CelulaExcel(models.Model):
    aba=models.ForeignKey(AbaExcel,on_delete=models.CASCADE,related_name='celulas')
    referencia=models.CharField(max_length=20)
    linha=models.PositiveIntegerField()
    coluna=models.PositiveIntegerField()
    valor=models.TextField(blank=True)
    formula=models.TextField(blank=True)
    numero_formato=models.CharField(max_length=120,blank=True)
    estilo_id=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['aba','referencia'],name='uniq_aba_celula')]
        indexes=[models.Index(fields=['aba','linha','coluna'])]

class RegistroAta(models.Model):
    ano=models.PositiveIntegerField(db_index=True)
    linha=models.PositiveIntegerField()
    dados=models.JSONField(default=dict)
    texto_busca=models.TextField(blank=True, db_index=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['ano','linha'],name='uniq_ata_linha')]
        ordering=['ano','linha']
