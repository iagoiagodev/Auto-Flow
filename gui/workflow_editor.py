"""
workflow_editor.py — Tela de edicao de um workflow (nome, hotkey, lista de steps).
"""

import sys
import json
import re
import customtkinter as ctk
from pathlib import Path
from gui.step_editor import StepEditorDialog



_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
WORKFLOWS_DIR = _BASE / "workflows"
STEP_LABELS = {
    "click":      lambda s: f"click[{s.get('clique','simples')}]  ({s.get('x')}, {s.get('y')})",
    "paste":      lambda s: f"paste  \"{s.get('texto','')[:40]}\"",
    "type":       lambda s: f"type  \"{s.get('texto','')[:35]}\"  @{s.get('intervalo',0.08)}s",
    "press":      lambda s: f"press  {s.get('tecla','')}",
    "hotkey":     lambda s: f"hotkey  {s.get('combinacao','')}",
    "scroll":     lambda s: f"scroll  {'+' if int(s.get('quantidade',3))>0 else ''}{s.get('quantidade',3)}",
    "wait_image": lambda s: f"wait_image  {s.get('template','')}  conf={s.get('confidence',0.8)}  [{s.get('ao_falhar','erro')}]",
    "sleep":      lambda s: f"sleep  {s.get('segundos',1.0)}s",
    "screenshot": lambda s: f"screenshot  {s.get('arquivo','')}",
    "loop":       lambda s: f"loop  {s.get('repeticoes',1)}x  ({len(s.get('steps',[]))} sub-steps)",
    "if_image":   lambda s: f"if_image  {s.get('template','')}  timeout={s.get('timeout',5)}s  [SIM:{len(s.get('steps_sim',[]))}  NAO:{len(s.get('steps_nao',[]))}]",
    "loop_lista": lambda s: f"loop_lista  {{{{{s.get('variavel','')}}}}}  {len(s.get('lista',[]))} itens  ({len(s.get('steps',[]))} sub-steps)",
    "if_var":           lambda s: f"if_var  {{{{{s.get('valor_comparar','')}}}}}  {s.get('operador','igual')}  \"{s.get('valor_ref','')}\"  [SIM:{len(s.get('steps_sim',[]))}  NAO:{len(s.get('steps_nao',[]))}]",
    "browser_open":     lambda s: f"browser_open  {s.get('browser','chrome')}  {s.get('url','')}{'  [headless]' if s.get('headless') else ''}",
    "browser_close":    lambda s: "browser_close",
    "browser_navigate": lambda s: f"browser_navigate  {s.get('url','')}",
    "browser_click":    lambda s: f"browser_click  [{s.get('por','css')}]  {s.get('selector','')}",
    "browser_fill":     lambda s: f"browser_fill  [{s.get('por','css')}]  {s.get('selector','')}  \"{s.get('texto','')[:30]}\"",
    "browser_wait":     lambda s: f"browser_wait  [{s.get('por','css')}]  {s.get('selector','')}  cond={s.get('condicao','presente')}  {s.get('timeout',10)}s",
    "browser_select":   lambda s: f"browser_select  [{s.get('por','css')}]  {s.get('selector','')}  val={s.get('valor','')}",
    "browser_get_text": lambda s: f"browser_get_text  [{s.get('por','css')}]  {s.get('selector','')}  → {{{{{s.get('variavel','')}}}}}",
    "browser_run_js":   lambda s: f"browser_run_js  {s.get('script','')[:50]}",
    "browser_screenshot": lambda s: f"browser_screenshot  {s.get('arquivo','')}",
    "click_image":   lambda s: f"click_image  {s.get('template','')}  conf={s.get('confidence',0.8)}  [{s.get('clique','simples')}]",
    "move_to_image": lambda s: f"move_to_image  {s.get('template','')}  conf={s.get('confidence',0.8)}",
    "click_text":    lambda s: f"click_text  \"{s.get('texto','')}\"  [{s.get('clique','simples')}]",
    "wait_text":     lambda s: f"wait_text  \"{s.get('texto','')}\"  timeout={s.get('timeout',30)}s  [{s.get('ao_falhar','erro')}]",
    "run_workflow":  lambda s: f"run_workflow  →  {s.get('workflow','')}",
    "get_clipboard": lambda s: f"get_clipboard  →  {{{{{s.get('variavel','')}}}}}",
    "browser_get_url": lambda s: f"browser_get_url  →  {{{{{s.get('variavel','')}}}}}",
}

