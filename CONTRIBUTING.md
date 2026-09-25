# Contributing

## Setup

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run corral --help          # the dev install
```

The code is laid out in layers, each depending only on the ones above it:

| Module | Role |
|---|---|
| `herdr.py` | typed wrapper over the `herdr` CLI; raises `HerdrError(code, message)` |
| `config.py` | XDG TOML config over built-in defaults |
| `labels.py` | `Model•effort[-N]` tab labels and agent names |
| `projects.py` | scanning the root, workspace matching |
| `ops.py` | the operations: `up`, `tab`, `stop`, `close` |
| `cli.py` | argparse front end, human and `--json` output |
| `tui/app.py` | the Textual app; calls `ops` in worker threads |

The CLI and the TUI both go through `ops`, so put behaviour changes there.
Tests use `tests/fake_herdr.py`, an in-memory herdr with the same methods as
`Herdr`.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/). The
version and changelog are generated from them:

- `feat: …` → minor bump
- `fix: …` → patch bump
- `feat!: …` or a `BREAKING CHANGE:` footer → major bump (minor while < 1.0)
- `docs:`, `refactor:`, `test:`, `ci:`, `chore:` → no release on their own

Pull request titles are checked for this format in CI.

## Releasing

Releases are automated with [release-please](https://github.com/googleapis/release-please):

1. Merge conventional commits to `master`.
2. release-please opens or updates a **release PR** that bumps the version
   (in `pyproject.toml`, `src/corral/__init__.py` and
   `.claude-plugin/plugin.json`) and adds a section to `CHANGELOG.md`.
3. Merging that PR tags `vX.Y.Z` and creates the GitHub release. The
   `publish` job then builds the package and uploads it to PyPI.

Don't edit versions or `CHANGELOG.md` by hand. To force a specific version,
add a `Release-As: 1.0.0` footer to a commit.

### One-time setup

- **PyPI trusted publishing:** on pypi.org, add a pending publisher for
  project `corral-herdr`: owner `johnfoland`, repo `corral`, workflow `release.yml`,
  environment `pypi`.
- **GitHub environment:** create an environment named `pypi` in the repo
  settings. Optionally require approval there.
- **Actions permissions:** in Settings → Actions → General, allow GitHub
  Actions to create pull requests.
- **CI on release PRs:** PRs opened with the default `GITHUB_TOKEN` don't
  trigger other workflows. To run CI on release PRs, give release-please a
  fine-grained PAT as `token:`.

### Homebrew

The formula lives in [johnfoland/homebrew-tap](https://github.com/johnfoland/homebrew-tap).
After a PyPI release, update `url`/`sha256` to the new sdist, and refresh
the dependency resources with `brew update-python-resources corral`.
