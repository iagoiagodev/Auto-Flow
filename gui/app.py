"""
app.py — Janela principal do AutoFlow (customtkinter).
Lista workflows, permite criar/editar/executar/duplicar/excluir/importar.
"""

import sys
import json
import shutil
import datetime
import threading
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
import tkinter as tk

import runner
import logger as _log_module
log = _log_module.log
from gui.workflow_editor import WorkflowEditorFrame

_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
WORKFLOWS_DIR = _BASE / "workflows"
SETTINGS_FILE = _BASE / "settings.json"
HISTORY_FILE  = _BASE / "history.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AutoFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoFlow")
        self.geometry("820x560")
        self.minsize(680, 420)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tray_icon = None          # injetado pelo main.py
        self._refresh_tray = None       # injetado pelo main.py
        self._cancel_hotkey = None      # hotkey ESC (ativo so durante run)
        self._pause_hotkey = None       # hotkey P (ativo so durante run)
        self._hotkey_registry: dict[str, str] = {}  # hotkey -> filename
        self._current_frame = None
        self._run_history: list = []
        self._exec_log: list = []
        self._workflow_cache: list = []  # cache de (wf, filename) — invalida em save/delete/import

        self._load_settings()
        self._load_history()
        self._build_ui()
        self.after(100, self._load_workflows)

    # ------------------------------------------------------------------
    # Persistencia de configuracoes
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                s = json.load(f)
            runner.pyautogui.PAUSE = float(s.get("pause", 0.3))
            runner.pyautogui.FAILSAFE = bool(s.get("failsafe", True))
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"pause": runner.pyautogui.PAUSE, "failsafe": runner.pyautogui.FAILSAFE},
                    f, indent=2,
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Persistencia de historico
    # ------------------------------------------------------------------
    def _load_history(self):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                self._run_history = json.load(f)
        except Exception:
            self._run_history = []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._run_history[-200:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI principal
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Topo
        top = ctk.CTkFrame(self, fg_color=("#1f538d", "#1f538d"), corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="AutoFlow",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="white").grid(row=0, column=0, padx=20, pady=12)

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.grid(row=0, column=2, padx=16, pady=8)
        ctk.CTkButton(btn_row, text="+ Novo Workflow", width=140,
                      command=self._new_workflow).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Importar", width=90,
                      fg_color="gray40", hover_color="gray30",
                      command=self._import_workflow).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Configuracoes", width=120,
                      fg_color="gray40", hover_color="gray30",
                      command=self._open_settings).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Historico", width=100,
                      fg_color="gray40", hover_color="gray30",
                      command=self._show_history_view).pack(side="left", padx=4)

        # Conteudo central (container que troca entre lista e editor)
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._container.grid_columnconfigure(0, weight=1)

        # Status bar
        status_bar = ctk.CTkFrame(self, fg_color=("gray17", "gray17"), corner_radius=0)
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        self._status_label = ctk.CTkLabel(
            status_bar, text="Pronto",
            font=ctk.CTkFont(size=12), text_color="gray50", anchor="w"
        )
        self._status_label.grid(row=0, column=0, padx=(12, 8), pady=(4, 0), sticky="w")

        self._progress_bar = ctk.CTkProgressBar(status_bar, height=6)
        self._progress_bar.set(0)
        self._progress_bar.grid(row=1, column=0, columnspan=3, padx=12, pady=(2, 4), sticky="ew")
        self._progress_bar.grid_remove()  # oculto por padrao

        ctk.CTkLabel(
            status_bar, text="ESC cancela  |  P pausa/retoma",
            font=ctk.CTkFont(size=11), text_color="gray35", anchor="e"
        ).grid(row=0, column=1, padx=4, pady=(4, 0), sticky="e")

        ctk.CTkButton(
            status_bar, text="Log", width=44, height=22,
            fg_color="gray30", hover_color="gray25",
            font=ctk.CTkFont(size=11),
            command=self._show_exec_log,
        ).grid(row=0, column=2, padx=(4, 12), pady=(4, 0))

        self._show_list_view()

        # Atalhos globais de teclado
        self.bind("<Control-n>", lambda e: self._new_workflow())
        self.bind("<Control-i>", lambda e: self._import_workflow())

    # ------------------------------------------------------------------
    # Navegacao de frames
    # ------------------------------------------------------------------
    def _clear_container(self):
        for w in self._container.winfo_children():
            w.destroy()

    def _show_list_view(self):
        self._clear_container()

        # Linha de busca
        self._container.grid_rowconfigure(0, weight=0)
        self._container.grid_rowconfigure(1, weight=1)

        search_frame = ctk.CTkFrame(self._container, fg_color="transparent")
        search_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._load_workflows())
        ctk.CTkEntry(search_frame, textvariable=self._search_var,
                     placeholder_text="Buscar workflow...").pack(fill="x")

        self._list_frame = ctk.CTkScrollableFrame(self._container, label_text="")
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._load_workflows()

    def _show_editor(self, workflow: dict, filename: str):
        self._clear_container()
        self._container.grid_rowconfigure(0, weight=1)
        editor = WorkflowEditorFrame(
            self._container,
            workflow=workflow,
            filename=filename,
            on_save=self._on_workflow_saved,
            on_back=self._show_list_view,
            on_run_from=self._run_workflow,
        )
        editor.grid(row=0, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Carregamento de workflows
    # ------------------------------------------------------------------
    def _reload_workflow_cache(self):
        """Le todos os JSONs do disco e atualiza o cache. Chama apenas ao salvar/deletar/importar."""
        WORKFLOWS_DIR.mkdir(exist_ok=True)
        cache = []
        for path in sorted(WORKFLOWS_DIR.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    wf = json.load(f)
                cache.append((wf, path.name))
            except Exception as e:
                log.warning(f"Erro ao carregar workflow {path.name}: {e}")
        self._workflow_cache = cache

    def _load_workflows(self):
        if not hasattr(self, "_list_frame"):
            return
        for w in self._list_frame.winfo_children():
            w.destroy()

        # Se o cache estiver vazio, carrega do disco
        if not self._workflow_cache:
            self._reload_workflow_cache()

        if not self._workflow_cache:
            ctk.CTkLabel(self._list_frame,
                         text="Nenhum workflow encontrado.\nClique em '+ Novo Workflow' para comecar.",
                         text_color="gray60").pack(pady=40)
            return

        self._unregister_all_hotkeys()

        # Filtro de busca — apenas na memoria, sem reler disco
        term = ""
        if hasattr(self, "_search_var"):
            term = self._search_var.get().strip().lower()

        workflows = self._workflow_cache
        if term:
            workflows = [(wf, fn) for wf, fn in workflows
                         if term in wf.get("name", fn).lower()]

        if not workflows:
            ctk.CTkLabel(self._list_frame,
                         text=f"Nenhum workflow encontrado para '{term}'.",
                         text_color="gray60").pack(pady=40)
            return

        # Detecta conflitos de hotkey
        hotkey_count: dict[str, int] = {}
        for wf, _ in self._workflow_cache:
            hk = wf.get("hotkey", "").strip()
            if hk:
                hotkey_count[hk] = hotkey_count.get(hk, 0) + 1

        for wf, filename in workflows:
            hk = wf.get("hotkey", "").strip()
            conflict = bool(hk and hotkey_count.get(hk, 0) > 1)
            self._build_workflow_row(wf, filename, conflict=conflict)
            if not conflict:
                self._register_hotkey(wf, filename)

    def _build_workflow_row(self, wf: dict, filename: str, conflict: bool = False):
        row = ctk.CTkFrame(self._list_frame)
        row.pack(fill="x", pady=5, padx=8)
        row.grid_columnconfigure(1, weight=1)
        row.bind("<Double-Button-1>", lambda e, w=wf, fn=filename: self._edit_workflow(w, fn))

        # Badge hotkey (ou aviso de conflito)
        hotkey = wf.get("hotkey", "")
        if hotkey and conflict:
            ctk.CTkLabel(row, text=f"⚠ {hotkey}",
                         fg_color="#7a3a00", corner_radius=6,
                         width=60, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="white").grid(row=0, column=0, padx=(12, 8), pady=10)
        elif hotkey:
            ctk.CTkLabel(row, text=hotkey,
                         fg_color="#1f538d", corner_radius=6,
                         width=40, font=ctk.CTkFont(size=11, weight="bold")).grid(
                row=0, column=0, padx=(12, 8), pady=10)
        else:
            ctk.CTkFrame(row, width=40, fg_color="transparent").grid(row=0, column=0)

        # Nome + badge de variaveis
        name_frame = ctk.CTkFrame(row, fg_color="transparent")
        name_frame.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        name_frame.grid_columnconfigure(0, weight=1)
        name_frame.bind("<Double-Button-1>", lambda e, w=wf, fn=filename: self._edit_workflow(w, fn))

        ctk.CTkLabel(name_frame, text=wf.get("name", filename),
                     font=ctk.CTkFont(size=14), anchor="w").grid(
            row=0, column=0, sticky="ew")

        var_values = wf.get("variaveis_valores", {})
        if var_values:
            empty = [k for k, v in var_values.items() if not str(v).strip()]
            badge_color = "#7a4a00" if empty else "#1a4a7a"
            badge_tip = f"{len(empty)} sem valor" if empty else f"{len(var_values)} var(s)"
            ctk.CTkLabel(name_frame, text=f"  ⚙ {badge_tip}  ",
                         fg_color=badge_color, corner_radius=4,
                         font=ctk.CTkFont(size=10), text_color="white").grid(
                row=0, column=1, padx=(8, 0))

        # Botoes de acao
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(4, 12), pady=6)

        ctk.CTkButton(btn_frame, text="Executar", width=76,
                      fg_color="#1a7a1a", hover_color="#145a14",
                      command=lambda w=wf: self._run_workflow(w)).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Editar", width=64,
                      command=lambda w=wf, fn=filename: self._edit_workflow(w, fn)).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="Dup", width=44,
                      fg_color="gray40", hover_color="gray30",
                      command=lambda fn=filename: self._dup_workflow(fn)).pack(side="left", padx=3)
        ctk.CTkButton(btn_frame, text="✕", width=32,
                      fg_color="#8B1A1A", hover_color="#6B0000",
                      command=lambda fn=filename: self._delete_workflow(fn)).pack(side="left", padx=3)

    # ------------------------------------------------------------------
    # Acoes de workflow
    # ------------------------------------------------------------------
    def _new_workflow(self):
        WORKFLOWS_DIR.mkdir(exist_ok=True)
        existing = {p.stem for p in WORKFLOWS_DIR.glob("*.json")}
        base = "novo_workflow"
        name = base
        n = 1
        while name in existing:
            name = f"{base}_{n}"
            n += 1
        filename = name + ".json"
        wf = {"name": "Novo Workflow", "hotkey": "", "steps": []}
        path = WORKFLOWS_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        self._show_editor(wf, filename)

    def _import_workflow(self):
        path = filedialog.askopenfilename(
            title="Importar Workflow",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        src = Path(path)
        # Valida que é um JSON de workflow antes de importar
        try:
            with open(src, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "steps" not in data:
                self._show_error("Arquivo invalido: nao e um workflow AutoFlow.")
                return
        except Exception as e:
            self._show_error(f"Nao foi possivel ler o arquivo:\n{e}")
            return
        WORKFLOWS_DIR.mkdir(exist_ok=True)
        dest = WORKFLOWS_DIR / src.name
        if dest.exists():
            stem = src.stem
            n = 1
            while True:
                new_name = f"{stem}_{n}.json"
                dest = WORKFLOWS_DIR / new_name
                if not dest.exists():
                    break
                n += 1
        shutil.copy(src, dest)
        log.info(f"Workflow importado: {dest.name}")
        self._workflow_cache = []  # invalida cache
        if self._refresh_tray:
            self._refresh_tray()
        self._show_list_view()

    def _edit_workflow(self, wf: dict, filename: str):
        self._show_editor(wf, filename)

    def _dup_workflow(self, filename: str):
        src = WORKFLOWS_DIR / filename
        stem = src.stem
        n = 1
        while True:
            new_name = f"{stem}_copia{n}.json"
            if not (WORKFLOWS_DIR / new_name).exists():
                break
            n += 1
        shutil.copy(src, WORKFLOWS_DIR / new_name)
        self._workflow_cache = []  # invalida cache
        self._show_list_view()

    def _delete_workflow(self, filename: str):
        dlg = ctk.CTkInputDialog(text=f"Digite 'SIM' para excluir {filename}:",
                                 title="Confirmar exclusao")
        if dlg.get_input() == "SIM":
            (WORKFLOWS_DIR / filename).unlink(missing_ok=True)
            log.info(f"Workflow excluido: {filename}")
            self._workflow_cache = []  # invalida cache
            if self._refresh_tray:
                self._refresh_tray()
            self._show_list_view()

    def _on_workflow_saved(self, wf: dict):
        self._workflow_cache = []  # invalida cache
        if self._refresh_tray:
            self._refresh_tray()
        # Defer navigation to avoid destroying CTk widgets while their
        # cleanup callbacks are still queued in the event loop.
        self.after(0, self._show_list_view)

    # ------------------------------------------------------------------
    # Execucao
    # ------------------------------------------------------------------
    def _set_status(self, text: str, *, error: bool = False, progress: float | None = None):
        color = "#e05a5a" if error else "gray50"
        self._status_label.configure(text=text, text_color=color)
        if progress is not None:
            self._progress_bar.set(max(0.0, min(1.0, progress)))
            self._progress_bar.grid()
        else:
            self._progress_bar.grid_remove()

    def _substitute_vars(self, wf: dict, values: dict) -> dict:
        import copy
        wf = copy.deepcopy(wf)

        def _sub(obj):
            if isinstance(obj, str):
                for k, v in values.items():
                    obj = obj.replace(f"{{{{{k}}}}}", str(v))
                return obj
            if isinstance(obj, dict):
                return {key: _sub(val) for key, val in obj.items()}
            if isinstance(obj, list):
                return [_sub(item) for item in obj]
            return obj

        return _sub(wf)

    def _check_missing_templates(self, steps: list) -> list:
        """Varre steps recursivamente e retorna templates PNG ausentes."""
        missing = []
        for step in steps:
            if step.get("tipo") in ("wait_image", "if_image"):
                tmpl = step.get("template", "")
                if tmpl and not (runner.TMPL / tmpl).exists() and tmpl not in missing:
                    missing.append(tmpl)
            for sub_key in ("steps", "steps_sim", "steps_nao"):
                for m in self._check_missing_templates(step.get(sub_key, [])):
                    if m not in missing:
                        missing.append(m)
        return missing

    def _warn_missing_templates(self, missing: list) -> bool:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Templates nao encontrados")
        dlg.geometry("440x240")
        dlg.grab_set()
        dlg.lift()
        dlg.resizable(False, False)
        result = [False]

        ctk.CTkLabel(dlg, text="Os seguintes templates PNG nao foram encontrados:",
                     font=ctk.CTkFont(size=13, weight="bold"), wraplength=400).pack(padx=20, pady=(20, 8))
        ctk.CTkLabel(dlg, text="\n".join(f"  • {t}" for t in missing),
                     font=ctk.CTkFont(family="Courier New", size=12),
                     text_color="#e0a040", justify="left", wraplength=400).pack(padx=20, pady=4)
        ctk.CTkLabel(dlg, text="O step vai aguardar o timeout inteiro antes de falhar.",
                     font=ctk.CTkFont(size=11), text_color="gray55", wraplength=400).pack(padx=20, pady=(8, 16))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=(0, 20))

        def _cancel():
            result[0] = False
            dlg.destroy()

        def _proceed():
            result[0] = True
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Cancelar", width=110,
                      fg_color="gray40", hover_color="gray30",
                      command=_cancel).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Executar assim mesmo", width=170,
                      fg_color="#7a4a00", hover_color="#5a3400",
                      command=_proceed).pack(side="left", padx=8)
        dlg.wait_window()
        return result[0]

    def _find_unresolved_vars(self, wf: dict) -> list:
        """Retorna lista de {{VAR}} presentes nos steps sem valor definido."""
        import re
        pattern = re.compile(r'\{\{(\w+)\}\}')
        valores = wf.get("variaveis_valores", {})

        def scan(steps):
            found = []
            for step in steps:
                for field in ("texto", "arquivo", "url", "selector", "script", "valor",
                              "valor_comparar", "valor_ref"):
                    for v in pattern.findall(step.get(field, "")):
                        if (v not in valores or not str(valores[v]).strip()) and v not in found:
                            found.append(v)
                for sub_key in ("steps", "steps_sim", "steps_nao"):
                    found += [v for v in scan(step.get(sub_key, [])) if v not in found]
            return found

        return scan(wf.get("steps", []))

    def _add_history(self, name: str, status: str, error: str = ""):
        self._run_history.append({
            "name": name,
            "timestamp": datetime.datetime.now().strftime("%d/%m %H:%M:%S"),
            "status": status,
            "error": error,
        })
        if len(self._run_history) > 200:
            self._run_history = self._run_history[-200:]
        self._save_history()

    def _toggle_pause(self):
        if runner.is_paused():
            runner.resume()
            self.after(0, lambda: self._set_status("● Executando... — P pausa / ESC cancela"))
        else:
            runner.pause()
            self.after(0, lambda: self._set_status("⏸ Pausado — P retoma / ESC cancela"))

    def _run_workflow(self, wf: dict):
        import keyboard
        if runner.is_running():
            runner.stop()
            return

        # Verificar e editar variaveis antes de executar
        import copy
        valores_atuais       = dict(wf.get("variaveis_valores", {}))
        variaveis_meta       = wf.get("variaveis", {})
        variaveis_perguntar  = wf.get("variaveis_perguntar", {})
        variaveis_perm_vazio = wf.get("variaveis_permitir_vazio", {})

        # Monta a lista completa de nomes de variaveis conhecidas
        all_names = list(valores_atuais.keys())
        for k in variaveis_meta:
            if k not in all_names:
                all_names.append(k)

        # Filtra apenas as que precisam de popup:
        #   - marcadas como "perguntar", OU
        #   - sem valor E sem "permitir_vazio" (vazio intencional nao precisa de popup)
        vars_para_popup = {
            name: valores_atuais.get(name, "")
            for name in all_names
            if variaveis_perguntar.get(name, False)
            or (
                not str(valores_atuais.get(name, "")).strip()
                and not variaveis_perm_vazio.get(name, False)
            )
        }

        if vars_para_popup:
            novos = self._prompt_vars_dialog(vars_para_popup, variaveis_meta)
            if novos is None:
                return  # usuario cancelou
            merged = {**valores_atuais, **novos}
            wf = self._substitute_vars(wf, merged)
            wf = copy.deepcopy(wf)
            wf["variaveis_valores"] = merged
        elif all_names:
            # Todas as variaveis sao fixas/vazias-intencionais — substitui silenciosamente
            wf = self._substitute_vars(wf, valores_atuais)
            wf = copy.deepcopy(wf)
            wf["variaveis_valores"] = valores_atuais
        else:
            # Sem variaveis cadastradas — verifica {{VAR}} soltos nos steps
            unresolved = self._find_unresolved_vars(wf)
            if unresolved:
                if not self._warn_unresolved_vars(wf, unresolved):
                    return

        # Verificar templates faltando antes de executar
        missing_tmpls = self._check_missing_templates(wf.get("steps", []))
        if missing_tmpls:
            if not self._warn_missing_templates(missing_tmpls):
                return

        self.iconify()
        wf_name = wf.get("name", "?")
        total = len(wf.get("steps", []))
        self._exec_log = []

        self._cancel_hotkey = keyboard.add_hotkey("esc", runner.stop)
        self._pause_hotkey = keyboard.add_hotkey("p", self._toggle_pause)

        def _cleanup():
            for attr in ("_cancel_hotkey", "_pause_hotkey"):
                hk = getattr(self, attr, None)
                if hk is not None:
                    try:
                        keyboard.remove_hotkey(hk)
                    except Exception:
                        pass
                    setattr(self, attr, None)

        def _ts():
            return datetime.datetime.now().strftime("%H:%M:%S")

        def _on_step(idx, step):
            tipo = step.get("tipo", "")
            details = runner._step_details(step)
            detail_str = f"  [{details}]" if details else ""
            self._exec_log.append(f"[{_ts()}]  Step {idx + 1}/{total}:  {tipo}{detail_str}")
            progress = (idx + 1) / total if total > 0 else 0
            self.after(0, lambda: self._set_status(
                f"● Step {idx + 1}/{total}: {tipo} — P pausa / ESC cancela",
                progress=progress,
            ))

        def _done():
            self._exec_log.append(f"[{_ts()}]  ✓ Concluido")
            _cleanup()
            self.after(0, lambda: self._set_status("✓ Concluido", progress=1.0))
            self.after(0, lambda: self._add_history(wf_name, "ok"))
            # Notificacao Windows via pystray
            if self._tray_icon:
                try:
                    self._tray_icon.notify(f"Workflow '{wf_name}' concluido com sucesso.", "AutoFlow")
                except Exception:
                    pass
            self.after(800, self.deiconify)

        def _error(msg):
            self._exec_log.append(f"[{_ts()}]  ✗ Erro: {msg}")
            _cleanup()
            self.after(0, lambda: self._show_error(msg))
            self.after(0, lambda: self._set_status(f"Erro: {msg}", error=True, progress=0))
            self.after(0, lambda: self._add_history(wf_name, "erro", msg))
            self.after(800, self.deiconify)

        def _cancelled():
            self._exec_log.append(f"[{_ts()}]  ⊘ Cancelado")
            _cleanup()
            self.after(0, lambda: self._set_status("Cancelado", progress=0))
            self.after(0, lambda: self._add_history(wf_name, "cancelado"))
            self.after(500, self.deiconify)

        runner.run_workflow(wf, on_step=_on_step, on_done=_done,
                            on_error=_error, on_cancel=_cancelled)

    def _show_error(self, msg: str):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Erro na execucao")
        dlg.geometry("520x280")
        dlg.grab_set()
        dlg.lift()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Erro na execucao",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#e05a5a").grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=11),
                             text_color="#e05a5a", wrap="word")
        box.grid(row=1, column=0, padx=16, pady=4, sticky="nsew")
        box.insert("1.0", msg)
        box.configure(state="disabled")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=(4, 16))

        def _copy():
            dlg.clipboard_clear()
            dlg.clipboard_append(msg)

        ctk.CTkButton(btn_row, text="Copiar", width=90,
                      fg_color="gray40", hover_color="gray30",
                      command=_copy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="OK", width=90,
                      command=dlg.destroy).pack(side="left", padx=8)

    def _prompt_vars_dialog(self, valores: dict, meta: dict) -> "dict | None":
        """Mostra dialog com todas as variaveis para edicao rapida antes de executar.
        Retorna dict com valores novos, ou None se cancelado."""
        if not valores and not meta:
            return {}

        dlg = ctk.CTkToplevel(self)
        dlg.title("Variaveis do Workflow")
        dlg.grab_set()
        dlg.lift()
        dlg.resizable(False, False)

        result = [None]
        entries = {}

        frame = ctk.CTkFrame(dlg, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Confirme ou edite os valores antes de executar:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 12))

        all_vars = list(valores.keys())
        for v in meta:
            if v not in all_vars:
                all_vars.append(v)

        for var in all_vars:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            desc = meta.get(var, "")
            label_text = f"  {{{{{var}}}}}  {('— ' + desc) if desc else ''}"
            ctk.CTkLabel(row, text=label_text, width=200, anchor="w",
                         font=ctk.CTkFont(family="Courier New", size=11),
                         text_color="gray70").pack(side="left")
            e = ctk.CTkEntry(row, width=220)
            e.insert(0, str(valores.get(var, "")))
            e.pack(side="left", padx=(8, 0))
            entries[var] = e

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=(16, 0))

        def _cancel():
            result[0] = None
            dlg.destroy()

        def _ok():
            result[0] = {k: e.get() for k, e in entries.items()}
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Cancelar", width=100,
                      fg_color="gray40", hover_color="gray30",
                      command=_cancel).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Executar", width=120,
                      fg_color="#1a7a1a", hover_color="#145a14",
                      command=_ok).pack(side="left", padx=8)

        dlg.bind("<Return>", lambda e: _ok())
        dlg.bind("<Escape>", lambda e: _cancel())

        # Tamanho dinamico
        height = 140 + len(all_vars) * 46
        dlg.geometry(f"500x{min(height, 520)}")
        dlg.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        py = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{px}+{py}")

        dlg.wait_window()
        return result[0]

    def _export_all_zip(self):
        import zipfile
        dest = filedialog.asksaveasfilename(
            title="Exportar todos os workflows",
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip")],
            initialfile=f"autoflow_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        )
        if not dest:
            return
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in WORKFLOWS_DIR.glob("*.json"):
                zf.write(f, f"workflows/{f.name}")
        log.info(f"Backup ZIP exportado: {dest}")

    def _warn_unresolved_vars(self, wf: dict, unresolved: list) -> bool:
        """
        Exibe aviso sobre variaveis sem valor. Retorna True se o usuario optar
        por executar assim mesmo, False para cancelar (ir editar).
        """
        dlg = ctk.CTkToplevel(self)
        dlg.title("Variaveis sem valor")
        dlg.geometry("440x260")
        dlg.grab_set()
        dlg.lift()
        dlg.resizable(False, False)

        result = [False]

        ctk.CTkLabel(
            dlg,
            text="As seguintes variaveis nao tem valor definido:",
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=400,
        ).pack(padx=20, pady=(20, 8))

        var_text = "  ".join(f"{{{{{v}}}}}" for v in unresolved)
        ctk.CTkLabel(
            dlg,
            text=var_text,
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color="#e0a040",
            wraplength=400,
        ).pack(padx=20, pady=4)

        ctk.CTkLabel(
            dlg,
            text="Os placeholders serao mantidos no texto (nao substituidos).\nDefina os valores na aba Variaveis do editor antes de executar.",
            font=ctk.CTkFont(size=11),
            text_color="gray55",
            wraplength=400,
            justify="center",
        ).pack(padx=20, pady=(8, 16))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=(0, 20))

        def _cancel():
            result[0] = False
            dlg.destroy()

        def _proceed():
            result[0] = True
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Cancelar", width=110,
                      fg_color="gray40", hover_color="gray30",
                      command=_cancel).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Executar assim mesmo", width=170,
                      fg_color="#7a4a00", hover_color="#5a3400",
                      command=_proceed).pack(side="left", padx=8)

        dlg.wait_window()
        return result[0]

    # ------------------------------------------------------------------
    # Hotkeys globais
    # ------------------------------------------------------------------
    def _register_hotkey(self, wf: dict, filename: str):
        import keyboard
        hotkey = wf.get("hotkey", "").strip()
        if not hotkey:
            return
        try:
            keyboard.add_hotkey(hotkey, lambda w=wf: self._run_workflow(w))
            self._hotkey_registry[hotkey] = filename
        except Exception:
            pass

    def _unregister_all_hotkeys(self):
        import keyboard
        for hk in list(self._hotkey_registry.keys()):
            try:
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self._hotkey_registry.clear()

    # ------------------------------------------------------------------
    # Configuracoes (PAUSE / FAILSAFE)
    # ------------------------------------------------------------------
    def _open_settings(self):
        import os
        dlg = ctk.CTkToplevel(self)
        dlg.title("Configuracoes")
        dlg.geometry("360x320")
        dlg.grab_set()
        dlg.lift()

        pause_var = ctk.DoubleVar(value=runner.pyautogui.PAUSE)
        fs_var = ctk.BooleanVar(value=runner.pyautogui.FAILSAFE)

        frame = ctk.CTkFrame(dlg, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="PAUSE (s):").grid(row=0, column=0, sticky="w", pady=6)
        ctk.CTkEntry(frame, textvariable=pause_var, width=80).grid(row=0, column=1, padx=8, pady=6)

        ctk.CTkLabel(frame, text="FAILSAFE:").grid(row=1, column=0, sticky="w", pady=6)
        ctk.CTkSwitch(frame, variable=fs_var, text="").grid(row=1, column=1, padx=8, pady=6, sticky="w")

        def _apply():
            runner.pyautogui.PAUSE = pause_var.get()
            runner.pyautogui.FAILSAFE = fs_var.get()
            self._save_settings()
            dlg.destroy()

        ctk.CTkButton(frame, text="Aplicar", command=_apply).grid(
            row=2, column=0, columnspan=2, pady=(16, 0))

        sep = ctk.CTkFrame(frame, height=1, fg_color="gray30")
        sep.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 8))

        def _open_logs():
            logs_dir = _log_module.LOGS_DIR
            logs_dir.mkdir(exist_ok=True)
            os.startfile(str(logs_dir))

        def _export_log():
            if not self._exec_log:
                return
            dest = filedialog.asksaveasfilename(
                title="Exportar log",
                defaultextension=".txt",
                filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
                initialfile=f"autoflow_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )
            if dest:
                Path(dest).write_text("\n".join(self._exec_log), encoding="utf-8")

        ctk.CTkButton(frame, text="Abrir pasta de logs", width=200,
                      fg_color="gray35", hover_color="gray25",
                      command=_open_logs).grid(row=4, column=0, columnspan=2, pady=4)
        ctk.CTkButton(frame, text="Exportar log da ultima execucao", width=200,
                      fg_color="gray35", hover_color="gray25",
                      command=_export_log).grid(row=5, column=0, columnspan=2, pady=4)
        ctk.CTkButton(frame, text="Exportar backup ZIP de todos os workflows", width=200,
                      fg_color="gray35", hover_color="gray25",
                      command=lambda: (dlg.destroy(), self._export_all_zip())).grid(
            row=6, column=0, columnspan=2, pady=4)

    # ------------------------------------------------------------------
    # Historico de execucoes
    # ------------------------------------------------------------------
    def _show_history_view(self):
        self._clear_container()
        self._container.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self._container, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
        ctk.CTkButton(header, text="← Voltar", width=80,
                      fg_color="gray40", hover_color="gray30",
                      command=self._show_list_view).pack(side="left")
        ctk.CTkLabel(header, text="Historico de Execucoes",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=12)
        ctk.CTkButton(header, text="Limpar", width=70,
                      fg_color="gray40", hover_color="gray30",
                      command=self._clear_history).pack(side="right")

        scroll = ctk.CTkScrollableFrame(frame, label_text="")
        scroll.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        if not self._run_history:
            ctk.CTkLabel(scroll, text="Nenhuma execucao registrada ainda.",
                         text_color="gray60").pack(pady=40)
            return

        for entry in reversed(self._run_history):
            self._build_history_row(scroll, entry)

    def _build_history_row(self, parent, entry: dict):
        colors = {"ok": "#1a6a1a", "erro": "#8B1A1A", "cancelado": "#6b5500"}
        labels = {"ok": "  OK  ", "erro": " ERRO ", "cancelado": " STOP "}
        status = entry["status"]

        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=3, padx=4)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text=labels.get(status, status),
                     fg_color=colors.get(status, "gray40"), corner_radius=6,
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=0, column=0, padx=(10, 8), pady=8)
        ctk.CTkLabel(row, text=entry["name"], anchor="w",
                     font=ctk.CTkFont(size=13)).grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        ctk.CTkLabel(row, text=entry["timestamp"], text_color="gray60",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(4, 10), pady=8)

        if entry.get("error"):
            ctk.CTkLabel(parent, text=f"  ↳ {entry['error'][:90]}",
                         text_color="#e05a5a", anchor="w",
                         font=ctk.CTkFont(size=11)).pack(fill="x", padx=18)

    def _clear_history(self):
        self._run_history.clear()
        self._save_history()
        self._show_history_view()

    # ------------------------------------------------------------------
    # Log de execucao
    # ------------------------------------------------------------------
    def _show_exec_log(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Log da ultima execucao")
        dlg.geometry("520x380")
        dlg.lift()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(0, weight=1)

        box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
        box.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")

        if self._exec_log:
            box.insert("1.0", "\n".join(self._exec_log))
        else:
            box.insert("1.0", "(Nenhuma execucao registrada ainda)")
        box.configure(state="disabled")

        ctk.CTkButton(dlg, text="Fechar", command=dlg.destroy).grid(
            row=1, column=0, pady=(0, 16))

    # ------------------------------------------------------------------
    # Fechar -> minimizar para tray
    # ------------------------------------------------------------------
    def _on_close(self):
        self.iconify()
        if self._tray_icon:
            self.withdraw()
        else:
            self.destroy()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()
