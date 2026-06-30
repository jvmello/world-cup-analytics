from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping


SUPPORTED_EDITIONS = (2022, 2026)
DEFAULT_EDITION = 2026
SELECTED_EDITION_STATE = "selected_edition"

ADVANCED_EVENT_DATA = "advanced_event_data"
FIFA_PDF_DATA = "fifa_pdf"


@dataclass(frozen=True)
class DataCoverage:
    edition: int
    source: str
    level: str
    available: bool
    supports_event_data: bool
    message: str


def normalize_edition(value: Any) -> int:
    try:
        edition = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported World Cup edition: {value!r}") from exc

    if edition not in SUPPORTED_EDITIONS:
        supported = ", ".join(str(item) for item in SUPPORTED_EDITIONS)
        raise ValueError(
            f"Unsupported World Cup edition: {edition}. Supported editions: {supported}."
        )

    return edition


def get_selected_edition(session_state: MutableMapping[str, Any]) -> int:
    if SELECTED_EDITION_STATE not in session_state:
        session_state[SELECTED_EDITION_STATE] = DEFAULT_EDITION
        return DEFAULT_EDITION

    raw_value = session_state[SELECTED_EDITION_STATE]
    try:
        return normalize_edition(raw_value)
    except ValueError:
        session_state[SELECTED_EDITION_STATE] = DEFAULT_EDITION
        return DEFAULT_EDITION


def set_selected_edition(
    session_state: MutableMapping[str, Any],
    edition: Any,
) -> int:
    normalized = normalize_edition(edition)
    session_state[SELECTED_EDITION_STATE] = normalized
    return normalized


def get_data_coverage(
    edition: Any,
    fifa_data_available: bool = False,
) -> DataCoverage:
    normalized = normalize_edition(edition)

    if normalized == 2022:
        return DataCoverage(
            edition=normalized,
            source="StatsBomb",
            level=ADVANCED_EVENT_DATA,
            available=True,
            supports_event_data=True,
            message=(
                "Dados StatsBomb com eventos granulares, coordenadas e métricas de xG."
            ),
        )

    if fifa_data_available:
        message = (
            "Relatórios FIFA processados em CSV com métricas agregadas. "
            "Eventos, coordenadas e xG por lance não estão disponíveis."
        )
    else:
        message = (
            "Os CSVs FIFA 2026 ainda não foram gerados. Execute o pipeline de PDFs "
            "para disponibilizar os dados agregados."
        )

    return DataCoverage(
        edition=normalized,
        source="FIFA PDF",
        level=FIFA_PDF_DATA,
        available=fifa_data_available,
        supports_event_data=False,
        message=message,
    )


def render_edition_selector(st_module: Any, label: str = "Edição") -> int:
    get_selected_edition(st_module.session_state)
    edition = st_module.selectbox(
        label,
        SUPPORTED_EDITIONS,
        key=SELECTED_EDITION_STATE,
    )
    return normalize_edition(edition)


def render_coverage_notice(st_module: Any, coverage: DataCoverage) -> None:
    if not coverage.available:
        st_module.warning(coverage.message)
    elif coverage.supports_event_data:
        st_module.caption(f"Fonte: {coverage.source} · eventos granulares")
    else:
        st_module.info(coverage.message)
