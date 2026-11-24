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

## Importação de fotografias

Na pasta `ComputerVisionPython`, instale o pacote atualizado e aplique a migração conforme a seção **Persistência local com SQLite**. A revisão atual deve ser `0002_image_import`.

O importador aceita imagens estáticas JPEG, PNG e WebP e identifica o formato pelo conteúdo. A foto original é copiada para `dataset/raw/<prefixo-do-hash>/<sha256>.<extensão>`. O caminho registrado é relativo a `dataset/raw`, ou à pasta passada em `storage_root`. Use a mesma pasta de armazenamento para as importações de um catálogo.

Execute esta demonstração no PowerShell. Ela gera dois arquivos sintéticos, importa ambos e tenta importar o primeiro novamente:

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from PIL import Image
from mfi_cv.data import CaptureSession, MotorModel, MotorUnit
from mfi_cv.data.database import create_database_engine
from mfi_cv.data.image_import import DuplicateImageError, import_photo
from mfi_cv.data.repository import MotorRepository

tag = uuid4().hex
model = MotorModel(f"modelo-{tag}", "Fabricante ficticio", "Linha ficticia",
                   "Modelo ficticio", "Fonte ficticia")
unit = MotorUnit(f"exemplar-{tag}", model)
session = CaptureSession(f"sessao-{tag}")
engine = create_database_engine()
with engine.begin() as connection:
    repository = MotorRepository(connection)
    repository.add_model(model)
    repository.add_unit(unit)
    repository.add_session(session)

metadata = dict(unit_id=unit.unit_id, session_id=session.session_id,
                origin="Imagem sintetica de demonstracao", capture_angle_deg=45)
with TemporaryDirectory() as temp:
    photo = Image.frombytes("RGB", (8, 8), bytes.fromhex(tag) * 12)
    files = [Path(temp) / "demo.png", Path(temp) / "demo.jpg"]
    for source in files:
        photo.save(source)
        imported = import_photo(engine, source, **metadata)
        print(imported.original_filename, Path("dataset/raw") / imported.path)
    try:
        import_photo(engine, files[0], **metadata)
    except DuplicateImageError as error:
        print("Duplicata da imagem", error.image_id)
engine.dispose()
'@ | .\.venv\Scripts\python.exe -
```

A saída deve mostrar os dois caminhos e, na última linha, o ID do registro da primeira foto. O SHA-256 identifica arquivos com bytes idênticos. Uma nova codificação da mesma foto pode produzir um hash diferente.

## Relatório de qualidade das fotografias

Na pasta `ComputerVisionPython`, execute no PowerShell:

```powershell
.\.venv\Scripts\python.exe -m mfi_cv.data.image_quality .\dataset\raw |
    Set-Content -Encoding ASCII .\dataset\relatorio-qualidade.json
Get-Content .\dataset\relatorio-qualidade.json -Raw | ConvertFrom-Json |
    Select-Object -ExpandProperty files |
    Where-Object { $_.issues.Count -gt 0 } |
    Format-Table path, width, height, sharpness, issues -AutoSize
```

O relatório tem caminhos relativos à pasta analisada. Abra os arquivos sinalizados para revisão visual. `invalid_image` indica conteúdo corrompido ou incompatível com os formatos estáticos aceitos. `unreadable` indica falha na leitura dos bytes, e `duplicate` indica conteúdo idêntico por SHA-256. Todos os caminhos de uma duplicata também aparecem em `duplicate_groups`.

A resolução recebe `low_resolution` quando o menor lado tem menos que `--min-side` pixels (padrão 640). A nitidez recebe `low_sharpness` quando a variância do Laplaciano fica abaixo de `--min-sharpness` (padrão 100). O Laplaciano mede diferenças locais de intensidade. Sua variância costuma cair quando o desfoque suaviza bordas. A métrica usa tons de cinza, limita o maior lado a 512 pixels sem ampliar e registra `null` se a imagem resultante for pequena demais para a janela de 3 × 3 pixels.

Os limites são iniciais e servem para triagem. Textura, ruído e iluminação também afetam a métrica. O relatório preserva as fotos e seus status no catálogo. Pastas e arquivos iniciados por ponto, incluindo os temporários do importador, são ignorados. Rode a análise com a pasta estável para reproduzir o resultado.

## Exportação do dataset de classificação

Na pasta `ComputerVisionPython`, com o catálogo migrado e as fotos aprovadas no armazenamento, execute:

```powershell
.\.venv\Scripts\python.exe -m mfi_cv.data.classification_dataset --source .\dataset\raw --output .\dataset\classification --seed 42
$manifesto = Get-Content .\dataset\classification\manifest.json -Raw -Encoding UTF8 | ConvertFrom-Json
$manifesto.classes | ConvertTo-Json -Depth 5
$manifesto.warnings
```

O comando lê o banco definido por `MFI_DATABASE_URL` ou o SQLite local. A saída deve ser uma pasta nova. Para verificar a repetibilidade, execute com a mesma seed e outra pasta de saída, com catálogo e arquivos estáveis, e compare o SHA-256 dos dois manifestos com `Get-FileHash`.

O manifesto mapeia as pastas de classe aos IDs comerciais e registra origem, hash, exemplar, sessão e partição de cada arquivo exportado. O exportador mantém juntos os registros ligados por exemplar, sessão ou SHA-256, inclusive por vínculos transitivos. Vínculos do catálogo podem incluir fotos pendentes ou rejeitadas. Somente as aprovadas são copiadas.

A divisão reserva treino para cada classe e tenta alocar cerca de 15% dos grupos por classe para validação e 15% para teste, priorizando cobertura em ambas. Os percentuais são metas para grupos, e a quantidade de fotos pode variar entre partições. Consulte `missing_splits` e `warnings` antes de usar o dataset para avaliação. Classes sem fotos aprovadas ficam fora da exportação. Se nenhuma foto estiver aprovada, o comando termina com erro e a saída não é publicada.

Para verificar o fluxo com dados sintéticos, sem alterar o catálogo local, execute:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_classification_dataset.py
```
