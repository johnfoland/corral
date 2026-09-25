from corral import labels


def test_tab_label_is_compact():
    assert labels.tab_label("Sonnet", "medium") == "Sonnet•medium"
    assert labels.tab_label("Opus", "high", 3) == "Opus•high-3"


def test_parse_accepts_compact_suffixed_and_legacy_spaced():
    assert labels.parse("Sonnet•medium") == labels.AgentLabel("Sonnet", "medium", 1)
    assert labels.parse("Opus•xhigh-2") == labels.AgentLabel("Opus", "xhigh", 2)
    assert labels.parse("Opus • high") == labels.AgentLabel("Opus", "high", 1)
    assert labels.parse("zsh x3") is None
    assert labels.parse("•medium") is None


def test_next_free_fills_gaps_and_counts_legacy():
    B = "•"
    assert labels.next_free([], "Sonnet", "medium") == f"Sonnet{B}medium"
    existing = [f"Sonnet {B} medium", f"Sonnet{B}medium-2", f"Sonnet{B}medium-4", f"Opus{B}high"]
    assert labels.next_free(existing, "Sonnet", "medium") == f"Sonnet{B}medium-3"
    assert labels.next_free(existing, "Sonnet", "high") == f"Sonnet{B}high"


def test_short_and_normalize():
    assert labels.short("Opus•xhigh-2") == "Opus xhi-2"
    assert labels.short("Opus • xhigh") == "Opus xhi"
    assert labels.short("zsh x3") == "zsh x3"
    assert labels.normalize("Sonnet • medium-2") == "Sonnet•medium-2"


def test_agent_name_is_valid_for_herdr():
    assert labels.agent_name("claude", "Sonnet•medium-2") == "claude-sonnet-medium-2"
    assert labels.agent_name("codex", "w1:p3") == "codex-w1-p3"
    assert len(labels.agent_name("claude", "X" * 60)) <= 32
