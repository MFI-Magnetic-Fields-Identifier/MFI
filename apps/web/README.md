# MFI — Seleção e identificação de motores

A tela usa o catálogo JSON em `src/profiles.json`. Os perfis monofásico e trifásico contêm valores ilustrativos de frequência, fases e polos.

## Executar no Windows PowerShell

A partir da raiz do repositório, use Node.js 20.19 ou superior na série 20, ou Node.js 22.12 ou superior:

```powershell
Set-Location .\apps\web
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Abra a URL local mostrada pelo Vite. Com a API Python desligada, alterne entre os perfis. O cartão de detalhes deve atualizar de 1 fase e 4 polos para 3 fases e 6 polos. Também é possível selecionar com Tab e as setas do teclado.

## Verificar a compilação

Na pasta `apps/web`, execute:

```powershell
npm.cmd run build
```

Esse comando verifica os tipos TypeScript e gera a versão estática em `dist/`.

## Identificar por foto

Em outro PowerShell, na raiz do repositório, inicie a API. O exemplo usa o checkpoint sintético gerado na etapa 4.1:

```powershell
Set-Location .\ComputerVisionPython
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:MFI_CHECKPOINT = (Resolve-Path .\models\demo-v1\best.pt).Path
.\.venv\Scripts\python.exe -m uvicorn mfi_cv.api:app --host 127.0.0.1 --port 8000
```

No frontend, selecione um JPEG, PNG ou WebP de até 8 MiB e clique em **Enviar foto**. Para verificar a integração com dados sintéticos, escolha um PNG de `ComputerVisionPython/dataset/raw/`. A tela deve mostrar o estado da identificação e os candidatos `demo-*` com suas pontuações. Para verificar indisponibilidade, pare a API e envie a foto novamente. A seleção manual deve continuar funcionando.

O Vite encaminha `POST /predict` para `http://127.0.0.1:8000` tanto em desenvolvimento quanto em preview. Se a API estiver em outra porta, defina `$env:MFI_API_TARGET` antes de iniciar o Vite. Ao servir `dist/` em outro servidor, configure o encaminhamento de `/predict` na mesma origem.
