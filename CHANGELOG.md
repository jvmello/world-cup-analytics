# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
A partir da v1.0.0, mudanças de DDL são versionadas em
`docker/postgres/migrations/` (ver `specs/017-v1-governanca/`).

## Não lançado

### Adicionado
- API pública versionada (`/v1/*`), em paralelo ao `/api/*` interno da SPA (que
  continua exatamente igual): fase 1 do split público/admin planejado — só o
  lado de leitura por enquanto, a divisão do lado de escrita (edição de
  jogadores/seleções) fica pra uma fase seguinte. `/v1/*` roda numa sub-app
  FastAPI própria (`webapp/v1/`), com OpenAPI/Swagger isolado (`/v1/docs`) que
  nunca lista rotas do `/api/*` nem do `/ops/metrics`. Autogeração de chave em
  `POST /v1/keys` (retorna a chave em texto puro uma única vez; hash SHA-256 —
  não bcrypt/argon2, é um token aleatório de alta entropia, não uma senha —
  guardado em `analytics.api_keys`; permanente até revogação manual via SQL,
  sem endpoint de revogação nesta fase). Rate limit por dia em
  `analytics.api_rate_limits`: 100 req/dia sem chave (por IP), 2000 com chave
  válida, 5 criações de chave/dia por IP (pra não virar loop de geração em
  massa contornando o limite sem chave). Dois papéis Postgres novos e sem
  sobreposição (`docker/postgres/migrations/002_public_api.sql`):
  `readonly_public` (só SELECT em `gold`, único schema que a leitura pública
  toca) e `public_api_writer` (só INSERT/UPDATE nas tabelas de tracking —
  nunca em `gold`). Faltava isso: hoje um único usuário Postgres faz tudo
  (leitura, escrita de métricas, pipeline).
- Curadoria (overrides de nome/posição/foto de jogador e seleção) ganhou um
  leitor somente-leitura (`CurationSnapshotReader`) como preparação pra fase 2:
  a leitura pública hoje depende do SQLite de curadoria pra aplicar overrides
  em toda resposta (`_curate_players`/`_curate_teams`) — abrir esse arquivo
  `:ro` de dois containers seria frágil (sqlite3 abre read-write por padrão, e
  WAL tem instabilidade documentada entre containers). Em vez de migrar pra
  Postgres ou arriscar isso, `CurationRepository` (o único escritor, sem
  mudança de comportamento) passou a exportar um snapshot JSON a cada
  gravação; o novo leitor só faz `json.load()`, sem sqlite3 nenhum. Ainda não
  está ligado no app — é só a peça que a fase 2 (split do serviço de admin)
  vai usar.

### Corrigido
- "Quem avançou" chamava de "avançou" a vitória na disputa de 3º lugar e (quando
  acontecer) a vitória na Final — mas ninguém avança de nenhuma das duas: a
  disputa de 3º lugar é o último jogo de classificação, e quem vence a Final não
  avança, conquista o título. `homeQualifiedStory()` (o texto que a Home
  realmente renderiza — recalculado no front, não vem do campo `narrative` do
  backend) e o gerador equivalente em `home_pulse()` agora tratam essas duas
  fases: "garantiu o 3º lugar" e "conquistou o título mundial". Requer rebuild
  do gold.

## v1.1.0 — 2026-07-18

### Adicionado
- Jogadores por clube: novo bloco na tela de Jogadores mostra o clube de origem de
  cada convocado (não o clube atual — quem se transferiu no meio da Copa, como
  Marc Cucurella, Chelsea → Real Madrid em julho, continua contando pelo clube de
  onde foi convocado). A fonte (`player_stats`) já trazia `club_team_id` por
  partida, mas ele refletia a afiliação do jogador no momento em que cada bundle
  foi buscado, não uma origem estável — dava pra ver isso na prática: as partidas
  de junho do Cucurella vinham com um `club_team_id` e as de julho com outro,
  batendo exatamente com a janela de transferências (que só abre em julho, sempre
  depois do início da fase de grupos). Por isso o clube de origem é resolvido pela
  partida cronologicamente mais antiga do jogador, não pela primeira da lista.
  Nomes de clube vêm de uma ingestão nova e idempotente
  (`/football/teams/{team_id}`, um bronze por clube distinto, ~470 chamadas
  no backfill inicial) plugada no sync para resolver clubes novos automaticamente.
  Requer rebuild do gold.
