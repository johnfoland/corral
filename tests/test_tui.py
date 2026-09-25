"""Drive the TUI headlessly against the fake herdr."""

from corral import ops
from corral.tui.app import AgentPicker, Confirm, CorralApp

B = "•"


async def settle(pilot, app, seconds=0.3):
    await pilot.pause(seconds)
    await app.workers.wait_for_complete()
    await pilot.pause(0.1)


def rows(app):
    return [str(k.value) for k in app.query_one("#projects").rows]


async def test_tree_folds_and_open_builds_nested_workspace(herdr, cfg):
    app = CorralApp(cfg, herdr)
    async with app.run_test(size=(150, 40)) as pilot:
        await settle(pilot, app)
        assert rows(app)[:3] == ["Archive", "courses", "cruzainet"]
        app.move_to("cruzainet")
        await pilot.press("right")
        assert "cruzainet/api" in rows(app)
        await pilot.press("right")  # step into the first child
        assert app.current_rel() == "cruzainet/api"
        await pilot.press("o")
        await settle(pilot, app)
        assert [w["label"] for w in herdr.ws.values()] == ["cruzainet/api"]
        assert app.st("cruzainet/api").ws is not None
        await pilot.press("left")  # to the parent
        await pilot.press("left")  # fold it
        assert "cruzainet/api" not in rows(app)


async def test_add_agent_twice_suffixes(herdr, cfg):
    ws = ops.up(herdr, cfg, cfg.root / "courses").workspace
    app = CorralApp(cfg, herdr)
    async with app.run_test(size=(150, 40)) as pilot:
        await settle(pilot, app)
        app.move_to("courses")
        for _ in range(2):
            await pilot.press("a")
            await pilot.pause(0.2)
            assert isinstance(app.screen, AgentPicker)
            await pilot.press("enter", "enter")  # sonnet (default) -> medium
            await settle(pilot, app)
        tabs = [t["label"] for t in herdr.tabs.values() if t["ws"] == ws]
        assert tabs[-2:] == [f"Sonnet{B}medium-2", f"Sonnet{B}medium-3"]


async def test_close_asks_first(herdr, cfg):
    ws = ops.up(herdr, cfg, cfg.root / "courses").workspace
    app = CorralApp(cfg, herdr)
    async with app.run_test(size=(150, 40)) as pilot:
        await settle(pilot, app)
        app.move_to("courses")
        await pilot.press("x")
        await pilot.pause(0.5)
        assert isinstance(app.screen, Confirm) and "would close" in app.screen.body
        await pilot.press("n")
        await settle(pilot, app)
        assert ws in herdr.ws
        await pilot.press("x")
        await pilot.pause(0.5)
        await pilot.press("y")
        await settle(pilot, app)
        assert ws not in herdr.ws


async def test_filter_keeps_ancestors(herdr, cfg):
    app = CorralApp(cfg, herdr)
    async with app.run_test(size=(150, 40)) as pilot:
        await settle(pilot, app)
        await pilot.press("slash", *"ayeai", "enter")
        await pilot.pause(0.2)
        assert rows(app) == ["Archive", "Archive/AyeAI", "Archive/AyeAI/ayeai-api"]
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert "courses" in rows(app)
