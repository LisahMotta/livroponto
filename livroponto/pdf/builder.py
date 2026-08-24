"""Monta o PDF do Livro Ponto: termo de abertura, para cada servidor uma
folha de ponto seguida da folha de consolidação (verso), e termo de
encerramento — para administrativos e para docentes, cada grupo como um
"livro" separado dentro do mesmo PDF.

O layout da folha de ponto e da folha de consolidação replica o formulário
oficial realmente usado (brasão do Estado de São Paulo, cabeçalho "GOVERNO
DO ESTADO DE SÃO PAULO / SECRETARIA DE ESTADO DA EDUCAÇÃO", os mesmos
campos/rótulos e a seção "INFORMAÇÕES FINANCEIRAS" no rodapé). Sábados,
domingos, feriados e exceções cadastradas (recesso, ponto facultativo etc.)
são marcados automaticamente na tabela de dias; dias úteis ficam em branco
para preenchimento manual. As observações cadastradas para cada servidor
(ex.: afastamentos) saem impressas na folha de consolidação."""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..calendario import montar_calendario, nome_mes
from ..models import LivroPontoConfig, Pessoa, TipoServidor, chave_ordenacao_rg

# Qualificação do tipo de servidor, do jeito que sai no formulário oficial
# (fotografado pelo usuário): "registro do Ponto do Pessoal Administrativo
# da ..."/"... do Pessoal da Equipe Gestora da ...". Não usa "trio gestor"
# em lugar nenhum — o nome oficial do formulário é "Equipe Gestora".
_QUALIFICACAO_TIPO = {
    TipoServidor.ADMINISTRATIVO: "Pessoal Administrativo",
    TipoServidor.DOCENTE: "Pessoal Docente",
    TipoServidor.GESTAO: "Pessoal da Equipe Gestora",
}

# Mesma qualificação, em caixa alta, para o subtítulo abaixo de "LIVRO
# PONTO" na página do termo.
_ROTULO_TIPO = {tipo: f"DO {qualificacao.upper()}" for tipo, qualificacao in _QUALIFICACAO_TIPO.items()}

# Tipos cuja folha usa o formato administrativo (folha de ponto tradicional
# + verso de consolidação) — o trio gestor clocka ponto do mesmo jeito que o
# administrativo, só entra num livro separado.
_TIPOS_FOLHA_PONTO = {TipoServidor.ADMINISTRATIVO, TipoServidor.GESTAO}

_MARGEM = 1.0 * cm
_MARGEM_ESQUERDA = 3.0 * cm  # mais larga que as demais, para dar espaço à encadernação
_LARGURA_CONTEUDO = A4[0] - _MARGEM_ESQUERDA - _MARGEM
_LIMITE_OBSERVACAO = 170
_LOGO_SP = Path(__file__).resolve().parent / "assets" / "brasao_sp.png"

# Proporções de coluna da tabela de dias (Dia | Entrada Hora/Assinatura |
# Saída Hora/Assinatura | Observações | Visto), tiradas do formulário real —
# Observações reduzida e Assinatura (Entrada/Saída) ampliadas a pedido, já
# que a assinatura precisa de mais espaço do que as observações no dia a dia.
_FRACOES_TABELA_DIAS = [0.0438, 0.0808, 0.2150, 0.0808, 0.2150, 0.2000, 0.1639]

# Proporções de coluna da seção "Informações financeiras" (6 colunas).
_FRACOES_FINANCEIRO = [0.1573, 0.2043, 0.1195, 0.2043, 0.2043, 0.1102]

# Rótulo e cor de fundo usados para marcar automaticamente sábados,
# domingos, feriados e exceções cadastradas (recesso, ponto facultativo
# etc.) na tabela de dias da folha de ponto administrativa.
_SIGLA_TIPO = {
    "FERIADO": "FERIADO",
    "RECESSO": "RECESSO",
    "PONTO_FACULTATIVO": "PONTO FACULTATIVO",
    "SUSPENSAO": "NÃO LETIVO",
    "SABADO": "SÁBADO",
    "DOMINGO": "DOMINGO",
}
_COR_SITUACAO = {
    "FERIADO": colors.Color(1, 0.85, 0.85),
    "RECESSO": colors.Color(0.83, 0.90, 1),
    "SUSPENSAO": colors.Color(0.90, 0.90, 0.90),
    "PONTO_FACULTATIVO": colors.Color(1, 0.96, 0.78),
    "SABADO": colors.whitesmoke,
    "DOMINGO": colors.whitesmoke,
}

