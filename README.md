# Auto Flow

**Auto Flow** é uma ferramenta de automação desktop baseada em Python que permite criar e executar fluxos de trabalho (workflows) de forma fácil e interativa.
Com essa aplicação, você não precisa programar para realizar automações de cliques, teclado e buscas na tela.
Basta abrir a ferramenta, selecionar suas ações (ex: mover o mouse, digitar um texto, ou aguardar uma imagem específica) e o Auto Flow fará tudo sozinho de acordo com a sua configuração.

## 📦 Instalação Rápida (Recomendado)

Você pode instalar o Auto Flow facilmente usando nosso script de instalação rápida. Ele verificará se você tem o Python instalado (baixando-o e instalando, se necessário) e configurará todo o ambiente.

Abra o **PowerShell** em modo Administrador e cole o seguinte comando:

```powershell
iwr -useb https://raw.githubusercontent.com/iagoiagodev/Auto-Flow/main/install.ps1 | iex
```

> **Nota:** Um explorador de arquivos será aberto para você escolher a pasta onde deseja instalar o Auto Flow.

## 🚀 Funcionalidades Principais

* **Criação e Execução de Workflows**: Automação de cliques, digitação, movimentação do mouse e mais.
* **Reconhecimento de Imagens (`wait_image`)**: Aguarde até que um elemento específico apareça na tela antes de continuar a execução usando OpenCV.
* **Atalhos Globais (Hotkeys)**: Controle seus fluxos de automação através de atalhos de teclado mesmo com o aplicativo minimizado.
* **Captura de Tela**: Ferramenta integrada para tirar screenshots rápidos e usá-los nas suas automações.
* **Bandeja do Sistema (Systray)**: O aplicativo pode ser minimizado para a bandeja do sistema, rodando silenciosamente em segundo plano.
* **Interface Moderna**: Construído com `customtkinter` para um visual elegante e intuitivo.

## 🛠️ Instalação Manual a partir do Código-Fonte

Caso prefira configurar tudo manualmente:

