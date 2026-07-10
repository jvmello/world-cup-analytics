# Spec: Camada gold de serving em PostgreSQL

## Problema

A API 2026 (`webapp/thestatsapi_service.py`) não tem cache: cada request relê
todo o bronze (~104 partidas × 7 JSONs) e refaz as agregações (percentis,
radar, campanha das seleções). O `overview` varre o bronze duas vezes por
request. Endpoints levam segundos.

## Objetivo

Mover todo o custo de carregamento/transformação para um passo de build
pós-extração. Os dados chegam "prontos" do backend: a API lê payloads
pré-computados do PostgreSQL (schema `gold`) e devolve.

## Requisitos

- Contrato do frontend inalterado: os payloads gravados são o JSON exato que
  cada endpoint responde hoje.
- Perfis totalmente pré-computados, incluindo os recortes por partida do
  perfil de jogador (`match:<id>` × cada jogador da partida).
- Build atômico: staging + swap em uma transação; build que falha nunca deixa
  gold parcial — o build anterior continua servindo.
- Fallback: enquanto `gold.api_payloads` não existir para a edição, a API
  serve pelo caminho bronze atual (fases 1–2); o fallback sai do request path
  no cutover (fase 3). O bronze permanece em disco como fonte da verdade.
- Produção na VPS: bronze em caminho persistido (volume, com backup),
  extração via CLIs existentes rodando na VPS, e `make thestatsapi-serving`
  reconstruindo o gold a partir do bronze local **sem re-consultar a API**.

## Fora de escopo (por ora)

- Edições de arquivo (StatsBomb parquet) — estáticas e pequenas; fase opcional.
- Migração dos overrides do admin (SQLite) para o Postgres — fase opcional.
