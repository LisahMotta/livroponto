import datetime as dt

from livroponto.calendario import mes_por_nome, montar_calendario, nome_mes
from livroponto.models import DiaNaoLetivo


def test_nome_mes_e_mes_por_nome_sao_inversos():
    for i in range(1, 13):
        assert mes_por_nome(nome_mes(i)) == i


def test_mes_por_nome_invalido():
    import pytest

    with pytest.raises(ValueError):
        mes_por_nome("mêsinventado")


def test_montar_calendario_abril_2026_tem_30_dias():
    dias = montar_calendario(2026, 4)
    assert len(dias) == 30
    assert dias[0].data == dt.date(2026, 4, 1)
    assert dias[-1].data == dt.date(2026, 4, 30)


def test_feriado_nacional_e_marcado():
    dias = montar_calendario(2026, 4)
    tiradentes = next(d for d in dias if d.dia == 21)
    assert tiradentes.tipo == "FERIADO"
    assert "Tiradentes" in tiradentes.rotulo
    assert not tiradentes.e_dia_normal


def test_fim_de_semana_e_marcado():
    dias = montar_calendario(2026, 4)
    # 2026-04-04 é sábado
    sabado = next(d for d in dias if d.dia == 4)
    assert sabado.tipo == "SABADO"
    domingo = next(d for d in dias if d.dia == 5)
    assert domingo.tipo == "DOMINGO"


def test_dia_util_normal():
    dias = montar_calendario(2026, 4)
    util = next(d for d in dias if d.dia == 2)  # quinta-feira comum
    assert util.tipo == "UTIL"
    assert util.e_dia_normal


def test_excecao_recesso_sobrepoe_dia_util():
    excecoes = [DiaNaoLetivo(mes=4, dia=2, tipo="RECESSO", descricao="Recesso escolar")]
    dias = montar_calendario(2026, 4, excecoes=excecoes)
    dia = next(d for d in dias if d.dia == 2)
    assert dia.tipo == "RECESSO"
    assert not dia.e_dia_normal


def test_excecao_letivo_desmarca_fim_de_semana():
    excecoes = [DiaNaoLetivo(mes=4, dia=4, tipo="LETIVO", descricao="Sábado letivo")]
    dias = montar_calendario(2026, 4, excecoes=excecoes)
    sabado = next(d for d in dias if d.dia == 4)
    assert sabado.tipo == "UTIL"
    assert sabado.e_dia_normal
