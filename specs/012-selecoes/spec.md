# Spec: Revisão da tela Seleções (2026-07-11)

Obrigatórios: scatter com quadrantes interpretativos (Dominantes / Criam muito
mas cedem muito / Sólidas mas pouco produtivas / Em dificuldade) e tooltip
completo (jogos, gols, xG criado/cedido, saldo, finalizações por jogo);
bandeiras com moderação (sem sobreposição excessiva); destaques da edição
clicáveis com fórmulas explícitas (dominante = saldo de xG; defesa = xG cedido
por jogo; eficiente = gols − xG); produção com métrica selecionável indicando
por jogo/total; perfil coletivo em barras (absoluto + %) com toggle
Gols/Finalizações; rankings top 5 + modal; filtros com escopo claro (sem a
nota confusa "não é afetado pelos filtros").

Aceite: leitura imediata de quem domina/sofre; fórmulas claras; tudo clicável
para Perfil > Seleção; menos dashboard, mais produto.

**Status 2026-07-11:** implementado — quadrantes interpretativos com labels no scatter xG criado × cedido, tooltip completo (jogos/gols/xG/xGA/saldo/finalizações por jogo), fórmulas nos destaques (title), perfil coletivo em barras (absoluto+%), nota de escopo dos filtros reescrita. Destaques já eram clicáveis; rankings top 5 + modal já existiam.
