import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico
from .services import historico_documento, historico_do_aluno


class HistoricoServiceTests(TestCase):
    def test_carga_horaria_do_registro_tem_precedencia_sobre_configuracao(self):
        aluno = Aluno.objects.create(codigo=1, nome="Aluno Teste")
        ConfiguracaoAno.objects.create(
            ano=2025,
            ch_anual="800",
            media_minima="60",
            dias_letivos="200",
        )
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
        self.assertEqual(dados["carga_horaria"], "820:00")
        self.assertEqual(dados["media_minima_num"], "60")

    def test_modelo_oficial_sempre_monta_primeiro_ao_quinto_ano(self):
        aluno = Aluno.objects.create(codigo=2, nome="Aluna Modelo")
        ConfiguracaoAno.objects.create(
            ano=2025,
            ch_anual="833.333333",
            dias_letivos="200",
            media_minima="0.6",
        )
        RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2025,
            serie=5,
            resultado="APROVADO",
        )

        oficial = historico_oficial_do_aluno(aluno)
        self.assertEqual(len(oficial["anos"]), 5)
        self.assertEqual(oficial["anos"][0]["ano"], "*")
        self.assertEqual(oficial["anos"][4]["ano"], 2025)
        self.assertEqual(oficial["anos"][4]["carga_horaria"], "833:20")
        self.assertEqual(oficial["anos"][4]["media_minima"], "60%")

    def test_documento_tem_cinco_anos_e_preserva_lacuna_com_asterisco(self):
        aluno = Aluno.objects.create(
            codigo=2,
            nome="Aluna Teste",
            sexo="FEMININO",
        )
        for serie, ano in [(1, 2022), (3, 2023), (4, 2024), (5, 2025)]:
            ConfiguracaoAno.objects.get_or_create(
                ano=ano,
                defaults={
                    "ch_anual": "800",
                    "media_minima": "60",
                    "dias_letivos": "200",
                },
            )
            RegistroAcademico.objects.create(
                aluno=aluno,
                ano=ano,
                serie=serie,
                carga_horaria="800",
                resultado="APROVADO",
                escola="E. M. EGÍDIO CORDEIRO AQUINO",
                municipio="MONTES CLAROS",
            )

        documento = historico_documento(aluno)

        self.assertEqual(len(documento["slots"]), 5)
        self.assertTrue(documento["slots"][1]["faltante"])
        self.assertEqual(documento["slots"][1]["ano"], "*")
        self.assertIn("LACUNA NO 2° ANO", documento["observacao"])
        self.assertIn("MATRICULAR-SE NO 6º ANO", documento["observacao"])


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

    def test_operador_salva_certificado_registro_nota_e_carga(self):
        url = reverse("historico:salvar_historico", args=[self.aluno.codigo])
        payload = {
            "aluno": {
                "nome": "Nome Atualizado",
                "matricula": "2025-001",
                "cpf": "123.456.789-00",
                "curso": "ENSINO FUNDAMENTAL",
                "identidade": "MG-22.487.354",
                "orgao_expedidor": "POLÍCIA CIVIL/MG",
                "data_conclusao": "15/12/2025",
                "data_expedicao": "12/06/2026",
                "observacao_historico": "REGULARIZAÇÃO DE VIDA ESCOLAR",
                "identidade": "MG-00.000.000",
                "orgao_expedidor": "POLÍCIA CIVIL/MG",
                "data_conclusao": "15/12/2025",
                "ultima_serie_concluida": "5º",
                "data_expedicao": "12/06/2026",
                "observacao_historico": "OBSERVAÇÃO TESTE",
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
                            "carga_horaria": "",
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
        self.assertEqual(self.aluno.identidade, "MG-22.487.354")
        self.assertEqual(self.aluno.data_conclusao, "15/12/2025")
        self.assertEqual(
            self.aluno.observacao_historico,
            "REGULARIZAÇÃO DE VIDA ESCOLAR",
        )
        self.assertEqual(self.aluno.identidade, "MG-00.000.000")
        self.assertEqual(self.aluno.orgao_expedidor, "POLÍCIA CIVIL/MG")
        self.assertEqual(self.aluno.data_conclusao, "15/12/2025")
        self.assertEqual(self.aluno.data_expedicao, "12/06/2026")
        self.assertEqual(self.aluno.observacao_historico, "OBSERVAÇÃO TESTE")
        self.assertEqual(self.registro.resultado, "REPROVADO")
        self.assertEqual(self.registro.frequencia, "74%")
        self.assertEqual(nota.valor, "5,5")
