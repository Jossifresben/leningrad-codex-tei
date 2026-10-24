"""validate stage: gate an alignment against its seed slice."""

from __future__ import annotations

from dataclasses import dataclass

from leningrad_codex_tei.schemas import AlignmentRecord, WordStream
from leningrad_codex_tei.stages.align import SeedSlice


@dataclass
class ValidationResult:
    folio: str
    checks: dict[str, bool]
    passed: bool
    status: str  # "aligned" | "failed"


def validate_folio(
    sl: SeedSlice, alignment: AlignmentRecord, word_stream: WordStream
) -> ValidationResult:
    """Cross-check the alignment against the seed slice. Pure; no side effects."""
    atoms = [a for col in alignment.columns for line in col.lines for a in line.atoms]
    expected = sl.atoms

    checks = {
        "word_count": len(atoms) == len(expected),
        # page order: across segments the atom numbers may jump (#517)
        "atoms_sequential": [a.atom for a in atoms] == expected[: len(atoms)],
    }
    passed = all(checks.values())
    return ValidationResult(
        folio=alignment.folio,
        checks=checks,
        passed=passed,
        status="aligned" if passed else "failed",
    )
