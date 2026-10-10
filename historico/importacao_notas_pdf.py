import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from django.db import transaction
from django.db.models import Max

from .models import Aluno, ConfiguracaoAno, Nota, RegistroAcademico


MAX_PAGINAS = 250
MAX_ITENS = 15000

COMPONENTES = {
    "lingua_portuguesa": Nota.LINGUA_PORTUGUESA,
    "arte": Nota.ARTE,
    "educacao_fisica": Nota.EDUCACAO_FISICA,
    "lingua_inglesa": Nota.LINGUA_INGLESA,
    "matematica": Nota.MATEMATICA,
    "ciencias": Nota.CIENCIAS,
    "geografia": Nota.GEOGRAFIA,
    "historia": Nota.HISTORIA,
    "educacao_religiosa": Nota.EDUCACAO_RELIGIOSA,
}

ROTULOS_COMPONENTES = dict(Nota.COMPONENTES)

ALIASES_COMPONENTES = {
    Nota.LINGUA_PORTUGUESA: {
        "lingua portuguesa",
        "portugues",
        "lingua portuguesa literatura",
        "portugues literatura",
        "lp",
    },
    Nota.ARTE: {"arte", "artes"},
    Nota.EDUCACAO_FISICA: {
        "educacao fisica",
        "ed fisica",
        "educ fisica",
        "ed fis",
    },
    Nota.LINGUA_INGLESA: {
        "lingua inglesa",
        "ingles",
        "lingua estrangeira ingles",
    },
    Nota.MATEMATICA: {"matematica", "mat"},
    Nota.CIENCIAS: {
        "ciencias",
        "ciencias da natureza",
        "ciencia",
    },
    Nota.GEOGRAFIA: {"geografia", "geo"},
    Nota.HISTORIA: {"historia"},
    Nota.EDUCACAO_RELIGIOSA: {
        "educacao religiosa",
        "ensino religioso",
        "ed religiosa",
        "religiao",
    },
}

ALIASES_CAMPOS = {
    "nome": {
        "nome",
        "aluno",
        "nome aluno",
        "nome do aluno",
        "estudante",
    },
    "turma": {"turma", "classe"},
    "ano": {
        "ano letivo",
        "ano escolar",
        "ano calendario",
        "ano calendario letivo",
    },
    "serie": {
        "serie",
        "serie ano",
        "serie escolar",
        "etapa",
    },
}


class ErroImportacaoNotasPdf(ValueError):
    pass


def _sem_acentos(valor):
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", str(valor or ""))
        if not unicodedata.combining(caractere)
    )


def _normalizar(valor):
    texto = _sem_acentos(valor).lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_nome(valor):
    return re.sub(r"\s+", " ", _sem_acentos(valor).upper()).strip()


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return re.sub(r"\s+", " ", str(valor)).strip()


def _ano(valor):
    texto = _texto(valor)
    encontrados = re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", texto)
    if encontrados:
        return int(encontrados[0])
    try:
        numero = int(float(texto.replace(",", ".")))
    except (ValueError, TypeError):
        return None
    return numero if 1900 <= numero <= 2100 else None


def _serie(valor):
    texto = _normalizar(valor)
    if not texto:
        return None

    padroes = (
        r"\b([1-9])\s*(?:o|a)?\s*ano\b",
        r"\b([1-9])\s*(?:o|a)?\s*serie\b",
        r"\bserie\s*([1-9])\b",
        r"\bano\s*([1-9])\b",
        r"^([1-9])$",
    )
    for padrao in padroes:
        match = re.search(padrao, texto)
        if match:
            return int(match.group(1))
    return None


def _mapear_cabecalho(celulas):
    mapa = {}
    reconhecidos = set()

    for indice, celula in enumerate(celulas):
        chave = _normalizar(celula)
        if not chave:
            continue

        for campo, aliases in ALIASES_CAMPOS.items():
            if chave in aliases and campo not in reconhecidos:
                mapa[indice] = ("campo", campo)
                reconhecidos.add(campo)
                break
        else:
            for componente, aliases in ALIASES_COMPONENTES.items():
                if chave in aliases and componente not in reconhecidos:
                    mapa[indice] = ("nota", componente)
                    reconhecidos.add(componente)
                    break

    score = 0
    campos = {valor for tipo, valor in mapa.values() if tipo == "campo"}
    notas = {valor for tipo, valor in mapa.values() if tipo == "nota"}

    if "nome" in campos:
        score += 6
    if "turma" in campos:
        score += 2
    if "ano" in campos:
        score += 2
    if "serie" in campos:
        score += 2
    score += min(len(notas), 6)

    return score, mapa


