"""
runner.py — Engine de execucao de workflows.
"""

import time
import threading
import datetime
import pyautogui
import pyperclip
import keyboard
from pathlib import Path

import sys
import logger as _log_module
log = _log_module.log

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
TMPL = BASE / "assets" / "templates"

# Contexto de log do step atual (preenchido por _run_steps)
_log_ctx: dict = {"wf": "?", "step": 0, "total": 0}

pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True

_running_thread: threading.Thread | None = None
_stop_event = threading.Event()
_pause_event = threading.Event()
_pause_event.set()  # set = NOT paused

_driver = None  # Selenium WebDriver global instance
_runtime_vars: dict = {}  # Variables captured at runtime (e.g. browser_get_text)


def is_running() -> bool:
    return _running_thread is not None and _running_thread.is_alive()


def is_paused() -> bool:
    return not _pause_event.is_set()


def stop():
    _stop_event.set()
    _pause_event.set()  # desbloqueio para a thread poder sair
    _close_driver()


def pause():
    _pause_event.clear()


def resume():
    _pause_event.set()


_last_test_error: str | None = None


def execute_single_step(step: dict, on_error=None):
    """Executa um unico step em thread separada (usado para testar no editor)."""
    global _last_test_error
    _last_test_error = None

    def _run():
        global _last_test_error
        try:
            _execute_step(step)
        except Exception as e:
            _last_test_error = _clean_selenium_error(str(e))
            if on_error:
                on_error(_clean_selenium_error(str(e)))
    threading.Thread(target=_run, daemon=True).start()


def run_workflow(workflow: dict, on_step=None, on_done=None, on_error=None, on_cancel=None):
    """
    Executa um workflow em thread separada.
    on_step(index, step), on_done(), on_error(msg), on_cancel()
    """
    global _running_thread, _stop_event, _pause_event, _runtime_vars, _log_ctx
    if is_running():
        return

    _stop_event = threading.Event()
    _pause_event = threading.Event()
    _pause_event.set()
    _runtime_vars = dict(workflow.get("variaveis_valores", {}))

    wf_name = workflow.get("name", "?")
    steps = workflow.get("steps", [])
    active_steps = [s for s in steps if s.get("ativo", True)]
    _log_ctx = {"wf": wf_name, "step": 0, "total": len(active_steps)}

    def _run():
        repeticoes = max(1, int(workflow.get("repeticoes", 1)))
        delay_entre = float(workflow.get("delay_entre_repeticoes", 0))
        vars_log = {k: _log_module._mask(str(v)) for k, v in _runtime_vars.items()}
        log.info(f"[{wf_name}] START | steps={len(active_steps)} | repeticoes={repeticoes} | vars={vars_log}")
        t0 = time.time()
        try:
            for rep_idx in range(repeticoes):
                if _stop_event.is_set():
                    break
                if repeticoes > 1:
                    log.info(f"[{wf_name}] Repeticao {rep_idx + 1}/{repeticoes}")
                _run_steps(steps, on_step=on_step)
                if delay_entre > 0 and rep_idx < repeticoes - 1:
                    deadline = time.time() + delay_entre
                    while time.time() < deadline:
                        if _stop_event.is_set():
                            break
                        time.sleep(0.05)
        except Exception as e:
            log.error(f"[{wf_name}] ERROR | step={_log_ctx['step']} | {_clean_selenium_error(str(e))}")
            try:
                import datetime as _dt
                ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_path = BASE / "assets" / "screenshots" / f"erro_{ts}.png"
                shot_path.parent.mkdir(parents=True, exist_ok=True)
                pyautogui.screenshot(str(shot_path))
                log.error(f"[{wf_name}] Screenshot do erro salvo: {shot_path.name}")
                msg = _clean_selenium_error(str(e)) + f"\n\n[Screenshot: {shot_path.name}]"
            except Exception:
                msg = _clean_selenium_error(str(e))
            if on_error:
                on_error(msg)
            return
        elapsed = time.time() - t0
        if _stop_event.is_set():
            log.info(f"[{wf_name}] CANCELLED | elapsed={elapsed:.2f}s")
            if on_cancel:
                on_cancel()
        else:
            log.info(f"[{wf_name}] DONE | elapsed={elapsed:.2f}s")
            if on_done:
                on_done()

    _running_thread = threading.Thread(target=_run, daemon=True)
    _running_thread.start()


