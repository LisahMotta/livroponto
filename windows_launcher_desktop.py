"""Ponto de entrada do executável Windows nativo (Tkinter), gerado com
PyInstaller — sem navegador, sem servidor local: uma janela de desktop.
"""
from __future__ import annotations

import sys


def main() -> None:
    if "--check" in sys.argv[1:]:
        # Smoke test usado pelo CI: só confirma que os módulos empacotados
        # importam corretamente, sem abrir a janela.
        import livroponto.desktop.app  # noqa: F401

        print("OK")
        return

    from livroponto.desktop.app import main as abrir_janela

    abrir_janela()


if __name__ == "__main__":
    main()
