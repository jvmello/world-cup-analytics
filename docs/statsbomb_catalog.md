# Catálogo StatsBomb Open Data — cobertura e licença

Levantamento do StatsBomb Open Data (`github.com/statsbomb/open-data`), a
mesma fonte já usada pelo projeto para a edição histórica de 2022
(`src/extract_statsbomb_world_cup.py`). Complementa
[`thestatsapi_catalog.md`](thestatsapi_catalog.md) — resposta direta à
pergunta "tem Copa do Mundo Feminina?" que ficou em aberto lá.

Levantado em 2026-07-13 direto no repositório público (`raw.githubusercontent.com`,
sem chave, sem autenticação). Lista completa em
[`statsbomb_catalog.csv`](statsbomb_catalog.csv).

## Licença — leia isto antes de qualquer decisão de produto

Baixei e li o `LICENSE.pdf` do repositório (StatsBomb Public Data User
Agreement, atualizado em 2023-09-08). Os pontos que afetam este projeto:

- **Uso comercial é proibido.** Cláusula 1.2.2: o usuário não pode
  "commercially exploit the data or any analysis derived from the use of the
  Service".
- **Redistribuição/revenda é proibida.** Cláusula 1.2.1: não pode "edit,
  distort, distribute, reproduce, sell or in any way provide the data to any
  external or third party".
- **Atribuição obrigatória com o logo.** Cláusula 1.4: toda publicação de
  análise feita com dado StatsBomb precisa creditar a StatsBomb com o logo
  oficial (disponível no Media Pack deles), não só um link de texto.
- Dado fornecido "as is", StatsBomb não garante acurácia/completude
  (cláusula 3.4) e pode suspender o acesso a qualquer momento sem aviso
  (cláusula 2.1/6.1) — é acesso via GitHub público, não um contrato de API
  com SLA.
- Regida por lei da Inglaterra e País de Gales.

**Isso é um regime bem mais restrito do que o da TheStatsAPI** que o projeto
já usa hoje (contratada, com chave, uso já em produção comercial-editorial
sem essa cláusula de proibição de exploração comercial). Qualquer extensão
usando StatsBomb precisa entrar como conteúdo **não-comercial** — pesquisa,
side project, portfólio pessoal sem monetização — e com o logo StatsBomb
visível onde os dados aparecerem. Se `worldcup.jvmello.dev` alguma hora
carregar anúncios, assinatura ou virar peça paga, dado StatsBomb não pode
estar na mesma superfície sem reler a licença com um advogado.

## Visão geral quantitativa

- **80 combinações competição × temporada** no total (bem menos que as 149
  competições da TheStatsAPI — ver seção de comparação abaixo).
- **24 competições distintas**, cobrindo homens, mulheres, sub-20 e
  internacionais/domésticas.
- **12 dessas 80 temporadas têm dado de rastreamento 360** (freeze-frame de
  posição de todos os jogadores visíveis, não só do lance) disponível em
  pelo menos uma partida.

## Catálogo completo

| Gênero | País/Confederação | Competição | Temporadas disponíveis (não contíguas) |
|---|---|---|---|
| Masculino | Internacional | FIFA World Cup | 1958, 1962, 1970, 1974, 1986, 1990, 2018, 2022 |
| Masculino | Internacional | FIFA U20 World Cup | 1979 |
| Masculino | Europa | UEFA Champions League | 1970/71–2018/19 (18 temporadas, não contíguas) |
| Masculino | Europa | UEFA Euro | 2020, 2024 |
| Masculino | Europa | UEFA Europa League | 1988/89 |
| Masculino | Espanha | La Liga | 1973/74–2020/21 (18 temporadas, não contíguas) |
| Masculino | Espanha | Copa del Rey | 1977/78, 1982/83, 1983/84 |
| Masculino | Inglaterra | Premier League | 2003/04, 2015/16 |
| Masculino | Alemanha | 1. Bundesliga | 2015/16, 2023/24 |
| Masculino | Itália | Serie A | 1986/87, 2015/16 |
| Masculino | França | Ligue 1 | 2015/16, 2021/22, 2022/23 |
| Masculino | Argentina | Liga Profesional | 1981, 1997/98 |
| Masculino | EUA | Major League Soccer | 2023 |
| Masculino | Índia | Indian Super League | 2021/22 |
| Masculino | América do Norte/Central | North American League | 1977 |
| Masculino | América do Sul | Copa América | 2024 |
| Masculino | África | African Cup of Nations | 2023 |
| Feminino | Internacional | **Women's World Cup** | **2019, 2023** |
| Feminino | Europa | UEFA Women's Euro | 2022, 2025 |
| Feminino | Inglaterra | FA Women's Super League | 2018/19, 2019/20, 2020/21, 2023/24 |
| Feminino | Alemanha | Frauen Bundesliga | 2023/24 |
| Feminino | Itália | Serie A Women | 2023/24 |
| Feminino | Espanha | Liga F | 2023/24 |
| Feminino | EUA | NWSL | 2018, 2023 |

