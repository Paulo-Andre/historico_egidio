from django.urls import path
from . import views
app_name='historico'
urlpatterns=[path('',views.inicio,name='inicio'),path('aluno/<int:codigo>/',views.aluno_detalhe,name='aluno'),path('aluno/<int:codigo>/historico/',views.historico_impressao,name='historico'),path('planilhas/',views.planilhas,name='planilhas'),path('planilhas/<int:pk>/',views.aba,name='aba')]
