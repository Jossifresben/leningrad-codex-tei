"""Unit tests for the agent-harness stage."""

from __future__ import annotations


from leningrad_codex_tei.stages.harness import (
    Task,
    column_line_counts,
    harness_snapshot,
)


def _task(**run_extra) -> Task:
    run = {
        "harness": "claude-code",
        "harness_version": "1.0",
        "model": "claude-test",
        "attempts": 1,
        **run_extra,
    }
    return Task(packet={"skill_sha256": "abc"}, packet_sha256="def", reply="", run=run)


def test_snapshot_has_no_effort() -> None:
    assert "effort" not in harness_snapshot(_task(effort="low"))


def test_column_line_counts() -> None:
    reply = '<cb n="1" /><lb n="1" />a b<lb n="2" />c<cb n="2" /><lb n="1" />d'
    assert column_line_counts(reply) == [2, 1]
    assert column_line_counts("no columns here") == []
