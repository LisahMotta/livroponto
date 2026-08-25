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
    assert app.tree_ferias is not None
    assert app.tree_licencas is not None


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


def test_rotulo_de_assinatura_sincroniza_com_o_modelo(app):
    """Campo pra preparar o livro pro uso numa URE — em branco (padrão de
    escola) ou preenchido (ex.: "Dirigente Regional de Ensino")."""
    app.var_rotulo_assinatura.set("Dirigente Regional de Ensino")
    app._sincronizar_escola()
    assert app.dados.rotulo_assinatura == "Dirigente Regional de Ensino"

    app.dados.rotulo_assinatura = "Outro Rótulo"
    app._atualizar_campos_escola()
    assert app.var_rotulo_assinatura.get() == "Outro Rótulo"


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
    # O botão não inclui mais os termos (aba própria) — a referência
    # precisa da mesma opção pra a comparação de tamanho fazer sentido.
    gerar_pdf_direto(config_admin_only, caminho_referencia, incluir_termos=False)
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
    """O nome do diretor (campo da aba Escola, sincronizado em
    self.dados.diretor_nome) tem que ir pro gerar_pdf independente de
    "Trio gestor" estar marcado em "Incluir" — não depende mais de
    nenhuma pessoa cadastrada na Gestão."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.var_nome.set("EE Exemplo Fictício")
    app.var_diretor.set("Diretora Teste")
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


def test_checkboxes_imprimir_existem_e_comecam_marcados(app):
    assert app.var_imprimir_folha.get() is True
    assert app.var_imprimir_consolidacao.get() is True


def test_gerar_pdf_pelo_botao_nunca_inclui_termos_e_repassa_opcoes_de_impressao(app, monkeypatch):
    """Pedido do usuário: o botão "Gerar Livro Ponto" não inclui mais os
    termos de abertura/encerramento (aba própria, Termos) — e repassa as
    opções de Imprimir Folha/Consolidação pro gerador de PDF."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.var_nome.set("EE Exemplo Fictício")
    app.var_imprimir_folha.set(True)
    app.var_imprimir_consolidacao.set(False)

    chamadas = []

    def _gerar_pdf_espiao(config, caminho, **kwargs):
        chamadas.append(kwargs)
        return caminho

    import livroponto.desktop.app as app_mod

    monkeypatch.setattr(app_mod, "gerar_pdf", _gerar_pdf_espiao)
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: "saida.pdf")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_pdf()

    assert len(chamadas) == 1
    assert chamadas[0]["incluir_termos"] is False
    assert chamadas[0]["imprimir_folha"] is True
    assert chamadas[0]["imprimir_consolidacao"] is False


def test_gerar_pdf_pelo_botao_avisa_se_nenhuma_opcao_de_impressao_marcada(app, monkeypatch):
    app.dados.pessoas.append(_pessoa_exemplo(nome="Administrativo Teste"))
    app.var_nome.set("EE Exemplo Fictício")
    app.var_imprimir_folha.set(False)
    app.var_imprimir_consolidacao.set(False)

    avisos = []
    monkeypatch.setattr(messagebox, "showwarning", lambda titulo, msg, **k: avisos.append(msg))
    chamou_salvar = []
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: chamou_salvar.append(1) or "saida.pdf")

    app._gerar_pdf()

    assert avisos  # avisou em vez de tentar gerar
    assert not chamou_salvar


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


def test_dialogo_pessoa_cargo_sugere_gestao_e_administrativo_mas_aceita_texto_livre(app, monkeypatch):
    """Pedido do usuário: a caixa de cargo/função sugere os cargos do
    trio gestor e os administrativos mais comuns, mas continua editável
    — as URES usam nomenclaturas diferentes das escolas."""
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    valores = dlg.combo_cargo.cget("values")
    assert "Diretor(a) de Escola" in valores
    assert "Agente de Organização Escolar" in valores
    assert "Secretário de Escola" in valores
    assert "Gerente de Organização Escolar" in valores
    assert str(dlg.combo_cargo.cget("state")) != "readonly"

    dlg.var_cargo.set("Dirigente Regional de Ensino")  # nomenclatura de URE, fora da lista
    assert dlg.var_cargo.get() == "Dirigente Regional de Ensino"


def test_dialogo_pessoa_formata_rg_automaticamente_ao_digitar(app, monkeypatch):
    """Pedido do usuário: o campo RG do cadastro formata sozinho no
    padrão XX.XXX.XXX-X conforme os números (ou letra, em RG de outro
    estado) vão sendo digitados."""
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    dlg.var_rg.set("123456789")
    assert dlg.var_rg.get() == "12.345.678-9"

    dlg.var_rg.set("m1234567")
    assert dlg.var_rg.get() == "M1.234.567"


