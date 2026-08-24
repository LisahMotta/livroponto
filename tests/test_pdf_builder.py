from livroponto.models import Escola, LivroPontoConfig, Pessoa, TipoServidor, chave_ordenacao_rg
from livroponto.pdf.builder import gerar_pdf


def _config_exemplo() -> LivroPontoConfig:
    escola = Escola(
        nome="EE Exemplo Fictício",
        diretoria_ensino="Região Exemplo",
        municipio="Cidade Exemplo",
    )
    pessoas = [
        Pessoa(
            nome="Servidor Fictício Um",
            tipo=TipoServidor.ADMINISTRATIVO,
            rg="00.000.000-0",
            cargo="Agente de Organização Escolar",
            jornada_semanal=40,
            entrada="07:00",
            saida="16:00",
            intervalo_inicio="11:00",
            intervalo_fim="12:00",
        ),
        Pessoa(
            nome="Docente Fictício Dois",
            tipo=TipoServidor.DOCENTE,
            rg="11.111.111-1",
            cargo="PEB II",
            categoria="Titular de Cargo",
            disciplinas="MATEMÁTICA",
        ),
    ]
    return LivroPontoConfig(escola=escola, mes=4, ano=2026, pessoas=pessoas)


def test_gerar_pdf_cria_arquivo_nao_vazio(tmp_path):
    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(_config_exemplo(), caminho)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000
    with open(resultado, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_gerar_pdf_sem_pessoas_lanca_erro(tmp_path):
    config = _config_exemplo()
    config.pessoas = []
    import pytest

    with pytest.raises(ValueError):
        gerar_pdf(config, tmp_path / "vazio.pdf")


def test_ordenacao_por_rg_e_numerica_nao_textual():
    """"9" deve vir antes de "10" (ordem numérica), não depois (ordem de
    texto, onde "10" < "9")."""
    nove = Pessoa(nome="Nove", tipo=TipoServidor.ADMINISTRATIVO, rg="9")
    dez = Pessoa(nome="Dez", tipo=TipoServidor.ADMINISTRATIVO, rg="10")

    ordenados = sorted([dez, nove], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Nove", "Dez"]


def test_ordenacao_por_rg_ignora_pontuacao():
    """Pontos e traço no RG (ex.: "1.234-5") não devem contar como parte
    do número na hora de ordenar."""
    menor = Pessoa(nome="Menor", tipo=TipoServidor.ADMINISTRATIVO, rg="500")
    maior_pontuado = Pessoa(nome="Maior", tipo=TipoServidor.ADMINISTRATIVO, rg="1.234-5")

    ordenados = sorted([maior_pontuado, menor], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Menor", "Maior"]


def test_ordenacao_por_rg_ignora_digito_verificador():
    """O dígito verificador depois do traço não conta como parte do
    número — senão um RG com dígito verificador (ex.: "9.876.543-2",
    que vira 98765432 se o traço não for tratado à parte) fica "maior"
    só por ter um dígito a mais do que um RG equivalente sem traço
    (ex.: "16304137"), e sai antes na ordem quando deveria vir depois."""
    comeca_com_9 = Pessoa(nome="Começa com 9", tipo=TipoServidor.ADMINISTRATIVO, rg="9.876.543-2")
    comeca_com_16 = Pessoa(nome="Começa com 16", tipo=TipoServidor.ADMINISTRATIVO, rg="16304137")

    ordenados = sorted([comeca_com_16, comeca_com_9], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Começa com 9", "Começa com 16"]


def test_ordenacao_por_rg_sem_rg_cadastrado_vai_pro_fim():
    com_rg = Pessoa(nome="Com RG", tipo=TipoServidor.ADMINISTRATIVO, rg="123")
    sem_rg = Pessoa(nome="Sem RG", tipo=TipoServidor.ADMINISTRATIVO, rg="")

    ordenados = sorted([sem_rg, com_rg], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Com RG", "Sem RG"]
