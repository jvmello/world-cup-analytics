# Plano técnico: kit colors por partida

## Fluxo

```text
kit_pallete/*.md (curadoria manual dos PDFs FIFA)
 -> src/thestatsapi/kit_colors.py (parser + normalização + PT→nome da API)
 -> enriquecimento em _match_summary (home_kit/away_kit)
 -> gold api_payloads (matches, match_detail)
 -> tela de partida: matchPalette prefere kit; demais telas seguem teamColors
```

## Componentes

- `src/thestatsapi/kit_colors.py`: regex tolerante por linha de jogo; dicionário
  PT→nome da API (aliases: Países Baixos→Netherlands, Catar→Qatar, Estados
  Unidos→USA, Tchéquia→Czechia…); chave `(fase, frozenset{timeA, timeB})`;
  `display_hex` por mistura com branco até luminância mínima (~0,22).
- `webapp/thestatsapi_service.py`: carrega o mapa uma vez por instância e anexa
  `home_kit`/`away_kit` em `_match_summary` (cobre matches list e match detail).
- `webapp/static/app.js`: `matchKitStyle(match)` → CSS vars com fallback para
  `teamColor()`; aplicado no hero/placar, mapa de chutes (`colors` por
  team_name), mapa de pênaltis e fluxo de xG da tela de partida.
- Infra: montar `kit_pallete/` (ro) nos containers `worldcup-pipeline` e
  `worldcup-web` (fallback bronze) no compose da jvmello-infra.

## Testes

- Parser sobre os 4 arquivos reais: todos os nomes PT resolvem; join cobre
  os jogos das fases publicadas; hexes válidos; display_hex clareia #111111.