def test_lista_de_pessoas_mostra_rg_formatado_mesmo_cadastrado_sem_pontuacao(app):
    app.dados.pessoas.append(_pessoa_exemplo(nome="Fulano", rg="123456789"))
    app._atualizar_listas_pessoas()
    valores = app.tree_administrativo.item("0", "values")
    assert valores[1] == "12.345.678-9"


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


def test_dialogo_pessoa_nao_tem_mais_campo_de_ferias(app, monkeypatch):
    """Férias saiu do diálogo de Adicionar/Editar servidor — agora só se
    edita pela aba Férias."""
    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    dlg = DialogoPessoa(app)
    assert not hasattr(dlg, "var_ferias_inicio")
    assert not hasattr(dlg, "var_ferias_fim")
    dlg._cancelar()


def test_dialogo_pessoa_editar_preserva_ferias_e_licencas_existentes(app, monkeypatch):
    """Editar um servidor pelo diálogo (sem os campos de férias/licenças,
    que agora moraram noutras abas) não pode apagar o que já estava
    cadastrado lá."""
    from livroponto.models import Licenca

    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    pessoa = _pessoa_exemplo(
        nome="Servidor Com Férias",
        ferias_inicio="03/04/2026",
        ferias_fim="02/05/2026",
        licencas=[Licenca(tipo="SAUDE", inicio="10/04/2026", fim="20/04/2026")],
    )
    dlg = DialogoPessoa(app, pessoa)
    dlg.var_cargo.set("Novo Cargo")  # muda outra coisa qualquer
    dlg._salvar()

    assert dlg.resultado.ferias_inicio == "03/04/2026"
    assert dlg.resultado.ferias_fim == "02/05/2026"
    assert dlg.resultado.periodo_ferias == "03/04/2026 a 02/05/2026"
    assert len(dlg.resultado.licencas) == 1
    assert dlg.resultado.licencas[0].tipo == "SAUDE"
    assert dlg.resultado.cargo == "Novo Cargo"


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


def test_aba_termos_existe_com_administrativo_marcado_por_padrao(app):
    from livroponto.desktop.app import MESES_CAP

    assert app.var_termo_administrativo.get() is True
    assert app.var_termo_gestao.get() is False
    assert app.var_termo_docente.get() is False
    assert app.var_termo_mes.get() in MESES_CAP
    assert app.var_termo_ano.get() != ""


def test_gerar_termos_chama_gerar_termos_pdf_com_mes_ano_e_tipos_escolhidos(app, monkeypatch):
    app.var_nome.set("EE Exemplo Fictício")
    app.var_diretor.set("Diretora Teste")
    app.var_termo_mes.set("Setembro")
    app.var_termo_ano.set("2027")
    app.var_termo_administrativo.set(True)
    app.var_termo_gestao.set(True)
    app.var_termo_docente.set(False)

    chamadas = []

    def _gerar_termos_pdf_espiao(config, caminho, tipos_incluidos, mes, ano):
        chamadas.append((config, tipos_incluidos, mes, ano))
        return caminho

    import livroponto.desktop.app as app_mod

    monkeypatch.setattr(app_mod, "gerar_termos_pdf", _gerar_termos_pdf_espiao)
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: "saida.pdf")
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_termos()

    assert len(chamadas) == 1
    config_recebido, tipos_incluidos, mes, ano = chamadas[0]
    assert config_recebido.diretor_nome == "Diretora Teste"
    assert tipos_incluidos == {TipoServidor.ADMINISTRATIVO, TipoServidor.GESTAO}
    assert mes == 9
    assert ano == 2027


def test_gerar_termos_sem_nenhum_tipo_marcado_avisa_e_nao_gera(app, monkeypatch):
    app.var_termo_administrativo.set(False)
    app.var_termo_gestao.set(False)
    app.var_termo_docente.set(False)

    avisos = []
    monkeypatch.setattr(messagebox, "showwarning", lambda titulo, msg, **k: avisos.append((titulo, msg)))
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", lambda **kw: pytest.fail("não devia chegar a abrir o diálogo de salvar")
    )

    app._gerar_termos()

    assert len(avisos) == 1


def test_gerar_termos_pelo_botao_gera_pdf_de_verdade(app, tmp_path, monkeypatch):
    app.var_nome.set("EE Exemplo Fictício")
    app.var_diretor.set("Diretora Teste")
    app.var_termo_administrativo.set(True)

    caminho = tmp_path / "termos.pdf"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(caminho))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)

    app._gerar_termos()

    assert caminho.exists()
    assert caminho.stat().st_size > 500


