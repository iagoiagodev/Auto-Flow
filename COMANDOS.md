# AutoFlow — Cheat Sheet & Referencia

## Como rodar a aplicacao

```bash
# Instalar dependencias
pip install customtkinter pystray Pillow pyautogui opencv-python pyperclip keyboard mouse pyinstaller

# Rodar a GUI
python main.py

# Empacotar como .exe portavel
pyinstaller --onefile --windowed --name AutoFlow main.py
# Saida: dist/AutoFlow.exe
```

## Estrutura do projeto
```
Python Automation/
├── main.py                  # Entry point: GUI + tray
├── runner.py                # Engine de execucao de workflows
├── gui/
│   ├── app.py               # Janela principal
│   ├── workflow_editor.py   # Editor de workflow
│   └── step_editor.py       # Modal de step + captura ao vivo
├── workflows/               # Um .json por workflow
└── assets/
    └── templates/           # Imagens para wait_image
```

## Tipos de step (JSON)
| tipo       | campos obrigatorios                                  |
|------------|------------------------------------------------------|
| click      | x, y                                                 |
| paste      | texto                                                 |
| press      | tecla (ex: enter, tab, f5)                           |
| hotkey     | combinacao (ex: ctrl+a)                              |
| wait_image | template (nome .png), confidence (0-1), timeout (s)  |
| sleep      | segundos                                             |
| screenshot | arquivo (nome do .png de saida)                      |

---

# Cheat Sheet — Automacao com Python (Avatar Humano)

> Referencia rapida dos comandos mais uteis para simular acoes humanas.

---

## Imports

```python
import pyautogui
import cv2
import pygetwindow as gw
import pyperclip
import random
import time
from pathlib import Path

pyautogui.PAUSE = 0.3          # pausa global entre acoes (segundos)
pyautogui.FAILSAFE = True      # mover mouse ate canto superior esquerdo = para o script
```

---

## pyautogui — Mouse

```python
# Posicao atual do mouse
x, y = pyautogui.position()

# Mover sem clicar
pyautogui.moveTo(x, y, duration=0.5)           # absoluto, com duracao
pyautogui.moveRel(dx, dy, duration=0.3)        # relativo a posicao atual

# Cliques
pyautogui.click(x, y)                          # clique simples
pyautogui.doubleClick(x, y)                    # duplo clique
pyautogui.rightClick(x, y)                     # clique direito
pyautogui.middleClick(x, y)                    # clique do meio
pyautogui.click(x, y, button='left', clicks=2, interval=0.2)  # customizado

# Arrastar
pyautogui.dragTo(x2, y2, duration=0.5, button='left')
pyautogui.dragRel(dx, dy, duration=0.5)

# Scroll
pyautogui.scroll(3)     # rolar para cima (3 unidades)
pyautogui.scroll(-3)    # rolar para baixo

# Tamanho da tela
largura, altura = pyautogui.size()
```

---

## pyautogui — Teclado

```python
# Digitar texto (simula humano, um char por vez)
pyautogui.write('texto aqui', interval=0.08)

# Pressionar tecla unica
pyautogui.press('enter')
pyautogui.press('tab')
pyautogui.press('esc')
pyautogui.press('f5')
pyautogui.press('delete')
pyautogui.press('backspace')

# Combinacoes de tecla (hotkeys)
pyautogui.hotkey('ctrl', 'c')          # copiar
pyautogui.hotkey('ctrl', 'v')          # colar
pyautogui.hotkey('ctrl', 'a')          # selecionar tudo
pyautogui.hotkey('ctrl', 'z')          # desfazer
pyautogui.hotkey('alt', 'tab')         # alternar janela
pyautogui.hotkey('ctrl', 'shift', 'esc')  # gerenciador de tarefas

# Segurar e soltar tecla
pyautogui.keyDown('shift')
pyautogui.press(['left', 'left', 'left'])
pyautogui.keyUp('shift')
```

---

## pyautogui — Tela e Imagens

```python
# Screenshot
img = pyautogui.screenshot()
img.save('assets/screenshots/captura.png')

# Localizar imagem na tela (retorna Box com left, top, width, height)
box = pyautogui.locateOnScreen('assets/templates/botao.png', confidence=0.9)
if box:
    centro = pyautogui.center(box)
    pyautogui.click(centro)

# Retorna apenas o centro (x, y) ou None
ponto = pyautogui.locateCenterOnScreen('assets/templates/botao.png', confidence=0.85)
if ponto:
    pyautogui.click(ponto)

# Aguardar imagem aparecer (loop manual)
while True:
    pos = pyautogui.locateCenterOnScreen('assets/templates/icone.png', confidence=0.9)
    if pos:
        break
    time.sleep(0.5)

# Cor de um pixel
r, g, b = pyautogui.pixel(x, y)
```

> **Nota:** `confidence` requer `import cv2` instalado (pip install opencv-python).

---

## cv2 (OpenCV) — Reconhecimento de Imagem

