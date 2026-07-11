# Spec: Revisão da tela Partidas (2026-07-11)

Objetivo: achar partida rápido; acompanhar hoje/próximos; resultados por data;
filtros claros; detalhe fácil. Reduzir densidade e criar hierarquia.

Estrutura alvo:
1. Header compacto com métricas.
2. "Hoje e próximos" (destaque, jogos de hoje/amanhã com peso visual maior).
3. "Últimos resultados".
4. Barra de filtros única: busca textual por seleção, fase (atalho "Quartas"
   quando for a fase atual), status, data, limpar filtros — sem pílulas soltas.
5. Calendário completo agrupado por data (área de arquivo), toggle Por data /
   Por fase, fonte de times/placares um pouco maior, menos cara de tabela admin.
6. Estado vazio bem escrito.

Regras: linha inteira clicável (botão de abrir é secundário); estados visuais
claros para futuro/encerrado/ao vivo; hover/focus visíveis em tudo.

Aceite: próximo jogo em <5s; busca por seleção funciona; calendário completo
não domina a primeira dobra; sem contradição de estados.

**Status 2026-07-11:** implementado — filter bar polida, badges hoje/amanhã, busca e blocos de destaque.
