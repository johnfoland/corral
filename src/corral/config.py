"""Configuration: an XDG-located TOML file layered over built-in defaults.

Lookup order for the file: $CORRAL_CONFIG, then $XDG_CONFIG_HOME/corral/
config.toml, then ~/.config/corral/config.toml. The XDG path is used on macOS
too, deliberately -- not ~/Library/Application Support.

Every key is optional; a missing file means all defaults. See DEFAULT_TOML
(written by `corral config init`) for the documented shape.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

EFFORT = "{effort}"

DEFAULT_PRUNE = frozenset(
    {
        "node_modules",
        "vendor",
        "dist",
        "build",
        "target",
        "venv",
        "env",
        "__pycache__",
        "site-packages",
        "Pods",
        "DerivedData",
        "bower_components",
    }
)

DEFAULT_EFFORTS: dict[str, list[str]] = {
    "claude": ["low", "medium", "high", "xhigh", "max"],
    "codex": ["minimal", "low", "medium", "high", "xhigh"],
}
FALLBACK_EFFORTS = ["low", "medium", "high"]


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    key: str  # what you type: "sonnet"
    tool: str  # herdr agent kind: "claude", "codex", ...
    display: str  # tab label prefix: "Sonnet"
    args: tuple[str, ...]  # agent args; "{effort}" is substituted

    def args_for(self, effort: str) -> list[str]:
        return [a.replace(EFFORT, effort) for a in self.args]


DEFAULT_MODELS = (
    ModelSpec("sonnet", "claude", "Sonnet", ("--model", "sonnet", "--effort", EFFORT)),
    ModelSpec("opus", "claude", "Opus", ("--model", "opus", "--effort", EFFORT)),
    ModelSpec("haiku", "claude", "Haiku", ("--model", "haiku", "--effort", EFFORT)),
    ModelSpec("codex", "codex", "Codex", ("-c", f"model_reasoning_effort={EFFORT}")),
)


@dataclass(frozen=True)
class Utility:
    """The utility tab: one pane on top, two below. Each is a command to run,
    or "" for a plain shell. Missing commands degrade to a shell."""

    enabled: bool = True
    top: str = "yazi"
    bottom_left: str = ""
    bottom_right: str = "lazygit"


@dataclass
class Config:
    root: Path = field(default_factory=lambda: Path("~/Code").expanduser())
    scan_depth: int = 3
    prune: frozenset[str] = DEFAULT_PRUNE
    default_agents: tuple[str, ...] = ("sonnet/medium",)
    refresh_seconds: float = 3.0
    agent_timeout_ms: int = 60000
    utility: Utility = field(default_factory=Utility)
    models: tuple[ModelSpec, ...] = DEFAULT_MODELS
    efforts: dict[str, list[str]] = field(default_factory=lambda: dict(DEFAULT_EFFORTS))
    path: Path | None = None  # file it was loaded from, if any

    def model(self, key: str) -> ModelSpec:
        for m in self.models:
            if m.key == key:
                return m
        known = ", ".join(m.key for m in self.models)
        raise ConfigError(f"unknown model '{key}' (known: {known})")

    def model_by_display(self, display: str) -> ModelSpec | None:
        want = display.strip().lower()
        return next((m for m in self.models if m.display.lower() == want), None)

    def efforts_for(self, tool: str) -> list[str]:
        return self.efforts.get(tool, FALLBACK_EFFORTS)


def config_path() -> Path:
    if env := os.environ.get("CORRAL_CONFIG"):
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "corral" / "config.toml"


def load(path: Path | None = None, root: str | None = None) -> Config:
    """Load the config file (if present) over the defaults. `root` (from a CLI
    flag) beats $CORRAL_ROOT, which beats the file's `root`."""
    path = path or config_path()
    data: dict = {}
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as e:
            raise ConfigError(f"{path}: {e}") from e
    cfg = from_dict(data)
    cfg.path = path if path.is_file() else None
    override = root or os.environ.get("CORRAL_ROOT")
    if override:
        cfg.root = Path(override).expanduser()
    return cfg


def _expect(data: dict, key: str, kind: type | tuple[type, ...], where: str = ""):
    v = data[key]
    if not isinstance(v, kind):
        raise ConfigError(f"{where}{key}: expected {getattr(kind, '__name__', kind)}")
    return v


