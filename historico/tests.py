import json
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .importacao_notas_pdf import aplicar_notas_pdf
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



class ImportacaoListaAlunosTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="importador",
            password="senha-teste",
            is_staff=True,
        )
        self.client.login(username="importador", password="senha-teste")

    def _arquivo_xlsx(self, linhas):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "historico"
        for linha in linhas:
            ws.append(linha)

        buffer = BytesIO()
        wb.save(buffer)
        wb.close()
        return SimpleUploadedFile(
            "lista.xlsx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )

    def test_importacao_atualiza_cria_e_preserva_quem_nao_esta_na_lista(self):
        existente = Aluno.objects.create(
            codigo=100,
            nome="ALUNO EXISTENTE",
            nascimento="10/02/2015",
            naturalidade="DADO ANTIGO",
            nacionalidade="BRASILEIRA",
            sexo="MASCULINO",
        )
        fora_da_lista = Aluno.objects.create(
            codigo=101,
            nome="ALUNO QUE DEVE PERMANECER",
            nascimento="03/03/2015",
        )

        arquivo = self._arquivo_xlsx(
            [
                ["E. M. EGÍDIO CORDEIRO AQUINO"],
                ["historico"],
                [
                    "NOME",
                    "PAI",
                    "MÃE",
                    "NASCIMENTO",
                    "NATURALIDADE",
                    "NACIONALIDAD",
                    "SEXO",
                ],
                [
                    "ALUNO EXISTENTE",
                    "PAI ATUALIZADO",
                    "MÃE ATUALIZADA",
                    "10/02/2015",
                    "MONTES CLAROS",
                    "BRASILEIRA",
                    "MASCULINO",
                ],
                [
                    "ALUNO NOVO",
                    "PAI NOVO",
                    "MÃE NOVA",
                    "05/06/2016",
                    "MONTES CLAROS",
                    "BRASILEIRA",
                    "FEMININO",
                ],
            ]
        )

        previa = self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "previsualizar", "arquivo": arquivo},
        )

        self.assertEqual(previa.status_code, 200)
        self.assertContains(previa, "1")
        self.assertContains(previa, "ALUNO EXISTENTE")
        self.assertEqual(Aluno.objects.count(), 2)

        aplicado = self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "aplicar"},
        )

        self.assertEqual(aplicado.status_code, 200)
        existente.refresh_from_db()
        fora_da_lista.refresh_from_db()

        self.assertEqual(existente.naturalidade, "MONTES CLAROS")
        self.assertEqual(existente.pai, "PAI ATUALIZADO")
        self.assertTrue(
            Aluno.objects.filter(
                nome="ALUNO NOVO",
                nascimento="05/06/2016",
            ).exists()
        )
        self.assertTrue(
            Aluno.objects.filter(pk=fora_da_lista.pk).exists()
        )
        self.assertEqual(Aluno.objects.count(), 3)

    def test_celula_vazia_da_lista_nao_apaga_dado_existente(self):
        aluno = Aluno.objects.create(
            codigo=200,
            nome="ALUNO PRESERVADO",
            nascimento="01/01/2014",
            naturalidade="MONTES CLAROS",
            mae="MÃE JÁ CADASTRADA",
        )

        arquivo = self._arquivo_xlsx(
            [
                ["NOME", "MÃE", "NASCIMENTO", "NATURALIDADE", "SEXO"],
                [
                    "ALUNO PRESERVADO",
                    "",
                    "01/01/2014",
                    "",
                    "MASCULINO",
                ],
            ]
        )

        self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "previsualizar", "arquivo": arquivo},
        )
        self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "aplicar"},
        )

        aluno.refresh_from_db()
        self.assertEqual(aluno.mae, "MÃE JÁ CADASTRADA")
        self.assertEqual(aluno.naturalidade, "MONTES CLAROS")
        self.assertEqual(aluno.sexo, "MASCULINO")

    def test_duas_colunas_sem_titulo_entre_nome_e_nascimento_viram_filiacao(self):
        arquivo = self._arquivo_xlsx(
            [
                ["NOME", "", "", "NASCIMENTO", "NATURALIDADE", "SEXO"],
                [
                    "ALUNO FILIAÇÃO",
                    "PAI SEM CABEÇALHO",
                    "MÃE SEM CABEÇALHO",
                    "07/08/2015",
                    "MONTES CLAROS",
                    "FEMININO",
                ],
            ]
        )

        self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "previsualizar", "arquivo": arquivo},
        )
        self.client.post(
            reverse("historico:importar_lista_alunos"),
            data={"acao": "aplicar"},
        )

        aluno = Aluno.objects.get(nome="ALUNO FILIAÇÃO")
        self.assertEqual(aluno.pai, "PAI SEM CABEÇALHO")
        self.assertEqual(aluno.mae, "MÃE SEM CABEÇALHO")



