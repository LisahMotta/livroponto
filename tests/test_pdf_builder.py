from livroponto.models import Escola, LivroPontoConfig, Pessoa, TipoServidor
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
