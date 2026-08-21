# livroponto

Aplicativo em Python que gera o **Livro Ponto** (registro de frequência) de
uma escola em PDF, pronto para impressão: termo de abertura, uma folha por
servidor com o calendário do mês para assinatura manual de entrada/saída, e
termo de encerramento — para o pessoal administrativo e para o pessoal
docente. Tem um **app web para editar os dados** (escola, servidores,
feriados) direto no navegador, sem precisar mexer em planilha — a linha de
comando (`livroponto gerar`) e a edição manual de um `.xlsx` continuam
funcionando pra quem preferir.

Foi construído a partir do modelo de planilha "LIVRO PONTO" (.xlsb) usado
pelas escolas da rede estadual de São Paulo (SEDUC-SP), automatizando o que
lá é feito manualmente com fórmulas: montar o calendário do mês, marcar
feriados/fins de semana/recesso, e emitir uma folha por pessoa.

## O que o app faz

- **Editor web** (`livroponto app`): edita escola, servidores/professores e
  exceções de calendário em tabelas no navegador, e a partir daí baixa o
  cadastro (`.xlsx`) e/ou o Livro Ponto (`.pdf`) — veja a seção
  [App web](#app-web-editor) abaixo.
- Lê os dados da escola e dos servidores de **duas fontes possíveis**
  (usadas tanto pela linha de comando quanto pelo editor web):
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

## App web (editor)

```bash
livroponto app
```

Abre `http://localhost:8501` no navegador com:

- **Dados da escola** e **período do livro** (mês/ano/UF/cidade) em campos de texto;
- **Servidores e professores** numa tabela editável (adicionar/editar/remover linhas direto na tela — sem abrir Excel);
- **Feriados e exceções de calendário** (recesso, ponto facultativo, suspensão, sábado letivo) em outra tabela editável;
- botão **Salvar cadastro**, que baixa um `.xlsx` com tudo o que foi editado (pra reabrir depois e continuar de onde parou);
- botão **Gerar PDF**, que baixa o Livro Ponto pronto pra imprimir.

Dá pra começar do zero ou carregar um arquivo existente (o `.xlsx` deste
app ou o `.xlsb` legado da rede estadual) pela barra lateral, editar o que
for preciso, e baixar de novo. As edições ficam só na sessão do navegador
até você clicar em salvar — nada é gravado automaticamente em disco.

Use `livroponto app --porta 8600` para escolher outra porta.

## Uso pela linha de comando

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

Preencha as abas **Escola** (campo/valor), **Pessoas** (uma linha por
servidor — colunas `tipo`, `nome`, `rg`, `cargo`, `jornada_semanal`,
`jornada_codigo`, `ponto`, `entrada`, `saida`, `intervalo_inicio`,
`intervalo_fim`, `disciplinas`, `categoria`, `situacao`, `observacoes`) e
**Excecoes** (opcional — colunas `mes`, `dia`, `tipo`, `descricao`, mesmo
formato do JSON descrito abaixo) — ou preencha tudo isso pelo
[app web](#app-web-editor), que gera esse mesmo arquivo. Depois:

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
    template_reader.py     lê/grava o modelo simplificado .xlsx
  pdf/
    builder.py              monta o PDF final (termos + folhas)
  webapp/
    app.py                   app Streamlit (editor web)
    state.py                 conversão entre modelos e DataFrames das tabelas
  cli.py                  comando `livroponto` (gerar / criar-modelo / app)
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
