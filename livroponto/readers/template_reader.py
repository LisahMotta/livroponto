"""Leitor/gerador do modelo simplificado (.xlsx) — alternativa para quem não
tem a planilha legada SEDUC-SP: uma aba "Escola" (campo/valor) e uma aba
"Pessoas" (uma linha por servidor)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook

from ..models import Escola, LivroPontoConfig, Pessoa, TipoServidor

COLUNAS_PESSOAS = [
    "tipo",
    "nome",
    "rg",
    "cargo",
    "jornada_semanal",
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

CAMPOS_ESCOLA = [
    ("nome", "Nome da escola"),
    ("diretoria_ensino", "Diretoria de Ensino"),
    ("endereco", "Endereço"),
    ("municipio", "Município"),
    ("telefone1", "Telefone 1"),
    ("telefone2", "Telefone 2"),
    ("email", "E-mail"),
    ("codigo_ua", "Código UA"),
    ("codigo_cie", "Código CIE"),
]


def criar_modelo(caminho: str | Path) -> None:
    """Gera um arquivo .xlsx em branco (com um exemplo) para o usuário
    preencher, no formato aceito por `ler_modelo`."""
    wb = Workbook()

    aba_escola = wb.active
    aba_escola.title = "Escola"
    aba_escola.append(["campo", "valor"])
    for campo, rotulo in CAMPOS_ESCOLA:
        aba_escola.append([campo, ""])
    aba_escola.append(["mes", 4])
    aba_escola.append(["ano", 2026])
    aba_escola.append(["cidade_assinatura", ""])

    aba_pessoas = wb.create_sheet("Pessoas")
    aba_pessoas.append(COLUNAS_PESSOAS)
    aba_pessoas.append(
        [
            "ADMINISTRATIVO",
            "Fulano de Tal",
            "12.345.678-9",
            "Agente de Organização Escolar",
            40,
            "S",
            "07:00",
            "16:00",
            "11:00",
            "12:00",
            "",
            "",
            "",
            "",
        ]
    )
    aba_pessoas.append(
        [
            "DOCENTE",
            "Ciclana da Silva",
            "98.765.432-1",
            "Professor de Educação Básica II",
            "",
            "S",
            "",
            "",
            "",
            "",
            "MATEMÁTICA",
            "Titular de Cargo",
            "PEB II",
            "",
        ]
    )

    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)


def _valor(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v


def ler_modelo(caminho: str | Path) -> LivroPontoConfig:
    wb = load_workbook(caminho, data_only=True)

    campos: dict[str, str] = {}
    aba_escola = wb["Escola"]
    for row in aba_escola.iter_rows(min_row=2, values_only=True):
        if not row or row[0] in (None, ""):
            continue
        chave = str(row[0]).strip()
        valor = _valor(row[1]) if len(row) > 1 else ""
        campos[chave] = valor

    escola = Escola(
        nome=str(campos.get("nome", "")),
        diretoria_ensino=str(campos.get("diretoria_ensino", "")),
        endereco=str(campos.get("endereco", "")),
        municipio=str(campos.get("municipio", "")),
        telefone1=str(campos.get("telefone1", "")),
        telefone2=str(campos.get("telefone2", "")),
        email=str(campos.get("email", "")),
        codigo_ua=str(campos.get("codigo_ua", "")),
        codigo_cie=str(campos.get("codigo_cie", "")),
    )
    mes = int(campos["mes"])
    ano = int(campos["ano"])
    cidade_assinatura = str(campos.get("cidade_assinatura") or escola.municipio)

    aba_pessoas = wb["Pessoas"]
    header = [str(c).strip().lower() if c else "" for c in next(aba_pessoas.iter_rows(min_row=1, max_row=1, values_only=True))]
    idx = {nome: i for i, nome in enumerate(header)}

    def campo(row, nome, default=""):
        i = idx.get(nome)
        if i is None or i >= len(row):
            return default
        v = row[i]
        return default if v is None else v

    pessoas: list[Pessoa] = []
    for row in aba_pessoas.iter_rows(min_row=2, values_only=True):
        if not row or all(v in (None, "") for v in row):
            continue
        nome = str(campo(row, "nome", "")).strip()
        if not nome:
            continue
        tipo_raw = str(campo(row, "tipo", "ADMINISTRATIVO")).strip().upper()
        tipo = TipoServidor.DOCENTE if tipo_raw.startswith("DOC") else TipoServidor.ADMINISTRATIVO
        ponto_raw = str(campo(row, "ponto", "S")).strip().upper()
        jornada_raw = campo(row, "jornada_semanal", "")
        pessoas.append(
            Pessoa(
                nome=nome,
                tipo=tipo,
                rg=str(campo(row, "rg", "")),
                cargo=str(campo(row, "cargo", "")),
                jornada_semanal=float(jornada_raw) if jornada_raw not in ("", None) else None,
                ponto=(ponto_raw != "N"),
                entrada=str(campo(row, "entrada", "")),
                saida=str(campo(row, "saida", "")),
                intervalo_inicio=str(campo(row, "intervalo_inicio", "")),
                intervalo_fim=str(campo(row, "intervalo_fim", "")),
                disciplinas=str(campo(row, "disciplinas", "")),
                categoria=str(campo(row, "categoria", "")),
                situacao=str(campo(row, "situacao", "")),
                observacoes=str(campo(row, "observacoes", "")),
            )
        )

    return LivroPontoConfig(
        escola=escola,
        mes=mes,
        ano=ano,
        pessoas=pessoas,
        cidade_assinatura=cidade_assinatura,
    )
