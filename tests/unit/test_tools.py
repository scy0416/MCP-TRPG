"""Unit tests for core Tool input validation."""

import pytest

from trpg_mcp.tools import (
    _validate_ability,
    _validate_dice_spec,
    _validate_rolls,
    _validate_stats,
    _validate_text,
    _validate_uuid,
)


def test_validate_stats_accepts_the_mvp_assignment() -> None:
    assert _validate_stats({"str": 3, "dex": 2, "int": 1, "cha": 0}) == {
        "str": 3,
        "dex": 2,
        "int": 1,
        "cha": 0,
    }


@pytest.mark.parametrize(
    "stats",
    [
        {"str": 3, "dex": 2, "int": 1},
        {"str": 3, "dex": 3, "int": 1, "cha": 0},
        {"str": True, "dex": 2, "int": 1, "cha": 0},
        {"str": 4, "dex": 2, "int": 1, "cha": 0},
    ],
)
def test_validate_stats_rejects_invalid_assignments(stats: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="ability|stats"):
        _validate_stats(stats)


def test_validate_text_and_uuid() -> None:
    _validate_text("  Tower  ", "title", 120)
    assert _validate_uuid("10000000-0000-0000-0000-000000000001", "campaign_id") == (
        "10000000-0000-0000-0000-000000000001"
    )

    with pytest.raises(ValueError):
        _validate_text("  ", "title", 120)
    with pytest.raises(ValueError, match="UUID"):
        _validate_uuid("not-a-uuid", "campaign_id")


def test_validate_check_inputs() -> None:
    assert _validate_ability("Strength") == "str"
    assert _validate_dice_spec({"count": 1, "sides": 20}) == {"count": 1, "sides": 20}

    with pytest.raises(ValueError, match="ability"):
        _validate_ability("wisdom")
    with pytest.raises(ValueError, match="dice"):
        _validate_dice_spec({"count": 0, "sides": 20})
    with pytest.raises(ValueError, match="dice"):
        _validate_dice_spec(None)  # type: ignore[arg-type]
    assert _validate_rolls([1, 20]) == [1, 20]
    with pytest.raises(ValueError, match="rolls"):
        _validate_rolls([])
