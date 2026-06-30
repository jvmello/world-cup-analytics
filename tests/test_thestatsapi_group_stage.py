from __future__ import annotations

from typing import Any

from thestatsapi.group_stage_bulk import (
    ANALYTICAL_ENDPOINTS,
    CONTEXT_ENDPOINTS,
    OVERVIEW_ENDPOINTS,
    endpoints_for_match,
    run_group_stage_batch,
    select_group_stage_matches,
)


def _fixture(
    match_id: str,
    *,
    group: str | None,
    status: str,
    kickoff: str,
) -> dict[str, Any]:
    return {
        "id": match_id,
        "group_label": group,
        "status": status,
        "utc_date": kickoff,
    }


class FakeIngestion:
    def __init__(self, *, broken_match_id: str | None = None) -> None:
        self.broken_match_id = broken_match_id
        self.calls: list[tuple[str, tuple[str, ...], bool]] = []

    def fetch_match_bundle(
        self,
        match_id: str,
        *,
        force: bool,
        endpoints: tuple[str, ...],
    ) -> dict[str, int]:
        self.calls.append((match_id, endpoints, force))
        if match_id == self.broken_match_id:
            raise RuntimeError("unexpected local failure")
        return {"success": 1}


def test_select_group_stage_matches_excludes_knockout_and_orders_by_kickoff() -> None:
    rows = [
        _fixture("late", group="B", status="finished", kickoff="2026-06-20"),
        _fixture("knockout", group=None, status="scheduled", kickoff="2026-06-28"),
        _fixture("early", group="A", status="finished", kickoff="2026-06-11"),
    ]

    selected = select_group_stage_matches(rows)

    assert [row["id"] for row in selected] == ["early", "late"]


def test_select_group_stage_matches_can_limit_groups_and_rows() -> None:
    rows = [
        _fixture("a1", group="Group A", status="finished", kickoff="2026-06-11"),
        _fixture("a2", group="A", status="finished", kickoff="2026-06-12"),
        _fixture("b1", group="B", status="finished", kickoff="2026-06-11"),
    ]

    selected = select_group_stage_matches(rows, groups=("a",), limit=1)

    assert [row["id"] for row in selected] == ["a1"]


def test_metadata_profile_covers_every_group_match_with_context_endpoints() -> None:
    scheduled = _fixture(
        "scheduled", group="A", status="scheduled", kickoff="2026-06-11"
    )

    assert endpoints_for_match(scheduled, profile="metadata") == CONTEXT_ENDPOINTS


def test_available_profile_adds_analytical_endpoints_only_for_finished_matches() -> None:
    finished = _fixture(
        "finished", group="A", status="finished", kickoff="2026-06-11"
    )
    scheduled = _fixture(
        "scheduled", group="A", status="scheduled", kickoff="2026-06-12"
    )

    assert endpoints_for_match(finished, profile="available") == (
        *CONTEXT_ENDPOINTS,
        *ANALYTICAL_ENDPOINTS,
    )
    assert endpoints_for_match(scheduled, profile="available") == CONTEXT_ENDPOINTS


def test_overview_profile_adds_match_stats_for_finished_matches() -> None:
    finished = _fixture(
        "finished", group="A", status="finished", kickoff="2026-06-11"
    )
    scheduled = _fixture(
        "scheduled", group="A", status="scheduled", kickoff="2026-06-12"
    )

    assert endpoints_for_match(finished, profile="overview") == (
        *CONTEXT_ENDPOINTS,
        *OVERVIEW_ENDPOINTS,
    )
    assert endpoints_for_match(scheduled, profile="overview") == CONTEXT_ENDPOINTS


def test_batch_runs_each_endpoint_separately_and_continues_after_local_failure() -> None:
    rows = [
        _fixture("broken", group="A", status="finished", kickoff="2026-06-11"),
        _fixture("healthy", group="A", status="scheduled", kickoff="2026-06-12"),
    ]
    ingestion = FakeIngestion(broken_match_id="broken")
    sleeps: list[float] = []

    summary = run_group_stage_batch(
        ingestion,
        rows,
        profile="metadata",
        force=False,
        request_interval_seconds=0.25,
        sleep_fn=sleeps.append,
    )

    assert summary == {
        "matches_selected": 2,
        "matches_processed": 2,
        "endpoints_planned": 4,
        "success": 2,
        "failed": 2,
    }
    assert ingestion.calls == [
        ("broken", ("match_detail",), False),
        ("broken", ("match_referee",), False),
        ("healthy", ("match_detail",), False),
        ("healthy", ("match_referee",), False),
    ]
    assert sleeps == [0.25, 0.25]
