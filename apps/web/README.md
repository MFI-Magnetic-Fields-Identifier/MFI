# MFI — Seleção manual de motores

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
