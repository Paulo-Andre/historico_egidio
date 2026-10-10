from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

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
    change_list_template = "admin/historico/nota/change_list.html"

    def get_actions(self, request):
        # Excluir dezenas de milhares de notas pela ação padrão do Django
        # gera um POST enorme na confirmação e pode resultar em Bad Request 400.
        # A limpeza total usa uma rota própria, com confirmação única.
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "limpar-todas/",
                self.admin_site.admin_view(self.limpar_todas_as_notas),
                name="historico_nota_limpar_todas",
            ),
        ]
        return custom + urls

    def limpar_todas_as_notas(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

        total = Nota.objects.count()
        confirmacao = ""

        if request.method == "POST":
            confirmacao = (request.POST.get("confirmacao") or "").strip()
            if confirmacao == "APAGAR TODAS AS NOTAS":
                with transaction.atomic():
                    apagadas, _ = Nota.objects.all().delete()

                self.message_user(
                    request,
                    f"{apagadas} nota(s) foram removidas. "
                    "Os alunos e registros acadêmicos foram preservados.",
                    level=messages.SUCCESS,
                )
                return redirect(reverse("admin:historico_nota_changelist"))

            messages.error(
                request,
                'Digite exatamente "APAGAR TODAS AS NOTAS" para confirmar.',
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Limpar todas as notas",
            "opts": self.model._meta,
            "total_notas": total,
            "confirmacao": confirmacao,
            "changelist_url": reverse("admin:historico_nota_changelist"),
        }
        return TemplateResponse(
            request,
            "admin/historico/nota/limpar_todas.html",
            context,
        )