class ImportacaoNotasPdfPreservacaoHistoricoTests(TestCase):
    def test_nota_de_um_ano_nao_substitui_nota_de_outro_ano(self):
        aluno = Aluno.objects.create(
            codigo=500,
            nome="ALUNO COM CINCO ANOS",
            curso="ENSINO FUNDAMENTAL",
        )
        primeiro = RegistroAcademico.objects.create(
            aluno=aluno,
            nome_original=aluno.nome,
            ano=2022,
            serie=1,
            turma="A",
        )
        segundo = RegistroAcademico.objects.create(
            aluno=aluno,
            nome_original=aluno.nome,
            ano=2023,
            serie=2,
            turma="A",
        )
        Nota.objects.create(
            registro=primeiro,
            componente=Nota.MATEMATICA,
            valor="81",
        )
        Nota.objects.create(
            registro=segundo,
            componente=Nota.MATEMATICA,
            valor="72",
        )

        aplicar_notas_pdf(
            {
                "itens": [
                    {
                        "nome": "ALUNO COM CINCO ANOS",
                        "ano": 2023,
                        "serie": 2,
                        "turma": "A",
                        "notas": {Nota.MATEMATICA: "95"},
                    }
                ]
            }
        )

        nota_2022 = Nota.objects.get(
            registro=primeiro,
            componente=Nota.MATEMATICA,
        )
        nota_2023 = Nota.objects.get(
            registro=segundo,
            componente=Nota.MATEMATICA,
        )

        self.assertEqual(nota_2022.valor, "81")
        self.assertEqual(nota_2023.valor, "72")
        self.assertEqual(
            Nota.objects.filter(
                registro__aluno=aluno,
                componente=Nota.MATEMATICA,
            ).count(),
            2,
        )

    def test_importacao_so_adiciona_nota_que_ainda_nao_existe(self):
        aluno = Aluno.objects.create(
            codigo=502,
            nome="ALUNO SEM SOBRESCRITA",
            curso="ENSINO FUNDAMENTAL",
        )
        registro = RegistroAcademico.objects.create(
            aluno=aluno,
            nome_original=aluno.nome,
            ano=2024,
            serie=4,
            turma="TURMA ANTIGA",
        )
        Nota.objects.create(
            registro=registro,
            componente=Nota.MATEMATICA,
            valor="70",
        )

        resultado = aplicar_notas_pdf(
            {
                "itens": [
                    {
                        "nome": "ALUNO SEM SOBRESCRITA",
                        "ano": 2024,
                        "serie": 4,
                        "turma": "TURMA NOVA",
                        "notas": {
                            Nota.MATEMATICA: "99",
                            Nota.HISTORIA: "88",
                        },
                    }
                ]
            }
        )

        registro.refresh_from_db()
        matematica = Nota.objects.get(
            registro=registro,
            componente=Nota.MATEMATICA,
        )
        historia = Nota.objects.get(
            registro=registro,
            componente=Nota.HISTORIA,
        )

        self.assertEqual(matematica.valor, "70")
        self.assertEqual(historia.valor, "88")
        self.assertEqual(registro.turma, "TURMA ANTIGA")
        self.assertEqual(resultado["notas_adicionadas"], 1)
        self.assertEqual(resultado["notas_preservadas"], 1)

    def test_mesma_disciplina_pode_existir_em_cinco_anos(self):
        aluno = Aluno.objects.create(
            codigo=501,
            nome="ALUNO HISTORICO COMPLETO",
            curso="ENSINO FUNDAMENTAL",
        )

        for serie, ano, valor in (
            (1, 2021, "70"),
            (2, 2022, "75"),
            (3, 2023, "80"),
            (4, 2024, "85"),
            (5, 2025, "90"),
        ):
            registro = RegistroAcademico.objects.create(
                aluno=aluno,
                nome_original=aluno.nome,
                ano=ano,
                serie=serie,
            )
            Nota.objects.create(
                registro=registro,
                componente=Nota.LINGUA_PORTUGUESA,
                valor=valor,
            )

        self.assertEqual(
            Nota.objects.filter(
                registro__aluno=aluno,
                componente=Nota.LINGUA_PORTUGUESA,
            ).count(),
            5,
        )



class LimpezaTotalNotasAdminTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="admin-limpeza",
            password="senha-teste",
            email="admin@example.com",
        )
        self.staff = get_user_model().objects.create_user(
            username="staff-limpeza",
            password="senha-teste",
            is_staff=True,
        )
        self.aluno = Aluno.objects.create(
            codigo=900,
            nome="ALUNO PARA LIMPEZA",
        )
        self.registro = RegistroAcademico.objects.create(
            aluno=self.aluno,
            nome_original=self.aluno.nome,
            ano=2025,
            serie=5,
        )
        Nota.objects.create(
            registro=self.registro,
            componente=Nota.MATEMATICA,
            valor="80",
        )
        Nota.objects.create(
            registro=self.registro,
            componente=Nota.LINGUA_PORTUGUESA,
            valor="90",
        )

    def test_superusuario_limpa_todas_as_notas_sem_apagar_aluno_ou_registro(self):
        self.client.login(username="admin-limpeza", password="senha-teste")

        response = self.client.post(
            reverse("admin:historico_nota_limpar_todas"),
            data={"confirmacao": "APAGAR TODAS AS NOTAS"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Nota.objects.count(), 0)
        self.assertTrue(Aluno.objects.filter(pk=self.aluno.pk).exists())
        self.assertTrue(
            RegistroAcademico.objects.filter(pk=self.registro.pk).exists()
        )
        self.assertContains(response, "Os alunos e registros acadêmicos foram preservados")

    def test_confirmacao_incorreta_nao_apaga_notas(self):
        self.client.login(username="admin-limpeza", password="senha-teste")

        response = self.client.post(
            reverse("admin:historico_nota_limpar_todas"),
            data={"confirmacao": "apagar"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Nota.objects.count(), 2)
        self.assertContains(response, "Digite exatamente")

    def test_staff_sem_superuser_nao_pode_limpar_todas_as_notas(self):
        self.client.login(username="staff-limpeza", password="senha-teste")

        response = self.client.get(
            reverse("admin:historico_nota_limpar_todas")
        )

        self.assertEqual(response.status_code, 403)
