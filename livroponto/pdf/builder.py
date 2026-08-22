"""Monta o PDF do Livro Ponto: termo de abertura, para cada servidor uma
folha de ponto (calendário do mês, para assinatura manual de entrada/saída)
seguida da folha de consolidação (verso), e termo de encerramento — para
administrativos e para docentes, cada grupo como um "livro" separado dentro
do mesmo PDF.

O layout da folha de ponto e da folha de consolidação segue o modelo real
usado pela rede estadual de SP (abas "Livro-Adm" e "Livro-Adm-Cons" da
planilha original): cabeçalho "GOVERNO DO ESTADO DE SÃO PAULO / SECRETARIA
DE ESTADO DA EDUCAÇÃO", legenda de cores (recesso/não letivo/feriado), os
mesmos rótulos de campo, e uma coluna de "Visto do Superior Imediato" por
dia (não só uma linha única no fim da folha)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..calendario import montar_calendario, nome_mes
from ..models import LivroPontoConfig, Pessoa, TipoServidor

_ROTULO_TIPO = {
    TipoServidor.ADMINISTRATIVO: "DO PESSOAL ADMINISTRATIVO",
    TipoServidor.DOCENTE: "DO PESSOAL DOCENTE",
}

_DIAS_SEMANA_COMPLETO = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]

_SIGLA_TIPO = {
    "FERIADO": "FERIADO",
    "RECESSO": "RECESSO",
    "PONTO_FACULTATIVO": "PONTO FACULTATIVO",
    "SUSPENSAO": "NÃO LETIVO",
    "SABADO": "SÁBADO",
    "DOMINGO": "DOMINGO",
}

# Cor de fundo de cada tipo de dia na tabela — mesma ideia da legenda por
# cor (recesso/não letivo/feriado) da planilha original.
_COR_SITUACAO = {
    "FERIADO": colors.Color(1, 0.85, 0.85),
    "RECESSO": colors.Color(0.83, 0.90, 1),
    "SUSPENSAO": colors.Color(0.90, 0.90, 0.90),
    "PONTO_FACULTATIVO": colors.Color(1, 0.96, 0.78),
    "SABADO": colors.whitesmoke,
    "DOMINGO": colors.whitesmoke,
}

_LEGENDA_ITENS = [
    ("RECESSO", _COR_SITUACAO["RECESSO"]),
    ("NÃO LETIVO", _COR_SITUACAO["SUSPENSAO"]),
    ("FERIADO", _COR_SITUACAO["FERIADO"]),
    ("PONTO FACULTATIVO", _COR_SITUACAO["PONTO_FACULTATIVO"]),
]

_COL_WIDTHS = [
    0.9 * cm,  # Dia
    2.3 * cm,  # Semana
    1.5 * cm,  # Entrada - Hora
    3.3 * cm,  # Entrada - Assinatura
    1.5 * cm,  # Saída - Hora
    3.3 * cm,  # Saída - Assinatura
    2.9 * cm,  # Observações
    2.9 * cm,  # Visto do Superior Imediato
]
_MARGEM = 1.2 * cm
_LIMITE_OBSERVACAO = 170


def _truncar(texto: str, limite: int = _LIMITE_OBSERVACAO) -> str:
    """Encurta textos livres (ex.: observações) para não estourar a altura
    da folha; o registro completo continua disponível na planilha de origem."""
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rstrip() + "…"


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("TituloLivro", parent=ss["Title"], fontSize=16, spaceAfter=6))
    ss.add(ParagraphStyle("SubTitulo", parent=ss["Heading2"], alignment=1, spaceAfter=10))
    ss.add(ParagraphStyle("Corpo", parent=ss["Normal"], fontSize=11, leading=16))
    ss.add(ParagraphStyle("CorpoCentro", parent=ss["Normal"], fontSize=11, leading=16, alignment=1))
    ss.add(ParagraphStyle("Rotulo", parent=ss["Normal"], fontSize=9, textColor=colors.grey))
    ss.add(ParagraphStyle("Legenda", parent=ss["Normal"], fontSize=7.5))
    ss.add(ParagraphStyle("CelSit", parent=ss["Normal"], fontSize=6.8, leading=8))
    ss.add(
        ParagraphStyle(
            "GovernoTitulo", parent=ss["Normal"], fontSize=10.5, alignment=1, fontName="Helvetica-Bold"
        )
    )
    ss.add(ParagraphStyle("Campo", parent=ss["Normal"], fontSize=9.3, leading=13))
    return ss


def _cabecalho_escola(config: LivroPontoConfig, styles) -> list:
    escola = config.escola
    linhas = [Paragraph(escola.nome or "(Nome da escola não informado)", styles["Heading3"])]
    detalhes = []
    if escola.diretoria_ensino:
        detalhes.append(f"Diretoria de Ensino: {escola.diretoria_ensino}")
    if escola.municipio:
        detalhes.append(f"Município: {escola.municipio}")
    if escola.codigo_cie:
        detalhes.append(f"Código CIE: {escola.codigo_cie}")
    if detalhes:
        linhas.append(Paragraph(" | ".join(detalhes), styles["Rotulo"]))
    return linhas


def _cabecalho_governo(config: LivroPontoConfig, styles) -> list:
    """Cabeçalho padrão da folha de ponto e da folha de consolidação,
    igual ao das abas Livro-Adm/Livro-Adm-Cons da planilha original."""
    escola = config.escola
    elementos = [
        Paragraph("GOVERNO DO ESTADO DE SÃO PAULO", styles["GovernoTitulo"]),
        Paragraph("SECRETARIA DE ESTADO DA EDUCAÇÃO", styles["GovernoTitulo"]),
        Spacer(1, 0.15 * cm),
    ]

    linha_legenda = []
    estilo_legenda = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 1)]
    for i, (rotulo, cor) in enumerate(_LEGENDA_ITENS):
        col = i * 2
        linha_legenda.append("")
        linha_legenda.append(Paragraph(rotulo, styles["Legenda"]))
        estilo_legenda.append(("BACKGROUND", (col, 0), (col, 0), cor))
        estilo_legenda.append(("BOX", (col, 0), (col, 0), 0.4, colors.black))
    tabela_legenda = Table(
        [linha_legenda],
        colWidths=[0.35 * cm, 2.6 * cm] * len(_LEGENDA_ITENS),
    )
    tabela_legenda.setStyle(TableStyle(estilo_legenda))
    elementos.append(tabela_legenda)
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(f"<b>Unidade:</b> {escola.nome}", styles["Campo"]))
    elementos.append(
        Paragraph(
            f"<b>REGISTRO DE PONTO — Mês/Ano:</b> {nome_mes(config.mes).capitalize()} / {config.ano}",
            styles["Campo"],
        )
    )
    elementos.append(Spacer(1, 0.2 * cm))
    return elementos


def _termo(
    config: LivroPontoConfig,
    tipo: TipoServidor,
    numero_folhas: int,
    encerramento: bool,
    styles,
) -> list:
    escola = config.escola
    elementos = []
    elementos += _cabecalho_escola(config, styles)
    elementos.append(Spacer(1, 0.6 * cm))
    elementos.append(Paragraph("LIVRO PONTO", styles["TituloLivro"]))
    elementos.append(
        Paragraph(_ROTULO_TIPO[tipo], styles["SubTitulo"])
    )
    elementos.append(
        Paragraph(
            f"Referente a {nome_mes(config.mes).upper()} de {config.ano}",
            styles["CorpoCentro"],
        )
    )
    elementos.append(Spacer(1, 1.2 * cm))

    titulo_termo = "Termo de Encerramento" if encerramento else "Termo de Abertura"
    elementos.append(Paragraph(titulo_termo, styles["Heading2"]))
    elementos.append(Spacer(1, 0.4 * cm))

    if not encerramento:
        texto = (
            f"Contém este livro ( {numero_folhas} ) folhas, por mim abertas, "
            f"numeradas e rubricadas, e destina-se ao registro do Ponto "
            f"{_ROTULO_TIPO[tipo].lower()} da {escola.nome}."
        )
    else:
        texto = (
            f"Contém este livro ( {numero_folhas} ) folhas, por mim abertas, "
            f"numeradas e rubricadas e encerradas, e se destinou ao uso no "
            f"termo de abertura indicado."
        )
    elementos.append(Paragraph(texto, styles["Corpo"]))
    elementos.append(Spacer(1, 2.0 * cm))

    cidade = config.cidade_assinatura or escola.municipio
    elementos.append(
        Paragraph(
            f"{cidade}, ____ de {nome_mes(config.mes)} de {config.ano}.",
            styles["Corpo"],
        )
    )
    elementos.append(Spacer(1, 2.0 * cm))
    elementos.append(Paragraph("_" * 50, styles["CorpoCentro"]))
    elementos.append(Paragraph("Direção da Unidade Escolar", styles["CorpoCentro"]))
    return elementos


def _campos_pessoa(pessoa: Pessoa, styles) -> list:
    """Campos de identificação do servidor, nos mesmos rótulos e na mesma
    ordem da aba Livro-Adm original."""
    P = lambda t: Paragraph(t, styles["Campo"])  # noqa: E731
    linhas = [
        P(f"<b>SERVIDOR:</b> {pessoa.nome} &nbsp;&nbsp;&nbsp; <b>RG:</b> {pessoa.rg}"),
        P(f"<b>CARGO/FUNÇÃO:</b> {pessoa.cargo}"),
    ]
    if pessoa.tipo == TipoServidor.ADMINISTRATIVO:
        jornada_txt = f"{pessoa.jornada_semanal:g}" if pessoa.jornada_semanal else "____"
        linhas.append(
            P(
                f"<b>JORNADA DE TRABALHO:</b> {jornada_txt} HORAS/SEMANAIS "
                f"&nbsp;&nbsp;&nbsp; <b>REGIME DE PLANTÃO:</b> _______________"
            )
        )
        horario = pessoa.horario_trabalho or "DAS ______ ÀS ______"
        linhas.append(P(f"<b>HORÁRIO DE TRABALHO:</b> {horario}"))
        intervalo = pessoa.intervalo or "DAS ______ ÀS ______"
        linhas.append(
            P(
                f"<b>INTERVALO DE ALMOÇO E DESCANSO:</b> {intervalo} "
                f"&nbsp;&nbsp;&nbsp; <b>HORÁRIO DE ESTUDANTE:</b> _______________"
            )
        )
    else:
        if pessoa.categoria:
            linhas.append(P(f"<b>CATEGORIA:</b> {pessoa.categoria}"))
        if pessoa.disciplinas:
            linhas.append(P(f"<b>DISCIPLINA(S):</b> {_truncar(pessoa.disciplinas, 90)}"))
        if pessoa.jornada_codigo:
            linhas.append(P(f"<b>JORNADA:</b> {pessoa.jornada_codigo}"))
        if pessoa.observacoes:
            linhas.append(P(f"<b>OBSERVAÇÕES:</b> {_truncar(pessoa.observacoes)}"))
    return linhas


def _folha_ponto(config: LivroPontoConfig, pessoa: Pessoa, dias, styles) -> list:
    elementos = _cabecalho_governo(config, styles)
    elementos += _campos_pessoa(pessoa, styles)
    elementos.append(Spacer(1, 0.2 * cm))

    # Nas colunas que mesclam as duas linhas do cabeçalho (Dia, Semana,
    # Observações, Visto), o texto tem que ir na linha de cima: numa célula
    # mesclada o reportlab exibe o conteúdo da célula âncora (topo/esquerda).
    linha_grupo = ["Dia", "Semana", "ENTRADA", "", "SAÍDA", "", "Observações", "Visto do\nSuperior Imediato"]
    cabecalho = ["", "", "Hora", "Assinatura", "Hora", "Assinatura", "", ""]
    dados = [linha_grupo, cabecalho]
    estilos_extra = [
        ("SPAN", (2, 0), (3, 0)),
        ("SPAN", (4, 0), (5, 0)),
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (6, 0), (6, 1)),
        ("SPAN", (7, 0), (7, 1)),
    ]

    for i, dia in enumerate(dias, start=2):
        semana_completa = _DIAS_SEMANA_COMPLETO[dia.data.weekday()]
        if dia.e_dia_normal:
            dados.append([str(dia.dia), semana_completa, "", "", "", "", "", ""])
        else:
            sigla = _SIGLA_TIPO.get(dia.tipo, dia.tipo)
            texto_situacao = f"{sigla} - {dia.rotulo}" if dia.rotulo and dia.rotulo != sigla else sigla
            dados.append(
                [str(dia.dia), semana_completa, Paragraph(texto_situacao, styles["CelSit"]), "", "", "", "", ""]
            )
            estilos_extra.append(("SPAN", (2, i), (5, i)))
            cor = _COR_SITUACAO.get(dia.tipo, colors.whitesmoke)
            estilos_extra.append(("BACKGROUND", (0, i), (5, i), cor))

    tabela = Table(dados, colWidths=_COL_WIDTHS, repeatRows=2)
    estilo = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 7.3),
            ("FONTSIZE", (0, 0), (-1, 1), 7.8),
            ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("BACKGROUND", (0, 0), (-1, 1), colors.lightgrey),
        ]
        + estilos_extra
    )
    tabela.setStyle(estilo)
    elementos.append(tabela)
    return elementos


def _folha_consolidacao(config: LivroPontoConfig, pessoa: Pessoa, dias, styles) -> list:
    """Verso da folha de ponto: mesmo cabeçalho, título CONSOLIDAÇÃO, um
    resumo do mês (dias úteis/não úteis) e o fecho com data e assinatura do
    superior imediato — igual à aba Livro-Adm-Cons da planilha original."""
    elementos = _cabecalho_governo(config, styles)
    elementos.append(Paragraph(f"SERVIDOR: {pessoa.nome}", styles["Campo"]))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph("CONSOLIDAÇÃO", styles["Heading2"]))
    elementos.append(Spacer(1, 0.3 * cm))

    contagem: dict[str, int] = {}
    for dia in dias:
        contagem[dia.tipo] = contagem.get(dia.tipo, 0) + 1
    dias_uteis = contagem.get("UTIL", 0)
    dias_nao_uteis = len(dias) - dias_uteis

    resumo = [
        ["Dias do mês", str(len(dias))],
        ["Dias úteis (sujeitos a registro de ponto)", str(dias_uteis)],
        ["Sábados/domingos", str(contagem.get("SABADO", 0) + contagem.get("DOMINGO", 0))],
        ["Feriados", str(contagem.get("FERIADO", 0))],
    ]
    if contagem.get("RECESSO"):
        resumo.append(["Recesso escolar", str(contagem["RECESSO"])])
    if contagem.get("PONTO_FACULTATIVO"):
        resumo.append(["Ponto facultativo", str(contagem["PONTO_FACULTATIVO"])])
    if contagem.get("SUSPENSAO"):
        resumo.append(["Suspensão de atividades (não letivo)", str(contagem["SUSPENSAO"])])
    resumo.append(["Total de dias não úteis", str(dias_nao_uteis)])

    tabela_resumo = Table(resumo, colWidths=[10 * cm, 3 * cm])
    tabela_resumo.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 0.6 * cm))
    elementos.append(
        Paragraph("Observações / anotações do superior imediato:", styles["Campo"])
    )
    elementos.append(Spacer(1, 0.1 * cm))

    # Espaço em branco pautado, igual ao usado na planilha original para
    # anotações manuscritas.
    linhas_em_branco = [[""] for _ in range(10)]
    tabela_branco = Table(linhas_em_branco, colWidths=[17.5 * cm], rowHeights=[0.9 * cm] * 10)
    tabela_branco.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.grey),
            ]
        )
    )
    elementos.append(tabela_branco)

    elementos.append(Spacer(1, 1.0 * cm))
    elementos.append(Paragraph("Data:  ____ / ____ / ________", styles["Corpo"]))
    elementos.append(Spacer(1, 1.6 * cm))
    elementos.append(Paragraph("_" * 55, styles["CorpoCentro"]))
    elementos.append(Paragraph("Assinatura do Superior Imediato ou Responsável", styles["CorpoCentro"]))
    return elementos


def _bloco_tipo(config: LivroPontoConfig, tipo: TipoServidor, dias, styles) -> list:
    pessoas = config.pessoas_por_tipo(tipo)
    if not pessoas:
        return []

    elementos: list = []
    # duas folhas por pessoa: a folha de ponto e o verso (folha de consolidação).
    numero_folhas = len(pessoas) * 2 + 2  # + termo de abertura + termo de encerramento
    elementos += _termo(config, tipo, numero_folhas, encerramento=False, styles=styles)
    elementos.append(PageBreak())

    for pessoa in pessoas:
        elementos.append(KeepTogether(_folha_ponto(config, pessoa, dias, styles)))
        elementos.append(PageBreak())
        elementos.append(KeepTogether(_folha_consolidacao(config, pessoa, dias, styles)))
        elementos.append(PageBreak())

    elementos += _termo(config, tipo, numero_folhas, encerramento=True, styles=styles)
    elementos.append(PageBreak())
    return elementos


def gerar_pdf(
    config: LivroPontoConfig,
    caminho_saida: str | Path,
    uf: str | None = None,
) -> Path:
    """Gera o PDF completo do Livro Ponto para o mês/ano de `config`.

    Só entram no PDF as pessoas com `ponto=True` — quem tem `ponto=False`
    fica no cadastro (para editar depois) mas não ganha folha impressa.
    """
    pessoas_com_ponto = [p for p in config.pessoas if p.ponto]
    if not pessoas_com_ponto:
        raise ValueError("Nenhuma pessoa com ponto habilitado para gerar o livro.")
    config = replace(config, pessoas=pessoas_com_ponto)

    dias = montar_calendario(
        config.ano, config.mes, uf=uf or config.uf, excecoes=config.dias_excecao
    )
    styles = _styles()

    doc = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        leftMargin=_MARGEM,
        rightMargin=_MARGEM,
        topMargin=_MARGEM,
        bottomMargin=_MARGEM,
        title=f"Livro Ponto - {nome_mes(config.mes)} {config.ano}",
    )

    elementos: list = []
    elementos += _bloco_tipo(config, TipoServidor.ADMINISTRATIVO, dias, styles)
    elementos += _bloco_tipo(config, TipoServidor.DOCENTE, dias, styles)

    if elementos and isinstance(elementos[-1], PageBreak):
        elementos.pop()

    doc.build(elementos)
    return Path(caminho_saida)
