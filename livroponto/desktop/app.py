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
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from ..calendario import nome_mes
from ..models import Escola, LivroPontoConfig, TipoServidor, chave_ordenacao_rg, formatar_rg
from ..pdf.builder import gerar_pdf, gerar_termos_pdf
from ..readers.template_reader import ler_modelo, salvar_modelo
from ..readers.xlsb_reader import ler_livro_ponto
from .dialogs import DialogoExcecao, DialogoFerias, DialogoLicenca, DialogoPessoa

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


def _observacoes_exibicao(pessoa) -> str:
    """Texto mostrado na coluna Observações do cadastro: junta a
    observação livre com um resumo das licenças lançadas na aba Licenças
    (independente de estarem em vigor agora — isso só importa na hora de
    imprimir a consolidação)."""
    partes = []
    if pessoa.observacoes:
        partes.append(pessoa.observacoes)
    for licenca in pessoa.licencas:
        if licenca.periodo:
            partes.append(f"{licenca.rotulo}: {licenca.periodo}")
    return " | ".join(partes)


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
        self._indices_combo_licenca: list[int] = []

        self._construir_barra_ferramentas()
        self._construir_abas()
        self._construir_barra_status()

        self._atualizar_tudo()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _construir_barra_ferramentas(self) -> None:
        barra_arquivo = ttk.Frame(self, padding=(8, 8, 8, 4))
        barra_arquivo.pack(fill="x")
        ttk.Button(barra_arquivo, text="Novo", command=self._novo, bootstyle="secondary-outline").pack(
            side="left"
        )
        ttk.Button(
            barra_arquivo, text="Abrir...", command=self._abrir, bootstyle="secondary-outline"
        ).pack(side="left", padx=6)
        ttk.Button(
            barra_arquivo, text="Salvar cadastro...", command=self._salvar_cadastro, bootstyle="secondary-outline"
        ).pack(side="left")

        barra_gerar = ttk.Frame(self, padding=(8, 0, 8, 4))
        barra_gerar.pack(fill="x")
        ttk.Button(
            barra_gerar, text="🖨️ Gerar Livro Ponto (PDF)...", command=self._gerar_pdf, bootstyle="success"
        ).pack(side="left")

        ttk.Label(barra_gerar, text="Imprimir:").pack(side="left", padx=(12, 2))
        self.var_imprimir_folha = tk.BooleanVar(value=True)
        self.var_imprimir_consolidacao = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            barra_gerar, text="Folha", variable=self.var_imprimir_folha, bootstyle="round-toggle"
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            barra_gerar,
            text="Consolidação (verso)",
            variable=self.var_imprimir_consolidacao,
            bootstyle="round-toggle",
        ).pack(side="left")

        # Linha própria pra "Incluir" (em vez de dividir a mesma linha com
        # "Imprimir") — evita que o texto dos toggles seja cortado em
        # janelas mais estreitas.
        barra_incluir = ttk.Frame(self, padding=(8, 0, 8, 4))
        barra_incluir.pack(fill="x")
        ttk.Label(barra_incluir, text="Incluir:").pack(side="left", padx=(0, 2))
        self.var_incluir_administrativos = tk.BooleanVar(value=True)
        self.var_incluir_docentes = tk.BooleanVar(value=True)
        self.var_incluir_gestao = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            barra_incluir,
            text="Administrativos",
            variable=self.var_incluir_administrativos,
            bootstyle="round-toggle",
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            barra_incluir, text="Docentes", variable=self.var_incluir_docentes, bootstyle="round-toggle"
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            barra_incluir, text="Trio gestor", variable=self.var_incluir_gestao, bootstyle="round-toggle"
        ).pack(side="left")

        ttk.Label(
            self,
            text=(
                "Gera só as folhas de ponto/frequência, frente e verso — desmarque "
                "Folha ou Consolidação pra imprimir cada lado em uma passada "
                "separada na impressora. Os termos de abertura/encerramento têm "
                "aba própria (Termos)."
            ),
            wraplength=920,
            foreground="grey",
        ).pack(fill="x", padx=8, pady=(0, 4))

    def _construir_abas(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        aba_escola = ttk.Frame(notebook, padding=12)
        aba_administrativo = ttk.Frame(notebook)
        aba_gestao = ttk.Frame(notebook)
        aba_excecoes = ttk.Frame(notebook)
        aba_ferias = ttk.Frame(notebook, padding=12)
        aba_licencas = ttk.Frame(notebook, padding=12)
        aba_termos = ttk.Frame(notebook, padding=12)
        notebook.add(aba_escola, text="Escola")
        notebook.add(aba_administrativo, text="Administrativo")
        notebook.add(aba_gestao, text="Gestão")
        notebook.add(aba_excecoes, text="Feriados e exceções")
        notebook.add(aba_ferias, text="Férias")
        notebook.add(aba_licencas, text="Licenças")
        notebook.add(aba_termos, text="Termos")

        self._construir_aba_escola(aba_escola)
        self.tree_administrativo = self._construir_aba_pessoas_tipo(aba_administrativo, TipoServidor.ADMINISTRATIVO)
        self.tree_gestao = self._construir_aba_pessoas_tipo(aba_gestao, TipoServidor.GESTAO)
        self._construir_aba_excecoes(aba_excecoes)
        self._construir_aba_ferias(aba_ferias)
        self._construir_aba_licencas(aba_licencas)
        self._construir_aba_termos(aba_termos)

    def _construir_aba_escola(self, aba: ttk.Frame) -> None:
        aba.columnconfigure(1, weight=1)
        aba.columnconfigure(3, weight=1)

        # Rótulo alinhado à direita (encostado no campo) — a coluna do
        # rótulo é larga o bastante pra caber o texto mais comprido
        # ("Rótulo da assinatura (padrão: ...)"), então com o rótulo
        # alinhado à esquerda os campos mais curtos ("Nome da escola" etc.)
        # ficavam com um vão enorme entre o texto e a caixa.
        def campo(r: int, c: int, rotulo: str, largura: int = 34) -> tk.StringVar:
            ttk.Label(aba, text=rotulo).grid(row=r, column=c, sticky="e", padx=(0, 8), pady=4)
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

        ttk.Label(aba, text="Mês").grid(row=7, column=0, sticky="e", padx=(0, 8), pady=4)
        self.var_mes = tk.StringVar(value=MESES_CAP[0])
        ttk.Combobox(
            aba, textvariable=self.var_mes, values=MESES_CAP, state="readonly", width=14
        ).grid(row=7, column=1, sticky="w", pady=4)

        ttk.Label(aba, text="Ano").grid(row=7, column=2, sticky="e", padx=(12, 8), pady=4)
        self.var_ano = tk.StringVar()
        ttk.Spinbox(aba, from_=2000, to=2100, textvariable=self.var_ano, width=8).grid(
            row=7, column=3, sticky="w", pady=4
        )

        self.var_uf = campo(8, 0, "UF (feriados)", 6)
        self.var_cidade = campo(8, 2, "Cidade (assinatura dos termos)", 24)

        self.var_diretor = campo(9, 0, "Nome do Diretor(a) (assinatura dos termos)", 60)
        aba.grid_slaves(row=9, column=1)[0].grid(columnspan=3, sticky="we")

        self.var_rotulo_assinatura = campo(
            10, 0, "Rótulo da assinatura (padrão: Direção da Unidade Escolar)", 60
        )
        aba.grid_slaves(row=10, column=1)[0].grid(columnspan=3, sticky="we")
        ttk.Label(
            aba,
            text="(deixe em branco para escola; use algo como \"Dirigente Regional de Ensino\" pra uma URE)",
            foreground="grey",
        ).grid(row=11, column=0, columnspan=4, sticky="w")

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
            barra, text="(duplo-clique numa linha também edita)", foreground="grey"
        ).pack(side="left", padx=(8, 0))

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

    def _construir_aba_ferias(self, aba: ttk.Frame) -> None:
        """Período de férias de cada servidor, numa aba própria — não
        aparece mais no diálogo de Adicionar/Editar servidor. Preenche o
        campo FÉRIAS do rodapé da folha de ponto e a anotação "Férias
        Regulares" no verso."""
        aviso = (
            "Selecione um servidor e clique em Editar (ou dê duplo-clique) para "
            "preencher o período de férias — puxa direto para o campo FÉRIAS da "
            "folha de ponto e para a anotação no verso."
        )
        ttk.Label(aba, text=aviso, wraplength=920, foreground="grey").pack(fill="x", pady=(0, 8))

        barra = ttk.Frame(aba)
        barra.pack(fill="x", pady=(0, 4))
        ttk.Button(
            barra, text="Editar período de férias", command=self._editar_ferias_selecionada, bootstyle="primary"
        ).pack(side="left")
        ttk.Label(barra, text="(duplo-clique numa linha também edita)", foreground="grey").pack(
            side="left", padx=(8, 0)
        )

        colunas = ("nome", "tipo", "rg", "ferias_inicio", "ferias_fim")
        titulos = {
            "nome": "Nome",
            "tipo": "Tipo",
            "rg": "RG",
            "ferias_inicio": "Férias de",
            "ferias_fim": "Férias até",
        }
        larguras = {"nome": 280, "tipo": 130, "rg": 110, "ferias_inicio": 110, "ferias_fim": 110}

        container = ttk.Frame(aba)
        container.pack(fill="both", expand=True, pady=(4, 0))
        self.tree_ferias = ttk.Treeview(container, columns=colunas, show="headings", selectmode="browse")
        for c in colunas:
            self.tree_ferias.heading(c, text=titulos[c])
            self.tree_ferias.column(c, width=larguras[c], anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_ferias.yview)
        self.tree_ferias.configure(yscrollcommand=scroll.set)
        self.tree_ferias.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree_ferias.bind("<Double-1>", lambda _e: self._editar_ferias_selecionada())

    def _construir_aba_licencas(self, aba: ttk.Frame) -> None:
        """Períodos de licença saúde/prêmio de cada servidor — um servidor
        pode ter vários ao longo do tempo. Aparecem no campo Observações
        do cadastro; só entram na folha de consolidação se ainda
        estiverem em vigor no mês do livro sendo gerado."""
        aviso = (
            "Escolha um servidor e clique em \"Adicionar licença\" para lançar um período "
            "de licença saúde ou prêmio. Aparece no campo Observações do cadastro; só sai "
            "impresso na folha de consolidação se ainda estiver em vigor no mês do livro "
            "sendo gerado."
        )
        ttk.Label(aba, text=aviso, wraplength=920, foreground="grey").pack(fill="x", pady=(0, 8))

        linha_servidor = ttk.Frame(aba)
        linha_servidor.pack(fill="x", pady=(0, 8))
        ttk.Label(linha_servidor, text="Servidor:").pack(side="left", padx=(0, 8))
        self.var_licenca_servidor = tk.StringVar()
        self.combo_licenca_servidor = ttk.Combobox(
            linha_servidor, textvariable=self.var_licenca_servidor, state="readonly", width=50
        )
        self.combo_licenca_servidor.pack(side="left", padx=(0, 8))
        ttk.Button(
            linha_servidor, text="Adicionar licença", command=self._adicionar_licenca, bootstyle="primary"
        ).pack(side="left")

        barra = ttk.Frame(aba)
        barra.pack(fill="x", pady=(0, 4))
        ttk.Button(
            barra, text="Editar", command=self._editar_licenca_selecionada, bootstyle="info-outline"
        ).pack(side="left")
        ttk.Button(
            barra, text="Remover", command=self._remover_licenca_selecionada, bootstyle="danger-outline"
        ).pack(side="left", padx=6)
        ttk.Label(barra, text="(duplo-clique numa linha também edita)", foreground="grey").pack(
            side="left", padx=(8, 0)
        )

        colunas = ("nome", "tipo", "inicio", "fim")
        titulos = {"nome": "Nome", "tipo": "Tipo", "inicio": "De", "fim": "Até"}
        larguras = {"nome": 280, "tipo": 150, "inicio": 110, "fim": 110}

        container = ttk.Frame(aba)
        container.pack(fill="both", expand=True, pady=(4, 0))
        self.tree_licencas = ttk.Treeview(container, columns=colunas, show="headings", selectmode="browse")
        for c in colunas:
            self.tree_licencas.heading(c, text=titulos[c])
            self.tree_licencas.column(c, width=larguras[c], anchor="w")
        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree_licencas.yview)
        self.tree_licencas.configure(yscrollcommand=scroll.set)
        self.tree_licencas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree_licencas.bind("<Double-1>", lambda _e: self._editar_licenca_selecionada())

    def _construir_aba_termos(self, aba: ttk.Frame) -> None:
        """Aba pra imprimir só os termos de abertura e encerramento (sem
        as folhas de ponto de cada servidor) — útil pra reimprimir/trocar
        o termo de um mês específico, escolhendo o mês/ano e o(s) tipo(s)
        de livro na hora, sem depender do mês configurado na aba Escola."""
        aviso = (
            "Gera só as duas páginas do termo (abertura e encerramento) do mês e "
            "tipo de livro escolhidos aqui — sem as folhas de ponto de cada "
            "servidor. Útil pra reimprimir um termo avulso."
        )
        ttk.Label(aba, text=aviso, wraplength=920, foreground="grey").pack(fill="x", pady=(0, 12))

        linha_mes = ttk.Frame(aba)
        linha_mes.pack(fill="x", pady=(0, 8))
        ttk.Label(linha_mes, text="Mês").pack(side="left", padx=(0, 8))
        self.var_termo_mes = tk.StringVar(value=MESES_CAP[self.dados.mes - 1])
        ttk.Combobox(
            linha_mes, textvariable=self.var_termo_mes, values=MESES_CAP, state="readonly", width=14
        ).pack(side="left")
        ttk.Label(linha_mes, text="Ano").pack(side="left", padx=(16, 8))
        self.var_termo_ano = tk.StringVar(value=str(self.dados.ano))
        ttk.Spinbox(linha_mes, from_=2000, to=2100, textvariable=self.var_termo_ano, width=8).pack(side="left")

        linha_tipos = ttk.Frame(aba)
        linha_tipos.pack(fill="x", pady=(0, 12))
        ttk.Label(linha_tipos, text="Livro:").pack(side="left", padx=(0, 8))
        self.var_termo_administrativo = tk.BooleanVar(value=True)
        self.var_termo_gestao = tk.BooleanVar(value=False)
        self.var_termo_docente = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            linha_tipos, text="Administrativo", variable=self.var_termo_administrativo, bootstyle="round-toggle"
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            linha_tipos, text="Trio gestor", variable=self.var_termo_gestao, bootstyle="round-toggle"
        ).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(
            linha_tipos, text="Docentes", variable=self.var_termo_docente, bootstyle="round-toggle"
        ).pack(side="left")

        ttk.Button(
            aba, text="🖨️ Gerar Termos (PDF)...", command=self._gerar_termos, bootstyle="success"
        ).pack(anchor="w")

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
        self.var_diretor.set(self.dados.diretor_nome)
        self.var_rotulo_assinatura.set(self.dados.rotulo_assinatura)

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
        self.dados.diretor_nome = self.var_diretor.get().strip()
        self.dados.rotulo_assinatura = self.var_rotulo_assinatura.get().strip()

    def _atualizar_tudo(self) -> None:
        self._atualizar_campos_escola()
        self._atualizar_listas_pessoas()  # também recarrega Férias e Licenças
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

        if not any(p.ponto for p in self.dados.pessoas if p.tipo in tipos_incluidos):
            messagebox.showwarning(
                "Nada para gerar",
                "Adicione ao menos um servidor (do(s) tipo(s) marcado(s) em \"Incluir\") "
                "com \"Ponto?\" marcado.",
                parent=self,
            )
            return

        imprimir_folha = self.var_imprimir_folha.get()
        imprimir_consolidacao = self.var_imprimir_consolidacao.get()
        if not imprimir_folha and not imprimir_consolidacao:
            messagebox.showwarning(
                "Nada para gerar",
                "Marque ao menos um em \"Imprimir\": Folha e/ou Consolidação (verso).",
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
            # O botão "Gerar Livro Ponto" não inclui mais os termos de
            # abertura/encerramento — eles têm aba própria (Termos). Folha
            # e Consolidação são opcionais, pra imprimir frente e verso em
            # duas passadas separadas na impressora.
            gerar_pdf(
                self.dados,
                caminho,
                tipos_incluidos=tipos_incluidos,
                incluir_termos=False,
                imprimir_folha=imprimir_folha,
                imprimir_consolidacao=imprimir_consolidacao,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao gerar PDF", str(exc), parent=self)
            return
        self._status(f"PDF gerado em {caminho}")
        if messagebox.askyesno("PDF gerado", f"Gerado em:\n{caminho}\n\nAbrir agora?", parent=self):
            _abrir_no_sistema(caminho)

    def _gerar_termos(self) -> None:
        self._sincronizar_escola()

        tipos_incluidos = set()
        if self.var_termo_administrativo.get():
            tipos_incluidos.add(TipoServidor.ADMINISTRATIVO)
        if self.var_termo_gestao.get():
            tipos_incluidos.add(TipoServidor.GESTAO)
        if self.var_termo_docente.get():
            tipos_incluidos.add(TipoServidor.DOCENTE)
        if not tipos_incluidos:
            messagebox.showwarning(
                "Nada para gerar",
                "Marque ao menos um livro: Administrativo, Trio gestor e/ou Docentes.",
                parent=self,
            )
            return

        if self.var_termo_mes.get() not in MESES_CAP:
            messagebox.showwarning("Mês inválido", "Escolha um mês da lista.", parent=self)
            return
        mes = MESES_CAP.index(self.var_termo_mes.get()) + 1
        try:
            ano = int(self.var_termo_ano.get())
        except ValueError:
            messagebox.showerror("Ano inválido", "O ano deve ser um número.", parent=self)
            return

        sufixo = "_".join(s for t, s in _SUFIXO_ARQUIVO_TIPO if t in tipos_incluidos)
        base = f"termos_{sufixo}" if sufixo else "termos"
        nome_sugerido = f"{base}_{mes:02d}_{ano}.pdf"
        caminho = filedialog.asksaveasfilename(
            title="Gerar Termos",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=nome_sugerido,
        )
        if not caminho:
            return
        try:
            gerar_termos_pdf(self.dados, caminho, tipos_incluidos, mes, ano)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao gerar PDF", str(exc), parent=self)
            return
        self._status(f"Termos gerados em {caminho}")
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
                values=(
                    p.nome,
                    formatar_rg(p.rg),
                    p.cargo,
                    jornada,
                    "Sim" if p.ponto else "Não",
                    _observacoes_exibicao(p),
                ),
            )

    def _atualizar_listas_pessoas(self) -> None:
        self._atualizar_lista_pessoas_tipo(TipoServidor.ADMINISTRATIVO)
        self._atualizar_lista_pessoas_tipo(TipoServidor.GESTAO)
        # Férias e Licenças listam todo mundo (qualquer tipo) — precisam
        # recarregar sempre que o cadastro de servidores mudar (adicionar,
        # editar, remover), senão um servidor recém-cadastrado não aparece
        # lá até fechar e reabrir o app.
        self._atualizar_lista_ferias()
        self._atualizar_lista_licencas()

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

    # ------------------------------------------------------------------
    # Aba Férias
    # ------------------------------------------------------------------
    def _atualizar_lista_ferias(self) -> None:
        tree = self.tree_ferias
        tree.delete(*tree.get_children())
        itens = sorted(enumerate(self.dados.pessoas), key=lambda item: chave_ordenacao_rg(item[1]))
        for i, p in itens:
            tree.insert(
                "",
                "end",
                iid=str(i),
                values=(p.nome, p.tipo.value, formatar_rg(p.rg), p.ferias_inicio, p.ferias_fim),
            )

    def _pessoa_selecionada_ferias(self) -> int | None:
        sel = self.tree_ferias.selection()
        return int(sel[0]) if sel else None

    def _editar_ferias_selecionada(self) -> None:
        idx = self._pessoa_selecionada_ferias()
        if idx is None:
            messagebox.showinfo("Selecione um servidor", "Clique numa linha da tabela primeiro.", parent=self)
            return
        dlg = DialogoFerias(self, self.dados.pessoas[idx])
        if dlg.resultado is not None:
            ferias_inicio, ferias_fim = dlg.resultado
            self.dados.pessoas[idx].ferias_inicio = ferias_inicio
            self.dados.pessoas[idx].ferias_fim = ferias_fim
            self._atualizar_lista_ferias()
            self._status("Período de férias atualizado.")

    # ------------------------------------------------------------------
    # Aba Licenças
    # ------------------------------------------------------------------
    def _atualizar_lista_licencas(self) -> None:
        pessoas_ordenadas = sorted(enumerate(self.dados.pessoas), key=lambda item: chave_ordenacao_rg(item[1]))
        self.combo_licenca_servidor.configure(
            values=[f"{p.nome} — {formatar_rg(p.rg)}" if p.rg else p.nome for _, p in pessoas_ordenadas]
        )
        self._indices_combo_licenca = [i for i, _ in pessoas_ordenadas]
        if self._indices_combo_licenca and self.combo_licenca_servidor.current() == -1:
            self.combo_licenca_servidor.current(0)

        tree = self.tree_licencas
        tree.delete(*tree.get_children())
        for i, p in pessoas_ordenadas:
            for j, lic in enumerate(p.licencas):
                tree.insert("", "end", iid=f"{i}:{j}", values=(p.nome, lic.rotulo, lic.inicio, lic.fim))

    def _pessoa_selecionada_no_combo_licenca(self) -> int | None:
        pos = self.combo_licenca_servidor.current()
        if pos < 0 or pos >= len(self._indices_combo_licenca):
            return None
        return self._indices_combo_licenca[pos]

    def _licenca_selecionada(self) -> tuple[int, int] | None:
        sel = self.tree_licencas.selection()
        if not sel:
            return None
        pessoa_idx, lic_idx = sel[0].split(":")
        return int(pessoa_idx), int(lic_idx)

    def _adicionar_licenca(self) -> None:
        idx = self._pessoa_selecionada_no_combo_licenca()
        if idx is None:
            messagebox.showinfo(
                "Selecione um servidor", "Escolha um servidor na lista antes de adicionar.", parent=self
            )
            return
        dlg = DialogoLicenca(self, self.dados.pessoas[idx])
        if dlg.resultado is not None:
            self.dados.pessoas[idx].licencas.append(dlg.resultado)
            self._atualizar_lista_licencas()
            self._atualizar_listas_pessoas()
            self._status("Licença adicionada.")

    def _editar_licenca_selecionada(self) -> None:
        sel = self._licenca_selecionada()
        if sel is None:
            messagebox.showinfo("Selecione uma licença", "Clique numa linha da tabela primeiro.", parent=self)
            return
        pessoa_idx, lic_idx = sel
        pessoa = self.dados.pessoas[pessoa_idx]
        dlg = DialogoLicenca(self, pessoa, pessoa.licencas[lic_idx])
        if dlg.resultado is not None:
            pessoa.licencas[lic_idx] = dlg.resultado
            self._atualizar_lista_licencas()
            self._atualizar_listas_pessoas()
            self._status("Licença atualizada.")

    def _remover_licenca_selecionada(self) -> None:
        sel = self._licenca_selecionada()
        if sel is None:
            messagebox.showinfo("Selecione uma licença", "Clique numa linha da tabela primeiro.", parent=self)
            return
        pessoa_idx, lic_idx = sel
        pessoa = self.dados.pessoas[pessoa_idx]
        if messagebox.askyesno("Remover licença", f"Remover essa licença de {pessoa.nome}?", parent=self):
            del pessoa.licencas[lic_idx]
            self._atualizar_lista_licencas()
            self._atualizar_listas_pessoas()
            self._status("Licença removida.")


def main() -> None:
    app = Aplicativo()
    app.mainloop()


if __name__ == "__main__":
    main()
