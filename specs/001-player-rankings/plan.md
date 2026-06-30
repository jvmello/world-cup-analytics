# Plano Técnico

## Dados

- Entrada principal: `data/gold/world_cup/gold_player_offensive_summary/gold_player_offensive_summary.parquet`
- Entrada complementar: `data/gold/world_cup/gold_player_shots/gold_player_shots.parquet`
- Partidas e torneio: `data/gold/world_cup/gold_match_summary/gold_match_summary.parquet`
- Estrutura 2026: `data/gold/world_cup/gold_tournament_groups/gold_tournament_groups.parquet`
- Fixtures/placeholders 2026: `data/gold/world_cup/gold_tournament_fixtures/gold_tournament_fixtures.parquet`
- Times: `gold_team_shot_summary`, `gold_match_team_shot_summary`, `gold_player_shots`

## Implementação

1. Criar módulo `app/player_rankings.py` com funções puras para enriquecer, filtrar e ordenar dados.
2. Criar página Streamlit `app/pages/3_Player_Rankings.py`.
3. Criar módulo `app/world_cup_history.py` para campeãs, artilheiros, grupos e mata-mata.
4. Criar página Streamlit `app/pages/4_Tournament_History.py`.
5. Criar gold seed de estrutura do torneio 2026.
6. Criar página Streamlit `app/pages/5_Team_Analytics.py`.
7. Criar testes em `tests/` usando `unittest`.
8. Validar com testes e compilação.

## Decisões

- Manter a feature como página Streamlit independente para preservar as telas atuais.
- Não alterar a pipeline gold neste ciclo; a aplicação deve consumir apenas golds já materializados.
- Usar Plotly, já presente no projeto, para barras, scatter e perfis por seleção.
- Inferir campeãs por placar da final; quando houver empate, usar pênaltis em `gold_player_shots` com `period == 5`.
- Expor assistências como lacuna de dados enquanto a silver/gold não preservarem campos detalhados de passe.
- Para 2026, usar estrutura local versionável e idempotente; resultados entram depois pela pipeline incremental.
- Renderizar competição com HTML/CSS controlado dentro do Streamlit para permitir o formato de caixas de grupos e bracket.
- Inferir grupos históricos por componentes de confronto quando a camada gold não tiver letra do grupo.
