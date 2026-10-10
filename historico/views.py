import json
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AlunoCadastroForm,
    ConfiguracaoAnoForm,
    ImportacaoAlunosForm,
    UF_CHOICES,
)
from .importacao_alunos import (
    ErroImportacao,
    analisar_lista,
    aplicar_lista,
    ler_lista_alunos,
)
from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico
from .services import historico_do_aluno, historico_oficial_do_aluno


COMPONENTES_EDITOR = [
    Nota.LINGUA_PORTUGUESA,
    Nota.ARTE,
    Nota.EDUCACAO_FISICA,
    Nota.LINGUA_INGLESA,
    Nota.MATEMATICA,
    Nota.CIENCIAS,
    Nota.GEOGRAFIA,
    Nota.HISTORIA,
    Nota.EDUCACAO_RELIGIOSA,
]
ROTULOS_COMPONENTES = dict(Nota.COMPONENTES)


RESULTADO_CHOICES = [
    ("", "Selecione..."),
    ("APROVADO", "Aprovado"),
    ("REPROVADO", "Reprovado"),
    ("APTO", "Apto"),
    ("APTA", "Apta"),
    ("EM CONTINUIDADE", "Em continuidade"),
    ("EM CURSO", "Em curso"),
]


def _opcoes_com_valor_atual(opcoes, atual):
    atuais = {valor for valor, _ in opcoes}
    if atual and atual not in atuais:
        return list(opcoes) + [(atual, atual)]
    return opcoes


def _registros_por_serie(aluno):
    if not aluno or not aluno.pk:
        return {}

    registros = {}
    queryset = (
        aluno.registros_academicos
        .prefetch_related("notas")
        .filter(serie__gte=1, serie__lte=5)
        .order_by("serie", "ano", "id")
    )
    for registro in queryset:
        registros[registro.serie] = registro
    return registros


def _anos_editor(aluno=None, post=None):
    registros = _registros_por_serie(aluno)
    anos = []

    for serie in range(1, 6):
        registro = registros.get(serie)
        notas_db = (
            {nota.componente: nota.valor for nota in registro.notas.all()}
            if registro
            else {}
        )
        prefixo = f"serie_{serie}_"

        def valor(campo, padrao=""):
            if post is not None:
                return str(post.get(prefixo + campo, padrao)).strip()
            if not registro:
                return padrao
            return str(getattr(registro, campo, "") or "").strip()

        notas = []
        for componente in COMPONENTES_EDITOR:
            nome_campo = f"nota_{componente}"
            nota_valor = (
                str(post.get(prefixo + nome_campo, "")).strip()
                if post is not None
                else str(notas_db.get(componente, "") or "").strip()
            )
            notas.append(
                {
                    "codigo": componente,
                    "rotulo": ROTULOS_COMPONENTES[componente],
                    "valor": nota_valor,
                }
            )

        anos.append(
            {
                "serie": serie,
                "registro": registro,
                "ano": valor("ano"),
                "turma": valor("turma"),
                "faltas": valor("faltas"),
                "frequencia": valor("frequencia"),
                "carga_horaria": valor("carga_horaria"),
                "resultado": valor("resultado"),
                "escola": valor("escola"),
                "municipio": valor("municipio", "MONTES CLAROS"),
                "uf": valor("uf", "MG"),
                "uf_opcoes": _opcoes_com_valor_atual(
                    UF_CHOICES,
                    valor("uf", "MG"),
                ),
                "resultado_opcoes": _opcoes_com_valor_atual(
                    RESULTADO_CHOICES,
                    valor("resultado"),
                ),
                "observacao": valor("observacao"),
                "notas": notas,
            }
        )

    return anos


def inicio(request):
    q = request.GET.get("q", "").strip()
    alunos = []
    if q:
        filtro = Q(nome__icontains=q)
        if q.isdigit():
            filtro |= Q(codigo=int(q))
        alunos = Aluno.objects.filter(filtro, ativo=True).order_by("nome")[:50]

    return render(
        request,
        "historico/inicio.html",
        {
            "q": q,
            "alunos": alunos,
            "total": Aluno.objects.count(),
            "registros": RegistroAcademico.objects.count(),
        },
    )


def _diretorio_importacoes():
    diretorio = Path(settings.DATA_DIR) / "importacoes_alunos"
    diretorio.mkdir(parents=True, exist_ok=True)

    limite = time.time() - (24 * 60 * 60)
    for arquivo in diretorio.glob("*"):
        try:
            if arquivo.is_file() and arquivo.stat().st_mtime < limite:
                arquivo.unlink()
        except OSError:
            pass

    return diretorio