def _inferir_ano_serie(dados, linha_original):
    if dados.get("ano") and dados.get("serie"):
        return

    candidatos = [_texto(v) for v in linha_original if _texto(v)]
    for candidato in candidatos:
        if not dados.get("ano"):
            valor_ano = _ano(candidato)
            if valor_ano:
                dados["ano"] = valor_ano
        if not dados.get("serie"):
            valor_serie = _serie(candidato)
            if valor_serie:
                dados["serie"] = valor_serie


def _linha_tabela_para_item(linha, mapa, pagina):
    dados = {
        "nome": "",
        "turma": "",
        "ano": None,
        "serie": None,
        "notas": {},
        "_pagina": pagina,
    }

    for indice, definicao in mapa.items():
        if indice >= len(linha):
            continue

        tipo, chave = definicao
        valor = _texto(linha[indice])
        if tipo == "nota":
            if valor:
                dados["notas"][chave] = valor
            continue

        if chave == "ano":
            dados["ano"] = _ano(valor)
        elif chave == "serie":
            dados["serie"] = _serie(valor)
        else:
            dados[chave] = valor

    _inferir_ano_serie(dados, linha)
    return dados


def _extrair_tabelas_pagina(pagina, numero_pagina):
    itens = []
    for tabela in pagina.extract_tables() or []:
        if not tabela:
            continue

        cabecalho = None
        mapa = None
        indice_cabecalho = None

        for indice, linha in enumerate(tabela[:8]):
            score, candidato = _mapear_cabecalho(linha or [])
            if mapa is None or score > cabecalho:
                cabecalho = score
                mapa = candidato
                indice_cabecalho = indice

        if not mapa or cabecalho < 7:
            continue

        for linha in tabela[indice_cabecalho + 1:]:
            if not linha:
                continue
            item = _linha_tabela_para_item(linha, mapa, numero_pagina)
            if not item["nome"]:
                continue
            if not item["notas"]:
                continue
            itens.append(item)
            if len(itens) >= MAX_ITENS:
                return itens

    return itens


def _valor_rotulado(texto, rotulos):
    rotulo = "|".join(re.escape(item) for item in rotulos)
    match = re.search(
        rf"(?:^|\n)\s*(?:{rotulo})\s*[:\-]\s*([^\n]+)",
        texto,
        flags=re.IGNORECASE,
    )
    return _texto(match.group(1)) if match else ""


def _parsear_blocos_texto(texto, pagina):
    if not texto:
        return []

    normalizado = texto.replace("\r", "\n")
    marcadores = list(
        re.finditer(
            r"(?im)^\s*(?:nome(?:\s+do\s+aluno)?|aluno|estudante)\s*[:\-]\s*",
            normalizado,
        )
    )
    if not marcadores:
        return []

    itens = []
    for indice, marcador in enumerate(marcadores):
        fim = (
            marcadores[indice + 1].start()
            if indice + 1 < len(marcadores)
            else len(normalizado)
        )
        bloco = normalizado[marcador.start():fim]

        primeira_linha = bloco.splitlines()[0]
        nome = re.sub(
            r"(?i)^\s*(?:nome(?:\s+do\s+aluno)?|aluno|estudante)\s*[:\-]\s*",
            "",
            primeira_linha,
        ).strip()

        turma = _valor_rotulado(bloco, ("turma", "classe"))
        ano_texto = _valor_rotulado(
            bloco,
            ("ano letivo", "ano escolar", "ano"),
        )
        serie_texto = _valor_rotulado(
            bloco,
            ("série", "serie", "série/ano", "serie/ano", "etapa"),
        )

        item = {
            "nome": nome,
            "turma": turma,
            "ano": _ano(ano_texto),
            "serie": _serie(serie_texto),
            "notas": {},
            "_pagina": pagina,
        }

        if not item["serie"]:
            item["serie"] = _serie(serie_texto or bloco)

        for componente, aliases in ALIASES_COMPONENTES.items():
            aliases_regex = "|".join(
                re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)
            )
            match = re.search(
                rf"(?im)^\s*(?:{aliases_regex})\s*[:\-]\s*"
                rf"([A-Za-z0-9,\.\-]+)\s*$",
                _sem_acentos(bloco),
            )
            if match:
                item["notas"][componente] = _texto(match.group(1))

        if item["nome"] and item["notas"]:
            itens.append(item)

    return itens


