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
    try:
        return Decimal(str(valor).replace("%", "").replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None

def _media_percentual(config):
    if not config or not config.media_minima:
        return None
    n = _numero(config.media_minima)
    if n is None:
        return None
    return n * 100 if n <= 1 else n

def situacao_apta(resultado):
    r = (resultado or "").strip().upper()
    return r in {"APROVADO", "EM CONTINUIDADE", "EM CURSO", "APTO", "APTA"}

def faltas_em_horas(registro):
    if registro.ano == 2020:
        return "*"
    n = _numero(registro.faltas)
    if n is None:
        return ""
    # A planilha original converte o total de faltas em aulas para horas multiplicando por 4.
    return f"{int(n * 4)}:00"

def avaliar_media(registro, config):
    media = _media_percentual(config)
    if media is None:
        return ""
    valores = []
    for nota in registro.notas.all():
        n = _numero(nota.valor)
        if n is not None:
            valores.append(n)
    if not valores:
        return ""
    # Escalas antigas N1/N2/N3 são qualitativas e não entram neste teste numérico.
    if any(v <= 3 for v in valores) and max(valores) <= 3:
        return ""
    return "ALUNO DENTRO DA MÉDIA" if all(v >= media for v in valores) else "ALUNO ABAIXO DA MÉDIA"

def historico_do_aluno(aluno):
    registros = (
        aluno.registros_academicos
        .prefetch_related("notas")
        .order_by("ano", "serie", "id")
    )
    saida = []
    for registro in registros:
        config = ConfiguracaoAno.objects.filter(ano=registro.ano).first()
        notas = {n.componente: n.valor for n in registro.notas.all()}
        saida.append({
            "registro": registro,
            "config": config,
            "notas": notas,
            "notas_ordenadas": [(c, notas.get(c, "")) for c in ORDEM_COMPONENTES],
            "apto": situacao_apta(registro.resultado),
            "faltas_horas": faltas_em_horas(registro),
            "avaliacao_media": avaliar_media(registro, config),
        })
    return saida
