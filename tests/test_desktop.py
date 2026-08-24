"""Testes do app nativo (Tkinter). Pulados automaticamente se tkinter não
estiver disponível (falta o pacote python3-tk no Linux) ou se não houver um
display utilizável (defina DISPLAY, ou rode sob xvfb-run)."""
from __future__ import annotations

from dataclasses import replace

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import filedialog, messagebox  # noqa: E402

from livroponto.models import DiaNaoLetivo, MembroGestao, Pessoa, TipoServidor  # noqa: E402

try:
    _raiz_teste = tk.Tk()
    _raiz_teste.destroy()
except tk.TclError:
    pytest.skip("Sem display utilizável para testes de Tkinter", allow_module_level=True)

from livroponto.desktop.app import Aplicativo  # noqa: E402
from livroponto.desktop.dialogs import DialogoExcecao, DialogoMembroGestao, DialogoPessoa  # noqa: E402


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
    assert app.tree_pessoas is not None
    assert app.tree_excecoes is not None
    assert app.tree_gestao is not None


def test_adicionar_e_remover_pessoa_atualiza_lista(app):
    app.dados.pessoas.append(_pessoa_exemplo())
    app._atualizar_lista_pessoas()
    assert len(app.tree_pessoas.get_children()) == 1

    app.tree_pessoas.selection_set("0")
    idx = app._pessoa_selecionada()
    assert idx == 0
    del app.dados.pessoas[idx]
    app._atualizar_lista_pessoas()
    assert len(app.tree_pessoas.get_children()) == 0


def test_lista_pessoas_ordenada_por_rg(app):
    """A lista mostra os servidores ordenados por RG (mesma ordem das
    folhas no PDF), mas o iid de cada linha continua apontando pro
    índice certo em app.dados.pessoas — editar/remover a primeira linha
    exibida tem que afetar a pessoa certa, não sempre o índice 0."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 30", rg="30"))
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 9", rg="9"))
    app.dados.pessoas.append(_pessoa_exemplo(nome="RG 15", rg="15"))
    app._atualizar_lista_pessoas()

    linhas = app.tree_pessoas.get_children()
    nomes_exibidos = [app.tree_pessoas.item(iid, "values")[1] for iid in linhas]
    assert nomes_exibidos == ["RG 9", "RG 15", "RG 30"]

    # a primeira linha exibida (RG 9) é o índice 1 na lista real
    app.tree_pessoas.selection_set(linhas[0])
    assert app._pessoa_selecionada() == 1
    assert app.dados.pessoas[app._pessoa_selecionada()].nome == "RG 9"


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


def test_checkboxes_incluir_existem_e_comecam_marcados(app):
    assert app.var_incluir_administrativos.get() is True
    assert app.var_incluir_docentes.get() is True


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


def test_dialogo_excecao_novo_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoExcecao(app)
    dlg.var_mes.set("4")
    dlg.var_dia.set("19")
    dlg.var_tipo.set("PONTO_FACULTATIVO")
    dlg.var_descricao.set("Teste")
    dlg._salvar()

    assert dlg.resultado == DiaNaoLetivo(mes=4, dia=19, tipo="PONTO_FACULTATIVO", descricao="Teste")


def test_adicionar_editar_remover_gestor_atualiza_lista(app):
    app.dados.equipe_gestora.append(MembroGestao(nome="Diretora Teste", cargo="Diretor(a) de Escola"))
    app._atualizar_lista_gestao()
    assert len(app.tree_gestao.get_children()) == 1

    app.tree_gestao.selection_set("0")
    idx = app._gestor_selecionado()
    assert idx == 0
    app.dados.equipe_gestora[idx] = MembroGestao(nome="Diretora Editada", cargo="Diretor(a) de Escola")
    app._atualizar_lista_gestao()
    assert app.tree_gestao.item("0", "values")[1] == "Diretora Editada"

    del app.dados.equipe_gestora[idx]
    app._atualizar_lista_gestao()
    assert len(app.tree_gestao.get_children()) == 0


def test_dialogo_membro_gestao_novo_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoMembroGestao(app)
    dlg.var_cargo.set("Diretor(a) de Escola")
    dlg.var_nome.set("Nova Diretora")
    dlg.var_rg.set("9.999.999-9")
    dlg._salvar()

    assert dlg.resultado == MembroGestao(nome="Nova Diretora", cargo="Diretor(a) de Escola", rg="9.999.999-9")


def test_dialogo_membro_gestao_sem_nome_nao_gera_resultado(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())
    monkeypatch.setattr("livroponto.desktop.dialogs.messagebox.showerror", lambda *a, **k: None)

    dlg = DialogoMembroGestao(app)
    dlg._salvar()

    assert dlg.resultado is None
    dlg.destroy()


def test_dialogo_membro_gestao_edicao_preenche_campos_existentes(app, monkeypatch):
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    existente = MembroGestao(nome="Existente", cargo="Vice-Diretor(a) de Escola", rg="1.111.111-1")
    dlg = DialogoMembroGestao(app, existente)

    assert dlg.var_nome.get() == "Existente"
    assert dlg.var_cargo.get() == "Vice-Diretor(a) de Escola"
    assert dlg.var_rg.get() == "1.111.111-1"

    dlg._cancelar()
    assert dlg.resultado is None
