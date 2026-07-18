from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# PT names used in the FIFA-curated kit_pallete/*.md files -> API team names.
PT_TO_API = {
    "Alemanha": "Germany", "Argentina": "Argentina", "Argélia": "Algeria",
    "Arábia Saudita": "Saudi Arabia", "Austrália": "Australia", "Brasil": "Brazil",
    "Bélgica": "Belgium", "Bósnia e Herzegovina": "Bosnia & Herzegovina",
    "Cabo Verde": "Cape Verde", "Canadá": "Canada", "Catar": "Qatar",
    "Colômbia": "Colombia", "Coreia do Sul": "South Korea",
    "Costa do Marfim": "Côte d'Ivoire", "Croácia": "Croatia", "Curaçao": "Curaçao",
    "Egito": "Egypt", "Equador": "Ecuador", "Escócia": "Scotland",
    "Espanha": "Spain", "Estados Unidos": "USA", "França": "France",
    "Gana": "Ghana", "Haiti": "Haiti", "Inglaterra": "England",
    "Iraque": "Iraq", "Irã": "Iran", "Japão": "Japan", "Jordânia": "Jordan",
    "Marrocos": "Morocco", "México": "Mexico", "Noruega": "Norway",
    "Nova Zelândia": "New Zealand", "Panamá": "Panama", "Paraguai": "Paraguay",
    "Países Baixos": "Netherlands", "Holanda": "Netherlands",
    "Portugal": "Portugal", "RD Congo": "DR Congo", "Senegal": "Senegal",
    "Suécia": "Sweden", "Suíça": "Switzerland", "Tchéquia": "Czechia",
    "Tunísia": "Tunisia", "Turquia": "Türkiye", "Uruguai": "Uruguay",
    "Uzbequistão": "Uzbekistan", "África do Sul": "South Africa",
    "Áustria": "Austria",
}

_GAME_LINE = re.compile(
    r"\*\*Jogo\s+(\d+)[^:]*:\*\*\s*(.+?)\s*[—–-]\s*(.+?)\s*\(`?(#[0-9A-Fa-f]{6})`?\)"
    r"\s*\*\*vs\*\*\s*(.+?)\s*[—–-]\s*(.+?)\s*\(`?(#[0-9A-Fa-f]{6})`?\)",
    re.UNICODE,
)

MIN_LUMINANCE = 0.22


def _relative_luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def display_hex(hex_color: str) -> str:
    """Kit hex lifted to a minimum luminance so dark shirts (black, navy) stay
    visible on the black UI; light shirts pass through unchanged."""
    value = hex_color
    for _ in range(12):
        if _relative_luminance(value) >= MIN_LUMINANCE:
            return value.upper()
        raw = value.lstrip("#")
        mixed = [min(255, round(int(raw[i:i + 2], 16) * 0.88 + 255 * 0.12)) for i in (0, 2, 4)]
        value = "#" + "".join(f"{c:02X}" for c in mixed)
    return value.upper()


def _phase_key(stem: str) -> str:
    return stem.strip().casefold().replace("-", "_").replace(" ", "_")


@lru_cache(maxsize=4)
def load_kit_colors(root: str = "kit_pallete") -> dict[tuple[str, frozenset[str]], dict[str, Any]]:
    """Parse every kit_pallete/*.md file into {(phase, {teamA, teamB}): kits}.

    Unknown PT names or unparsable lines are skipped with a warning print — the
    match simply falls back to the identity colors."""
    mapping: dict[tuple[str, frozenset[str]], dict[str, Any]] = {}
    base = Path(root)
    if not base.is_dir():
        return mapping
    for path in sorted(base.glob("*.md")):
        phase = _phase_key(path.stem)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("**Jogo"):
                continue
            found = _GAME_LINE.search(line)
            if not found:
                print(f"[kit_colors] linha não reconhecida em {path.name}: {line[:80]}")
                continue
            number, home_pt, home_color, home_hex, away_pt, away_color, away_hex = found.groups()
            home = PT_TO_API.get(home_pt.strip())
            away = PT_TO_API.get(away_pt.strip())
            if not home or not away:
                print(f"[kit_colors] seleção desconhecida em {path.name}: {home_pt!r} / {away_pt!r}")
                continue
            mapping[(phase, frozenset({home, away}))] = {
                "match_number": int(number),
                "teams": {
                    home: {"hex": home_hex.upper(), "name": home_color, "display_hex": display_hex(home_hex)},
                    away: {"hex": away_hex.upper(), "name": away_color, "display_hex": display_hex(away_hex)},
                },
            }
    return mapping


def kits_for(stage: Any, group_name: Any, home: Any, away: Any, root: str = "kit_pallete") -> dict[str, Any] | None:
    """Kits for a fixture: phase derived from the stage (group matches normalize
    to group_stage regardless of the raw label)."""
    if not home or not away:
        return None
    phase = _phase_key(str(stage or ""))
    if group_name or "group" in phase:
        phase = "group_stage"
    entry = load_kit_colors(root).get((phase, frozenset({str(home), str(away)})))
    return entry["teams"] if entry else None
