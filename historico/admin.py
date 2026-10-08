from django.contrib import admin

from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico


class NotaInline(admin.TabularInline):
    model = Nota
    extra = 0


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "matricula",
        "nome",
        "cpf",
        "nascimento",
        "sexo",
        "ativo",
    )
    search_fields = ("nome", "codigo", "matricula", "cpf", "mae", "pai")
    list_filter = ("ativo", "sexo")


@admin.register(ConfiguracaoAno)
class ConfiguracaoAnoAdmin(admin.ModelAdmin):
    list_display = (
        "ano",
        "ch_anual",
        "dias_letivos",
        "media_minima",
        "escola",
    )
    ordering = ("ano",)


@admin.register(RegistroAcademico)
class RegistroAcademicoAdmin(admin.ModelAdmin):
    list_display = (
        "ano",
        "serie",
        "turma",
        "aluno",
        "carga_horaria",
        "frequencia",
        "faltas",
        "resultado",
    )
    list_filter = ("ano", "serie", "resultado")
    search_fields = ("aluno__nome", "nome_original", "turma")
    autocomplete_fields = ("aluno",)
    inlines = [NotaInline]


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ("registro", "componente", "valor")
    list_filter = ("componente",)
    search_fields = ("registro__aluno__nome", "registro__nome_original")
