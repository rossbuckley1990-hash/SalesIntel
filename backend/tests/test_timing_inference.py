from datetime import date

from app.intelligence.timing_inference import clue_window, convergence, infer_timing, parse_when

TODAY = date(2026, 11, 4)


def test_dates_keep_their_precision():
    assert parse_when("2014").precision == "year" and parse_when("2014-03").precision == "month"
    assert parse_when("2014-03-09").day == date(2014, 3, 9)
    assert parse_when("not a date") is None and parse_when("1820") is None


def test_an_old_fire_alarm_opens_a_replacement_window():
    window = clue_window({"kind": "system_installed", "date": "2013", "system_family": "fire_alarm", "basis": "stated"}, TODAY)
    assert window["start"] == date(2023, 7, 1) and window["end"] == date(2028, 7, 1) and window["polarity"] == 1
    assert window["strength"] == "moderate"  # a stated year, not a stated day


def test_a_supplier_appointed_this_year_locks_the_account():
    result = infer_timing([{"kind": "supplier_appointed", "date": "2026-05-01", "basis": "stated"}], TODAY)
    assert result["phase"] == "not_yet" and result["light"] == "red" and result["blocked_until"] == date(2027, 5, 1)


def test_an_incident_overrides_a_recent_appointment():
    result = infer_timing([{"kind": "supplier_appointed", "date": "2026-05-01", "basis": "stated"},
                           {"kind": "incident", "date": "2026-10-20", "basis": "stated"}], TODAY)
    assert result["phase"] == "engage_now" and result["blocked_until"] is None


def test_two_weak_clues_that_converge_mean_engage_now():
    clues = [{"kind": "building_completed", "date": "2016", "basis": "inferred"},
             {"kind": "leadership_change", "date": "2026-09", "basis": "inferred"}]
    result = infer_timing(clues, TODAY)
    assert result["phase"] == "engage_now" and result["convergence"]["kinds"] == ["building_completed", "leadership_change"]
    assert "converge" in result["reasons"][0]


def test_a_single_weak_clue_only_means_prepare():
    result = infer_timing([{"kind": "building_completed", "date": "2016", "basis": "inferred"}], TODAY)
    assert result["phase"] == "prepare" and result["light"] == "amber"


def test_budget_window_rolls_to_the_next_year_end():
    window = clue_window({"kind": "financial_year_end", "date": "2020-03-31", "basis": "stated"}, TODAY)
    assert window["start"] == date(2026, 9, 28) and window["end"] == date(2027, 1, 28)


def test_future_windows_say_when_to_prepare_and_nothing_means_unknown():
    opening = infer_timing([{"kind": "site_opening", "date": "2027-09-01", "basis": "stated"}], TODAY)
    assert opening["phase"] == "engage_now" and opening["window"]["end"] == date(2027, 6, 1)
    soon = infer_timing([{"kind": "supplier_appointed", "date": "2024-11-01", "basis": "stated"}], TODAY)
    assert soon["phase"] == "prepare" and soon["window"]["start"] == date(2027, 5, 1)
    later = infer_timing([{"kind": "supplier_appointed", "date": "2025-06-01", "basis": "stated"}], TODAY)
    assert later["phase"] == "not_yet" and later["window"]["start"] == date(2027, 12, 1)
    assert infer_timing([], TODAY)["phase"] == "unknown"
    assert infer_timing([{"kind": "made_up", "date": "2020"}], TODAY)["phase"] == "unknown"


def test_convergence_ignores_closing_clues():
    windows = [clue_window({"kind": "supplier_appointed", "date": "2026-06-01", "basis": "stated"}, TODAY),
               clue_window({"kind": "leadership_change", "date": "2026-10-01", "basis": "stated"}, TODAY)]
    assert convergence(windows, TODAY) is None


def test_a_generic_inferred_deadline_is_context_not_evidence():
    pstn = {"kind": "regulatory_deadline", "date": "2027-01-31", "basis": "inferred", "detail": "PSTN switch-off"}
    opening = {"kind": "site_opening", "date": "2027", "basis": "stated"}
    alone = infer_timing([pstn], TODAY)
    assert alone["phase"] == "unknown" and any(r.startswith("Context: PSTN") for r in alone["reasons"])
    both = infer_timing([pstn, opening], TODAY)
    assert both["convergence"] is None and both["phase"] == "engage_now"
    stated = infer_timing([{**pstn, "basis": "stated"}, opening], TODAY)
    assert stated["convergence"]["kinds"] == ["regulatory_deadline", "site_opening"]
