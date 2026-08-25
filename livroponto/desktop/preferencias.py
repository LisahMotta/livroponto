"""Lembra qual foi o último cadastro (.xlsx ou .xlsb) aberto/salvo no app
desktop, num arquivinho de configuração em disco — pra reabrir sozinho na
próxima vez que o app iniciar, em vez de sempre começar em branco e o
usuário ter que ir em "Abrir..." toda vez.

Não usa banco de dados (SQLite) nem nada do tipo: o app já tem um formato
de persistência de verdade, o .xlsx gerado por `salvar_modelo()`/lido por
`ler_modelo()` — os próprios dados do cadastro. O que faltava era só
lembrar ONDE esse arquivo está, entre uma sessão e outra do app; é só
isso que este módulo guarda (um ponteiro pro último caminho, não os
dados em si)."""
from __future__ import annotations

import json
from pathlib import Path

_ARQUIVO_ESTADO = Path.home() / ".livroponto" / "estado.json"


def carregar_ultimo_caminho() -> str | None:
    """Caminho do último cadastro aberto/salvo, ou None se nunca foi
    salvo nenhum (primeira vez usando o app) ou se o arquivo de estado
    estiver ilegível/corrompido — nesse caso o app simplesmente começa
    em branco, como sempre começou."""
    try:
        dados = json.loads(_ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    caminho = dados.get("ultimo_arquivo")
    return caminho if isinstance(caminho, str) and caminho else None


def salvar_ultimo_caminho(caminho: str) -> None:
    """Grava o caminho pra lembrar da próxima vez. Falha silenciosa (ex.:
    sem permissão de escrita na pasta do usuário) — não é crítico, só
    significa que o app não vai reabrir sozinho da próxima vez, igual já
    era o comportamento antes desse recurso existir."""
    try:
        _ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
        _ARQUIVO_ESTADO.write_text(json.dumps({"ultimo_arquivo": caminho}), encoding="utf-8")
    except OSError:
        pass
