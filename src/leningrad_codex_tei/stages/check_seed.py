"""check-seed stage: flag seed page boundaries that may be at the wrong word.

Known seed boundary errors (#1076) fall where a word repeats within the
verse that spans two sides: the boundary is set at the other copy of the
word. This check finds every boundary with that shape, so an aligner can
look at the image there. A flag is not an error; most flagged boundaries
are correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from leningrad_codex_tei.schemas import Word, WordStream
from leningrad_codex_tei.stages.align import _norm_word, stream_book_for


@dataclass
class BoundaryFlag:
    before: str  # side that ends mid-verse
    after: str  # side that continues the verse
    ref: str  # e.g. "Kings_2 13:21"
    last: Word  # last word on `before`
    first: Word  # first word on `after`
    # other word_index values in the verse with the same consonants
    last_also_at: list[int]
    first_also_at: list[int]


def _anchor(verse_words: list[Word], part, stop: bool) -> Word | None:
    """Word at a seed part-of-verse; None part means the verse edge."""
    if part is None:
        return verse_words[-1] if stop else verse_words[0]
    return next((w for w in verse_words if w.word_index == int(part)), None)


def _repeats(word: Word, verse_words: list[Word]) -> list[int]:
    norm = _norm_word(word.text)
    return [
        w.word_index
        for w in verse_words
        if w.atom != word.atom and _norm_word(w.text) == norm
    ]


def find_repeated_boundaries(seed: dict, word_stream: WordStream) -> list[BoundaryFlag]:
    """Boundaries inside a verse where the word on either side repeats in it.

    Pure; no side effects. A boundary is the stop of the last seed record of
    one side and the start of the first record of the next side. Records
    with no bkid (e.g. Masoretic lists) are skipped, and so are boundaries
    between verses.
    """
    verses: dict[tuple[str, int, int], list[Word]] = {}
    for w in word_stream.words:
        verses.setdefault((w.book, w.chapter, w.verse), []).append(w)

    recs = seed.get("body", [])
    flags: list[BoundaryFlag] = []
    for a, b in pairwise(recs):
        if a["page"] == b["page"] or not a.get("bkid") or not b.get("bkid"):
            continue
        key = (stream_book_for(a["bkid"]), a.get("stopc"), a.get("stopv"))
        if key != (stream_book_for(b["bkid"]), b.get("startc"), b.get("startv")):
            continue
        verse_words = verses.get(key)
        if not verse_words:
            continue
        last = _anchor(verse_words, a.get("stopp"), stop=True)
        first = _anchor(verse_words, b.get("startp"), stop=False)
        if last is None or first is None or first.atom != last.atom + 1:
            continue
        last_also_at = _repeats(last, verse_words)
        first_also_at = _repeats(first, verse_words)
        if last_also_at or first_also_at:
            flags.append(
                BoundaryFlag(
                    before=a["page"],
                    after=b["page"],
                    ref=f"{key[0]} {key[1]}:{key[2]}",
                    last=last,
                    first=first,
                    last_also_at=last_also_at,
                    first_also_at=first_also_at,
                )
            )
    return flags
