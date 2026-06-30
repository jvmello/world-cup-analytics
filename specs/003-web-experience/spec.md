# Feature 003: World Cup Analytics Web

**Criado em**: 2026-06-22  
**Status**: Validada pelo pedido do usuário  
**Fonte de verdade**: `orchestra.md`

## 🎯 Visão Geral

Substituir o Streamlit como interface principal por uma experiência web editorial,
rápida e responsiva, inspirada na referência visual fornecida. A aplicação deve
colocar a edição no nível mais alto da navegação e derivar os menus das capacidades
reais dos dados daquela Copa.

Os pipelines StatsBomb e FIFA PDF permanecem inalterados. O Streamlit continua
disponível temporariamente como ferramenta interna, enquanto a nova aplicação web
se torna a superfície principal do produto.

## 👤 User Stories

### US1 - Selecionar edição no cabeçalho (P1)

Como usuário, quero trocar a edição no topo da aplicação para que todo conteúdo,
tema e navegação sejam atualizados de forma coerente.

Critérios:

- O seletor lista as edições materializadas no projeto.
- A edição 2026 é o padrão.
- Fonte, cobertura e completude ficam visíveis.
- Não existe fallback silencioso para outra edição.

### US2 - Navegação derivada da cobertura (P1)

Como usuário, quero ver somente menus compatíveis com os dados disponíveis.

Critérios:

- Menus comuns: visão geral, competição, times, jogadores e partidas.
- StatsBomb avançado pode expor finalizações e xG.
- FIFA PDF pode expor estatísticas oficiais, fases de jogo e métricas físicas.
- Ausência de granularidade nunca é exibida como zero.

### US3 - Histórico transversal (P1)

Como usuário, quero navegar pelo acervo das Copas independentemente da edição
selecionada.

Critérios:

- Exibir cobertura por edição, partidas, gols, seleções e campeãs conhecidas.
- Destacar quando a amostra histórica avançada é parcial.
- Permitir abrir uma edição a partir do histórico.

### US4 - Interface editorial responsiva (P2)

Como usuário, quero uma interface de produto, não um painel exploratório.

Critérios:

- Cabeçalho em duas camadas, cards, tabelas compactas e estados vazios.
- Tema histórico neutro e skins 2022/2026.
- Navegação utilizável em desktop e mobile.
- Contraste, foco e semântica adequados.

### US5 - Dashboard analítico por edição (P1)

Como usuário, quero interpretar o torneio por métricas e visualizações, sem
precisar navegar por arquivos ou registros técnicos.

Critérios:

- Visão geral combina KPIs, destaques de times e jogadores.
- Times apresentam rankings de xG, gols, volume e precisão.
- Jogadores apresentam líderes e comparação entre gols e xG.
- Partidas apresentam placares e distribuição por fase.
- Edições StatsBomb apresentam mapa de finalizações, fluxo de xG e recortes.
- Edições FIFA PDF apresentam comparação oficial entre equipes, fases de jogo e
  líderes individuais.
- Informações de fonte e disponibilidade ficam em uma visão técnica separada.

## 📋 Requisitos

- RF-001: O backend deve ler somente Parquet/CSV processados.
- RF-002: O catálogo de edições deve retornar capacidades e menus.
- RF-003: A API deve oferecer overview, competição, times, jogadores, partidas e histórico.
- RF-004: A aplicação web deve funcionar sem Node/npm.
- RF-005: O frontend deve usar HTML/CSS/JavaScript nativos servidos pelo FastAPI.
- RF-006: O Streamlit não deve ser removido neste ciclo.
- RF-007: A aplicação deve expor health check.
- RF-008: Os endpoints devem retornar JSON serializável e tratar arquivos ausentes.
- RF-009: Os endpoints analíticos devem retornar agregações prontas para gráficos.
- RF-010: A interface não deve expor nomes de arquivos, caminhos ou páginas do PDF.
- RF-011: Gráficos devem possuir alternativa textual ou tabela resumida.
- RF-012: A disponibilidade deve descrever capacidades, sem substituir métricas.

## ✅ Critérios de Sucesso

- A aplicação abre em 2026 e permite trocar para 2022 e edições históricas.
- A navegação muda conforme as capacidades retornadas pela API.
- O histórico agrega todas as edições locais.
- As páginas exibem KPIs e gráficos equivalentes às análises do Streamlit.
- A edição 2022 exibe mapa de chutes e comparação gols versus xG.
- A edição 2026 exibe comparação Brasil versus Marrocos e fases de jogo.
- Testes de API e catálogo passam.
- Docker expõe a nova web em porta própria e health check retorna 200.

## Fora de escopo

- Autenticação, edição administrativa e deploy público.
- Migração dos pipelines para banco.
- React/Next.js neste primeiro ciclo.
- Reprodução pixel-perfect da marca mostrada na referência.