```python
import cv2
import numpy as np

# Carregar imagens
img_tela   = cv2.imread('assets/screenshots/tela.png')
img_modelo = cv2.imread('assets/templates/botao.png')

# Converter para cinza (melhora performance)
tela_gray   = cv2.cvtColor(img_tela, cv2.COLOR_BGR2GRAY)
modelo_gray = cv2.cvtColor(img_modelo, cv2.COLOR_BGR2GRAY)

# Buscar template na tela
resultado = cv2.matchTemplate(tela_gray, modelo_gray, cv2.TM_CCOEFF_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(resultado)

LIMIAR = 0.85
if max_val >= LIMIAR:
    # max_loc = canto superior esquerdo do match
    h, w = modelo_gray.shape
    centro_x = max_loc[0] + w // 2
    centro_y = max_loc[1] + h // 2
    pyautogui.click(centro_x, centro_y)

# Salvar imagem (debug)
cv2.imwrite('assets/screenshots/debug.png', img_tela)
```

---

## pygetwindow — Controle de Janelas

```python
import pygetwindow as gw

# Listar todas as janelas abertas
todas = gw.getAllTitles()

# Buscar janela pelo titulo (parcial)
janelas = gw.getWindowsWithTitle('Chrome')
if janelas:
    win = janelas[0]
    win.activate()       # trazer para frente
    win.maximize()       # maximizar
    win.minimize()       # minimizar
    win.restore()        # restaurar

# Posicao e tamanho
print(win.left, win.top, win.width, win.height)

# Mover e redimensionar
win.moveTo(0, 0)
win.resizeTo(1280, 720)

# Janela ativa no momento
ativa = gw.getActiveWindow()
print(ativa.title)
```

---

## pyperclip — Copiar e Colar

```python
import pyperclip

# Copiar para o clipboard
pyperclip.copy('texto que quero colar')

# Ler o que esta no clipboard
conteudo = pyperclip.paste()

# Fluxo tipico: colar texto sem digitar char a char (mais rapido e seguro)
pyperclip.copy('Texto longo aqui...')
pyautogui.hotkey('ctrl', 'v')
```

---

## random — Humanizacao dos Movimentos

```python
import random

# Atraso aleatorio entre acoes (parece mais humano)
time.sleep(random.uniform(0.5, 1.5))

# Numero inteiro aleatorio
n = random.randint(1, 5)

# Distribuicao gaussiana (mais natural para delays)
delay = max(0.1, random.gauss(mu=0.8, sigma=0.2))
time.sleep(delay)

# Offset aleatorio no clique (evita clicar sempre no pixel exato)
def clique_humano(x, y, desvio=3):
    ox = random.randint(-desvio, desvio)
    oy = random.randint(-desvio, desvio)
    pyautogui.moveTo(x + ox, y + oy, duration=random.uniform(0.3, 0.7))
    time.sleep(random.uniform(0.05, 0.15))
    pyautogui.click()

# Escolher item aleatorio de uma lista
opcao = random.choice(['opcao1', 'opcao2', 'opcao3'])
```

---

## time — Controle de Tempo

```python
import time

# Esperar N segundos
time.sleep(2)
time.sleep(0.5)

# Marcar tempo de execucao
inicio = time.time()
# ... acoes ...
decorrido = time.time() - inicio
print(f'Tempo: {decorrido:.2f}s')

# Timeout: aguardar ate X segundos por uma condicao
def aguardar_imagem(caminho, timeout=10, confianca=0.9):
    inicio = time.time()
    while time.time() - inicio < timeout:
        pos = pyautogui.locateCenterOnScreen(caminho, confidence=confianca)
        if pos:
            return pos
        time.sleep(0.5)
    return None  # nao encontrou dentro do timeout
```

---

## pathlib — Organizacao de Caminhos

```python
from pathlib import Path

# Definir raiz do projeto
BASE    = Path(__file__).parent        # pasta do script atual
ASSETS  = BASE / 'assets'
TMPL    = ASSETS / 'templates'
SHOTS   = ASSETS / 'screenshots'

# Usar nos comandos de imagem
pyautogui.locateCenterOnScreen(str(TMPL / 'botao.png'), confidence=0.9)

# Verificar se arquivo existe
if (TMPL / 'icone.png').exists():
    print('Template encontrado')

# Listar todos os templates
for img in TMPL.glob('*.png'):
    print(img.name)

# Criar pasta se nao existir
SHOTS.mkdir(parents=True, exist_ok=True)
```

---

## Padroes Uteis — Receitas Prontas

### Escrever em campo de texto de forma humanizada
```python
pyautogui.click(x, y)
time.sleep(random.uniform(0.2, 0.4))
pyautogui.hotkey('ctrl', 'a')      # selecionar conteudo anterior
pyperclip.copy('novo texto')
pyautogui.hotkey('ctrl', 'v')
```

### Aguardar janela abrir e focar
```python
for _ in range(20):
    janelas = gw.getWindowsWithTitle('Nome da Janela')
    if janelas:
        janelas[0].activate()
        break
    time.sleep(0.5)
```

### Screenshot de debug nomeado por timestamp
```python
nome = f"assets/screenshots/{int(time.time())}.png"
pyautogui.screenshot().save(nome)
```

### Teclas especiais uteis
```python
# F-keys, setas, etc.
pyautogui.press(['up', 'down', 'left', 'right'])
pyautogui.press(['pageup', 'pagedown', 'home', 'end'])
pyautogui.press(['insert', 'delete', 'numlock', 'capslock'])
```
