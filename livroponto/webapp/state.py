"""Conversões entre os modelos (Pessoa, DiaNaoLetivo) e DataFrames pandas,
usadas pelas tabelas editáveis do app web."""
from __future__ import annotations

import pandas as pd

from ..models import DiaNaoLetivo, Pessoa, TipoServidor

COLUNAS_PESSOAS = [
    "tipo",
    "nome",
    "rg",
    "cargo",
    "jornada_semanal",
    "jornada_codigo",
    "ponto",
    "entrada",
    "saida",
    "intervalo_inicio",
    "intervalo_fim",
    "disciplinas",
    "categoria",
    "situacao",
    "observacoes",
]

COLUNAS_EXCECOES = ["mes", "dia", "tipo", "descricao"]

TIPOS_EXCECAO = ["FERIADO", "RECESSO", "PONTO_FACULTATIVO", "SUSPENSAO", "LETIVO"]


def pessoas_para_df(pessoas: list[Pessoa]) -> pd.DataFrame:
    linhas = [
        {
            "tipo": p.tipo.value,
            "nome": p.nome,
            "rg": p.rg,
            "cargo": p.cargo,
            "jornada_semanal": p.jornada_semanal,
            "jornada_codigo": p.jornada_codigo,
            "ponto": p.ponto,
            "entrada": p.entrada,
            "saida": p.saida,
            "intervalo_inicio": p.intervalo_inicio,
            "intervalo_fim": p.intervalo_fim,
            "disciplinas": p.disciplinas,
            "categoria": p.categoria,
            "situacao": p.situacao,
            "observacoes": p.observacoes,
        }
        for p in pessoas
    ]
    return pd.DataFrame(linhas, columns=COLUNAS_PESSOAS)


def _texto(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def df_para_pessoas(df: pd.DataFrame) -> list[Pessoa]:
    pessoas: list[Pessoa] = []
    for row in df.to_dict("records"):
        nome = _texto(row.get("nome"))
        if not nome:
            continue
        tipo_raw = _texto(row.get("tipo")).upper()
        tipo = TipoServidor.DOCENTE if tipo_raw.startswith("DOC") else TipoServidor.ADMINISTRATIVO
        jornada_raw = row.get("jornada_semanal")
        jornada = None
        if jornada_raw not in (None, "") and not (isinstance(jornada_raw, float) and pd.isna(jornada_raw)):
            try:
                jornada = float(jornada_raw)
            except (TypeError, ValueError):
                jornada = None
        ponto_raw = row.get("ponto")
        ponto = True if ponto_raw is None or (isinstance(ponto_raw, float) and pd.isna(ponto_raw)) else bool(ponto_raw)
        pessoas.append(
            Pessoa(
                nome=nome,
                tipo=tipo,
                rg=_texto(row.get("rg")),
                cargo=_texto(row.get("cargo")),
                jornada_semanal=jornada,
                jornada_codigo=_texto(row.get("jornada_codigo")),
                ponto=ponto,
                entrada=_texto(row.get("entrada")),
                saida=_texto(row.get("saida")),
                intervalo_inicio=_texto(row.get("intervalo_inicio")),
                intervalo_fim=_texto(row.get("intervalo_fim")),
                disciplinas=_texto(row.get("disciplinas")),
                categoria=_texto(row.get("categoria")),
                situacao=_texto(row.get("situacao")),
                observacoes=_texto(row.get("observacoes")),
            )
        )
    return pessoas


def excecoes_para_df(excecoes: list[DiaNaoLetivo]) -> pd.DataFrame:
    linhas = [
        {"mes": e.mes, "dia": e.dia, "tipo": e.tipo, "descricao": e.descricao} for e in excecoes
    ]
    return pd.DataFrame(linhas, columns=COLUNAS_EXCECOES)


def df_para_excecoes(df: pd.DataFrame) -> list[DiaNaoLetivo]:
    excecoes: list[DiaNaoLetivo] = []
    for row in df.to_dict("records"):
        mes_raw, dia_raw = row.get("mes"), row.get("dia")
        if mes_raw in (None, "") or dia_raw in (None, ""):
            continue
        if isinstance(mes_raw, float) and pd.isna(mes_raw):
            continue
        if isinstance(dia_raw, float) and pd.isna(dia_raw):
            continue
        try:
            mes, dia = int(mes_raw), int(dia_raw)
        except (TypeError, ValueError):
            continue
        tipo = _texto(row.get("tipo")).upper() or "FERIADO"
        excecoes.append(DiaNaoLetivo(mes=mes, dia=dia, tipo=tipo, descricao=_texto(row.get("descricao"))))
    return excecoes
