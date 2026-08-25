"""Preferências do app desktop guardadas num arquivinho de configuração em
disco (~/.livroponto/estado.json) — não tem nada a ver com o cadastro do
Livro Ponto em si (esse continua sendo o .xlsx de sempre, via
`salvar_modelo()`/`ler_modelo()`). O que mora aqui é só:

- o caminho do último cadastro aberto/salvo, pra reabrir sozinho na
  próxima vez que o app iniciar, em vez de sempre começar em branco;
- se o tutorial de primeiro uso já foi mostrado, pra não aparecer sozinho
  de novo (o botão de acesso rápido continua funcionando a qualquer hora).

Não usa banco de dados (SQLite) nem nada do tipo: é só um ponteiro/flag,
não os dados do cadastro."""
from __future__ import annotations

import json
from pathlib import Path

_ARQUIVO_ESTADO = Path.home() / ".livroponto" / "estado.json"


def _carregar_estado() -> dict:
    try:
        dados = json.loads(_ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _salvar_estado(dados: dict) -> None:
    """Falha silenciosa (ex.: sem permissão de escrita na pasta do
    usuário) — não é crítico, só significa que essa preferência não vai
    ser lembrada da próxima vez, igual já era o comportamento antes
    desse recurso existir."""
    try:
        _ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
        _ARQUIVO_ESTADO.write_text(json.dumps(dados), encoding="utf-8")
    except OSError:
        pass


def carregar_ultimo_caminho() -> str | None:
    """Caminho do último cadastro aberto/salvo, ou None se nunca foi
    salvo nenhum (primeira vez usando o app) ou se o arquivo de estado
    estiver ilegível/corrompido — nesse caso o app simplesmente começa
    em branco, como sempre começou."""
    caminho = _carregar_estado().get("ultimo_arquivo")
    return caminho if isinstance(caminho, str) and caminho else None


def salvar_ultimo_caminho(caminho: str) -> None:
    dados = _carregar_estado()
    dados["ultimo_arquivo"] = caminho
    _salvar_estado(dados)


def tutorial_ja_visto() -> bool:
    return bool(_carregar_estado().get("tutorial_visto"))


def marcar_tutorial_visto() -> None:
    dados = _carregar_estado()
    dados["tutorial_visto"] = True
    _salvar_estado(dados)
