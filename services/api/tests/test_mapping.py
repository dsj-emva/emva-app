"""The Mapping and the rules that decide whether a person may confirm it.

Mistakes here are expensive (START_HERE section 3): a CRM stage on the wrong Stage, or a
personal-data column fed to the model, would corrupt everything trained afterwards.
"""

from datetime import UTC, datetime

import pytest

from emva_api.ladder import LOST, Stage
from emva_api.mapping import (
    ColumnKind,
    Files,
    LeadsColumns,
    Mapping,
    NotConfirmable,
    StageHistoryColumns,
    confirm,
    problems,
)

FILES = Files(
    leads_columns=["Lead ID", "Created", "Full Name", "Email", "Phone", "Trip Type", "Budget"],
    stage_history_columns=["Lead ID", "Stage", "Changed At", "Deal Value"],
    crm_stages=["New enquiry", "Call attempted", "Closed won", "Closed lost"],
)

COMPLETE = Mapping(
    leads=LeadsColumns(
        lead_id="Lead ID",
        submitted_at="Created",
        name="Full Name",
        email="Email",
        phone="Phone",
        inputs={"Trip Type": ColumnKind.CATEGORY, "Budget": ColumnKind.NUMBER},
    ),
    stage_history=StageHistoryColumns(
        lead_id="Lead ID", crm_stage="Stage", changed_at="Changed At", deal_value="Deal Value"
    ),
    crm_stages={
        "New enquiry": Stage.SUBMITTED,
        "Call attempted": Stage.CONTACT_ATTEMPTED,
        "Closed won": Stage.WON,
        "Closed lost": LOST,
    },
    typical_deal_size=8000,
)

AT = datetime(2026, 9, 14, 10, 0, tzinfo=UTC)


def with_leads(**columns) -> Mapping:
    return COMPLETE.model_copy(update={"leads": COMPLETE.leads.model_copy(update=columns)})


def with_stage_history(**columns) -> Mapping:
    history = COMPLETE.stage_history.model_copy(update=columns)
    return COMPLETE.model_copy(update={"stage_history": history})


def with_crm_stages(crm_stages) -> Mapping:
    return COMPLETE.model_copy(update={"crm_stages": crm_stages})


def with_typical_deal_size(size) -> Mapping:
    return COMPLETE.model_copy(update={"typical_deal_size": size})


def test_a_complete_mapping_has_no_problems():
    assert problems(COMPLETE, FILES) == []


def test_a_new_mapping_lists_everything_still_to_do():
    assert problems(Mapping(), FILES) == [
        "Mark the leads file's column holding the lead identifier.",
        "Mark the leads file's column holding the submission time.",
        "Mark the stage-history file's column holding the lead identifier.",
        "Mark the stage-history file's column holding the CRM stage.",
        "Mark the stage-history file's column holding when the change happened.",
        "Enter the typical deal size.",
    ]


# Required columns


@pytest.mark.parametrize(
    ("role", "reason"),
    [
        ("lead_id", "Mark the leads file's column holding the lead identifier."),
        ("submitted_at", "Mark the leads file's column holding the submission time."),
    ],
)
def test_each_required_leads_column_must_be_marked(role, reason):
    assert problems(with_leads(**{role: None}), FILES) == [reason]


@pytest.mark.parametrize(
    ("role", "reason"),
    [
        ("lead_id", "Mark the stage-history file's column holding the lead identifier."),
        ("changed_at", "Mark the stage-history file's column holding when the change happened."),
    ],
)
def test_each_required_stage_history_column_must_be_marked(role, reason):
    assert problems(with_stage_history(**{role: None}), FILES) == [reason]


def test_a_stage_history_file_without_deal_values_may_leave_that_column_unmarked():
    # Some CRMs do not export it; the typical deal size sizes leads in the meantime.
    assert problems(with_stage_history(deal_value=None), FILES) == []


def test_without_the_crm_stage_column_there_are_no_crm_stages_to_place_yet():
    unmarked = with_stage_history(crm_stage=None).model_copy(update={"crm_stages": {}})

    assert problems(unmarked, Files(FILES.leads_columns, FILES.stage_history_columns, [])) == [
        "Mark the stage-history file's column holding the CRM stage."
    ]


@pytest.mark.parametrize("role", ["name", "email", "phone"])
def test_a_leads_file_without_a_personal_data_column_may_leave_it_unmarked(role):
    assert problems(with_leads(**{role: None}), FILES) == []


def test_a_marked_column_must_be_in_the_file():
    # As when a file is uploaded again with different columns after the draft was made.
    files = Files(
        leads_columns=[name for name in FILES.leads_columns if name not in {"Phone", "Budget"}],
        stage_history_columns=["Lead ID", "Stage", "Changed At"],
        crm_stages=FILES.crm_stages,
    )

    assert problems(COMPLETE, files) == [
        "The leads file has no column “Phone”.",
        "The leads file has no column “Budget”.",
        "The stage-history file has no column “Deal Value”.",
    ]


# One column, one role


@pytest.mark.parametrize(
    ("column", "role"), [("Full Name", "name"), ("Email", "email"), ("Phone", "phone")]
)
def test_an_input_column_cannot_also_be_personal_data(column, role):
    inputs = {**COMPLETE.leads.inputs, column: ColumnKind.CATEGORY}

    assert problems(with_leads(inputs=inputs), FILES) == [
        f"The leads file's column “{column}” is marked as the lead's {role} "
        "and an input to the score; mark it as one only."
    ]