1. Instale o [Python 3.11 ou 3.12](https://www.python.org/downloads/) (marque a opção **"Add Python to PATH"**).
2. Clone este repositório ou baixe o código fonte:
   ```cmd
   git clone https://github.com/iagoiagodev/Auto-Flow.git
   cd Auto-Flow
   ```
3. Instale as dependências executando:
   ```cmd
   pip install customtkinter pystray Pillow pyautogui opencv-python pyperclip keyboard mouse pyinstaller
   ```
4. Execute o aplicativo:
   ```cmd
   python main.py
   ```

## 🏗️ Estrutura de Diretórios 

Após a primeira execução, o Auto Flow criará as seguintes pastas:

* `workflows/`: Onde seus fluxos de automação salvos ficarão armazenados (arquivos não sofrem controle de versão).
* `assets/templates/`: Imagens de referência usadas no comando de espera por imagem.
* `assets/screenshots/`: Capturas de tela geradas pelo app.

## 📝 Observações

* Caso ocorra um erro de "Windows protegeu seu computador" ao rodar um executável compilado, clique em "Mais informações" e depois "Executar assim mesmo". Isso ocorre temporariamente pela ausência de um certificado digital.
* Para fechar a aplicação completamente, clique com o botão direito no ícone do Auto Flow na bandeja do sistema e selecione "Sair".

---

# Build e Distribuição

## Como as dependências funcionam

O PyInstaller **embute todas as dependências dentro do `.exe`** (ou da pasta gerada).
Quem instala o AutoFlow **não precisa ter Python, pip, ou nada instalado** — o executável
já carrega customtkinter, pyautogui, keyboard, etc. internamente.

O que o installer/ZIP precisa criar na máquina do usuário são apenas as **pastas de dados**
que o app usa em runtime:
- `workflows/` — onde os arquivos `.json` são salvos
- `assets/templates/` — imagens de referência para `wait_image`
- `assets/screenshots/` — screenshots gerados pelo app

---

## Pré-requisito: gerar o executável

Antes de criar o installer ou o ZIP, compile o app com PyInstaller:

```
pip install pyinstaller
```

```
pyinstaller --onedir --windowed --name AutoFlow --noupx ^
  --add-data "assets;assets" ^
  main.py
```

| Flag | Por quê |
|---|---|
| `--onedir` | Gera uma pasta `dist\AutoFlow\` com o `.exe` e DLLs separadas — **menos falsos positivos** que `--onefile` |
| `--windowed` | Sem janela de console |
| `--noupx` | Desativa compressão UPX, que ativa heurísticas de antivírus |
| `--add-data "assets;assets"` | Inclui a pasta de assets no pacote |

O resultado fica em `dist\AutoFlow\` — é essa pasta que vai para o installer ou ZIP.

---

## Opção A — Installer com Inno Setup

**Quando usar:** quer uma experiência profissional com atalhos, desinstalador e integração com o Windows.

### 1. Instalar o Inno Setup
Baixe em: https://jrsoftware.org/isinfo.php (gratuito)

### 2. Criar o script `installer.iss`

Salve o arquivo abaixo na raiz do projeto:

```iss
[Setup]
AppName=AutoFlow
AppVersion=1.0.0
AppPublisher=Seu Nome
DefaultDirName={autopf}\AutoFlow
DefaultGroupName=AutoFlow
OutputDir=installer_output
OutputBaseFilename=AutoFlow_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar ícone na Área de Trabalho"; GroupDescription: "Ícones:"
Name: "startupicon"; Description: "Iniciar AutoFlow com o Windows"; GroupDescription: "Inicialização:"

[Files]
; Copia tudo que o PyInstaller gerou (--onedir)
Source: "dist\AutoFlow\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Dirs]
; Cria as pastas de dados que o app precisa em runtime
Name: "{app}\workflows"
Name: "{app}\assets\templates"
Name: "{app}\assets\screenshots"

[Icons]
Name: "{group}\AutoFlow"; Filename: "{app}\AutoFlow.exe"
Name: "{group}\Desinstalar AutoFlow"; Filename: "{uninstallexe}"
Name: "{userdesktop}\AutoFlow"; Filename: "{app}\AutoFlow.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "AutoFlow"; \
  ValueData: """{app}\AutoFlow.exe"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\AutoFlow.exe"; Description: "Executar AutoFlow agora"; \
  Flags: nowait postinstall skipifsilent
```

### 3. Compilar o installer

1. Abra o **Inno Setup Compiler**
2. `File → Open` → selecione `installer.iss`
3. `Build → Compile` (ou `Ctrl+F9`)
4. O installer gerado fica em `installer_output\AutoFlow_Setup_1.0.0.exe`

O usuário final só precisa rodar esse único arquivo. O installer cria as pastas, atalhos e desinstalador automaticamente.

---

## Opção B — ZIP portátil

**Quando usar:** distribuição simples, sem instalação. Usuário extrai e roda.
Mais fácil de manter e menos bloqueado por antivírus corporativos.

### 1. Preparar a pasta antes de zipar

Após rodar o PyInstaller (`dist\AutoFlow\`), crie as pastas de dados dentro dela:
```
mkdir dist\AutoFlow\workflows
mkdir dist\AutoFlow\assets\templates
mkdir dist\AutoFlow\assets\screenshots
```

Adicione também um arquivo `LEIA-ME.txt` dentro da pasta:
```
AutoFlow v1.0.0

Como usar:
1. Extraia esta pasta para qualquer local (ex: C:\AutoFlow)
2. Execute AutoFlow.exe
3. Seus workflows serão salvos na pasta "workflows\"

Não mova o AutoFlow.exe para fora desta pasta.
```

### 2. Zipar
```
# PowerShell
Compress-Archive -Path "dist\AutoFlow" -DestinationPath "AutoFlow_v1.0.0.zip"
```

Ou com 7-Zip (melhor compressão):
```
7z a -mx=9 AutoFlow_v1.0.0.zip .\dist\AutoFlow\
```

Distribua o `.zip` via GitHub Releases, Google Drive, etc.

---

## Como projetos open source no GitHub evitam bloqueio de antivírus sem pagar

Projetos grandes (ex: Keypirinha, AutoHotkey apps, scripts de automação) usam uma
combinação de estratégias gratuitas:

### 1. Código aberto visível
O repositório público funciona como prova de intenção. Antivírus como Windows Defender
e Kaspersky têm programas de whitelisting para projetos open source verificados.
- Microsoft: https://www.microsoft.com/en-us/wdsi/filesubmission
- Kaspersky: https://opentip.kaspersky.com (aba False Positive)
- Avast/AVG: https://www.avast.com/false-positive-file-form.aspx

Ao abrir o issue de falso positivo, você envia o link do repo como evidência.

### 2. Distribuição via GitHub Releases
Arquivos hospedados no GitHub têm reputação própria com o SmartScreen porque o domínio
`github.com` / `objects.githubusercontent.com` é trusted. Isso **não elimina** o aviso,
mas reduz a severidade em comparação com um `.exe` baixado de site desconhecido.

### 3. `--onedir` em vez de `--onefile`
O modo `--onefile` extrai tudo para `%TEMP%` em runtime — comportamento idêntico ao de
malware que faz dropper. O modo `--onedir` não faz isso e ativa menos heurísticas.

### 4. Nuitka como alternativa ao PyInstaller
[Nuitka](https://nuitka.net) compila Python para C nativo antes de gerar o `.exe`.
O resultado é menos reconhecido como "padrão PyInstaller" pelas engines de AV:
```
pip install nuitka
python -m nuitka --onefile --windows-disable-console --windows-icon-from-ico=assets\icon.ico main.py
```
É mais lento de compilar mas gera binários mais limpos.

### 5. Construir no GitHub Actions (reproducible build)
Projetos sérios usam CI para compilar — o hash do `.exe` pode ser verificado
por qualquer um que clonar o repo e rodar o mesmo workflow. Isso aumenta confiança.

### 6. Aceitar que alguns AVs vão reclamar e documentar isso
Projetos como o próprio AutoHotkey têm aviso no README:
> "Some antivirus programs may flag this file as suspicious. This is a false positive."

Usuários técnicos entendem e adicionam exclusão manual.

---

## Qual opção escolher?

| | Installer (A) | ZIP portátil (B) |
|---|---|---|
| Experiência do usuário | Profissional | Simples |
| Atalho no menu iniciar | Sim | Não |
| Desinstalador | Sim | Usuário apaga a pasta |
| Bloqueio por AV corporativo | Mais comum | Menos comum |
| Facilidade de atualizar | Requer novo installer | Substitui a pasta |
| Ideal para | Distribuição ampla | Uso pessoal / colegas |

Para um app de automação pessoal ou de equipe pequena, **o ZIP é suficiente e mais prático**.
Se quiser distribuir publicamente com experiência polida, use o installer.