STEP_COLORS = {
    # Desktop — azul acinzentado
    "click": "#1a3a5a", "paste": "#1a3a5a", "type": "#1a3a5a",
    "press": "#1a3a5a", "hotkey": "#1a3a5a", "scroll": "#1a3a5a",
    # Imagem — laranja escuro
    "wait_image": "#5a3a00", "click_image": "#5a3a00",
    "move_to_image": "#5a3a00", "click_text": "#5a3a00", "wait_text": "#5a3a00",
    # Fluxo — roxo escuro
    "loop": "#3a1a5a", "if_image": "#3a1a5a",
    "loop_lista": "#3a1a5a", "if_var": "#3a1a5a",
    # Browser — verde escuro
    "browser_open": "#0a3a1a", "browser_close": "#0a3a1a",
    "browser_navigate": "#0a3a1a", "browser_click": "#0a3a1a",
    "browser_fill": "#0a3a1a", "browser_wait": "#0a3a1a",
    "browser_select": "#0a3a1a", "browser_get_text": "#0a3a1a",
    "browser_run_js": "#0a3a1a", "browser_screenshot": "#0a3a1a",
    "browser_get_url": "#0a3a1a",
    # Util — cinza
    "sleep": "#2a2a2a", "screenshot": "#2a2a2a",
    "run_workflow": "#3a1a3a", "get_clipboard": "#2a2a2a",
}


def _step_label(step: dict) -> str:
    fn = STEP_LABELS.get(step.get("tipo", ""), lambda s: str(s))
    return fn(step)


