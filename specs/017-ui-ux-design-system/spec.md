# Spec: Revisão global UI/UX e design system 2026

Objetivo: consolidar regras reutilizáveis para o World Cup Analytics 2026,
mantendo a identidade editorial escura já existente e reduzindo inconsistências
entre Home, Competição, Partidas, Jogadores, Seleções, Perfil e Match Center.

Escopo:
- padronizar header de página, seções, cards, filtros, tabs, tabelas, rankings,
  barras, scatters, radares, mapas de chutes, timelines, estados vazios,
  tooltips e CTAs;
- manter visual editorial, não administrativo;
- não alterar ingestão, banco, Bronze, Silver, Gold ou contratos de dados.

Regras globais:
- todo gráfico deve ter título, subtítulo e legenda quando necessário;
- toda métrica derivada deve ter tooltip com fórmula;
- todo ranking deve indicar escopo: total, por jogo, por 90 ou percentual;
- todo filtro deve deixar claro o que afeta;
- todo item clicável deve ter hover/focus;
- nenhum ID interno ou texto técnico cru deve aparecer na UI pública;
- “Pular para o conteúdo” só aparece em foco;
- scatters densos usam pontos simples, não bandeiras em massa;
- pie charts devem ceder lugar a barras quando houver muitas categorias;
- estrelas em mapas de chute têm tamanho máximo;
- radares têm tamanho mínimo e legenda clara;
- tabelas longas usam agrupamento, scroll, disclosure ou modal;
- cards de diagnóstico usam texto curto e métrica de apoio.

Implementação inicial:
- contrato global de fórmulas e escopos de ranking em `webapp/static/app.js`;
- atributos semânticos em cards métricos, barras e painéis de gráfico;
- estado de foco consistente para CTAs, tabs, cards clicáveis e botões;
- estados vazios com texto amigável já preservados por `emptyState`;
- testes estáticos cobrindo as regras centrais.
