Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " Instalador do Auto Flow" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Requisita interface gráfica para seleção da pasta
Add-Type -AssemblyName System.Windows.Forms
$browser = New-Object System.Windows.Forms.FolderBrowserDialog
$browser.Description = "Selecione a pasta onde deseja instalar o Auto Flow"
$browser.ShowNewFolderButton = $true

# Traz a janela para frente
$mainForm = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}
$result = $browser.ShowDialog($mainForm)

if ($result -ne [System.Windows.Forms.DialogResult]::OK -or [string]::IsNullOrWhiteSpace($browser.SelectedPath)) {
    Write-Host "Instalação cancelada pelo usuário (Nenhuma pasta selecionada)." -ForegroundColor Red
    exit
}

$installPath = $browser.SelectedPath
$appFolder = Join-Path $installPath "AutoFlow"

if (-not (Test-Path $appFolder)) {
    New-Item -ItemType Directory -Force -Path $appFolder | Out-Null
}
Write-Host "Pasta de instalação: $appFolder" -ForegroundColor Green

# 2. Verificação do Python
$pythonInstalled = $false
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python verificado localmente: $pythonVersion" -ForegroundColor Green
    $pythonInstalled = $true
} else {
    Write-Host "❌ Python não encontrado. Baixando e instalando Python 3.12..." -ForegroundColor Yellow
    $pythonInstallerPath = "$env:TEMP\python-installer.exe"
    $pythonUrl = "https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe"
    
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstallerPath -UseBasicParsing
        
        Write-Host "Executando instalador do Python em modo silencioso (Isso pode demorar alguns minutos)..." -ForegroundColor Yellow
        $installArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0"
        Start-Process -FilePath $pythonInstallerPath -ArgumentList $installArgs -Wait -NoNewWindow
        
        # Atualiza a variável PATH da sessão atual
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        if (Get-Command "python" -ErrorAction SilentlyContinue) {
            Write-Host "✅ Python instalado e adicionado ao PATH com sucesso!" -ForegroundColor Green
            $pythonInstalled = $true
        } else {
            Write-Host "Erro: Falha ao instalar ou detectar o Python após instalação. Instale-o manualmente, marque 'Add to PATH' e tente novamente." -ForegroundColor Red
            exit
        }
    } catch {
        Write-Host "Erro ao tentar baixar o Python: $_" -ForegroundColor Red
        exit
    }
}

# 3. Baixar o Código-Fonte do Repositório do GitHub
Write-Host "📥 Baixando os arquivos do Auto Flow..." -ForegroundColor Cyan
$repoZip = "$env:TEMP\AutoFlow-main.zip"

# O repositório oficial do Auto Flow no GitHub
$repoUrl = "https://github.com/iagoiagodev/Auto-Flow/archive/refs/heads/main.zip"

try {
    Write-Host "Fazendo o download do repositório..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $repoUrl -OutFile $repoZip -UseBasicParsing
    
    Write-Host "Extraindo arquivos do ZIP..." -ForegroundColor Yellow
    # Caso esteja no PowerShell 5, Microsoft.PowerShell.Archive vem por padrão
    Expand-Archive -Path $repoZip -DestinationPath $env:TEMP -Force
    
    # Copiar o conteúdo da pasta extraída para o destino
    $extractedFolder = "$env:TEMP\AutoFlow-main"
    Copy-Item -Path "$extractedFolder\*" -Destination $appFolder -Recurse -Force
    
    # Limpeza dos arquivos temporários
    Remove-Item $repoZip -Force
    Remove-Item $extractedFolder -Recurse -Force
    Write-Host "✅ Arquivos do projeto instalados com sucesso na pasta!" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Não foi possível baixar diretamente do repositório 'iagoiagodev/Auto-Flow'." -ForegroundColor Red
    Write-Host "Certifique-se de ter acesso à internet ou que o link está correto." -ForegroundColor Yellow
    Write-Host "Detalhe do erro: $_ " -ForegroundColor Red
    # Não cancelamos a instalação aqui pois o usuário pode usar o script localmente copiando os arquivos se desejar.
}

# 4. Instalar Dependências do Projeto
Write-Host "📦 Instalando dependências (Módulos do Python)..." -ForegroundColor Cyan
Set-Location $appFolder

try {
    python -m pip install --upgrade pip --quiet
    Write-Host "Aguarde, instalando customtkinter, opencv, pyautogui, etc..." -ForegroundColor Yellow
    python -m pip install customtkinter pystray Pillow pyautogui opencv-python pyperclip keyboard mouse pyinstaller --quiet
    Write-Host "✅ Todos os pacotes Python foram instalados!" -ForegroundColor Green
} catch {
    Write-Host "Erro ao tentar instalar pacotes Python via pip." -ForegroundColor Red
}

# 5. Criar um .bat de Ativação
Write-Host "⚙️ Criando atalho .bat para iniciar..." -ForegroundColor Cyan
$batContent = "@echo off`nchcp 65001 >nul`ncd /d `"%~dp0`"`npython main.py`npause"
$batPath = Join-Path $appFolder "Executar AutoFlow.bat"
Set-Content -Path $batPath -Value $batContent -Encoding UTF8

Write-Host "===================================================" -ForegroundColor Green
Write-Host " 🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""
Write-Host "O Auto Flow foi instalado na seguinte pasta:" -ForegroundColor White
Write-Host " > $appFolder" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para executar, basta ir na pasta e dar dois cliques em 'Executar AutoFlow.bat'." -ForegroundColor White
Write-Host "Boa sorte e boa automação!" -ForegroundColor White

Start-Sleep -Seconds 5
