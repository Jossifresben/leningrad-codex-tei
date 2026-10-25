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
  `work/` in the task folder (`crop.py` writes `work/crops.json`;
  do not edit it).
- Do not change `packet.json`, `prompt.md`, the image, the seed, the
  word stream, source code, or this skill. `ingest-folio` checks the
  hashes and rejects the run if they change.
- Do not use replies, alignments or TEI from other folio sides.
- Do not place words from the full image alone. Use the crops.
  If you cannot run `crop.py` (for example, the shell command is
  refused), stop and tell the user. Do not go on without crops.
- Do not run `generate-tei` unless the user asks. If they ask, use
  `--folio <FOLIO>` only.

## How to read the prompt

The prompt is the same text that the pipeline sends to Gemini. It
was written for Gemini's code execution tool. Read it like this:

- "Code execution" means Python that you run through your shell.
  Use `scripts/crop.py` (below) or short scripts of your own.
- One run of a script counts as one code-execution call. Opening a
  crop to look at it does not count.
- The prompt says to use extra image work only when the text is
  hard to read. That does not apply here: the crop step is always
  required.
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

2. **Crop the image. This step is required.**
   Do not place any word before you crop. `ingest-folio` rejects a
   run that has no crops made by `scripts/crop.py` for this image.
   The full image is about 3700 × 4200 pixels. You see a smaller
   copy if you open it whole, and line ends are not clear in it.
   Look at the whole image once only, to count the columns. Then
   let `crop.py` find them:

   ```bash
   uv run --no-project --with pillow python \
     .agents/skills/align-folio/scripts/crop.py <image_path> \
     --out-dir {alignments}/tasks/<FOLIO>/work \
     --auto --columns <N> --rows 2
   ```

   Use `work` as the output folder. `<N>` is the number of columns
   you see (3 for prose, 2 for poetry, 1 for a song). `c1` is the
   rightmost column. `crop.py` finds the columns from the ink on
   the page, so you do not give it any box. It writes the crops and
   `work/crops.json`.
   Read the output of `crop.py`:
   - A `WARNING ... text may be cut off` means ink touches the edge
     of a crop. Open the crop and look. If text is cut, run
     `crop.py` again with the box that the warning suggests
     (`--column-box N=x0,y0,x1,y1`), or set the column yourself.
     Keep `--out-dir work`: the last run is the one that counts.
   - A `WARNING ... expected N columns` means `crop.py` could not
     find the columns by itself. Give each column with
     `--column-box N=x0,y0,x1,y1` (fractions of the image, 0-1).
   - No warning does not prove that the crops are complete. Check
     that each crop shows the whole width of every line, and that
     the first and last line of each column are in the crops.
   Use `--rows 3` if the line ends are still too small to read.
   Completion: every column is in crops that you can read, and you
   have seen the first and last line of each column.

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
     "scripts": ["<each script command you ran, in order>"],
     "notes": "<anything a reviewer should know, or empty>"
   }
   ```

   `attempts` is the number of `check-reply` runs. All fields
   except `scripts` and `notes` are required.
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

8. **Hand off.**
   Tell the user the folio is aligned. Do not run `generate-tei`.
   Offer the `commit-folios` skill, which makes the TEI document and the commit. If other folios of the same set are still open, say that `commit-folios` can take all of them at once.

## Many folio sides

Run one session per folio side, for example:

```bash
uv run leningrad prepare-folio --folio 001B --limit 3
for f in 001B 002A 002B; do
  claude -p "/align-folio $f"
done
```

When all sides are aligned, run `commit-folios` once for the whole set, then `folio-pr`.

## Notes

- The skill folder is hashed into each packet. Commit changes to
  this skill before you run `prepare-folio`; the pipeline refuses
  to run with uncommitted changes here.
- The TEI header of the folio records the harness, its version,
  the model, the skill hash, and the attempt count, and links to
  this skill at the commit used.
