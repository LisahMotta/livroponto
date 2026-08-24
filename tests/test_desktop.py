"""Testes do app nativo (Tkinter). Pulados automaticamente se tkinter não
estiver disponível (falta o pacote python3-tk no Linux) ou se não houver um
display utilizável (defina DISPLAY, ou rode sob xvfb-run)."""
from __future__ import annotations

from dataclasses import replace

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import filedialog, messagebox  # noqa: E402

from livroponto.models import DiaNaoLetivo, Pessoa, TipoServidor  # noqa: E402

try:
    _raiz_teste = tk.Tk()
    _raiz_teste.destroy()
except tk.TclError:
    pytest.skip("Sem display utilizável para testes de Tkinter", allow_module_level=True)

from livroponto.desktop.app import Aplicativo  # noqa: E402
from livroponto.desktop.dialogs import DialogoExcecao, DialogoPessoa  # noqa: E402


@pytest.fixture
def app():
    aplicativo = Aplicativo()
    yield aplicativo
    aplicativo.destroy()


def _pessoa_exemplo(**overrides) -> Pessoa:
    base = dict(
        nome="Fulano Teste",
        tipo=TipoServidor.ADMINISTRATIVO,
        rg="1.111.111-1",
        cargo="Agente de Organização Escolar",
        jornada_semanal=40,
        entrada="07:00",
        saida="16:00",
    )
    base.update(overrides)
    return Pessoa(**base)


def test_janela_abre_com_abas(app):
    assert app.title() == "Livro Ponto — editor"
    assert app.tree_administrativo is not None
    assert app.tree_gestao is not None
    assert app.tree_excecoes is not None


def test_adicionar_e_remover_pessoa_atualiza_lista(app):
    app.dados.pessoas.append(_pessoa_exemplo())
    app._atualizar_listas_pessoas()
    assert len(app.tree_administrativo.get_children()) == 1

    app.tree_administrativo.selection_set("0")
    idx = app._pessoa_selecionada_tipo(TipoServidor.ADMINISTRATIVO)
    assert idx == 0
    del app.dados.pessoas[idx]
    app._atualizar_listas_pessoas()
    assert len(app.tree_administrativo.get_children()) == 0


def test_lista_pessoas_mostra_coluna_de_observacoes(app):
    """A observação cadastrada tem que aparecer direto na lista da aba,
    sem precisar abrir o diálogo de editar pra ver."""
    app.dados.pessoas.append(_pessoa_exemplo(observacoes="Afastada por licença médica"))
    app._atualizar_listas_pessoas()

    valores = app.tree_administrativo.item("0", "values")
    assert valores[-1] == "Afastada por licença médica"


def test_abas_administrativo_e_gestao_sao_separadas(app):
    """Cada aba mostra só o tipo dela — Administrativo não mostra gente
    da Gestão, e vice-versa. Não existe mais uma aba única misturando
    tudo (nem uma aba de Docentes)."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.dados.pessoas.append(
        _pessoa_exemplo(nome="Diretora Teste", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    )
    app.dados.pessoas.append(_pessoa_exemplo(nome="Docente Teste", tipo=TipoServidor.DOCENTE))
    app._atualizar_listas_pessoas()

    nomes_admin = [app.tree_administrativo.item(iid, "values")[0] for iid in app.tree_administrativo.get_children()]
    nomes_gestao = [app.tree_gestao.item(iid, "values")[0] for iid in app.tree_gestao.get_children()]
    assert nomes_admin == ["Administrativo Teste"]
    assert nomes_gestao == ["Diretora Teste"]
    assert not hasattr(app, "tree_docente")


def test_lista_pessoas_ordenada_por_rg(app):
    """A lista mostra os servidores ordenados por RG (mesma ordem das
    folhas no PDF), mas o iid de cada linha continua apontando pro
    índice certo em app.dados.pessoas — editar/remover a primeira linha
    exibida tem que afetar a pessoa certa, não sempre o índice 0."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 30", rg="30"))
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 9", rg="9"))
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 15", rg="15"))
    app._atualizar_listas_pessoas()

    linhas = app.tree_administrativo.get_children()
    nomes_exibidos = [app.tree_administrativo.item(iid, "values")[0] for iid in linhas]
    assert nomes_exibidos == ["RG 9", "RG 15", "RG 30"]

    # a primeira linha exibida (RG 9) é o índice 1 na lista real
    app.tree_administrativo.selection_set(linhas[0])
    idx = app._pessoa_selecionada_tipo(TipoServidor.ADMINISTRATIVO)
    assert idx == 1
    assert app.dados.pessoas[idx].nome == "RG 9"


