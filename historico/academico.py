from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q

from .models import (
    Aluno,
    ConfiguracaoAno,
    DocumentoHistorico,
    MatrizCurricularVersao,
    Nota,
    RegistroAcademico,
)


def _numero(valor):
    if valor in (None, "", "-", "*"):
        return None
    texto = str(valor).strip().replace("%", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def matriz_para_ano(ano):
    return (
        MatrizCurricularVersao.objects
        .filter(ativa=True, vigente_de__lte=ano)
        .filter(Q(vigente_ate__isnull=True) | Q(vigente_ate__gte=ano))
        .order_by("-vigente_de", "codigo")
        .first()
    )


def garantir_matriz_registro(registro):
    if registro.matriz_curricular_id:
        return registro.matriz_curricular
    config = (
        ConfiguracaoAno.objects
        .select_related("matriz_curricular")
        .filter(ano=registro.ano)
        .first()
    )
    matriz = (
        config.matriz_curricular
        if config and config.matriz_curricular_id
        else matriz_para_ano(registro.ano)
    )
    if matriz:
        registro.matriz_curricular = matriz
        registro.save(update_fields=["matriz_curricular"])
    return matriz


def media_ponderada_registro(registro):
    notas = {
        nota.componente: _numero(nota.valor)
        for nota in registro.notas.all()
    }
    notas = {k: v for k, v in notas.items() if v is not None}
    if not notas:
        return None

    matriz = registro.matriz_curricular
    pesos = {}
    if matriz:
        pesos = {
            item.componente: item.peso
            for item in matriz.componentes.all()
        }

    soma = Decimal("0")
    peso_total = Decimal("0")
    for componente, valor in notas.items():
        peso = Decimal(pesos.get(componente, 1))
        if peso <= 0:
            continue
        soma += valor * peso
        peso_total += peso

    if peso_total == 0:
        return None
    return (soma / peso_total).quantize(Decimal("0.01"))


def _frequencia_percentual(valor):
    numero = _numero(valor)
    if numero is None:
        return None
    if numero <= 1:
        numero *= 100
    return numero


def alertas_registro(registro):
    alertas = []
    config = ConfiguracaoAno.objects.filter(ano=registro.ano).first()
    minimo = _numero(config.media_minima) if config else None
    if minimo is not None and minimo <= 1:
        minimo *= 100

    notas_numericas = []
    for nota in registro.notas.all():
        valor = _numero(nota.valor)
        if valor is not None and valor > 5:
            notas_numericas.append((nota, valor))

    if minimo is not None:
        abaixo = [
            nota.get_componente_display()
            for nota, valor in notas_numericas
            if valor < minimo
        ]
        if abaixo:
            alertas.append(
                {
                    "tipo": "nota",
                    "nivel": "alto",
                    "titulo": "Notas abaixo do mínimo",
                    "detalhe": ", ".join(abaixo),
                }
            )

    frequencia = _frequencia_percentual(registro.frequencia)
    if frequencia is not None and frequencia < 75:
        alertas.append(
            {
                "tipo": "frequencia",
                "nivel": "alto",
                "titulo": "Frequência abaixo de 75%",
                "detalhe": f"{frequencia}%",
            }
        )

    matriz = registro.matriz_curricular
    if matriz:
        obrigatorios = {
            item.componente: item.nome_exibicao
            for item in matriz.componentes.filter(obrigatorio=True)
        }
        presentes = set(registro.notas.values_list("componente", flat=True))
        faltantes = [
            nome
            for componente, nome in obrigatorios.items()
            if componente not in presentes
        ]
        if faltantes:
            alertas.append(
                {
                    "tipo": "componente",
                    "nivel": "medio",
                    "titulo": "Componentes sem nota",
                    "detalhe": ", ".join(faltantes),
                }
            )

    if not registro.resultado:
        alertas.append(
            {
                "tipo": "resultado",
                "nivel": "medio",
                "titulo": "Resultado final não informado",
                "detalhe": "Complete a situação do aluno neste ano.",
            }
        )

    return alertas


def indicadores_aluno(aluno):
    registros = list(
        aluno.registros_academicos
        .select_related("matriz_curricular")
        .prefetch_related("notas", "matriz_curricular__componentes")
        .order_by("ano", "serie", "id")
    )

    linhas = []
    medias = []
    alertas = []
    total_notas = 0

    for registro in registros:
        media = media_ponderada_registro(registro)
        if media is not None:
            medias.append(media)
        alertas_ano = alertas_registro(registro)
        alertas.extend(
            [{**alerta, "ano": registro.ano, "serie": registro.serie} for alerta in alertas_ano]
        )
        total_notas += registro.notas.count()
        linhas.append(
            {
                "registro": registro,
                "media": media,
                "alertas": alertas_ano,
                "quantidade_notas": registro.notas.count(),
            }
        )

    media_geral = None
    if medias:
        media_geral = (
            sum(medias, Decimal("0")) / Decimal(len(medias))
        ).quantize(Decimal("0.01"))

    return {
        "registros": linhas,
        "media_geral": media_geral,
        "total_notas": total_notas,
        "alertas": alertas,
        "anos_cursados": len(registros),
        "ultimo_ano": max((r.ano for r in registros), default=None),
        "ultima_serie": max(
            (r.serie or 0 for r in registros),
            default=0,
        ) or None,
    }


def painel_geral():
    alunos_total = Aluno.objects.count()
    registros_total = RegistroAcademico.objects.count()
    notas_total = Nota.objects.count()
    documentos_total = DocumentoHistorico.objects.count()

    alunos_incompletos = (
        Aluno.objects.filter(
            Q(nome="")
            | Q(nascimento="")
            | Q(naturalidade="")
            | Q(mae="")
        )
        .count()
    )
    registros_sem_notas = (
        RegistroAcademico.objects
        .annotate(qtd=Count("notas"))
        .filter(qtd=0)
        .count()
    )
    registros_sem_matriz = RegistroAcademico.objects.filter(
        matriz_curricular__isnull=True
    ).count()

    documentos_recentes = list(
        DocumentoHistorico.objects
        .select_related("aluno", "emitido_por")
        .order_by("-emitido_em")[:8]
    )

    return {
        "alunos_total": alunos_total,
        "registros_total": registros_total,
        "notas_total": notas_total,
        "documentos_total": documentos_total,
        "alunos_incompletos": alunos_incompletos,
        "registros_sem_notas": registros_sem_notas,
        "registros_sem_matriz": registros_sem_matriz,
        "documentos_recentes": documentos_recentes,
    }



def relatorio_integridade(limite=50):
    alunos_incompletos = list(
        Aluno.objects.filter(
            Q(nome="")
            | Q(nascimento="")
            | Q(naturalidade="")
            | Q(mae="")
        )
        .order_by("nome")[:limite]
    )

    registros_sem_notas = list(
        RegistroAcademico.objects
        .select_related("aluno")
        .annotate(qtd=Count("notas"))
        .filter(qtd=0)
        .order_by("-ano", "aluno__nome")[:limite]
    )

    registros_sem_matriz = list(
        RegistroAcademico.objects
        .select_related("aluno")
        .filter(matriz_curricular__isnull=True)
        .order_by("-ano", "aluno__nome")[:limite]
    )

    nomes_duplicados = list(
        Aluno.objects
        .values("nome")
        .annotate(qtd=Count("id"))
        .filter(qtd__gt=1)
        .order_by("-qtd", "nome")[:limite]
    )

    return {
        "alunos_incompletos": alunos_incompletos,
        "registros_sem_notas": registros_sem_notas,
        "registros_sem_matriz": registros_sem_matriz,
        "nomes_duplicados": nomes_duplicados,
        "totais": {
            "alunos_incompletos": len(alunos_incompletos),
            "registros_sem_notas": len(registros_sem_notas),
            "registros_sem_matriz": len(registros_sem_matriz),
            "nomes_duplicados": len(nomes_duplicados),
        },
    }
