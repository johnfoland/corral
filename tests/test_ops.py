import pytest

from corral import ops
from corral.config import ConfigError

B = "•"


def labels_in(herdr, ws):
    return [t["label"] for t in herdr.tabs.values() if t["ws"] == ws]


def test_up_builds_utility_and_default_agent(herdr, cfg, root):
    res = ops.up(herdr, cfg, root / "cruzainet" / "api")
    assert res.action == "created" and res.label == "cruzainet/api"
    assert labels_in(herdr, res.workspace) == ["cruzainet/api", f"Sonnet{B}medium"]
    utility_panes = [p for p in herdr.panes.values() if p["tab"].endswith("t2")]
    assert len(utility_panes) == 3
    start = next(c for c in herdr.calls if c[0] == "agent_start")
    assert start[1:3] == ("claude-sonnet-medium", "claude")
    assert start[4] == ("--model", "sonnet", "--effort", "medium")


def test_up_existing_focuses_and_fill_is_idempotent(herdr, cfg, root):
    first = ops.up(herdr, cfg, root / "courses")
    again = ops.up(herdr, cfg, root / "courses")
    assert again.action == "focused" and again.workspace == first.workspace
    filled = ops.up(herdr, cfg, root / "courses", fill=True, agents=["sonnet", "opus/high"])
    assert [(t.label, t.action) for t in filled.tabs] == [
        ("courses", "have"),
        (f"Sonnet{B}medium", "have"),
        (f"Opus{B}high", "added"),
    ]


def test_fill_treats_legacy_spaced_label_as_present(herdr, cfg, root):
    ws, tab, _ = herdr.create_workspace(str(root / "courses"), "courses")
    herdr.create_tab(ws, str(root / "courses"), f"Sonnet {B} medium")
    res = ops.up(herdr, cfg, root / "courses", fill=True, dry_run=True)
    assert (f"Sonnet{B}medium", "have") in [(t.label, t.action) for t in res.tabs]


def test_new_agent_tab_gets_suffix_and_unique_agent_name(herdr, cfg, root):
    ws = ops.up(herdr, cfg, root / "courses").workspace
    r = ops.tab(herdr, cfg, ["sonnet"], ws=ws)
    assert r[0].action == "have"
    r2 = ops.tab(herdr, cfg, ["sonnet", "sonnet"], ws=ws, new=True)
    assert [x.label for x in r2] == [f"Sonnet{B}medium-2", f"Sonnet{B}medium-3"]
    assert [x.agent for x in r2] == ["claude-sonnet-medium-2", "claude-sonnet-medium-3"]


def test_agent_name_collision_falls_back_to_pane_id(herdr, cfg, root):
    ops.up(herdr, cfg, root / "cruzainet")  # takes claude-sonnet-medium
    ws = ops.up(herdr, cfg, root / "courses", no_agent=True).workspace
    res = ops.tab(herdr, cfg, ["sonnet"], ws=ws)
    assert res[0].action == "added"
    assert res[0].agent == "claude-" + res[0].pane.replace(":", "-")


def test_agent_start_busy_pane_is_retried(herdr):
    herdr.create_workspace("/tmp", "x")
    pane = next(iter(herdr.panes))
    herdr.busy_once.add(pane)
    assert ops.start_agent(herdr, "claude-a", "claude", pane, 1000, []) == "claude-a"
    assert sum(1 for c in herdr.calls if c[0] == "agent_start") == 2


def test_failed_agent_leaves_shell_and_reports(herdr, cfg, root):
    herdr.fail_start.add("claude")
    res = ops.up(herdr, cfg, root / "courses")
    assert not res.ok and res.tabs[-1].action == "failed"


def test_unknown_model_fails_before_touching_herdr(herdr, cfg, root):
    with pytest.raises(ConfigError, match="unknown model"):
        ops.up(herdr, cfg, root / "courses", agents=["nope"])
    assert not herdr.ws


def test_force_fill_closes_strays_keeps_agents(herdr, cfg, root):
    ws = ops.up(herdr, cfg, root / "courses").workspace
    stray, _ = herdr.create_tab(ws, "/tmp", "zsh")
    busy, busy_pane = herdr.create_tab(ws, "/tmp", "manual claude")
    herdr.agents[busy_pane] = {"name": "", "kind": "claude", "args": [], "status": "idle"}
    plan = ops.up(herdr, cfg, root / "courses", force_fill=True, dry_run=True)
    assert plan.closed == ["zsh"] and plan.kept_running == ["manual claude"]
    assert stray in herdr.tabs  # dry run changed nothing
    ops.up(herdr, cfg, root / "courses", force_fill=True)
    assert stray not in herdr.tabs and busy in herdr.tabs


def test_stop_by_label_name_and_all(herdr, cfg, root):
    ws = ops.up(herdr, cfg, root / "courses", agents=["sonnet", "opus/high"]).workspace
    r = ops.stop(herdr, cfg, [f"Opus {B} high"], ws=ws, dry_run=True)
    assert r[0].action == "would-stop"
    r = ops.stop(herdr, cfg, ["claude-sonnet-medium"], ws=ws)
    assert r[0].action == "stopped"
    assert ops.stop(herdr, cfg, ["ghost"], ws=ws)[0].action == "failed"
    r = ops.stop(herdr, cfg, [], ws=ws, all_=True)
    assert [x.target for x in r] == [f"Opus{B}high"] and not herdr.agents
    with pytest.raises(ConfigError):
        ops.stop(herdr, cfg, ["x"], ws=ws, all_=True)


def test_close_by_label_and_refusals(herdr, cfg, root, monkeypatch):
    a = ops.up(herdr, cfg, root / "courses").workspace
    herdr.create_workspace("/tmp", "dup")
    herdr.create_workspace("/tmp", "dup")
    assert ops.close(herdr, ["dup"])[0].action == "failed"  # ambiguous
    monkeypatch.setenv("HERDR_WORKSPACE_ID", a)
    assert ops.close(herdr, ["courses"])[0].action == "refused"
    r = ops.close(herdr, ["courses"], dry_run=True, include_self=True)[0]
    assert r.action == "would-close" and r.agents == ["claude-sonnet-medium"]
    assert ops.close(herdr, [a], include_self=True)[0].action == "closed"
    assert a not in herdr.ws
