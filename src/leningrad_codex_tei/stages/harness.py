"""Agent-harness alignment: task packets out, raw replies in.

An alternative to the Gemini path in ``align``. ``prepare-folio`` writes a
provider-neutral task packet per folio side; any agent harness (e.g. Claude
Code, driven by the ``align-folio`` skill) reads it and writes a reply plus a
run record next to it; ``ingest-folio`` verifies the run against the packet
and copies the reply into ``{alignments}/raw/`` with a conversation file, so
``parse-raw`` and every later stage run unchanged.

How the agent uses its tools lives in the skill, not the packet. The skill
directory is hashed into the packet and must be committed, like the prompt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from leningrad_codex_tei.config import Config
from leningrad_codex_tei.schemas import AlignmentRecord, WordStream
from leningrad_codex_tei.stages import align as align_stage
from leningrad_codex_tei.stages.align import SeedSlice
from leningrad_codex_tei.stages.validate import ValidationResult, validate_folio
from leningrad_codex_tei.util.git import require_file_clean

# Value of the conversation `inference` field for harness replies.
INFERENCE = "harness"

SKILL_DIR = Path(__file__).resolve().parents[3] / ".agents" / "skills" / "align-folio"

PACKET_FILE = "packet.json"
PROMPT_FILE = "prompt.md"
REPLY_FILE = "reply.xml"
RUN_FILE = "run.json"

# Fields the agent must write to run.json.
RUN_REQUIRED = ("harness", "harness_version", "model", "packet_sha256", "attempts")


def skill_sha256(skill_dir: Path = SKILL_DIR) -> str:
    """sha256 over every file in the skill directory (path + bytes, sorted)."""
    digest = hashlib.sha256()
    files = sorted(
        p for p in skill_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts
    )
    if not files:
        raise FileNotFoundError(f"no skill files in {skill_dir}")
    for path in files:
        digest.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def ensure_skill_clean() -> None:
    """Refuse to run when the skill has uncommitted changes."""
    require_file_clean(SKILL_DIR)


def task_dir(config: Config, folio: str) -> Path:
    return config.paths.alignments / "tasks" / folio


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_path(config: Config, folio: str) -> Path:
    return config.paths.images / config.images.naming.format(folio=folio)


def build_packet(
    sl: SeedSlice,
    word_stream: WordStream,
    config: Config,
    *,
    seed_sha256: str,
    repo_hash: str,
    created: str,
) -> dict:
    """The provider-neutral inputs for one folio side."""
    image = image_path(config, sl.folio)
    if not image.exists():
        raise FileNotFoundError(f"image for {sl.folio} not found: {image}")
    tdir = task_dir(config, sl.folio)
    return {
        "folio": sl.folio,
        "range": f"{sl.start_ref} – {sl.stop_ref}",
        "atom_start": sl.atom_start,
        "atom_end": sl.atom_end,
        "atoms": sl.atom_end - sl.atom_start + 1,
        "prompt_version": align_stage.PROMPT_VERSION,
        "prompt": align_stage._build_prompt(sl, word_stream),
        "image_path": str(image),
        "image_sha256": _file_sha(image),
        "seed_sha256": seed_sha256,
        "skill_sha256": skill_sha256(),
        "repo_hash": repo_hash,
        "created": created,
        "reply_path": str(tdir / REPLY_FILE),
        "run_path": str(tdir / RUN_FILE),
    }


def write_packet(config: Config, packet: dict) -> Path:
    """Write packet.json and prompt.md; return the packet path.

    An old reply.xml/run.json is left in place: its packet_sha256 no longer
    matches, so ingest-folio rejects it until the agent runs again.
    """
    tdir = task_dir(config, packet["folio"])
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / PROMPT_FILE).write_text(packet["prompt"], encoding="utf-8")
    dest = tdir / PACKET_FILE
    dest.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return dest


def check_reply(
    sl: SeedSlice, word_stream: WordStream, text: str
) -> tuple[AlignmentRecord, ValidationResult]:
    """Parse and validate a reply in memory, as parse-raw + validate would."""
    record = align_stage.record_from_reply(sl, word_stream, text)
    return record, validate_folio(sl, record, word_stream)


@dataclass
class Task:
    packet: dict
    packet_sha256: str
    reply: str
    run: dict


def load_task(config: Config, folio: str) -> Task:
    tdir = task_dir(config, folio)
    packet_path = tdir / PACKET_FILE
    if not packet_path.exists():
        raise FileNotFoundError(f"no packet for {folio} (run prepare-folio first)")
    reply_path = tdir / REPLY_FILE
    if not reply_path.exists():
        raise FileNotFoundError(f"no reply for {folio}: {reply_path}")
    run_path = tdir / RUN_FILE
    if not run_path.exists():
        raise FileNotFoundError(f"no run record for {folio}: {run_path}")
    return Task(
        packet=json.loads(packet_path.read_text(encoding="utf-8")),
        packet_sha256=_file_sha(packet_path),
        reply=reply_path.read_text(encoding="utf-8"),
        run=json.loads(run_path.read_text(encoding="utf-8")),
    )


def verify_task(
    task: Task,
    sl: SeedSlice,
    word_stream: WordStream,
    config: Config,
    *,
    seed_sha256: str,
) -> list[str]:
    """Problems that stop ingest; empty when the run matches its packet."""
    problems: list[str] = []
    run, packet = task.run, task.packet
    missing = [k for k in RUN_REQUIRED if run.get(k) in (None, "")]
    if missing:
        problems.append(f"run.json is missing {', '.join(missing)}")
    attempts = run.get("attempts")
    if attempts is not None and (
        not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1
    ):
        problems.append(f"run.json attempts must be an integer >= 1, got {attempts!r}")
    if run.get("packet_sha256") and run["packet_sha256"] != task.packet_sha256:
        problems.append("run.json packet_sha256 does not match packet.json")
    if packet.get("prompt_version") != align_stage.PROMPT_VERSION:
        problems.append("packet prompt_version does not match the current prompt")
    if packet.get("prompt") != align_stage._build_prompt(sl, word_stream):
        problems.append("packet prompt does not match the current seed/word stream")
    image = image_path(config, sl.folio)
    if not image.exists() or packet.get("image_sha256") != _file_sha(image):
        problems.append("packet image_sha256 does not match the image on disk")
    if packet.get("seed_sha256") != seed_sha256:
        problems.append("packet seed_sha256 does not match the seed file")
    if packet.get("skill_sha256") != skill_sha256():
        problems.append("packet skill_sha256 does not match the current skill")
    return problems


def harness_snapshot(task: Task) -> dict:
    """The run settings kept with results and shown in the TEI header."""
    run = task.run
    snapshot = {
        "model": run["model"],
        "harness": run["harness"],
        "harness_version": run["harness_version"],
        "skill_sha256": task.packet["skill_sha256"],
        "attempts": run["attempts"],
    }
    # Optional: only what the agent can state. An absent or "unknown"
    # effort is left out, never filled in.
    effort = run.get("effort")
    if isinstance(effort, str) and effort.strip().lower() not in ("", "unknown"):
        snapshot["effort"] = effort.strip()
    return snapshot


def build_harness_conversation(task: Task) -> dict:
    """Conversation file in the same shape as the Gemini path."""
    packet = task.packet
    conversation = align_stage.build_conversation(
        folio=packet["folio"],
        prompt=packet["prompt"],
        image_uri=packet["image_path"],
        model=task.run["model"],
        prompt_version=packet["prompt_version"],
        inference=INFERENCE,
        response_text=task.reply,
        parts=[{"text": task.reply}],
        ai=harness_snapshot(task),
    )
    conversation["packet_sha256"] = task.packet_sha256
    conversation["harness_run"] = task.run
    return conversation