class WorkflowEditorFrame(ctk.CTkFrame):
    """
    Exibida como conteudo principal quando o usuario abre um workflow para editar.
    Chama on_save(workflow) ao salvar e on_back() para voltar a lista.
    """

    _VAR_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    def __init__(self, parent, workflow: dict, filename: str,
                 on_save=None, on_back=None, on_run_from=None):
        super().__init__(parent, fg_color="transparent")
        self._workflow = json.loads(json.dumps(workflow))  # deep copy
        self._original = json.loads(json.dumps(workflow))  # para detectar alteracoes nao salvas
        self._filename = filename
        self._on_save = on_save
        self._on_back = on_back
        self._on_run_from = on_run_from
        # list[dict]: cada dict = {"name": str, "label": str, "value": str}
        self._var_entries: list[dict] = []
        self._deleted_step: dict | None = None   # para undo
        self._deleted_step_idx: int = -1
        self._copied_step: dict | None = None    # para copy/paste
        self._build_ui()
        self._refresh_steps()
        self._load_var_entries()

    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Cabecalho
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        ctk.CTkButton(header, text="← Voltar", width=80,
                      fg_color="gray40", hover_color="gray30",
                      command=self._back).pack(side="left")
        ctk.CTkLabel(header, text="Editor de Workflow",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=12)

        # Nome + Hotkey
        meta_frame = ctk.CTkFrame(self)
        meta_frame.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        meta_frame.grid_columnconfigure(1, weight=1)
        meta_frame.grid_columnconfigure(3, weight=0)

        ctk.CTkLabel(meta_frame, text="Nome:", width=60, anchor="w").grid(row=0, column=0, padx=(12, 4), pady=10)
        self._name_entry = ctk.CTkEntry(meta_frame, placeholder_text="Nome do workflow")
        self._name_entry.insert(0, self._workflow.get("name", ""))
        self._name_entry.grid(row=0, column=1, padx=4, pady=10, sticky="ew")

        ctk.CTkLabel(meta_frame, text="Hotkey:", width=60, anchor="w").grid(row=0, column=2, padx=(16, 4), pady=10)
        self._hotkey_entry = ctk.CTkEntry(meta_frame, width=80, placeholder_text="F8")
        self._hotkey_entry.insert(0, self._workflow.get("hotkey", ""))
        self._hotkey_entry.grid(row=0, column=3, padx=(4, 12), pady=10)
        self._hotkey_entry.bind("<FocusOut>", self._validate_hotkey)

        ctk.CTkLabel(meta_frame, text="Repeticoes:", width=80, anchor="w").grid(row=1, column=0, padx=(12, 4), pady=(0, 6))
        self._reps_entry = ctk.CTkEntry(meta_frame, width=60)
        self._reps_entry.insert(0, str(self._workflow.get("repeticoes", 1)))
        self._reps_entry.grid(row=1, column=1, padx=4, pady=(0, 6), sticky="w")
        ctk.CTkLabel(meta_frame, text="(quantas vezes executar o workflow completo)",
                     text_color="gray60", font=ctk.CTkFont(size=11)).grid(
            row=1, column=2, columnspan=2, padx=(4, 12), pady=(0, 6), sticky="w")

        ctk.CTkLabel(meta_frame, text="Delay rep. (s):", width=80, anchor="w").grid(row=2, column=0, padx=(12, 4), pady=(0, 10))
        self._delay_entry = ctk.CTkEntry(meta_frame, width=60)
        self._delay_entry.insert(0, str(self._workflow.get("delay_entre_repeticoes", 0)))
        self._delay_entry.grid(row=2, column=1, padx=4, pady=(0, 10), sticky="w")
        ctk.CTkLabel(meta_frame, text="(segundos de pausa entre cada repeticao)",
                     text_color="gray60", font=ctk.CTkFont(size=11)).grid(
            row=2, column=2, columnspan=2, padx=(4, 12), pady=(0, 10), sticky="w")

        # Tab view: Steps | Variaveis
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=2, column=0, padx=20, pady=(4, 0), sticky="nsew")

        self._tab_steps = self._tabs.add("  Steps  ")
        self._tab_vars = self._tabs.add("  Variaveis  ")

        self._build_steps_tab(self._tab_steps)
        self._build_vars_tab(self._tab_vars)

        # Salvar
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, padx=20, pady=(8, 20), sticky="ew")
        ctk.CTkButton(footer, text="Salvar  (Ctrl+S)", command=self._save).pack(side="right")

        # Ctrl+S global no toplevel
        self._ctrl_s_id = self.winfo_toplevel().bind("<Control-s>", lambda e: self._save())
        self.bind("<Destroy>", self._on_destroy)

    # ------------------------------------------------------------------
    def _build_steps_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 0))
        top.grid_columnconfigure(0, weight=1)

        self._step_search_var = ctk.StringVar()
        self._step_search_var.trace_add("write", lambda *_: self._refresh_steps())
        ctk.CTkEntry(top, textvariable=self._step_search_var,
                     placeholder_text="Buscar step...").pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._undo_btn = ctk.CTkButton(top, text="Desfazer", width=100,
                                        fg_color="gray35", hover_color="gray25",
                                        command=self._undo_delete)
        # botao fica oculto ate ter algo para desfazer

        self._paste_btn = ctk.CTkButton(top, text="Colar Step", width=100,
                                         fg_color="gray35", hover_color="gray25",
                                         command=self._paste_step)

        self._steps_scroll = ctk.CTkScrollableFrame(parent, label_text="")
        self._steps_scroll.grid(row=1, column=0, sticky="nsew")

        steps_footer = ctk.CTkFrame(parent, fg_color="transparent")
        steps_footer.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ctk.CTkButton(steps_footer, text="+ Adicionar Step",
                      command=self._add_step).pack(side="left")

    def _build_vars_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # Barra de acoes
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 2))
        ctk.CTkButton(top, text="Auto-detectar", width=130,
                      fg_color="gray40", hover_color="gray30",
                      command=self._detect_vars).pack(side="left")
        ctk.CTkButton(top, text="+ Adicionar variavel", width=150,
                      command=self._add_var_row).pack(side="left", padx=8)
        ctk.CTkLabel(top,
                     text="Use {{NOME}} nos steps de paste/type para referenciar variaveis",
                     text_color="gray55", font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        # Feedback da deteccao
        self._detect_feedback_label = ctk.CTkLabel(
            parent, text="", text_color="gray55", font=ctk.CTkFont(size=11), anchor="w")
        self._detect_feedback_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))

        # Lista de variaveis (scroll simples)
        self._vars_scroll = ctk.CTkScrollableFrame(parent)
        self._vars_scroll.grid(row=2, column=0, sticky="nsew")
        self._vars_scroll.grid_columnconfigure(0, weight=1)

        self._refresh_var_list()

    # ------------------------------------------------------------------
    # Logica da aba Variaveis
    # ------------------------------------------------------------------
    def _load_var_entries(self):
        """Popula _var_entries com os dados salvos no workflow."""
        self._var_entries.clear()
        existing_labels        = self._workflow.get("variaveis", {})
        existing_values        = self._workflow.get("variaveis_valores", {})
        existing_perguntar     = self._workflow.get("variaveis_perguntar", {})
        existing_permitir_vazio = self._workflow.get("variaveis_permitir_vazio", {})

        all_names = list(existing_labels.keys())
        for name in existing_values:
            if name not in all_names:
                all_names.append(name)

        for name in all_names:
            self._var_entries.append({
                "name":           name,
                "label":          existing_labels.get(name, ""),
                "value":          existing_values.get(name, ""),
                "perguntar":      existing_perguntar.get(name, False),
                "permitir_vazio": existing_permitir_vazio.get(name, False),
            })
        self._refresh_var_list()

    def _refresh_var_list(self):
        """Reconstroi a lista visual de variaveis no scroll."""
        for w in self._vars_scroll.winfo_children():
            w.destroy()

        if not self._var_entries:
            ctk.CTkLabel(
                self._vars_scroll,
                text="Nenhuma variavel cadastrada.\nClique em '+ Adicionar variavel' ou use 'Auto-detectar'.",
                text_color="gray50", font=ctk.CTkFont(size=12),
            ).pack(pady=30)
            return

        for i, v in enumerate(self._var_entries):
            self._build_var_display_row(i, v)

    def _build_var_display_row(self, idx: int, v: dict):
        """Constroi uma linha de exibicao (somente leitura) para uma variavel."""
        row = ctk.CTkFrame(self._vars_scroll)
        row.pack(fill="x", pady=2, padx=4)
        row.grid_columnconfigure(1, weight=1)

        # Coluna 0 — nome da variavel (monospace, largura fixa)
        name_text = f"{{{{ {v['name']} }}}}" if v["name"] else "{{ ??? }}"
        ctk.CTkLabel(row, text=name_text, width=160, anchor="w",
                     font=ctk.CTkFont(family="Courier New", size=12),
                     text_color="gray85").grid(row=0, column=0, padx=(10, 4), pady=8)

        # Coluna 1 — descricao + valor (expande)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", padx=4, pady=6)

        # Badge de comportamento
        perguntar      = v.get("perguntar", False)
        permitir_vazio = v.get("permitir_vazio", False)
        has_value      = bool(str(v.get("value", "")).strip())

        badge_frame = ctk.CTkFrame(info, fg_color="transparent")
        badge_frame.pack(anchor="w", pady=(0, 2))

        if perguntar:
            ctk.CTkLabel(badge_frame, text="  Pergunta ao executar  ",
                         fg_color="#7a4a00", corner_radius=4,
                         font=ctk.CTkFont(size=10), text_color="white").pack(side="left", padx=(0, 4))
        if permitir_vazio:
            ctk.CTkLabel(badge_frame, text="  Pode ser vazio  ",
                         fg_color="#1a3a5a", corner_radius=4,
                         font=ctk.CTkFont(size=10), text_color="white").pack(side="left", padx=(0, 4))
        if not perguntar and not permitir_vazio:
            color = "#1a3a1a" if has_value else "#5a1a1a"
            txt   = "Valor fixo" if has_value else "Sem valor — pedira ao executar"
            ctk.CTkLabel(badge_frame, text=f"  {txt}  ",
                         fg_color=color, corner_radius=4,
                         font=ctk.CTkFont(size=10), text_color="white").pack(side="left")

        if v["label"]:
            ctk.CTkLabel(info, text=v["label"], anchor="w",
                         font=ctk.CTkFont(size=11), text_color="gray55").pack(fill="x")
        val_text  = v["value"] if v["value"] else "(sem valor)"
        val_color = "gray80"   if v["value"] else "gray40"
        ctk.CTkLabel(info, text=val_text, anchor="w",
                     font=ctk.CTkFont(size=12), text_color=val_color).pack(fill="x")

        # Coluna 2 — botoes Editar + Excluir
        btn = ctk.CTkFrame(row, fg_color="transparent")
        btn.grid(row=0, column=2, padx=(4, 8), pady=6)
        ctk.CTkButton(btn, text="Editar", width=60, height=28,
                      command=lambda i=idx: self._edit_var_at(i)).pack(side="left", padx=2)
        ctk.CTkButton(btn, text="✕", width=28, height=28,
                      fg_color="#8B1A1A", hover_color="#6B0000",
                      command=lambda i=idx: self._remove_var_at(i)).pack(side="left", padx=2)

    def _add_var_row(self, name: str = "", label: str = "", value: str = "", perguntar: bool = False, permitir_vazio: bool = False):
        """Abre o dialog de criacao e adiciona a variavel se confirmada."""
        dlg = VarEditorDialog(self.winfo_toplevel(),
                              {"name": name, "label": label, "value": value,
                               "perguntar": perguntar, "permitir_vazio": permitir_vazio})
        self.wait_window(dlg)
        if dlg.result:
            self._var_entries.append(dlg.result)
            self._refresh_var_list()

    def _edit_var_at(self, idx: int):
        """Abre o dialog pre-preenchido para editar uma variavel existente."""
        dlg = VarEditorDialog(self.winfo_toplevel(), dict(self._var_entries[idx]))
        self.wait_window(dlg)
        if dlg.result:
            self._var_entries[idx] = dlg.result
            self._refresh_var_list()

    def _remove_var_at(self, idx: int):
        self._var_entries.pop(idx)
        self._refresh_var_list()

    def _detect_vars(self):
        """Escaneia os steps e adiciona variaveis ainda nao cadastradas."""
        found = []

        def scan(steps):
            for step in steps:
                for field in ("texto", "arquivo", "combinacao", "tecla",
                              "url", "selector", "script", "valor",
                              "valor_comparar", "valor_ref"):
                    for var in self._VAR_PATTERN.findall(step.get(field, "")):
                        if var not in found:
                            found.append(var)
                for sub_key in ("steps", "steps_sim", "steps_nao"):
                    scan(step.get(sub_key, []))

        scan(self._workflow.get("steps", []))

        existing_names = {v["name"] for v in self._var_entries}
        added = 0
        for var in found:
            if var not in existing_names:
                # Novas variaveis detectadas automaticamente assumem "Pergunta ao executar"
                # pois o usuario ainda nao definiu um valor fixo
                self._var_entries.append({"name": var, "label": "", "value": "", "perguntar": True, "permitir_vazio": False})
                existing_names.add(var)
                added += 1

        total_steps = len(self._workflow.get("steps", []))
        if added:
            self._refresh_var_list()
            self._tabs.set("  Variaveis  ")
            msg = f"✔  {added} variavel(is) nova(s) adicionada(s) a partir de {total_steps} step(s)."
            self._detect_feedback_label.configure(text=msg, text_color="#4CAF50")
        elif found:
            msg = f"Todas as {len(found)} variavel(is) encontradas ja estao cadastradas."
            self._detect_feedback_label.configure(text=msg, text_color="gray55")
        elif total_steps == 0:
            self._detect_feedback_label.configure(
                text="Nenhum step criado ainda. Adicione steps com {{VARIAVEL}} no texto.",
                text_color="gray55")
        else:
            self._detect_feedback_label.configure(
                text=f"Nenhuma {{{{VARIAVEL}}}} encontrada nos {total_steps} step(s). "
                     "Use {{NOME}} em steps de paste/type.",
                text_color="gray55")
        # Limpa o feedback apos 6 segundos
        self.after(6000, lambda: self._detect_feedback_label.configure(text=""))

    def _collect_var_data(self) -> tuple[dict, dict, dict, dict]:
        """Retorna (variaveis, variaveis_valores, variaveis_perguntar, variaveis_permitir_vazio)."""
        variaveis: dict = {}
        variaveis_valores: dict = {}
        variaveis_perguntar: dict = {}
        variaveis_permitir_vazio: dict = {}
        for v in self._var_entries:
            name = v["name"].strip()
            if not name:
                continue
            if v["label"].strip():
                variaveis[name] = v["label"]
            variaveis_valores[name] = v["value"]
            variaveis_perguntar[name] = bool(v.get("perguntar", False))
            variaveis_permitir_vazio[name] = bool(v.get("permitir_vazio", False))
        return variaveis, variaveis_valores, variaveis_perguntar, variaveis_permitir_vazio

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _refresh_steps(self):
        for w in self._steps_scroll.winfo_children():
            w.destroy()

        steps = self._workflow.get("steps", [])
        term = ""
        if hasattr(self, "_step_search_var"):
            term = self._step_search_var.get().strip().lower()

        for i, step in enumerate(steps):
            if term:
                label = _step_label(step).lower()
                nota = step.get("nota", "").lower()
                tipo = step.get("tipo", "").lower()
                if term not in label and term not in nota and term not in tipo:
                    continue
            self._build_step_row(i, step)

        # Mostra/oculta botoes de undo e paste
        if hasattr(self, "_undo_btn"):
            if self._deleted_step is not None:
                self._undo_btn.pack(side="right", padx=4)
            else:
                try:
                    self._undo_btn.pack_forget()
                except Exception:
                    pass
        if hasattr(self, "_paste_btn"):
            if self._copied_step is not None:
                self._paste_btn.pack(side="right", padx=4)
            else:
                try:
                    self._paste_btn.pack_forget()
                except Exception:
                    pass

    def _build_step_row(self, index: int, step: dict):
        ativo = step.get("ativo", True)
        tipo  = step.get("tipo", "")
        bg    = STEP_COLORS.get(tipo, "#1e1e2e")
        row   = ctk.CTkFrame(self._steps_scroll, fg_color=bg)
        row.pack(fill="x", pady=3, padx=4)
        row.grid_columnconfigure(2, weight=1)

        # Numero
        ctk.CTkLabel(row, text=f"{index + 1:>2}.", width=28,
                     font=ctk.CTkFont(family="Courier New"),
                     fg_color="transparent").grid(row=0, column=0, padx=(8, 2), pady=6)

        # Toggle ativo
        ativo_var = ctk.BooleanVar(value=ativo)
        def _toggle(i=index, var=ativo_var):
            self._workflow["steps"][i]["ativo"] = var.get()
            self._refresh_steps()
        ctk.CTkCheckBox(row, text="", variable=ativo_var, width=20, height=20,
                        command=_toggle).grid(row=0, column=1, padx=(2, 6), pady=6)

        # Descricao + nota
        label_color = "gray45" if not ativo else "gray90"
        label_frame = ctk.CTkFrame(row, fg_color="transparent")
        label_frame.grid(row=0, column=2, padx=4, pady=(6, 2), sticky="ew")
        ctk.CTkLabel(label_frame, text=_step_label(step), anchor="w",
                     font=ctk.CTkFont(family="Courier New", size=12),
                     text_color=label_color, fg_color="transparent").pack(fill="x")
        nota = step.get("nota", "").strip()
        if nota:
            ctk.CTkLabel(label_frame, text=nota, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color="gray55", fg_color="transparent").pack(fill="x")
        if step.get("retry", 0):
            ctk.CTkLabel(label_frame,
                         text=f"  retry={step['retry']}x  delay={step.get('retry_delay',1)}s",
                         anchor="w", font=ctk.CTkFont(size=10),
                         text_color="#e0a040", fg_color="transparent").pack(fill="x")

        # Botoes — tamanho compacto para nao transbordar em janelas estreitas
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.grid(row=0, column=3, padx=(2, 6), pady=4)

        H = 26  # altura uniforme
        ctk.CTkButton(btn_frame, text="▶", width=26, height=H,
                      fg_color="#1a5a1a", hover_color="#0a4a0a",
                      command=lambda i=index: self._run_from_step(i)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="↑", width=24, height=H,
                      command=lambda i=index: self._move_step(i, -1)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="↓", width=24, height=H,
                      command=lambda i=index: self._move_step(i, 1)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="Editar", width=52, height=H,
                      command=lambda i=index: self._edit_step(i)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="Dup", width=36, height=H,
                      fg_color="gray40", hover_color="gray30",
                      command=lambda i=index: self._dup_step(i)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="⎘", width=26, height=H,
                      fg_color="gray35", hover_color="gray25",
                      command=lambda i=index: self._copy_step(i)).pack(side="left", padx=1)
        ctk.CTkButton(btn_frame, text="✕", width=26, height=H,
                      fg_color="#8B1A1A", hover_color="#6B0000",
                      command=lambda i=index: self._remove_step(i)).pack(side="left", padx=1)

    # ------------------------------------------------------------------
    def _add_step(self):
        dlg = StepEditorDialog(self.winfo_toplevel())
        self.wait_window(dlg)
        if dlg.result:
            self._workflow.setdefault("steps", []).append(dlg.result)
            self._refresh_steps()

    def _edit_step(self, index: int):
        step = self._workflow["steps"][index]
        dlg = StepEditorDialog(self.winfo_toplevel(), step)
        self.wait_window(dlg)
        if dlg.result:
            self._workflow["steps"][index] = dlg.result
            self._refresh_steps()

    def _dup_step(self, index: int):
        import copy
        step = copy.deepcopy(self._workflow["steps"][index])
        self._workflow["steps"].insert(index + 1, step)
        self._refresh_steps()

    def _remove_step(self, index: int):
        import copy
        self._deleted_step = copy.deepcopy(self._workflow["steps"][index])
        self._deleted_step_idx = index
        self._workflow["steps"].pop(index)
        self._refresh_steps()

    def _move_step(self, index: int, direction: int):
        steps = self._workflow["steps"]
        new_index = index + direction
        if 0 <= new_index < len(steps):
            steps[index], steps[new_index] = steps[new_index], steps[index]
            self._refresh_steps()

    def _undo_delete(self):
        if self._deleted_step is not None:
            idx = min(self._deleted_step_idx, len(self._workflow.get("steps", [])))
            self._workflow.setdefault("steps", []).insert(idx, self._deleted_step)
            self._deleted_step = None
            self._deleted_step_idx = -1
            self._refresh_steps()

    def _copy_step(self, index: int):
        import copy
        self._copied_step = copy.deepcopy(self._workflow["steps"][index])
        self._refresh_steps()  # mostra o botao Colar

    def _paste_step(self):
        if self._copied_step is not None:
            import copy
            self._workflow.setdefault("steps", []).append(copy.deepcopy(self._copied_step))
            self._refresh_steps()

    def _run_from_step(self, index: int):
        """Pede ao app pai para executar o workflow a partir deste step."""
        # Captura os dados antes de salvar (save pode destruir este frame via on_save)
        wf = dict(self._workflow)
        wf["steps"] = list(wf.get("steps", []))[index:]
        callback = self._on_run_from
        self._save()
        if callback:
            callback(wf)

    # ------------------------------------------------------------------
    def _save(self):
        import datetime
        import shutil as _shutil

        self._workflow["name"] = self._name_entry.get().strip() or "Sem nome"
        self._workflow["hotkey"] = self._hotkey_entry.get().strip()
        reps = self._reps_entry.get().strip()
        self._workflow["repeticoes"] = max(1, int(reps)) if reps.isdigit() else 1
        delay_str = self._delay_entry.get().strip()
        try:
            self._workflow["delay_entre_repeticoes"] = max(0.0, float(delay_str))
        except ValueError:
            self._workflow["delay_entre_repeticoes"] = 0.0

        variaveis, variaveis_valores, variaveis_perguntar, variaveis_permitir_vazio = self._collect_var_data()
        self._workflow["variaveis"] = variaveis
        self._workflow["variaveis_valores"] = variaveis_valores
        self._workflow["variaveis_perguntar"] = variaveis_perguntar
        self._workflow["variaveis_permitir_vazio"] = variaveis_permitir_vazio

        WORKFLOWS_DIR.mkdir(exist_ok=True)
        out_path = WORKFLOWS_DIR / self._filename

        # Backup automatico (ultimos 5 por workflow)
        if out_path.exists():
            bkp_dir = WORKFLOWS_DIR / ".bkp"
            bkp_dir.mkdir(exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            _shutil.copy(out_path, bkp_dir / f"{out_path.stem}_{ts}.json")
            backups = sorted(bkp_dir.glob(f"{out_path.stem}_*.json"))
            for old in backups[:-5]:
                old.unlink(missing_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self._workflow, f, ensure_ascii=False, indent=2)

        self._original = json.loads(json.dumps(self._workflow))
        if self._on_save:
            self._on_save(self._workflow)

    def _back(self):
        current_name = self._name_entry.get().strip() or "Sem nome"
        current_hotkey = self._hotkey_entry.get().strip()
        changed = (
            current_name != self._original.get("name", "")
            or current_hotkey != self._original.get("hotkey", "")
            or json.dumps(self._workflow.get("steps", []), sort_keys=True)
            != json.dumps(self._original.get("steps", []), sort_keys=True)
        )
        if changed:
            dlg = ctk.CTkInputDialog(
                text="Ha alteracoes nao salvas. Digite 'SIM' para sair sem salvar:",
                title="Alteracoes nao salvas",
            )
            if dlg.get_input() != "SIM":
                return
        if self._on_back:
            self._on_back()

    def _validate_hotkey(self, event=None):
        import keyboard as _kb
        hk = self._hotkey_entry.get().strip()
        if not hk:
            self._hotkey_entry.configure(border_color=("gray65", "gray30"))
            return
        try:
            _kb.parse_hotkey(hk)
            self._hotkey_entry.configure(border_color="#2fa827")
        except Exception:
            self._hotkey_entry.configure(border_color="#e05a5a")

    def _on_destroy(self, event):
        if str(event.widget) == str(self):
            try:
                self.winfo_toplevel().unbind("<Control-s>", self._ctrl_s_id)
            except Exception:
                pass


# ---------------------------------------------------------------------------
class VarEditorDialog(ctk.CTkToplevel):
    """
    Dialog modal para criar ou editar uma variavel.
    Recebe var_data = {"name": str, "label": str, "value": str}.
    Expoe self.result com o mesmo formato apos OK, ou None se cancelado.
    """

    def __init__(self, parent, var_data: dict | None = None):
        super().__init__(parent)
        self.title("Variavel")
        self.geometry("480x400")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        self.result: dict | None = None
        self._data = var_data or {"name": "", "label": "", "value": "", "perguntar": False, "permitir_vazio": False}
        self._build_ui()

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=0, column=0, padx=28, pady=(20, 8), sticky="nsew")
        form.grid_columnconfigure(1, weight=1)

        lbl_w = 90  # largura dos rotulos

        # ---- Nome ----
        ctk.CTkLabel(form, text="Nome:", width=lbl_w, anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 12))

        name_frame = ctk.CTkFrame(form, fg_color="transparent")
        name_frame.grid(row=0, column=1, sticky="ew", pady=(0, 12))
        name_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(name_frame, text="{{",
                     font=ctk.CTkFont(family="Courier New"),
                     text_color="gray50", width=20).grid(row=0, column=0)
        self._name_entry = ctk.CTkEntry(
            name_frame,
            placeholder_text="nome_var",
            font=ctk.CTkFont(family="Courier New", size=13))
        self._name_entry.insert(0, self._data.get("name", ""))
        self._name_entry.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkLabel(name_frame, text="}}",
                     font=ctk.CTkFont(family="Courier New"),
                     text_color="gray50", width=20).grid(row=0, column=2)

        # ---- Descricao ----
        ctk.CTkLabel(form, text="Descricao:", width=lbl_w, anchor="w").grid(
            row=1, column=0, sticky="w", pady=(0, 12))
        self._label_entry = ctk.CTkEntry(form, placeholder_text="Descricao opcional")
        if label_val := self._data.get("label", ""):
            self._label_entry.insert(0, label_val)
        self._label_entry.grid(row=1, column=1, sticky="ew", pady=(0, 12))

        # ---- Valor ----
        ctk.CTkLabel(form, text="Valor:", width=lbl_w, anchor="w").grid(
            row=2, column=0, sticky="w", pady=(0, 12))
        self._value_entry = ctk.CTkEntry(form, placeholder_text="Valor usado na execucao")
        if value_val := self._data.get("value", ""):
            self._value_entry.insert(0, value_val)
        self._value_entry.grid(row=2, column=1, sticky="ew", pady=(0, 12))

        # ---- Perguntar ao executar ----
        ctk.CTkFrame(form, height=1, fg_color="gray25").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._perguntar_var = ctk.BooleanVar(value=bool(self._data.get("perguntar", False)))
        self._permitir_vazio_var = ctk.BooleanVar(value=bool(self._data.get("permitir_vazio", False)))

        # ---- Perguntar ao executar ----
        perg_frame = ctk.CTkFrame(form, fg_color="transparent")
        perg_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ctk.CTkCheckBox(perg_frame, text="Perguntar ao executar",
                        variable=self._perguntar_var,
                        font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(perg_frame,
                     text="  — abre popup para editar antes de cada execucao",
                     text_color="gray55", font=ctk.CTkFont(size=11)).pack(side="left")

        # ---- Permitir em branco ----
        vazio_frame = ctk.CTkFrame(form, fg_color="transparent")
        vazio_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ctk.CTkCheckBox(vazio_frame, text="Permitir em branco",
                        variable=self._permitir_vazio_var,
                        font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(vazio_frame,
                     text="  — {{VAR}} substituido por texto vazio sem aviso",
                     text_color="gray55", font=ctk.CTkFont(size=11)).pack(side="left")

        # Dica contextual dinamica
        self._perg_hint = ctk.CTkLabel(
            form, text="",
            text_color="gray55", font=ctk.CTkFont(size=11), anchor="w", wraplength=400)
        self._perg_hint.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self._perguntar_var.trace_add("write", self._update_perg_hint)
        self._permitir_vazio_var.trace_add("write", self._update_perg_hint)
        self._update_perg_hint()

        # ---- Botoes ----
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=1, column=0, padx=28, pady=(0, 20), sticky="ew")
        ctk.CTkButton(btn_bar, text="Cancelar", width=100,
                      fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_bar, text="OK", width=100,
                      command=self._on_ok).pack(side="right")

        # Enter confirma, Esc cancela
        self.bind("<Return>", lambda _: self._on_ok())
        self.bind("<Escape>", lambda _: self.destroy())
        self._name_entry.focus_set()

    def _update_perg_hint(self, *_):
        perg  = self._perguntar_var.get()
        vazio = self._permitir_vazio_var.get()
        if perg and vazio:
            txt   = "Popup abre antes de executar, mas voce pode deixar em branco — {{VAR}} sera substituido por texto vazio."
            color = "#e0a040"
        elif perg:
            txt   = "Popup abre antes de executar. O valor precisa ser preenchido."
            color = "#e0a040"
        elif vazio:
            txt   = "Sem popup. Se o valor estiver em branco, {{VAR}} sera substituido por texto vazio automaticamente."
            color = "#4a9adf"
        else:
            txt   = "Sem popup. O valor salvo acima sera usado. Se estiver em branco, o popup sera exibido para preencher."
            color = "gray55"
        self._perg_hint.configure(text=txt, text_color=color)

    def _on_ok(self):
        name = self._name_entry.get().strip()
        if not name:
            self._name_entry.configure(border_color="red")
            return
        self.result = {
            "name":          name,
            "label":         self._label_entry.get().strip(),
            "value":         self._value_entry.get(),
            "perguntar":     self._perguntar_var.get(),
            "permitir_vazio": self._permitir_vazio_var.get(),
        }
        self.destroy()