# Abreviação do dia da semana (convenção "2ª feira" = segunda) usada na
# coluna "Sem." da Folha de Frequência do docente.
_ABREV_SEMANA_FREQ = {0: "2ª", 1: "3ª", 2: "4ª", 3: "5ª", 4: "6ª", 5: "S", 6: "D"}


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
    ss.add(
        ParagraphStyle(
            "GovernoTitulo", parent=ss["Normal"], fontSize=8, alignment=1, fontName="Helvetica-Bold", leading=10
        )
    )
    ss.add(ParagraphStyle("PagRotulo", parent=ss["Normal"], fontSize=9, alignment=2))
    ss.add(ParagraphStyle("Campo", parent=ss["Normal"], fontSize=8, leading=11))
    # Nome do servidor maior e em negrito, bem destacado dos demais campos
    # (RG, cargo etc.) — a pedido, pra ficar mais legível na folha impressa.
    ss.add(
        ParagraphStyle("CampoNome", parent=ss["Campo"], fontSize=13, leading=16, fontName="Helvetica-Bold")
    )
    ss.add(ParagraphStyle("CelTabela", parent=ss["Normal"], fontSize=8, alignment=1, leading=9))
    ss.add(ParagraphStyle("CelTabelaPequena", parent=ss["Normal"], fontSize=7.3, alignment=1, leading=8.3))
    ss.add(ParagraphStyle("ConsolidacaoTitulo", parent=ss["Normal"], fontSize=12, fontName="Helvetica-Bold"))
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

    # A quantidade de folhas fica em branco tanto no termo de abertura quanto
    # no de encerramento, para preenchimento manual — pode mudar durante o
    # mês (servidor incluído/excluído do livro) — com espaço tanto para o
    # número quanto para escrever por extenso, igual ao formulário oficial
    # ("Contém este livro 07 (Sete) folhas...").
    _BLANK_FOLHAS = "_____ ( _____________________ )"
    if not encerramento:
        texto = (
            f"Contém este livro {_BLANK_FOLHAS} folhas, por mim abertas, "
            f"numeradas e rubricadas, e destina-se ao registro do Ponto "
            f"do {_QUALIFICACAO_TIPO[tipo]} da {escola.nome}."
        )
    else:
        texto = (
            f"Contém este livro {_BLANK_FOLHAS} folhas, por mim abertas, "
            "numeradas e rubricadas e encerradas, e se destinou ao uso no "
            "termo de abertura indicado."
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
    nome_diretor = config.nome_diretor()
    if nome_diretor:
        elementos.append(Paragraph(nome_diretor, styles["CorpoCentro"]))
    elementos.append(Paragraph("Direção da Unidade Escolar", styles["CorpoCentro"]))
    return elementos


def _col_widths(fracoes: list[float]) -> list[float]:
    return [f * _LARGURA_CONTEUDO for f in fracoes]


def _cabecalho_formulario(config: LivroPontoConfig, styles, numero_pagina: int | None) -> Table:
    """Cabeçalho do formulário oficial: brasão à esquerda, "GOVERNO DO
    ESTADO DE SÃO PAULO / SECRETARIA DE ESTADO DA EDUCAÇÃO / Unidade: ... /
    Registro de Ponto Mês/Ano: ..." ao centro, e "PAG: <número>" no canto
    superior direito — só na folha de ponto (uma página por servidor dentro
    do livro), não no verso de consolidação, que não é numerado."""
    escola = config.escola
    texto_central = Paragraph(
        "GOVERNO DO ESTADO DE SÃO PAULO<br/>"
        "SECRETARIA DE ESTADO DA EDUCAÇÃO<br/>"
        f"UNIDADE: {escola.nome}<br/>"
        f"REGISTRO DE PONTO MÊS/ANO: {nome_mes(config.mes).upper()} DE {config.ano}",
        styles["GovernoTitulo"],
    )
    pag = Paragraph(f"PAG: {numero_pagina}", styles["PagRotulo"]) if numero_pagina is not None else ""

    try:
        logo = Image(str(_LOGO_SP), width=1.55 * cm, height=1.7 * cm)
    except Exception:  # noqa: BLE001 — sem o brasão, segue sem imagem
        logo = ""

    largura_logo = 2.0 * cm
    largura_pag = 2.8 * cm
    largura_central = _LARGURA_CONTEUDO - largura_logo - largura_pag

    # Numa célula mesclada o reportlab exibe o conteúdo da célula âncora
    # (topo/esquerda do SPAN) — por isso a logo vai na linha 0, não na 1.
    tabela = Table(
        [[logo, pag], ["", texto_central]],
        colWidths=[largura_logo, largura_central + largura_pag],
        rowHeights=[0.5 * cm, 1.9 * cm],
    )
    tabela.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (0, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LINEBELOW", (0, 0), (0, 0), 0.6, colors.black),
            ]
        )
    )
    return tabela


