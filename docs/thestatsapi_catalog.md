# Catálogo TheStatsAPI — cobertura além da Copa 2026

Levantamento do catálogo completo do provedor (não só a Copa do Mundo), para
embasar a ideia de estender o projeto a outras competições. Complementa
[`thestatsapi_data_dictionary.md`](thestatsapi_data_dictionary.md), que
descreve o *schema* campo a campo já em uso; este documento descreve a
*abrangência* — quais ligas, qual profundidade histórica, qual nível de
detalhe por partida.

Levantado em 2026-07-13 direto na API de produção (`api.thestatsapi.com`),
com a chave já configurada no projeto (`THESTATSAPI_API_KEY`). Lista completa
em [`thestatsapi_catalog.csv`](thestatsapi_catalog.csv).

## Como foi levantado

Endpoints consultados (nenhum documentado ainda em `src/thestatsapi/config.py`
— o projeto hoje só usa `/football/matches*` fixo na Copa 2026):

- `GET /football/competitions` (paginado, `per_page=100`) — catálogo completo
- `GET /football/competitions/{id}` — detalhe + `current_season_id`
- `GET /football/competitions/{id}/seasons` — histórico de temporadas
- `GET /football/matches?competition_id=&season_id=` — amostra de partidas
- Endpoints de partida já conhecidos (`shotmap`, `player-stats`, `lineups`,
  `events`/`timeline`) aplicados a partidas de outras ligas/temporadas para
  checar profundidade

Respeitado o rate limit (~12 req/min) já documentado no projeto — a sondagem
inteira usou ~25 requisições espaçadas.

## Visão geral quantitativa

- **149 competições** cadastradas no total.
- Por tipo: **89 ligas**, 35 torneios (copas continentais/internacionais,
  qualificatórias), 25 copas nacionais.
- **65 países** com pelo menos uma competição doméstica; mais 34 competições
  sem país (continentais/internacionais — Champions League, Libertadores,
  qualificatórias, Copa do Mundo etc.).
- Cobertura de flags declaradas pelo provedor: `has_team_stats` em 141/149,
  `has_player_stats` em 140/149, `xg_available` em 108/149, `odds_available`
  em 141/149. `live_odds_available` é raro (2/149) — não é uma fonte de dado
  ao vivo.

### Maiores catálogos por país

| País | Competições |
|---|---:|
| Inglaterra | 11 |
| EUA | 5 |
| Alemanha, Itália, Espanha | 4 cada |
| Brasil, França, Escócia, Suécia, Emirados Árabes | 3 cada |

A lista completa (65 países) está no CSV.

### Ligas de primeira divisão já identificadas (exemplos)

| País | Liga | id |
|---|---|---|
| Inglaterra | Premier League | `comp_3039` |
| Espanha | LaLiga | `comp_8814` |
| Itália | Serie A | `comp_5840` |
| Alemanha | Bundesliga | `comp_4643` |
| França | Ligue 1 | `comp_0256` |
| Brasil | Brasileirão Série A | `comp_4795` |
| Brasil | Brasileirão Série B | `comp_1085` |
| Argentina | Liga Profesional de Fútbol | `comp_4540` |
| Portugal | Liga Portugal Betclic | `comp_8385` |
| Países Baixos | Eredivisie | `comp_3809` |
| EUA | MLS | `comp_9799` |
| México | Liga MX (Apertura/Clausura) | `comp_298265` / `comp_137103` |
| Arábia Saudita | Saudi Pro League | `comp_45025` |
| Japão | J1 League | `comp_6240` |
| Coreia do Sul | K League 1 | `comp_1646` |

### Continentais e seleções

| Competição | Tipo | id |
|---|---|---|
| FIFA World Cup | Copa do Mundo | `comp_6107` (em uso) |
| UEFA Champions League | Clubes | `comp_3498` |
| UEFA Europa League | Clubes | `comp_7739` |
| UEFA Conference League | Clubes | `comp_408698` |
| CONMEBOL Libertadores | Clubes | `comp_0499` |
| Copa América | Seleções | `comp_5749` |
| EURO | Seleções | `comp_2949` |
| Africa Cup of Nations | Seleções | `comp_1554` |
| Club World Championship | Clubes (Mundial de Clubes) | `comp_3872` |
| UEFA Women's Champions League | Clubes (feminino) | `comp_6694` |
| Women's Euro | Seleções (feminino) | `comp_3135` |
| Qualificatórias da Copa (AFC/CAF/CONCACAF/CONMEBOL/OFC/UEFA) | Seleções | 6 ids distintos |

