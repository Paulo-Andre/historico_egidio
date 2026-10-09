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
        "identidade",
        "nascimento",
        "sexo",
        "ativo",
    )
    search_fields = (
        "nome",
        "codigo",
        "matricula",
        "cpf",
        "identidade",
        "mae",
        "pai",
    )
    list_filter = ("ativo", "sexo")
    fieldsets = (
        ("Identificação", {
            "fields": (
                "codigo",
                "nome",
                "matricula",
                "cpf",
                "identidade",
                "orgao_expedidor",
                "sexo",
                "nascimento",
                "naturalidade",
                "uf",
                "nacionalidade",
                "pai",
                "mae",
                "ativo",
            )
        }),
        ("Histórico / certificado", {
            "fields": (
                "curso",
                "data_conclusao",
                "ultima_serie_concluida",
                "data_expedicao",
                "observacao_historico",
            )
        }),
    )


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
    list_display = ("registro", "componente", "valor", "carga_horaria")
    list_filter = ("componente",)
    search_fields = ("registro__aluno__nome", "registro__nome_original")
