"""Estruturas de dados usadas pelo gerador de Livro Ponto."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
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


TIPOS_LICENCA = ["SAUDE", "PREMIO"]
ROTULO_LICENCA = {"SAUDE": "Licença Saúde", "PREMIO": "Licença Prêmio"}


@dataclass
class Licenca:
    """Um período de licença (saúde ou prêmio) de um servidor — cadastrado
    na aba Licenças, não no diálogo de Adicionar/Editar servidor. Um
    servidor pode acumular vários períodos ao longo do tempo; cada um só
    vira anotação na folha de consolidação do(s) mês(es) em que estiver
    de fato em vigor (ver `licencas_em_vigor`)."""

    tipo: str  # SAUDE | PREMIO
    inicio: str = ""  # ex.: "03/04/2026" — data livre, sem formato fixo
    fim: str = ""

    @property
    def periodo(self) -> str:
        if self.inicio and self.fim:
            return f"{self.inicio} a {self.fim}"
        return ""

    @property
    def rotulo(self) -> str:
        return ROTULO_LICENCA.get(self.tipo, self.tipo)


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
    ferias_inicio: str = ""  # ex.: "03/04/2026" — data livre, sem formato fixo — aba Férias
    ferias_fim: str = ""
    licencas: list[Licenca] = field(default_factory=list)  # aba Licenças
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


def _parse_data_br(texto: str) -> date | None:
    """Lê uma data no formato "DD/MM/AAAA" — tolerante: qualquer coisa
    fora desse formato (campo vazio, texto livre) vira None em vez de
    erro, já que os campos de data desses formulários são livres."""
    partes = (texto or "").strip().split("/")
    if len(partes) != 3:
        return None
    try:
        dia, mes, ano = (int(p) for p in partes)
        return date(ano, mes, dia)
    except ValueError:
        return None


def licencas_em_vigor(pessoa: Pessoa, mes: int, ano: int) -> list[Licenca]:
    """Licenças do servidor cujo período tem alguma sobreposição com o
    mês/ano do livro sendo gerado — só essas saem anotadas na folha de
    consolidação; uma licença já encerrada (ou que ainda nem começou) num
    mês diferente do gerado não aparece."""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    vigentes = []
    for licenca in pessoa.licencas:
        inicio = _parse_data_br(licenca.inicio)
        fim = _parse_data_br(licenca.fim)
        if inicio is None or fim is None:
            continue
        if inicio <= ultimo_dia and fim >= primeiro_dia:
            vigentes.append(licenca)
    return vigentes


def ferias_em_vigor(pessoa: Pessoa, mes: int, ano: int) -> bool:
    """Verdadeiro se o período de férias regulares do servidor (aba
    Férias) tem alguma sobreposição com o mês/ano do livro sendo gerado —
    mesma lógica de `licencas_em_vigor`, usada pra só anotar as férias no
    verso (Consolidação) do mês em que elas de fato caem, e não em todo
    livro gerado dali pra frente."""
    inicio = _parse_data_br(pessoa.ferias_inicio)
    fim = _parse_data_br(pessoa.ferias_fim)
    if inicio is None or fim is None:
        return False
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    return inicio <= ultimo_dia and fim >= primeiro_dia


def formatar_rg(texto: str) -> str:
    """Formata um RG no padrão XX.XXX.XXX-X (2-3-3-1 caracteres) conforme
    vai sendo digitado — usada tanto pelo campo RG do cadastro (formata a
    cada tecla) quanto pela impressão da folha de ponto/frequência (pra
    RGs importados ou digitados antes dessa formatação existir também
    saírem no padrão).

    Só reorganiza a pontuação: mantém os caracteres na ordem em que
    foram digitados (não descarta zero à esquerda, não completa dígito
    faltando) e aceita letra no meio dos números — RG de outro estado às
    vezes vem com uma letra (ex.: "M1.234.567-8") em vez de só dígitos."""
    brutos = re.sub(r"[^0-9A-Za-z]", "", texto or "").upper()[:9]
    blocos = [brutos[0:2], brutos[2:5], brutos[5:8], brutos[8:9]]
    blocos = [b for b in blocos if b]
    if not blocos:
        return ""
    separadores = [".", ".", "-"]
    resultado = blocos[0]
    for bloco, separador in zip(blocos[1:], separadores):
        resultado += separador + bloco
    return resultado


def chave_ordenacao_rg(pessoa: Pessoa) -> tuple:
    """Chave de ordenação por número de RG — numérica, não textual ("9"
    vem antes de "10"); RG com letra (de outro estado, ex.: "M1.234.567-8")
    sempre vem primeiro; quem não tem RG cadastrado vai para o fim,
    ordenado por nome. Usada tanto na lista de servidores do app desktop
    quanto na ordem das folhas do PDF gerado, para as duas ficarem
    consistentes.

    O dígito verificador depois do traço (ex.: "9.876.543-2") não faz
    parte do número em si — é descartado antes de comparar. Sem isso, um
    RG com dígito verificador ficaria com um dígito a mais que um RG
    equivalente sem traço (ex.: "9.876.543-2" -> 98765432, 9 dígitos,
    contra "16304137" -> 16304137, 8 dígitos) e pareceria maior do que
    realmente é, saindo antes na ordem quando deveria vir depois.

    O zero à esquerda também não conta pra comparação numérica (ex.:
    "01.234.567-8" -> 1234567, não 01234567) — é só o `int()` de baixo
    convertendo naturalmente, sem descartar dígito nenhum do RG em si."""
    numero = (pessoa.rg or "").split("-")[0]
    bruto = re.sub(r"[^0-9A-Za-z]", "", numero)
    if not bruto:
        return (2, 0, pessoa.nome)
    if re.search(r"[A-Za-z]", bruto):
        return (0, 0, pessoa.nome)
    return (1, int(bruto), pessoa.nome)


@dataclass
class DiaNaoLetivo:
    """Uma exceção de calendário informada manualmente (recesso, ponto
    facultativo, sábado letivo, feriado municipal etc.), que complementa ou
    sobrepõe os feriados nacionais/estaduais calculados automaticamente."""

    mes: int
    dia: int
    tipo: str  # FERIADO | RECESSO | PONTO_FACULTATIVO | SUSPENSAO | LETIVO
    descricao: str = ""


# Rótulo padrão embaixo da assinatura nos termos de abertura/encerramento —
# usado quando `LivroPontoConfig.rotulo_assinatura` está em branco (o caso
# comum: livro de uma escola). Uma URE ou outra unidade não-escolar pode
# trocar por outro texto (ex.: "Dirigente Regional de Ensino") sem precisar
# de nenhuma mudança de código, só preenchendo o campo na aba Escola.
ROTULO_ASSINATURA_PADRAO = "Direção da Unidade Escolar"


@dataclass
class LivroPontoConfig:
    escola: Escola
    mes: int
    ano: int
    pessoas: list[Pessoa] = field(default_factory=list)
    livro_numero: str = ""
    cidade_assinatura: str = ""
    diretor_nome: str = ""
    rotulo_assinatura: str = ""
    uf: str = "SP"
    dias_excecao: list[DiaNaoLetivo] = field(default_factory=list)

    def pessoas_por_tipo(self, tipo: TipoServidor) -> list[Pessoa]:
        return [p for p in self.pessoas if p.tipo == tipo]

    def rotulo_assinatura_efetivo(self) -> str:
        """Texto que sai impresso embaixo da assinatura nos termos — o que
        foi digitado em `rotulo_assinatura` (aba Escola), ou o padrão de
        escola se o campo estiver em branco."""
        return self.rotulo_assinatura.strip() or ROTULO_ASSINATURA_PADRAO

    def nome_diretor(self) -> str:
        """Nome de quem assina o termo de abertura/encerramento — vem
        direto do campo `diretor_nome` cadastrado na aba Escola. Não busca
        mais no cadastro da Gestão: essa busca (por um cargo começando com
        "Diretor") dependia de outra aba e de quais tipos estavam marcados
        em "Incluir" na hora de gerar, e sumia sozinha quando a Gestão não
        entrava naquele PDF."""
        return self.diretor_nome.strip()