def _linha_campo(rotulo: str, valor: str) -> str:
    return f"<b>{rotulo}:</b> {valor}" if valor else f"<b>{rotulo}:</b>"


def _bloco_dados_pessoa(pessoa: Pessoa, styles) -> Table:
    """Bloco "SERVIDOR / CARGO / JORNADA / HORÁRIO / INTERVALO", nos mesmos
    rótulos e na mesma ordem do formulário original."""
    P = lambda t: Paragraph(t, styles["Campo"])  # noqa: E731
    P_nome = lambda t: Paragraph(t, styles["CampoNome"])  # noqa: E731

    linhas = [
        [P_nome(_linha_campo("SERVIDOR", pessoa.nome)), P(_linha_campo("RG", pessoa.rg))],
        [P(_linha_campo("CARGO/FUNÇÃO", pessoa.cargo)), ""],
    ]
    if pessoa.tipo in _TIPOS_FOLHA_PONTO:
        jornada_txt = f"{pessoa.jornada_semanal:g} Horas" if pessoa.jornada_semanal else ""
        linhas.append(
            [P(_linha_campo("JORNADA DE TRABALHO", jornada_txt)), P("<b>REGIME DE PLANTÃO:</b>")]
        )
        linhas.append([P(f"<b>HORÁRIO DE TRABALHO:</b> {pessoa.horario_trabalho}"), ""])
        linhas.append(
            [
                P(f"<b>INTERVALO DE ALMOÇO E DESCANSO:</b> {pessoa.intervalo}"),
                P("<b>HORÁRIO DE ESTUDANTE (SIM/NÃO):</b>"),
            ]
        )
    else:
        linhas.append([P(_linha_campo("CATEGORIA", pessoa.categoria)), ""])
        linhas.append(
            [
                P(_linha_campo("DISCIPLINA(S)", _truncar(pessoa.disciplinas, 80))),
                P(_linha_campo("JORNADA", pessoa.jornada_codigo)),
            ]
        )
        if pessoa.observacoes:
            linhas.append([P(_linha_campo("OBSERVAÇÕES", _truncar(pessoa.observacoes))), ""])

    largura_esq = 0.722 * _LARGURA_CONTEUDO
    tabela = Table(linhas, colWidths=[largura_esq, _LARGURA_CONTEUDO - largura_esq])
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
            ]
        )
    )
    return tabela


def _tabela_dias(dias, styles) -> Table:
    """A grade "Dia | Entrada | Saída | Observações | Visto do superior
    imediato". Sábados, domingos, feriados e exceções cadastradas (recesso,
    ponto facultativo etc.) são marcados automaticamente — fundo colorido e
    rótulo, ocupando o espaço de Entrada/Saída; dias úteis ficam em branco
    para preenchimento manual, como no formulário original."""
    linha_grupo = ["Dia", "Entrada", "", "Saída", "", "Observações", "Visto do superior\nimediato"]
    cabecalho = ["", "Hora", "Assinatura", "Hora", "Assinatura", "", ""]
    dados = [linha_grupo, cabecalho]
    estilos_extra = [
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (3, 0), (4, 0)),
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (5, 0), (5, 1)),
        ("SPAN", (6, 0), (6, 1)),
    ]
    for i, dia in enumerate(dias, start=2):
        if dia.e_dia_normal:
            dados.append([str(dia.dia), "", "", "", "", "", ""])
            continue
        sigla = _SIGLA_TIPO.get(dia.tipo, dia.tipo)
        texto = f"{sigla} - {dia.rotulo}" if dia.rotulo and dia.rotulo != sigla else sigla
        dados.append([str(dia.dia), Paragraph(texto, styles["CelTabelaPequena"]), "", "", "", "", ""])
        estilos_extra.append(("SPAN", (1, i), (4, i)))
        cor = _COR_SITUACAO.get(dia.tipo, colors.whitesmoke)
        estilos_extra.append(("BACKGROUND", (0, i), (4, i), cor))

    tabela = Table(dados, colWidths=_col_widths(_FRACOES_TABELA_DIAS), repeatRows=2)
    tabela.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("BACKGROUND", (0, 0), (-1, 1), colors.lightgrey),
            ]
            + estilos_extra
        )
    )
    return tabela


