from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Aluno, AbaExcel, CelulaExcel, ParametroAno
from .services import resumo_academico

def inicio(request):
    q=request.GET.get('q','').strip()
    alunos=[]
    if q:
        filtro=Q(nome__icontains=q)
        if q.isdigit(): filtro |= Q(codigo=int(q))
        alunos=Aluno.objects.filter(filtro).order_by('nome')[:50]
    return render(request,'historico/inicio.html',{'q':q,'alunos':alunos,'total':Aluno.objects.count(),'abas':AbaExcel.objects.count()})

def aluno_detalhe(request,codigo):
    aluno=get_object_or_404(Aluno,codigo=codigo)
    return render(request,'historico/aluno.html',{'aluno':aluno,'historico':resumo_academico(aluno)})

def historico_impressao(request,codigo):
    aluno=get_object_or_404(Aluno,codigo=codigo)
    return render(request,'historico/historico.html',{'aluno':aluno,'historico':resumo_academico(aluno)})

def planilhas(request):
    return render(request,'historico/planilhas.html',{'abas':AbaExcel.objects.order_by('ordem')})

def aba(request,pk):
    aba=get_object_or_404(AbaExcel,pk=pk)
    limite_linhas=min(int(request.GET.get('linhas','120')),500)
    limite_cols=min(aba.max_coluna,60)
    cells=CelulaExcel.objects.filter(aba=aba,linha__lte=limite_linhas,coluna__lte=limite_cols)
    mapa={(c.linha,c.coluna):c for c in cells}
    linhas=[]
    for r in range(1,limite_linhas+1):
        row=[]
        for c in range(1,limite_cols+1): row.append(mapa.get((r,c)))
        if any(x and (x.valor or x.formula) for x in row): linhas.append((r,row))
    return render(request,'historico/aba.html',{'aba':aba,'linhas':linhas,'cols':range(1,limite_cols+1),'limite':limite_linhas})
