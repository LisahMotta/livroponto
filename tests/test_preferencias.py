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
