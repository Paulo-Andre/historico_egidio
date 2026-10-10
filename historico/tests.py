import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico
from .services import historico_oficial_do_aluno


class HistoricoServiceTests(TestCase):
    def test_modelo_oficial_monta_cinco_anos_e_detecta_2020(self):
        aluno = Aluno.objects.create(codigo=1, nome="Aluno Teste")
        ConfiguracaoAno.objects.create(
            ano=2020,
            ch_anual="800",
            dias_letivos="200",
            media_minima="60",
        )
        registro = RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2020,
            serie=3,
            carga_horaria="800",
            resultado="APROVADO",
        )
        Nota.objects.create(
            registro=registro,
            componente=Nota.MATEMATICA,
            valor="80",
        )

        documento = historico_oficial_do_aluno(aluno)

        self.assertEqual(len(documento["anos"]), 5)
        self.assertEqual(documento["anos"][0]["ano"], "")
        self.assertEqual(documento["anos"][0]["carga_horaria"], "")
        self.assertEqual(documento["anos"][0]["situacao"], "")
        self.assertTrue(documento["anos"][0]["vazio"])
        self.assertEqual(documento["anos"][2]["ano"], 2020)
        self.assertTrue(documento["tem_2020"])


class HistoricoEditorJsonTests(TestCase):
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

    def test_operador_salva_certificado_registro_e_nota(self):
        url = reverse("historico:salvar_historico", args=[self.aluno.codigo])
        payload = {
            "aluno": {
                "nome": "Nome Atualizado",
                "matricula": "2025-001",
                "identidade": "MG-22.487.354",
                "orgao_expedidor": "POLÍCIA CIVIL/MG",
                "data_conclusao": "15/12/2025",
                "data_expedicao": "12/06/2026",
                "observacao_historico": "OBSERVAÇÃO TESTE",
            },
            "registros": [
                {
                    "id": self.registro.id,
                    "campos": {
                        "ano": "2025",
                        "resultado": "REPROVADO",
                        "frequencia": "74%",
                        "carga_horaria": "800",
                    },
                    "notas": {
                        "matematica": {
                            "valor": "55",
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
        self.assertEqual(self.registro.resultado, "REPROVADO")
        self.assertEqual(self.registro.frequencia, "74%")
        self.assertEqual(nota.valor, "55")


class AlunoCadastroEdicaoTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="secretaria",
            password="senha-teste",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            username="usuario",
            password="senha-teste",
            is_staff=False,
        )

    def test_operador_acessa_pagina_de_novo_aluno(self):
        self.client.login(username="secretaria", password="senha-teste")
        response = self.client.get(reverse("historico:aluno_novo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastrar novo aluno")
        self.assertContains(response, "Vida escolar e notas")

    def test_usuario_sem_permissao_nao_edita(self):
        aluno = Aluno.objects.create(codigo=20, nome="Aluno Protegido")
        self.client.login(username="usuario", password="senha-teste")

        response = self.client.get(
            reverse("historico:aluno_editar", args=[aluno.codigo])
        )

        self.assertEqual(response.status_code, 403)

    def test_cadastra_aluno_registro_e_notas_na_mesma_tela(self):
        self.client.login(username="secretaria", password="senha-teste")
        response = self.client.post(
            reverse("historico:aluno_novo"),
            data={
                "codigo": "30",
                "nome": "Maria da Silva",
                "matricula": "2026-030",
                "cpf": "",
                "curso": "ENSINO FUNDAMENTAL",
                "identidade": "MG-123",
                "orgao_expedidor": "PC/MG",
                "data_conclusao": "",
                "data_expedicao": "",
                "uf": "MG",
                "pai": "Pai da Aluna",
                "mae": "Mãe da Aluna",
                "nascimento": "10/05/2015",
                "naturalidade": "MONTES CLAROS",
                "nacionalidade": "BRASILEIRA",
                "sexo": "FEMININO",
                "observacao_historico": "",
                "ativo": "on",
                "serie_1_ano": "2022",
                "serie_1_turma": "A",
                "serie_1_faltas": "8",
                "serie_1_frequencia": "95%",
                "serie_1_carga_horaria": "800",
                "serie_1_resultado": "APROVADO",
                "serie_1_escola": "E. M. EGÍDIO CORDEIRO AQUINO",
                "serie_1_municipio": "MONTES CLAROS",
                "serie_1_uf": "MG",
                "serie_1_observacao": "",
                "serie_1_nota_matematica": "92",
                "serie_1_nota_lingua_portuguesa": "88",
            },
        )

        self.assertEqual(response.status_code, 302)
        aluno = Aluno.objects.get(codigo=30)
        registro = RegistroAcademico.objects.get(aluno=aluno, serie=1)
        matematica = Nota.objects.get(
            registro=registro,
            componente=Nota.MATEMATICA,
        )
        portugues = Nota.objects.get(
            registro=registro,
            componente=Nota.LINGUA_PORTUGUESA,
        )

        self.assertEqual(aluno.nome, "Maria da Silva")
        self.assertEqual(registro.ano, 2022)
        self.assertEqual(registro.turma, "A")
        self.assertEqual(matematica.valor, "92")
        self.assertEqual(portugues.valor, "88")

    def test_edita_dados_e_notas_do_aluno(self):
        aluno = Aluno.objects.create(
            codigo=40,
            nome="João Antigo",
            curso="ENSINO FUNDAMENTAL",
        )
        registro = RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2023,
            serie=2,
            resultado="APROVADO",
        )
        Nota.objects.create(
            registro=registro,
            componente=Nota.CIENCIAS,
            valor="70",
        )

        self.client.login(username="secretaria", password="senha-teste")
        response = self.client.post(
            reverse("historico:aluno_editar", args=[aluno.codigo]),
            data={
                "codigo": "40",
                "nome": "João Atualizado",
                "matricula": "",
                "cpf": "",
                "curso": "ENSINO FUNDAMENTAL",
                "identidade": "",
                "orgao_expedidor": "",
                "data_conclusao": "",
                "data_expedicao": "",
                "uf": "MG",
                "pai": "",
                "mae": "",
                "nascimento": "",
                "naturalidade": "MONTES CLAROS",
                "nacionalidade": "BRASILEIRA",
                "sexo": "MASCULINO",
                "observacao_historico": "",
                "ativo": "on",
                "serie_2_ano": "2023",
                "serie_2_turma": "B",
                "serie_2_faltas": "4",
                "serie_2_frequencia": "98%",
                "serie_2_carga_horaria": "833:20",
                "serie_2_resultado": "APROVADO",
                "serie_2_escola": "E. M. EGÍDIO CORDEIRO AQUINO",
                "serie_2_municipio": "MONTES CLAROS",
                "serie_2_uf": "MG",
                "serie_2_observacao": "",
                "serie_2_nota_ciencias": "95",
            },
        )

        self.assertEqual(response.status_code, 302)
        aluno.refresh_from_db()
        registro.refresh_from_db()
        nota = Nota.objects.get(
            registro=registro,
            componente=Nota.CIENCIAS,
        )

        self.assertEqual(aluno.nome, "João Atualizado")
        self.assertEqual(registro.turma, "B")
        self.assertEqual(registro.frequencia, "98%")
        self.assertEqual(nota.valor, "95")



class DadosExtrasAnuaisTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="configurador",
            password="senha-teste",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            username="leitor",
            password="senha-teste",
            is_staff=False,
        )

    def test_operador_acessa_dados_extras(self):
        self.client.login(username="configurador", password="senha-teste")
        response = self.client.get(reverse("historico:dados_extras_anuais"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dados extras por ano letivo")
        self.assertContains(response, "Mínimo para aprovação")
        self.assertContains(response, "Carga horária anual")
        self.assertContains(response, "Dias letivos")
        self.assertContains(response, "Data de conclusão")

    def test_usuario_sem_permissao_nao_altera_configuracao_anual(self):
        self.client.login(username="leitor", password="senha-teste")
        response = self.client.get(reverse("historico:dados_extras_anuais"))

        self.assertEqual(response.status_code, 403)

    def test_cadastra_configuracao_anual(self):
        self.client.login(username="configurador", password="senha-teste")
        response = self.client.post(
            reverse("historico:dados_extras_anuais"),
            data={
                "anos-TOTAL_FORMS": "1",
                "anos-INITIAL_FORMS": "0",
                "anos-MIN_NUM_FORMS": "0",
                "anos-MAX_NUM_FORMS": "1000",
                "anos-0-ano": "2026",
                "anos-0-media_minima": "60",
                "anos-0-ch_anual": "833:20",
                "anos-0-dias_letivos": "200",
                "anos-0-ch_ingles": "66:40",
                "anos-0-ch_sem_ingles": "766:40",
                "anos-0-data_conclusao": "18/12/2026",
                "anos-0-escola": "E. M. EGÍDIO CORDEIRO AQUINO",
                "anos-0-municipio": "MONTES CLAROS",
                "anos-0-uf": "MG",
            },
        )

        self.assertEqual(response.status_code, 302)
        config = ConfiguracaoAno.objects.get(ano=2026)
        self.assertEqual(config.media_minima, "60")
        self.assertEqual(config.ch_anual, "833:20")
        self.assertEqual(config.dias_letivos, "200")
        self.assertEqual(config.data_conclusao, "18/12/2026")

    def test_data_conclusao_anual_e_usada_como_padrao_do_certificado(self):
        aluno = Aluno.objects.create(codigo=77, nome="Aluno Concluinte")
        ConfiguracaoAno.objects.create(
            ano=2026,
            media_minima="60",
            ch_anual="833:20",
            dias_letivos="200",
            data_conclusao="18/12/2026",
        )
        RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2026,
            serie=5,
            resultado="APROVADO",
        )

        documento = historico_oficial_do_aluno(aluno)

        self.assertEqual(documento["data_conclusao"], "18/12/2026")



class CertificadoUltimoAnoTests(TestCase):
    def test_conclusao_e_serie_usam_ultimo_ano_cursado(self):
        aluno = Aluno.objects.create(codigo=88, nome="Aluno com transferência")
        ConfiguracaoAno.objects.create(
            ano=2024,
            media_minima="60",
            ch_anual="800",
            dias_letivos="200",
            data_conclusao="17/12/2024",
        )
        RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2022,
            serie=2,
            resultado="APROVADO",
        )
        RegistroAcademico.objects.create(
            aluno=aluno,
            ano=2024,
            serie=4,
            resultado="APROVADO",
        )

        documento = historico_oficial_do_aluno(aluno)

        self.assertEqual(documento["ultima_serie"], 4)
        self.assertEqual(documento["data_conclusao"], "17/12/2024")
