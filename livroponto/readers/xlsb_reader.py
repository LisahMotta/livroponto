"""Leitor para o modelo legado "LIVRO PONTO" (.xlsb) usado pelas escolas da
rede estadual de São Paulo (planilha com abas Escola/Funcionários/Professores/
LP-Abertura etc.).

Esse modelo tem posições de célula fixas (não é uma tabela nomeada), então a
leitura é feita por endereço absoluto (linha, coluna), igual à referência
usada pelas próprias fórmulas da planilha original.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pyxlsb import open_workbook

from ..calendario import mes_por_nome
from ..models import Escola, LivroPontoConfig, Pessoa, TipoServidor

CellMap = dict[tuple[int, int], Any]


def _mapa_celulas(wb, nome_aba: str) -> CellMap:
    celulas: CellMap = {}
    with wb.get_sheet(nome_aba) as sheet:
        for row in sheet.rows():
            for c in row:
                if c.v not in (None, ""):
                    celulas[(c.r, c.c)] = c.v
    return celulas


def _texto(celulas: CellMap, r: int, c: int, default: str = "") -> str:
    v = celulas.get((r, c), default)
    if v is None:
        return default
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _ler_escola(celulas: CellMap) -> Escola:
    return Escola(
        diretoria_ensino=_texto(celulas, 1, 7),
        nome=_texto(celulas, 2, 4),
        endereco=_texto(celulas, 3, 4),
        municipio=_texto(celulas, 5, 4),
        telefone1=_texto(celulas, 4, 4),
        telefone2=_texto(celulas, 4, 10),
        email=_texto(celulas, 6, 4),
        codigo_ua=_texto(celulas, 5, 14),
        codigo_cie=_texto(celulas, 6, 14),
    )


def _ler_mes_ano(celulas: CellMap) -> tuple[int | None, int | None, str, str]:
    """Lê mês/ano padrão e a cidade a partir da aba LP-Abertura."""
    cidade = _texto(celulas, 4, 2)
    mes_txt = _texto(celulas, 6, 2)
    ano_txt = _texto(celulas, 6, 7)
    mes = None
    ano = None
    try:
        mes = mes_por_nome(mes_txt)
    except ValueError:
        pass
    if ano_txt:
        try:
            ano = int(float(ano_txt))
        except ValueError:
            pass
    return mes, ano, cidade, mes_txt


def _ler_funcionarios(celulas: CellMap) -> list[Pessoa]:
    pessoas: list[Pessoa] = []
    r = 3
    while True:
        nome = _texto(celulas, r, 5)
        if not nome:
            # a tabela pode ter linhas em branco intercaladas perto do fim;
            # tolera algumas antes de parar de vez.
            if all(not _texto(celulas, rr, 5) for rr in range(r, r + 5)):
                break
            r += 1
            continue
        seq_raw = celulas.get((r, 4))
        ponto_raw = _texto(celulas, r, 10).upper()
        jornada_raw = celulas.get((r, 9))
        pessoas.append(
            Pessoa(
                nome=nome,
                tipo=TipoServidor.ADMINISTRATIVO,
                rg=_texto(celulas, r, 6),
                cargo=_texto(celulas, r, 8),
                jornada_semanal=float(jornada_raw) if jornada_raw not in (None, "") else None,
                ponto=(ponto_raw != "N"),
                entrada=_texto(celulas, r, 11),
                saida=_texto(celulas, r, 12),
                intervalo_inicio=_texto(celulas, r, 13),
                intervalo_fim=_texto(celulas, r, 14),
                seq=int(seq_raw) if seq_raw not in (None, "") else None,
            )
        )
        r += 1
    return pessoas


def _ler_professores(celulas: CellMap) -> list[Pessoa]:
    pessoas: list[Pessoa] = []
    r = 4
    while True:
        nome = _texto(celulas, r, 3)
        if not nome:
            if all(not _texto(celulas, rr, 3) for rr in range(r, r + 5)):
                break
            r += 1
            continue
        seq_raw = celulas.get((r, 0))
        ponto_raw = _texto(celulas, r, 18).upper()
        pessoas.append(
            Pessoa(
                nome=nome,
                tipo=TipoServidor.DOCENTE,
                rg=_texto(celulas, r, 4),
                cargo=_texto(celulas, r, 9),  # ex.: PEB I / PEB II
                categoria=_texto(celulas, r, 10),  # vínculo: Titular de Cargo, OFA...
                jornada_semanal=None,
                ponto=(ponto_raw != "N"),
                disciplinas=_texto(celulas, r, 14),
                observacoes=_texto(celulas, r, 19),
                jornada_codigo=_texto(celulas, r, 11),
                seq=int(seq_raw) if seq_raw not in (None, "") else None,
            )
        )
        r += 1
    return pessoas


def ler_livro_ponto(
    caminho: str | Path,
    mes: int | None = None,
    ano: int | None = None,
    incluir_administrativos: bool = True,
    incluir_docentes: bool = True,
    somente_com_ponto: bool = True,
) -> LivroPontoConfig:
    """Lê o arquivo .xlsb legado e monta um LivroPontoConfig.

    Se `mes`/`ano` não forem informados, usa os valores padrão da aba
    LP-Abertura do próprio arquivo.
    """
    caminho = Path(caminho)
    with open_workbook(str(caminho)) as wb:
        abas = set(wb.sheets)
        celulas_escola = _mapa_celulas(wb, "Escola") if "Escola" in abas else {}
        escola = _ler_escola(celulas_escola)

        mes_padrao = ano_padrao = None
        cidade = ""
        if "LP-Abertura" in abas:
            celulas_abertura = _mapa_celulas(wb, "LP-Abertura")
            mes_padrao, ano_padrao, cidade, _ = _ler_mes_ano(celulas_abertura)

        pessoas: list[Pessoa] = []
        if incluir_administrativos and "Funcionários" in abas:
            celulas_func = _mapa_celulas(wb, "Funcionários")
            pessoas += _ler_funcionarios(celulas_func)
        if incluir_docentes and "Professores" in abas:
            celulas_prof = _mapa_celulas(wb, "Professores")
            pessoas += _ler_professores(celulas_prof)

    if somente_com_ponto:
        pessoas = [p for p in pessoas if p.ponto]

    mes_final = mes if mes is not None else mes_padrao
    ano_final = ano if ano is not None else ano_padrao
    if mes_final is None or ano_final is None:
        raise ValueError(
            "Não foi possível determinar mês/ano automaticamente a partir do "
            "arquivo; informe --mes e --ano."
        )

    return LivroPontoConfig(
        escola=escola,
        mes=mes_final,
        ano=ano_final,
        pessoas=pessoas,
        cidade_assinatura=cidade or escola.municipio,
    )
