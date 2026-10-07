from django.contrib import admin
from .models import Aluno, ParametroAno, AbaExcel, CelulaExcel, RegistroAta
@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display=('codigo','nome','nascimento','sexo'); search_fields=('nome','codigo','mae','pai')
@admin.register(ParametroAno)
class ParametroAnoAdmin(admin.ModelAdmin): list_display=('ano','ch_anual','dias_letivos','media','escola')
@admin.register(AbaExcel)
class AbaExcelAdmin(admin.ModelAdmin): list_display=('ordem','nome','visivel','max_linha','max_coluna')
@admin.register(RegistroAta)
class RegistroAtaAdmin(admin.ModelAdmin): list_display=('ano','linha','texto_busca'); search_fields=('texto_busca',)
admin.site.register(CelulaExcel)