def _texto_feriados_excecoes(dias, mes: int) -> str:
    """Lista, em uma linha só, os feriados e exceções cadastradas
    (recesso, ponto facultativo, suspensão) que caíram no mês — não
    inclui sábado/domingo comum, só o que sai marcado como exceção na
    tabela de dias da folha de ponto."""
    itens = []
    for dia in dias:
        if dia.tipo not in ("FERIADO", "RECESSO", "PONTO_FACULTATIVO", "SUSPENSAO"):
            continue
        sigla = _SIGLA_TIPO.get(dia.tipo, dia.tipo)
        descricao = f" ({dia.rotulo})" if dia.rotulo and dia.rotulo != sigla else ""
        itens.append(f"{dia.dia:02d}/{mes:02d} - {sigla}{descricao}")
    return "; ".join(itens)


def _secao_financeira(pessoa: Pessoa, styles) -> Table:
    """Rodapé "INFORMAÇÕES FINANCEIRAS" (férias, GTN, ACA, serviço
    extraordinário, substituição eventual, vale transporte). O período de
    férias sai preenchido automaticamente se cadastrado para o servidor;
    os demais campos ficam em branco para preenchimento manual, igual ao
    formulário original."""
    P = lambda t: Paragraph(t, styles["CelTabelaPequena"])  # noqa: E731
    ferias_de = pessoa.ferias_inicio or "___/___/___"
    ferias_ate = pessoa.ferias_fim or "___/___/___"
    dados = [
        ["INFORMAÇÕES FINANCEIRAS", "", "", "", "", ""],
        [
            P("<b>FÉRIAS</b>"),
            P(f"DE {ferias_de}<br/>ATÉ {ferias_ate}"),
            P("MÉDIA DE GTN"),
            P("<b>ACA</b>"),
            P("DE ___/___/___<br/>ATÉ ___/___/___"),
            P("QTDE."),
        ],
        [
            P("<b>GTN</b>"),
            P("DE ___/___/___<br/>ATÉ ___/___/___"),
            P("20% &nbsp;&nbsp; 10%"),
            P("SERVIÇO<br/>EXTRAORDINÁRIO"),
            P("DE ___/___/___<br/>ATÉ ___/___/___"),
            P("QTDE."),
        ],
        [
            P("<b>SUBSTITUIÇÃO<br/>EVENTUAL</b>"),
            P("PERÍODO<br/>___/___/___ ATÉ ___/___/___"),
            "",
            P("CARGO/FUNÇÃO SUBSTITUÍDA:<br/>_____________________"),
            P("VALE TRANSPORTE - CLT (SIM/NÃO)"),
            "",
        ],
    ]
    larguras = _col_widths(_FRACOES_FINANCEIRO)
    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(
        TableStyle(
            [
                ("GRID", (0, 1), (-1, -1), 0.4, colors.black),
                ("BOX", (0, 0), (-1, 0), 0.4, colors.black),
                ("SPAN", (0, 0), (-1, 0)),
                ("SPAN", (1, 3), (2, 3)),
                ("SPAN", (4, 3), (5, 3)),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabela


def _rodape_assinaturas(styles) -> Table:
    """Linha de assinaturas, com um espaço em branco real entre a do
    servidor e a do superior imediato — para não parecerem "coladas"."""
    linhas = [
        ["_" * 27, "", "_" * 27, "", ""],
        [
            Paragraph("ASSINATURA DO SERVIDOR", styles["CelTabelaPequena"]),
            "",
            Paragraph("ASSINATURA DO SUPERIOR IMEDIATO", styles["CelTabelaPequena"]),
            "",
            Paragraph("DATA: ___/___/_____", styles["Campo"]),
        ],
    ]
    larguras = [
        _LARGURA_CONTEUDO * 0.35,
        _LARGURA_CONTEUDO * 0.05,
        _LARGURA_CONTEUDO * 0.35,
        _LARGURA_CONTEUDO * 0.03,
        _LARGURA_CONTEUDO * 0.22,
    ]
    tabela = Table(linhas, colWidths=larguras)
    tabela.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
                ("ALIGN", (4, 0), (4, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabela


def _folha_ponto(config: LivroPontoConfig, pessoa: Pessoa, dias, styles, numero_pagina: int) -> Table:
    conteudo = [
        [_cabecalho_formulario(config, styles, numero_pagina)],
        [_bloco_dados_pessoa(pessoa, styles)],
        [_tabela_dias(dias, styles)],
        [_secao_financeira(pessoa, styles)],
        [Spacer(1, 0.4 * cm)],
        [_rodape_assinaturas(styles)],
    ]
    outer = Table(conteudo, colWidths=[_LARGURA_CONTEUDO])
    outer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return outer


def _folha_consolidacao(config: LivroPontoConfig, pessoa: Pessoa, dias, styles) -> list:
    """Verso da folha de ponto: mesmo cabeçalho (sem "PAG"), título
    CONSOLIDAÇÃO, as anotações automáticas já impressas (feriados e
    exceções do mês, férias regulares cadastradas e observações — ex.:
    afastamentos), e o espaço pautado restante para anotações
    manuscritas, com o fecho de data e assinatura do superior imediato —
    igual ao formulário original."""
    elementos = [_cabecalho_formulario(config, styles, numero_pagina=None)]
    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(Paragraph("CONSOLIDAÇÃO", styles["ConsolidacaoTitulo"]))
    elementos.append(Spacer(1, 0.25 * cm))

    anotacoes = []
    texto_feriados = _texto_feriados_excecoes(dias, config.mes)
    if texto_feriados:
        anotacoes.append(
            Paragraph(f"<b>Feriados e exceções do mês:</b> {_truncar(texto_feriados, 400)}", styles["Campo"])
        )
    if pessoa.periodo_ferias:
        anotacoes.append(Paragraph(f"<b>Férias Regulares</b> de {pessoa.periodo_ferias}", styles["Campo"]))
    if pessoa.observacoes:
        anotacoes.append(Paragraph(f"<b>OBSERVAÇÕES:</b> {_truncar(pessoa.observacoes, 400)}", styles["Campo"]))

    total_linhas = 25
    if anotacoes:
        altura_total = sum(a.wrap(_LARGURA_CONTEUDO, 100 * cm)[1] + 0.3 * cm for a in anotacoes)
        linhas_ocupadas = math.ceil(altura_total / (0.72 * cm))
        total_linhas = max(10, 25 - linhas_ocupadas)
        for anotacao in anotacoes:
            elementos.append(anotacao)
            elementos.append(Spacer(1, 0.3 * cm))

    linhas_pautadas = [[""] for _ in range(total_linhas)]
    tabela_pauta = Table(linhas_pautadas, colWidths=[_LARGURA_CONTEUDO], rowHeights=[0.72 * cm] * total_linhas)
    tabela_pauta.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.black)]))
    elementos.append(tabela_pauta)

    elementos.append(Spacer(1, 0.6 * cm))
    elementos.append(Paragraph("DATA:  ___/___/_____", styles["Campo"]))
    elementos.append(Spacer(1, 0.9 * cm))
    elementos.append(Paragraph("_" * 50, styles["CorpoCentro"]))
    elementos.append(Paragraph("Assinatura do Superior Imediato", styles["CorpoCentro"]))
    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(Paragraph("Verso", ParagraphStyle("VersoTxt", parent=styles["Normal"], alignment=2)))
    return elementos


_LARGURA_FREQ_PRINCIPAL = 0.70 * _LARGURA_CONTEUDO
_LARGURA_FREQ_PAINEL = _LARGURA_CONTEUDO - _LARGURA_FREQ_PRINCIPAL
# 1 coluna larga (Assinaturas) + 22 colunas estreitas e iguais (Dia, Semana,
# Jornada Dia, Subst. Eventual, Reposição, Total Geral, 1ª a 11ª aula,
# U.E. Local, Geral, Natureza, Saldo Pendente, Falta M. Parcial).
_LARGURA_FREQ_ESTREITA = _LARGURA_FREQ_PRINCIPAL * 0.0354
_LARGURA_FREQ_ASSINATURAS = _LARGURA_FREQ_PRINCIPAL - 22 * _LARGURA_FREQ_ESTREITA
_COLS_FREQ = [_LARGURA_FREQ_ASSINATURAS] + [_LARGURA_FREQ_ESTREITA] * 22


def _cabecalho_frequencia(config: LivroPontoConfig, styles, numero_pagina: int) -> Table:
    titulo = Paragraph(
        f"FOLHA DE FREQUÊNCIA &nbsp;&nbsp;&nbsp; {nome_mes(config.mes).upper()} DE {config.ano}",
        styles["GovernoTitulo"],
    )
    pag = Paragraph(f"PAG: {numero_pagina}", styles["PagRotulo"])
    tabela = Table([[titulo, pag]], colWidths=[_LARGURA_FREQ_PRINCIPAL - 2.2 * cm, 2.2 * cm])
    tabela.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
            ]
        )
    )
    return tabela


