"""Monta o PDF do Livro Ponto: termo de abertura, uma folha por servidor com
o calendário do mês (para assinatura manual de entrada/saída) e termo de
encerramento — para administrativos e para docentes, cada grupo como um
"livro" separado dentro do mesmo PDF."""
from __future__ import annotations

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

_LEGENDA = (
    "F = Feriado   R = Recesso escolar   PF = Ponto facultativo   "
    "S = Suspensão de atividades   Sáb/Dom = fim de semana"
)

_SIGLA_TIPO = {
    "FERIADO": "F",
    "RECESSO": "R",
    "PONTO_FACULTATIVO": "PF",
    "SUSPENSAO": "S",
    "SABADO": "SÁBADO",
    "DOMINGO": "DOMINGO",
}

_COL_WIDTHS = [1.0 * cm, 1.7 * cm, 3.1 * cm, 1.6 * cm, 4.0 * cm, 1.6 * cm, 4.0 * cm, 1.6 * cm]
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
    ss.add(ParagraphStyle("Legenda", parent=ss["Normal"], fontSize=7.5, textColor=colors.grey))
    ss.add(ParagraphStyle("CelSit", parent=ss["Normal"], fontSize=6.8, leading=8))
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


def _tabela_pessoa(config: LivroPontoConfig, pessoa: Pessoa, dias, styles) -> list:
    elementos = []
    elementos += _cabecalho_escola(config, styles)
    elementos.append(Spacer(1, 0.25 * cm))

    def linha(esquerda: str, direita: str = "") -> list:
        return [
            Paragraph(esquerda, styles["Normal"]),
            Paragraph(direita, styles["Normal"]) if direita else "",
        ]

    info = [linha(f"<b>Servidor:</b> {pessoa.nome}", f"<b>RG:</b> {pessoa.rg}")]
    cargo_dir = f"<b>Categoria:</b> {pessoa.categoria}" if pessoa.categoria else ""
    info.append(linha(f"<b>Cargo/Função:</b> {pessoa.cargo}", cargo_dir))

    if pessoa.tipo == TipoServidor.ADMINISTRATIVO:
        jornada_txt = f"{pessoa.jornada_semanal:g} h/semana" if pessoa.jornada_semanal else ""
        info.append(linha(f"<b>Jornada:</b> {jornada_txt}", f"<b>Horário:</b> {pessoa.horario_trabalho}"))
        if pessoa.intervalo:
            info.append(linha(f"<b>Intervalo:</b> {pessoa.intervalo}"))
    else:
        jornada_dir = f"<b>Jornada:</b> {pessoa.jornada_codigo}" if pessoa.jornada_codigo else ""
        info.append(linha(f"<b>Disciplina(s):</b> {_truncar(pessoa.disciplinas, 60)}", jornada_dir))
        if pessoa.observacoes:
            info.append(linha(f"<b>Observações:</b> {_truncar(pessoa.observacoes)}"))

    info.append(
        linha(
            f"<b>Mês/Ano:</b> {nome_mes(config.mes).capitalize()}/{config.ano}",
            f"<b>Escola:</b> {config.escola.nome}",
        )
    )

    tabela_info = Table(info, colWidths=[9.3 * cm, 9.3 * cm])
    tabela_info.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    elementos.append(tabela_info)
    elementos.append(Spacer(1, 0.25 * cm))

    cabecalho = ["Dia", "Semana", "Situação", "Hora", "Assinatura", "Hora", "Assinatura", "Obs."]
    linha_grupo = ["", "", "", "ENTRADA", "", "SAÍDA", "", ""]
    dados = [linha_grupo, cabecalho]
    estilos_extra = [
        ("SPAN", (3, 0), (4, 0)),
        ("SPAN", (5, 0), (6, 0)),
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (1, 1)),
        ("SPAN", (2, 0), (2, 1)),
        ("SPAN", (7, 0), (7, 1)),
    ]

    for i, dia in enumerate(dias, start=2):
        if dia.e_dia_normal:
            dados.append([str(dia.dia), dia.semana_abrev, "", "", "", "", "", ""])
        else:
            sigla = _SIGLA_TIPO.get(dia.tipo, dia.tipo)
            rotulo = dia.rotulo or sigla
            texto_situacao = f"{sigla} - {rotulo}" if dia.rotulo and dia.rotulo != sigla else sigla
            dados.append(
                [str(dia.dia), dia.semana_abrev, Paragraph(texto_situacao, styles["CelSit"]), "", "", "", "", ""]
            )
            estilos_extra.append(("SPAN", (3, i), (6, i)))
            estilos_extra.append(("BACKGROUND", (0, i), (-1, i), colors.whitesmoke))

    tabela = Table(dados, colWidths=_COL_WIDTHS, repeatRows=2)
    estilo = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("FONTSIZE", (0, 0), (-1, 1), 8),
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

    elementos.append(Spacer(1, 0.35 * cm))
    elementos.append(Paragraph(_LEGENDA, styles["Legenda"]))
    elementos.append(Spacer(1, 0.5 * cm))
    elementos.append(
        Paragraph(
            "Visto do Superior Imediato: _______________________________________________",
            styles["Normal"],
        )
    )
    return elementos


def _bloco_tipo(config: LivroPontoConfig, tipo: TipoServidor, dias, styles) -> list:
    pessoas = config.pessoas_por_tipo(tipo)
    if not pessoas:
        return []

    elementos: list = []
    numero_folhas = len(pessoas) + 2  # + termo de abertura + termo de encerramento
    elementos += _termo(config, tipo, numero_folhas, encerramento=False, styles=styles)
    elementos.append(PageBreak())

    for pessoa in pessoas:
        elementos.append(KeepTogether(_tabela_pessoa(config, pessoa, dias, styles)))
        elementos.append(PageBreak())

    elementos += _termo(config, tipo, numero_folhas, encerramento=True, styles=styles)
    elementos.append(PageBreak())
    return elementos


def gerar_pdf(
    config: LivroPontoConfig,
    caminho_saida: str | Path,
    uf: str | None = None,
) -> Path:
    """Gera o PDF completo do Livro Ponto para o mês/ano de `config`."""
    if not config.pessoas:
        raise ValueError("Nenhuma pessoa com ponto habilitado para gerar o livro.")

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