def from_dict(data: dict) -> Config:
    cfg = Config()
    if "root" in data:
        cfg.root = Path(_expect(data, "root", str)).expanduser()
    if "scan_depth" in data:
        cfg.scan_depth = _expect(data, "scan_depth", int)
    if "prune" in data:
        cfg.prune = frozenset(_expect(data, "prune", list))
    if "prune_extra" in data:
        cfg.prune = cfg.prune | frozenset(_expect(data, "prune_extra", list))
    if "default_agents" in data:
        cfg.default_agents = tuple(_expect(data, "default_agents", list))
    if "refresh_seconds" in data:
        cfg.refresh_seconds = float(_expect(data, "refresh_seconds", (int, float)))
    if "agent_timeout_ms" in data:
        cfg.agent_timeout_ms = _expect(data, "agent_timeout_ms", int)

    if "utility" in data:
        u = _expect(data, "utility", dict)
        base = Utility()
        cfg.utility = Utility(
            enabled=bool(u.get("enabled", base.enabled)),
            top=str(u.get("top", base.top)),
            bottom_left=str(u.get("bottom_left", base.bottom_left)),
            bottom_right=str(u.get("bottom_right", base.bottom_right)),
        )

    if "models" in data:
        models = []
        for i, m in enumerate(_expect(data, "models", list)):
            where = f"models[{i}]."
            if not isinstance(m, dict):
                raise ConfigError(f"models[{i}]: expected a table")
            for k in ("key", "tool", "display"):
                if k not in m:
                    raise ConfigError(f"{where}{k} is required")
            args = m.get("args", [])
            if isinstance(args, str):
                args = args.split()
            models.append(
                ModelSpec(
                    key=str(m["key"]),
                    tool=str(m["tool"]),
                    display=str(m["display"]),
                    args=tuple(str(a) for a in args),
                )
            )
        keys = [m.key for m in models]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise ConfigError(f"models: duplicate key(s): {', '.join(dupes)}")
        if not models:
            raise ConfigError("models: at least one model is required")
        cfg.models = tuple(models)

    if "efforts" in data:
        eff = _expect(data, "efforts", dict)
        cfg.efforts = {**DEFAULT_EFFORTS, **{k: list(v) for k, v in eff.items()}}

    for spec in cfg.default_agents:
        cfg.model(spec.partition("/")[0])  # fail early on a bad default
    return cfg


DEFAULT_TOML = """\
# corral configuration -- every key is optional.
# Location: $CORRAL_CONFIG, else $XDG_CONFIG_HOME/corral/config.toml,
# else ~/.config/corral/config.toml.

# Directory whose subdirectories are your projects. Overridden by --root or
# $CORRAL_ROOT.
root = "~/Code"

# How many levels below a top-level project to look for nested git repos.
scan_depth = 3

# Directory names never descended into. `prune` replaces the built-in list;
# `prune_extra` adds to it. Hidden directories are always skipped.
# prune_extra = ["third_party"]

# Agent tabs a new workspace gets, as "model/effort" specs.
default_agents = ["sonnet/medium"]

# How often the TUI polls herdr, and how long to wait for an agent to start.
refresh_seconds = 3.0
agent_timeout_ms = 60000

# The utility tab: a pane on top, two below. Each value is a command, or ""
# for a plain shell. A command that isn't installed falls back to a shell.
[utility]
enabled = true
top = "yazi"
bottom_left = ""
bottom_right = "lazygit"

# Effort levels offered per agent tool (herdr agent kind).
[efforts]
claude = ["low", "medium", "high", "xhigh", "max"]
codex = ["minimal", "low", "medium", "high", "xhigh"]

# The model matrix. `tool` is the herdr agent kind (claude, codex, gemini,
# opencode, ...). `key` is what you type (`corral tab opus/high`), `display`
# prefixes the tab label ("Opus•high"), and `args` go to the agent binary
# with {effort} substituted. Defining any [[models]] replaces the defaults.
[[models]]
key = "sonnet"
tool = "claude"
display = "Sonnet"
args = ["--model", "sonnet", "--effort", "{effort}"]

[[models]]
key = "opus"
tool = "claude"
display = "Opus"
args = ["--model", "opus", "--effort", "{effort}"]

[[models]]
key = "haiku"
tool = "claude"
display = "Haiku"
args = ["--model", "haiku", "--effort", "{effort}"]

[[models]]
key = "codex"
tool = "codex"
display = "Codex"
args = ["-c", "model_reasoning_effort={effort}"]
"""
