# Auditoria de Segurança, Arquitetura e UX — Histórico Egídio

Data da revisão: 10/10/2026

## Stack auditada

- Backend: Python 3.13 + Django 5.2.7
- Servidor: Gunicorn 23
- Estáticos: WhiteNoise
- Banco atual: SQLite persistido em `data/historico.sqlite3`
- Execução: Docker / Docker Compose
- Importações: XLS/XLSX (openpyxl/xlrd) e PDF (pdfplumber)
- Frontend: Django Templates + CSS + JavaScript

> Este documento registra controles técnicos de privacidade e segurança. Ele não substitui avaliação jurídica/encarregado de dados para afirmar conformidade legal integral com a LGPD.

# PASSO 1 — Segurança e conformidade

## Achados críticos encontrados

1. Páginas de busca, aluno e impressão aceitavam acesso sem autenticação.
2. `ALLOWED_HOSTS=*` e chave Django fixa estavam no compose.
3. Não havia política forte de senha.
4. Não existia trilha estruturada de auditoria.
5. O histórico não possuía prova pública de autenticidade.
6. Uploads temporários tinham permissões padrão do sistema operacional.
7. XLSX não possuía proteção específica contra arquivos compactados maliciosos.
8. Fontes eram carregadas do Google, gerando requisição a terceiro.
9. Não havia distinção entre documento em edição e documento oficialmente emitido.

## Controles implementados

### Controle de acesso / IDOR

- Nesta fase de desenvolvimento, o módulo de Histórico Escolar permanece sem autenticação própria, por decisão de integração: ele será incorporado ao sistema principal, que fornecerá usuário/senha e controle de sessão.
- O Django Admin continua protegido pela autenticação nativa do Django.
- A validação pública continua separada e revela apenas dados mínimos mascarados.
- Antes de expor o módulo fora do ambiente controlado, a autenticação do sistema principal deverá proteger todas as rotas operacionais.
- Consultas usam Django ORM; não há SQL montado com texto fornecido pelo usuário.

### Criptografia de integridade e antifraude

Foi criado `DocumentoHistorico` com:

- UUID público não sequencial;
- snapshot imutável do conteúdo emitido;
- SHA-256 do JSON canônico;
- HMAC-SHA256 usando chave dedicada;
- emissor e data/hora;
- suporte à revogação;
- QR Code local apontando para a validação pública.

A chave de assinatura é persistida em `data/.document_signing_key`; não é versionada.

### Auditoria

Foi criado `AuditoriaEvento`, com:

- usuário responsável;
- ação;
- entidade e identificador;
- request-id;
- data/hora;
- método/caminho;
- hash do IP, sem gravar o IP puro;
- metadados mínimos da operação.

O middleware `SecurityAuditMiddleware` gera request-id e registra operações mutáveis sem armazenar conteúdo bruto de formulários/arquivos.

Alterações de notas pelo Django Admin possuem auditoria específica.

### LGPD / minimização

- página pública usa nome e código mascarados;
- CPF, filiação, notas, identidade e nascimento completo não aparecem na validação pública;
- nascimento é mascarado na listagem de busca;
- IP é armazenado apenas como hash salgado;
- arquivos temporários usam diretório 0700 e arquivo 0600;
- arquivos temporários são excluídos após aplicação e expiram;
- fontes externas do Google foram removidas;
- logs técnicos de importação não imprimem nome do aluno.

### Cabeçalhos e sessão

Implementados:

- CSP;
- X-Content-Type-Options;
- X-Frame-Options;
- Referrer-Policy;
- Permissions-Policy;
- SameSite;
- sessão HTTPOnly;
- configuração opcional para cookies Secure, redirect HTTPS e HSTS;
- sessão padrão de 1 hora;
- validação forte de senha (mínimo 12 caracteres + validadores Django).

# PASSO 2 — Arquitetura e banco

## Relacionamentos

O desenho principal permanece:

`Aluno -> RegistroAcademico -> Nota`

A unicidade de nota continua por:

`RegistroAcademico + Componente`

Isso preserva corretamente até cinco notas de uma mesma disciplina para o aluno, pois cada ano/série possui seu próprio `RegistroAcademico`.

Foram adicionados índices para:

- aluno + ano + série;
- ano + série + turma;
- auditoria por ação/data;
- auditoria por entidade/id.

## Versionamento da matriz curricular

Criados:

- `MatrizCurricularVersao`
- `MatrizComponente`

Uma matriz possui vigência, componentes, carga horária, peso, ordem e obrigatoriedade.

`ConfiguracaoAno` pode apontar para a matriz oficial daquele ano e cada `RegistroAcademico` guarda sua própria referência. Assim, alterar a matriz utilizada em anos futuros não altera a interpretação de registros passados.

