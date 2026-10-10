from django.db import migrations, models
from django.db.models import Count, Q


def escolher_relacao_ativa(apps, schema_editor):
    Registro = apps.get_model("historico", "RegistroAcademico")
    Nota = apps.get_model("historico", "Nota")

    grupos = (
        Registro.objects
        .exclude(aluno_id__isnull=True)
        .exclude(serie__isnull=True)
        .values("aluno_id", "serie")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    for grupo in grupos.iterator():
        registros = list(
            Registro.objects.filter(
                aluno_id=grupo["aluno_id"],
                serie=grupo["serie"],
            ).order_by("ano", "id")
        )

        def pontuacao(registro):
            notas_preenchidas = (
                Nota.objects
                .filter(registro_id=registro.id)
                .exclude(valor__in=["", "-", "*"])
                .count()
            )
            campos_preenchidos = sum(
                bool(str(getattr(registro, campo, "") or "").strip())
                for campo in (
                    "turma",
                    "resultado",
                    "carga_horaria",
                    "frequencia",
                    "faltas",
                    "escola",
                )
            )
            return (
                1 if notas_preenchidas else 0,
                notas_preenchidas,
                campos_preenchidos,
                registro.ano or 0,
                registro.id,
            )

        escolhido = max(registros, key=pontuacao)
        Registro.objects.filter(
            aluno_id=grupo["aluno_id"],
            serie=grupo["serie"],
        ).update(ativo_no_historico=False)
        Registro.objects.filter(pk=escolhido.pk).update(
            ativo_no_historico=True
        )


class Migration(migrations.Migration):
    dependencies = [
        ("historico", "0006_indices_registro_academico"),
    ]

    operations = [
        migrations.AddField(
            model_name="registroacademico",
            name="ativo_no_historico",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text=(
                    "Somente relações ativas entram no Histórico Escolar oficial. "
                    "Desativar não remove notas nem apaga o registro."
                ),
            ),
        ),
        migrations.RunPython(
            escolher_relacao_ativa,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="registroacademico",
            constraint=models.UniqueConstraint(
                fields=("aluno", "serie"),
                condition=Q(
                    ativo_no_historico=True,
                    aluno__isnull=False,
                    serie__isnull=False,
                ),
                name="uniq_registro_ativo_aluno_serie",
            ),
        ),
    ]