@pytest.mark.parametrize("role", ["name", "email", "phone"])
def test_personal_data_cannot_be_the_lead_identifier(role):
    assert problems(with_leads(lead_id="Lead ID", **{role: "Lead ID"}), FILES) == [
        f"The leads file's column “Lead ID” is marked as the lead identifier "
        f"and the lead's {role}; mark it as one only."
    ]


def test_a_column_marked_for_three_roles_is_named_once_with_all_three():
    mapping = with_leads(submitted_at="Email", email="Email", inputs={"Email": ColumnKind.CATEGORY})

    assert problems(mapping, FILES) == [
        "The leads file's column “Email” is marked as the submission time, the lead's email "
        "and an input to the score; mark it as one only."
    ]


def test_a_stage_history_column_holds_one_role_too():
    mapping = with_stage_history(changed_at="Stage")

    assert problems(mapping, FILES) == [
        "The stage-history file's column “Stage” is marked as the CRM stage "
        "and when the change happened; mark it as one only."
    ]


def test_the_same_column_name_may_be_used_once_in_each_file():
    # Both files name their lead identifier "Lead ID"; that is one role per file.
    assert COMPLETE.leads.lead_id == COMPLETE.stage_history.lead_id
    assert problems(COMPLETE, FILES) == []


def test_a_mapping_may_have_no_input_columns():
    assert problems(with_leads(inputs={}), FILES) == []


# CRM stages on the Canonical ladder


def test_every_crm_stage_must_be_placed():
    placed = {name: place for name, place in COMPLETE.crm_stages.items() if name != "Closed lost"}

    assert problems(with_crm_stages(placed), FILES) == [
        "Place the CRM stage “Closed lost” on the canonical ladder or on Lost."
    ]


def test_each_unplaced_crm_stage_is_named_in_the_order_the_file_lists_them():
    placed = {"Closed won": Stage.WON}

    assert problems(with_crm_stages(placed), FILES) == [
        "Place the CRM stage “New enquiry” on the canonical ladder or on Lost.",
        "Place the CRM stage “Call attempted” on the canonical ladder or on Lost.",
        "Place the CRM stage “Closed lost” on the canonical ladder or on Lost.",
    ]


def test_some_crm_stage_must_be_placed_on_won():
    placed = {**COMPLETE.crm_stages, "Closed won": Stage.PROPOSAL}

    assert problems(with_crm_stages(placed), FILES) == ["Place at least one CRM stage on Won."]


def test_several_crm_stages_may_share_a_stage():
    files = Files(
        FILES.leads_columns,
        FILES.stage_history_columns,
        ["Call attempted", "Left voicemail", "Closed won", "Closed lost", "Closed Lost"],
    )
    placed = {
        "Call attempted": Stage.CONTACT_ATTEMPTED,
        "Left voicemail": Stage.CONTACT_ATTEMPTED,
        "Closed won": Stage.WON,
        "Closed lost": LOST,
        "Closed Lost": LOST,
    }

    assert problems(with_crm_stages(placed), files) == []


def test_crm_stage_names_differing_only_in_case_are_placed_separately():
    files = Files(FILES.leads_columns, FILES.stage_history_columns, ["Closed won", "Closed Won"])

    assert problems(with_crm_stages({"Closed won": Stage.WON}), files) == [
        "Place the CRM stage “Closed Won” on the canonical ladder or on Lost."
    ]


def test_a_mapping_may_leave_stages_of_the_ladder_empty():
    files = Files(FILES.leads_columns, FILES.stage_history_columns, ["Quote sent", "Won"])
    placed = {"Quote sent": Stage.PROPOSAL, "Won": Stage.WON}

    assert problems(with_crm_stages(placed), files) == []


def test_a_placement_for_a_name_the_file_does_not_use_is_no_problem():
    # Left over from an earlier choice of CRM stage column; it is dropped on confirmation.
    placed = {**COMPLETE.crm_stages, "Itinerary revised": Stage.PROPOSAL}

    assert problems(with_crm_stages(placed), FILES) == []


# typical deal size


def test_the_typical_deal_size_must_be_entered():
    assert problems(with_typical_deal_size(None), FILES) == ["Enter the typical deal size."]


@pytest.mark.parametrize("size", [0, -1, -0.01])
def test_the_typical_deal_size_must_be_positive(size):
    assert problems(with_typical_deal_size(size), FILES) == [
        "The typical deal size must be more than zero."
    ]


def test_a_fractional_typical_deal_size_is_allowed():
    assert problems(with_typical_deal_size(0.5), FILES) == []


# Confirmation


def test_confirming_records_when_and_the_mapping_as_it_stood():
    confirmed = confirm(COMPLETE, FILES, AT)

    assert confirmed.confirmed_at == AT
    assert confirmed.mapping == COMPLETE


def test_confirming_drops_placements_for_names_the_file_does_not_use():
    placed = {**COMPLETE.crm_stages, "Itinerary revised": Stage.PROPOSAL}

    confirmed = confirm(with_crm_stages(placed), FILES, AT)

    assert confirmed.mapping.crm_stages == COMPLETE.crm_stages


def test_a_mapping_with_problems_cannot_be_confirmed():
    with pytest.raises(NotConfirmable) as refused:
        confirm(with_typical_deal_size(0), FILES, AT)

    assert refused.value.problems == ["The typical deal size must be more than zero."]