def test_editar_pessoa_muda_tipo_move_para_outra_aba(app):
    """Editar um administrativo e trocar o Tipo pra GESTAO no diálogo tem
    que sumir da aba Administrativo e aparecer na aba Gestão."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Vai Virar Gestor"))
    app._atualizar_listas_pessoas()
    app.tree_administrativo.selection_set("0")

    app.dados.pessoas[0] = replace(app.dados.pessoas[0], tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    app._atualizar_listas_pessoas()

    assert len(app.tree_administrativo.get_children()) == 0
    nomes_gestao = [app.tree_gestao.item(iid, "values")[0] for iid in app.tree_gestao.get_children()]
    assert nomes_gestao == ["Vai Virar Gestor"]


def test_adicionar_excecao_atualiza_lista(app):
    app.dados.dias_excecao.append(DiaNaoLetivo(mes=4, dia=19, tipo="PONTO_FACULTATIVO", descricao="Teste"))
    app._atualizar_lista_excecoes()
    assert len(app.tree_excecoes.get_children()) == 1


def test_sincronizar_escola_le_campos_para_o_modelo(app):
    app.var_nome.set("EE Exemplo Fictício")
    app.var_municipio.set("Cidade Exemplo")
    app.var_mes.set("Abril")
    app.var_ano.set("2026")
    app.var_uf.set("SP")

    app._sincronizar_escola()

    assert app.dados.escola.nome == "EE Exemplo Fictício"
    assert app.dados.escola.municipio == "Cidade Exemplo"
    assert app.dados.mes == 4
    assert app.dados.ano == 2026
    assert app.dados.uf == "SP"


def test_salvar_e_reabrir_cadastro_xlsx(app, tmp_path):
    app.dados.pessoas.append(_pessoa_exemplo())
    app.dados.pessoas.append(_pessoa_exemplo(nome="Ciclana Teste", tipo=TipoServidor.DOCENTE, disciplinas="HISTÓRIA"))
    app.var_nome.set("EE Exemplo Fictício")
    app._sincronizar_escola()

    from livroponto.readers.template_reader import ler_modelo, salvar_modelo

    caminho = tmp_path / "cadastro.xlsx"
    salvar_modelo(app.dados, caminho)
    recarregado = ler_modelo(caminho)
    assert recarregado.escola.nome == "EE Exemplo Fictício"
    assert len(recarregado.pessoas) == 2


def test_gerar_pdf_a_partir_dos_dados_da_janela(app, tmp_path):
    app.dados.pessoas.append(_pessoa_exemplo())
    app.var_nome.set("EE Exemplo Fictício")
    app._sincronizar_escola()

    from livroponto.pdf.builder import gerar_pdf

    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(app.dados, caminho)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000


def test_gerar_pdf_pelo_botao_respeita_filtro_incluir(app, tmp_path, monkeypatch):
    """Desmarcar "Docentes" em Incluir não deve gerar a folha do docente,
    mesmo com ele cadastrado e com ponto=True."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.dados.pessoas.append(
        _pessoa_exemplo(
            nome="Docente Teste",
            tipo=TipoServidor.DOCENTE,
            disciplinas="MATEMÁTICA",
            entrada="",
            saida="",
        )
    )
    app.var_nome.set("EE Exemplo Fictício")
    app.var_incluir_docentes.set(False)

    caminho = tmp_path / "livro_ponto.pdf"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(caminho))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_pdf()

    assert caminho.exists()
    texto = caminho.read_bytes()
    assert b"Administrativo Teste" not in texto  # texto do PDF vai comprimido/codificado
    # confirma via reportlab: reabrir o config filtrado teria só 1 pessoa
    from livroponto.pdf.builder import gerar_pdf as gerar_pdf_direto

    config_admin_only = replace(
        app.dados, pessoas=[p for p in app.dados.pessoas if p.tipo == TipoServidor.ADMINISTRATIVO]
    )
    caminho_referencia = tmp_path / "referencia.pdf"
    gerar_pdf_direto(config_admin_only, caminho_referencia)
    # o PDF gerado pelo botão deve ter tamanho parecido ao gerado só com o
    # administrativo (bem menor do que se tivesse incluído o docente também)
    assert abs(caminho.stat().st_size - caminho_referencia.stat().st_size) < 500


