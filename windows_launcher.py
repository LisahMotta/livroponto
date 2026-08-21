"""Ponto de entrada do executável Windows (gerado com PyInstaller).

Empacota o app web (Streamlit) do livroponto num único .exe: ao dar
duplo-clique, sobe o servidor local e abre o navegador automaticamente —
sem precisar instalar Python nem nada pela linha de comando.
"""
from __future__ import annotations

import os
import sys


def _caminho_app() -> str:
    # Dentro do .exe empacotado, os arquivos ficam em sys._MEIPASS
    # (pasta temporária onde o PyInstaller extrai tudo em tempo de execução).
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "livroponto", "webapp", "app.py")


def main() -> None:
    args = sys.argv[1:]

    if "--check" in args:
        # Smoke test usado pelo CI: só confirma que os módulos empacotados
        # importam corretamente, sem subir o servidor nem abrir navegador.
        import livroponto.webapp.state  # noqa: F401
        import streamlit  # noqa: F401

        print("OK")
        return

    from streamlit.web import cli as stcli

    # Empacotado pelo PyInstaller, o Streamlit não acha os metadados do
    # pacote (importlib.metadata) e liga "developmentMode" sozinho — o que
    # por sua vez proíbe usar --server.port. Desligamos aqui sempre.
    extras = args if args else ["--server.headless=false"]
    sys.argv = ["streamlit", "run", _caminho_app(), "--global.developmentMode=false", *extras]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