def _arquivo_importacao_da_sessao(request):
    token = request.session.get("importacao_alunos_token")
    extensao = request.session.get("importacao_alunos_extensao")
    if not token or extensao not in {".xls", ".xlsx"}:
        return None

    try:
        uuid.UUID(token)
    except (ValueError, TypeError):
        return None

    caminho = _diretorio_importacoes() / f"{token}{extensao}"
    return caminho if caminho.exists() else None


def _limpar_importacao_da_sessao(request):
    caminho = _arquivo_importacao_da_sessao(request)
    if caminho:
        try:
            caminho.unlink()
        except OSError:
            pass

    for chave in (
        "importacao_alunos_token",
        "importacao_alunos_extensao",
        "importacao_alunos_nome",
    ):
        request.session.pop(chave, None)


@login_required
def importar_lista_alunos(request):
    if not request.user.is_staff:
        return HttpResponseForbidden(
            "Apenas operadores autorizados podem atualizar a lista de alunos."
        )

    formulario = ImportacaoAlunosForm()
    previa = None
    leitura = None
    erro = ""
    resultado = None

    if request.method == "POST":
        acao = request.POST.get("acao", "previsualizar")

        if acao == "cancelar":
            _limpar_importacao_da_sessao(request)
            return redirect("historico:importar_lista_alunos")

        if acao == "aplicar":
            caminho = _arquivo_importacao_da_sessao(request)
            if not caminho:
                erro = "A prévia expirou. Envie a lista novamente."
            else:
                try:
                    leitura = ler_lista_alunos(caminho)
                    resultado = aplicar_lista(leitura)
                    _limpar_importacao_da_sessao(request)
                except ErroImportacao as exc:
                    erro = str(exc)
                except Exception:
                    erro = (
                        "Não foi possível aplicar a atualização. "
                        "Nenhum aluno foi removido."
                    )
        else:
            formulario = ImportacaoAlunosForm(request.POST, request.FILES)
            if formulario.is_valid():
                arquivo = formulario.cleaned_data["arquivo"]
                extensao = Path(arquivo.name).suffix.lower()
                token = str(uuid.uuid4())
                caminho = _diretorio_importacoes() / f"{token}{extensao}"

                _limpar_importacao_da_sessao(request)

                with caminho.open("wb") as destino:
                    for bloco in arquivo.chunks():
                        destino.write(bloco)

                try:
                    leitura = ler_lista_alunos(caminho)
                    previa = analisar_lista(leitura)
                except ErroImportacao as exc:
                    erro = str(exc)
                    try:
                        caminho.unlink()
                    except OSError:
                        pass
                except Exception:
                    erro = (
                        "Não foi possível ler esta planilha. "
                        "Confirme se o arquivo é um XLS/XLSX válido."
                    )
                    try:
                        caminho.unlink()
                    except OSError:
                        pass
                else:
                    request.session["importacao_alunos_token"] = token
                    request.session["importacao_alunos_extensao"] = extensao
                    request.session["importacao_alunos_nome"] = arquivo.name

    if previa is None and resultado is None and not erro:
        caminho = _arquivo_importacao_da_sessao(request)
        if caminho:
            try:
                leitura = ler_lista_alunos(caminho)
                previa = analisar_lista(leitura)
            except Exception:
                _limpar_importacao_da_sessao(request)

    return render(
        request,
        "historico/importar_lista_alunos.html",
        {
            "formulario": formulario,
            "previa": previa,
            "leitura": leitura,
            "erro": erro,
            "resultado": resultado,
            "arquivo_nome": request.session.get("importacao_alunos_nome", ""),
        },
    )


@login_required
def dados_extras_anuais(request):
    if not request.user.is_staff:
        return HttpResponseForbidden(
            "Apenas operadores autorizados podem alterar os dados anuais."
        )

    FormSet = modelformset_factory(
        ConfiguracaoAno,
        form=ConfiguracaoAnoForm,
        extra=1,
        can_delete=False,
    )

    queryset = ConfiguracaoAno.objects.all().order_by("-ano")

    if request.method == "POST":
        formset = FormSet(request.POST, queryset=queryset, prefix="anos")
        if formset.is_valid():
            formset.save()
            return redirect(
                f'{reverse("historico:dados_extras_anuais")}?salvo=1'
            )
    else:
        formset = FormSet(queryset=queryset, prefix="anos")

    return render(
        request,
        "historico/dados_extras_anuais.html",
        {
            "formset": formset,
            "salvo": request.GET.get("salvo") == "1",
        },
    )