## Profundidade real por partida (o que dá a fama à StatsBomb)

TheStatsAPI dá o essencial por partida (escalação, estatística agregada de
jogador, timeline resumida, mapa de finalizações). StatsBomb dá um **stream
de evento completo** — todo passe, condução de bola, pressão, disputa,
recuperação — não só os chutes.

Conferido na final da Copa do Mundo Feminina 2023 (Espanha 1–0 Inglaterra,
`match_id=3906390`):

| Métrica | Valor real conferido |
|---|---:|
| Eventos totais na partida | **3.581** |
| Passes | 927 |
| Recepções de bola | 897 |
| Conduções de bola | 741 |
| Pressões | 433 |
| Finalizações | 22 |
| Frames de rastreamento 360 (posição de todos em campo) | **3.238** |

Cada evento de passe já vem com coordenada de início e fim, ângulo,
distância, parte do corpo e recebedor — não é uma agregação por jogo, é
literalmente cada toque na bola com posição em campo. O dado 360 vai além:
para cada evento (nem todos, mas a maioria), uma "foto" de onde cada jogador
visível estava naquele instante — a base de qualquer métrica de posicionamento
fora da bola (pressão, linha defensiva, espaço criado), algo que a TheStatsAPI
simplesmente não oferece em nenhum grão.

## TheStatsAPI vs. StatsBomb — não é "qual é melhor", é eixos diferentes

| | TheStatsAPI (em uso hoje) | StatsBomb Open Data |
|---|---|---|
| Competições distintas | 149 | 24 |
| Profundidade típica por liga | ~5–7 temporadas contínuas | Temporadas avulsas, não contínuas |
| Grão por partida | Chutes com xG, stats agregadas por jogador, timeline (às vezes vazia) | Todo evento (passe/condução/pressão/disputa), coordenadas em cada um |
| Rastreamento posicional (360) | Não existe | Só em partidas/competições selecionadas (12 de 80 temporadas) |
| Licença | Comercial, chave paga, já em uso em produção | Não-comercial, atribuição com logo obrigatória, sem redistribuição |
| Copa do Mundo Feminina | Não existe no catálogo | **2019 e 2023 completas** |
| Confiabilidade operacional | API com contrato/SLA implícito | "As is", acesso via GitHub, pode ser suspenso sem aviso |

Ou seja: StatsBomb não é "mais abrangente" em cobertura de competições — é
**mais fundo** num recorte bem mais estreito de competições, e vem com uma
licença que restringe onde esse dado pode aparecer.

## Implicações para estender o projeto

- **A Copa do Mundo Feminina só é viável via StatsBomb**, e só como conteúdo
  claramente não-comercial, com o logo StatsBomb visível — não dá para
  simplesmente clonar o produto atual (que já é hospedado como projeto
  pessoal, então isso é provavelmente compatível, mas vale confirmar a
  intenção antes de publicar).
- **O grão de evento completo + 360 abriria um tipo de análise que o produto
  atual não tem** — mapas de pressão, ocupação de espaço, rede de passes real
  (não só o mapa de chutes) — mas só para as 12 temporadas com 360 e as ~80
  combinações competição×temporada disponíveis, não para qualquer liga.
- **Não dá para misturar as duas fontes na mesma tela sem deixar claro qual é
  qual** — schemas diferentes (já é assim hoje: `shot.xg` da TheStatsAPI vs
  `shot.statsbomb_xg` do arquivo 2022), licenças diferentes, e a atribuição
  com logo da StatsBomb precisa aparecer onde o dado dela for exibido.
- **Nenhuma lacuna técnica de ingestão** — o projeto já tem
  `src/extract_statsbomb_world_cup.py` funcionando com `statsbombpy`; estender
  para outra competição/temporada é generalizar `WORLD_CUP_SEASONS` em
  `src/config.py`, mesmo padrão da recomendação para a TheStatsAPI.