def test_adicionar_editar_ou_remover_servidor_atualiza_ferias_e_licencas(app):
    """Bug real reportado pelo usuário: um servidor recém-cadastrado (ou
    removido) na aba Administrativo/Gestão não aparecia/sumia na aba
    Férias nem no combo de servidor da aba Licenças até fechar e reabrir
    o cadastro — _atualizar_listas_pessoas() não recarregava essas duas
    abas, só as próprias listas de Administrativo/Gestão."""
    app.dados.pessoas.append(_pessoa_exemplo(nome="Novo Servidor"))
    app._atualizar_listas_pessoas()

    assert len(app.tree_ferias.get_children()) == 1
    assert app.tree_ferias.item("0", "values")[0] == "Novo Servidor"
    valores_combo = app.combo_licenca_servidor.cget("values")
    assert any("Novo Servidor" in v for v in valores_combo)

    del app.dados.pessoas[0]
    app._atualizar_listas_pessoas()
    assert len(app.tree_ferias.get_children()) == 0
    assert len(app.combo_licenca_servidor.cget("values")) == 0


def test_aba_ferias_lista_todo_mundo_e_editar_atualiza_pessoa(app):
    app.dados.pessoas.append(_pessoa_exemplo(nome="Servidor Sem Férias", rg="5"))
    app._atualizar_lista_ferias()
    assert len(app.tree_ferias.get_children()) == 1

    app.tree_ferias.selection_set("0")
    idx = app._pessoa_selecionada_ferias()
    assert idx == 0

    app.dados.pessoas[idx].ferias_inicio = "03/04/2026"
    app.dados.pessoas[idx].ferias_fim = "02/05/2026"
    app._atualizar_lista_ferias()
    valores = app.tree_ferias.item("0", "values")
    assert valores[3] == "03/04/2026"
    assert valores[4] == "02/05/2026"


def test_dialogo_ferias_edita_e_limpa_periodo(app, monkeypatch):
    from livroponto.desktop.dialogs import DialogoFerias

    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    pessoa = _pessoa_exemplo(nome="Fulano", ferias_inicio="03/04/2026", ferias_fim="02/05/2026")
    dlg = DialogoFerias(app, pessoa)
    assert dlg.var_ferias_inicio.get() == "03/04/2026"
    assert dlg.var_ferias_fim.get() == "02/05/2026"

    dlg._limpar()
    dlg._salvar()
    assert dlg.resultado == ("", "")


def test_licenca_adicionar_editar_remover_atualiza_lista_e_observacoes(app, monkeypatch):
    from livroponto.desktop.dialogs import DialogoLicenca

    monkeypatch.setattr(tk.Toplevel, "wait_window", lambda self, *a: self.update())

    app.dados.pessoas.append(_pessoa_exemplo(nome="Servidor Licença", rg="9"))
    app._atualizar_lista_licencas()
    app._atualizar_listas_pessoas()

    app.combo_licenca_servidor.current(0)
    dlg = DialogoLicenca(app, app.dados.pessoas[0])
    dlg.var_tipo.set("SAUDE")
    dlg.var_inicio.set("10/04/2026")
    dlg.var_fim.set("20/04/2026")
    dlg._salvar()
    assert dlg.resultado is not None
    app.dados.pessoas[0].licencas.append(dlg.resultado)
    app._atualizar_lista_licencas()
    app._atualizar_listas_pessoas()

    assert len(app.tree_licencas.get_children()) == 1
    linha = app.tree_licencas.item("0:0", "values")
    assert linha[0] == "Servidor Licença"
    assert linha[1] == "Licença Saúde"

    # a licença aparece resumida na coluna Observações do cadastro
    valores_admin = app.tree_administrativo.item("0", "values")
    assert "Licença Saúde: 10/04/2026 a 20/04/2026" in valores_admin[-1]

    # remover
    app.tree_licencas.selection_set("0:0")
    sel = app._licenca_selecionada()
    assert sel == (0, 0)
    del app.dados.pessoas[0].licencas[0]
    app._atualizar_lista_licencas()
    assert len(app.tree_licencas.get_children()) == 0


def test_observacoes_exibicao_mescla_texto_livre_e_licencas():
    from livroponto.desktop.app import _observacoes_exibicao
    from livroponto.models import Licenca

    pessoa = _pessoa_exemplo(
        observacoes="Afastada por licença médica",
        licencas=[Licenca(tipo="PREMIO", inicio="01/06/2026", fim="30/06/2026")],
    )
    texto = _observacoes_exibicao(pessoa)
    assert "Afastada por licença médica" in texto
    assert "Licença Prêmio: 01/06/2026 a 30/06/2026" in texto