def _bloco_dados_docente(config: LivroPontoConfig, pessoa: Pessoa, styles) -> Table:
    """Bloco NOME/RG/FAIXA-NÍVEL, SITUAÇÃO/CATEGORIA/JORNADA, CARGA
    SUPLEMENTAR/CARGA HORÁRIA, DISCIPLINAS, SEDE DE CONTROLE DE FREQUÊNCIA —
    nos mesmos rótulos do formulário "Folha de Frequência" original."""
    P = lambda t: Paragraph(t, styles["Campo"])  # noqa: E731
    P_nome = lambda t: Paragraph(t, styles["CampoNome"])  # noqa: E731
    linhas = [
        [P_nome(_linha_campo("NOME", pessoa.nome)), P(_linha_campo("RG", pessoa.rg)), P("<b>FAIXA/NÍVEL:</b>")],
        [
            P(_linha_campo("SITUAÇÃO", pessoa.cargo)),
            P(_linha_campo("CATEGORIA", pessoa.categoria)),
            P("<b>JORNADA:</b> HORAS DE TRABALHO DOCENTE"),
        ],
        [P("<b>CARGA SUPLEMENTAR:</b> ____ HORAS"), P("<b>CARGA HORÁRIA:</b> ____ HORAS"), ""],
        [P(_linha_campo("DISCIPLINAS", _truncar(pessoa.disciplinas, 90))), "", ""],
        [P(_linha_campo("SEDE DE CONTROLE DE FREQUÊNCIA", config.escola.nome)), "", ""],
    ]
    larguras = [_LARGURA_FREQ_PRINCIPAL * 0.40, _LARGURA_FREQ_PRINCIPAL * 0.32, _LARGURA_FREQ_PRINCIPAL * 0.28]
    tabela = Table(linhas, colWidths=larguras)
    tabela.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 3), (-1, 3)),
                ("SPAN", (0, 4), (-1, 4)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.black),
            ]
        )
    )
    return tabela


