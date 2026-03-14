# Auto Flow

**Auto Flow** é uma ferramenta de automação desktop baseada em Python que permite criar e executar fluxos de trabalho (workflows) de forma fácil e rápida. 

## 📦 Instalação Rápida (Recomendado)

Você pode instalar o Auto Flow facilmente usando nosso script de instalação rápida. Ele verificará se você tem o Python instalado (baixando-o e instalando, se necessário) e configurará todo o ambiente.

Abra o **PowerShell** em modo Administrador e cole o seguinte comando:

```powershell
iwr -useb https://raw.githubusercontent.com/SEU_USUARIO/AutoFlow/main/install.ps1 | iex
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
   git clone https://github.com/SEU_USUARIO/AutoFlow.git
   cd AutoFlow
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
