# Plano técnico: World Cup Analytics Web

## Arquitetura

```text
Parquet StatsBomb + CSV FIFA PDF
        ↓
FastAPI /api
        ↓
SPA HTML/CSS/JavaScript
```

## Arquivos

### Backend

- `webapp/main.py`
- `webapp/catalog.py`
- `webapp/data_service.py`
- `tests/test_web_api.py`

### Frontend

- `webapp/static/index.html`
- `webapp/static/styles.css`
- `webapp/static/app.js`

### Operação

- `Dockerfile.web`
- `docker-compose.yaml`
- `Makefile`
- `requirements.txt`
- `README.md`

## API

- `GET /api/health`
- `GET /api/editions`
- `GET /api/editions/{year}/overview`
- `GET /api/editions/{year}/competition`
- `GET /api/editions/{year}/teams`
- `GET /api/editions/{year}/players`
- `GET /api/editions/{year}/matches`
- `GET /api/editions/{year}/official-metrics`
- `GET /api/editions/{year}/availability`
- `GET /api/history`

## Decisões

- FastAPI mantém todo o stack em Python e reutiliza Pandas/PyArrow.
- SPA sem build evita Node e mantém o frontend substituível.
- O catálogo de capacidades é o contrato central da navegação.
- Dados históricos antigos são rotulados como cobertura parcial quando necessário.
- Agregações para visualização são produzidas no backend para não duplicar regras
  analíticas no navegador.
- SVG nativo é usado em barras, dispersão, linhas e campo de finalizações.
- A visualização toma como referência os mapas, rankings, fluxo de xG e comparações
  implementados no Streamlit e no projeto `statsbomb_aula`.

## Testes

- Catálogo ordenado, default 2026 e capacidades por fonte.
- Endpoints 2022 e 2026.
- Histórico e tratamento de edição inválida.
- Rankings, séries, mapa de chutes e comparações oficiais.
- Ausência de nomes de arquivos nos contratos consumidos pela interface.
- Arquivos estáticos e health check.
- Smoke test Docker.
