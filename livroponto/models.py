"""Estruturas de dados usadas pelo gerador de Livro Ponto."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TipoServidor(str, Enum):
    ADMINISTRATIVO = "ADMINISTRATIVO"
    DOCENTE = "DOCENTE"
    GESTAO = "GESTAO"  # trio gestor: Diretor(a), Vice-Diretor(a), Coordenador de Gestão Pedagógica


@dataclass
class Escola:
    nome: str = ""
    diretoria_ensino: str = ""
    endereco: str = ""
    municipio: str = ""
    telefone1: str = ""
    telefone2: str = ""
    email: str = ""
    codigo_ua: str = ""
    codigo_cie: str = ""


@dataclass
class Pessoa:
    """Um servidor (administrativo, docente ou do trio gestor) que assina o
    livro ponto. O trio gestor (TipoServidor.GESTAO) usa os mesmos campos do
    administrativo (RG, cargo, jornada semanal, horário) — clocka ponto do
    mesmo jeito, só entra num livro próprio, separado."""

    nome: str
    tipo: TipoServidor
    rg: str = ""
    cargo: str = ""
    jornada_semanal: Optional[float] = None
    ponto: bool = True
    entrada: str = ""
    saida: str = ""
    intervalo_inicio: str = ""
    intervalo_fim: str = ""
    disciplinas: str = ""
    categoria: str = ""
    situacao: str = ""
    jornada_codigo: str = ""  # p.ex. R/I/B/C (Reduzida/Inicial/Básica/Integral) — só docentes
    observacoes: str = ""
    ferias_inicio: str = ""  # ex.: "03/04/2026" — data livre, sem formato fixo
    ferias_fim: str = ""
    seq: Optional[int] = None

    @property
    def horario_trabalho(self) -> str:
        if self.entrada and self.saida:
            return f"DAS {self.entrada} ÀS {self.saida}"
        return ""

    @property
    def intervalo(self) -> str:
        if self.intervalo_inicio and self.intervalo_fim:
            return f"DAS {self.intervalo_inicio} ÀS {self.intervalo_fim}"
        return ""

    @property
    def periodo_ferias(self) -> str:
        if self.ferias_inicio and self.ferias_fim:
            return f"{self.ferias_inicio} a {self.ferias_fim}"
        return ""


def chave_ordenacao_rg(pessoa: Pessoa) -> tuple:
    """Chave de ordenação por número de RG — numérica, não textual ("9"
    vem antes de "10"); quem não tem RG cadastrado vai para o fim,
    ordenado por nome. Usada tanto na lista de servidores do app desktop
    quanto na ordem das folhas do PDF gerado, para as duas ficarem
    consistentes.

    O dígito verificador depois do traço (ex.: "9.876.543-2") não faz
    parte do número em si — é descartado antes de comparar. Sem isso, um
    RG com dígito verificador ficaria com um dígito a mais que um RG
    equivalente sem traço (ex.: "9.876.543-2" -> 98765432, 9 dígitos,
    contra "16304137" -> 16304137, 8 dígitos) e pareceria maior do que
    realmente é, saindo antes na ordem quando deveria vir depois."""
    numero = (pessoa.rg or "").split("-")[0]
    digitos = re.sub(r"\D", "", numero)
    if digitos:
        return (0, int(digitos), pessoa.nome)
    return (1, 0, pessoa.nome)


@dataclass
class DiaNaoLetivo:
    """Uma exceção de calendário informada manualmente (recesso, ponto
    facultativo, sábado letivo, feriado municipal etc.), que complementa ou
    sobrepõe os feriados nacionais/estaduais calculados automaticamente."""

    mes: int
    dia: int
    tipo: str  # FERIADO | RECESSO | PONTO_FACULTATIVO | SUSPENSAO | LETIVO
    descricao: str = ""


@dataclass
class LivroPontoConfig:
    escola: Escola
    mes: int
    ano: int
    pessoas: list[Pessoa] = field(default_factory=list)
    livro_numero: str = ""
    cidade_assinatura: str = ""
    uf: str = "SP"
    dias_excecao: list[DiaNaoLetivo] = field(default_factory=list)

    def pessoas_por_tipo(self, tipo: TipoServidor) -> list[Pessoa]:
        return [p for p in self.pessoas if p.tipo == tipo]

    def nome_diretor(self) -> str:
        """Nome do(a) Diretor(a) de Escola cadastrado no trio gestor, se
        houver ("Vice-Diretor(a)" não conta — o cargo precisa começar com
        "Diretor"). Retorna string vazia se não houver ninguém cadastrado
        com esse cargo. Usado para assinar "Direção da Unidade Escolar" nos
        termos de abertura/encerramento do livro (administrativo/docente)."""
        for pessoa in self.pessoas_por_tipo(TipoServidor.GESTAO):
            if pessoa.cargo.strip().lower().startswith("diretor"):
                return pessoa.nome
        return ""
