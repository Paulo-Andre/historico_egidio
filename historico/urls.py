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
]
