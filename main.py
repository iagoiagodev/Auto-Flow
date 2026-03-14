"""
main.py — Entry point do AutoFlow.
Inicia a GUI (customtkinter) e o icone na bandeja do sistema (pystray).
"""

import json
import threading
from pathlib import Path

# ---------- Tray icon ----------
import pystray
from PIL import Image, ImageDraw

# ---------- App ----------
from gui.app import AutoFlowApp
import runner

WORKFLOWS_DIR = Path(__file__).parent / "workflows"


# ------------------------------------------------------------------
# Cria um icone simples com Pillow (AF em fundo azul)
# ------------------------------------------------------------------
def _make_icon() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Fundo circular azul
    draw.ellipse([0, 0, size - 1, size - 1], fill=(31, 83, 141, 255))
    # Letras AF em branco
    try:
        from PIL import ImageFont

        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, 16), "AF", fill="white", font=font)
    return img


# ------------------------------------------------------------------
# Monta menu do tray dinamicamente a partir dos workflows salvos
# ------------------------------------------------------------------
def _build_tray_menu(app: AutoFlowApp) -> pystray.Menu:
    items = [
        pystray.MenuItem("Abrir AutoFlow", lambda: app.after(0, app.show)),
        pystray.Menu.SEPARATOR,
    ]

    WORKFLOWS_DIR.mkdir(exist_ok=True)
    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                wf = json.load(f)
            label = wf.get("name", path.stem)
            hotkey = wf.get("hotkey", "")
            if hotkey:
                label = f"{label}  [{hotkey}]"
            items.append(
                pystray.MenuItem(
                    label,
                    lambda wf=wf: app.after(0, lambda wf=wf: app._run_workflow(wf)),
                )
            )
        except Exception:
            pass

    items += [
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", lambda: _quit(app)),
    ]
    return pystray.Menu(*items)


def _quit(app: AutoFlowApp):
    runner.stop()
    app.after(0, app.destroy)


# ------------------------------------------------------------------
# Ponto de entrada
# ------------------------------------------------------------------
def main():
    app = AutoFlowApp()

    icon_img = _make_icon()

    def _refresh_menu(icon):
        icon.menu = _build_tray_menu(app)

    tray = pystray.Icon(
        name="AutoFlow",
        icon=icon_img,
        title="AutoFlow",
        menu=_build_tray_menu(app),
    )

    # Injeta referencia ao tray na app para que _on_close funcione corretamente
    app._tray_icon = tray
    app._refresh_tray = lambda: setattr(tray, "menu", _build_tray_menu(app))

    # Roda o tray em thread separada (pystray.run() e um loop bloqueante)
    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    # Roda a GUI no thread principal (tkinter exige isso)
    app.mainloop()

    # Ao fechar a GUI encerra o tray
    tray.stop()


if __name__ == "__main__":
    main()
