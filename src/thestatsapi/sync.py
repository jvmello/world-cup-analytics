from __future__ import annotations

import argparse
import fcntl
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from dotenv import load_dotenv

from .config import WORLD_CUP_2026_EDITION
from .group_stage_bulk import FINISHED_STATUSES
from .ingestion import default_ingestion
from .opening_match_smoke import match_id as fixture_match_id
from .opening_match_smoke import read_fixture_rows, team_name

# player_stats marks a complete bundle (same criterion as the extraction runbook):
# the seven endpoints are fetched together and the fetch is idempotent per endpoint,
# so a match with player_stats saved has already been covered.
BUNDLE_MARKER = "player_stats/response.json"


def bronze_root(data_root: Path, year: int) -> Path:
    return Path(data_root) / "bronze/thestatsapi/world_cup" / str(year)


def bundled_match_ids(data_root: Path, year: int) -> set[str]:
    matches_root = bronze_root(data_root, year) / "matches"
    return {
        path.name.removeprefix("match_id=")
        for path in matches_root.glob("match_id=*")
        if (path / BUNDLE_MARKER).exists()
    }


def pending_finished_matches(
    rows: list[dict[str, Any]],
    bundled: set[str],
) -> list[dict[str, Any]]:
    """Finished fixtures that still have no bundle in Bronze, in date order."""
    pending = []
    for row in rows:
        status = str(row.get("status") or "").casefold()
        if status not in FINISHED_STATUSES:
            continue
        row_match_id = fixture_match_id(row)
        if not row_match_id or row_match_id in bundled:
            continue
        pending.append(row)
    pending.sort(key=lambda row: (str(row.get("utc_date") or ""), str(fixture_match_id(row))))
    return pending


def match_label(row: dict[str, Any]) -> str:
    return f"{team_name(row, 'home') or '?'} x {team_name(row, 'away') or '?'}"


def _log(message: str) -> None:
    print(f"[sync {time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def _acquire_lock(data_root: Path) -> TextIO | None:
    """File lock (flock) so cron never overlaps two runs.

    The file lives in data/ (bind mount), so the lock holds across containers on
    the same host and the kernel releases it if the process dies.
    """
    lock_path = Path(data_root) / "ingestion" / "sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def run_sync(
    year: int = WORLD_CUP_2026_EDITION,
    *,
    data_root: Path = Path("data"),
    interval_seconds: float = 30.0,
    limit: int | None = None,
    skip_fixtures: bool = False,
    skip_serving: bool = False,
    dry_run: bool = False,
) -> int:
    lock = _acquire_lock(data_root)
    if lock is None:
        _log("outra execução do sync ainda está em andamento — saindo sem fazer nada.")
        return 0
    try:
        ingestion = default_ingestion()
        if not skip_fixtures and not dry_run:
            core = ingestion.fetch_core(force=True)
            _log(f"fixtures/standings atualizados: {core}")

        rows = read_fixture_rows(bronze_root(data_root, year) / "fixtures")
        pending = pending_finished_matches(rows, bundled_match_ids(data_root, year))
        if limit is not None:
            pending = pending[:limit]
        if not pending:
            _log("nenhuma partida encerrada sem bundle — base já está em dia.")
            return 0
        _log(f"partidas encerradas sem bundle: {len(pending)}")
        for row in pending:
            _log(f"  pendente: {fixture_match_id(row)} · {match_label(row)} · {str(row.get('utc_date') or '')[:16]}")
        if dry_run:
            _log("dry-run: nada foi buscado nem materializado.")
            return 0

        failures = 0
        for index, row in enumerate(pending, start=1):
            pending_id = str(fixture_match_id(row))
            _log(f"({index}/{len(pending)}) buscando bundle de {pending_id} · {match_label(row)}")
            try:
                result = ingestion.fetch_match_bundle(pending_id)
                _log(f"({index}/{len(pending)}) resultado: {dict(result)}")
                if result.get("failed"):
                    failures += 1
            except Exception as error:  # network/API: record and move on to the next
                failures += 1
                _log(f"({index}/{len(pending)}) FALHA em {pending_id}: {error}")
            if index < len(pending) and interval_seconds > 0:
                time.sleep(interval_seconds)

        club_teams = ingestion.fetch_club_teams()
        _log(f"clubes de origem resolvidos: {club_teams}")

        if skip_serving:
            _log("bundles buscados; rebuild do gold pulado (--skip-serving).")
        else:
            _log("materializando o gold (staging + swap atômico)...")
            from .serving import rebuild_gold_serving

            build = rebuild_gold_serving(year, data_root=data_root)
            _log(f"gold materializado: { {table: count for table, count in build.counts.items()} }")

        if failures:
            _log(f"concluído com {failures} partida(s) com falha — a próxima execução tenta de novo (fetch idempotente).")
            return 1
        _log("concluído sem falhas.")
        return 0
    finally:
        lock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Varre o calendário por partidas encerradas que ainda não estão no Bronze, "
            "busca os bundles que faltam e rematerializa o gold. Feito para rodar em cron."
        )
    )
    parser.add_argument("--year", type=int, default=WORLD_CUP_2026_EDITION)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=30.0,
        help="Pausa entre partidas (rate limit da conta: ~12 requisições/min; cada bundle são 7).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Processa no máximo N partidas nesta execução.")
    parser.add_argument("--skip-fixtures", action="store_true", help="Não atualiza o calendário antes da varredura.")
    parser.add_argument("--skip-serving", action="store_true", help="Não rematerializa o gold ao final.")
    parser.add_argument("--dry-run", action="store_true", help="Só lista as pendências; não busca nem materializa nada.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    return run_sync(
        args.year,
        data_root=args.data_root,
        interval_seconds=args.interval_seconds,
        limit=args.limit,
        skip_fixtures=args.skip_fixtures,
        skip_serving=args.skip_serving,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
