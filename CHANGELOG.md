# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
A partir da v1.0.0, mudanças de DDL são versionadas em
`docker/postgres/migrations/` (ver `specs/017-v1-governanca/`).

## Não lançado

### Corrigido
- Placar de partidas decididas na prorrogação: o placar público agora inclui os
  gols do tempo extra (fonte: `after_extra_time`), e "venceu nos pênaltis" só
  aparece quando houve disputa de verdade (`penalty_shootout` + flag da fonte).
  Antes, Argentina 3–1 Suíça (prorrogação) era exibido como "1–1, Argentina
  venceu nos pênaltis por 3–1". Novo badge e narrativa "na prorrogação" no
  herói da partida, no pulso da Home e no chaveamento. Requer rebuild do gold.

## v1.0.0 — 2026-07-11

Primeira versão em produção (worldcup.jvmello.dev).

### Dados e infraestrutura
- Camada gold de serving no PostgreSQL: payloads pré-computados por endpoint,
  build atômico (staging + swap) a partir do bronze, fallback bronze.
- Sync automático (`thestatsapi.sync`): varre partidas encerradas, ingere
  bundles faltantes e rematerializa o gold; lock contra sobreposição; cron.
- Deploy via jvmello-infra (Caddy + Cloudflare, Postgres fechado, backups).
- Admin desativado por ora (rotas comentadas, teste-trava).

### Produto
- Home editorial: resumo com barra de progresso, pulso com fase em destaque,
  destaques sem repetição, líderes divididos (jogadores × seleções).
- Partidas: hoje/próximos + últimos resultados, busca por seleção, badges
  hoje/amanhã, atalho de fase.
- Competição: aba padrão pela fase atual, resumo estrutural, salto A–L.
- Detalhe de partida: cores de camisa reais por partida (kit colors FIFA),
  mapa de pênaltis com disputa separada do xG, veredito de pênaltis no header,
  impacto com soft-knee e pesos de disputa, tabela de jogadores enxuta.
- Jogadores/Seleções: scatters legíveis (pontos + destaques), quadrantes
  interpretativos, destaques variados, breakdowns em barras.
- Perfis: contextos de destaque, diagnóstico da seleção, radar 540px,
  comparáveis com ação de comparar, seletor recolhível.
- Comparar: seletor colapsável, radar grande, tabela agrupada colapsável,
  leituras de confronto.
- Sobre: página completa (fontes, metodologia, limitações, contato).
