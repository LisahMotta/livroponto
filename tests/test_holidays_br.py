import json

from livroponto.holidays_br import carregar_dias_excecao, feriados_do_ano, indexar_excecoes


def test_feriados_do_ano_inclui_feriados_nacionais_e_de_sp():
    feriados = feriados_do_ano(2026, uf="SP")
    nomes = " | ".join(feriados.values())
    assert "Tiradentes" in nomes
    assert "Revolução Constitucionalista" in nomes  # feriado estadual de SP


def test_carregar_dias_excecao(tmp_path):
    caminho = tmp_path / "feriados.json"
    caminho.write_text(
        json.dumps(
            [{"mes": 4, "dia": 19, "tipo": "ponto_facultativo", "descricao": "Aniversário"}]
        ),
        encoding="utf-8",
    )
    excecoes = carregar_dias_excecao(caminho)
    assert len(excecoes) == 1
    assert excecoes[0].tipo == "PONTO_FACULTATIVO"
    assert excecoes[0].mes == 4
    assert excecoes[0].dia == 19


def test_indexar_excecoes(tmp_path):
    caminho = tmp_path / "feriados.json"
    caminho.write_text(
        json.dumps([{"mes": 7, "dia": 1, "tipo": "RECESSO", "descricao": "Recesso"}]),
        encoding="utf-8",
    )
    excecoes = carregar_dias_excecao(caminho)
    indice = indexar_excecoes(excecoes, 2026)
    import datetime as dt

    assert dt.date(2026, 7, 1) in indice
