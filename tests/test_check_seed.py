"""Tests for the check-seed stage: seed boundaries on repeated words."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from click.testing import CliRunner

from leningrad_codex_tei.cli import check_seed
from leningrad_codex_tei.schemas import Word, WordStream
from leningrad_codex_tei.stages.check_seed import find_repeated_boundaries
from leningrad_codex_tei.stages.word_stream import save_word_stream

# Josh 7:12, words 1-11. לִפְנֵי אֹיְבֵיהֶם is words 6-7 and 10-11 (#1076).
JOSH_7_12 = [
    "וְלֹ֨א",
    "יֻכְל֜וּ",
    "בְּנֵ֣י",
    "יִשְׂרָאֵ֗ל",
    "לָקוּם֙",
    "לִפְנֵ֣י",
    "אֹיְבֵיהֶ֔ם",
    "עֹ֗רֶף",
    "יִפְנוּ֙",
    "לִפְנֵ֣י",
    "אֹֽיְבֵיהֶ֔ם",
]
VERSE_2 = ["כִּ֥י", "הָי֖וּ", "לְחֵ֑רֶם"]


def _stream() -> WordStream:
    words = []
    for verse, texts in ((12, JOSH_7_12), (13, VERSE_2)):
        for i, text in enumerate(texts, start=1):
            words.append(
                Word(
                    atom=len(words) + 1,
                    text=text,
                    book="Joshua",
                    chapter=7,
                    verse=verse,
                    word_index=i,
                )
            )
    return WordStream(
        source="test", generated_at=datetime.now(timezone.utc), words=words
    )


def _rec(page: str, startv: int, startp, stopv: int, stopp, bkid="Joshua") -> dict:
    return {
        "page": page,
        "bkid": bkid,
        "startc": 7,
        "startv": startv,
        "startp": startp,
        "stopc": 7,
        "stopv": stopv,
        "stopp": stopp,
    }


def _seed(*recs: dict) -> dict:
    return {"header": {}, "body": list(recs)}


def test_flags_boundary_on_repeated_last_word() -> None:
    seed = _seed(_rec("124B", 12, 1, 12, 6), _rec("125A", 12, 7, 13, None))
    [flag] = find_repeated_boundaries(seed, _stream())
    assert (flag.before, flag.after, flag.ref) == ("124B", "125A", "Joshua 7:12")
    assert flag.last.word_index == 6
    assert flag.last_also_at == [10]
    assert flag.first_also_at == [11]


def test_flags_repeat_ignoring_points() -> None:
    # word 11 has a meteg that word 7 lacks; the consonants still match
    seed = _seed(_rec("124B", 12, 1, 12, 10), _rec("125A", 12, 11, 13, None))
    [flag] = find_repeated_boundaries(seed, _stream())
    assert flag.last_also_at == [6]
    assert flag.first_also_at == [7]


def test_no_flag_when_boundary_words_are_unique() -> None:
    seed = _seed(_rec("124B", 12, 1, 12, 8), _rec("125A", 12, 9, 13, None))
    assert find_repeated_boundaries(seed, _stream()) == []


def test_no_flag_at_verse_boundary() -> None:
    seed = _seed(_rec("124B", 12, 1, 12, None), _rec("125A", 13, 1, 13, None))
    assert find_repeated_boundaries(seed, _stream()) == []


def test_records_on_one_side_are_not_a_boundary() -> None:
    seed = _seed(_rec("124B", 12, 1, 12, 6), _rec("124B", 12, 7, 13, None))
    assert find_repeated_boundaries(seed, _stream()) == []


def test_skips_records_without_bkid() -> None:
    seed = _seed(_rec("124B", 12, 1, 12, 6, bkid=None), _rec("125A", 12, 7, 13, None))
    assert find_repeated_boundaries(seed, _stream()) == []


def test_skips_seed_gap_between_sides() -> None:
    # the next side does not start on the word after the stop
    seed = _seed(_rec("124B", 12, 1, 12, 6), _rec("125A", 12, 8, 13, None))
    assert find_repeated_boundaries(seed, _stream()) == []


def _write_inputs(config) -> None:
    config.paths.seed.parent.mkdir(parents=True, exist_ok=True)
    seed = _seed(
        _rec("124B", 12, 1, 12, 6),
        _rec("125A", 12, 7, 12, 10),
        _rec("125B", 12, 11, 13, None),
    )
    config.paths.seed.write_text(json.dumps(seed), encoding="utf-8")
    save_word_stream(_stream(), config.paths.word_stream)


def test_cli_lists_flags(config) -> None:
    _write_inputs(config)
    result = CliRunner().invoke(check_seed, [], obj=config)
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == (
        "check-seed: 124B/125A Joshua 7:12: "
        "last word on 124B (word 6, לִפְנֵ֣י) also at word 10; "
        "first word on 125A (word 7, אֹיְבֵיהֶ֔ם) also at word 11"
    )
    assert lines[1].startswith("check-seed: 125A/125B Joshua 7:12: ")
    assert lines[-1] == "check-seed: 2 flagged"


def test_cli_filters_by_folio_and_start_folio(config) -> None:
    _write_inputs(config)
    runner = CliRunner()
    by_folio = runner.invoke(check_seed, ["--folio", "125B"], obj=config)
    assert by_folio.output.splitlines()[0].startswith("check-seed: 125A/125B")
    assert by_folio.output.splitlines()[-1] == "check-seed: 1 flagged"
    onward = runner.invoke(check_seed, ["--start-folio", "125B"], obj=config)
    assert onward.output.splitlines()[-1] == "check-seed: 1 flagged"
    both = runner.invoke(
        check_seed, ["--folio", "124B", "--start-folio", "125A"], obj=config
    )
    assert both.exit_code != 0
