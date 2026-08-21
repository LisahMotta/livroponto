"""Estruturas de dados usadas pelo gerador de Livro Ponto."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TipoServidor(str, Enum):
    ADMINISTRATIVO = "ADMINISTRATIVO"
    DOCENTE = "DOCENTE"


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
    """Um servidor (administrativo ou docente) que assina o livro ponto."""

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
