import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico
from .services import historico_do_aluno


class HistoricoServiceTests(TestCase):
    def test_carga_horaria_do_registro_tem_precedencia_sobre_configuracao(self):
        aluno = Aluno.objects.create(codigo=1, nome="Aluno Teste")
        ConfiguracaoAno.objects.create(ano=2025, ch_anual="800", media_minima="60")
        registro = RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2025,
            serie=5,
            carga_horaria="820",
            resultado="APROVADO",
        )
        Nota.objects.create(
            registro=registro,
            componente=Nota.MATEMATICA,
            valor="80",
        )

        dados = historico_do_aluno(aluno)[0]
        self.assertEqual(dados["carga_horaria"], "820")
        self.assertEqual(dados["media_minima_num"], "60")


class HistoricoEditorTests(TestCase):
    def setUp(self):
        self.aluno = Aluno.objects.create(codigo=10, nome="Nome Antigo")
        self.registro = RegistroAcademico.objects.create(
            aluno=self.aluno,
            ano=2025,
            serie=5,
            resultado="APROVADO",
        )
        self.user = get_user_model().objects.create_user(
            username="operador",
            password="senha-forte-teste",
            is_staff=True,
        )
        self.client.login(username="operador", password="senha-forte-teste")

    def test_operador_salva_aluno_registro_nota_e_carga(self):
        url = reverse("historico:salvar_historico", args=[self.aluno.codigo])
        payload = {
            "aluno": {
                "nome": "Nome Atualizado",
                "matricula": "2025-001",
                "cpf": "123.456.789-00",
                "curso": "ENSINO FUNDAMENTAL",
            },
            "registros": [
                {
                    "id": self.registro.id,
                    "campos": {
                        "resultado": "REPROVADO",
                        "frequencia": "74%",
                        "carga_horaria": "800",
                    },
                    "notas": {
                        "matematica": {
                            "valor": "5,5",
                            "carga_horaria": "160",
                        }
                    },
                }
            ],
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.aluno.refresh_from_db()
        self.registro.refresh_from_db()
        nota = Nota.objects.get(
            registro=self.registro,
            componente=Nota.MATEMATICA,
        )

        self.assertEqual(self.aluno.nome, "Nome Atualizado")
        self.assertEqual(self.registro.resultado, "REPROVADO")
        self.assertEqual(self.registro.frequencia, "74%")
        self.assertEqual(nota.valor, "5,5")
        self.assertEqual(nota.carga_horaria, "160")
