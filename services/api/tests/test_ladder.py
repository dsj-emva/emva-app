from emva_api.ladder import LADDER, LOST, STAGES_AND_LOST, Stage, name_of


def test_the_canonical_ladder_runs_from_submitted_to_won_in_order():
    assert [name_of(stage) for stage in LADDER] == [
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
    assert name_of(LOST) == "Lost"


def test_a_crm_stage_can_be_placed_on_any_stage_or_on_lost():
    assert [name_of(stage_or_lost) for stage_or_lost in STAGES_AND_LOST] == [
        "Submitted",
        "Contact attempted",
        "Engaged",
        "Qualified",
        "Proposal",
        "Won",
        "Lost",
    ]