def _tabela_dias_frequencia(dias, styles) -> Table:
    """Grade principal: Dia/Semana, Jornada prevista (Jorn. Dia/Subst.
    Eventual/Reposição/Total Geral), Aulas por período (1ª a 11ª), Total
    (U.E. Local/Geral) e Saldo Pend. Mês Anterior (Natureza/Saldo
    Pendente/Falta M. Parcial) — dia e dia da semana preenchidos a partir do
    calendário; o resto fica em branco, para preenchimento manual."""
    C = lambda t: Paragraph(t, styles["CelTabelaPequena"])  # noqa: E731
    aulas = [f"{n}ª" for n in range(1, 12)]
    linha0 = (
        ["Assinaturas", "Dias", "", "Jornada prevista / UE-SCF", "", "", "", "Aulas — Unidade Escolar Local"]
        + [""] * 10
        + ["Total", "", "Saldo pend. mês anterior", "", ""]
    )
    linha1 = ["", "Dia", "Sem."] + ["Jorn.\nDia", "Subst.\nEvent.", "Repos.", "Total\nGeral"] + aulas + [
        "U.E.\nLocal",
        "Geral",
        "Nat.",
        "Saldo\nPend.",
        "Falta M.\nParc.",
    ]
    dados = [linha0, linha1]
    estilos_extra = [
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (3, 0), (6, 0)),
        ("SPAN", (7, 0), (17, 0)),
        ("SPAN", (18, 0), (19, 0)),
        ("SPAN", (20, 0), (22, 0)),
    ]
    for dia in dias:
        semana = _ABREV_SEMANA_FREQ[dia.data.weekday()]
        dados.append(["", str(dia.dia), semana] + [""] * 20)

    tabela = Table([[C(c) if isinstance(c, str) and c else c for c in row] for row in dados], colWidths=_COLS_FREQ, repeatRows=2)
    tabela.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 5.6),
                ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("BACKGROUND", (0, 0), (-1, 1), colors.lightgrey),
            ]
            + estilos_extra
        )
    )
    return tabela


