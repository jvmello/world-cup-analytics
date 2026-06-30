# Feature 002: Pipeline FIFA PDF 2026 e seleção de edição

**Criado em**: 2026-06-21  
**Status**: Validada pelo pedido do usuário  
**Fonte de verdade**: `orchestra.md`

## 🎯 Visão Geral

Adicionar uma ingestão incremental de relatórios pós-jogo FIFA em PDF, mantendo o
pipeline StatsBomb existente, e permitir que a aplicação alterne entre as edições
2022 e 2026. O PDF de referência obrigatório é
`data/pdf/PMSR-M07-BRA-V-MAR.pdf`.

## 👤 User Stories & Cenários de Teste

### US1 - Ingestão incremental de PDFs (P1)

Como mantenedor, quero adicionar PDFs em `data/pdf/inbox/` e executar um comando
que processe apenas documentos novos ou alterados.

Critérios de aceitação:

- Cada documento recebe `document_id` estável derivado do SHA-256.
- Reprocessar o mesmo PDF não duplica linhas.
- Texto, tabelas brutas, metadados e problemas de extração ficam auditáveis.
- Um PDF inválido não impede o processamento dos demais.

### US2 - CSVs agrupados por domínio (P1)

Como analista, quero CSVs separados por domínio para usar dados agregados da FIFA
sem depender do PDF em tempo de tela.

Critérios de aceitação:

- A saída inclui datasets de documentos, páginas, tabelas brutas, partidas,
  estatísticas de times, fases de jogo, tentativas e métricas de jogadores.
- Toda linha preserva `document_id`, `match_id`, fonte, página e confiança.
- Valores não confiáveis permanecem brutos e geram um registro de issue.

### US3 - Alternância 2022/2026 (P1)

Como usuário, quero selecionar 2022 ou 2026 uma única vez e manter essa escolha
ao navegar entre as páginas.

Critérios de aceitação:

- A edição selecionada é compartilhada pelas páginas Streamlit.
- Em 2022, as telas continuam usando StatsBomb.
- Em 2026, as telas usam CSVs FIFA disponíveis.
- Componentes de evento granular não são exibidos como disponíveis quando a
  fonte possui somente dados agregados.

## Casos de borda

- PDF duplicado, renomeado ou reprocessado.
- PDF incompleto, protegido ou com páginas sem texto.
- Tabela cuja fonte embutida produz caracteres privados.
- Página de domínio novo ainda sem parser específico.
- Edição 2026 sem CSVs gerados.
- Métrica presente para apenas um time ou jogador.

## 📋 Requisitos

### Requisitos funcionais

- RF-001: A entrada padrão deve ser `data/pdf/inbox/`.
- RF-002: A CLI deve aceitar também um arquivo PDF explícito.
- RF-003: O pipeline deve processar todos os PDFs elegíveis em lote.
- RF-004: Os CSVs devem usar escrita idempotente por chaves naturais.
- RF-005: O parser deve classificar páginas por domínio.
- RF-006: O sistema deve preservar texto e tabelas brutas para auditoria.
- RF-007: A UI deve suportar somente 2022 e 2026 neste ciclo.
- RF-008: A UI deve renderizar seções conforme `data_coverage_level`.
- RF-009: O código não deve alterar nem remover o pipeline StatsBomb.

## Requisitos não funcionais

- RNF-001: Processamento local e determinístico.
- RNF-002: Nenhuma escrita em banco ou ambiente de produção.
- RNF-003: Falhas devem ser isoladas por documento.
- RNF-004: Dados de origem e hash devem permitir rastreabilidade.
- RNF-005: O dashboard não deve abrir PDFs diretamente.

## Entidades

- `PdfDocument`: identidade, hash, arquivo, versão do parser e status.
- `PdfPage`: texto bruto e domínio classificado.
- `RawTable`: células extraídas com coordenadas de página/tabela/linha/coluna.
- `MatchSummary`: metadados canônicos da partida.
- `TeamMetric`: métrica agregada por time.
- `PlayerMetric`: métrica agregada por jogador e domínio.
- `ExtractionIssue`: aviso ou erro com contexto e confiança.

## ✅ Critérios de Sucesso

- CS-001: O PDF-base produz um resumo de partida e métricas para Brasil e Marrocos.
- CS-002: Duas execuções consecutivas geram a mesma contagem de linhas.
- CS-003: Os 18 testes existentes continuam passando.
- CS-004: A seleção 2022/2026 não quebra páginas sem granularidade avançada.

## Conformidade

- [x] Library-first: implementação em `src/fifa_pdf/`.
- [x] CLI: `python -m fifa_pdf.cli`.
- [x] Test-first: testes escritos antes da implementação.
- [x] Simplicidade: CSV local e `pdfplumber`, sem banco ou orquestrador externo.
- [x] Anti-abstração: classes apenas para extração, parsing, storage e pipeline.

## Fora de escopo

- OCR completo de PDFs digitalizados.
- Mapas de eventos ou xG por lance para PDFs FIFA.
- Airflow, API ou migração para React.
- Processamento automático em background sem comando explícito.
