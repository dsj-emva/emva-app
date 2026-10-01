from emva_api.ladder import LADDER, LOST, PLACES, Stage, place_name


def test_the_canonical_ladder_runs_from_submitted_to_won_in_order():
    assert [place_name(stage) for stage in LADDER] == [
        "Submitted",
        "Contact attempted",
        "Engaged",
        "Qualified",
        "Proposal",
        "Won",
    ]
    assert LADDER[0] is Stage.SUBMITTED
    assert LADDER[-1] is Stage.WON


def test_lost_is_not_a_stage_on_the_ladder():
    assert LOST not in LADDER
    assert place_name(LOST) == "Lost"


def test_a_crm_stage_can_be_placed_on_any_stage_or_on_lost():
    assert [place_name(place) for place in PLACES] == [
        "Submitted",
        "Contact attempted",
        "Engaged",
        "Qualified",
        "Proposal",
        "Won",
        "Lost",
    ]
