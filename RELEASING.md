# Releasing chip

This checklist is the canonical release path. If anything here is wrong
or missing, update this file *first*, then run the release.

## Versioning

`chipspec` is a single package with one version, tracked in two places
that must move together:

- `pyproject.toml` (`[project].version`)
- `src/chip/version.py`

Version bump rules:

- **Patch (0.1.0 → 0.1.1)** — bug fixes, doc updates, wire-format
  clarifications. No spec changes, no API additions.
- **Minor (0.1.1 → 0.2.0)** — new spec surface (ports, stages, receipt
  fields) or validator API that stays backward-compatible.
- **Major (0.x → 1.0)** — a deliberate stability declaration for the
  spec, not a routine feature release.

## The checklist

1. **All tests pass locally.**
   ```bash
   uv run pytest -q
   ```

2. **Bump both version strings.**
   ```bash
   OLD=0.1.0; NEW=0.1.1
   sed -i "s/version = \"$OLD\"/version = \"$NEW\"/" pyproject.toml
   sed -i "s/VERSION = \"$OLD\"/VERSION = \"$NEW\"/" src/chip/version.py
   ```

3. **Update `CHANGELOG.md`.** Add a new dated heading at the top:
   ```markdown
   ## [X.Y.Z] — YYYY-MM-DD

   ### Added
   - …

   ### Fixed
   - …
   ```
   Be specific. Future-you and downstream hosts both read this.

4. **Update `docs/index.html`.** The GitHub Pages landing page is a
   marketing surface, not auto-generated — it lags if we forget.
   Minimum edit on every release: the version marker in the header.

5. **Run the test suite one more time.** Version bumps occasionally
   touch version-format tests.
   ```bash
   uv run pytest -q
   ```

6. **Commit the release.**
   ```bash
   git add pyproject.toml src/chip/version.py CHANGELOG.md docs/index.html
   git commit -m "chore(release): X.Y.Z"
   ```

7. **Tag and push.**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z — one-line summary"
   git push origin main
   git push origin vX.Y.Z
   ```

8. **Create the GitHub release.** Use `gh release create` with
   `--notes` via a heredoc so Markdown renders cleanly:
   ```bash
   gh release create vX.Y.Z \
     --title "vX.Y.Z — short tagline" \
     --notes "$(cat <<'EOF'
   ## Highlights
   …

   **Full diff:** https://github.com/lavallee/chip/compare/vX.Y.Z-1...vX.Y.Z
   EOF
   )"
   ```
   Creating the release triggers `.github/workflows/publish.yml`
   (trusted publishing, `skip-existing`) — no manual `uv publish` step.

## Post-release

- Confirm the release at https://github.com/lavallee/chip/releases.
- If `docs/index.html` changed, wait ~1 minute for GitHub Pages to
  deploy, then verify the version marker updated.
- Verify the publish workflow run went green and the new version shows
  on https://pypi.org/project/chipspec/.