def _painel_horario(styles) -> Table:
    """Painel lateral: grade HORÁRIO (aulas 1ª-11ª x dia da semana), Carga
    Horária - Outras UEs, Resumo Final (Resolução SE 08/2012) e Anotações —
    igual ao formulário original."""
    C = lambda t: Paragraph(t, styles["CelTabelaPequena"])  # noqa: E731
    dias_semana = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM", "Total"]
    # coluna de rótulo mais larga que as 8 colunas de dia — senão um texto
    # como "Dias da semana" quebra em muitas linhas e estoura a altura.
    larg_rotulo = 0.26 * _LARGURA_FREQ_PAINEL
    larg_dia = (_LARGURA_FREQ_PAINEL - larg_rotulo) / 8
    larguras_painel = [larg_rotulo] + [larg_dia] * 8

    linhas: list = [[C("<b>Dias da\nsemana</b>")] + [C(f"<b>{d}</b>") for d in dias_semana]]
    linhas.append([C("<b>Aulas</b>")] + [""] * 8)
    for n in range(1, 12):
        linhas.append([C(f"{n}ª")] + [""] * 8)
    linhas.append([C("<b>Sub total 1</b>")] + [""] * 8)

    tabela_horario = Table(linhas, colWidths=larguras_painel)
    tabela_horario.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.3, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 5.6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )

    linhas_outras_ue = [[C("<b>Carga horária — outras UEs</b>")] + [""] * 8]
    for n in range(1, 6):
        linhas_outras_ue.append([C(f"{n}ª UE")] + [""] * 8)
    linhas_outras_ue.append([C("<b>Sub total 2</b>")] + [""] * 8)
    linhas_outras_ue.append([C("<b>Total C.H. diária</b>")] + [""] * 8)
    tabela_outras_ue = Table(linhas_outras_ue, colWidths=larguras_painel)
    tabela_outras_ue.setStyle(
        TableStyle(
            [
                ("GRID", (0, 1), (-1, -1), 0.3, colors.black),
                ("SPAN", (0, 0), (-1, 0)),
                ("BOX", (0, 0), (-1, 0), 0.3, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 5.6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )

    resumo = [
        [C("<b>Resumo final</b> (Resolução SE 08/2012)"), "", ""],
        ["", C("Semanal"), C("Mensal")],
        [C("Jornada"), "", ""],
        [C("Carga suplementar / carga horária"), C("0/ 12"), C("0/ 60")],
        [C("Limite: Anexo Decreto nº 39.931/95"), C("Quantidade"), C("Vigência")],
        ["", C("2"), ""],
    ]
    tabela_resumo = Table(
        resumo,
        colWidths=[0.56 * _LARGURA_FREQ_PAINEL, 0.22 * _LARGURA_FREQ_PAINEL, 0.22 * _LARGURA_FREQ_PAINEL],
    )
    tabela_resumo.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("GRID", (0, 1), (-1, -1), 0.3, colors.black),
                ("BOX", (0, 0), (-1, -1), 0.3, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 5.6),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )

    anotacoes = Table(
        [[C("<b>Anotações:</b> Aulas em Local Livre (ATPL)")]],
        colWidths=[_LARGURA_FREQ_PAINEL],
        rowHeights=[1.8 * cm],
    )
    anotacoes.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.3, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    painel = Table(
        [[tabela_horario], [Spacer(1, 0.15 * cm)], [tabela_outras_ue], [Spacer(1, 0.15 * cm)], [tabela_resumo], [Spacer(1, 0.15 * cm)], [anotacoes]],
        colWidths=[_LARGURA_FREQ_PAINEL],
    )
    painel.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return painel


def _rodape_frequencia(styles) -> Table:
    linhas = [
        ["_" * 42, "_" * 42],
        [
            Paragraph("Responsável pelo registro", styles["CelTabelaPequena"]),
            Paragraph("Diretor(a) de Escola", styles["CelTabelaPequena"]),
        ],
    ]
    tabela = Table(linhas, colWidths=[_LARGURA_FREQ_PRINCIPAL * 0.5, _LARGURA_FREQ_PRINCIPAL * 0.5])
    tabela.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabela


def _folha_frequencia_docente(
    config: LivroPontoConfig, pessoa: Pessoa, dias, styles, numero_pagina: int
) -> Table:
    """Folha de Frequência do docente: grade de aulas por dia/período,
    painel de horário semanal e resumo final — formulário próprio,
    diferente da folha de ponto administrativa (aqui não há verso de
    consolidação: o resumo final já vem embutido na própria folha)."""
    coluna_principal = Table(
        [
            [_cabecalho_frequencia(config, styles, numero_pagina)],
            [_bloco_dados_docente(config, pessoa, styles)],
            [_tabela_dias_frequencia(dias, styles)],
            [Paragraph("<b>Observações:</b>", styles["Campo"])],
            [Spacer(1, 0.9 * cm)],
            [_rodape_frequencia(styles)],
        ],
        colWidths=[_LARGURA_FREQ_PRINCIPAL],
    )
    coluna_principal.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    outer = Table([[coluna_principal, _painel_horario(styles)]], colWidths=[_LARGURA_FREQ_PRINCIPAL, _LARGURA_FREQ_PAINEL])
    outer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("LINEAFTER", (0, 0), (0, 0), 0.6, colors.black),
            ]
        )
    )
    return outer


