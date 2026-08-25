from reportlab.platypus import KeepTogether, Paragraph, Table

from livroponto.calendario import montar_calendario
from livroponto.models import Escola, Licenca, LivroPontoConfig, Pessoa, TipoServidor, chave_ordenacao_rg
from livroponto.pdf.builder import _bloco_tipo, _folha_consolidacao, _secao_financeira, _styles, _termo, gerar_pdf


def _config_exemplo() -> LivroPontoConfig:
    escola = Escola(
        nome="EE Exemplo Fictício",
        diretoria_ensino="Região Exemplo",
        municipio="Cidade Exemplo",
    )
    pessoas = [
        Pessoa(
            nome="Servidor Fictício Um",
            tipo=TipoServidor.ADMINISTRATIVO,
            rg="00.000.000-0",
            cargo="Agente de Organização Escolar",
            jornada_semanal=40,
            entrada="07:00",
            saida="16:00",
            intervalo_inicio="11:00",
            intervalo_fim="12:00",
        ),
        Pessoa(
            nome="Docente Fictício Dois",
            tipo=TipoServidor.DOCENTE,
            rg="11.111.111-1",
            cargo="PEB II",
            categoria="Titular de Cargo",
            disciplinas="MATEMÁTICA",
        ),
    ]
    return LivroPontoConfig(escola=escola, mes=4, ano=2026, pessoas=pessoas)


