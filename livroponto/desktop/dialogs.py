"""Janelas modais (formulários) para adicionar/editar uma Pessoa, uma
exceção de calendário ou um membro da equipe gestora no app desktop."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..models import DiaNaoLetivo, MembroGestao, Pessoa, TipoServidor

TIPOS_PESSOA = ["ADMINISTRATIVO", "DOCENTE"]
TIPOS_EXCECAO = ["FERIADO", "RECESSO", "PONTO_FACULTATIVO", "SUSPENSAO", "LETIVO"]
CARGOS_GESTAO = [
    "Diretor(a) de Escola",
    "Vice-Diretor(a) de Escola",
    "Professor Coordenador Pedagógico",
    "Secretário(a) de Escola",
]


class _DialogoBase(tk.Toplevel):
    """Janela modal simples: centraliza, trava o foco, e guarda o
    resultado em `self.resultado` (None se cancelado)."""

    def __init__(self, parent: tk.Widget, titulo: str):
        super().__init__(parent)
        self.title(titulo)
        self.resultado = None
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

    def _finalizar(self, centro_em: tk.Widget) -> None:
        self.update_idletasks()
        x = centro_em.winfo_rootx() + (centro_em.winfo_width() - self.winfo_width()) // 2
        y = centro_em.winfo_rooty() + (centro_em.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.wait_window(self)


def _linha(frame: tk.Widget, r: int, rotulo: str, largura: int = 32) -> tk.StringVar:
    ttk.Label(frame, text=rotulo).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
    var = tk.StringVar()
    ttk.Entry(frame, textvariable=var, width=largura).grid(row=r, column=1, sticky="we", pady=3)
    return var


class DialogoPessoa(_DialogoBase):
    def __init__(self, parent: tk.Widget, pessoa: Pessoa | None = None):
        super().__init__(parent, "Editar servidor" if pessoa else "Adicionar servidor")

        corpo = ttk.Frame(self, padding=12)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)
        corpo.columnconfigure(3, weight=1)

        r = 0
        ttk.Label(corpo, text="Tipo").grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_tipo = tk.StringVar(value=TIPOS_PESSOA[0])
        ttk.Combobox(
            corpo, textvariable=self.var_tipo, values=TIPOS_PESSOA, state="readonly", width=18
        ).grid(row=r, column=1, sticky="w", pady=3)
        self.var_ponto = tk.BooleanVar(value=True)
        ttk.Checkbutton(corpo, text="Imprime folha de ponto", variable=self.var_ponto).grid(
            row=r, column=2, columnspan=2, sticky="w", pady=3
        )
        r += 1

        self.var_nome = _linha(corpo, r, "Nome")
        r += 1
        self.var_rg = _linha(corpo, r, "RG")
        r += 1
        self.var_cargo = _linha(corpo, r, "Cargo/Função")
        r += 1
        self.var_observacoes = _linha(corpo, r, "Observações", 40)
        ttk.Label(corpo, text="(ex.: afastamentos — sai impressa na folha de Consolidação)", foreground="grey").grid(
            row=r, column=2, columnspan=2, sticky="w", padx=(12, 0)
        )
        r += 1

        ttk.Label(corpo, text="Jornada (h/sem)").grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_jornada = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_jornada, width=10).grid(row=r, column=1, sticky="w", pady=3)
        ttk.Label(corpo, text="Jornada (código, docente)").grid(row=r, column=2, sticky="w", padx=(12, 8), pady=3)
        self.var_jornada_codigo = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_jornada_codigo, width=10).grid(row=r, column=3, sticky="w", pady=3)
        r += 1

        ttk.Separator(corpo).grid(row=r, column=0, columnspan=4, sticky="we", pady=6)
        r += 1

        ttk.Label(corpo, text="— campos de administrativo —", foreground="grey").grid(
            row=r, column=0, columnspan=4, sticky="w"
        )
        r += 1
        self.var_entrada = _linha(corpo, r, "Entrada", 12)
        self.var_saida = tk.StringVar()
        ttk.Label(corpo, text="Saída").grid(row=r, column=2, sticky="w", padx=(12, 8))
        ttk.Entry(corpo, textvariable=self.var_saida, width=12).grid(row=r, column=3, sticky="w")
        r += 1
        self.var_intervalo_inicio = _linha(corpo, r, "Intervalo de", 12)
        self.var_intervalo_fim = tk.StringVar()
        ttk.Label(corpo, text="Intervalo até").grid(row=r, column=2, sticky="w", padx=(12, 8))
        ttk.Entry(corpo, textvariable=self.var_intervalo_fim, width=12).grid(row=r, column=3, sticky="w")
        r += 1
        self.var_ferias_inicio = _linha(corpo, r, "Férias de", 12)
        self.var_ferias_fim = tk.StringVar()
        ttk.Label(corpo, text="Férias até").grid(row=r, column=2, sticky="w", padx=(12, 8))
        ttk.Entry(corpo, textvariable=self.var_ferias_fim, width=12).grid(row=r, column=3, sticky="w")
        r += 1
        ttk.Label(
            corpo,
            text="(preenche o campo FÉRIAS da folha de ponto e sai anotado no verso: "
            "\"Férias Regulares de ___ a ___\")",
            foreground="grey",
        ).grid(row=r, column=0, columnspan=4, sticky="w")
        r += 1

        ttk.Separator(corpo).grid(row=r, column=0, columnspan=4, sticky="we", pady=6)
        r += 1
        ttk.Label(corpo, text="— campos de docente —", foreground="grey").grid(
            row=r, column=0, columnspan=4, sticky="w"
        )
        r += 1
        self.var_disciplinas = _linha(corpo, r, "Disciplina(s)")
        r += 1
        self.var_categoria = _linha(corpo, r, "Categoria")
        r += 1
        self.var_situacao = _linha(corpo, r, "Situação")
        r += 1

        botoes = ttk.Frame(corpo)
        botoes.grid(row=r, column=0, columnspan=4, sticky="e", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self._cancelar).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Salvar", command=self._salvar).pack(side="right")

        if pessoa is not None:
            self._preencher(pessoa)

        self.bind("<Return>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._finalizar(parent)

    def _preencher(self, p: Pessoa) -> None:
        self.var_tipo.set(p.tipo.value)
        self.var_ponto.set(p.ponto)
        self.var_nome.set(p.nome)
        self.var_rg.set(p.rg)
        self.var_cargo.set(p.cargo)
        self.var_jornada.set("" if p.jornada_semanal is None else str(p.jornada_semanal))
        self.var_jornada_codigo.set(p.jornada_codigo)
        self.var_entrada.set(p.entrada)
        self.var_saida.set(p.saida)
        self.var_intervalo_inicio.set(p.intervalo_inicio)
        self.var_intervalo_fim.set(p.intervalo_fim)
        self.var_ferias_inicio.set(p.ferias_inicio)
        self.var_ferias_fim.set(p.ferias_fim)
        self.var_disciplinas.set(p.disciplinas)
        self.var_categoria.set(p.categoria)
        self.var_situacao.set(p.situacao)
        self.var_observacoes.set(p.observacoes)

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def _salvar(self) -> None:
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showerror("Faltou o nome", "Informe o nome do servidor.", parent=self)
            return
        jornada_raw = self.var_jornada.get().strip().replace(",", ".")
        jornada = None
        if jornada_raw:
            try:
                jornada = float(jornada_raw)
            except ValueError:
                messagebox.showerror("Jornada inválida", "A jornada (h/semana) deve ser um número.", parent=self)
                return
        self.resultado = Pessoa(
            nome=nome,
            tipo=TipoServidor(self.var_tipo.get()),
            rg=self.var_rg.get().strip(),
            cargo=self.var_cargo.get().strip(),
            jornada_semanal=jornada,
            jornada_codigo=self.var_jornada_codigo.get().strip(),
            ponto=self.var_ponto.get(),
            entrada=self.var_entrada.get().strip(),
            saida=self.var_saida.get().strip(),
            intervalo_inicio=self.var_intervalo_inicio.get().strip(),
            intervalo_fim=self.var_intervalo_fim.get().strip(),
            ferias_inicio=self.var_ferias_inicio.get().strip(),
            ferias_fim=self.var_ferias_fim.get().strip(),
            disciplinas=self.var_disciplinas.get().strip(),
            categoria=self.var_categoria.get().strip(),
            situacao=self.var_situacao.get().strip(),
            observacoes=self.var_observacoes.get().strip(),
        )
        self.destroy()


class DialogoExcecao(_DialogoBase):
    def __init__(self, parent: tk.Widget, excecao: DiaNaoLetivo | None = None):
        super().__init__(parent, "Editar exceção" if excecao else "Adicionar exceção de calendário")

        corpo = ttk.Frame(self, padding=12)
        corpo.pack(fill="both", expand=True)

        ttk.Label(corpo, text="Mês (1-12)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_mes = tk.StringVar(value="1")
        ttk.Spinbox(corpo, from_=1, to=12, textvariable=self.var_mes, width=6).grid(row=0, column=1, sticky="w")

        ttk.Label(corpo, text="Dia").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_dia = tk.StringVar(value="1")
        ttk.Spinbox(corpo, from_=1, to=31, textvariable=self.var_dia, width=6).grid(row=1, column=1, sticky="w")

        ttk.Label(corpo, text="Tipo").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_tipo = tk.StringVar(value=TIPOS_EXCECAO[0])
        ttk.Combobox(
            corpo, textvariable=self.var_tipo, values=TIPOS_EXCECAO, state="readonly", width=20
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(corpo, text="Descrição").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_descricao = tk.StringVar()
        ttk.Entry(corpo, textvariable=self.var_descricao, width=32).grid(row=3, column=1, sticky="we")

        botoes = ttk.Frame(corpo)
        botoes.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self._cancelar).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Salvar", command=self._salvar).pack(side="right")

        if excecao is not None:
            self.var_mes.set(str(excecao.mes))
            self.var_dia.set(str(excecao.dia))
            self.var_tipo.set(excecao.tipo)
            self.var_descricao.set(excecao.descricao)

        self.bind("<Return>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._finalizar(parent)

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def _salvar(self) -> None:
        try:
            mes = int(self.var_mes.get())
            dia = int(self.var_dia.get())
        except ValueError:
            messagebox.showerror("Data inválida", "Mês e dia devem ser números.", parent=self)
            return
        if not (1 <= mes <= 12) or not (1 <= dia <= 31):
            messagebox.showerror("Data inválida", "Mês deve ser 1-12 e dia 1-31.", parent=self)
            return
        self.resultado = DiaNaoLetivo(
            mes=mes, dia=dia, tipo=self.var_tipo.get(), descricao=self.var_descricao.get().strip()
        )
        self.destroy()


class DialogoMembroGestao(_DialogoBase):
    def __init__(self, parent: tk.Widget, membro: MembroGestao | None = None):
        super().__init__(parent, "Editar membro da equipe gestora" if membro else "Adicionar membro da equipe gestora")

        corpo = ttk.Frame(self, padding=12)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text="Cargo").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.var_cargo = tk.StringVar(value=CARGOS_GESTAO[0])
        ttk.Combobox(corpo, textvariable=self.var_cargo, values=CARGOS_GESTAO, width=34).grid(
            row=0, column=1, sticky="we", pady=3
        )

        self.var_nome = _linha(corpo, 1, "Nome")
        self.var_rg = _linha(corpo, 2, "RG")

        botoes = ttk.Frame(corpo)
        botoes.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self._cancelar).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Salvar", command=self._salvar).pack(side="right")

        if membro is not None:
            self.var_cargo.set(membro.cargo)
            self.var_nome.set(membro.nome)
            self.var_rg.set(membro.rg)

        self.bind("<Return>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._finalizar(parent)

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def _salvar(self) -> None:
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showerror("Faltou o nome", "Informe o nome do membro da equipe gestora.", parent=self)
            return
        self.resultado = MembroGestao(
            nome=nome,
            cargo=self.var_cargo.get().strip(),
            rg=self.var_rg.get().strip(),
        )
        self.destroy()
