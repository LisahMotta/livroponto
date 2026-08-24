from openpyxl import load_workbook

from livroponto.models import DiaNaoLetivo, Escola, LivroPontoConfig, MembroGestao, Pessoa, TipoServidor
from livroponto.readers.template_reader import criar_modelo, ler_modelo, salvar_modelo


def test_criar_modelo_gera_abas_esperadas(tmp_path):
    caminho = tmp_path / "modelo.xlsx"
    criar_modelo(caminho)
    wb = load_workbook(caminho)
    assert "Escola" in wb.sheetnames
    assert "Pessoas" in wb.sheetnames
    assert "EquipeGestora" in wb.sheetnames


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
    assert len(config.equipe_gestora) == 1
    assert config.equipe_gestora[0].cargo == "Diretor(a) de Escola"


def test_salvar_modelo_e_ler_modelo_preservam_excecoes_e_jornada_codigo(tmp_path):
    config = LivroPontoConfig(
        escola=Escola(nome="EE Exemplo Fictício", municipio="Cidade Exemplo"),
        mes=7,
        ano=2026,
        uf="SP",
        cidade_assinatura="Cidade Exemplo",
        pessoas=[
            Pessoa(
                nome="Docente Fictício",
                tipo=TipoServidor.DOCENTE,
                rg="1.111.111-1",
                cargo="PEB II",
                jornada_codigo="B",
                disciplinas="HISTÓRIA",
            ),
        ],
        dias_excecao=[
            DiaNaoLetivo(mes=7, dia=8, tipo="RECESSO", descricao="Recesso escolar"),
        ],
    )

    caminho = tmp_path / "modelo.xlsx"
    salvar_modelo(config, caminho)
    recarregado = ler_modelo(caminho)

    assert recarregado.uf == "SP"
    assert len(recarregado.pessoas) == 1
    assert recarregado.pessoas[0].jornada_codigo == "B"
    assert len(recarregado.dias_excecao) == 1
    assert recarregado.dias_excecao[0].tipo == "RECESSO"
    assert recarregado.dias_excecao[0].dia == 8


def test_salvar_modelo_e_ler_modelo_preservam_equipe_gestora(tmp_path):
    config = LivroPontoConfig(
        escola=Escola(nome="EE Exemplo Fictício", municipio="Cidade Exemplo"),
        mes=4,
        ano=2026,
        equipe_gestora=[
            MembroGestao(nome="Diretora Fictícia", cargo="Diretor(a) de Escola", rg="1.234.567-8"),
            MembroGestao(nome="Vice Fictício", cargo="Vice-Diretor(a) de Escola"),
        ],
    )

    caminho = tmp_path / "modelo.xlsx"
    salvar_modelo(config, caminho)
    recarregado = ler_modelo(caminho)

    assert len(recarregado.equipe_gestora) == 2
    assert recarregado.equipe_gestora[0].nome == "Diretora Fictícia"
    assert recarregado.equipe_gestora[0].rg == "1.234.567-8"
    assert recarregado.nome_diretor() == "Diretora Fictícia"


def test_salvar_modelo_e_ler_modelo_preservam_periodo_de_ferias(tmp_path):
    config = LivroPontoConfig(
        escola=Escola(nome="EE Exemplo Fictício", municipio="Cidade Exemplo"),
        mes=4,
        ano=2026,
        pessoas=[
            Pessoa(
                nome="Servidor Fictício",
                tipo=TipoServidor.ADMINISTRATIVO,
                rg="1.111.111-1",
                ferias_inicio="03/04/2026",
                ferias_fim="02/05/2026",
            ),
        ],
    )

    caminho = tmp_path / "modelo.xlsx"
    salvar_modelo(config, caminho)
    recarregado = ler_modelo(caminho)

    assert recarregado.pessoas[0].ferias_inicio == "03/04/2026"
    assert recarregado.pessoas[0].ferias_fim == "02/05/2026"
    assert recarregado.pessoas[0].periodo_ferias == "03/04/2026 a 02/05/2026"
