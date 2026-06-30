# Feature 005: Produtos analíticos particionados por partida

**Criado em**: 2026-06-23
**Status**: Validada pelo pedido do usuário
**Fonte de verdade**: `orchestra.md`

## 🎯 Visão Geral

Publicar cada relatório FIFA em uma pasta independente no formato
`year=YYYY/match=N/`. A pasta deve expor apenas produtos esportivos temáticos.
Metadados técnicos ficam restritos a `_manifest.json`, usado para idempotência e
controle de versão.

## 👤 User Stories

### US1 - Encontrar os dados de uma partida (P1)

Como analista, quero abrir a pasta da edição e da partida e encontrar arquivos
por assunto, sem navegar por documentos, páginas ou células do PDF.

### US2 - Adicionar novos PDFs (P1)

Como mantenedor, quero colocar outro PDF no pipeline e criar automaticamente uma
nova pasta `year=<edição>/match=<número>`.

### US3 - Reprocessar com segurança (P1)

Como mantenedor, quero que o mesmo hash seja ignorado e que uma nova versão do
mesmo jogo atualize os produtos e incremente a versão técnica.

## 📋 Requisitos

- RF-001: A raiz padrão deve ser `data/parsed/fifa_pdf/`.
- RF-002: Ano e número da partida devem vir da capa.
- RF-003: Produtos não devem expor `document_id`, hash ou caminho do PDF.
- RF-004: A pasta deve conter `data_dictionary.csv`.
- RF-005: `_manifest.json` deve ser o único produto técnico.
- RF-006: Todos os produtos temáticos conhecidos devem existir, mesmo vazios.
- RF-007: Seções ainda não totalmente normalizadas devem preservar linhas
  temáticas de forma semiestruturada, sem cair em arquivos genéricos de página.

## ✅ Critérios de Sucesso

- O primeiro PDF cria `year=2026/match=7/`.
- A pasta contém os produtos solicitados e nenhum CSV de metadados do PDF.
- Uma segunda execução com o mesmo PDF é idempotente.
- O dicionário cobre todos os arquivos e campos.

