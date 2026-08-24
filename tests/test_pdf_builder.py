from reportlab.platypus import Paragraph

from livroponto.calendario import montar_calendario
from livroponto.models import Escola, LivroPontoConfig, Pessoa, TipoServidor, chave_ordenacao_rg
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


def _textos(elementos) -> list[str]:
    return [e.text for e in elementos if isinstance(e, Paragraph)]


def test_termo_assina_com_nome_do_diretor_cadastrado():
    config = _config_exemplo()
    config.pessoas += [
        Pessoa(nome="Fulana Diretora", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola"),
        Pessoa(nome="Ciclano Vice", tipo=TipoServidor.GESTAO, cargo="Vice-Diretor(a) de Escola"),
    ]
    elementos = _termo(config, TipoServidor.ADMINISTRATIVO, numero_folhas=5, encerramento=False, styles=_styles())
    assert "Fulana Diretora" in _textos(elementos)


def test_gerar_pdf_so_administrativo_ainda_encontra_diretor_da_gestao(tmp_path, monkeypatch):
    """Bug real reportado pelo usuário: gerando só o livro administrativo
    (tipos_incluidos sem GESTAO — equivalente a desmarcar "Trio gestor" em
    "Incluir" no app desktop), o(a) Diretor(a) de Escola cadastrado na
    Gestão sumia da assinatura do termo, porque quem chamava gerar_pdf
    filtrava config.pessoas por tipo ANTES de passar pra cá, removendo a
    pessoa que nome_diretor() precisa encontrar. gerar_pdf agora só decide
    quais livros ganham folhas via tipos_incluidos, sem tirar ninguém do
    config — espiona o config que de fato chega em _bloco_tipo pra provar
    isso (o PDF final vem comprimido, não dá pra checar o texto direto nos
    bytes — a cobertura do texto em si já está em
    test_termo_assina_com_nome_do_diretor_cadastrado)."""
    import livroponto.pdf.builder as builder_mod

    config = _config_exemplo()
    config.pessoas.append(
        Pessoa(nome="Fulana Diretora", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola")
    )

    configs_vistos = []
    original = builder_mod._bloco_tipo

    def _bloco_tipo_espiao(config_recebido, tipo, dias, styles):
        configs_vistos.append((tipo, config_recebido))
        return original(config_recebido, tipo, dias, styles)

    monkeypatch.setattr(builder_mod, "_bloco_tipo", _bloco_tipo_espiao)

    caminho = tmp_path / "livro_ponto.pdf"
    gerar_pdf(config, caminho, tipos_incluidos={TipoServidor.ADMINISTRATIVO})

    # só o bloco administrativo roda — mas o config que ele recebe ainda
    # tem a diretora da Gestão, então nome_diretor() a encontra.
    assert [tipo for tipo, _ in configs_vistos] == [TipoServidor.ADMINISTRATIVO]
    assert configs_vistos[0][1].nome_diretor() == "Fulana Diretora"


def test_termo_sem_diretor_cadastrado_fica_so_com_o_rotulo():
    config = _config_exemplo()
    assert config.pessoas_por_tipo(TipoServidor.GESTAO) == []
    elementos = _termo(config, TipoServidor.ADMINISTRATIVO, numero_folhas=5, encerramento=False, styles=_styles())
    textos = _textos(elementos)
    idx = textos.index("Direção da Unidade Escolar")
    # sem diretor cadastrado, o rótulo vem logo depois da linha de
    # assinatura (sublinhado) — nenhum parágrafo de nome é inserido entre eles
    assert textos[idx - 1] == "_" * 50


def test_nome_diretor_ignora_vice_diretor():
    config = _config_exemplo()
    config.pessoas.append(Pessoa(nome="Ciclano Vice", tipo=TipoServidor.GESTAO, cargo="Vice-Diretor(a) de Escola"))
    assert config.nome_diretor() == ""

    config.pessoas.append(Pessoa(nome="Fulana Diretora", tipo=TipoServidor.GESTAO, cargo="Diretor(a) de Escola"))
    assert config.nome_diretor() == "Fulana Diretora"


def test_pessoa_periodo_ferias():
    sem_ferias = Pessoa(nome="Sem Férias", tipo=TipoServidor.ADMINISTRATIVO)
    assert sem_ferias.periodo_ferias == ""

    so_inicio = Pessoa(nome="Só início", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026")
    assert so_inicio.periodo_ferias == ""  # precisa das duas datas

    com_ferias = Pessoa(
        nome="Com Férias", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    assert com_ferias.periodo_ferias == "03/04/2026 a 02/05/2026"


def test_secao_financeira_preenche_ferias_cadastradas():
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    tabela = _secao_financeira(pessoa, _styles())
    linha_ferias = tabela._cellvalues[1][1]
    assert "03/04/2026" in linha_ferias.text
    assert "02/05/2026" in linha_ferias.text


def test_secao_financeira_sem_ferias_cadastradas_fica_em_branco():
    pessoa = Pessoa(nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO)
    tabela = _secao_financeira(pessoa, _styles())
    linha_ferias = tabela._cellvalues[1][1]
    assert "___/___/___" in linha_ferias.text


def test_folha_consolidacao_anota_ferias_regulares_no_verso():
    config = _config_exemplo()
    pessoa = Pessoa(
        nome="Fulano", tipo=TipoServidor.ADMINISTRATIVO, ferias_inicio="03/04/2026", ferias_fim="02/05/2026"
    )
    elementos = _folha_consolidacao(config, pessoa, [], _styles())
    textos = _textos(elementos)
    assert any("Férias Regulares" in t and "03/04/2026 a 02/05/2026" in t for t in textos)


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
            elementos = _termo(config, tipo, numero_folhas=99, encerramento=encerramento, styles=_styles())
            textos = _textos(elementos)
            assert any("_____ ( _____________________ ) folhas" in t for t in textos)
            assert not any("99" in t for t in textos)


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
