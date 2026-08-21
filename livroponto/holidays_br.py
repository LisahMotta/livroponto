"""Feriados nacionais e estaduais (via biblioteca `holidays`) + exceções de
calendário escolar informadas manualmente (recesso, ponto facultativo,
sábado letivo etc.)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import holidays

from .models import DiaNaoLetivo


def feriados_do_ano(ano: int, uf: str = "SP") -> dict[dt.date, str]:
    """Retorna {data: nome_do_feriado} para feriados nacionais + estaduais."""
    br = holidays.Brazil(subdiv=uf, years=[ano])
    return dict(br.items())


def carregar_dias_excecao(caminho: str | Path) -> list[DiaNaoLetivo]:
    """Lê um JSON de exceções de calendário escolar.

    Formato esperado::

        [
          {"mes": 4, "dia": 19, "tipo": "PONTO_FACULTATIVO", "descricao": "Aniversário da cidade"},
          {"mes": 7, "dia": 1,  "tipo": "RECESSO", "descricao": "Recesso escolar"},
          {"mes": 6, "dia": 15, "tipo": "LETIVO", "descricao": "Sábado letivo (reposição)"}
        ]

    tipo pode ser: FERIADO, RECESSO, PONTO_FACULTATIVO, SUSPENSAO, ou LETIVO
    (este último "desmarca" um sábado/domingo, tornando-o dia útil normal —
    útil para sábados letivos de reposição).
    """
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return [
        DiaNaoLetivo(
            mes=int(item["mes"]),
            dia=int(item["dia"]),
            tipo=str(item["tipo"]).upper(),
            descricao=item.get("descricao", ""),
        )
        for item in dados
    ]


def indexar_excecoes(
    excecoes: Iterable[DiaNaoLetivo], ano: int
) -> dict[dt.date, DiaNaoLetivo]:
    return {dt.date(ano, e.mes, e.dia): e for e in excecoes}
