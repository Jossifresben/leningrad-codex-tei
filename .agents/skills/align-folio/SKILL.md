---
name: align-folio
description: Align one folio side with this agent instead of Gemini. Reads a task packet from prepare-folio, writes reply.xml and run.json for ingest-folio.
---

# Align Folio (agent harness)

Do the alignment step of the pipeline with your own tools. The
pipeline does all other steps. Your output goes through the same
parser and checks as a Gemini reply.

Use the repo glossary in `AGENTS.md`: a **folio side** is
`Fxxx{A|B}`; **alignment** puts the known words on columns and
lines; **locate-known-text** is the method.

The argument is one folio side, for example `001B`. Do one folio
side per session. Context from one folio can change your work on
the next.

Paths below use `{alignments}` for `config.paths.alignments`
(`data/alignments/` by default). The task folder is
`{alignments}/tasks/<FOLIO>/`.

## Rules

- Write only these files: `reply.xml`, `run.json`, and files under
  `work/` in the task folder.
- Do not change `packet.json`, `prompt.md`, the image, the seed, the
  word stream, source code, or this skill. `ingest-folio` checks the
  hashes and rejects the run if they change.
- Do not use replies, alignments or TEI from other folio sides.
- Do not run `generate-tei` unless the user asks. If they ask, use
  `--folio <FOLIO>` only.

## How to read the prompt

The prompt is the same text that the pipeline sends to Gemini. It
was written for Gemini's code execution tool. Read it like this:

- "Code execution" means Python that you run through your shell.
  Use `scripts/crop.py` (below) or short scripts of your own.
- One run of a script counts as one code-execution call. Opening a
  crop to look at it does not count.
- Keep to the prompt's limits when you can. If you must go past a
  limit (for example, a bad column crop), write the reason in
  `run.json` `notes`.
- "Return the XML directly" and "Return ONLY the TEI XML" apply to
  `reply.xml`, not to your messages.
- "Return the XML directly first" does not apply. You cannot write
  the XML before you crop and read the image. Do steps 2 and 3 first.

## Steps

1. **Read the packet.**
   Read `{alignments}/tasks/<FOLIO>/packet.json` and `prompt.md`.
   If there is no packet, stop and tell the user to run
   `uv run leningrad prepare-folio --folio <FOLIO>`.
   Get the packet hash now:
   `shasum -a 256 {alignments}/tasks/<FOLIO>/packet.json`.
   Completion: you have the prompt, the image path, and the hash.

2. **Crop the image.**
   The full image is about 3700 × 4200 pixels. You see a smaller
   copy if you open it whole, so look at the whole image once only,
   to find the columns. Then crop:

   ```bash
   uv run --no-project --with pillow python \
     .agents/skills/align-folio/scripts/crop.py <image_path> \
     --out-dir {alignments}/tasks/<FOLIO>/work \
     --box x0,y0,x1,y1 --columns 3 --rows 2
   ```

   `--box` is the text area as fractions of the image (0-1).
   For a 3-column prose page, start with
   `--box 0.11,0.17,0.87,0.78` (this fitted folio 099A). Page
   margins differ, so check the first crop and change the box if
   text is cut off. A page with a wide top or bottom margin note
   (for example the masorah) may need a different top or bottom.
   `--columns` is the number of columns on the page (3 for prose,
   2 for poetry, 1 for a song). `c1` is the rightmost column.
   Use `--rows 2` or `3` so the line ends are large enough to read.
   Completion: each column is in crops that you can read.

3. **Place the words.**
   Count the lines in each column. Find the last word of each line.
   Copy the words from `<TEXT>` in the prompt onto the lines, in
   order, with no changes. Follow the prompt's notes and lineation
   rules (blank lines get their own `<lb>`).
   Line breaks are the part that `check-reply` cannot check. Look
   at each line end in the crops:
   - A whole word that does not fit goes on the next line. Check
     the first word of each line and the last word of the line
     before it. Most line-break errors are a whole word on the
     wrong line.
   - A word that is broken across two lines is rare. Do not join
     it. Write each piece on its own line, as it is written in the
     codex. The parser joins the pieces, and the word counts for
     the line where it starts. If you find one, write it in
     `run.json` `notes`.
   - A standalone paseq (`׀`) stays with the word before it.
   Completion: every line of every column has its words, and you
   looked at each line end in the crops.

4. **Write `reply.xml`.**
   Write only the `<cb>`/`<lb>` XML and the words, as in the
   prompt's example output. No commentary, no markdown fences.
   Completion: `{alignments}/tasks/<FOLIO>/reply.xml` exists.

5. **Check the reply.**
   `uv run leningrad check-reply --folio <FOLIO>`
   This runs the same parser and checks as `parse-raw` and
   `validate`, and writes nothing. If it fails, fix `reply.xml` and
   run it again. Count each run of this command as one attempt.
   Stop after 3 failed attempts and tell the user.
   A pass means the words are complete and in order. It does not
   mean the line breaks are correct. Only your look at the image
   can make the line breaks correct.
   Completion: the check passes, or you stopped after 3 attempts.

6. **Write `run.json`.**
   Write `{alignments}/tasks/<FOLIO>/run.json`:

   ```json
   {
     "harness": "claude-code",
     "harness_version": "<output of `claude --version`>",
     "model": "<your exact model ID>",
     "packet_sha256": "<hash from step 1>",
     "attempts": 1,
     "effort": "<effort level, only if you know it>",
     "scripts": ["<each script command you ran, in order>"],
     "notes": "<anything a reviewer should know, or empty>"
   }
   ```

   `attempts` is the number of `check-reply` runs. All fields
   except `effort`, `scripts` and `notes` are required.
   `effort` is the reasoning effort level of this session (for
   example `low`, `medium`, `high`). Write it only if the user, the
   command that started you, or your harness settings state it.
   Do not guess. If you do not know it, leave the field out. It is
   not a sampling setting such as temperature, which you cannot
   read.
   If `claude --version` is not found, get the version from your
   harness in another way (for example, an environment variable
   such as `AI_AGENT`, or the `--version` output of your harness
   binary), and write how you got it in `notes`. Do not leave
   `harness_version` empty.
   Completion: `run.json` exists and has all required fields.

7. **Ingest and parse.**
   ```bash
   uv run leningrad ingest-folio --folio <FOLIO>
   uv run leningrad parse-raw --folio <FOLIO>
   uv run leningrad validate --folio <FOLIO>
   ```
   If `ingest-folio` rejects the run, tell the user the reason. Do
   not edit the packet to make it pass.
   Completion: `validate` shows the folio as aligned.

## Many folio sides

Run one session per folio side, for example:

```bash
uv run leningrad prepare-folio --folio 001B --limit 3
for f in 001B 002A 002B; do
  claude -p "/align-folio $f"
done
```

## Notes

- The skill folder is hashed into each packet. Commit changes to
  this skill before you run `prepare-folio`; the pipeline refuses
  to run with uncommitted changes here.
- The TEI header of the folio records the harness, its version,
  the model, the skill hash, and the attempt count, and links to
  this skill at the commit used.
