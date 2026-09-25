from pathlib import Path

from corral import projects


def test_scan_finds_nested_repos_and_leading_folders(cfg):
    tree = projects.scan(cfg)
    assert tree.tops == ["Archive", "courses", "cruzainet", "cSolveWordle", "MCPs", "scratch"]
    n = tree.nodes
    assert n["cruzainet"].children == ["cruzainet/api", "cruzainet/web-app"]
    assert n["cruzainet"].repos_below == 2 and n["cruzainet"].branch == "master"
    assert n["cruzainet/api"].branch == "develop" and n["cruzainet/api"].depth == 1
    assert n["Archive"].is_repo is False
    assert n["Archive/AyeAI"].children == ["Archive/AyeAI/ayeai-api"]
    assert "cruzainet/notes" not in n  # not a repo, no repos below
    assert n["cSolveWordle"].children == []  # hidden and pruned dirs skipped
    assert tree.ancestors("Archive/AyeAI/ayeai-api") == ["Archive/AyeAI", "Archive"]


def test_scan_depth_limit(cfg):
    cfg.scan_depth = 1
    n = projects.scan(cfg).nodes
    assert "cruzainet/api" in n
    assert "Archive/AyeAI" not in n  # its repo is at depth 2


def test_label_for(cfg, root, tmp_path):
    assert projects.label_for(root / "courses", root) == "courses"
    assert projects.label_for(root / "cruzainet" / "api", root) == "cruzainet/api"
    assert projects.label_for(tmp_path / "elsewhere", root) == "elsewhere"


def test_find_workspace_by_label_then_legacy_basename(herdr, root):
    api = root / "cruzainet" / "api"
    ws, _, _ = herdr.create_workspace(str(api.resolve()), "api")  # legacy basename label
    snap = herdr.snapshot()
    assert projects.find_workspace(snap, "cruzainet/api", api).id == ws
    assert projects.find_workspace(snap, "cruzainet/web-app", root / "cruzainet/web-app") is None
    # a basename match in a different directory is not the same project
    assert projects.find_workspace(snap, "other/api", Path("/nowhere/api")) is None
    ws2, _, _ = herdr.create_workspace(str(api), "cruzainet/api")
    assert projects.find_workspace(herdr.snapshot(), "cruzainet/api", api).id == ws2