def _step_details(step: dict) -> str:
    """Retorna string resumida com campos relevantes do step para o log."""
    tipo = step.get("tipo", "?")
    parts = []
    if tipo in ("browser_click", "browser_fill", "browser_wait", "browser_select",
                "browser_get_text"):
        parts.append(f"selector={repr(step.get('selector', ''))}")
        parts.append(f"por={step.get('por', 'css')}")
    if tipo == "browser_fill":
        texto = step.get("texto", "")
        parts.append(f"texto={repr(_log_module._mask(texto))}")
    if tipo in ("browser_open", "browser_navigate"):
        parts.append(f"url={step.get('url', '')}")
    if tipo == "click":
        parts.append(f"x={step.get('x')} y={step.get('y')}")
    if tipo == "sleep":
        parts.append(f"segundos={step.get('segundos')}")
    if tipo == "wait_image":
        parts.append(f"template={step.get('template')} confidence={step.get('confidence', 0.8)}")
    if tipo == "run_workflow":
        parts.append(f"workflow={repr(step.get('workflow', ''))}")
    if tipo == "get_clipboard":
        parts.append(f"variavel={repr(step.get('variavel', ''))}")
    if tipo in ("wait_text", "click_text"):
        parts.append(f"texto={repr(step.get('texto', ''))}")
    if tipo == "browser_get_url":
        parts.append(f"variavel={repr(step.get('variavel', ''))}")
    nota = step.get("nota", "")
    if nota:
        parts.append(f"nota={repr(nota)}")
    return " | ".join(parts)


def _run_steps(steps: list, on_step=None, step_offset: int = 0):
    global _log_ctx
    for i, step in enumerate(steps):
        if _stop_event.is_set():
            break
        while not _pause_event.is_set():
            if _stop_event.is_set():
                return
            time.sleep(0.1)
        if not step.get("ativo", True):
            continue
        if on_step:
            on_step(step_offset + i, step)

        tipo = step.get("tipo", "?")
        step_num = step_offset + i + 1
        _log_ctx["step"] = step_num
        details = _step_details(step)
        log.debug(f"[{_log_ctx['wf']}] STEP {step_num} | {tipo}" + (f" | {details}" if details else ""))

        t0 = time.time()
        retries = int(step.get("retry", 0))
        retry_delay = float(step.get("retry_delay", 1.0))
        last_exc = None
        for attempt in range(retries + 1):
            try:
                _execute_step(_apply_runtime_vars(step))
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    log.warning(f"[{_log_ctx['wf']}] STEP {step_num} | retry {attempt+1}/{retries} | {_clean_selenium_error(str(exc))}")
                    time.sleep(retry_delay)
        if last_exc is not None:
            raise last_exc
        elapsed = time.time() - t0
        log.debug(f"[{_log_ctx['wf']}] STEP {step_num} | OK | {elapsed:.3f}s")


def _apply_runtime_vars(step: dict) -> dict:
    """Substitui {{VAR}} usando _runtime_vars nas strings do step (deep copy)."""
    import copy
    result = copy.deepcopy(step)

    def _sub(obj):
        if isinstance(obj, str):
            for k, v in _runtime_vars.items():
                obj = obj.replace(f"{{{{{k}}}}}", v)
            return obj
        if isinstance(obj, dict):
            return {k: _sub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sub(i) for i in obj]
        return obj

    return _sub(result)


def _substitute_in_steps(steps: list, var: str, value: str) -> list:
    """Deep-copy dos steps substituindo {{var}} por value em todos os campos string."""
    import copy
    placeholder = f"{{{{{var}}}}}"

    def _sub(obj):
        if isinstance(obj, str):
            return obj.replace(placeholder, value)
        if isinstance(obj, dict):
            return {k: _sub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sub(i) for i in obj]
        return obj

    return [_sub(copy.deepcopy(s)) for s in steps]


