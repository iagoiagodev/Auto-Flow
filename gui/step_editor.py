"""
step_editor.py — Modal de configuracao de um step.
Campos dinamicos conforme o tipo selecionado.
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
import threading
import pyautogui

STEP_TYPES = [
    "click", "paste", "type", "press", "hotkey",
    "scroll", "wait_image", "click_image", "move_to_image", "click_text",
    "wait_text", "run_workflow", "get_clipboard",
    "sleep", "screenshot", "loop", "if_image",
    "loop_lista", "if_var",
    "browser_open", "browser_close", "browser_navigate",
    "browser_click", "browser_fill", "browser_wait",
    "browser_select", "browser_get_text", "browser_run_js", "browser_screenshot",
    "browser_get_url",
]


class StepEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, step: dict = None):
        super().__init__(parent)
        self.title("Editar Step")
        self.geometry("560x580")
        self.minsize(480, 400)
        self.resizable(True, True)
        self.grab_set()
        self.lift()

        self.result: dict | None = None
        self._step = step or {}
        self._loop_steps: list = list(self._step.get("steps", []))
        self._if_steps_sim: list = list(self._step.get("steps_sim", []))
        self._if_steps_nao: list = list(self._step.get("steps_nao", []))
        self._ll_steps: list = list(self._step.get("steps", []))
        self._ifv_steps_sim: list = list(self._step.get("steps_sim", []))
        self._ifv_steps_nao: list = list(self._step.get("steps_nao", []))

        self._build_ui()
        self._load_step(self._step)

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        tipo_frame = ctk.CTkFrame(self, fg_color="transparent")
        tipo_frame.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        ctk.CTkLabel(tipo_frame, text="Tipo:", width=100, anchor="w").pack(side="left")
        self._tipo_var = ctk.StringVar(value=STEP_TYPES[0])
        self._tipo_menu = ctk.CTkOptionMenu(
            tipo_frame, variable=self._tipo_var,
            values=STEP_TYPES, command=self._on_type_change
        )
        self._tipo_menu.pack(side="left", fill="x", expand=True)

        # Scrollable container so fields never get clipped regardless of step type
        self._fields_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="")
        self._fields_scroll.grid(row=1, column=0, padx=20, pady=4, sticky="nsew")
        self._fields_scroll.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        # _fields_frame is a plain CTkFrame inside the scroll so that
        # _clear_fields() / winfo_children() continue to work correctly.
        self._fields_frame = ctk.CTkFrame(self._fields_scroll, fg_color="transparent")
        self._fields_frame.pack(fill="x", expand=True)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=(8, 20), sticky="ew")
        ctk.CTkButton(btn_frame, text="Cancelar", width=100,
                      fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_frame, text="OK", width=100,
                      command=self._on_ok).pack(side="right")
        ctk.CTkButton(btn_frame, text="Testar", width=90,
                      fg_color="#1a5a7a", hover_color="#124a6a",
                      command=self._test_step).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------------
    def _clear_fields(self):
        for w in self._fields_frame.winfo_children():
            w.destroy()

    def _row(self, label: str, widget_factory):
        frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        frame.pack(fill="x", pady=3)
        ctk.CTkLabel(frame, text=label, width=110, anchor="w").pack(side="left")
        w = widget_factory(frame)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _entry(self, parent, default=""):
        e = ctk.CTkEntry(parent)
        if str(default) != "":
            e.insert(0, str(default))
        return e

    def _add_nota_field(self, default: str = ""):
        ctk.CTkFrame(self._fields_frame, height=1, fg_color="gray30").pack(fill="x", pady=(10, 4))
        self._nota_entry = self._row("Nota:", lambda p: self._entry(p, default))

    # ------------------------------------------------------------------
    def _on_type_change(self, tipo: str):
        # Preserva nota digitada antes de reconstruir
        saved_nota = ""
        if hasattr(self, "_nota_entry"):
            saved_nota = self._nota_entry.get().strip()
        self._build_fields(tipo, saved_nota=saved_nota)

    def _build_fields(self, tipo: str, saved_nota: str = ""):
        self._clear_fields()
        nota_default = saved_nota or self._step.get("nota", "")

        if tipo == "click":
            self._x_entry = self._row("X:", lambda p: self._entry(p, self._step.get("x", 0)))
            self._y_entry = self._row("Y:", lambda p: self._entry(p, self._step.get("y", 0)))
            self._click_type_var = ctk.StringVar(value=self._step.get("clique", "simples"))
            click_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            click_row.pack(fill="x", pady=3)
            ctk.CTkLabel(click_row, text="Tipo:", width=110, anchor="w").pack(side="left")
            ctk.CTkOptionMenu(click_row, variable=self._click_type_var,
                              values=["simples", "duplo", "direito"]).pack(side="left")
            ctk.CTkButton(self._fields_frame, text="Capturar ao vivo",
                          command=self._capture_live).pack(pady=(8, 0))

        elif tipo == "paste":
            ctk.CTkLabel(self._fields_frame,
                         text="Texto:  (use {{NOME}} para variaveis dinamicas)",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._texto_box = ctk.CTkTextbox(self._fields_frame, height=120)
            self._texto_box.pack(fill="both", expand=True, pady=(4, 0))
            self._texto_box.insert("1.0", self._step.get("texto", ""))

        elif tipo == "type":
            ctk.CTkLabel(self._fields_frame,
                         text="Texto:  (digita char a char — suporta campos que bloqueiam paste)",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._type_box = ctk.CTkTextbox(self._fields_frame, height=100)
            self._type_box.pack(fill="both", expand=True, pady=(4, 0))
            self._type_box.insert("1.0", self._step.get("texto", ""))
            self._type_interval = self._row("Intervalo (s):",
                                            lambda p: self._entry(p, self._step.get("intervalo", 0.08)))

        elif tipo == "press":
            self._tecla_entry = self._row("Tecla:",
                                          lambda p: self._entry(p, self._step.get("tecla", "enter")))

        elif tipo == "hotkey":
            self._combo_entry = self._row("Combinacao:",
                                          lambda p: self._entry(p, self._step.get("combinacao", "ctrl+c")))

        elif tipo == "scroll":
            ctk.CTkLabel(self._fields_frame,
                         text="Quantidade: positivo = cima, negativo = baixo",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._scroll_qty = self._row("Quantidade:",
                                         lambda p: self._entry(p, self._step.get("quantidade", 3)))
            self._scroll_x = self._row("X (opcional):",
                                       lambda p: self._entry(p, self._step.get("x", "")))
            self._scroll_y = self._row("Y (opcional):",
                                       lambda p: self._entry(p, self._step.get("y", "")))

        elif tipo == "wait_image":
            tpl_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            tpl_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(tpl_frame, text="Template:", width=110, anchor="w").pack(side="left")
            self._tpl_entry = ctk.CTkEntry(tpl_frame)
            self._tpl_entry.insert(0, self._step.get("template", ""))
            self._tpl_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkButton(tpl_frame, text="...", width=32,
                          command=self._pick_template).pack(side="left")

            self._conf_var = tk.DoubleVar(value=self._step.get("confidence", 0.8))
            conf_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            conf_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(conf_frame, text="Confidence:", width=110, anchor="w").pack(side="left")
            self._conf_label = ctk.CTkLabel(conf_frame, text=f"{self._conf_var.get():.2f}", width=40)
            slider = ctk.CTkSlider(conf_frame, from_=0.5, to=1.0, variable=self._conf_var,
                                   command=lambda v: self._conf_label.configure(text=f"{float(v):.2f}"))
            slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._conf_label.pack(side="left")

            self._timeout_entry = self._row("Timeout (s):",
                                            lambda p: self._entry(p, self._step.get("timeout", 30)))

            ao_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            ao_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(ao_frame, text="Ao falhar:", width=110, anchor="w").pack(side="left")
            self._ao_falhar_var = ctk.StringVar(value=self._step.get("ao_falhar", "erro"))
            ctk.CTkOptionMenu(ao_frame, variable=self._ao_falhar_var,
                              values=["erro", "continuar"]).pack(side="left")

        elif tipo in ("click_image", "move_to_image"):
            ctk.CTkLabel(self._fields_frame,
                         text="Captura um PNG da imagem que quer clicar/mover e salva em assets/templates/",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11), wraplength=420).pack(fill="x", pady=(0, 4))
            tpl_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            tpl_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(tpl_frame, text="Template PNG:", width=110, anchor="w").pack(side="left")
            self._tpl_entry = ctk.CTkEntry(tpl_frame)
            self._tpl_entry.insert(0, self._step.get("template", ""))
            self._tpl_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkButton(tpl_frame, text="...", width=32,
                          command=self._pick_template).pack(side="left")

            self._conf_var = tk.DoubleVar(value=self._step.get("confidence", 0.8))
            conf_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            conf_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(conf_frame, text="Confidence:", width=110, anchor="w").pack(side="left")
            self._conf_label = ctk.CTkLabel(conf_frame, text=f"{self._conf_var.get():.2f}", width=40)
            slider = ctk.CTkSlider(conf_frame, from_=0.5, to=1.0, variable=self._conf_var,
                                   command=lambda v: self._conf_label.configure(text=f"{float(v):.2f}"))
            slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._conf_label.pack(side="left")

            self._timeout_entry = self._row("Timeout (s):",
                                            lambda p: self._entry(p, self._step.get("timeout", 30)))
            self._offset_x = self._row("Offset X:",
                                       lambda p: self._entry(p, self._step.get("offset_x", 0)))
            self._offset_y = self._row("Offset Y:",
                                       lambda p: self._entry(p, self._step.get("offset_y", 0)))

            if tipo == "click_image":
                clique_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
                clique_frame.pack(fill="x", pady=3)
                ctk.CTkLabel(clique_frame, text="Tipo clique:", width=110, anchor="w").pack(side="left")
                self._click_type_var = ctk.StringVar(value=self._step.get("clique", "simples"))
                ctk.CTkOptionMenu(clique_frame, variable=self._click_type_var,
                                  values=["simples", "duplo", "direito"]).pack(side="left")
            else:
                self._duracao_entry = self._row("Duracao mov. (s):",
                                                lambda p: self._entry(p, self._step.get("duracao", 0.3)))

            ao_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            ao_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(ao_frame, text="Ao falhar:", width=110, anchor="w").pack(side="left")
            self._ao_falhar_var = ctk.StringVar(value=self._step.get("ao_falhar", "erro"))
            ctk.CTkOptionMenu(ao_frame, variable=self._ao_falhar_var,
                              values=["erro", "continuar"]).pack(side="left")

        elif tipo == "click_text":
            ctk.CTkLabel(self._fields_frame,
                         text="Requer Tesseract OCR instalado no computador.",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(0, 4))
            self._ct_texto = self._row("Texto a achar:", lambda p: self._entry(p, self._step.get("texto", "")))
            self._timeout_entry = self._row("Timeout (s):",
                                            lambda p: self._entry(p, self._step.get("timeout", 30)))
            self._offset_x = self._row("Offset X:",
                                       lambda p: self._entry(p, self._step.get("offset_x", 0)))
            self._offset_y = self._row("Offset Y:",
                                       lambda p: self._entry(p, self._step.get("offset_y", 0)))

            clique_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            clique_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(clique_frame, text="Tipo clique:", width=110, anchor="w").pack(side="left")
            self._click_type_var = ctk.StringVar(value=self._step.get("clique", "simples"))
            ctk.CTkOptionMenu(clique_frame, variable=self._click_type_var,
                              values=["simples", "duplo", "direito"]).pack(side="left")

            ao_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            ao_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(ao_frame, text="Ao falhar:", width=110, anchor="w").pack(side="left")
            self._ao_falhar_var = ctk.StringVar(value=self._step.get("ao_falhar", "erro"))
            ctk.CTkOptionMenu(ao_frame, variable=self._ao_falhar_var,
                              values=["erro", "continuar"]).pack(side="left")

        elif tipo == "wait_text":
            ctk.CTkLabel(self._fields_frame,
                         text="Aguarda o texto aparecer na tela (OCR). Requer Tesseract.",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11), wraplength=420).pack(fill="x", pady=(0, 4))
            self._ct_texto = self._row("Texto a aguardar:", lambda p: self._entry(p, self._step.get("texto", "")))
            self._timeout_entry = self._row("Timeout (s):", lambda p: self._entry(p, self._step.get("timeout", 30)))
            ao_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            ao_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(ao_frame, text="Ao falhar:", width=110, anchor="w").pack(side="left")
            self._ao_falhar_var = ctk.StringVar(value=self._step.get("ao_falhar", "erro"))
            ctk.CTkOptionMenu(ao_frame, variable=self._ao_falhar_var,
                              values=["erro", "continuar"]).pack(side="left")

        elif tipo == "run_workflow":
            ctk.CTkLabel(self._fields_frame,
                         text="Executa outro workflow inline (herda as variaveis atuais).",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11), wraplength=420).pack(fill="x", pady=(0, 4))
            self._rw_entry = self._row("Workflow (.json):", lambda p: self._entry(p, self._step.get("workflow", "")))
            ctk.CTkLabel(self._fields_frame,
                         text="  Ex: meu_workflow.json ou meu_workflow (sem extensao)",
                         text_color="gray55", font=ctk.CTkFont(size=10)).pack(fill="x")

        elif tipo == "get_clipboard":
            ctk.CTkLabel(self._fields_frame,
                         text="Captura o conteudo atual do clipboard em uma variavel.",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11), wraplength=420).pack(fill="x", pady=(0, 4))
            self._gc_var = self._row("Variavel:", lambda p: self._entry(p, self._step.get("variavel", "")))
            ctk.CTkLabel(self._fields_frame,
                         text="  Ex: RESULTADO (use {{RESULTADO}} nos steps seguintes)",
                         text_color="gray55", font=ctk.CTkFont(size=10)).pack(fill="x")

        elif tipo == "sleep":
            self._sleep_entry = self._row("Segundos:",
                                          lambda p: self._entry(p, self._step.get("segundos", 1.0)))

        elif tipo == "screenshot":
            self._shot_entry = self._row("Arquivo:",
                                         lambda p: self._entry(p, self._step.get("arquivo", "screenshot.png")))

        elif tipo == "loop":
            self._loop_reps = self._row("Repeticoes:",
                                        lambda p: self._entry(p, self._step.get("repeticoes", 1)))
            n = len(self._loop_steps)
            self._loop_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar sub-steps ({n})",
                command=self._edit_loop_steps,
            )
            self._loop_btn.pack(pady=12)
            ctk.CTkLabel(self._fields_frame,
                         text="Sub-steps sao executados N vezes em sequencia.",
                         text_color="gray60", font=ctk.CTkFont(size=11)).pack()

        elif tipo == "if_image":
            tpl_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            tpl_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(tpl_frame, text="Template:", width=110, anchor="w").pack(side="left")
            self._if_tpl_entry = ctk.CTkEntry(tpl_frame)
            self._if_tpl_entry.insert(0, self._step.get("template", ""))
            self._if_tpl_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctk.CTkButton(tpl_frame, text="...", width=32,
                          command=self._pick_template_if).pack(side="left")

            self._if_conf_var = tk.DoubleVar(value=self._step.get("confidence", 0.8))
            conf_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            conf_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(conf_frame, text="Confidence:", width=110, anchor="w").pack(side="left")
            self._if_conf_label = ctk.CTkLabel(conf_frame, text=f"{self._if_conf_var.get():.2f}", width=40)
            slider = ctk.CTkSlider(conf_frame, from_=0.5, to=1.0, variable=self._if_conf_var,
                                   command=lambda v: self._if_conf_label.configure(text=f"{float(v):.2f}"))
            slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._if_conf_label.pack(side="left")

            self._if_timeout_entry = self._row("Timeout (s):",
                                               lambda p: self._entry(p, self._step.get("timeout", 5)))

            n_sim = len(self._if_steps_sim)
            n_nao = len(self._if_steps_nao)
            self._if_sim_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar steps SE ENCONTRADO ({n_sim})",
                fg_color="#1a5a1a", hover_color="#124a12",
                command=self._edit_if_sim_steps,
            )
            self._if_sim_btn.pack(pady=(8, 2), fill="x")
            self._if_nao_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar steps SE NAO ENCONTRADO ({n_nao})",
                fg_color="#5a1a1a", hover_color="#4a1212",
                command=self._edit_if_nao_steps,
            )
            self._if_nao_btn.pack(pady=(2, 4), fill="x")
            ctk.CTkLabel(self._fields_frame,
                         text="Aguarda ate N segundos pela imagem, executa o ramo correspondente.",
                         text_color="gray60", font=ctk.CTkFont(size=11), wraplength=380).pack()

        elif tipo == "loop_lista":
            ctk.CTkLabel(self._fields_frame,
                         text="Variavel substituida em cada iteracao (sem {{ }})",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._ll_var_entry = self._row("Variavel:",
                                           lambda p: self._entry(p, self._step.get("variavel", "")))
            ctk.CTkLabel(self._fields_frame,
                         text="Lista de itens (um por linha):",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(6, 2))
            self._ll_lista_box = ctk.CTkTextbox(self._fields_frame, height=90)
            self._ll_lista_box.pack(fill="x")
            self._ll_lista_box.insert("1.0", "\n".join(self._step.get("lista", [])))

            n = len(self._ll_steps)
            self._ll_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar sub-steps ({n})",
                command=self._edit_ll_steps,
            )
            self._ll_btn.pack(pady=(8, 2), fill="x")
            ctk.CTkLabel(self._fields_frame,
                         text="{{VARIAVEL}} nos sub-steps sera substituida por cada item da lista.",
                         text_color="gray60", font=ctk.CTkFont(size=11), wraplength=380).pack()

        elif tipo == "if_var":
            ctk.CTkLabel(self._fields_frame,
                         text="Use {{NOME}} para referenciar o valor de uma variavel",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._ifv_comparar = self._row("Valor atual:",
                                           lambda p: self._entry(p, self._step.get("valor_comparar", "")))

            op_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            op_frame.pack(fill="x", pady=3)
            ctk.CTkLabel(op_frame, text="Operador:", width=110, anchor="w").pack(side="left")
            self._ifv_op_var = ctk.StringVar(value=self._step.get("operador", "igual"))
            ctk.CTkOptionMenu(op_frame, variable=self._ifv_op_var,
                              values=["igual", "diferente", "contem",
                                      "comeca_com", "termina_com"]).pack(side="left")

            self._ifv_ref = self._row("Comparar com:",
                                      lambda p: self._entry(p, self._step.get("valor_ref", "")))

            n_sim = len(self._ifv_steps_sim)
            n_nao = len(self._ifv_steps_nao)
            self._ifv_sim_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar steps SE VERDADEIRO ({n_sim})",
                fg_color="#1a5a1a", hover_color="#124a12",
                command=self._edit_ifv_sim_steps,
            )
            self._ifv_sim_btn.pack(pady=(8, 2), fill="x")
            self._ifv_nao_btn = ctk.CTkButton(
                self._fields_frame,
                text=f"Editar steps SE FALSO ({n_nao})",
                fg_color="#5a1a1a", hover_color="#4a1212",
                command=self._edit_ifv_nao_steps,
            )
            self._ifv_nao_btn.pack(pady=(2, 4), fill="x")
            ctk.CTkLabel(self._fields_frame,
                         text="Exemplo: Valor atual = {{STATUS}}, comparar com = Aprovado",
                         text_color="gray60", font=ctk.CTkFont(size=11), wraplength=380).pack()

        # ------------------------------------------------------------------
        # Browser steps
        # ------------------------------------------------------------------

        elif tipo == "browser_open":
            browser_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            browser_row.pack(fill="x", pady=3)
            ctk.CTkLabel(browser_row, text="Browser:", width=110, anchor="w").pack(side="left")
            self._browser_var = ctk.StringVar(value=self._step.get("browser", "chrome"))
            ctk.CTkOptionMenu(browser_row, variable=self._browser_var,
                              values=["chrome", "edge", "firefox"]).pack(side="left")

            self._browser_url = self._row("URL:", lambda p: self._entry(p, self._step.get("url", "")))

            headless_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            headless_row.pack(fill="x", pady=3)
            ctk.CTkLabel(headless_row, text="Headless:", width=110, anchor="w").pack(side="left")
            self._headless_var = ctk.BooleanVar(value=bool(self._step.get("headless", False)))
            ctk.CTkCheckBox(headless_row, text="Sem janela (background)",
                            variable=self._headless_var).pack(side="left")

        elif tipo == "browser_close":
            ctk.CTkLabel(self._fields_frame,
                         text="Fecha o browser aberto pelo step 'browser_open'.",
                         text_color="gray60", font=ctk.CTkFont(size=11)).pack(fill="x", pady=8)

        elif tipo == "browser_navigate":
            self._browser_url = self._row("URL:", lambda p: self._entry(p, self._step.get("url", "")))

        elif tipo == "browser_click":
            self._sel_entry, self._por_var = self._selector_row(
                self._step.get("selector", ""), self._step.get("por", "css"))
            self._br_timeout = self._row("Timeout (s):",
                                         lambda p: self._entry(p, self._step.get("timeout", 10)))

        elif tipo == "browser_fill":
            self._sel_entry, self._por_var = self._selector_row(
                self._step.get("selector", ""), self._step.get("por", "css"))
            ctk.CTkLabel(self._fields_frame,
                         text="Texto:  (suporta {{VAR}})",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(4, 0))
            self._fill_texto = ctk.CTkEntry(self._fields_frame)
            self._fill_texto.insert(0, self._step.get("texto", ""))
            self._fill_texto.pack(fill="x", pady=(2, 4))

            limpar_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            limpar_row.pack(fill="x", pady=3)
            ctk.CTkLabel(limpar_row, text="Limpar antes:", width=110, anchor="w").pack(side="left")
            self._limpar_var = ctk.BooleanVar(value=bool(self._step.get("limpar", True)))
            ctk.CTkCheckBox(limpar_row, text="", variable=self._limpar_var).pack(side="left")

            self._br_timeout = self._row("Timeout (s):",
                                         lambda p: self._entry(p, self._step.get("timeout", 10)))

        elif tipo == "browser_wait":
            self._sel_entry, self._por_var = self._selector_row(
                self._step.get("selector", ""), self._step.get("por", "css"))
            cond_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            cond_row.pack(fill="x", pady=3)
            ctk.CTkLabel(cond_row, text="Condicao:", width=110, anchor="w").pack(side="left")
            self._cond_var = ctk.StringVar(value=self._step.get("condicao", "presente"))
            ctk.CTkOptionMenu(cond_row, variable=self._cond_var,
                              values=["presente", "visivel", "clicavel"]).pack(side="left")
            self._br_timeout = self._row("Timeout (s):",
                                         lambda p: self._entry(p, self._step.get("timeout", 10)))

        elif tipo == "browser_select":
            self._sel_entry, self._por_var = self._selector_row(
                self._step.get("selector", ""), self._step.get("por", "css"))
            self._select_valor = self._row("Valor:",
                                           lambda p: self._entry(p, self._step.get("valor", "")))
            self._br_timeout = self._row("Timeout (s):",
                                         lambda p: self._entry(p, self._step.get("timeout", 10)))

        elif tipo == "browser_get_text":
            self._sel_entry, self._por_var = self._selector_row(
                self._step.get("selector", ""), self._step.get("por", "css"))
            ctk.CTkLabel(self._fields_frame,
                         text="Nome da variavel (sem {{ }}) para guardar o texto capturado:",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x", pady=(4, 0))
            self._variavel_entry = self._row("Variavel:",
                                             lambda p: self._entry(p, self._step.get("variavel", "")))
            self._br_timeout = self._row("Timeout (s):",
                                         lambda p: self._entry(p, self._step.get("timeout", 10)))

        elif tipo == "browser_run_js":
            ctk.CTkLabel(self._fields_frame,
                         text="Script JavaScript executado na pagina:",
                         anchor="w", text_color="gray70",
                         font=ctk.CTkFont(size=11)).pack(fill="x")
            self._js_box = ctk.CTkTextbox(self._fields_frame, height=140,
                                          font=ctk.CTkFont(family="Courier New", size=11))
            self._js_box.pack(fill="both", expand=True, pady=(4, 0))
            self._js_box.insert("1.0", self._step.get("script", ""))

        elif tipo == "browser_screenshot":
            self._br_shot_entry = self._row(
                "Arquivo:",
                lambda p: self._entry(p, self._step.get("arquivo", "browser_screenshot.png")))

        elif tipo == "browser_get_url":
            ctk.CTkLabel(self._fields_frame,
                         text="Salva a URL atual do browser em uma variavel.",
                         anchor="w", text_color="gray60",
                         font=ctk.CTkFont(size=11), wraplength=420).pack(fill="x", pady=(0, 4))
            self._bgu_var = self._row("Variavel:", lambda p: self._entry(p, self._step.get("variavel", "")))

        # Retry (universal para todos os steps)
        retry_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        retry_frame.pack(fill="x", pady=(8, 0))
        sep = ctk.CTkFrame(retry_frame, height=1, fg_color="gray25")
        sep.pack(fill="x", pady=(0, 6))
        retry_row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        retry_row.pack(fill="x", pady=2)
        ctk.CTkLabel(retry_row, text="Retry:", width=110, anchor="w").pack(side="left")
        self._retry_entry = ctk.CTkEntry(retry_row, width=50)
        self._retry_entry.insert(0, str(self._step.get("retry", 0)))
        self._retry_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(retry_row, text="tentativas  Delay (s):", anchor="w").pack(side="left")
        self._retry_delay = ctk.CTkEntry(retry_row, width=50)
        self._retry_delay.insert(0, str(self._step.get("retry_delay", 1.0)))
        self._retry_delay.pack(side="left", padx=(4, 0))
        ctk.CTkLabel(self._fields_frame,
                     text="  0 = sem retry. Util para steps que falham por timing.",
                     text_color="gray50", font=ctk.CTkFont(size=10)).pack(fill="x")

        self._add_nota_field(nota_default)

    def _pick_template_if(self):
        path = filedialog.askopenfilename(
            title="Selecionar template",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")]
        )
        if path:
            from pathlib import Path
            self._if_tpl_entry.delete(0, "end")
            self._if_tpl_entry.insert(0, Path(path).name)

    def _edit_if_sim_steps(self):
        dlg = LoopStepsDialog(self, list(self._if_steps_sim))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._if_steps_sim = dlg.result
            self._if_sim_btn.configure(text=f"Editar steps SE ENCONTRADO ({len(self._if_steps_sim)})")

    def _edit_if_nao_steps(self):
        dlg = LoopStepsDialog(self, list(self._if_steps_nao))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._if_steps_nao = dlg.result
            self._if_nao_btn.configure(text=f"Editar steps SE NAO ENCONTRADO ({len(self._if_steps_nao)})")

    def _edit_ll_steps(self):
        dlg = LoopStepsDialog(self, list(self._ll_steps))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._ll_steps = dlg.result
            self._ll_btn.configure(text=f"Editar sub-steps ({len(self._ll_steps)})")

    def _edit_ifv_sim_steps(self):
        dlg = LoopStepsDialog(self, list(self._ifv_steps_sim))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._ifv_steps_sim = dlg.result
            self._ifv_sim_btn.configure(text=f"Editar steps SE VERDADEIRO ({len(self._ifv_steps_sim)})")

    def _edit_ifv_nao_steps(self):
        dlg = LoopStepsDialog(self, list(self._ifv_steps_nao))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._ifv_steps_nao = dlg.result
            self._ifv_nao_btn.configure(text=f"Editar steps SE FALSO ({len(self._ifv_steps_nao)})")

    # ------------------------------------------------------------------
    def _edit_loop_steps(self):
        dlg = LoopStepsDialog(self, list(self._loop_steps))
        self.wait_window(dlg)
        if dlg.result is not None:
            self._loop_steps = dlg.result
            self._loop_btn.configure(text=f"Editar sub-steps ({len(self._loop_steps)})")

    # ------------------------------------------------------------------
    def _load_step(self, step: dict):
        tipo = step.get("tipo", STEP_TYPES[0])
        if tipo in STEP_TYPES:
            self._tipo_var.set(tipo)
        self._build_fields(self._tipo_var.get())

    # ------------------------------------------------------------------
    def _pick_template(self):
        path = filedialog.askopenfilename(
            title="Selecionar template",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")]
        )
        if path:
            from pathlib import Path
            self._tpl_entry.delete(0, "end")
            self._tpl_entry.insert(0, Path(path).name)

    # ------------------------------------------------------------------
    def _capture_live(self):
        root = self.master
        self.withdraw()
        root.iconify()

        def _wait_click():
            import mouse
            mouse.read_event(filter_type="down")
            x, y = pyautogui.position()
            root.after(0, lambda: self._fill_coords(x, y, root))

        try:
            import mouse
            threading.Thread(target=_wait_click, daemon=True).start()
        except ImportError:
            self._poll_capture(root)

    def _poll_capture(self, root):
        import keyboard

        captured = {"x": None, "y": None}
        _hk_ref = [None]

        def _on_hotkey():
            x, y = pyautogui.position()
            captured["x"] = x
            captured["y"] = y
            try:
                keyboard.remove_hotkey(_hk_ref[0])
            except Exception:
                pass
            root.after(0, lambda: self._fill_coords(captured["x"], captured["y"], root))

        _hk_ref[0] = keyboard.add_hotkey("ctrl+shift+c", _on_hotkey)

        tip = tk.Toplevel()
        tip.title("")
        tip.attributes("-topmost", True)
        tip.geometry("320x60+50+50")
        tip.overrideredirect(True)
        tk.Label(tip, text="Posicione o mouse e pressione Ctrl+Shift+C",
                 font=("Segoe UI", 11), bg="#1a1a2e", fg="white",
                 padx=16, pady=16).pack(fill="both")
        tip.after(15000, tip.destroy)

    def _fill_coords(self, x, y, root):
        root.deiconify()
        self.deiconify()
        self.lift()
        if hasattr(self, "_x_entry"):
            self._x_entry.delete(0, "end")
            self._x_entry.insert(0, str(x))
        if hasattr(self, "_y_entry"):
            self._y_entry.delete(0, "end")
            self._y_entry.insert(0, str(y))

    # ------------------------------------------------------------------
    def _selector_row(self, default_selector: str = "", default_por: str = "css"):
        """Linha Selector + botao Capturar + linha Por. Retorna (sel_entry, por_var)."""
        sel_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        sel_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(sel_frame, text="Selector:", width=110, anchor="w").pack(side="left")
        sel_entry = ctk.CTkEntry(sel_frame)
        sel_entry.insert(0, default_selector)
        sel_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(sel_frame, text="Capturar", width=78,
                      command=self._capture_browser_element).pack(side="left")

        por_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        por_frame.pack(fill="x", pady=3)
        ctk.CTkLabel(por_frame, text="Por:", width=110, anchor="w").pack(side="left")
        por_var = ctk.StringVar(value=default_por)
        ctk.CTkOptionMenu(por_frame, variable=por_var,
                          values=["css", "xpath", "id", "name", "text", "class"]).pack(side="left")

        dica = (
            "  #id → css  |  .classe ou tag.classe → css  |"
            "  //xpath → xpath  |  só o texto do id → id  |  nome do campo → name"
        )
        ctk.CTkLabel(self._fields_frame, text=dica,
                     anchor="w", text_color="gray55",
                     font=ctk.CTkFont(size=10)).pack(fill="x", pady=(0, 2))
        return sel_entry, por_var

    def _capture_browser_element(self):
        """Injeta JS no browser aberto para capturar o seletor CSS do proximo clique."""
        import runner
        driver = runner._driver
        if driver is None:
            tip = tk.Toplevel()
            tip.title("")
            tip.attributes("-topmost", True)
            tip.geometry("380x60+50+50")
            tip.overrideredirect(True)
            tk.Label(tip,
                     text="Abra o browser primeiro com um step 'browser_open'",
                     font=("Segoe UI", 11), bg="#2a1a1a", fg="white",
                     padx=16, pady=16).pack(fill="both")
            tip.after(4000, tip.destroy)
            return

        js = """(function() {
    var prev = null;
    function genSel(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        var cn = (typeof el.className === 'string') ? el.className.trim() : '';
        if (cn) {
            var cls = cn.split(/\\s+/).filter(Boolean).join('.');
            if (cls) return el.tagName.toLowerCase() + '.' + cls;
        }
        if (!el.parentNode) return el.tagName.toLowerCase();
        var idx = Array.from(el.parentNode.children).indexOf(el) + 1;
        if (idx < 1) return el.tagName.toLowerCase();
        return el.tagName.toLowerCase() + ':nth-child(' + idx + ')';
    }
    document.addEventListener('mouseover', function(e) {
        if (prev) prev.style.outline = '';
        prev = e.target;
        e.target.style.outline = '2px solid red';
    }, true);
    document.addEventListener('click', function(e) {
        e.preventDefault(); e.stopPropagation();
        if (prev) prev.style.outline = '';
        try {
            document.title = '__AF__:' + genSel(e.target);
        } catch(err) {
            document.title = '__AF__:' + e.target.tagName.toLowerCase();
        }
    }, true);
})();"""

        try:
            original_title = driver.title
            driver.execute_script(js)
        except Exception as e:
            tip_err = tk.Toplevel()
            tip_err.title("")
            tip_err.attributes("-topmost", True)
            tip_err.geometry("420x60+50+50")
            tip_err.overrideredirect(True)
            tk.Label(tip_err,
                     text=f"Erro ao injetar JS: {e}",
                     font=("Segoe UI", 10), bg="#3a1a1a", fg="white",
                     padx=16, pady=16).pack(fill="both")
            tip_err.after(5000, tip_err.destroy)
            return

        self._capturing_browser = True

        tip = tk.Toplevel()
        tip.title("")
        tip.attributes("-topmost", True)
        tip.geometry("380x60+50+50")
        tip.overrideredirect(True)
        tk.Label(tip,
                 text="Clique no elemento no browser para capturar o seletor",
                 font=("Segoe UI", 11), bg="#1a1a2e", fg="white",
                 padx=16, pady=16).pack(fill="both")

        def _on_tip_timeout():
            self._capturing_browser = False
            try:
                tip.destroy()
            except Exception:
                pass

        tip.after(15000, _on_tip_timeout)

        def _poll():
            if not getattr(self, "_capturing_browser", False):
                return
            try:
                title = driver.title
            except Exception:
                self._capturing_browser = False
                return
            if title.startswith("__AF__:"):
                selector = title[7:]
                self._capturing_browser = False
                try:
                    tip.destroy()
                except Exception:
                    pass
                try:
                    driver.execute_script(f"document.title = {repr(original_title)};")
                except Exception:
                    pass
                self.after(0, lambda: self._fill_selector(selector))
                return
            self.after(200, _poll)

        self.after(200, _poll)

    def _fill_selector(self, selector: str):
        if hasattr(self, "_sel_entry"):
            self._sel_entry.delete(0, "end")
            self._sel_entry.insert(0, selector)

    # ------------------------------------------------------------------
    def _collect_step(self) -> "dict | None":
        """Coleta os valores dos campos em um dict de step. Retorna None se houver erro."""
        tipo = self._tipo_var.get()
        step: dict = {"tipo": tipo}

        try:
            if tipo == "click":
                step["x"] = int(self._x_entry.get())
                step["y"] = int(self._y_entry.get())
                step["clique"] = self._click_type_var.get()
            elif tipo == "paste":
                step["texto"] = self._texto_box.get("1.0", "end-1c")
            elif tipo == "type":
                step["texto"] = self._type_box.get("1.0", "end-1c")
                step["intervalo"] = float(self._type_interval.get())
            elif tipo == "press":
                step["tecla"] = self._tecla_entry.get().strip()
            elif tipo == "hotkey":
                step["combinacao"] = self._combo_entry.get().strip()
            elif tipo == "scroll":
                step["quantidade"] = int(self._scroll_qty.get())
                x_val = self._scroll_x.get().strip()
                y_val = self._scroll_y.get().strip()
                if x_val:
                    step["x"] = int(x_val)
                if y_val:
                    step["y"] = int(y_val)
            elif tipo in ("click_image", "move_to_image"):
                step["template"]   = self._tpl_entry.get().strip()
                step["confidence"] = round(self._conf_var.get(), 2)
                step["timeout"]    = int(self._timeout_entry.get())
                step["offset_x"]   = int(self._offset_x.get() or 0)
                step["offset_y"]   = int(self._offset_y.get() or 0)
                step["ao_falhar"]  = self._ao_falhar_var.get()
                if tipo == "click_image":
                    step["clique"] = self._click_type_var.get()
                else:
                    step["duracao"] = float(self._duracao_entry.get() or 0.3)
            elif tipo == "click_text":
                step["texto"]     = self._ct_texto.get().strip()
                step["timeout"]   = int(self._timeout_entry.get())
                step["offset_x"]  = int(self._offset_x.get() or 0)
                step["offset_y"]  = int(self._offset_y.get() or 0)
                step["clique"]    = self._click_type_var.get()
                step["ao_falhar"] = self._ao_falhar_var.get()
            elif tipo == "wait_image":
                step["template"] = self._tpl_entry.get().strip()
                step["confidence"] = round(self._conf_var.get(), 2)
                step["timeout"] = int(self._timeout_entry.get())
                step["ao_falhar"] = self._ao_falhar_var.get()
            elif tipo == "sleep":
                step["segundos"] = float(self._sleep_entry.get())
            elif tipo == "screenshot":
                step["arquivo"] = self._shot_entry.get().strip()
            elif tipo == "loop":
                step["repeticoes"] = int(self._loop_reps.get())
                step["steps"] = self._loop_steps
            elif tipo == "if_image":
                step["template"] = self._if_tpl_entry.get().strip()
                step["confidence"] = round(self._if_conf_var.get(), 2)
                step["timeout"] = int(self._if_timeout_entry.get())
                step["steps_sim"] = self._if_steps_sim
                step["steps_nao"] = self._if_steps_nao
            elif tipo == "loop_lista":
                step["variavel"] = self._ll_var_entry.get().strip()
                raw = self._ll_lista_box.get("1.0", "end-1c")
                step["lista"] = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                step["steps"] = self._ll_steps
            elif tipo == "if_var":
                step["valor_comparar"] = self._ifv_comparar.get().strip()
                step["operador"] = self._ifv_op_var.get()
                step["valor_ref"] = self._ifv_ref.get().strip()
                step["steps_sim"] = self._ifv_steps_sim
                step["steps_nao"] = self._ifv_steps_nao

            # ------------------------------------------------------------------
            # Browser steps
            # ------------------------------------------------------------------
            elif tipo == "browser_open":
                step["browser"] = self._browser_var.get()
                step["url"] = self._browser_url.get().strip()
                step["headless"] = self._headless_var.get()
            elif tipo == "browser_close":
                pass  # sem campos
            elif tipo == "browser_navigate":
                step["url"] = self._browser_url.get().strip()
            elif tipo == "browser_click":
                step["selector"] = self._sel_entry.get().strip()
                step["por"] = self._por_var.get()
                step["timeout"] = int(self._br_timeout.get())
            elif tipo == "browser_fill":
                step["selector"] = self._sel_entry.get().strip()
                step["por"] = self._por_var.get()
                step["texto"] = self._fill_texto.get()
                step["limpar"] = self._limpar_var.get()
                step["timeout"] = int(self._br_timeout.get())
            elif tipo == "browser_wait":
                step["selector"] = self._sel_entry.get().strip()
                step["por"] = self._por_var.get()
                step["condicao"] = self._cond_var.get()
                step["timeout"] = int(self._br_timeout.get())
            elif tipo == "browser_select":
                step["selector"] = self._sel_entry.get().strip()
                step["por"] = self._por_var.get()
                step["valor"] = self._select_valor.get().strip()
                step["timeout"] = int(self._br_timeout.get())
            elif tipo == "browser_get_text":
                step["selector"] = self._sel_entry.get().strip()
                step["por"] = self._por_var.get()
                step["variavel"] = self._variavel_entry.get().strip()
                step["timeout"] = int(self._br_timeout.get())
            elif tipo == "browser_run_js":
                step["script"] = self._js_box.get("1.0", "end-1c")
            elif tipo == "browser_screenshot":
                step["arquivo"] = self._br_shot_entry.get().strip()
            elif tipo == "wait_text":
                step["texto"]     = self._ct_texto.get().strip()
                step["timeout"]   = int(self._timeout_entry.get())
                step["ao_falhar"] = self._ao_falhar_var.get()
            elif tipo == "run_workflow":
                step["workflow"] = self._rw_entry.get().strip()
            elif tipo == "get_clipboard":
                step["variavel"] = self._gc_var.get().strip()
            elif tipo == "browser_get_url":
                step["variavel"] = self._bgu_var.get().strip()

            # Retry (universal)
            try:
                step["retry"] = int(self._retry_entry.get())
                step["retry_delay"] = float(self._retry_delay.get())
            except Exception:
                pass

        except ValueError as e:
            ctk.CTkLabel(self._fields_frame,
                         text=f"Erro: {e}", text_color="red").pack()
            return None

        return step

    def _on_ok(self):
        step = self._collect_step()
        if step is None:
            return

        # Nota opcional
        if hasattr(self, "_nota_entry"):
            nota = self._nota_entry.get().strip()
            if nota:
                step["nota"] = nota

        # Preserva flag ativo
        step["ativo"] = self._step.get("ativo", True)

        self.result = step
        self.destroy()

    def _test_step(self):
        """Executa apenas este step (sem fechar o dialog)."""
        import runner
        step = self._collect_step()
        if step is None:
            return

        def _show_error(msg):
            self.after(0, lambda: self._show_test_error(msg))

        runner.execute_single_step(step, on_error=_show_error)

    def _show_test_error(self, msg: str):
        tip = tk.Toplevel()
        tip.title("Erro ao testar step")
        tip.attributes("-topmost", True)
        tip.geometry("480x80+50+50")
        tip.overrideredirect(True)
        tk.Label(tip, text=f"Erro: {msg}",
                 font=("Segoe UI", 10), bg="#3a1010", fg="white",
                 padx=14, pady=14, wraplength=450, justify="left").pack(fill="both")
        tip.after(7000, tip.destroy)


# ------------------------------------------------------------------
class LoopStepsDialog(ctk.CTkToplevel):
    """Dialog para gerenciar os sub-steps de um step tipo loop."""

    def __init__(self, parent, steps: list = None):
        super().__init__(parent)
        self.title("Sub-steps do Loop")
        self.geometry("540x500")
        self.grab_set()
        self.lift()

        self.result: list | None = None
        self._steps: list = steps or []
        self._build_ui()
        self._refresh()

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, label_text="Steps do loop")
        self._scroll.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        ctk.CTkButton(footer, text="+ Adicionar Step", command=self._add_step).pack(side="left")
        ctk.CTkButton(footer, text="Cancelar", width=90,
                      fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="OK", width=90, command=self._on_ok).pack(side="right")

    def _refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        if not self._steps:
            ctk.CTkLabel(self._scroll,
                         text="Nenhum sub-step. Clique em '+ Adicionar Step'.",
                         text_color="gray60").pack(pady=20)
            return
        for i, step in enumerate(self._steps):
            self._build_row(i, step)

    def _build_row(self, i: int, step: dict):
        from gui.workflow_editor import _step_label
        row = ctk.CTkFrame(self._scroll)
        row.pack(fill="x", pady=2, padx=4)
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=f"{i+1:>2}.", width=28,
                     font=ctk.CTkFont(family="Courier New")).grid(row=0, column=0, padx=(6, 2), pady=6)
        ctk.CTkLabel(row, text=_step_label(step), anchor="w",
                     font=ctk.CTkFont(family="Courier New", size=11)).grid(
            row=0, column=1, padx=2, pady=6, sticky="ew")
        bf = ctk.CTkFrame(row, fg_color="transparent")
        bf.grid(row=0, column=2, padx=(2, 6), pady=4)
        ctk.CTkButton(bf, text="Editar", width=52, height=26,
                      command=lambda i=i: self._edit(i)).pack(side="left", padx=2)
        ctk.CTkButton(bf, text="✕", width=26, height=26,
                      fg_color="#8B1A1A", hover_color="#6B0000",
                      command=lambda i=i: self._remove(i)).pack(side="left", padx=2)

    def _add_step(self):
        dlg = StepEditorDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._steps.append(dlg.result)
            self._refresh()

    def _edit(self, i: int):
        dlg = StepEditorDialog(self, self._steps[i])
        self.wait_window(dlg)
        if dlg.result:
            self._steps[i] = dlg.result
            self._refresh()

    def _remove(self, i: int):
        self._steps.pop(i)
        self._refresh()

    def _on_ok(self):
        self.result = self._steps
        self.destroy()
