from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from .models import Aluno, RegistroAcademico
from .services import historico_do_aluno

def inicio(request):
    q = request.GET.get("q", "").strip()
    alunos = []
    if q:
        filtro = Q(nome__icontains=q)
        if q.isdigit():
            filtro |= Q(codigo=int(q))
        alunos = Aluno.objects.filter(filtro, ativo=True).order_by("nome")[:50]
    return render(request, "historico/inicio.html", {
        "q": q,
        "alunos": alunos,
        "total": Aluno.objects.count(),
        "registros": RegistroAcademico.objects.count(),
    })

def aluno_detalhe(request, codigo):
    aluno = get_object_or_404(Aluno, codigo=codigo)
    return render(request, "historico/aluno.html", {
        "aluno": aluno,
        "historico": historico_do_aluno(aluno),
    })

def historico_impressao(request, codigo):
    aluno = get_object_or_404(Aluno, codigo=codigo)
    return render(request, "historico/historico.html", {
        "aluno": aluno,
        "historico": historico_do_aluno(aluno),
    })
