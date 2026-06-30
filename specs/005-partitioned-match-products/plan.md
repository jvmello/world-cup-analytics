# Plano técnico: Produtos particionados por partida

## Fluxo

```text
PDF
 -> extração e parsers existentes
 -> publicação temática
 -> data/parsed/fifa_pdf/year=YYYY/match=N/*.csv
```

## Estratégia

- Reutilizar os parsers normalizados existentes.
- Pivotar métricas individuais para um registro por jogador.
- Derivar resumos de finalização.
- Preservar seções adicionais em arquivos temáticos semiestruturados.
- Manter idempotência em `_manifest.json`.

## Arquivos

- `src/fifa_pdf/publication.py`
- `tests/test_fifa_pdf_pipeline.py`
- `docs/fifa_match_products_dictionary.md`
- `data/parsed/fifa_pdf/year=2026/match=7/`

