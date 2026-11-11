# Maude's Library: working rules for Claude

README.md is the source of truth for what this project is and how it is built
(site pages, stack, flow, file map). Read it first. If your work changes any of
that, update README.md in the same change.

## This repo is public
Every file, commit and the published site are public. Never write emails, phone
numbers, IDs, tokens, or private notes into any file, commit message or post.
Secrets live in `.env` (gitignored) and GitHub Secrets only.

## Before every push (the three checks)
1. **Local:** run `scripts/check.sh` (PII/secret scan, then `pytest`). Do not push
   if it fails; fix the cause. Never use `--no-verify` or edit the checks to make
   them pass without asking me.
2. **Git hook:** `.githooks/pre-push` runs the same script. Enabled per clone with
   `git config core.hooksPath .githooks`.
3. **CI:** `.github/workflows/deploy.yml` runs the PII scan and pytest again before
   building and deploying.
If you add a new kind of data to the site, extend `scripts/pii_check.py` and add a
test for it.

## How the code is organized
- All logic is Python in `src/`; `build.py` is the entry point. Browser JS only
  sorts, filters and shows things Python already computed.
- Notion column names live in `config.py`; change them there only.
- Hand-edited content: `data/*.yml` (taste page), `posts/*.md` (blog),
  `static/doodles/<series>/` (doodles).
- `data/cache/books.json` and `static/covers/` are written by the build; don't
  edit them by hand.

## Working style
- Work on one area at a time: Design, Main page, Taste, Blog, Doodles, Maintenance.
  Follow the Figma design guideline for visual changes.
- Add or update a test with every behaviour change in `src/`.
- Don't commit or push unless I ask. Say what you changed and what you didn't verify.
- Keep README.md short and written for outside readers, not for me.
