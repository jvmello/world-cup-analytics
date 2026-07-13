# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
A partir da v1.0.0, mudanças de DDL são versionadas em
`docker/postgres/migrations/` (ver `specs/017-v1-governanca/`).

## Não lançado

### Adicionado
- Prognóstico pré-jogo: partidas ainda não realizadas (qualquer fase, desde
  que os dois times já estejam definidos e com estatísticas na Copa) passam a
  mostrar gols/jogo, xG/jogo, finalizações/jogo e cartões/jogo lado a lado,
  em barras pintadas com a cor de uniforme de cada seleção — sem veredito de
  quem deve vencer. Antes disso a página só mostrava "partida não
  encontrada". Pré-computado no build do gold (`_build_fixture_prognosis`
  reaproveita os agregados de seleção já calculados no mesmo build); fallback
  ao vivo no bronze quando o gold ainda não tem a linha.

### Corrigido
- Ordem da chave de mata-mata: as colunas de Fase de 32 até Semifinais eram
  ordenadas por data do jogo, então dois confrontos que alimentam o mesmo jogo
  da rodada seguinte apareciam espalhados (ex.: Suíça × Argélia longe de
  Colômbia × Gana, embora as duas decidam quem enfrenta quem nas oitavas).
  Agora a ordem é derivada da chave real: cada rodada é montada a partir da
  seguinte, rastreando os dois lados de cada confronto até seu jogo de origem
  (pelo código `W<N>`/`L<N>` da fonte enquanto o confronto não é decidido, ou
  pelo nome real do time já decidido). Efeito colateral corrigido junto: a
  disputa de 3º lugar não tinha `stage_name` na fonte e sumia da chave;
  passou a ser reconhecida pelo placeholder `L<N>` (perdedor da semifinal N),
  e esse mesmo placeholder — que vazava como texto bruto ("L101") assim que a
  partida veio à tona — agora resolve para "Perdedor de X x Y". Requer
  rebuild do gold.

## v1.0.0 — 2026-07-13

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

### Corrigido
- Números de camisa nas escalações: o provedor publica majoritariamente números
  de clube (976 dos 1.248 jogadores da edição vestem outro número na Copa), além
  de lacunas e duplicatas. A fonte primária passou a ser curadoria das listas de
  convocados da Wikipédia (CC BY-SA): extração em
  `src/thestatsapi/wikipedia_jerseys.py`, 1.143 casados por nome + 105 revisados
  à mão (`data/admin/jersey_curation/`), mapa versionado em
  `webapp/jersey_overrides.py` cobrindo as 48 seleções × 26 números únicos na
  faixa 1–26. O mapa vence o número por partida do provedor; valores do provedor
  só sobrevivem para quem estiver fora do mapa, com deduplicação por time como
  salvaguarda.
- Placar de partidas decididas na prorrogação: o placar público agora inclui os
  gols do tempo extra (fonte: `after_extra_time`), e "venceu nos pênaltis" só
  aparece quando houve disputa de verdade (`penalty_shootout` + flag da fonte).
  Antes, Argentina 3–1 Suíça (prorrogação) era exibido como "1–1, Argentina
  venceu nos pênaltis por 3–1". Novo badge e narrativa "na prorrogação" no
  herói da partida, no pulso da Home e no chaveamento.
- Mapa de chutes da partida: eixo vertical espelhado para coincidir com a visão
  de TV (o eixo y da fonte cresce no sentido oposto ao da transmissão). Ajuste
  somente no frontend; o mapa recortado do perfil já estava na orientação certa.
- Gols contra (13 na edição): a fonte só os marca no shotmap (`goal_type: "own"`,
  atribuído ao time beneficiado); a timeline de eventos credita o gol ao time do
  próprio autor, sem flag. Agora o gol aparece na lista do lado beneficiado com
  "(contra)", vira "Gol contra" na timeline (lado corrigido via shotmap) e sai
  do mapa de chutes, dos agregados de xG e da "chance mais clara" da narrativa —
  gols contra não são finalizações do time creditado. Contagem de gols da
  partida segue incluindo-os (fato do placar).