def _bloco_tipo(config: LivroPontoConfig, tipo: TipoServidor, dias, styles) -> list:
    # Páginas em ordem de número de RG (não a ordem do cadastro).
    pessoas = sorted(config.pessoas_por_tipo(tipo), key=chave_ordenacao_rg)
    if not pessoas:
        return []

    elementos: list = []
    if tipo in _TIPOS_FOLHA_PONTO:
        # duas folhas por pessoa: a folha de ponto e o verso (consolidação).
        numero_folhas = len(pessoas) * 2 + 2
    else:
        # a Folha de Frequência do docente já traz o resumo do mês embutido
        # (não tem verso/consolidação separada): uma folha por pessoa.
        numero_folhas = len(pessoas) + 2
    elementos += _termo(config, tipo, numero_folhas, encerramento=False, styles=styles)
    elementos.append(PageBreak())

    # Só as páginas com o nome do servidor (folha de ponto / folha de
    # frequência) são numeradas em "PAG: ___" — o verso de consolidação não
    # entra na numeração.
    for numero_pagina, pessoa in enumerate(pessoas, start=1):
        if tipo in _TIPOS_FOLHA_PONTO:
            elementos.append(_folha_ponto(config, pessoa, dias, styles, numero_pagina))
            elementos.append(PageBreak())
            elementos.append(KeepTogether(_folha_consolidacao(config, pessoa, dias, styles)))
        else:
            elementos.append(_folha_frequencia_docente(config, pessoa, dias, styles, numero_pagina))
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

    # Calendário do mês: marca automaticamente sábados, domingos, feriados
    # nacionais/estaduais (via `holidays`, pela UF) e as exceções cadastradas
    # (recesso, ponto facultativo etc.) nas folhas de ponto e de frequência.
    dias = montar_calendario(config.ano, config.mes, uf=uf or config.uf, excecoes=config.dias_excecao)
    styles = _styles()

    doc = SimpleDocTemplate(
        str(caminho_saida),
        pagesize=A4,
        leftMargin=_MARGEM_ESQUERDA,
        rightMargin=_MARGEM,
        topMargin=_MARGEM,
        bottomMargin=_MARGEM,
        title=f"Livro Ponto - {nome_mes(config.mes)} {config.ano}",
    )

    elementos: list = []
    elementos += _bloco_tipo(config, TipoServidor.ADMINISTRATIVO, dias, styles)
    elementos += _bloco_tipo(config, TipoServidor.GESTAO, dias, styles)
    elementos += _bloco_tipo(config, TipoServidor.DOCENTE, dias, styles)

    if elementos and isinstance(elementos[-1], PageBreak):
        elementos.pop()

    doc.build(elementos)
    return Path(caminho_saida)
