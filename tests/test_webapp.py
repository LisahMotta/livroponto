"""Testes do app web (Streamlit, opcional — `pip install .[web]`), usando o
harness oficial de testes do Streamlit (`AppTest`), que roda o script sem
precisar de navegador. Pulados automaticamente se streamlit não estiver
instalado (não é uma dependência básica do pacote)."""
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

from livroponto.models import Escola, LivroPontoConfig, Pessoa, TipoServidor  # noqa: E402

CAMINHO_APP = str(Path(__file__).resolve().parent.parent / "livroponto" / "webapp" / "app.py")


def _config_exemplo() -> LivroPontoConfig:
    return LivroPontoConfig(
        escola=Escola(nome="EE Teste Fictícia", municipio="Cidade Teste"),
        mes=4,
        ano=2026,
        pessoas=[
            Pessoa(
                nome="Fulano Teste",
                tipo=TipoServidor.ADMINISTRATIVO,
                rg="1.111.111-1",
                cargo="Agente de Organização Escolar",
                jornada_semanal=40,
                entrada="07:00",
                saida="16:00",
            )
        ],
    )


def test_app_carrega_sem_excecoes():
    at = AppTest.from_file(CAMINHO_APP)
    at.run(timeout=30)
    assert not at.exception
    assert at.title[0].value == "📘 Livro Ponto — editor"


def test_gerar_pdf_pela_ui_produz_botao_de_download():
    at = AppTest.from_file(CAMINHO_APP)
    at.session_state["config"] = _config_exemplo()
    at.run(timeout=30)
    assert not at.exception

    botoes = {b.label: b for b in at.button}
    botoes["Gerar PDF"].click().run(timeout=30)

    assert not at.exception
    rotulos_download = [d.label for d in at.download_button]
    assert "⬇️ Baixar livro_ponto.pdf" in rotulos_download


def test_salvar_cadastro_pela_ui_produz_botao_de_download():
    at = AppTest.from_file(CAMINHO_APP)
    at.session_state["config"] = _config_exemplo()
    at.run(timeout=30)

    botoes = {b.label: b for b in at.button}
    botoes["Preparar .xlsx para download"].click().run(timeout=30)

    assert not at.exception
    rotulos_download = [d.label for d in at.download_button]
    assert "⬇️ Baixar modelo_livro_ponto.xlsx" in rotulos_download


def test_comecar_do_zero_limpa_cadastro():
    at = AppTest.from_file(CAMINHO_APP)
    at.session_state["config"] = _config_exemplo()
    at.run(timeout=30)

    botoes = {b.label: b for b in at.button}
    botoes["🗑️ Começar do zero"].click().run(timeout=30)

    assert not at.exception
    assert at.session_state["config"].escola.nome == ""
    assert at.session_state["config"].pessoas == []
