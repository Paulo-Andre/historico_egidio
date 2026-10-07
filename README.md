# EMITIR HISTÓRICO — versão web

Migração inicial do arquivo Excel `EMITIR HISTORICO.xlsx` para Django.

## O que esta versão preserva
- As 49 abas originais e suas células relevantes no banco.
- Valores calculados salvos no Excel e fórmulas originais, lado a lado.
- Base `DADOS ALUNOS` convertida em cadastro pesquisável.
- `DADOS ADCIONAIS` convertida em parâmetros por ano.
- Todas as `ATA 2009` a `ATA 2025` importadas para consulta histórica.
- Pesquisa por código/nome do aluno.
- Tela de aluno e visualização dos registros encontrados nas ATAs.
- Modelo web de histórico para impressão.
- Administração Django.
- Visualizador técnico das planilhas importadas.

## Importante sobre fidelidade
Esta é a fundação executável da migração. O Excel contém centenas de fórmulas e layouts de impressão específicos. Elas são preservadas no banco pela importação, mas a reimplementação regra-a-regra do motor de cálculo (para reproduzir dinamicamente `INFO. ALUNO`, `NOTAS AL.` e `HISTÓRICO 2025`) deve ser validada contra o Excel antes de substituir definitivamente a planilha. Nenhuma regra foi descartada.

## Executar localmente
```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py makemigrations historico
python manage.py migrate
python manage.py importar_excel "data/EMITIR HISTORICO.xlsx"
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```
Abra `http://IP_DO_SERVIDOR:8000/`.

## Executar com Docker
Primeira inicialização:
```bash
docker compose build
docker compose run --rm web python manage.py makemigrations historico
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py importar_excel "data/EMITIR HISTORICO.xlsx"
docker compose run --rm web python manage.py createsuperuser
docker compose up -d
```
Depois, use `http://IP_DO_SERVIDOR:8000/`.

## Próxima etapa recomendada
Implementar e testar o motor de equivalência das fórmulas das abas `NOTAS AL.`, `INFO. ALUNO`, `HISTÓRICO 2025` e `HISTORICO`, comparando vários alunos com o resultado atual do Excel até obter equivalência total.
