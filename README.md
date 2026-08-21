# livroponto

Aplicativo em Python que gera o **Livro Ponto** (registro de frequência) de
uma escola em PDF, pronto para impressão: termo de abertura, uma folha por
servidor com o calendário do mês para assinatura manual de entrada/saída, e
termo de encerramento — para o pessoal administrativo e para o pessoal
docente.

Foi construído a partir do modelo de planilha "LIVRO PONTO" (.xlsb) usado
pelas escolas da rede estadual de São Paulo (SEDUC-SP), automatizando o que
lá é feito manualmente com fórmulas: montar o calendário do mês, marcar
feriados/fins de semana/recesso, e emitir uma folha por pessoa.

## O que o app faz

- Lê os dados da escola e dos servidores de **duas fontes possíveis**:
  1. A planilha legada `.xlsb` (abas `Escola`, `Funcionários`, `Professores`,
     `LP-Abertura`) — o mesmo modelo usado pelas escolas da rede estadual.
  2. Um modelo `.xlsx` simplificado (gerado pelo próprio app), para quem não
     tem a planilha legada.
- Monta o calendário do mês informado, marcando automaticamente:
  - feriados nacionais e estaduais (via [`holidays`](https://pypi.org/project/holidays/), por UF);
  - sábados e domingos;
  - exceções extras informadas manualmente em JSON (recesso escolar, ponto
    facultativo, suspensão de atividades, ou um sábado letivo de reposição).
- Gera um **PDF** com:
  - termo de abertura e termo de encerramento (um par para o livro dos
    administrativos, outro para o dos docentes — só é gerado o grupo que
    tiver gente);
  - uma folha por servidor, com cabeçalho (nome, RG, cargo/função, jornada,
    horário — ou disciplina(s)/categoria no caso de docentes) e uma tabela
    com todos os dias do mês, marcando os dias não úteis e deixando em
    branco os campos de hora/assinatura de entrada e saída para
    preenchimento manual.

## O que **não** está implementado (fora do escopo desta v1)

A planilha original também controla substituições, BO (boletim de
ocorrência de aulas), Ficha 100, ATPC, e a "Folha de Frequência" por
período/aula de cada docente (grade semanal de aulas). Esse é um universo
de regras muito mais amplo que o registro de ponto em si (que é o que os
termos de abertura da própria planilha descrevem: "destina-se ao registro
do Ponto"), e ficou fora desta primeira versão — o foco aqui é emitir o
livro ponto (entrada/saída assinada) de forma correta e reaproveitável.

## Instalação

```bash
pip install -r requirements.txt
pip install -e .        # opcional: registra o comando `livroponto`
```

Requer Python 3.10+.

## Uso

### 1. A partir da planilha legada (.xlsb)

```bash
livroponto gerar \
  --entrada "LIVRO_PONTO_2019__FUNC_E_PROF_abril_2019.xlsb" \
  --mes 4 --ano 2019 \
  --saida livro_ponto_abril_2019.pdf
```

Se `--mes`/`--ano` forem omitidos, o app usa os valores padrão da aba
`LP-Abertura` do próprio arquivo.

### 2. A partir do modelo simplificado (.xlsx)

Gere o modelo em branco:

```bash
livroponto criar-modelo --saida modelo_livro_ponto.xlsx
```

Preencha as abas **Escola** (campo/valor) e **Pessoas** (uma linha por
servidor — colunas `tipo`, `nome`, `rg`, `cargo`, `jornada_semanal`,
`ponto`, `entrada`, `saida`, `intervalo_inicio`, `intervalo_fim`,
`disciplinas`, `categoria`, `situacao`, `observacoes`) e então:

```bash
livroponto gerar --entrada modelo_livro_ponto.xlsx --saida livro_ponto.pdf
```

### Feriados/recessos extras

Feriados nacionais e estaduais são calculados automaticamente (padrão UF
`SP`). Para recesso escolar, pontos facultativos municipais, suspensão de
atividades ou um sábado letivo de reposição, informe um JSON (veja
[`exemplos/feriados_extra_exemplo.json`](exemplos/feriados_extra_exemplo.json)):

```json
[
  {"mes": 4, "dia": 19, "tipo": "PONTO_FACULTATIVO", "descricao": "Aniversário do município"},
  {"mes": 7, "dia": 8, "tipo": "RECESSO", "descricao": "Recesso escolar"},
  {"mes": 6, "dia": 21, "tipo": "LETIVO", "descricao": "Sábado letivo (reposição)"}
]
```

```bash
livroponto gerar --entrada dados.xlsb --mes 7 --ano 2026 \
  --feriados-extra exemplos/feriados_extra_exemplo.json \
  --saida livro_ponto_julho_2026.pdf
```

Outras opções úteis: `--uf` (feriado estadual, padrão `SP`), `--cidade`
(usada na assinatura dos termos), `--somente-docentes` /
`--somente-administrativos`.

## Estrutura do projeto

```
livroponto/
  models.py             dataclasses: Escola, Pessoa, LivroPontoConfig...
  calendario.py          monta o calendário do mês e classifica cada dia
  holidays_br.py          feriados nacionais/estaduais + exceções manuais
  readers/
    xlsb_reader.py         lê a planilha legada .xlsb (SEDUC-SP)
    template_reader.py     lê/gera o modelo simplificado .xlsx
  pdf/
    builder.py              monta o PDF final (termos + folhas)
  cli.py                  comando `livroponto` (gerar / criar-modelo)
tests/                    testes automatizados (dados fictícios)
exemplos/                 exemplo de JSON de feriados/recesso extras
```

## Testes

```bash
pip install pytest
pytest
```

Os testes usam apenas dados fictícios gerados no próprio teste — nenhum
dado real de servidor é incluído neste repositório.

## Privacidade

Este repositório não contém a planilha original nem qualquer dado real de
servidor/professor — apenas o código do gerador e dados de exemplo
fictícios. Ao usar o app com sua própria planilha, os arquivos `.xlsb`/
`.xlsx`/`.pdf` de entrada e saída ficam só na sua máquina.
