"""App nativo (Tkinter) para editar os dados do Livro Ponto e gerar o PDF —
sem servidor local, sem navegador: uma janela de desktop de verdade.

Rode com:

    livroponto desktop

ou diretamente:

    python -m livroponto.desktop.app
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from ..calendario import nome_mes
from ..models import Escola, LivroPontoConfig, TipoServidor, chave_ordenacao_rg
from ..pdf.builder import gerar_pdf
from ..readers.template_reader import ler_modelo, salvar_modelo
from ..readers.xlsb_reader import ler_livro_ponto
from .dialogs import DialogoExcecao, DialogoPessoa

_ICONE = Path(__file__).resolve().parent / "assets" / "icone_livro.png"

MESES_CAP = [nome_mes(i).capitalize() for i in range(1, 13)]

# Sufixo do nome de arquivo sugerido ao gerar o PDF, na ordem em que deve
# aparecer quando mais de um tipo está marcado em "Incluir".
_SUFIXO_ARQUIVO_TIPO = [
    (TipoServidor.ADMINISTRATIVO, "administrativo"),
    (TipoServidor.GESTAO, "gestao"),
    (TipoServidor.DOCENTE, "docente"),
]


def _config_vazio() -> LivroPontoConfig:
    hoje = date.today()
    return LivroPontoConfig(escola=Escola(), mes=hoje.month, ano=hoje.year, pessoas=[])


def _abrir_no_sistema(caminho: str) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", caminho], check=False)
        else:
            subprocess.run(["xdg-open", caminho], check=False)
    except OSError:
        pass  # não é crítico — o usuário já sabe onde o arquivo ficou


class Aplicativo(ttk.Window):
    def __init__(self) -> None:
        super().__init__(title="Livro Ponto — editor", themename="bootstrap-light", size=(1000, 650))
        self.minsize(760, 480)
        try:
            self.iconphoto(True, tk.PhotoImage(file=str(_ICONE)))
        except tk.TclError:
            pass  # ícone é só um detalhe visual — se faltar, o app segue normal

        self.dados: LivroPontoConfig = _config_vazio()
        self.caminho_atual: str | None = None

        self._construir_barra_ferramentas()
        self._construir_abas()
        self._construir_barra_status()

        self._atualizar_tudo()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _construir_barra_ferramentas(self) -> None:
        barra = ttk.Frame(self, padding=(8, 8, 8, 0))
        barra.pack(fill="x")
        ttk.Button(barra, text="Novo", command=self._novo, bootstyle="secondary-outline").pack(side="left")
        ttk.Button(barra, text="Abrir...", command=self._abrir, bootstyle="secondary-outline").pack(
            side="left", padx=6
        )
        ttk.Button(
            barra, text="Salvar cadastro...", command=self._salvar_cadastro, bootstyle="secondary-outline"
        ).pack(side="left")
        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(
            barra, text="🖨️ Gerar Livro Ponto (PDF)...", command=self._gerar_pdf, bootstyle="success"
        ).pack(side="left")
        ttk.Label(barra, text="Incluir:").pack(side="left", padx=(10, 2))
        self.var_incluir_administrativos = tk.BooleanVar(value=True)
        self.var_incluir_docentes = tk.BooleanVar(value=True)
        self.var_incluir_gestao = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            barra,
            text="Administrativos",
            variable=self.var_incluir_administrativos,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            barra, text="Docentes", variable=self.var_incluir_docentes, bootstyle="round-toggle"
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            barra, text="Trio gestor", variable=self.var_incluir_gestao, bootstyle="round-toggle"
        ).pack(side="left")

    def _construir_abas(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        aba_escola = ttk.Frame(notebook, padding=12)
        aba_administrativo = ttk.Frame(notebook)
        aba_gestao = ttk.Frame(notebook)
        aba_excecoes = ttk.Frame(notebook)
        notebook.add(aba_escola, text="Escola")
        notebook.add(aba_administrativo, text="Administrativo")
        notebook.add(aba_gestao, text="Gestão")
        notebook.add(aba_excecoes, text="Feriados e exceções")

        self._construir_aba_escola(aba_escola)
        self.tree_administrativo = self._construir_aba_pessoas_tipo(aba_administrativo, TipoServidor.ADMINISTRATIVO)
        self.tree_gestao = self._construir_aba_pessoas_tipo(aba_gestao, TipoServidor.GESTAO)
        self._construir_aba_excecoes(aba_excecoes)

    def _construir_aba_escola(self, aba: ttk.Frame) -> None:
        aba.columnconfigure(1, weight=1)
        aba.columnconfigure(3, weight=1)

        def campo(r: int, c: int, rotulo: str, largura: int = 34) -> tk.StringVar:
            ttk.Label(aba, text=rotulo).grid(row=r, column=c, sticky="w", padx=(0, 8), pady=4)
            var = tk.StringVar()
            ttk.Entry(aba, textvariable=var, width=largura).grid(row=r, column=c + 1, sticky="we", pady=4)
            return var

        self.var_nome = campo(0, 0, "Nome da escola", 60)
        aba.grid_slaves(row=0, column=1)[0].grid(columnspan=3, sticky="we")
        self.var_diretoria = campo(1, 0, "Diretoria de Ensino", 60)
        aba.grid_slaves(row=1, column=1)[0].grid(columnspan=3, sticky="we")
        self.var_endereco = campo(2, 0, "Endereço", 60)
        aba.grid_slaves(row=2, column=1)[0].grid(columnspan=3, sticky="we")
        self.var_municipio = campo(3, 0, "Município")
        self.var_telefone1 = campo(3, 2, "Telefone")
        self.var_email = campo(4, 0, "E-mail")
        self.var_codigo_ua = campo(4, 2, "Código UA", 16)
        self.var_codigo_cie = campo(5, 0, "Código CIE", 16)

        ttk.Separator(aba).grid(row=6, column=0, columnspan=4, sticky="we", pady=10)

        ttk.Label(aba, text="Mês").grid(row=7, column=0, sticky="w", padx=(0, 8), pady=4)
        self.var_mes = tk.StringVar(value=MESES_CAP[0])
        ttk.Combobox(
            aba, textvariable=self.var_mes, values=MESES_CAP, state="readonly", width=14
        ).grid(row=7, column=1, sticky="w", pady=4)

        ttk.Label(aba, text="Ano").grid(row=7, column=2, sticky="w", padx=(12, 8), pady=4)
        self.var_ano = tk.StringVar()
        ttk.Spinbox(aba, from_=2000, to=2100, textvariable=self.var_ano, width=8).grid(
            row=7, column=3, sticky="w", pady=4
        )

        self.var_uf = campo(8, 0, "UF (feriados)", 6)
        self.var_cidade = campo(8, 2, "Cidade (assinatura dos termos)", 24)

    def _construir_aba_pessoas_tipo(self, aba: ttk.Frame, tipo: TipoServidor) -> ttk.Treeview:
        """Monta uma aba de cadastro (Treeview + Adicionar/Editar/Remover)
        filtrada para um único tipo de servidor — Administrativo e Gestão
        têm cada um a sua, sempre mostrando/criando gente desse tipo."""
        barra = ttk.Frame(aba, padding=(8, 8, 8, 4))
        barra.pack(fill="x")
        ttk.Button(
            barra, text="Adicionar", command=lambda: self._adicionar_pessoa_tipo(tipo), bootstyle="primary"
        ).pack(side="left")
        ttk.Button(
            barra,
            text="Editar",
            command=lambda: self._editar_pessoa_selecionada_tipo(tipo),
            bootstyle="info-outline",
        ).pack(side="left", padx=6)
        ttk.Button(
            barra,
            text="Remover",
            command=lambda: self._remover_pessoa_selecionada_tipo(tipo),
            bootstyle="danger-outline",
        ).pack(side="left")
        ttk.Label(
            barra, text="  (duplo-clique numa linha também edita)", foreground="grey"
        ).pack(side="left")

        colunas = ("nome", "rg", "cargo", "jornada", "ponto", "observacoes")
        titulos = {
            "nome": "Nome",
            "rg": "RG",
            "cargo": "Cargo/Função",
            "jornada": "Jornada",
            "ponto": "Ponto?",
            "observacoes": "Observações",
        }
        larguras = {"nome": 220, "rg": 110, "cargo": 220, "jornada": 70, "ponto": 60, "observacoes": 260}

        container = ttk.Frame(aba)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tree = ttk.Treeview(container, columns=colunas, show="headings", selectmode="browse")
        for c in colunas:
            tree.heading(c, text=titulos[c])
            tree.column(c, width=larguras[c], anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda _e: self._editar_pessoa_selecionada_tipo(tipo))
        return tree

    def _construir_aba_excecoes(self, aba: ttk.Frame) -> None:
        aviso = (
            "Feriados nacionais e estaduais já são calculados automaticamente pela UF "
            "informada na aba Escola. Cadastre aqui só o que for específico do seu "
            "município/escola: recesso, ponto facultativo, suspensão de atividades, "
            "ou um sábado letivo de reposição (tipo LETIVO)."
        )
        ttk.Label(aba, text=aviso, wraplength=920, foreground="grey").pack(
            fill="x", padx=8, pady=(8, 4)
        )

        barra = ttk.Frame(aba, padding=(8, 0, 8, 4))
        barra.pack(fill="x")
        ttk.Button(barra, text="Adicionar", command=self._adicionar_excecao, bootstyle="primary").pack(side="left")
        ttk.Button(
            barra, text="Editar", command=self._editar_excecao_selecionada, bootstyle="info-outline"
        ).pack(side="left", padx=6)
        ttk.Button(
            barra, text="Remover", command=self._remover_excecao_selecionada, bootstyle="danger-outline"
        ).pack(side="left")

        colunas = ("mes", "dia", "tipo", "descricao")
        titulos = {"mes": "Mês", "dia": "Dia", "tipo": "Tipo", "descricao": "Descrição"}
        larguras = {"mes": 60, "dia": 50, "tipo": 160, "descricao": 400}

        container = ttk.Frame(aba)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree_excecoes = ttk.Treeview(container, columns=colunas, show="headings", selectmode="browse")
        for c in colunas:
            self.tree_excecoes.heading(c, text=titulos[c])
            self.tree_excecoes.column(c, width=larguras[c], anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_excecoes.yview)
        self.tree_excecoes.configure(yscrollcommand=scroll.set)
        self.tree_excecoes.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree_excecoes.bind("<Double-1>", lambda _e: self._editar_excecao_selecionada())

    def _construir_barra_status(self) -> None:
        self.var_status = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.var_status, relief="sunken", anchor="w", padding=(6, 2)).pack(
            fill="x", side="bottom"
        )

    # ------------------------------------------------------------------
    # Sincronização entre self.dados e os campos da aba Escola
    # ------------------------------------------------------------------
    def _atualizar_campos_escola(self) -> None:
        e = self.dados.escola
        self.var_nome.set(e.nome)
        self.var_diretoria.set(e.diretoria_ensino)
        self.var_endereco.set(e.endereco)
        self.var_municipio.set(e.municipio)
        self.var_telefone1.set(e.telefone1)
        self.var_email.set(e.email)
        self.var_codigo_ua.set(e.codigo_ua)
        self.var_codigo_cie.set(e.codigo_cie)
        self.var_mes.set(MESES_CAP[self.dados.mes - 1])
        self.var_ano.set(str(self.dados.ano))
        self.var_uf.set(self.dados.uf or "SP")
        self.var_cidade.set(self.dados.cidade_assinatura or e.municipio)

    def _sincronizar_escola(self) -> None:
        e = self.dados.escola
        e.nome = self.var_nome.get().strip()
        e.diretoria_ensino = self.var_diretoria.get().strip()
        e.endereco = self.var_endereco.get().strip()
        e.municipio = self.var_municipio.get().strip()
        e.telefone1 = self.var_telefone1.get().strip()
        e.email = self.var_email.get().strip()
        e.codigo_ua = self.var_codigo_ua.get().strip()
        e.codigo_cie = self.var_codigo_cie.get().strip()
        if self.var_mes.get() in MESES_CAP:
            self.dados.mes = MESES_CAP.index(self.var_mes.get()) + 1
        try:
            self.dados.ano = int(self.var_ano.get())
        except ValueError:
            pass
        self.dados.uf = self.var_uf.get().strip() or "SP"
        self.dados.cidade_assinatura = self.var_cidade.get().strip()

    def _atualizar_tudo(self) -> None:
        self._atualizar_campos_escola()
        self._atualizar_listas_pessoas()
        self._atualizar_lista_excecoes()

    def _status(self, texto: str) -> None:
        self.var_status.set(texto)

    # ------------------------------------------------------------------
    # Arquivo: novo / abrir / salvar / gerar PDF
    # ------------------------------------------------------------------
    def _novo(self) -> None:
        if not messagebox.askyesno(
            "Começar do zero", "Os dados não salvos serão perdidos. Continuar?", parent=self
        ):
            return
        self.dados = _config_vazio()
        self.caminho_atual = None
        self._atualizar_tudo()
        self._status("Novo cadastro.")

    def _abrir(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Abrir planilha",
            filetypes=[
                ("Planilhas suportadas", "*.xlsx *.xlsb"),
                ("Modelo deste app (.xlsx)", "*.xlsx"),
                ("Planilha legada SEDUC-SP (.xlsb)", "*.xlsb"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not caminho:
            return
        try:
            if caminho.lower().endswith(".xlsb"):
                novo = ler_livro_ponto(caminho)
            else:
                novo = ler_modelo(caminho)
        except Exception as exc:  # noqa: BLE001 — mostra qualquer erro de leitura ao usuário
            messagebox.showerror("Erro ao abrir arquivo", str(exc), parent=self)
            return
        self.dados = novo
        self.caminho_atual = caminho
        self._atualizar_tudo()
        self._status(f"Carregado: {len(novo.pessoas)} pessoa(s) de {Path(caminho).name}")

    def _salvar_cadastro(self) -> None:
        self._sincronizar_escola()
        caminho = filedialog.asksaveasfilename(
            title="Salvar cadastro",
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")],
            initialfile="modelo_livro_ponto.xlsx",
        )
        if not caminho:
            return
        try:
            salvar_modelo(self.dados, caminho)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao salvar", str(exc), parent=self)
            return
        self.caminho_atual = caminho
        self._status(f"Cadastro salvo em {caminho}")
        messagebox.showinfo("Cadastro salvo", f"Salvo em:\n{caminho}", parent=self)

    def _gerar_pdf(self) -> None:
        self._sincronizar_escola()

        tipos_incluidos = set()
        if self.var_incluir_administrativos.get():
            tipos_incluidos.add(TipoServidor.ADMINISTRATIVO)
        if self.var_incluir_docentes.get():
            tipos_incluidos.add(TipoServidor.DOCENTE)
        if self.var_incluir_gestao.get():
            tipos_incluidos.add(TipoServidor.GESTAO)
        if not tipos_incluidos:
            messagebox.showwarning(
                "Nada para gerar",
                "Marque ao menos um em \"Incluir\": Administrativos, Docentes e/ou Trio gestor.",
                parent=self,
            )
            return

        pessoas_filtradas = [p for p in self.dados.pessoas if p.tipo in tipos_incluidos]
        if not any(p.ponto for p in pessoas_filtradas):
            messagebox.showwarning(
                "Nada para gerar",
                "Adicione ao menos um servidor (do(s) tipo(s) marcado(s) em \"Incluir\") "
                "com \"Ponto?\" marcado.",
                parent=self,
            )
            return

        sufixo = "_".join(s for t, s in _SUFIXO_ARQUIVO_TIPO if t in tipos_incluidos)
        base = f"livro_ponto_{sufixo}" if sufixo else "livro_ponto"
        nome_sugerido = f"{base}_{self.dados.mes:02d}_{self.dados.ano}.pdf"
        caminho = filedialog.asksaveasfilename(
            title="Gerar Livro Ponto",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=nome_sugerido,
        )
        if not caminho:
            return
        try:
            gerar_pdf(replace(self.dados, pessoas=pessoas_filtradas), caminho)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao gerar PDF", str(exc), parent=self)
            return
        self._status(f"PDF gerado em {caminho}")
        if messagebox.askyesno("PDF gerado", f"Gerado em:\n{caminho}\n\nAbrir agora?", parent=self):
            _abrir_no_sistema(caminho)

    # ------------------------------------------------------------------
    # Abas Administrativo / Gestão
    # ------------------------------------------------------------------
    def _tree_do_tipo(self, tipo: TipoServidor) -> ttk.Treeview:
        return self.tree_administrativo if tipo == TipoServidor.ADMINISTRATIVO else self.tree_gestao

    def _atualizar_lista_pessoas_tipo(self, tipo: TipoServidor) -> None:
        """Mostra os servidores desse tipo ordenados por RG (mesma ordem em
        que saem as folhas no PDF) — o iid de cada linha continua sendo o
        índice real em `self.dados.pessoas`, só a ordem de exibição muda."""
        tree = self._tree_do_tipo(tipo)
        tree.delete(*tree.get_children())
        itens = sorted(
            ((i, p) for i, p in enumerate(self.dados.pessoas) if p.tipo == tipo),
            key=lambda item: chave_ordenacao_rg(item[1]),
        )
        for i, p in itens:
            jornada = "" if p.jornada_semanal is None else f"{p.jornada_semanal:g}"
            tree.insert(
                "",
                "end",
                iid=str(i),
                values=(p.nome, p.rg, p.cargo, jornada, "Sim" if p.ponto else "Não", p.observacoes),
            )

    def _atualizar_listas_pessoas(self) -> None:
        self._atualizar_lista_pessoas_tipo(TipoServidor.ADMINISTRATIVO)
        self._atualizar_lista_pessoas_tipo(TipoServidor.GESTAO)

    def _pessoa_selecionada_tipo(self, tipo: TipoServidor) -> int | None:
        sel = self._tree_do_tipo(tipo).selection()
        return int(sel[0]) if sel else None

    def _adicionar_pessoa_tipo(self, tipo: TipoServidor) -> None:
        dlg = DialogoPessoa(self, tipo_inicial=tipo)
        if dlg.resultado:
            self.dados.pessoas.append(dlg.resultado)
            self._atualizar_listas_pessoas()
            self._status("Servidor adicionado.")

    def _editar_pessoa_selecionada_tipo(self, tipo: TipoServidor) -> None:
        idx = self._pessoa_selecionada_tipo(tipo)
        if idx is None:
            messagebox.showinfo("Selecione um servidor", "Clique numa linha da tabela primeiro.", parent=self)
            return
        dlg = DialogoPessoa(self, self.dados.pessoas[idx])
        if dlg.resultado:
            self.dados.pessoas[idx] = dlg.resultado
            # o tipo pode ter mudado no diálogo (ex.: promovido a Gestão) —
            # atualiza as duas abas pra pessoa aparecer na certa.
            self._atualizar_listas_pessoas()
            self._status("Servidor atualizado.")

    def _remover_pessoa_selecionada_tipo(self, tipo: TipoServidor) -> None:
        idx = self._pessoa_selecionada_tipo(tipo)
        if idx is None:
            messagebox.showinfo("Selecione um servidor", "Clique numa linha da tabela primeiro.", parent=self)
            return
        pessoa = self.dados.pessoas[idx]
        if messagebox.askyesno("Remover servidor", f"Remover {pessoa.nome}?", parent=self):
            del self.dados.pessoas[idx]
            self._atualizar_listas_pessoas()
            self._status("Servidor removido.")

    # ------------------------------------------------------------------
    # Aba Exceções de calendário
    # ------------------------------------------------------------------
    def _atualizar_lista_excecoes(self) -> None:
        self.tree_excecoes.delete(*self.tree_excecoes.get_children())
        for i, exc in enumerate(self.dados.dias_excecao):
            self.tree_excecoes.insert(
                "", "end", iid=str(i), values=(exc.mes, exc.dia, exc.tipo, exc.descricao)
            )

    def _excecao_selecionada(self) -> int | None:
        sel = self.tree_excecoes.selection()
        return int(sel[0]) if sel else None

    def _adicionar_excecao(self) -> None:
        dlg = DialogoExcecao(self)
        if dlg.resultado:
            self.dados.dias_excecao.append(dlg.resultado)
            self._atualizar_lista_excecoes()
            self._status("Exceção adicionada.")

    def _editar_excecao_selecionada(self) -> None:
        idx = self._excecao_selecionada()
        if idx is None:
            messagebox.showinfo("Selecione uma exceção", "Clique numa linha da tabela primeiro.", parent=self)
            return
        dlg = DialogoExcecao(self, self.dados.dias_excecao[idx])
        if dlg.resultado:
            self.dados.dias_excecao[idx] = dlg.resultado
            self._atualizar_lista_excecoes()
            self._status("Exceção atualizada.")

    def _remover_excecao_selecionada(self) -> None:
        idx = self._excecao_selecionada()
        if idx is None:
            messagebox.showinfo("Selecione uma exceção", "Clique numa linha da tabela primeiro.", parent=self)
            return
        if messagebox.askyesno("Remover exceção", "Remover esta exceção de calendário?", parent=self):
            del self.dados.dias_excecao[idx]
            self._atualizar_lista_excecoes()
            self._status("Exceção removida.")


def main() -> None:
    app = Aplicativo()
    app.mainloop()


if __name__ == "__main__":
    main()
