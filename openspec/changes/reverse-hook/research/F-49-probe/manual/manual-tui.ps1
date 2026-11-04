# Ручная проба F-49 в интерактивном клиенте. Нужны PowerShell и opencode в PATH. Запускает человек, агент этого не проверял.
#   .\manual-tui.ps1 setup            создать временный проект рядом с плагином пробы, вывести путь
#   .\manual-tui.ps1 wake "текст"     строка в файле событий: session.prompt в последней сессии каталога
#   .\manual-tui.ps1 wake "текст" queue
#   .\manual-tui.ps1 wake "текст" steer
#   .\manual-tui.ps1 synthetic "текст"
#   .\manual-tui.ps1 log              что записал плагин
#   .\manual-tui.ps1 clean            удалить сессии из журнала и временный проект
param([Parameter(Position = 0)][string]$Op = "setup", [Parameter(Position = 1)][string]$Text = "", [Parameter(Position = 2)][string]$Delivery = "")

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$pointer = Join-Path $env:TEMP "f49-manual-project.txt"

function Project {
  if (-not (Test-Path $pointer)) { throw "Сначала .\manual-tui.ps1 setup" }
  return (Get-Content -LiteralPath $pointer -Encoding utf8 -TotalCount 1)
}

switch ($Op) {
  "setup" {
    $root = Join-Path $env:TEMP ("f49-manual-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Force -Path (Join-Path $root ".opencode\plugins"), (Join-Path $root ".symphysis\viewer"), (Join-Path $root "openspec\changes\demo\answers") | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "manual-plugin.js") -Destination (Join-Path $root ".opencode\plugins\f49-manual.js")
    Set-Content -LiteralPath (Join-Path $root "openspec\changes\demo\answers\2026-11-04.md") -Value "# Ответы`n`nМАРКЕР-ОТВЕТА: ОЛЬХА-7141" -Encoding utf8
    Set-Content -LiteralPath (Join-Path $root "opencode.json") -Value '{ "model": "ollama-cloud/deepseek-v4.1-flash" }' -Encoding utf8
    git -C $root init -q
    Set-Content -LiteralPath $pointer -Value $root -Encoding utf8
    Write-Output "Проект: $root"
    Write-Output "Окно 1, без фоновой службы (навыки из ~/.claude модели не уйдут):"
    Write-Output "  cd `"$root`"; `$env:OPENCODE_DISABLE_CLAUDE_CODE = '1'; opencode --standalone"
    Write-Output "Окно 2: .\manual-tui.ps1 wake `"Открой файл openspec/changes/demo/answers/2026-11-04.md и ответь строкой со словом МАРКЕР`""
    Write-Output "Что смотреть: research/F-49.md, раздел «Проба», подраздел «Что проверить руками»."
  }
  { $_ -in "wake", "synthetic" } {
    $row = @{ op = $(if ($Op -eq "synthetic") { "synthetic" } else { "prompt" }); text = $Text }
    if ($Delivery) { $row.delivery = $Delivery }
    $line = ($row | ConvertTo-Json -Compress) + "`n"
    [System.IO.File]::AppendAllText((Join-Path (Project) ".symphysis\viewer\events.jsonl"), $line, [System.Text.UTF8Encoding]::new($false))
    Write-Output "Строка записана. Журнал плагина: .\manual-tui.ps1 log"
  }
  "log" { Get-Content -LiteralPath (Join-Path (Project) ".symphysis\viewer\probe.log") -Encoding utf8 }
  "clean" {
    $root = Project
    $log = Join-Path $root ".symphysis\viewer\probe.log"
    $ids = @()
    if (Test-Path -LiteralPath $log) { $ids = Select-String -LiteralPath $log -Pattern 'ses_[A-Za-z0-9]+' -AllMatches | ForEach-Object { $_.Matches.Value } | Sort-Object -Unique }
    foreach ($id in $ids) {
      Write-Output "Удаляю сессию $id"
      opencode session delete --standalone $id
    }
    Write-Output "Осталось снять вручную: файл плагина держит наблюдатель, пока жив сервер. Закрой TUI, затем:"
    Write-Output "  Remove-Item -LiteralPath `"$root`" -Recurse -Force; Remove-Item -LiteralPath `"$pointer`""
  }
  default { throw "Нет такой команды: $Op" }
}