def test_folha_ponto_cabe_em_uma_pagina_em_todo_mes_de_31_dias():
    """Bug real: nos meses de 31 dias (janeiro, março, maio, julho,
    agosto, outubro, dezembro) a folha de ponto administrativa quase não
    cabia numa página só — a linha de assinatura acabava pulando pra uma
    segunda folha."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    from livroponto.pdf.builder import _MARGEM, _folha_ponto

    altura_disponivel = A4[1] - 2 * _MARGEM
    for mes in (1, 3, 5, 7, 8, 10, 12):
        config = _config_exemplo()
        config.mes = mes
        pessoa = config.pessoas[0]
        dias = montar_calendario(config.ano, mes, uf=config.uf)
        tabela = _folha_ponto(config, pessoa, dias, _styles(), numero_pagina=1)
        _, altura = tabela.wrap(1000, 1000 * cm)
        assert altura <= altura_disponivel, f"mês {mes} estoura a página (altura={altura})"


def test_folha_frequencia_docente_nao_estoura_com_nome_comprido_em_mes_de_31_dias(tmp_path):
    """Bug real: um nome de docente comprido (que quebra em várias linhas
    na coluna estreita de NOME) combinado com um mês de 31 dias fazia o
    reportlab lançar LayoutError — essa folha tem layout fixo de uma
    página só, sem como quebrar em duas."""
    config = _config_exemplo()
    config.mes = 1
    config.pessoas = [
        Pessoa(
            nome="José Carlos Rodrigues de Oliveira Neto Ferreira",
            tipo=TipoServidor.DOCENTE,
            cargo="PEB II",
            rg="9.876.543-2",
            disciplinas="MATEMÁTICA",
            categoria="F",
        )
    ]
    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(config, caminho)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000


def test_gerar_pdf_cria_arquivo_nao_vazio(tmp_path):
    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(_config_exemplo(), caminho)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000
    with open(resultado, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_gerar_pdf_sem_pessoas_lanca_erro(tmp_path):
    config = _config_exemplo()
    config.pessoas = []
    import pytest

    with pytest.raises(ValueError):
        gerar_pdf(config, tmp_path / "vazio.pdf")


def test_ordenacao_por_rg_e_numerica_nao_textual():
    """"9" deve vir antes de "10" (ordem numérica), não depois (ordem de
    texto, onde "10" < "9")."""
    nove = Pessoa(nome="Nove", tipo=TipoServidor.ADMINISTRATIVO, rg="9")
    dez = Pessoa(nome="Dez", tipo=TipoServidor.ADMINISTRATIVO, rg="10")

    ordenados = sorted([dez, nove], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Nove", "Dez"]


def test_ordenacao_por_rg_ignora_pontuacao():
    """Pontos e traço no RG (ex.: "1.234-5") não devem contar como parte
    do número na hora de ordenar."""
    menor = Pessoa(nome="Menor", tipo=TipoServidor.ADMINISTRATIVO, rg="500")
    maior_pontuado = Pessoa(nome="Maior", tipo=TipoServidor.ADMINISTRATIVO, rg="1.234-5")

    ordenados = sorted([maior_pontuado, menor], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Menor", "Maior"]


def test_ordenacao_por_rg_ignora_digito_verificador():
    """O dígito verificador depois do traço não conta como parte do
    número — senão um RG com dígito verificador (ex.: "9.876.543-2",
    que vira 98765432 se o traço não for tratado à parte) fica "maior"
    só por ter um dígito a mais do que um RG equivalente sem traço
    (ex.: "16304137"), e sai antes na ordem quando deveria vir depois."""
    comeca_com_9 = Pessoa(nome="Começa com 9", tipo=TipoServidor.ADMINISTRATIVO, rg="9.876.543-2")
    comeca_com_16 = Pessoa(nome="Começa com 16", tipo=TipoServidor.ADMINISTRATIVO, rg="16304137")

    ordenados = sorted([comeca_com_16, comeca_com_9], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Começa com 9", "Começa com 16"]


def test_ordenacao_por_rg_sem_rg_cadastrado_vai_pro_fim():
    com_rg = Pessoa(nome="Com RG", tipo=TipoServidor.ADMINISTRATIVO, rg="123")
    sem_rg = Pessoa(nome="Sem RG", tipo=TipoServidor.ADMINISTRATIVO, rg="")

    ordenados = sorted([sem_rg, com_rg], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Com RG", "Sem RG"]


def test_ordenacao_por_rg_letra_no_inicio_vem_sempre_primeiro():
    """Pedido do usuário: RG de outro estado com letra (ex.:
    "M1.234.567-8") sempre vem primeiro, antes de qualquer RG só
    numérico — não entra na comparação numérica normal."""
    com_letra = Pessoa(nome="Com Letra", tipo=TipoServidor.ADMINISTRATIVO, rg="M1.234.567-8")
    numerico_pequeno = Pessoa(nome="Numérico Pequeno", tipo=TipoServidor.ADMINISTRATIVO, rg="1")

    ordenados = sorted([numerico_pequeno, com_letra], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Com Letra", "Numérico Pequeno"]


def test_ordenacao_por_rg_zero_a_esquerda_nao_conta_pra_comparacao():
    """Pedido do usuário: "01.234.567-8" vale como 1234567 (não
    01234567) na hora de comparar com outro RG."""
    com_zero = Pessoa(nome="Com Zero", tipo=TipoServidor.ADMINISTRATIVO, rg="01.234.567-8")
    maior = Pessoa(nome="Maior", tipo=TipoServidor.ADMINISTRATIVO, rg="2.000.000-0")

    ordenados = sorted([maior, com_zero], key=chave_ordenacao_rg)
    assert [p.nome for p in ordenados] == ["Com Zero", "Maior"]


def test_formatar_rg_padrao_numerico():
    from livroponto.models import formatar_rg

    assert formatar_rg("123456789") == "12.345.678-9"
    assert formatar_rg("12.345.678-9") == "12.345.678-9"  # idempotente


def test_formatar_rg_mantem_zero_a_esquerda():
    """Diferente da ordenação, a formatação preserva o zero à esquerda
    como parte do valor digitado — só reorganiza a pontuação."""
    from livroponto.models import formatar_rg

    assert formatar_rg("012345678") == "01.234.567-8"


def test_formatar_rg_aceita_letra():
    from livroponto.models import formatar_rg

    assert formatar_rg("M1234567") == "M1.234.567"
    assert formatar_rg("m12345678") == "M1.234.567-8"


def test_formatar_rg_incompleto_formata_progressivamente():
    """Formata conforme os caracteres vão sendo digitados — a pontuação
    só aparece quando o próximo bloco começa."""
    from livroponto.models import formatar_rg

    assert formatar_rg("") == ""
    assert formatar_rg("1") == "1"
    assert formatar_rg("12") == "12"
    assert formatar_rg("123") == "12.3"
    assert formatar_rg("12345") == "12.345"
    assert formatar_rg("123456") == "12.345.6"


def test_bloco_dados_pessoa_imprime_rg_formatado_mesmo_sem_pontuacao_salva():
    from livroponto.pdf.builder import _bloco_dados_pessoa

    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, rg="123456789")
    tabela = _bloco_dados_pessoa(pessoa, _styles())
    assert "12.345.678-9" in tabela._cellvalues[0][1].text


def test_bloco_dados_docente_imprime_rg_formatado_com_letra():
    from livroponto.pdf.builder import _bloco_dados_docente

    config = _config_exemplo()
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.DOCENTE, rg="M1234567")
    tabela = _bloco_dados_docente(config, pessoa, _styles())
    assert "M1.234.567" in tabela._cellvalues[0][1].text


def _textos(elementos) -> list[str]:
    return [e.text for e in elementos if isinstance(e, Paragraph)]


def _textos_profundo(obj) -> list[str]:
    """Como `_textos`, mas desce em Table/KeepTogether aninhados — usada
    quando o texto procurado está dentro de uma célula de tabela (ex.:
    nome do servidor, número da página), não num Paragraph solto."""
    if isinstance(obj, Paragraph):
        return [obj.text]
    if isinstance(obj, Table):
        textos = []
        for linha in obj._cellvalues:
            for celula in linha:
                textos.extend(_textos_profundo(celula))
        return textos
    if isinstance(obj, KeepTogether):
        return _textos_profundo(obj._content)
    if isinstance(obj, (list, tuple)):
        textos = []
        for item in obj:
            textos.extend(_textos_profundo(item))
        return textos
    return []


def test_termo_assina_com_nome_do_diretor_cadastrado():
    """O nome de quem assina "Direção da Unidade Escolar" vem do campo
    `diretor_nome` (aba Escola) — não mais de uma busca no cadastro da
    Gestão, que dependia de outra aba e sumia quando ela não entrava no
    PDF sendo gerado."""
    config = _config_exemplo()
    config.diretor_nome = "Fulana Diretora"
    elementos = _termo(config, TipoServidor.ADMINISTRATIVO, encerramento=False, styles=_styles())
    assert "Fulana Diretora" in _textos(elementos)


def test_gerar_pdf_so_administrativo_ainda_assina_com_diretor_do_campo(tmp_path, monkeypatch):
    """A assinatura do diretor não depende mais de quais tipos estão em
    tipos_incluidos nem do cadastro de pessoas — gerando só o livro
    administrativo, o nome cadastrado em `diretor_nome` continua indo pro
    termo normalmente."""
    import livroponto.pdf.builder as builder_mod

    config = _config_exemplo()
    config.diretor_nome = "Fulana Diretora"

    configs_vistos = []
    original = builder_mod._bloco_tipo

    def _bloco_tipo_espiao(config_recebido, tipo, dias, styles, **kwargs):
        configs_vistos.append((tipo, config_recebido))
        return original(config_recebido, tipo, dias, styles, **kwargs)

    monkeypatch.setattr(builder_mod, "_bloco_tipo", _bloco_tipo_espiao)

    caminho = tmp_path / "livro_ponto.pdf"
    gerar_pdf(config, caminho, tipos_incluidos={TipoServidor.ADMINISTRATIVO})

    assert [tipo for tipo, _ in configs_vistos] == [TipoServidor.ADMINISTRATIVO]
    assert configs_vistos[0][1].nome_diretor() == "Fulana Diretora"


def test_termo_sem_diretor_cadastrado_fica_so_com_o_rotulo():
    config = _config_exemplo()
    assert config.diretor_nome == ""
    elementos = _termo(config, TipoServidor.ADMINISTRATIVO, encerramento=False, styles=_styles())
    textos = _textos(elementos)
    idx = textos.index("Direção da Unidade Escolar")
    # sem diretor cadastrado, o rótulo vem logo depois da linha de
    # assinatura (sublinhado) — nenhum parágrafo de nome é inserido entre eles
    assert textos[idx - 1] == "_" * 50


def test_nome_diretor_vem_do_campo_e_ignora_espacos_em_branco():
    config = _config_exemplo()
    assert config.nome_diretor() == ""

    config.diretor_nome = "  Fulana Diretora  "
    assert config.nome_diretor() == "Fulana Diretora"


def test_termo_usa_rotulo_de_assinatura_customizado():
    """Pedido do usuário: preparar o livro pra uso numa URE (Unidade
    Regional de Ensino), não só em escola — o rótulo embaixo da
    assinatura ("Direção da Unidade Escolar") tem que poder virar outra
    coisa (ex.: "Dirigente Regional de Ensino") sem mexer em código."""
    config = _config_exemplo()
    config.rotulo_assinatura = "Dirigente Regional de Ensino"
    elementos = _termo(config, TipoServidor.ADMINISTRATIVO, encerramento=False, styles=_styles())
    textos = _textos(elementos)
    assert "Dirigente Regional de Ensino" in textos
    assert "Direção da Unidade Escolar" not in textos


def test_rotulo_assinatura_efetivo_cai_no_padrao_de_escola_se_em_branco():
    config = _config_exemplo()
    assert config.rotulo_assinatura == ""
    assert config.rotulo_assinatura_efetivo() == "Direção da Unidade Escolar"

    config.rotulo_assinatura = "  Dirigente Regional de Ensino  "
    assert config.rotulo_assinatura_efetivo() == "Dirigente Regional de Ensino"


def test_pessoa_periodo_ferias():
    sem_ferias = Pessoa(nome="Sem Férias", tipo=TipoServidor.ADMINISTRATIVO)
    assert sem_ferias.periodo_ferias == ""

    so_inicio = Pessoa(nome="Só início", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026")
    assert so_inicio.periodo_ferias == ""  # precisa das duas datas

    com_ferias = Pessoa(
        nome="Com Férias", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    assert com_ferias.periodo_ferias == "03/04/2026 a 02/05/2026"


def test_licencas_em_vigor_considera_sobreposicao_de_periodo():
    from livroponto.models import licencas_em_vigor

    pessoa = Pessoa(
        nome="Fulano",
        tipo=TipoServidor.ADMINISTRATIVO,
        licencas=[
            Licenca(tipo="SAUDE", inicio="15/03/2026", fim="10/04/2026"),  # começa antes, termina dentro do mês
            Licenca(tipo="PREMIO", inicio="25/04/2026", fim="10/05/2026"),  # começa dentro, termina depois
            Licenca(tipo="SAUDE", inicio="01/01/2026", fim="28/02/2026"),  # totalmente antes do mês
            Licenca(tipo="SAUDE", inicio="", fim=""),  # sem data — ignorada, não quebra nada
        ],
    )
    vigentes = licencas_em_vigor(pessoa, mes=4, ano=2026)
    assert {(v.tipo, v.inicio, v.fim) for v in vigentes} == {
        ("SAUDE", "15/03/2026", "10/04/2026"),
        ("PREMIO", "25/04/2026", "10/05/2026"),
    }


def test_ferias_em_vigor_considera_sobreposicao_de_periodo():
    from livroponto.models import ferias_em_vigor

    com_sobreposicao = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    fora_do_mes = Pessoa(
        nome="Beltrano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/07/2026", ferias_fim="02/08/2026"
    )
    sem_data = Pessoa(nome="Sem Data", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026")

    assert ferias_em_vigor(com_sobreposicao, mes=4, ano=2026) is True
    assert ferias_em_vigor(fora_do_mes, mes=4, ano=2026) is False
    assert ferias_em_vigor(sem_data, mes=4, ano=2026) is False


def test_licenca_rotulo_e_periodo():
    saude = Licenca(tipo="SAUDE", inicio="10/04/2026", fim="20/04/2026")
    assert saude.rotulo == "Licença Saúde"
    assert saude.periodo == "10/04/2026 a 20/04/2026"

    premio = Licenca(tipo="PREMIO")
    assert premio.rotulo == "Licença Prêmio"
    assert premio.periodo == ""


def test_secao_financeira_preenche_ferias_em_vigor_no_mes_selecionado():
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    tabela = _secao_financeira(pessoa, _styles(), mes=4, ano=2026)
    linha_ferias = tabela._cellvalues[1][1]
    assert "03/04/2026" in linha_ferias.text
    assert "02/05/2026" in linha_ferias.text


def test_secao_financeira_nao_preenche_ferias_fora_do_mes_do_livro():
    """Pedido do usuário: as férias só saem preenchidas no campo
    FÉRIAS/anotadas no verso do(s) mês(es) em que efetivamente caem —
    um livro de outro mês mantém o campo em branco, igual ao formulário
    original."""
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/07/2026", ferias_fim="02/08/2026"
    )
    tabela = _secao_financeira(pessoa, _styles(), mes=4, ano=2026)
    linha_ferias = tabela._cellvalues[1][1]
    assert "___/___/___" in linha_ferias.text
    assert "03/07/2026" not in linha_ferias.text


def test_secao_financeira_sem_ferias_cadastradas_fica_em_branco():
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO)
    tabela = _secao_financeira(pessoa, _styles(), mes=4, ano=2026)
    linha_ferias = tabela._cellvalues[1][1]
    assert "___/___/___" in linha_ferias.text


def test_folha_consolidacao_anota_ferias_regulares_no_verso_do_mes_selecionado():
    config = _config_exemplo()  # mes=4, ano=2026
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert any("Férias Regulares" in t and "03/04/2026 a 02/05/2026" in t for t in textos)


def test_folha_consolidacao_nao_anota_ferias_fora_do_mes_do_livro():
    """Pedido do usuário: férias regulares só saem anotadas no verso do
    mês em que caem — um período de férias de outro mês não deve
    aparecer no livro gerado para o mês selecionado."""
    config = _config_exemplo()  # mes=4, ano=2026
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/07/2026", ferias_fim="02/08/2026"
    )
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert not any("Férias Regulares" in t for t in textos)


def test_folha_consolidacao_sem_ferias_nao_anota_nada():
    config = _config_exemplo()
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO)
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert not any("Férias Regulares" in t for t in textos)


def test_folha_consolidacao_lista_feriados_e_excecoes_do_mes():
    """Pedido do usuário: feriado e exceções (recesso, ponto facultativo,
    suspensão) cadastrados/calculados para o mês têm que aparecer
    também na folha de consolidação (verso), não só marcados na tabela
    de dias da folha de ponto."""
    from livroponto.models import DiaNaoLetivo

    config = _config_exemplo()
    config.mes = 4
    config.ano = 2026
    config.dias_excecao = [DiaNaoLetivo(mes=4, dia=8, tipo="RECESSO", descricao="Recesso escolar")]
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO)
    dias = montar_calendario(config.ano, config.mes, uf=config.uf, excecoes=config.dias_excecao)

    elementos = _folha_consolidacao(config, pessoa, dias, _styles())
    textos = _textos(elementos)
    assert any("Feriados e exceções do mês" in t and "RECESSO" in t and "08/04" in t for t in textos)


def test_folha_consolidacao_sem_feriados_no_mes_nao_anota_nada():
    config = _config_exemplo()
    config.mes = 4
    config.ano = 2026
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO)
    dias = [d for d in montar_calendario(config.ano, config.mes, uf=config.uf) if d.e_dia_normal]

    elementos = _folha_consolidacao(config, pessoa, dias, _styles())
    textos = _textos(elementos)
    assert not any("Feriados e exceções do mês" in t for t in textos)


def test_folha_consolidacao_anota_licenca_em_vigor_no_mes():
    """Pedido do usuário: uma licença (saúde ou prêmio) só sai anotada na
    consolidação se ainda estiver em vigor no mês do livro sendo gerado —
    uma já encerrada em outro mês não deve aparecer."""
    config = _config_exemplo()
    config.mes = 4
    config.ano = 2026
    pessoa = Pessoa(
        nome="Fulano",
        tipo=TipoServidor.ADMINISTRATIVO,
        licencas=[
            Licenca(tipo="SAUDE", inicio="10/04/2026", fim="20/04/2026"),
            Licenca(tipo="PREMIO", inicio="01/01/2025", fim="31/03/2025"),
        ],
    )
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert any("Licença Saúde" in t and "10/04/2026 a 20/04/2026" in t for t in textos)
    assert not any("Licença Prêmio" in t for t in textos)


def test_folha_consolidacao_sem_licenca_em_vigor_nao_anota_nada():
    config = _config_exemplo()
    config.mes = 6
    config.ano = 2026
    pessoa = Pessoa(
        nome="Fulano",
        tipo=TipoServidor.ADMINISTRATIVO,
        licencas=[Licenca(tipo="SAUDE", inicio="10/04/2026", fim="20/04/2026")],
    )
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert not any("Licença" in t for t in textos)


def test_bloco_tipo_sem_termos_nao_inclui_paragrafo_de_termo():
    """Pedido do usuário: o botão principal "Gerar Livro Ponto" não inclui
    mais os termos de abertura/encerramento — só as folhas, pra poder
    imprimir frente e verso (os termos têm aba própria, "Termos")."""
    config = _config_exemplo()
    dias = montar_calendario(config.ano, config.mes, uf=config.uf)
    elementos = _bloco_tipo(config, TipoServidor.ADMINISTRATIVO, dias, _styles(), incluir_termos=False)
    assert not any("LIVRO PONTO" in t for t in _textos(elementos))
    assert any(isinstance(e, Table) for e in elementos)


def test_bloco_tipo_imprimir_apenas_folha_nao_inclui_consolidacao():
    config = _config_exemplo()
    dias = montar_calendario(config.ano, config.mes, uf=config.uf)
    elementos = _bloco_tipo(
        config,
        TipoServidor.ADMINISTRATIVO,
        dias,
        _styles(),
        incluir_termos=False,
        imprimir_folha=True,
        imprimir_consolidacao=False,
    )
    assert any(isinstance(e, Table) for e in elementos)
    assert not any(isinstance(e, KeepTogether) for e in elementos)


def test_bloco_tipo_imprimir_apenas_consolidacao_nao_inclui_folha():
    config = _config_exemplo()
    dias = montar_calendario(config.ano, config.mes, uf=config.uf)
    elementos = _bloco_tipo(
        config,
        TipoServidor.ADMINISTRATIVO,
        dias,
        _styles(),
        incluir_termos=False,
        imprimir_folha=False,
        imprimir_consolidacao=True,
    )
    assert any(isinstance(e, KeepTogether) for e in elementos)
    assert not any(isinstance(e, Table) for e in elementos)


def test_gerar_pdf_sem_folha_nem_consolidacao_lanca_erro(tmp_path):
    import pytest

    config = _config_exemplo()
    with pytest.raises(ValueError):
        gerar_pdf(config, tmp_path / "vazio.pdf", imprimir_folha=False, imprimir_consolidacao=False)


def test_gerar_pdf_sem_termos_gera_arquivo(tmp_path):
    """Fluxo do botão "Gerar Livro Ponto" do app desktop: sem termos,
    só as folhas."""
    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(_config_exemplo(), caminho, incluir_termos=False)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000


def test_bloco_tipo_pessoas_selecionadas_imprime_so_quem_esta_marcado_mantendo_pagina():
    """Pedido do usuário: marcar um servidor específico na lista deve
    imprimir só a folha/consolidação dele, mas com o número de página
    igual ao que ele tem no livro completo (não renumerado a partir de
    1 pra quem sobrou)."""
    config = _config_exemplo()  # já tem "Servidor Fictício Um" (rg 00.000.000-0) -> página 1
    segundo = Pessoa(nome="Segundo Fictício", tipo=TipoServidor.ADMINISTRATIVO, rg="99.999.999-9")
    config.pessoas.append(segundo)  # rg maior -> página 2 na ordenação por RG
    dias = montar_calendario(config.ano, config.mes, uf=config.uf)

    elementos = _bloco_tipo(
        config,
        TipoServidor.ADMINISTRATIVO,
        dias,
        _styles(),
        incluir_termos=False,
        pessoas_selecionadas={id(segundo)},
    )
    textos = _textos_profundo(elementos)
    assert any("Segundo Fictício" in t for t in textos)
    assert not any("Servidor Fictício Um" in t for t in textos)
    assert any("PAG: 2" in t for t in textos)


def test_bloco_tipo_pessoas_selecionadas_vazio_nao_imprime_ninguem():
    config = _config_exemplo()
    dias = montar_calendario(config.ano, config.mes, uf=config.uf)
    elementos = _bloco_tipo(
        config, TipoServidor.ADMINISTRATIVO, dias, _styles(), incluir_termos=False, pessoas_selecionadas=set()
    )
    assert elementos == []


def test_gerar_pdf_pessoas_selecionadas_gera_arquivo_menor_que_o_livro_completo(tmp_path):
    config = _config_exemplo()
    segundo = Pessoa(nome="Segundo Fictício", tipo=TipoServidor.ADMINISTRATIVO, rg="99.999.999-9")
    config.pessoas.append(segundo)

    completo = tmp_path / "completo.pdf"
    gerar_pdf(config, completo, incluir_termos=False)

    so_um = tmp_path / "so_um.pdf"
    resultado = gerar_pdf(config, so_um, incluir_termos=False, pessoas_selecionadas={id(segundo)})

    assert resultado.exists()
    assert resultado.stat().st_size < completo.stat().st_size


def test_bloco_tipo_gestao_usa_formato_folha_de_ponto_com_livro_proprio():
    """O trio gestor usa o mesmo formato de folha de ponto do
    administrativo (com verso de consolidação), em livro próprio — o
    termo desse livro usa o nome oficial "Equipe Gestora" (nunca "trio
    gestor"), igual ao formulário real fotografado pelo usuário:
    "registro do Ponto do Pessoal da Equipe Gestora da ..."."""
    config = _config_exemplo()
    config.pessoas.append(
        Pessoa(
            nome="Diretora Fictícia",
            tipo=TipoServidor.GESTAO,
            cargo="Diretor(a) de Escola",
            rg="5",
            jornada_semanal=40,
            entrada="07:00",
            saida="16:00",
        )
    )
    dias = montar_calendario(config.ano, config.mes, uf=config.uf, excecoes=config.dias_excecao)
    elementos = _bloco_tipo(config, TipoServidor.GESTAO, dias, _styles())
    assert elementos
    textos = _textos(elementos)
    assert not any("trio gestor" in t.lower() for t in textos)
    assert "LIVRO PONTO" in textos
    assert any("Pessoal da Equipe Gestora" in t for t in textos)
    assert any("registro do Ponto do Pessoal da Equipe Gestora da" in t for t in textos)


def test_termo_deixa_espaco_para_numero_e_extenso_da_quantidade_de_folhas():
    """O formulário oficial tem dois espaços em branco pra quantidade de
    folhas: o número ("07") e, entre parênteses, por extenso ("Sete") —
    os dois ficam em branco para preenchimento manual, em todo tipo e
    em ambos os termos (abertura e encerramento)."""
    config = _config_exemplo()
    for tipo in (TipoServidor.ADMINISTRATIVO, TipoServidor.DOCENTE, TipoServidor.GESTAO):
        for encerramento in (False, True):
            elementos = _termo(config, tipo, encerramento=encerramento, styles=_styles())
            textos = _textos(elementos)
            assert any("_____ ( _____________________ ) folhas" in t for t in textos)


def test_gerar_pdf_inclui_folha_do_trio_gestor(tmp_path):
    config = _config_exemplo()
    config.pessoas.append(
        Pessoa(
            nome="Diretora Fictícia",
            tipo=TipoServidor.GESTAO,
            cargo="Diretor(a) de Escola",
            rg="5",
            jornada_semanal=40,
            entrada="07:00",
            saida="16:00",
        )
    )
    caminho = tmp_path / "livro_ponto.pdf"
    resultado = gerar_pdf(config, caminho)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000
