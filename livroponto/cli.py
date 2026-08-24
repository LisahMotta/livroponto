"""Interface de linha de comando do livroponto."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .holidays_br import carregar_dias_excecao
from .models import TipoServidor
from .pdf.builder import gerar_pdf
from .readers.template_reader import criar_modelo, ler_modelo
from .readers.xlsb_reader import ler_livro_ponto


def _detectar_formato(caminho: Path) -> str:
    sufixo = caminho.suffix.lower()
    if sufixo == ".xlsb":
        return "xlsb"
    if sufixo in (".xlsx", ".xlsm"):
        return "xlsx"
    raise SystemExit(f"Formato de entrada não suportado: {sufixo}")


def _cmd_gerar(args: argparse.Namespace) -> None:
    entrada = Path(args.entrada)
    if not entrada.exists():
        raise SystemExit(f"Arquivo de entrada não encontrado: {entrada}")

    formato = args.formato_entrada or _detectar_formato(entrada)

    if formato == "xlsb":
        config = ler_livro_ponto(
            entrada,
            mes=args.mes,
            ano=args.ano,
            incluir_administrativos=not args.somente_docentes,
            incluir_docentes=not args.somente_administrativos,
        )
    else:
        config = ler_modelo(entrada)
        if args.mes is not None:
            config.mes = args.mes
        if args.ano is not None:
            config.ano = args.ano

    if args.feriados_extra:
        config.dias_excecao = carregar_dias_excecao(args.feriados_extra)
    if args.uf:
        config.uf = args.uf
    if args.cidade:
        config.cidade_assinatura = args.cidade

    if not config.pessoas:
        raise SystemExit(
            "Nenhuma pessoa encontrada para gerar o livro ponto (verifique os "
            "filtros e a coluna PONTO/ponto na planilha de entrada)."
        )

    # Os --somente-* escolhem quais livros ganham folhas, sem tirar ninguém
    # de config.pessoas antes de chamar gerar_pdf.
    tipos_incluidos = {
        tipo
        for tipo, somente in (
            (TipoServidor.ADMINISTRATIVO, args.somente_administrativos),
            (TipoServidor.DOCENTE, args.somente_docentes),
            (TipoServidor.GESTAO, args.somente_gestao),
        )
        if somente
    } or None

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_final = gerar_pdf(config, saida, tipos_incluidos=tipos_incluidos)
    print(f"Livro Ponto gerado: {caminho_final}")
    print(
        f"  Escola: {config.escola.nome or '(não informado)'} | "
        f"Mês/Ano: {config.mes:02d}/{config.ano} | "
        f"{len(config.pessoas_por_tipo(TipoServidor.ADMINISTRATIVO))} administrativo(s), "
        f"{len(config.pessoas_por_tipo(TipoServidor.DOCENTE))} docente(s), "
        f"{len(config.pessoas_por_tipo(TipoServidor.GESTAO))} da gestão"
    )


def _cmd_criar_modelo(args: argparse.Namespace) -> None:
    caminho = Path(args.saida)
    criar_modelo(caminho)
    print(f"Modelo criado em: {caminho}")
    print("Preencha as abas 'Escola' e 'Pessoas' e depois rode:")
    print(f"  livroponto gerar --entrada {caminho} --saida livro_ponto.pdf")


def _cmd_app(args: argparse.Namespace) -> None:
    caminho_app = Path(__file__).resolve().parent / "webapp" / "app.py"
    comando = [sys.executable, "-m", "streamlit", "run", str(caminho_app)]
    if args.porta:
        comando += ["--server.port", str(args.porta)]
    try:
        subprocess.run(comando, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(
            "Streamlit não encontrado. Instale com: pip install streamlit"
        ) from exc
    except KeyboardInterrupt:
        pass


def _cmd_desktop(args: argparse.Namespace) -> None:
    try:
        from .desktop.app import main as abrir_app_desktop
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Tkinter não está disponível neste Python (módulo 'tkinter' ausente). "
            "No Windows/Mac ele já vem com o Python; no Linux instale o pacote "
            "'python3-tk' da sua distribuição."
        ) from exc
    abrir_app_desktop()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="livroponto",
        description="Gera o Livro Ponto (registro de frequência) escolar em PDF.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_gerar = sub.add_parser("gerar", help="Gera o PDF do Livro Ponto a partir de uma planilha.")
    p_gerar.add_argument(
        "--entrada",
        required=True,
        help="Planilha de entrada: o arquivo legado .xlsb (SEDUC-SP) ou o modelo simplificado .xlsx.",
    )
    p_gerar.add_argument(
        "--formato-entrada",
        choices=["xlsb", "xlsx"],
        default=None,
        help="Força o formato de leitura (por padrão é detectado pela extensão do arquivo).",
    )
    p_gerar.add_argument("--saida", required=True, help="Caminho do PDF a ser gerado.")
    p_gerar.add_argument("--mes", type=int, default=None, help="Mês (1-12). Padrão: o do arquivo de entrada.")
    p_gerar.add_argument("--ano", type=int, default=None, help="Ano (ex.: 2026). Padrão: o do arquivo de entrada.")
    p_gerar.add_argument("--uf", default=None, help="UF para cálculo de feriados estaduais (padrão: SP).")
    p_gerar.add_argument("--cidade", default=None, help="Cidade usada na assinatura dos termos.")
    p_gerar.add_argument(
        "--feriados-extra",
        default=None,
        help="Caminho de um JSON com recesso/pontos facultativos/feriados municipais (veja README).",
    )
    p_gerar.add_argument(
        "--somente-docentes", action="store_true", help="Gera o livro apenas para o pessoal docente."
    )
    p_gerar.add_argument(
        "--somente-administrativos",
        action="store_true",
        help="Gera o livro apenas para o pessoal administrativo.",
    )
    p_gerar.add_argument(
        "--somente-gestao",
        action="store_true",
        help="Gera o livro apenas para o trio gestor (Diretor(a), Vice-Diretor(a), Coordenador de Gestão Pedagógica).",
    )
    p_gerar.set_defaults(func=_cmd_gerar)

    p_modelo = sub.add_parser(
        "criar-modelo", help="Cria uma planilha .xlsx modelo para preencher manualmente."
    )
    p_modelo.add_argument("--saida", default="modelo_livro_ponto.xlsx")
    p_modelo.set_defaults(func=_cmd_criar_modelo)

    p_desktop = sub.add_parser(
        "desktop",
        help="Abre o app nativo (janela Tkinter, sem navegador nem servidor) para editar os dados e gerar o PDF.",
    )
    p_desktop.set_defaults(func=_cmd_desktop)

    p_app = sub.add_parser(
        "app",
        help="Abre o app web (Streamlit, no navegador) para editar os dados e gerar o PDF.",
    )
    p_app.add_argument("--porta", type=int, default=None, help="Porta do servidor (padrão do Streamlit).")
    p_app.set_defaults(func=_cmd_app)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = construir_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