- Versão exibida no rodapé do site (`v1.0.1`), lida de `/api/health`. Fonte
  única em `webapp/__version__` — o container de produção roda sem `.git`
  montado, então não dá pra derivar isso do git em runtime; precisa ser
  bumpado manualmente junto com este changelog e a tag correspondente.
  Corrigido de quebra: `FastAPI(version=...)` estava hardcoded em "1.0.0" e
  nunca tinha sido atualizado.

### Corrigido
- Prognóstico ausente na Final e na disputa de 3º lugar: a fonte às vezes
  demora a propagar o vencedor de uma rodada pro placeholder da rodada
  seguinte (`W101`/`W102`, `L101`/`L102`), mesmo com o resultado já
  disponível nos nossos dados — a Final chegou a ficar com um lado resolvido
  ("Spain") e o outro ainda cru ("W102"). A tela de chaveamento já resolve
  isso via `winner_matchups`; a rota de prognóstico nunca usava esse
  mecanismo, então caía sempre em "partida não encontrada". Novo
  `_knockout_resolved_matches` reaproveita a resolução do chaveamento nos
  dois pontos de entrada (`_fixture_prognosis` e o build do gold). No
  caminho, um bug de forma: os dois pontos passavam `service.fixtures(year)`
  (formato bruto, `home_team` como dict aninhado) pro resolvedor, que espera
  o formato achatado de `_match_summary`/`match_items` — com o formato
  errado, a fase nem era reconhecida e o nome do time virava o repr de um
  dict. Requer rebuild do gold.
- Cores de uniforme ausentes no prognóstico da Final e da disputa de 3º lugar:
  `kits_for()` era chamado dentro de `_match_summary()`, antes de
  `_knockout_resolved_matches()` trocar os placeholders (`W102`/`L102`) pelos
  nomes reais — a busca por (fase, {times}) nunca batia. A disputa de 3º lugar
  tinha uma segunda causa: a fonte nunca envia `stage_name` pra essa partida,
  então `kits_for()` (que usa `stage` pra achar o arquivo da fase) não
  resolvia mesmo com os nomes já certos; `_knockout_resolved_matches` agora
  também define `stage: "third_place"` nesse caso. Kits recalculados depois
  da resolução, em `_fixture_prognosis` e no build do gold. De quebra, a
  curadoria de `kit_pallete/*.md` mudou de paleta normalizada (nomes de cor
  genéricos, ex. "vermelho", reaproveitados entre seleções) pra amostragem
  direta da camisa de cada partida (hex e nome variam mesmo pro mesmo time
  entre partidas diferentes) — o parser (`kit_colors.py`) só aceitava nomes
  de cor simples/hifenizados e quebrava com descrições mais longas; passou a
  aceitar qualquer texto até o hex. Requer rebuild do gold.

## v1.0.1 — 2026-07-15

### Adicionado
- Tracking de uso: dashboard interno `/ops/metrics` (Basic Auth, 404 sem
  credenciais configuradas — mesma postura do admin desativado) mostra
  chamadas de API por endpoint, latência média/p95 e taxa de erro, lidos de
  `analytics.api_requests` (schema já existia na baseline, sem uso até
  agora). Middleware fire-and-forget grava cada chamada `/api/*` sem
  adicionar latência à resposta. Complementado por Umami self-hosted
  (`analytics.jvmello.dev`, infra em `jvmello-infra`) para "quais seções são
  mais usadas" nos dois sites (worldcup.jvmello.dev via `window.umami.track()`
  a cada troca de rota da SPA; jvmello.dev, que já tinha o script e a CSP
  prontos, só falta o `website-id`). Migração `001_api_request_metrics.sql`.
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
- Ranking de artilharia sem desempate real: jogadores empatados em gols
  ficavam na ordem que sobrava de uma ordenação anterior por xG (efeito
  colateral, não critério de verdade) — ex.: Mbappé (8 gols, 3 assistências)
  na frente de Messi (8 gols, 4 assistências) só por ter xG levemente maior.
  `player_leaders` agora desempata gols por mais assistências e, se ainda
  empatado, por menos minutos jogados. Requer rebuild do gold.

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
