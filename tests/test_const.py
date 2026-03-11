"""Tests for shared descriptor constants."""

from custom_components.fronius_tdc.const import (
    SCHEDULE_ACTIVE_SWITCH_DESCRIPTION,
    SCHEDULE_END_TIME_DESCRIPTION,
    SCHEDULE_POWER_NUMBER_DESCRIPTION,
    SCHEDULE_START_TIME_DESCRIPTION,
    SCHEDULE_TYPE_LABELS,
    SCHEDULE_TYPE_SELECT_DESCRIPTION,
    SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS,
)


def test_active_schedule_switch_description() -> None:
    """Test active schedule switch metadata."""
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.key == "active"
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.value_path == ("Active",)
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.setter_name == "async_set_active"
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.setter_value_parameter == "active"
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.entity_id_suffix == "active"
    assert SCHEDULE_ACTIVE_SWITCH_DESCRIPTION.unique_id_suffix == ""


def test_weekday_schedule_switch_descriptions() -> None:
    """Test weekday switch descriptor metadata is complete and ordered."""
    assert [
        description.name for description in SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS
    ] == [
        "Mon",
        "Tue",
        "Wed",
        "Thu",
        "Fri",
        "Sat",
        "Sun",
    ]
    assert SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS[0].setter_args == ("Mon",)
    assert SCHEDULE_WEEKDAY_SWITCH_DESCRIPTIONS[-1].value_path == (
        "Weekdays",
        "Sun",
    )


def test_schedule_power_number_description() -> None:
    """Test schedule power number metadata."""
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.value_path == ("Power",)
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.setter_name == "async_set_power"
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.setter_value_parameter == "power"
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.native_min_value == 0
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.native_max_value == 200000
    assert SCHEDULE_POWER_NUMBER_DESCRIPTION.native_step == 100


def test_schedule_type_select_description() -> None:
    """Test schedule type select mappings."""
    assert SCHEDULE_TYPE_SELECT_DESCRIPTION.value_path == ("ScheduleType",)
    assert SCHEDULE_TYPE_SELECT_DESCRIPTION.options == list(
        SCHEDULE_TYPE_LABELS.values()
    )
    assert (
        SCHEDULE_TYPE_SELECT_DESCRIPTION.option_to_value["Charge Max"] == "CHARGE_MAX"
    )
    assert (
        SCHEDULE_TYPE_SELECT_DESCRIPTION.value_to_option["DISCHARGE_MIN"]
        == "Discharge Min"
    )


def test_schedule_time_descriptions() -> None:
    """Test schedule start/end time descriptor metadata."""
    assert SCHEDULE_START_TIME_DESCRIPTION.value_path == ("TimeTable", "Start")
    assert SCHEDULE_START_TIME_DESCRIPTION.setter_name == "async_set_start_time"
    assert SCHEDULE_START_TIME_DESCRIPTION.setter_value_parameter == "start"
    assert SCHEDULE_END_TIME_DESCRIPTION.value_path == ("TimeTable", "End")
    assert SCHEDULE_END_TIME_DESCRIPTION.setter_name == "async_set_end_time"
    assert SCHEDULE_END_TIME_DESCRIPTION.setter_value_parameter == "end"
