from .models import RegistroAta, ParametroAno

def localizar_registros_aluno(aluno):
    termos={str(aluno.codigo).strip(), aluno.nome.strip().upper()}
    qs=RegistroAta.objects.all().order_by('ano','linha')
    encontrados=[]
    for r in qs.iterator():
        texto=(r.texto_busca or '').upper()
        if any(t and t.upper() in texto for t in termos): encontrados.append(r)
    return encontrados

def resumo_academico(aluno):
    regs=localizar_registros_aluno(aluno)
    saida=[]
    for r in regs:
        parametro=ParametroAno.objects.filter(ano=r.ano).first()
        saida.append({'ano':r.ano,'linha':r.linha,'dados':r.dados,'parametro':parametro})
    return saida
