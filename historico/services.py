import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

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

MESES = {
    1: "JANEIRO",
    2: "FEVEREIRO",
    3: "MARÇO",
    4: "ABRIL",
    5: "MAIO",
    6: "JUNHO",
    7: "JULHO",
    8: "AGOSTO",
    9: "SETEMBRO",
    10: "OUTUBRO",
    11: "NOVEMBRO",
    12: "DEZEMBRO",
}


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


def formatar_percentual(valor):
    if valor in (None, "", "*"):
        return "*" if valor == "*" else ""
    texto = str(valor).strip()
    if "%" in texto:
        return texto
    numero = _numero(texto)
    if numero is None:
        return texto
    if numero <= 1:
        numero *= 100
    return f"{int(numero) if numero == int(numero) else numero}%"


def formatar_carga_horaria(valor):
    if valor in (None, "", "*"):
        return "*" if valor == "*" else ""
    texto = str(valor).strip()
    if ":" in texto:
        return texto
    numero = _numero(texto)
    if numero is None:
        return texto
    horas = int(numero)
    minutos = int(round((numero - horas) * 60))
    if minutos == 60:
        horas += 1
        minutos = 0
    return f"{horas}:{minutos:02d}"


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


def _partes_data(valor):
    texto = (valor or "").strip()
    if not texto:
        return {"dia": "", "mes": "", "ano": ""}

    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            data = datetime.strptime(texto, formato)
            return {
                "dia": str(data.day),
                "mes": MESES[data.month],
                "ano": str(data.year),
            }
        except ValueError:
            pass

    match = re.match(
        r"^\s*(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})\s*$",
        texto,
        re.IGNORECASE,
    )
    if match:
        return {
            "dia": match.group(1),
            "mes": match.group(2).upper(),
            "ano": match.group(3),
        }

    return {"dia": texto, "mes": "", "ano": ""}


def _dados_registro(registro):
    config = ConfiguracaoAno.objects.filter(ano=registro.ano).first()
    notas_qs = list(registro.notas.all())
    notas = {nota.componente: nota.valor for nota in notas_qs}
    cargas_componentes = {
        nota.componente: nota.carga_horaria for nota in notas_qs
    }
    media_minima = media_minima_percentual(config)

    carga = registro.carga_horaria or (config.ch_anual if config else "")

    return {
        "registro": registro,
        "registro_id": registro.id,
        "serie": registro.serie,
        "ano": registro.ano,
        "faltante": False,
        "config": config,
        "notas": notas,
        "cargas_componentes": cargas_componentes,
        "notas_ordenadas": [
            (componente, notas.get(componente, ""))
            for componente in ORDEM_COMPONENTES
        ],
        "apto": situacao_apta(registro.resultado),
        "situacao": "APTO" if situacao_apta(registro.resultado) else (registro.resultado or ""),
        "faltas_horas": faltas_em_horas(registro),
        "frequencia": registro.frequencia,
        "carga_horaria": formatar_carga_horaria(carga),
        "dias_letivos": str(config.dias_letivos) if config and config.dias_letivos else "",
        "media_minima": formatar_percentual(config.media_minima if config else ""),
        "media_minima_num": str(media_minima) if media_minima is not None else "",
        "avaliacao_media": avaliar_media(registro, config),
        "escola": registro.escola or (config.escola if config else ""),
        "municipio": registro.municipio or (config.municipio if config else ""),
        "uf": registro.uf or (config.uf if config else ""),
    }


def historico_do_aluno(aluno):
    registros = (
        aluno.registros_academicos
        .prefetch_related("notas")
        .order_by("ano", "serie", "id")
    )
    return [_dados_registro(registro) for registro in registros]


def _slot_faltante(serie):
    estrela_notas = {componente: "*" for componente in ORDEM_COMPONENTES}
    return {
        "registro": None,
        "registro_id": None,
        "serie": serie,
        "ano": "*",
        "faltante": True,
        "config": None,
        "notas": estrela_notas,
        "cargas_componentes": {},
        "notas_ordenadas": [(componente, "*") for componente in ORDEM_COMPONENTES],
        "apto": False,
        "situacao": "*",
        "faltas_horas": "*",
        "frequencia": "*",
        "carga_horaria": "*",
        "dias_letivos": "*",
        "media_minima": "*",
        "media_minima_num": "",
        "avaliacao_media": "",
        "escola": "*",
        "municipio": "*",
        "uf": "",
    }


def _observacao_automatica(aluno, slots):
    linhas = []
    presentes = [slot for slot in slots if not slot["faltante"]]
    if not presentes:
        return ""

    maior_serie = max(slot["serie"] for slot in presentes)

    for slot in slots:
        if (
            slot["faltante"]
            and slot["serie"] < maior_serie
            and any(
                not posterior["faltante"] and posterior["serie"] > slot["serie"]
                for posterior in slots
            )
        ):
            linhas.append(
                f'*"REGULARIZAÇÃO DE VIDA ESCOLAR - LACUNA NO {slot["serie"]}° ANO '
                'DO ENSINO FUNDAMENTAL, AMPARADA PELO PARECER CME/CTEB N° 03/2016, '
                'DE 16 DE MARÇO DE 2016, UTILIZADO POR ANALOGIA."'
            )

    ultimo = max(presentes, key=lambda item: (item["serie"], item["ano"] or 0))
    if ultimo["apto"]:
        feminino = "FEM" in (aluno.sexo or "").upper()
        substantivo = "ALUNA" if feminino else "ALUNO"
        apto = "APTA" if feminino else "APTO"
        proxima = min(int(ultimo["serie"]) + 1, 9)
        linhas.append(
            f"*INFORMAMOS QUE {substantivo} ENCONTRA-SE {apto} A MATRICULAR-SE "
            f"NO {proxima}º ANO DO ENSINO FUNDAMENTAL."
        )

    return "\n".join(linhas)


def historico_documento(aluno):
    registros = list(
        aluno.registros_academicos
        .prefetch_related("notas")
        .order_by("ano", "serie", "id")
    )

    por_serie = {}
    for registro in registros:
        if registro.serie not in {1, 2, 3, 4, 5}:
            continue
        atual = por_serie.get(registro.serie)
        if atual is None or registro.ano >= atual.ano:
            por_serie[registro.serie] = registro

    slots = []
    for serie in range(1, 6):
        registro = por_serie.get(serie)
        slots.append(_dados_registro(registro) if registro else _slot_faltante(serie))

    presentes = [slot for slot in slots if not slot["faltante"]]
    ultimo = max(
        presentes,
        key=lambda item: (item["serie"], item["ano"]),
        default=None,
    )

    observacao = (aluno.observacao_historico or "").strip()
    if not observacao:
        observacao = _observacao_automatica(aluno, slots)

    data_expedicao = (aluno.data_expedicao or "").strip()
    if not data_expedicao:
        data_expedicao = timezone.localdate().strftime("%d/%m/%Y")

    return {
        "slots": slots,
        "nascimento": _partes_data(aluno.nascimento),
        "data_conclusao": aluno.data_conclusao,
        "serie_conclusao": (
            aluno.ultima_serie_concluida
            or (f'{ultimo["serie"]}º' if ultimo else "")
        ),
        "identidade": aluno.identidade,
        "orgao_expedidor": aluno.orgao_expedidor,
        "observacao": observacao,
        "data_expedicao": data_expedicao,
        "municipio_expedicao": (
            (ultimo["municipio"] if ultimo else "") or "MONTES CLAROS"
        ),
    }