def test_gerar_pdf_sugere_nome_de_arquivo_pelo_tipo_incluido(app, tmp_path, monkeypatch):
    """O nome sugerido no "Salvar como" identifica o livro que está
    sendo gerado — evita salvar por cima do livro de outro tipo sem
    perceber."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.dados.pessoas.append(
        _pessoa_exemplo(nome="Diretora Teste", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    )
    app.var_nome.set("EE Exemplo Fictício")
    app.var_incluir_docentes.set(False)
    app.var_incluir_gestao.set(False)

    nomes_sugeridos = []

    def _fake_asksaveasfilename(**kw):
        nomes_sugeridos.append(kw.get("initialfile"))
        return str(tmp_path / "saida.pdf")

    monkeypatch.setattr(filedialog, "asksaveasfilename", _fake_asksaveasfilename)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_pdf()
    assert nomes_sugeridos[-1].startswith("livro_ponto_administrativo_")

    app.var_incluir_administrativos.set(False)
    app.var_incluir_gestao.set(True)
    app._gerar_pdf()
    assert nomes_sugeridos[-1].startswith("livro_ponto_gestao_")


def test_gerar_pdf_sem_gestao_ainda_leva_diretor_pro_gerar_pdf(app, monkeypatch):
    """Bug real reportado pelo usuário: desmarcar "Trio gestor" em
    "Incluir" não pode fazer o(a) Diretor(a) de Escola cadastrado na
    Gestão sumir do cadastro passado pra gerar_pdf — senão o termo do
    livro administrativo perde a assinatura automática. O app não filtra
    mais app.dados.pessoas por tipo antes de chamar gerar_pdf; quem
    decide quais livros ganham folhas é o parâmetro tipos_incluidos."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.dados.pessoas.append(
        _pessoa_exemplo(nome="Diretora Teste", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    )
    app.var_nome.set("EE Exemplo Fictício")
    app.var_incluir_gestao.set(False)

    chamadas = []

    def _gerar_pdf_espiao(config, caminho, **kwargs):
        chamadas.append((config, kwargs.get("tipos_incluidos")))
        return caminho

    import livroponto.desktop.app as app_mod

    monkeypatch.setattr(app_mod, "gerar_pdf", _gerar_pdf_espiao)
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: "saida.pdf")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_pdf()

    assert len(chamadas) == 1
    config_recebido, tipos_incluidos = chamadas[0]
    assert config_recebido.nome_diretor() == "Diretora Teste"
    assert TipoServidor.GESTAO not in tipos_incluidos
    assert TipoServidor.ADMINISTRATIVO in tipos_incluidos


def test_checkboxes_incluir_existem_e_comecam_marcados(app):
    assert app.var_incluir_administrativos.get() is True
    assert app.var_incluir_docentes.get() is True
    assert app.var_incluir_gestao.get() is True


