# MFI — Visão computacional

O comando inicial verifica se o pacote `mfi_cv` foi instalado e pode ser executado.

## Configuração no Windows PowerShell

Use Python 3.11 ou superior com `venv` e `pip`. A partir da raiz do repositório:

```powershell
Set-Location .\ComputerVisionPython
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
```

O comando instala o pacote em modo editável e inclui o pytest. Os comandos abaixo usam diretamente o Python do ambiente virtual, sem precisar ativá-lo.

## Execução e testes

Na pasta `ComputerVisionPython`, execute:

```powershell
.\.venv\Scripts\python.exe -m mfi_cv
.\.venv\Scripts\python.exe -m mfi_cv --help
.\.venv\Scripts\python.exe -m pytest
```

O primeiro comando deve imprimir `MFI CV: ambiente Python pronto.` e o segundo deve mostrar a ajuda. Para verificar a rejeição de parâmetros desconhecidos, execute:

```powershell
.\.venv\Scripts\python.exe -m mfi_cv --invalido
$LASTEXITCODE
```

O comando deve indicar o argumento inválido e retornar o código `2`.

## Persistência local com SQLite

Na pasta `ComputerVisionPython`, instale as dependências e aplique a migração:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
Remove-Item Env:MFI_DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

O banco local fica em `mfi_cv.sqlite3`, ignorado pelo Git. Use estes dados fictícios para verificar o cadastro e a consulta em conexões separadas:

```powershell
@'
from uuid import uuid4
from mfi_cv.data import MotorModel
from mfi_cv.data.database import create_database_engine
from mfi_cv.data.repository import MotorRepository

model = MotorModel(f"demo-{uuid4()}", "Fabricante ficticio", "Linha ficticia",
                   "Modelo ficticio", "Fonte ficticia")
engine = create_database_engine()
with engine.begin() as connection:
    MotorRepository(connection).add_model(model)
with engine.connect() as connection:
    repository = MotorRepository(connection)
    print(repository.get_model(model.model_id))
    print(repository.get_model("id-ausente"))
engine.dispose()
'@ | .\.venv\Scripts\python.exe -
```

A consulta deve imprimir o modelo cadastrado e, para o ID ausente, `None`. Use `engine.begin()` para agrupar cadastros em uma transação. Um ID duplicado ou uma referência estrangeira ausente gera `sqlalchemy.exc.IntegrityError`. Trate essa exceção fora do bloco da transação para que o SQLAlchemy reverta os cadastros do bloco.

## PostgreSQL

Instale o driver opcional, configure `MFI_DATABASE_URL` no ambiente da sessão e aplique a mesma migração a um banco PostgreSQL existente, com permissão para criar tabelas. O valor abaixo usa apenas dados fictícios:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[postgres]'
$env:MFI_DATABASE_URL = 'postgresql+psycopg://usuario:senha@localhost:5432/mfi'
.\.venv\Scripts\python.exe -m alembic upgrade head
```
