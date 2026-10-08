from decimal import Decimal, InvalidOperation

from .models import ConfiguracaoAno, Nota


ORDEM_COMPONENTES = [
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


def _numero(valor):
    if valor in (None, "", "-", "*"):
        return None
    texto = str(valor).replace("%", "").replace(",", ".").strip()
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def media_minima_percentual(config):
    if not config or not config.media_minima:
        return None
    numero = _numero(config.media_minima)
    if numero is None:
        return None
    return numero * 100 if numero <= 1 else numero


def situacao_apta(resultado):
    resultado_normalizado = (resultado or "").strip().upper()
    return resultado_normalizado in {
        "APROVADO",
        "EM CONTINUIDADE",
        "EM CURSO",
        "APTO",
        "APTA",
    }


def faltas_em_horas(registro):
    if registro.ano == 2020:
        return "*"
    numero = _numero(registro.faltas)
    if numero is None:
        return ""
    return f"{int(numero * 4)}:00"


def avaliar_media(registro, config):
    media = media_minima_percentual(config)
    if media is None:
        return ""

    valores = []
    for nota in registro.notas.all():
        numero = _numero(nota.valor)
        if numero is not None:
            valores.append(numero)

    if not valores:
        return ""

    if max(valores) <= 5:
        return ""

    return (
        "ALUNO DENTRO DA MÉDIA"
        if all(valor >= media for valor in valores)
        else "ALUNO ABAIXO DA MÉDIA"
    )


def historico_do_aluno(aluno):
    registros = (
        aluno.registros_academicos
        .prefetch_related("notas")
        .order_by("ano", "serie", "id")
    )

    saida = []
    for registro in registros:
        config = ConfiguracaoAno.objects.filter(ano=registro.ano).first()
        notas_qs = list(registro.notas.all())
        notas = {nota.componente: nota.valor for nota in notas_qs}
        cargas_componentes = {
            nota.componente: nota.carga_horaria for nota in notas_qs
        }
        media_minima = media_minima_percentual(config)

        saida.append(
            {
                "registro": registro,
                "config": config,
                "notas": notas,
                "cargas_componentes": cargas_componentes,
                "notas_ordenadas": [
                    (componente, notas.get(componente, ""))
                    for componente in ORDEM_COMPONENTES
                ],
                "apto": situacao_apta(registro.resultado),
                "faltas_horas": faltas_em_horas(registro),
                "frequencia": registro.frequencia,
                "carga_horaria": (
                    registro.carga_horaria
                    or (config.ch_anual if config else "")
                ),
                "media_minima_num": (
                    str(media_minima) if media_minima is not None else ""
                ),
                "avaliacao_media": avaliar_media(registro, config),
            }
        )

    return saida