# ---------------------------------------------------------------------------
# Selenium helpers
# ---------------------------------------------------------------------------

def _get_driver():
    global _driver
    if _driver is None:
        raise RuntimeError("Browser nao aberto. Use o step 'browser_open' primeiro.")
    return _driver


def _close_driver():
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


def _clean_selenium_error(msg: str) -> str:
    """Remove o stacktrace sem simbolos que Chrome 145 anexa em toda excecao."""
    cutoff = msg.find("Stacktrace:")
    if cutoff != -1:
        msg = msg[:cutoff].strip()
    cutoff2 = msg.find("\nSymbols not available")
    if cutoff2 != -1:
        msg = msg[:cutoff2].strip()
    return msg


def _find_element(driver, selector: str, por: str, timeout: int, interactable: bool = False):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    by_map = {
        "css":   By.CSS_SELECTOR,
        "xpath": By.XPATH,
        "id":    By.ID,
        "name":  By.NAME,
        "text":  By.LINK_TEXT,
        "class": By.CLASS_NAME,
    }
    by = by_map.get(por, By.CSS_SELECTOR)
    if not selector:
        raise ValueError("Selector vazio — preencha o campo Selector no step.")
    try:
        condition = EC.element_to_be_clickable((by, selector)) if interactable \
                    else EC.presence_of_element_located((by, selector))
        el = WebDriverWait(driver, timeout).until(condition)
    except Exception as e:
        raise RuntimeError(
            f"Elemento nao encontrado apos {timeout}s.\n"
            f"  Selector: {repr(selector)}\n"
            f"  Por: {por}\n"
            f"  Pagina atual: {driver.current_url}\n"
            f"  Detalhe: {_clean_selenium_error(str(e))}"
        )
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass
    return el


# ---------------------------------------------------------------------------