Futebol feminino existe no catálogo, mas é bem mais raso e **não tem Copa do
Mundo Feminina**: a única competição chamada "World Cup" no catálogo inteiro
é a `comp_6107` (FIFA World Cup), cujas temporadas são 1998–2026 de dois em
dois anos — exatamente o calendário do masculino; 2019 e 2023 (edições da
Copa Feminina) não aparecem. O total de competições femininas é 5: Women's
Super League (Inglaterra, única liga doméstica), UEFA Women's Champions
League, Women's Euro (+ qualificatória) e UEFA Women's Nations League. Não dá
para tratar como paridade com o masculino, e uma extensão "Copa do Mundo
Feminina Analytics" não é viável com este provedor.

### Nota sobre o campo `confederation`

O campo vem **inconsistente** na resposta da API: "AFC Champions League
Elite", "CAF Champions League" e "CONCACAF Gold Cup" aparecem todos marcados
como `confederation: "UEFA"`, e a maioria das ligas domésticas vem com
`confederation: null`. Não dá para confiar nesse campo para agrupar por
confederação — o país (`country`) e o nome da competição são mais confiáveis.
Mesma categoria de cuidado documentada no artigo do projeto: "a fonte é
insumo, não verdade".

## Profundidade de temporadas

Testado com `/football/competitions/{id}/seasons` em 11 competições
representativas:

| Competição | Temporadas disponíveis | Alcance |
|---|---|---|
| FIFA World Cup | 2026, 2022, 2018, 2014, 2010, 2006, 2002, 1998 | 8 edições, até 1998 |
| UEFA Champions League | 26/27 → 20/21 | 7 temporadas (inclui a próxima, ainda não iniciada) |
| Premier League | 25/26 → 18/19 | 8 temporadas |
| Bundesliga / LaLiga / Serie A / Saudi Pro League | 25/26 → 20/21 | 6 temporadas cada |
| Ligue 1 | 25/26 → 20/21 | 6 temporadas |
| Brasileirão Série A | 2026 → 2021 (+ "20/21") | 7 temporadas |
| MLS | 2026 → 2020 | 7 temporadas |
| CONMEBOL Libertadores | 2026 → 2020 | 7 temporadas |
| Copa América | 2024, 2021, 2019, 2016, 2015, 2011 | Irregular — acompanha o calendário real do torneio |

Padrão observado: **ligas domésticas de primeira linha giram em torno de 5–6
temporadas** (tipicamente desde 20/21), a **Copa do Mundo tem histórico bem
mais longo** (quase 30 anos), e **torneios não-anuais** (Copa América, Euro,
Copa Africana) têm exatamente as edições reais, sem lacunas nem temporadas
fantasma. Não testei as 149 competições uma a uma — ligas menores/menos
centrais podem ter menos profundidade; o padrão acima é o piso observado nas
ligas de maior visibilidade.

## Nível de detalhe por partida

Testado nos mesmos oito endpoints já usados no bronze da Copa 2026, aplicados
fora do World Cup:

- **Partida de 2018/19 da Premier League** (`mt_725052325`, Liverpool 2–0
  Wolverhampton): `shotmap` retornou 20 finalizações completas — xG, `x`/`y`,
  `body_part`, `goal_mouth_location`, `goal_mouth_coordinates`,
  `block_coordinates` — exatamente o mesmo grão de detalhe hoje descrito no
  dicionário de dados da Copa 2026, sete temporadas atrás, numa liga
  diferente.
- **Partida de 2020/21 da Saudi Pro League** (`mt_969119781`, liga bem menos
  central que Premier/Champions): `shotmap` (21 chutes) e `player-stats` (40
  jogadores) vieram igualmente completos; `lineups` também. Já `events`
  devolveu 404 na rota principal, e o fallback `timeline` respondeu 200 mas
  com **zero eventos** — a mesma partida tem finalizações e estatísticas de
  jogador ricas, mas timeline vazia.