def test_gerar_pdf_pelo_botao_inclui_trio_gestor(app, tmp_path, monkeypatch):
    """O botão "Gerar Livro Ponto" também gera a folha do trio gestor
    quando há gente cadastrada com tipo GESTAO e "Trio gestor" marcado
    em Incluir."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.dados.pessoas.append(
        _pessoa_exemplo(nome="Diretora Teste", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    )
    app.var_nome.set("EE Exemplo Fictício")

    caminho = tmp_path / "livro_ponto.pdf"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(caminho))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_pdf()

    assert caminho.exists()
    assert caminho.stat().st_size > 1000


def test_dialogo_pessoa_novo_preenchido_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    dlg.var_nome.set("Novo Servidor")
    dlg.var_rg.set("9.999.999-9")
    dlg.var_jornada.set("40")
    dlg._salvar()

    assert dlg.resultado is not None
    assert dlg.resultado.nome == "Novo Servidor"
    assert dlg.resultado.jornada_semanal == 40.0


def test_dialogo_pessoa_sem_nome_nao_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())
    monkeypatch.setattr("livroponto.desktop.dialogs.messagebox.showerror", lambda *a, **k: None)

    dlg = DialogoPessoa(app)
    dlg._salvar()

    assert dlg.resultado is None
    dlg.destroy()


def test_dialogo_pessoa_edicao_preenche_campos_existentes(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    existente = _pessoa_exemplo(tipo=TipoServidor.DOCENTE, disciplinas="HISTÓRIA", nome="Existente")
    dlg = DialogoPessoa(app, existente)

    assert dlg.var_nome.get() == "Existente"
    assert dlg.var_disciplinas.get() == "HISTÓRIA"

    dlg._cancelar()
    assert dlg.resultado is None


def test_dialogo_pessoa_periodo_de_ferias_vai_pro_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    dlg.var_nome.set("Servidor Com Férias")
    dlg.var_ferias_inicio.set("03/04/2026")
    dlg.var_ferias_fim.set("02/05/2026")
    dlg._salvar()

    assert dlg.resultado.ferias_inicio == "03/04/2026"
    assert dlg.resultado.ferias_fim == "02/05/2026"
    assert dlg.resultado.periodo_ferias == "03/04/2026 a 02/05/2026"


def test_dialogo_pessoa_tipo_gestao_com_jornada_e_horario(app, monkeypatch):
    """O trio gestor cadastra jornada semanal e horário de entrada/saída
    do mesmo jeito que o administrativo — mesmos campos do formulário,
    só muda o Tipo."""
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    dlg.var_tipo.set("GESTAO")
    dlg.var_nome.set("Diretora Teste")
    dlg.var_cargo.set("Diretor(a) de Escola")
    dlg.var_jornada.set("40")
    dlg.var_entrada.set("07:00")
    dlg.var_saida.set("16:00")
    dlg._salvar()

    assert dlg.resultado.tipo == TipoServidor.GESTAO
    assert dlg.resultado.cargo == "Diretor(a) de Escola"
    assert dlg.resultado.jornada_semanal == 40.0
    assert dlg.resultado.entrada == "07:00"
    assert dlg.resultado.saida == "16:00"
    assert dlg.resultado.horario_trabalho == "DAS 07:00 ÀS 16:00"


def test_botao_adicionar_da_aba_gestao_abre_dialogo_ja_no_tipo_gestao(app, monkeypatch):
    """O botão Adicionar da aba Gestão pré-seleciona Tipo=GESTAO no
    diálogo (e o da aba Administrativo, Tipo=ADMINISTRATIVO) — não
    precisa trocar manualmente toda vez."""
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    capturado = {}

    class DialogoPessoaEspiao(DialogoPessoa):
        def __init__(self, parent, pessoa=None, tipo_inicial=None):
            capturado["tipo_inicial"] = tipo_inicial
            super().__init__(parent, pessoa, tipo_inicial)
            self._cancelar()

    monkeypatch.setattr("livroponto.desktop.app.DialogoPessoa", DialogoPessoaEspiao)
    app._adicionar_pessoa_tipo(TipoServidor.GESTAO)

    assert capturado["tipo_inicial"] == TipoServidor.GESTAO


def test_dialogo_excecao_novo_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoExcecao(app)
    dlg.var_mes.set("4")
    dlg.var_dia.set("19")
    dlg.var_tipo.set("PONTO_FACULTATIVO")
    dlg.var_descricao.set("Teste")
    dlg._salvar()

    assert dlg.resultado == DiaNaoLetivo(mes=4, dia=19, tipo="PONTO_FACULTATIVO", descricao="Teste")
