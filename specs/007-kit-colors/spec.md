# Spec: Cores de camisa por partida (kit colors)

## Objetivo

Na tela de partida, as cores de cada seleção devem refletir a camisa que ela
usou naquele jogo (fonte: PDFs "Match Colour Designation" da FIFA, curados
manualmente em `kit_pallete/*.md`, um arquivo por fase). Fora da tela de
partida, as cores fixas de identidade (`teamColors`) continuam valendo.

## Requisitos

- `kit_pallete/*.md` é a fonte de curadoria; o parser tolera as variações de
  formato entre arquivos (hífen/travessão, hex com/sem crase, sufixo de grupo).
- Join com fixtures por **(fase, par de seleções)** — fixtures não têm o número
  FIFA do jogo e a data UTC diverge da local; o par por fase é único.
- Payloads de partida ganham `home_kit`/`away_kit` = `{hex, name, display_hex}`,
  fluindo pelo gold ("vem pronto"). `display_hex` = variante com luminância
  mínima para a UI preta (camisas pretas/azul-marinho seriam invisíveis).
- Nome PT desconhecido, hex inválido ou jogo sem correspondência viram warning
  de build, nunca erro fatal — partida sem kit cai no fallback de identidade.
- Fases futuras (semifinal, decisão de 3º, final): basta adicionar o `.md` e
  rematerializar o gold.

## Fora de escopo (extensão futura)

- Agenda da Home e lista de Partidas com cores de kit.