Conclusão prática: **`shotmap` e `player-stats` parecem ser o núcleo mais
consistente do provedor**, disponível mesmo em ligas/temporadas menos
centrais. **`events`/timeline é o endpoint mais frágil** — o próprio projeto
já lida com isso via `fallback_paths=("/football/matches/{match_id}/timeline",)`
em `src/thestatsapi/config.py`, mas o levantamento aqui mostra que mesmo o
fallback pode vir vazio. Qualquer extensão para outra liga deveria validar
`events` partida a partida antes de prometer timeline completa na UI — o
padrão de resiliência que o produto já usa (`_match_goals` cai para `events`
só quando o `shotmap` está vazio) se aplicaria bem aqui.

## Catálogo de endpoints (forma genérica)

O projeto hoje só usa a forma fixa na Copa 2026
(`competition_id=comp_6107&season_id=sn_118868`). A forma genérica, válida
para qualquer competição/temporada do catálogo:

| Endpoint lógico | Rota | Observação |
|---|---|---|
| Lista de competições | `GET /football/competitions` | Paginado, `per_page` até 100 |
| Detalhe da competição | `GET /football/competitions/{id}` | Traz `current_season_id`, `total_teams` |
| Temporadas da competição | `GET /football/competitions/{id}/seasons` | `is_current` marca a temporada ativa |
| Classificação | `GET /football/competitions/{id}/seasons/{season_id}/standings` | Já em uso |
| Calendário/partidas | `GET /football/matches?competition_id=&season_id=` | Paginado; já em uso |
| Detalhe da partida | `GET /football/matches/{match_id}` | Já em uso |
| Escalações | `GET /football/matches/{match_id}/lineups` | Já em uso |
| Estatísticas da partida | `GET /football/matches/{match_id}/stats` | Já em uso |
| Estatísticas por jogador | `GET /football/matches/{match_id}/player-stats` | Já em uso |
| Timeline de eventos | `GET /football/matches/{match_id}/events` (fallback `/timeline`) | Já em uso; cobertura inconsistente (ver acima) |
| Mapa de finalizações | `GET /football/matches/{match_id}/shotmap` | Já em uso |
| Árbitro | `GET /football/matches/{match_id}/referee` | Já em uso |

Os quatro primeiros (competições/temporadas/standings) não têm nenhum código
no projeto hoje — `WORLD_CUP_2026_COMPETITION_ID`/`WORLD_CUP_2026_SEASON_ID`
estão hardcoded em `src/thestatsapi/config.py`. Estender para outra
competição significa generalizar esses dois valores para parâmetros, não
reescrever a ingestão.

## Implicações para estender o projeto

- **A arquitetura bronze/gold já criada é reaproveitável quase 1:1.** O
  schema por partida (shotmap com xG e coordenadas, player-stats,
  lineups, eventos, árbitro) é o mesmo em qualquer competição/temporada
  testada — o trabalho de modelagem já feito para pênaltis, gols contra,
  posições inferidas etc. não precisa ser refeito por liga.
- **Ligas domésticas de ponta (top 5 europeias + Brasileirão/MLS) têm ~5–7
  temporadas** — dá para um produto tipo "Brasileirão Analytics" ou
  "Premier League Analytics" com histórico multi-temporada desde o dia um,
  não só a temporada corrente.
- **A própria Copa do Mundo tem 8 edições no catálogo (1998–2026).** Antes de
  qualquer nova competição, dá para estender o produto atual para cobrir
  Copas anteriores — reaproveita 100% do código, é só trocar
  `competition_id`/`season_id` e reingerir. Provavelmente o menor esforço de
  extensão com maior familiaridade de produto (mesmo formato editorial, mais
  edições).
- **Continentais de clubes (Champions League, Libertadores) e de seleções
  (Copa América, Euro, Copa Africana) já têm o mesmo grão de detalhe** —
  caminho natural depois das ligas domésticas, com o bônus de reaproveitar a
  UI de chaveamento/mata-mata já construída para a Copa.
- **`events`/timeline precisa de um plano de degradação por competição**,
  não só por partida — a UI já trata timeline vazia graciosamente (fallback
  para o `shotmap`), então isso é sobretudo uma expectativa a calibrar, não
  um bloqueador técnico.
- **Futebol feminino não tem Copa do Mundo no catálogo** — só 5 competições
  no total (liga inglesa + torneios da UEFA). Uma extensão espelhando o
  produto atual para o feminino ("Copa do Mundo Feminina Analytics") não é
  viável com este provedor; o que dá para fazer é algo focado em Champions
  League/Euro feminina, escopo bem menor.