def aluno_detalhe(request, codigo):
    aluno = get_object_or_404(Aluno, codigo=codigo)
    return render(
        request,
        "historico/aluno.html",
        {
            "aluno": aluno,
            "historico": historico_do_aluno(aluno),
        },
    )


def historico_impressao(request, codigo):
    aluno = get_object_or_404(Aluno, codigo=codigo)
    oficial = historico_oficial_do_aluno(aluno)
    return render(
        request,
        "historico/historico.html",
        {
            "aluno": aluno,
            "historico": oficial["anos"],
            "tem_2020": oficial["tem_2020"],
            "nascimento": oficial["nascimento"],
            "data_conclusao": oficial["data_conclusao"],
            "ultima_serie": oficial["ultima_serie"],
            "data_expedicao": oficial["data_expedicao"],
            "observacao_historico": oficial["observacao_historico"],
            "can_edit": bool(
                request.user.is_authenticated and request.user.is_staff
            ),
        },
    )


@login_required
def gerenciar_aluno(request, codigo=None):
    if not request.user.is_staff:
        return HttpResponseForbidden(
            "Apenas operadores autorizados podem cadastrar ou editar alunos."
        )

    aluno = None
    if codigo is not None:
        aluno = get_object_or_404(Aluno, codigo=codigo)

    if request.method == "POST":
        form = AlunoCadastroForm(request.POST, instance=aluno)
        anos = _anos_editor(aluno, request.POST)
        erros_anos = []

        anos_validos = {}
        for item in anos:
            texto_ano = item["ano"]
            if not texto_ano:
                continue
            try:
                ano = int(texto_ano)
            except ValueError:
                erros_anos.append(
                    f'{item["serie"]}º ano: informe um ano letivo válido.'
                )
                continue
            if ano < 1000 or ano > 9999:
                erros_anos.append(
                    f'{item["serie"]}º ano: informe o ano com 4 dígitos.'
                )
                continue
            anos_validos[item["serie"]] = ano

        if form.is_valid() and not erros_anos:
            with transaction.atomic():
                aluno_salvo = form.save()
                registros = _registros_por_serie(aluno_salvo)

                for item in anos:
                    serie = item["serie"]
                    if serie not in anos_validos:
                        continue

                    registro = registros.get(serie)
                    novo_ano = anos_validos[serie]
                    if registro is None:
                        registro = RegistroAcademico(
                            aluno=aluno_salvo,
                            nome_original=aluno_salvo.nome,
                            serie=serie,
                            ano=novo_ano,
                        )
                    else:
                        if registro.ano != novo_ano:
                            # Ao alterar manualmente o ano, a referência de linha
                            # da importação deixa de representar a origem exata.
                            registro.linha_origem = None
                        registro.ano = novo_ano

                    for campo in (
                        "turma",
                        "faltas",
                        "frequencia",
                        "carga_horaria",
                        "resultado",
                        "escola",
                        "municipio",
                        "uf",
                        "observacao",
                    ):
                        setattr(
                            registro,
                            campo,
                            _texto_limitado(
                                RegistroAcademico,
                                campo,
                                item[campo],
                            ),
                        )

                    registro.nome_original = aluno_salvo.nome
                    registro.save()

                    for nota_item in item["notas"]:
                        Nota.objects.update_or_create(
                            registro=registro,
                            componente=nota_item["codigo"],
                            defaults={
                                "valor": _texto_limitado(
                                    Nota,
                                    "valor",
                                    nota_item["valor"],
                                )
                            },
                        )

            parametro = "criado=1" if aluno is None else "salvo=1"
            return redirect(
                f'{reverse("historico:aluno_editar", args=[aluno_salvo.codigo])}?{parametro}'
            )
    else:
        if aluno is None:
            ultimo_codigo = (
                Aluno.objects.order_by("-codigo")
                .values_list("codigo", flat=True)
                .first()
                or 0
            )
            form = AlunoCadastroForm(
                initial={
                    "codigo": ultimo_codigo + 1,
                    "curso": "ENSINO FUNDAMENTAL",
                    "ativo": True,
                }
            )
        else:
            form = AlunoCadastroForm(instance=aluno)
        anos = _anos_editor(aluno)
        erros_anos = []

    return render(
        request,
        "historico/aluno_form.html",
        {
            "aluno": aluno,
            "form": form,
            "anos": anos,
            "erros_anos": erros_anos,
            "salvo": request.GET.get("salvo") == "1",
            "criado": request.GET.get("criado") == "1",
        },
    )


