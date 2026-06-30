# Plano técnico: FIFA PDF 2026

## Arquivos

### Criar

- `src/fifa_pdf/models.py`: contratos internos.
- `src/fifa_pdf/extractor.py`: extração de páginas e tabelas.
- `src/fifa_pdf/parsers.py`: classificação e normalização por domínio.
- `src/fifa_pdf/storage.py`: upsert idempotente dos CSVs.
- `src/fifa_pdf/pipeline.py`: orquestração por documento/lote.
- `src/fifa_pdf/cli.py`: interface de linha de comando.
- `app/edition_context.py`: edição global 2022/2026.
- `app/fifa_pdf_data.py`: loader dos CSVs FIFA.
- `tests/test_fifa_pdf_pipeline.py`: parser, contratos e idempotência.
- `tests/test_edition_context.py`: regras de edição e cobertura.

### Alterar

- `app/streamlit_app.py` e `app/pages/*.py`: seleção e fallback por cobertura.
- `Makefile`: comandos do pipeline PDF e testes.
- `requirements.txt`: `pdfplumber`.
- `README.md`: operação e estrutura dos CSVs.

## Fluxo

```text
data/pdf/inbox/*.pdf
    -> SHA-256 + manifest
    -> pdfplumber
    -> Bronze CSV: documents, pages, raw_tables
    -> parsers por domínio
    -> Silver CSV: matches, team_metrics, phases, attempts, player_metrics
    -> Streamlit 2026
```

O arquivo de referência fora da inbox pode ser processado com `--file`.

## Datasets CSV

### Bronze

- `documents.csv`
- `pages.csv`
- `raw_tables.csv`

### Silver

- `match_summary.csv`
- `team_key_statistics.csv`
- `phases_of_play.csv`
- `attempts_at_goal.csv`
- `player_metrics.csv`
- `extraction_issues.csv`

`player_metrics.csv` é long-form e distingue o domínio em `metric_group`, evitando
um arquivo frágil para cada layout de página. As tabelas brutas permitem criar
parsers específicos adicionais sem reabrir decisões antigas.

## Decisões

- `pdfplumber` foi escolhido porque o PDF-base possui texto pesquisável e tabelas.
- Caracteres privados usados nos dados físicos serão normalizados por mapa
  explícito; valores ainda ambíguos terão confiança reduzida.
- A UI usará um seletor global salvo no `st.session_state`.
- 2026 terá cobertura `fifa_pdf`; mapas de coordenadas continuarão exclusivos de
  `advanced_event_data`.

## Testes

- Parsing de metadados da capa.
- Parsing bilateral de key statistics e fases de jogo.
- Normalização dos dígitos privados.
- Classificação de páginas.
- Upsert idempotente por chaves.
- Falha isolada por PDF.
- Edição válida e cobertura esperada.
- Suíte legada e sintaxe.

## Riscos

- Layouts futuros podem mudar: mitigar com classificação por título, raw tables e
  issues em vez de falha global.
- Extração tabular pode mesclar células: usar texto como fonte principal nos
  parsers conhecidos.
- Dados físicos usam encoding especial: preservar `raw_value`.
- CSV concorrente não será suportado neste ciclo; executar uma instância por vez.

