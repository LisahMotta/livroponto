from livroponto.desktop import preferencias


def test_carregar_ultimo_caminho_sem_nada_salvo_ainda(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", tmp_path / "nao-existe" / "estado.json")
    assert preferencias.carregar_ultimo_caminho() is None


def test_salvar_e_carregar_ultimo_caminho_faz_o_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", tmp_path / "livroponto" / "estado.json")

    preferencias.salvar_ultimo_caminho(str(tmp_path / "modelo_livro_ponto.xlsx"))

    assert preferencias.carregar_ultimo_caminho() == str(tmp_path / "modelo_livro_ponto.xlsx")


def test_salvar_ultimo_caminho_cria_a_pasta_se_nao_existir(tmp_path, monkeypatch):
    arquivo_estado = tmp_path / "ainda-nao-existe" / "estado.json"
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", arquivo_estado)

    preferencias.salvar_ultimo_caminho("C:/algum/caminho.xlsx")

    assert arquivo_estado.exists()


def test_carregar_ultimo_caminho_com_arquivo_de_estado_corrompido_nao_quebra(tmp_path, monkeypatch):
    arquivo_estado = tmp_path / "estado.json"
    arquivo_estado.write_text("isso não é json válido {{{", encoding="utf-8")
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", arquivo_estado)

    assert preferencias.carregar_ultimo_caminho() is None


def test_tutorial_ja_visto_comeca_falso(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", tmp_path / "estado.json")
    assert preferencias.tutorial_ja_visto() is False


def test_marcar_tutorial_visto_faz_o_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", tmp_path / "estado.json")

    preferencias.marcar_tutorial_visto()

    assert preferencias.tutorial_ja_visto() is True


def test_ultimo_caminho_e_tutorial_visto_nao_se_atropelam(tmp_path, monkeypatch):
    """As duas preferências moram no mesmo arquivo — salvar uma não pode
    apagar a outra."""
    monkeypatch.setattr(preferencias, "_ARQUIVO_ESTADO", tmp_path / "estado.json")

    preferencias.salvar_ultimo_caminho(str(tmp_path / "cadastro.xlsx"))
    preferencias.marcar_tutorial_visto()

    assert preferencias.carregar_ultimo_caminho() == str(tmp_path / "cadastro.xlsx")
    assert preferencias.tutorial_ja_visto() is True
