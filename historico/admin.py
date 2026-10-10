from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .auditoria import registrar_auditoria
from .models import (
    Aluno,
    AuditoriaEvento,
    ConfiguracaoAno,
    DocumentoHistorico,
    MatrizComponente,
    MatrizCurricularVersao,
    Nota,
    RegistroAcademico,
)


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
        "matriz_curricular",
    )
    ordering = ("ano",)
    autocomplete_fields = ("matriz_curricular",)


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
        "matriz_curricular",
    )
    list_filter = ("ano", "serie", "resultado", "matriz_curricular")
    search_fields = ("aluno__nome", "nome_original", "turma")
    autocomplete_fields = ("aluno", "matriz_curricular")
    inlines = [NotaInline]


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ("registro", "componente", "valor", "carga_horaria")
    list_filter = ("componente",)
    search_fields = ("registro__aluno__nome", "registro__nome_original")
    change_list_template = "admin/historico/nota/change_list.html"

    def save_model(self, request, obj, form, change):
        anterior = None
        if change and obj.pk:
            anterior = Nota.objects.filter(pk=obj.pk).values(
                "valor", "carga_horaria", "componente", "registro_id"
            ).first()

        super().save_model(request, obj, form, change)

        registrar_auditoria(
            request,
            "NOTAS_ALTERADAS",
            entidade="Nota",
            objeto_id=obj.pk,
            objeto_repr=str(obj),
            detalhes={
                "registro_id": obj.registro_id,
                "componente": obj.componente,
                "operacao": "alteracao" if change else "criacao",
                "campos_alterados": sorted(form.changed_data),
                "valor_anterior": anterior.get("valor") if anterior else None,
                "valor_novo": obj.valor,
            },
        )

    def delete_model(self, request, obj):
        identificador = obj.pk
        descricao = str(obj)
        registro_id = obj.registro_id
        componente = obj.componente
        super().delete_model(request, obj)
        registrar_auditoria(
            request,
            "NOTAS_ALTERADAS",
            entidade="Nota",
            objeto_id=identificador,
            objeto_repr=descricao,
            detalhes={
                "registro_id": registro_id,
                "componente": componente,
                "operacao": "exclusao",
            },
        )

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



class MatrizComponenteInline(admin.TabularInline):
    model = MatrizComponente
    extra = 1


@admin.register(MatrizCurricularVersao)
class MatrizCurricularVersaoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "vigente_de", "vigente_ate", "ativa")
    list_filter = ("ativa", "vigente_de")
    search_fields = ("codigo", "nome", "descricao")
    inlines = [MatrizComponenteInline]


@admin.register(DocumentoHistorico)
class DocumentoHistoricoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "aluno",
        "emitido_em",
        "emitido_por",
        "hash_curto",
        "revogado",
    )
    list_filter = ("revogado", "emitido_em")
    search_fields = (
        "aluno__nome",
        "aluno__codigo",
        "hash_sha256",
        "id",
    )
    readonly_fields = (
        "id",
        "aluno",
        "emitido_por",
        "emitido_em",
        "hash_sha256",
        "assinatura_hmac",
        "snapshot",
    )

    @admin.display(description="SHA-256")
    def hash_curto(self, obj):
        return obj.hash_sha256[:16]


@admin.register(AuditoriaEvento)
class AuditoriaEventoAdmin(admin.ModelAdmin):
    list_display = (
        "criado_em",
        "usuario",
        "acao",
        "entidade",
        "objeto_id",
        "request_id",
    )
    list_filter = ("acao", "criado_em")
    search_fields = (
        "usuario__username",
        "entidade",
        "objeto_id",
        "objeto_repr",
        "request_id",
    )
    readonly_fields = (
        "criado_em",
        "usuario",
        "acao",
        "entidade",
        "objeto_id",
        "objeto_repr",
        "metodo",
        "caminho",
        "ip_hash",
        "user_agent",
        "request_id",
        "detalhes",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
