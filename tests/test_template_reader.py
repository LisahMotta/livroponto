from openpyxl import load_workbook

from livroponto.models import TipoServidor
from livroponto.readers.template_reader import criar_modelo, ler_modelo


def test_criar_modelo_gera_abas_esperadas(tmp_path):
    caminho = tmp_path / "modelo.xlsx"
    criar_modelo(caminho)
    wb = load_workbook(caminho)
    assert "Escola" in wb.sheetnames
    assert "Pessoas" in wb.sheetnames


def test_ler_modelo_roundtrip(tmp_path):
    caminho = tmp_path / "modelo.xlsx"
    criar_modelo(caminho)

    wb = load_workbook(caminho)
    aba_escola = wb["Escola"]
    for row in aba_escola.iter_rows(min_row=2):
        if row[0].value == "nome":
            row[1].value = "EE Exemplo Fictício"
        if row[0].value == "municipio":
            row[1].value = "Cidade Exemplo"
        if row[0].value == "mes":
            row[1].value = 4
        if row[0].value == "ano":
            row[1].value = 2026
    wb.save(caminho)

    config = ler_modelo(caminho)
    assert config.escola.nome == "EE Exemplo Fictício"
    assert config.mes == 4
    assert config.ano == 2026
    assert len(config.pessoas) == 2
    tipos = {p.tipo for p in config.pessoas}
    assert tipos == {TipoServidor.ADMINISTRATIVO, TipoServidor.DOCENTE}