def _mesclar_itens(itens):
    agrupados = {}

    for item in itens:
        chave = (
            _normalizar_nome(item.get("nome")),
            item.get("ano"),
            item.get("serie"),
            _normalizar(item.get("turma")),
        )

        if chave not in agrupados:
            agrupados[chave] = {
                "nome": item.get("nome", ""),
                "turma": item.get("turma", ""),
                "ano": item.get("ano"),
                "serie": item.get("serie"),
                "notas": {},
                "_paginas": [],
            }

        destino = agrupados[chave]
        destino["notas"].update(
            {
                componente: valor
                for componente, valor in item.get("notas", {}).items()
                if _texto(valor)
            }
        )
        if item.get("_pagina") and item["_pagina"] not in destino["_paginas"]:
            destino["_paginas"].append(item["_pagina"])

    return list(agrupados.values())


def extrair_notas_pdf(caminho):
    import pdfplumber

    caminho = Path(caminho)
    itens = []
    paginas_com_texto = 0

    try:
        with pdfplumber.open(caminho) as pdf:
            if len(pdf.pages) > MAX_PAGINAS:
                raise ErroImportacaoNotasPdf(
                    f"O PDF possui {len(pdf.pages)} páginas. "
                    f"O limite é {MAX_PAGINAS} páginas."
                )

            for numero, pagina in enumerate(pdf.pages, start=1):
                tabelas = _extrair_tabelas_pagina(pagina, numero)
                itens.extend(tabelas)

                texto_pagina = pagina.extract_text() or ""
                if texto_pagina.strip():
                    paginas_com_texto += 1

                # O parser textual complementa PDFs nos quais a tabela não é
                # detectada pelo mecanismo geométrico.
                if not tabelas:
                    itens.extend(_parsear_blocos_texto(texto_pagina, numero))

                if len(itens) >= MAX_ITENS:
                    break
    except ErroImportacaoNotasPdf:
        raise
    except Exception as exc:
        raise ErroImportacaoNotasPdf(
            "Não foi possível abrir ou interpretar o PDF."
        ) from exc

    if paginas_com_texto == 0:
        raise ErroImportacaoNotasPdf(
            "O PDF parece ser apenas uma imagem digitalizada. "
            "Envie um PDF com texto selecionável."
        )

    itens = _mesclar_itens(itens)

    validos = []
    incompletos = []
    for item in itens:
        faltando = []
        if not item.get("nome"):
            faltando.append("nome")
        if not item.get("ano"):
            faltando.append("ano")
        if not item.get("serie"):
            faltando.append("série")
        if not item.get("notas"):
            faltando.append("notas")

        if faltando:
            item["erro"] = "Faltando: " + ", ".join(faltando)
            incompletos.append(item)
        else:
            validos.append(item)

    if not validos:
        raise ErroImportacaoNotasPdf(
            "Não encontrei registros completos com nome do aluno, ano, "
            "série e notas. Verifique o formato do PDF."
        )

    return {
        "itens": validos,
        "incompletos": incompletos,
        "paginas_com_texto": paginas_com_texto,
    }


def _indice_alunos():
    indice = defaultdict(list)
    for aluno in Aluno.objects.all().order_by("id"):
        indice[_normalizar_nome(aluno.nome)].append(aluno)
    return indice


def _resolver_aluno(nome, indice):
    encontrados = indice.get(_normalizar_nome(nome), [])
    if len(encontrados) == 1:
        return encontrados[0], None
    if len(encontrados) > 1:
        return None, "Existem vários alunos no banco com este mesmo nome."
    return None, None


def _resolver_registro(aluno, item):
    registros = list(
        aluno.registros_academicos.filter(
            ano=item["ano"],
            serie=item["serie"],
        ).order_by("id")
    )

    if not registros:
        return None, None

    turma = _normalizar(item.get("turma"))
    if turma:
        mesma_turma = [
            registro
            for registro in registros
            if _normalizar(registro.turma) == turma
        ]
        if len(mesma_turma) == 1:
            return mesma_turma[0], None
        if len(mesma_turma) > 1:
            return None, "Há mais de um registro acadêmico para a mesma turma."

    if len(registros) == 1:
        return registros[0], None

    return None, (
        "Há mais de um registro acadêmico para este aluno, ano e série. "
        "Informe uma turma que identifique o registro correto."
    )


