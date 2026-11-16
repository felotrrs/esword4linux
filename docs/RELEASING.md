# Releasing esword4linux

This is the maintainer checklist for a public release.

## Before tagging

1. Update `__version__` in `src/esword4linux/__init__.py`. `pyproject.toml`
   reads the version from there.
2. Add the release entry at the top of `docs/CHANGELOG.md`.
3. Confirm that no module files are tracked:

   ```bash
   git ls-files | grep -Ei '\.(bblx|bbli|cmtx|cmti|dctx|dcti|lexi|lexx|refx|refi|topx|devx|harx|mapx|twm)$'
   ```

   The command must print nothing.

4. Run the default suite without a corpus:

   ```bash
   make test
   ```

5. If a private corpus is available, run the real-module tests too:

   ```bash
   ESWORD4LINUX_TEST_CORPUS=/path/to/modules make test
   ```

6. Check the vendored core when the upstream is available:

   ```bash
   ESWORD4LINUX_VENDOR_ORIGIN=/path/to/shared/esword make drift
   ```

7. Build and smoke-test the application:

   ```bash
   make install
   ./run.sh
   ```

   On a clean profile, the first-run dialog must appear and cancelling must
   exit without creating a window.

## Publish

```bash
git add -A
git commit -m "chore: prepare public release"
git push origin main
git tag -a v0.5.0 -m "esword4linux 0.5.0"
git push origin v0.5.0
```

Then create the GitHub release from the tag and paste the top
`docs/CHANGELOG.md` section as release notes.
