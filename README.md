# Histórico Egídio

Sistema web para emissão e administração de históricos escolares da Escola Municipal Egídio Cordeiro Aquino.

## Arquitetura atual

A aplicação **não usa Excel durante o funcionamento**. Os dados são armazenados em banco SQLite próprio e o sistema trabalha com entidades relacionais:

- Alunos
- Configurações por ano letivo
- Registros acadêmicos
- Turmas e séries
- Notas por componente curricular
- Faltas
- Resultado final
- Histórico escolar para impressão

As regras principais que estavam nas fórmulas do Excel foram migradas para Python, incluindo:

- média mínima por ano;
- situação APTO;
- resultados APROVADO, EM CONTINUIDADE e Em Curso;
- conversão de faltas para horas;
- tratamento especial do ano de 2020;
- carga horária e dias letivos por ano.

## Migração dos dados antigos

O arquivo Excel original foi usado somente como **fonte de conversão**. Foi gerado um pacote privado chamado:

`migracao_inicial_historico_egidio.json`

Esse arquivo contém dados pessoais de alunos e, por segurança, **não fica no GitHub público**.

Coloque-o uma única vez em:

```
data/migracao_inicial_historico_egidio.json
```

Na primeira inicialização, o container cria o banco e importa esse pacote automaticamente. Depois disso o sistema utiliza somente:

```
data/historico.sqlite3
```

Após confirmar a migração, o JSON também pode ser removido do servidor.

## Instalação com Docker

```bash
git clone https://github.com/Paulo-Andre/historico_egidio.git
cd historico_egidio
mkdir -p data
# copiar migracao_inicial_historico_egidio.json para ./data/
docker compose build
docker compose up -d
```

Acompanhe a primeira carga:

```bash
docker compose logs -f web
```

O log deve informar a quantidade de alunos, registros acadêmicos e notas migradas.

Acesse:

```
http://IP_DO_SERVIDOR:8000
```

## Administração

Crie o usuário administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

Depois acesse:

```
http://IP_DO_SERVIDOR:8000/admin/
```

No painel é possível cadastrar e editar alunos, registros acadêmicos, resultados, faltas, notas e configurações anuais sem utilizar Excel.

## Backup

O banco fica em:

```
data/historico.sqlite3
```

Para backup, basta copiar esse arquivo com o container parado ou utilizar uma rotina de backup consistente para SQLite.
