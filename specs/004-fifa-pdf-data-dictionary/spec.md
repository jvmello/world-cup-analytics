# Feature 004: Dicionário e snapshot de execução FIFA PDF

**Criado em**: 2026-06-23
**Status**: Validada pelo pedido do usuário
**Fonte de verdade**: `orchestra.md`

## 🎯 Visão Geral

Documentar os dados efetivamente extraídos do primeiro relatório FIFA
`data/pdf/PMSR-M07-BRA-V-MAR.pdf` e salvar uma execução reproduzível do parser
com seus produtos bronze e silver.

## 👤 User Stories

### US1 - Consultar o dicionário de dados (P1)

Como analista, quero entender grão, chave, tipo, significado e exemplo de cada
campo para usar os CSVs sem reler o código do parser.

### US2 - Auditar uma execução (P1)

Como mantenedor, quero um pacote imutável por execução contendo manifesto,
hashes, contagens, timestamps, versão do parser e produtos parseados.

## 📋 Requisitos

- RF-001: O dicionário deve cobrir os três produtos bronze e seis silver.
- RF-002: O dicionário deve distinguir valor normalizado de `raw_value`.
- RF-003: A execução deve usar diretórios isolados, sem mesclar snapshots.
- RF-004: O manifesto deve registrar fonte, SHA-256, parser, status, datasets,
  campos, contagens e hashes dos produtos.
- RF-005: O pacote deve conter cópias dos CSVs produzidos.
- RF-006: A execução deve possuir identificador configurável ou temporal.
- RF-007: Falha de processamento deve resultar em código de saída não zero.

## ✅ Critérios de Sucesso

- O PDF-base gera um pacote com nove CSVs, `manifest.json` e `execution.txt`.
- O manifesto informa 52 páginas e as contagens reais de cada dataset.
- Todos os hashes registrados correspondem aos arquivos salvos.
- O dicionário Markdown e CSV descrevem todos os campos de `storage.DATASETS`.
- Testes existentes continuam passando.

