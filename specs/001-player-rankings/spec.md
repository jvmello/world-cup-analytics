# Feature 001: Player Rankings

## 🎯 Visão Geral

Criar uma visão de comparação ofensiva entre jogadores da Copa do Mundo usando os dados gold já disponíveis em `gold_player_offensive_summary` e `gold_player_shots`. Conforme necessário, implementar novos arquivos gold.

## 👤 User Stories

1. Como analista, quero filtrar rankings por edição, seleção e volume mínimo de finalizações para encontrar líderes ofensivos confiáveis.
2. Como analista, quero alternar a métrica principal do ranking para investigar perfis diferentes: volume, xG, conversão, precisão e overperformance.
3. Como analista, quero comparar times por perfil de finalização para identificar seleções com maior produção, eficiência e dependência de grandes chances.
4. Como analista, quero também ter esses dados para copas passadas, além de dados mais gerais. Artilheiros, melhores assistentes, seleções campeãs... Tanto de forma geral como para uma copa específica.
5. Como analista, quero também desenvolver um formato que mostra as fases de grupos, partidas e também os mata-matas.
6. Como analista, quero implementar uma forma de manter essa extração para dados da próxima copa do mundo. Atualizando conforme eles forem ficando disponíveis, talvez usando Airflow para a extração gradual.
7. Como usuário, quero abrir a competição com a edição 2026 como padrão, exibindo os grupos definidos mesmo antes de haver resultados.
8. Como usuário, quero navegar por uma visão de times com menus internos para vitrine, performance, ranking, radar, evolução, forma e mapas ofensivos.
9. Como usuário administrador, quero adicionar imagens de bandeiras para os países e também editar os nomes dos jogadores. Eles vão ter um nome completo e um nome "comum", como são conhecidos.

## 📋 Requisitos

- A aplicação deve ler apenas arquivos locais da camada gold.
- A página deve funcionar mesmo quando `player_display_name` não existir no parquet.
- Métricas derivadas devem tratar divisão por zero sem quebrar a UI.
- O ranking deve expor ao menos: jogador, time, edição, finalizações, gols, xG, xG/finalização, gols - xG, precisão, conversão e grandes chances.
- A página deve oferecer gráficos e tabela ordenados por métrica selecionada.
- A seção de competição deve mostrar cada grupo separadamente quando houver estrutura de grupos disponível.
- A edição 2026 deve possuir tabela zerada e placeholders de mata-mata até os resultados serem carregados.
- A visão de times deve reaproveitar os golds de time, partida-time e finalizações.
- A seção de competição deve renderizar grupos em caixas visuais com classificação e lista de partidas abaixo.
- O mata-mata deve ser exibido em formato de esquema/bracket com caixas por partida e colunas por fase quando houver dados suficientes.
- A navegação da página de competição deve ficar horizontal no topo, com seletor de competição e seletor de edição antes do conteúdo.
- A navegação principal da aplicação deve usar abas horizontais no topo em vez do seletor lateral padrão do Streamlit.
- O seletor de competição deve ficar no nível global da aplicação, acima do conteúdo das páginas.
- Filtros específicos de página devem ficar dentro da página, logo abaixo do título/subtítulo e antes dos cards de métricas.
- A página de times deve manter edição, time e menu de visão dentro do layout principal, sem depender da sidebar.
- A página de jogadores deve manter edição, time, jogador e menu de visão dentro do layout principal, sem depender da sidebar.

## Fora de Escopo

- Alterar a pipeline bronze/silver/gold.
- Baixar novos dados externos.
- Escrever em banco ou produção.

## Riscos

- Edições antigas têm amostra pequena; a UI precisa permitir filtro por volume mínimo.
- Dados de xG e localização podem não existir para todo evento; a feature usa apenas o gold já filtrado.

## ✅ Critérios de Sucesso

- Testes unitários para métricas derivadas, filtros e ordenação do leaderboard.
- Validação sintática dos módulos Streamlit.