def analisar_notas_pdf(resultado):
    indice = _indice_alunos()
    itens = []
    alunos_novos = 0
    alunos_existentes = 0
    conflitos = 0
    registros_novos = 0
    registros_existentes = 0

    for item in resultado["itens"]:
        aluno, erro = _resolver_aluno(item["nome"], indice)
        registro = None

        if erro:
            status = "conflito"
            conflitos += 1
        elif aluno:
            alunos_existentes += 1
            registro, erro_registro = _resolver_registro(aluno, item)
            if erro_registro:
                status = "conflito"
                erro = erro_registro
                conflitos += 1
            elif registro:
                status = "atualizar"
                registros_existentes += 1
            else:
                status = "novo_registro"
                registros_novos += 1
        else:
            status = "novo_aluno"
            alunos_novos += 1
            registros_novos += 1

        itens.append(
            {
                **item,
                "status": status,
                "erro": erro or "",
                "aluno_codigo": aluno.codigo if aluno else "",
                "registro_id": registro.id if registro else "",
                "quantidade_notas": len(item["notas"]),
                "notas_legiveis": [
                    {
                        "componente": ROTULOS_COMPONENTES.get(
                            componente,
                            componente,
                        ),
                        "valor": valor,
                    }
                    for componente, valor in item["notas"].items()
                ],
            }
        )

    return {
        "total": len(itens),
        "alunos_novos": alunos_novos,
        "alunos_existentes": alunos_existentes,
        "registros_novos": registros_novos,
        "registros_existentes": registros_existentes,
        "conflitos": conflitos,
        "incompletos": len(resultado.get("incompletos", [])),
        "itens": itens,
    }


def _novo_codigo():
    return (Aluno.objects.aggregate(maximo=Max("codigo"))["maximo"] or 0) + 1


@transaction.atomic
def aplicar_notas_pdf(resultado):
    indice = _indice_alunos()
    proximo_codigo = _novo_codigo()

    alunos_criados = 0
    alunos_localizados = 0
    registros_criados = 0
    registros_atualizados = 0
    notas_atualizadas = 0
    conflitos = []

    for item in resultado["itens"]:
        aluno, erro = _resolver_aluno(item["nome"], indice)
        if erro:
            conflitos.append(
                {
                    "nome": item["nome"],
                    "ano": item["ano"],
                    "serie": item["serie"],
                    "erro": erro,
                }
            )
            continue

        if aluno is None:
            while Aluno.objects.filter(codigo=proximo_codigo).exists():
                proximo_codigo += 1
            aluno = Aluno.objects.create(
                codigo=proximo_codigo,
                nome=_texto(item["nome"])[:255],
                curso="ENSINO FUNDAMENTAL",
                ativo=True,
            )
            proximo_codigo += 1
            indice[_normalizar_nome(aluno.nome)].append(aluno)
            alunos_criados += 1
        else:
            alunos_localizados += 1

        registro, erro_registro = _resolver_registro(aluno, item)
        if erro_registro:
            conflitos.append(
                {
                    "nome": item["nome"],
                    "ano": item["ano"],
                    "serie": item["serie"],
                    "erro": erro_registro,
                }
            )
            continue

        if registro is None:
            config = ConfiguracaoAno.objects.filter(ano=item["ano"]).first()
            registro = RegistroAcademico.objects.create(
                aluno=aluno,
                nome_original=aluno.nome,
                ano=item["ano"],
                serie=item["serie"],
                turma=_texto(item.get("turma"))[:120],
                carga_horaria=(config.ch_anual if config else ""),
                escola=(config.escola if config else ""),
                municipio=(config.municipio if config else "MONTES CLAROS"),
                uf=(config.uf if config else "MG"),
            )
            registros_criados += 1
        else:
            alterados = []
            turma = _texto(item.get("turma"))
            if turma and registro.turma != turma[:120]:
                registro.turma = turma[:120]
                alterados.append("turma")
            if registro.nome_original != aluno.nome:
                registro.nome_original = aluno.nome
                alterados.append("nome_original")
            if alterados:
                registro.save(update_fields=alterados)
            registros_atualizados += 1

        for componente, valor in item["notas"].items():
            valor = _texto(valor)
            if not valor:
                continue
            Nota.objects.update_or_create(
                registro=registro,
                componente=componente,
                defaults={"valor": valor[:40]},
            )
            notas_atualizadas += 1

    return {
        "total": len(resultado["itens"]),
        "alunos_criados": alunos_criados,
        "alunos_localizados": alunos_localizados,
        "registros_criados": registros_criados,
        "registros_atualizados": registros_atualizados,
        "notas_atualizadas": notas_atualizadas,
        "conflitos": conflitos,
    }
