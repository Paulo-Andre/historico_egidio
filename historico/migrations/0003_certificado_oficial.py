from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("historico", "0002_editor_documento"),
    ]

    operations = [
        migrations.AddField(
            model_name="aluno",
            name="identidade",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="aluno",
            name="orgao_expedidor",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="aluno",
            name="data_conclusao",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="aluno",
            name="ultima_serie_concluida",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="aluno",
            name="data_expedicao",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="aluno",
            name="observacao_historico",
            field=models.TextField(blank=True),
        ),
    ]
}
