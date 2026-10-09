import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Aluno, Nota, RegistroAcademico
from .services import historico_documento, historico_do_aluno


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
    return render(
        request,
        "historico/historico.html",
        {
            "aluno": aluno,
            "documento": historico_documento(aluno),
            "can_edit": bool(
                request.user.is_authenticated and request.user.is_staff
            ),
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
        "ultima_serie_concluida",
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

    return JsonResponse({"ok": True})
