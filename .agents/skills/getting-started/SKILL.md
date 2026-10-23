---
name: getting-started
description: Set up a fresh clone of this repo for contributing. Checks uv and gh, installs dependencies, sets up Gemini or the agent harness, sets the git identity, and runs the initial pipeline steps.
disable-model-invocation: true
---

# Getting Started

Guide a new contributor through setup, one step at a time.
Assume the user has already cloned the repo and the shell is at the repo root.
The source of truth is `CONTRIBUTING.MD`. Read it first. If it differs from this skill, follow `CONTRIBUTING.MD`.

Use the repo glossary in `AGENTS.md`.

## Rules

- Do one step at a time. Tell the user the result of each step before you start the next.
- Ask before you install anything or change any setting.
- Never ask the user for an API key. Never print, read, or echo the contents of `.env`.
- Before you give install commands, read the current docs (use WebFetch). Do not use commands from memory. The docs are listed in each step.
- Use the platform found in step 0 for every install command and path. Do not ask the user for the platform.
- If a step fails, show the error, explain the cause in plain words, and stop. Do not try other fixes without asking.

## Steps

0. **Identify the platform.**
   Do this first, before any other step and without asking the user.
   Run `uname -s` and `uname -m`. If `uname` is not available, run `echo $OS` (Windows sets `OS=Windows_NT`) and `echo %PROCESSOR_ARCHITECTURE%`.
   Also find the shell and the package managers that are present (for example `brew`, `apt`, `dnf`, `winget`, `scoop`) with `command -v`.
   Tell the user what you found in one line (for example "macOS arm64, zsh, Homebrew").
   Completion: you know the OS, the CPU architecture, the shell, and the package managers.

1. **Confirm the repo root.**
   Run `git rev-parse --show-toplevel` and check that `pyproject.toml` and `config.yaml` are in that folder. If not, tell the user to `cd` into the clone and stop.
   Completion: you are in the repo root.

2. **Check `uv`.**
   Run `uv --version`. The version must be 0.13.4 or higher. Older versions have known security issues.
   - Missing: read <https://docs.astral.sh/uv/getting-started/installation/>. Show the install command for the platform from step 0 (prefer a package manager that is present). Ask if you may run it. After the install, run `uv --version` again. If the shell does not find `uv`, tell the user to open a new shell.
   - Too old: if `uv self update` works for this install method, offer it. If `uv` came from a package manager (for example Homebrew), give the upgrade command for that manager from the docs instead.
   Completion: `uv --version` shows 0.13.4 or higher.

3. **Install the dependencies.**
   The project needs Python 3.11 or later. `uv` fetches a fitting Python if none is present.
   Run `uv sync`, then `uv run leningrad --help`.
   Completion: the help text lists the `leningrad` commands.

4. **Check `gh`.**
   Run `gh --version`.
   - Missing: say that `gh` is optional but recommended. It is used to find folio issues and to open pull requests. Ask if the user wants it. If yes, read <https://github.com/cli/cli#installation>, show the command for the platform from step 0, and ask before you run it.
   - Present: run `gh auth status`. If the user is not logged in, tell them to run `gh auth login` themselves (it is interactive).
   Completion: `gh` is installed and logged in, or the user declined.

5. **Choose how to align folios.**
   Use AskUserQuestion with two options:
   - **Gemini**: sends each folio image to the Gemini API. Needs a Gemini API key. Supports batch inference.
   - **Agent harness**: an agent (for example Claude Code) does the alignment with the `/align-folio` skill. No API key is needed.

   If **harness**: no API key or `.env` is needed. Skip the Gemini sub-steps below, but still do the remaining steps.

   If **Gemini**:
   1. Tell the user to get a key at <https://ai.google.dev/gemini-api/docs/api-key>.
   2. Run `git check-ignore .env`. If `.env` is not ignored, stop and tell the user. Do not create the file.
   3. If `.env` does not exist, create it with exactly this line: `GEMINI_API_KEY=`. If it exists, do not open it. Check only with `grep -c '^GEMINI_API_KEY=' .env`, which prints a count and no secret. If the count is 0, append the line `GEMINI_API_KEY=`.
   4. Tell the user to open `.env` in their editor, paste the key after the `=`, and save. Tell them not to paste the key in this chat. Wait for them to say they are done.
   5. Check that a value is set without showing it: `grep -Eq '^GEMINI_API_KEY=.+' .env && echo set || echo empty`. If the result is `empty`, ask the user to try again.
   6. Explain that the pipeline reads the key from the environment and does not load `.env` by itself. Commands that need the key must run as `uv run --env-file .env leningrad align-folio ...` (or the user can set `UV_ENV_FILE=.env` in their shell).

   Completion: the choice is made. For Gemini, `.env` has a non-empty key.

6. **Set the git identity (optional).**
   The TEI header takes the contributor name and email from git `user.name` and `user.email`.
   Run `git config user.name` and `git config user.email` and show the values to the user. Ask if they want to change them, and whether the change is for this repo only (recommended) or for all repos (`--global`).
   - Yes: ask for the new values. Run `git config user.name "<name>"` and `git config user.email "<email>"` (add `--global` only if the user asked for it).
   - No: continue.
   Completion: the user kept or changed the values.

7. **Check the UXLC mirror warning.**
   Tell the user not to change `uxlc.download_url` in `config.yaml`. The pipeline gets UXLC 2.5 from the `uxlc-mirror` branch on purpose.
   For local config changes, tell them to copy `config.yaml` to `config.local.yaml` and use `--config config.local.yaml`.

8. **Run the initial steps (optional).**
   Ask if the user wants to run the pulling-data commands now. They download data and can take some time. Run them in this order, and stop at the first error:
   ```bash
   uv run leningrad vendor-seed
   uv run leningrad download-uxlc
   uv run leningrad download-images
   uv run leningrad build-word-stream
   ```
   If `download-uxlc` or `build-word-stream` stops with a UXLC version error, see "UXLC version" in `CONTRIBUTING.MD`: run `download-uxlc` with the default config, then run `build-word-stream` again.
   Completion: all four commands succeed, or the user declined.

9. **Summarize and point to the next step.**
   Give a short list of what is set up. Then say:
   - Find open folios: ask the user if they want to do this now. If yes, use the `find-folios` skill. It lists open issues and asks the owner to assign them.
   - See assigned folios: if the user already has folios, use the `my-folios` skill to list them.
   - Gemini: `uv run --env-file .env leningrad align-folio --folio <FOLIO> --limit <LIMIT>`.
   - Harness: `/align-folio <FOLIO>`.
   - When the work is committed, `/folio-pr` opens the pull request.
   - Never run `generate-tei` without `--folio` or `--start-folio`. It drops hand edits.
