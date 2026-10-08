# Auditoria e Refatoração — Histórico Egídio

## Stack identificada

- Backend: Django 5.2
- Renderização: Django Templates (server-side)
- Banco: SQLite persistido em `data/historico.sqlite3`
- Servidor: Gunicorn
- Arquivos estáticos: WhiteNoise
- UI: CSS próprio, sem Tailwind/Bootstrap
- Interatividade: JavaScript vanilla
- Runtime sem dependência de Excel

## Mapeamento de responsabilidades

### Documento oficial
- `historico/templates/historico/historico.html`
- Estrutura semântica do histórico, certificado, vida escolar, observações e assinaturas.

### Design System da aplicação
- `historico/static/historico/css/app.css`
- Navegação, cards, busca, painel e elementos gerais da aplicação.

### Motor visual A4/PDF
- `historico/static/historico/css/document.css`
- Folha A4 em tela, tipografia acadêmica, tabela, editor e `@media print`.

### Interatividade do editor
- `historico/static/historico/js/historico-editor.js`
- Edição inline, cálculo de resumo, alertas, autosave, status e fallback da timbragem.

### Regras de negócio
- `historico/services.py`
- Média mínima por ano, situação acadêmica, faltas e montagem do histórico.

### Persistência
- `historico/models.py`
- Aluno, configuração anual, registro acadêmico e notas/carga por componente.

### API de edição
- `historico/views.py::salvar_historico`
- Endpoint autenticado, restrito a operador staff, com transação atômica.

## Princípios adotados

1. O documento em tela e o PDF possuem responsabilidades visuais distintas.
2. Alertas de reprovação existem apenas para operação em tela.
3. Alertas são rigorosamente neutralizados no `@media print`.
4. Valores oficiais não são normalizados no banco; a normalização 0–10/0–100 é usada apenas no resumo operacional.
5. Escalas qualitativas históricas N1/N2/N3/N4/N5 não são tratadas como notas numéricas.
6. O currículo oficial continua representado por componentes estruturados no banco para impedir alterações acidentais de semântica.
7. Edições inline são persistidas no servidor, não apenas no DOM.
8. A timbragem oficial possui fallback versionado para evitar dependência de upload manual.
9. Cada bloco de ano letivo é isolado em um `tbody` para reduzir quebras inadequadas no PDF.
10. O runtime não depende do arquivo Excel original.

## Segurança da edição

- Apenas usuários autenticados com `is_staff=True` podem persistir alterações.
- O endpoint usa CSRF.
- O registro acadêmico é validado como pertencente ao aluno antes da alteração.
- O salvamento ocorre dentro de `transaction.atomic()`.
- Campos são limitados ao tamanho definido no modelo.
- Componentes curriculares recebidos são validados contra as choices do modelo.

## Testes

`historico/tests.py` cobre:
- precedência da carga horária do registro;
- média mínima;
- edição de aluno;
- edição de registro acadêmico;
- nota;
- carga horária por componente.

O workflow `.github/workflows/tests.yml` executa:
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`

## Impressão

Tela:
- folha com 210mm x 297mm;
- padding 15mm 20mm;
- sombra de papel;
- campos editáveis com hover/focus;
- alertas operacionais.

PDF/impressão:
- A4 portrait;
- sem sombra;
- sem barra de operação;
- sem outline de edição;
- sem vermelho de reprovação;
- `print-color-adjust: exact`;
- blocos acadêmicos configurados para evitar quebra interna sempre que possível.
