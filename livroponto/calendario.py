"""Monta o calendário de um mês, classificando cada dia (útil, sábado,
domingo, feriado, recesso, ponto facultativo...) para preencher a folha do
livro ponto."""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from .holidays_br import feriados_do_ano, indexar_excecoes
from .models import DiaNaoLetivo

DIAS_SEMANA_ABREV = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
DIAS_SEMANA_NOME = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

MESES_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


def nome_mes(mes: int) -> str:
    return MESES_PT[mes - 1]


def mes_por_nome(nome: str) -> int:
    nome = nome.strip().lower()
    for i, m in enumerate(MESES_PT, start=1):
        if m == nome:
            return i
    raise ValueError(f"Nome de mês desconhecido: {nome!r}")


@dataclass
class DiaInfo:
    data: dt.date
    dia: int
    semana_abrev: str
    semana_nome: str
    tipo: str  # UTIL | SABADO | DOMINGO | FERIADO | RECESSO | PONTO_FACULTATIVO | SUSPENSAO
    rotulo: str  # texto a exibir na folha (ex.: nome do feriado)

    @property
    def e_dia_normal(self) -> bool:
        """Dia em que se espera registro de entrada/saída."""
        return self.tipo == "UTIL"


def montar_calendario(
    ano: int, mes: int, uf: str = "SP", excecoes: list[DiaNaoLetivo] | None = None
) -> list[DiaInfo]:
    feriados = feriados_do_ano(ano, uf=uf)
    excecoes_por_data = indexar_excecoes(excecoes or [], ano)

    _, ultimo_dia = calendar.monthrange(ano, mes)
    dias: list[DiaInfo] = []
    for dia in range(1, ultimo_dia + 1):
        data = dt.date(ano, mes, dia)
        weekday = data.weekday()  # 0=segunda ... 6=domingo
        abrev = DIAS_SEMANA_ABREV[weekday]
        nome = DIAS_SEMANA_NOME[weekday]

        excecao = excecoes_por_data.get(data)
        if excecao is not None and excecao.tipo == "LETIVO":
            # Desmarca um fim de semana/feriado: vira dia útil normal.
            dias.append(DiaInfo(data, dia, abrev, nome, "UTIL", excecao.descricao))
            continue

        if excecao is not None:
            dias.append(
                DiaInfo(data, dia, abrev, nome, excecao.tipo, excecao.descricao)
            )
            continue

        if data in feriados:
            dias.append(DiaInfo(data, dia, abrev, nome, "FERIADO", feriados[data]))
            continue

        if weekday == 5:
            dias.append(DiaInfo(data, dia, abrev, nome, "SABADO", "SÁBADO"))
            continue
        if weekday == 6:
            dias.append(DiaInfo(data, dia, abrev, nome, "DOMINGO", "DOMINGO"))
            continue

        dias.append(DiaInfo(data, dia, abrev, nome, "UTIL", ""))

    return dias
