"""App web (Streamlit) para editar os dados do Livro Ponto e gerar o PDF.

Rode com:

    livroponto app

ou diretamente:

    streamlit run livroponto/webapp/app.py
"""
from __future__ import annotations

import tempfile
from dataclasses import replace
from datetime import date
from pathlib import Path

import streamlit as st

# Streamlit executa este arquivo como script "solto" (não como parte do
# pacote), então imports relativos (`from ..x import y`) não funcionam aqui
# — por isso os imports abaixo são absolutos, exigindo que o pacote
# `livroponto` esteja instalado (`pip install -e .`) ou no PYTHONPATH.
from livroponto.calendario import nome_mes
from livroponto.models import Escola, LivroPontoConfig, TipoServidor
from livroponto.pdf.builder import gerar_pdf
from livroponto.readers.template_reader import ler_modelo, salvar_modelo
from livroponto.readers.xlsb_reader import ler_livro_ponto
from livroponto.webapp.state import (
    df_para_excecoes,
    df_para_pessoas,
    excecoes_para_df,
    pessoas_para_df,
)

st.set_page_config(page_title="Livro Ponto", page_icon="📘", layout="wide")


def _config_vazio() -> LivroPontoConfig:
    hoje = date.today()
    return LivroPontoConfig(escola=Escola(), mes=hoje.month, ano=hoje.year, pessoas=[])


if "config" not in st.session_state:
    st.session_state.config = _config_vazio()

st.title("📘 Livro Ponto — editor")
st.caption(
    "Edite os dados da escola, dos servidores/professores e das exceções de "
    "calendário, depois baixe o cadastro (.xlsx) e/ou gere o Livro Ponto em PDF."
)

with st.sidebar:
    st.header("Abrir arquivo")
    up = st.file_uploader(
        "Planilha existente: o modelo .xlsx deste app, ou o arquivo legado "
        ".xlsb da rede estadual de SP",
        type=["xlsx", "xlsb"],
    )
    if up is not None and st.session_state.get("_ultimo_upload") != up.name:
        st.session_state["_ultimo_upload"] = up.name
        sufixo = Path(up.name).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
            tmp.write(up.getvalue())
            caminho_tmp = tmp.name
        try:
            if sufixo == ".xlsb":
                novo_config = ler_livro_ponto(caminho_tmp)
            else:
                novo_config = ler_modelo(caminho_tmp)
            st.session_state.config = novo_config
            st.session_state.pop("editor_pessoas", None)
            st.session_state.pop("editor_excecoes", None)
            st.success(f"Carregado: {len(novo_config.pessoas)} pessoa(s).")
        except Exception as exc:  # noqa: BLE001 — mostra qualquer erro de leitura ao usuário
            st.error(f"Erro ao ler arquivo: {exc}")

    st.divider()
    st.caption(
        "As edições ficam nesta sessão do navegador. Clique em **Salvar cadastro** "
        "para baixar um .xlsx e não perder o que foi editado."
    )
    if st.button("🗑️ Começar do zero"):
        st.session_state.config = _config_vazio()
        st.session_state.pop("editor_pessoas", None)
        st.session_state.pop("editor_excecoes", None)
        st.rerun()

config: LivroPontoConfig = st.session_state.config

st.subheader("Dados da escola")
col1, col2 = st.columns(2)
with col1:
    config.escola.nome = st.text_input("Nome da escola", config.escola.nome)
    config.escola.diretoria_ensino = st.text_input(
        "Diretoria de Ensino", config.escola.diretoria_ensino
    )
    config.escola.endereco = st.text_input("Endereço", config.escola.endereco)
    config.escola.municipio = st.text_input("Município", config.escola.municipio)
with col2:
    config.escola.telefone1 = st.text_input("Telefone", config.escola.telefone1)
    config.escola.email = st.text_input("E-mail", config.escola.email)
    config.escola.codigo_ua = st.text_input("Código UA", config.escola.codigo_ua)
    config.escola.codigo_cie = st.text_input("Código CIE", config.escola.codigo_cie)

st.subheader("Período do livro")
col3, col4, col5, col6 = st.columns(4)
with col3:
    config.mes = st.selectbox(
        "Mês",
        list(range(1, 13)),
        index=config.mes - 1,
        format_func=lambda m: nome_mes(m).capitalize(),
    )
with col4:
    config.ano = int(st.number_input("Ano", min_value=2000, max_value=2100, value=config.ano, step=1))
with col5:
    config.uf = st.text_input("UF (feriados)", config.uf or "SP")
