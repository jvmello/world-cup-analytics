# Plano técnico: Dicionário e snapshot FIFA PDF

## Fluxo

```text
PDF de referência
  -> fifa_pdf.snapshot
  -> diretório isolado da execução
      -> bronze/*.csv
      -> silver/*.csv
      -> manifest.json
      -> execution.txt
```

## Arquivos

- `src/fifa_pdf/snapshot.py`: execução isolada e manifesto.
- `tests/test_fifa_pdf_pipeline.py`: contrato do snapshot.
- `docs/fifa_pdf_data_dictionary.md`: documentação humana.
- `docs/fifa_pdf_data_dictionary.csv`: catálogo tabular.
- `data/runs/fifa_pdf/2026/<run_id>/`: execução materializada.

## Validação

- Teste unitário de contagens, schemas e SHA-256 do manifesto.
- Execução real sobre `PMSR-M07-BRA-V-MAR.pdf`.
- Comparação das contagens com os contratos existentes.

