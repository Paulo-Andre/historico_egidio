from django.urls import path

from . import views


app_name = "historico"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("aluno/novo/", views.gerenciar_aluno, name="aluno_novo"),
    path(
        "dados-extras/",
        views.dados_extras_anuais,
        name="dados_extras_anuais",
    ),
    path(
        "alunos/importar/",
        views.importar_lista_alunos,
        name="importar_lista_alunos",
    ),
    path(
        "notas/importar-pdf/",
        views.importar_notas_pdf,
        name="importar_notas_pdf",
    ),
    path(
        "aluno/<int:codigo>/editar/",
        views.gerenciar_aluno,
        name="aluno_editar",
    ),
    path("aluno/<int:codigo>/", views.aluno_detalhe, name="aluno"),
    path(
        "aluno/<int:codigo>/historico/",
        views.historico_impressao,
        name="historico",
    ),
    path(
        "aluno/<int:codigo>/historico/salvar/",
        views.salvar_historico,
        name="salvar_historico",
    ),
    path(
        "aluno/<int:codigo>/historico/emitir/",
        views.emitir_historico,
        name="emitir_historico",
    ),
    path(
        "validar/<uuid:documento_id>/",
        views.validar_documento_publico,
        name="validar_documento",
    ),
]