with col6:
    config.cidade_assinatura = st.text_input(
        "Cidade (assinatura dos termos)", config.cidade_assinatura or config.escola.municipio
    )
config.diretor_nome = st.text_input(
    "Nome do Diretor(a) (assinatura dos termos)", config.diretor_nome
)

st.subheader("Servidores e professores")
st.caption(
    "Clique numa célula para editar. Use a linha em branco no final da tabela "
    "para adicionar alguém; selecione uma linha e aperte a lixeira pra remover. "
    "Desmarque **ponto** para alguém que não deve ter folha impressa."
)
df_pessoas_editado = st.data_editor(
    pessoas_para_df(config.pessoas),
    num_rows="dynamic",
    width="stretch",
    column_config={
        "tipo": st.column_config.SelectboxColumn(
            "Tipo", options=["ADMINISTRATIVO", "DOCENTE"], required=True
        ),
        "jornada_semanal": st.column_config.NumberColumn("Jornada (h/sem)", min_value=0, max_value=60),
        "jornada_codigo": st.column_config.TextColumn("Jornada (código, docentes)"),
        "ponto": st.column_config.CheckboxColumn("Ponto?", default=True),
        "entrada": st.column_config.TextColumn("Entrada"),
        "saida": st.column_config.TextColumn("Saída"),
        "intervalo_inicio": st.column_config.TextColumn("Intervalo de"),
        "intervalo_fim": st.column_config.TextColumn("Intervalo até"),
    },
    key="editor_pessoas",
)
config.pessoas = df_para_pessoas(df_pessoas_editado)

st.subheader("Feriados e exceções de calendário")
st.caption(
    "Feriados nacionais e estaduais já são calculados automaticamente pela UF "
    "acima. Aqui você só informa o que for específico do seu município/escola: "
    "recesso, ponto facultativo, suspensão de atividades, ou um sábado letivo "
    "de reposição (tipo LETIVO)."
)
df_excecoes_editado = st.data_editor(
    excecoes_para_df(config.dias_excecao),
    num_rows="dynamic",
    width="stretch",
    column_config={
        "mes": st.column_config.NumberColumn("Mês", min_value=1, max_value=12),
        "dia": st.column_config.NumberColumn("Dia", min_value=1, max_value=31),
        "tipo": st.column_config.SelectboxColumn(
            "Tipo",
            options=["FERIADO", "RECESSO", "PONTO_FACULTATIVO", "SUSPENSAO", "LETIVO"],
        ),
        "descricao": st.column_config.TextColumn("Descrição"),
    },
    key="editor_excecoes",
)
config.dias_excecao = df_para_excecoes(df_excecoes_editado)

st.session_state.config = config

st.divider()
col_salvar, col_pdf = st.columns(2)

with col_salvar:
    st.subheader("💾 Salvar cadastro")
    st.caption("Baixa um .xlsx com tudo o que foi editado, para reabrir depois e continuar.")
    if st.button("Preparar .xlsx para download"):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            salvar_modelo(config, tmp.name)
            dados_xlsx = Path(tmp.name).read_bytes()
        st.download_button(
            "⬇️ Baixar modelo_livro_ponto.xlsx",
            data=dados_xlsx,
            file_name="modelo_livro_ponto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with col_pdf:
    st.subheader("🖨️ Gerar Livro Ponto (PDF)")
    st.caption("Termos de abertura/encerramento + uma folha por servidor com o calendário do mês.")
    n_admin = len(config.pessoas_por_tipo(TipoServidor.ADMINISTRATIVO))
    n_docente = len(config.pessoas_por_tipo(TipoServidor.DOCENTE))
    st.write(f"{n_admin} administrativo(s), {n_docente} docente(s) cadastrados.")
    if st.button("Gerar PDF", type="primary"):
        pessoas_com_ponto = [p for p in config.pessoas if p.ponto]
        if not pessoas_com_ponto:
            st.error("Nenhuma pessoa com **ponto** marcado — nada para gerar.")
        else:
            config_final = replace(config, pessoas=pessoas_com_ponto)
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    gerar_pdf(config_final, tmp.name)
                    dados_pdf = Path(tmp.name).read_bytes()
                st.success("PDF gerado!")
                st.download_button(
                    "⬇️ Baixar livro_ponto.pdf",
                    data=dados_pdf,
                    file_name=f"livro_ponto_{config.mes:02d}_{config.ano}.pdf",
                    mime="application/pdf",
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Erro ao gerar PDF: {exc}")
