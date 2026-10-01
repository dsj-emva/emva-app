"""Every number Emva shows carries the label of the Data source it came from."""

import pytest

from emva_api.records import DataSource


@pytest.mark.parametrize(
    ("source", "label"),
    [
        (DataSource.HAND_MADE_TEST, "on hand-made test data"),
        (DataSource.SIMULATED, "on simulated data"),
        (DataSource.PUBLIC, "on public data"),
        (DataSource.PRIVATE, "on the advertiser's private export"),
    ],
)
def test_each_data_source_has_the_label_its_numbers_carry(source: DataSource, label: str):
    assert source.label == label