def _texto_limitado(model, campo, valor):
    field = model._meta.get_field(campo)
    texto = "" if valor is None else str(valor).strip()
    if field.max_length:
        texto = texto[: field.max_length]
    return texto


@login_required
@require_POST
def salvar_historico(request, codigo):
    if not request.user.is_staff:
        return JsonResponse(
            {"ok": False, "erro": "Apenas operadores autorizados podem editar."},
            status=403,
        )

    aluno = get_object_or_404(Aluno, codigo=codigo)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)

    campos_aluno = {
        "nome",
        "matricula",
        "cpf",
        "curso",
        "identidade",
        "orgao_expedidor",
        "data_conclusao",
        "data_expedicao",
        "observacao_historico",
        "uf",
        "pai",
        "mae",
        "nascimento",
        "naturalidade",
        "nacionalidade",
        "sexo",
    }
    campos_registro = {
        "ano",
        "faltas",
        "frequencia",
        "carga_horaria",
        "resultado",
        "escola",
        "municipio",
        "uf",
        "observacao",
    }
    componentes_validos = {codigo for codigo, _ in Nota.COMPONENTES}

    novos_criados = 0

    with transaction.atomic():
        dados_aluno = payload.get("aluno") or {}
        alterados = []
        for campo in campos_aluno:
            if campo not in dados_aluno:
                continue
            setattr(
                aluno,
                campo,
                _texto_limitado(Aluno, campo, dados_aluno[campo]),
            )
            alterados.append(campo)

        if alterados:
            aluno.save(update_fields=alterados)

        for item in payload.get("registros") or []:
            try:
                registro_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue

            registro = (
                aluno.registros_academicos
                .select_for_update()
                .filter(pk=registro_id)
                .first()
            )
            if not registro:
                return JsonResponse(
                    {"ok": False, "erro": "Registro não pertence ao aluno."},
                    status=400,
                )

            dados_registro = item.get("campos") or {}
            campos_alterados = []
            for campo in campos_registro:
                if campo not in dados_registro:
                    continue

                if campo == "ano":
                    try:
                        valor_ano = int(str(dados_registro[campo]).strip())
                    except (TypeError, ValueError):
                        return JsonResponse(
                            {"ok": False, "erro": "Ano letivo inválido."},
                            status=400,
                        )
                    if valor_ano < 1000 or valor_ano > 9999:
                        return JsonResponse(
                            {"ok": False, "erro": "Informe o ano com 4 dígitos."},
                            status=400,
                        )
                    registro.ano = valor_ano
                else:
                    setattr(
                        registro,
                        campo,
                        _texto_limitado(
                            RegistroAcademico,
                            campo,
                            dados_registro[campo],
                        ),
                    )
                campos_alterados.append(campo)

            if campos_alterados:
                registro.save(update_fields=campos_alterados)

            notas = item.get("notas") or {}
            for componente, dados_nota in notas.items():
                if componente not in componentes_validos:
                    continue

                if isinstance(dados_nota, dict):
                    valor = dados_nota.get("valor", "")
                    carga_horaria = dados_nota.get("carga_horaria", "")
                else:
                    valor = dados_nota
                    carga_horaria = ""

                Nota.objects.update_or_create(
                    registro=registro,
                    componente=componente,
                    defaults={
                        "valor": _texto_limitado(Nota, "valor", valor),
                        "carga_horaria": _texto_limitado(
                            Nota,
                            "carga_horaria",
                            carga_horaria,
                        ),
                    },
                )

        for item in payload.get("novos_registros") or []:
            try:
                serie = int(item.get("serie"))
                ano = int(str(item.get("ano", "")).strip())
            except (TypeError, ValueError):
                continue

            if serie < 1 or serie > 5 or ano < 1000 or ano > 9999:
                continue

            ja_existe = (
                aluno.registros_academicos
                .select_for_update()
                .filter(serie=serie)
                .exists()
            )
            if ja_existe:
                continue

            RegistroAcademico.objects.create(
                aluno=aluno,
                nome_original=aluno.nome,
                ano=ano,
                serie=serie,
            )
            novos_criados += 1

    return JsonResponse({"ok": True, "recarregar": novos_criados > 0})