def _execute_step(step: dict):
    tipo = step.get("tipo")

    if tipo == "click":
        clique = step.get("clique", "simples")
        if clique == "duplo":
            pyautogui.doubleClick(step["x"], step["y"])
        elif clique == "direito":
            pyautogui.rightClick(step["x"], step["y"])
        else:
            pyautogui.click(step["x"], step["y"])

    elif tipo == "paste":
        pyperclip.copy(step.get("texto", ""))
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")

    elif tipo == "type":
        keyboard.write(step.get("texto", ""), delay=float(step.get("intervalo", 0.08)))

    elif tipo == "press":
        pyautogui.press(step.get("tecla", "enter"))

    elif tipo == "hotkey":
        keys = step.get("combinacao", "ctrl+c").split("+")
        pyautogui.hotkey(*keys)

    elif tipo == "scroll":
        quantidade = int(step.get("quantidade", 3))
        x = step.get("x")
        y = step.get("y")
        if x is not None and y is not None:
            pyautogui.scroll(quantidade, x=int(x), y=int(y))
        else:
            pyautogui.scroll(quantidade)

    elif tipo == "click_image":
        template   = step.get("template", "")
        confidence = float(step.get("confidence", 0.8))
        timeout    = float(step.get("timeout", 30))
        clique     = step.get("clique", "simples")
        offset_x   = int(step.get("offset_x", 0))
        offset_y   = int(step.get("offset_y", 0))
        ao_falhar  = step.get("ao_falhar", "erro")
        template_path = TMPL / template
        if not template_path.exists():
            raise FileNotFoundError(f"Template nao encontrado: {template}\nPasta: {TMPL}")
        deadline = time.time() + timeout
        pos = None
        while pos is None:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                if ao_falhar == "continuar":
                    return
                raise TimeoutError(f"Imagem nao encontrada na tela: {template}")
            try:
                pos = pyautogui.locateCenterOnScreen(str(template_path), confidence=confidence)
            except Exception:
                pass
            if pos is None:
                time.sleep(0.3)
        cx, cy = pos.x + offset_x, pos.y + offset_y
        log.debug(f"click_image: {template} encontrado em ({cx},{cy}) conf={confidence}")
        pyautogui.moveTo(cx, cy, duration=0.2)
        if clique == "duplo":
            pyautogui.doubleClick(cx, cy)
        elif clique == "direito":
            pyautogui.rightClick(cx, cy)
        else:
            pyautogui.click(cx, cy)

    elif tipo == "move_to_image":
        template   = step.get("template", "")
        confidence = float(step.get("confidence", 0.8))
        timeout    = float(step.get("timeout", 30))
        offset_x   = int(step.get("offset_x", 0))
        offset_y   = int(step.get("offset_y", 0))
        ao_falhar  = step.get("ao_falhar", "erro")
        template_path = TMPL / template
        if not template_path.exists():
            raise FileNotFoundError(f"Template nao encontrado: {template}\nPasta: {TMPL}")
        deadline = time.time() + timeout
        pos = None
        while pos is None:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                if ao_falhar == "continuar":
                    return
                raise TimeoutError(f"Imagem nao encontrada na tela: {template}")
            try:
                pos = pyautogui.locateCenterOnScreen(str(template_path), confidence=confidence)
            except Exception:
                pass
            if pos is None:
                time.sleep(0.3)
        cx, cy = pos.x + offset_x, pos.y + offset_y
        log.debug(f"move_to_image: {template} encontrado em ({cx},{cy})")
        pyautogui.moveTo(cx, cy, duration=float(step.get("duracao", 0.3)))

    elif tipo == "click_text":
        texto      = step.get("texto", "")
        timeout    = float(step.get("timeout", 30))
        clique     = step.get("clique", "simples")
        offset_x   = int(step.get("offset_x", 0))
        offset_y   = int(step.get("offset_y", 0))
        ao_falhar  = step.get("ao_falhar", "erro")
        if not texto:
            raise ValueError("click_text: campo 'texto' vazio.")
        try:
            import pytesseract
            from PIL import ImageGrab
        except ImportError:
            raise RuntimeError("pytesseract nao instalado. Execute: pip install pytesseract\n"
                               "E instale o Tesseract OCR em: https://github.com/UB-Mannheim/tesseract/wiki")
        deadline = time.time() + timeout
        found_box = None
        while found_box is None:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                if ao_falhar == "continuar":
                    return
                raise TimeoutError(f"Texto nao encontrado na tela: {repr(texto)}")
            try:
                img = ImageGrab.grab()
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                                  lang=step.get("lang", "por+eng"))
                for i, word in enumerate(data["text"]):
                    if texto.lower() in word.lower() and int(data["conf"][i]) > 40:
                        x = data["left"][i] + data["width"][i] // 2 + offset_x
                        y = data["top"][i] + data["height"][i] // 2 + offset_y
                        found_box = (x, y)
                        break
            except Exception:
                pass
            if found_box is None:
                time.sleep(0.5)
        cx, cy = found_box
        log.debug(f"click_text: {repr(texto)} encontrado em ({cx},{cy})")
        pyautogui.moveTo(cx, cy, duration=0.2)
        if clique == "duplo":
            pyautogui.doubleClick(cx, cy)
        elif clique == "direito":
            pyautogui.rightClick(cx, cy)
        else:
            pyautogui.click(cx, cy)

    elif tipo == "wait_text":
        texto     = step.get("texto", "")
        timeout   = float(step.get("timeout", 30))
        ao_falhar = step.get("ao_falhar", "erro")
        if not texto:
            raise ValueError("wait_text: campo 'texto' vazio.")
        try:
            import pytesseract
            from PIL import ImageGrab
        except ImportError:
            raise RuntimeError("pytesseract nao instalado.")
        deadline = time.time() + timeout
        found = False
        while not found:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                if ao_falhar == "continuar":
                    return
                raise TimeoutError(f"Texto nao encontrado na tela: {repr(texto)}")
            try:
                img = ImageGrab.grab()
                data = pytesseract.image_to_string(img, lang=step.get("lang", "por+eng"))
                if texto.lower() in data.lower():
                    found = True
            except Exception:
                pass
            if not found:
                time.sleep(0.5)
        log.debug(f"wait_text: {repr(texto)} encontrado na tela")

    elif tipo == "wait_image":
        template = step.get("template", "")
        confidence = step.get("confidence", 0.8)
        timeout = step.get("timeout", 30)
        ao_falhar = step.get("ao_falhar", "erro")
        template_path = TMPL / template
        deadline = time.time() + timeout
        found = None
        while found is None:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                if ao_falhar == "continuar":
                    return
                raise TimeoutError(f"Imagem nao encontrada: {template}")
            try:
                found = pyautogui.locateOnScreen(str(template_path), confidence=confidence)
            except Exception:
                pass
            time.sleep(0.5)

    elif tipo == "sleep":
        segundos = float(step.get("segundos", 1.0))
        deadline = time.time() + segundos
        while time.time() < deadline:
            if _stop_event.is_set():
                return
            time.sleep(0.05)

    elif tipo == "screenshot":
        filename = step.get("arquivo", "screenshot.png")
        out_path = BASE / "assets" / "screenshots" / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot(str(out_path))

    elif tipo == "loop":
        repeticoes = max(1, int(step.get("repeticoes", 1)))
        sub_steps = step.get("steps", [])
        for _ in range(repeticoes):
            if _stop_event.is_set():
                break
            _run_steps(sub_steps)

    elif tipo == "if_image":
        template = step.get("template", "")
        confidence = step.get("confidence", 0.8)
        timeout = step.get("timeout", 5)
        template_path = TMPL / template
        deadline = time.time() + timeout
        found = None
        while found is None:
            if _stop_event.is_set():
                return
            if time.time() > deadline:
                break
            try:
                found = pyautogui.locateOnScreen(str(template_path), confidence=confidence)
            except Exception:
                pass
            if found is None:
                time.sleep(0.3)
        if found is not None:
            _run_steps(step.get("steps_sim", []))
        else:
            _run_steps(step.get("steps_nao", []))

    elif tipo == "loop_lista":
        variavel = step.get("variavel", "")
        lista = step.get("lista", [])
        sub_steps = step.get("steps", [])
        for item in lista:
            if _stop_event.is_set():
                break
            subst = _substitute_in_steps(sub_steps, variavel, str(item))
            _run_steps(subst)

    elif tipo == "if_var":
        valor_comparar = step.get("valor_comparar", "")
        operador = step.get("operador", "igual")
        valor_ref = step.get("valor_ref", "")
        match_ops = {
            "igual":       valor_comparar == valor_ref,
            "diferente":   valor_comparar != valor_ref,
            "contem":      valor_ref in valor_comparar,
            "comeca_com":  valor_comparar.startswith(valor_ref),
            "termina_com": valor_comparar.endswith(valor_ref),
        }
        if match_ops.get(operador, False):
            _run_steps(step.get("steps_sim", []))
        else:
            _run_steps(step.get("steps_nao", []))

    elif tipo == "run_workflow":
        import json as _json
        wf_file = step.get("workflow", "")
        wf_path = BASE / "workflows" / wf_file
        if not wf_path.suffix:
            wf_path = wf_path.with_suffix(".json")
        if not wf_path.exists():
            raise FileNotFoundError(f"Workflow nao encontrado: {wf_file}\nProcurado em: {wf_path}")
        with open(wf_path, encoding="utf-8") as _f:
            sub_wf = _json.load(_f)
        sub_vars = dict(sub_wf.get("variaveis_valores", {}))
        sub_vars.update(_runtime_vars)
        old_vars = dict(_runtime_vars)
        _runtime_vars.clear()
        _runtime_vars.update(sub_vars)
        log.info(f"run_workflow: iniciando '{wf_file}' ({len(sub_wf.get('steps',[]))} steps)")
        _run_steps(sub_wf.get("steps", []))
        _runtime_vars.clear()
        _runtime_vars.update(old_vars)

    elif tipo == "get_clipboard":
        variavel = step.get("variavel", "").strip()
        if variavel:
            _runtime_vars[variavel] = pyperclip.paste()
            log.debug(f"get_clipboard: {variavel} = {repr(_runtime_vars[variavel][:40])}")

    # ------------------------------------------------------------------
    # Selenium / Browser steps
    # ------------------------------------------------------------------

    elif tipo == "browser_open":
        global _driver
        _close_driver()
        from selenium import webdriver
        browser = step.get("browser", "chrome").lower()
        url = step.get("url", "")
        headless = bool(step.get("headless", False))

        if browser == "edge":
            from selenium.webdriver.edge.options import Options as EdgeOptions
            opts = EdgeOptions()
            if headless:
                opts.add_argument("--headless=new")
            _driver = webdriver.Edge(options=opts)
        elif browser == "firefox":
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            opts = FirefoxOptions()
            if headless:
                opts.add_argument("--headless")
            _driver = webdriver.Firefox(options=opts)
        else:  # chrome (default)
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument("--disable-blink-features=AutomationControlled")
            _driver = webdriver.Chrome(options=opts)

        if url:
            if url and not url.startswith(("http://", "https://", "file://")):
                url = "https://" + url
            _driver.get(url)

    elif tipo == "browser_close":
        _close_driver()

    elif tipo == "browser_navigate":
        url = step.get("url", "")
        if url and not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        _get_driver().get(url)

    elif tipo == "browser_click":
        driver = _get_driver()
        el = _find_element(
            driver,
            step.get("selector", ""),
            step.get("por", "css"),
            int(step.get("timeout", 10)),
            interactable=True,
        )
        try:
            el.click()
        except Exception:
            # Fallback: click via JS (útil para elementos cobertos por overlay)
            driver.execute_script("arguments[0].click();", el)

    elif tipo == "browser_fill":
        driver = _get_driver()
        el = _find_element(
            driver,
            step.get("selector", ""),
            step.get("por", "css"),
            int(step.get("timeout", 10)),
            interactable=True,
        )
        if step.get("limpar", True):
            el.clear()
        el.send_keys(step.get("texto", ""))

    elif tipo == "browser_wait":
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        driver = _get_driver()
        by_map = {
            "css":   By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id":    By.ID,
            "name":  By.NAME,
            "text":  By.LINK_TEXT,
            "class": By.CLASS_NAME,
        }
        by = by_map.get(step.get("por", "css"), By.CSS_SELECTOR)
        timeout = int(step.get("timeout", 10))
        condicao = step.get("condicao", "presente")
        locator = (by, step.get("selector", ""))
        wait = WebDriverWait(driver, timeout)
        if condicao == "visivel":
            wait.until(EC.visibility_of_element_located(locator))
        elif condicao == "clicavel":
            wait.until(EC.element_to_be_clickable(locator))
        else:  # presente
            wait.until(EC.presence_of_element_located(locator))

    elif tipo == "browser_select":
        from selenium.webdriver.support.ui import Select
        driver = _get_driver()
        el = _find_element(
            driver,
            step.get("selector", ""),
            step.get("por", "css"),
            int(step.get("timeout", 10)),
        )
        sel = Select(el)
        valor = step.get("valor", "")
        try:
            sel.select_by_visible_text(valor)
        except Exception:
            try:
                sel.select_by_value(valor)
            except Exception:
                sel.select_by_index(int(valor))

    elif tipo == "browser_get_text":
        driver = _get_driver()
        el = _find_element(
            driver,
            step.get("selector", ""),
            step.get("por", "css"),
            int(step.get("timeout", 10)),
        )
        variavel = step.get("variavel", "").strip()
        if variavel:
            _runtime_vars[variavel] = el.text

    elif tipo == "browser_get_url":
        variavel = step.get("variavel", "").strip()
        if variavel:
            _runtime_vars[variavel] = _get_driver().current_url
            log.debug(f"browser_get_url: {variavel} = {_runtime_vars[variavel]}")

    elif tipo == "browser_run_js":
        _get_driver().execute_script(step.get("script", ""))

    elif tipo == "browser_screenshot":
        driver = _get_driver()
        filename = step.get("arquivo", "browser_screenshot.png")
        out_path = BASE / "assets" / "screenshots" / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(out_path))

    else:
        raise ValueError(f"Tipo de step desconhecido: {tipo}")