## SQLite

Foi habilitado:

- foreign_keys;
- WAL;
- busy_timeout;
- synchronous=NORMAL.

O SQLite continua apropriado para o servidor atual de baixa concorrência. Para múltiplos usuários simultâneos, alta disponibilidade ou integração externa intensa, PostgreSQL deve ser a próxima evolução de infraestrutura.

# PASSO 3 — Recursos inteligentes implementados

## 1. Média acadêmica ponderada

A média utiliza pesos definidos na versão da matriz curricular. Sem matriz/peso específico, usa peso 1.

Ela é apresentada como indicador operacional e não altera automaticamente a regra legal do histórico.

## 2. Alertas acadêmicos automáticos

São calculados por registro:

- nota abaixo do mínimo configurado;
- frequência abaixo de 75%;
- componentes obrigatórios sem nota;
- resultado final ausente.

## 3. Painel de integridade dos dados

Foi criada tela específica que identifica:

- aluno com dados essenciais incompletos;
- registro sem notas;
- registro sem matriz;
- nome exatamente duplicado.

## 4. Dashboard institucional

A página inicial agora mostra:

- alunos;
- registros;
- notas;
- históricos autenticados;
- pendências de qualidade;
- emissões recentes;
- busca de aluno;
- atalhos operacionais.

# PASSO 4 — UI/UX e documento

## Diretrizes aplicadas

- verde institucional como cor primária;
- tipografia local/system para reduzir dependência externa;
- hierarquia visual clara;
- componentes responsivos;
- ações destrutivas isoladas;
- feedback de importação antes de gravar;
- histórico A4 preservado;
- modo de edição separado de emissão autenticada.

## Histórico oficial

O documento oficial mantém o modelo A4 e recebeu, quando emitido:

- QR Code;
- prefixo do SHA-256;
- UUID da emissão no modo operador;
- validação pública;
- snapshot que impede alterações posteriores de modificarem o documento já emitido.

A prévia continua editável pela secretaria; a versão autenticada é somente leitura.

# PASSO 5 — Plano de implantação

## Alta prioridade

- [x] Aplicar migrations 0005 e 0006.
- [x] Rebuild da imagem Docker por causa da dependência `qrcode`.
- [ ] Definir domínio HTTPS real em `DJANGO_ALLOWED_HOSTS`.
- [ ] Com HTTPS ativo, configurar `DJANGO_SECURE_COOKIES=1`.
- [ ] Com HTTPS ativo, configurar `DJANGO_SECURE_SSL_REDIRECT=1`.
- [ ] Após validar HTTPS por alguns dias, configurar HSTS.
- [ ] Fazer backup do SQLite antes da implantação.
- [ ] Testar a emissão autenticada no próprio sistema (snapshot, SHA-256 e registro de auditoria). A leitura externa do QR Code fica adiada por enquanto.
- [ ] Controle de contas staff/superuser fica adiado nesta etapa, pois o sistema será incorporado a outro sistema que já exige usuário e senha.

## Média prioridade

- [ ] Cadastrar as versões reais das matrizes curriculares, sem inventar vigências.
- [ ] Vincular cada `ConfiguracaoAno` à matriz correta.
- [ ] Tratar os registros apontados na tela Integridade.
- [ ] Programar backup diário criptografado e teste mensal de restauração.
- [ ] Quando ocorrer a integração com o sistema principal, proteger todas as rotas operacionais usando a autenticação central do sistema e validar o repasse seguro de identidade/permissões ao Django.
- [ ] Até essa integração, manter este módulo apenas em ambiente controlado/rede interna, pois as telas operacionais estão deliberadamente sem login próprio.
- [ ] Planejar PostgreSQL antes de ampliar a quantidade de operadores simultâneos.

## Baixa prioridade / evolução

- [ ] Política formal de retenção de logs de auditoria.
- [ ] Rotina de exportação de relatório de auditoria.
- [ ] Fluxo de solicitação LGPD (acesso/correção conforme base legal e política da instituição).
- [ ] Monitoramento de disponibilidade e espaço em disco.
- [ ] Testes de impressão automatizados por navegador headless para regressão visual.

## Operação recomendada para deploy

```bash
cd /srv/projetos/historico_egidio
cp data/historico.sqlite3 data/historico-pre-seguranca-$(date +%F-%H%M).sqlite3
git pull
docker compose up -d --build
docker compose logs --tail=150 web
docker compose exec web python manage.py showmigrations historico
```

As migrations esperadas ao final incluem:

- `0005_seguranca_auditoria_matriz_documentos`
- `0006_indices_registro_academico`
