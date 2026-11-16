from datetime import date

from app.intelligence.timing_inference import clue_window, convergence, infer_timing, parse_when, reclassify

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


def test_a_building_contractor_is_not_a_fire_and_security_supplier():
    """Live research chat, 16 November 2026: two new sites opening in 2027 said "Not yet" because the firm building them
    was filed as a newly appointed supplier. The wording below is what the research stored, with fictional names."""
    builds = [{"kind": "supplier_appointed", "date": "2026-02", "basis": "stated", "detail": "Example Construction appointed; build began February 2026"},
              {"kind": "supplier_appointed", "date": "2026-09", "basis": "stated", "detail": "Example Developments leading build from September 2026"}]
    for clue, opens in zip(builds, ("2027-04", "2027-10")):
        assert reclassify(clue)["kind"] == "contractor_appointed" and reclassify(clue)["filed_as"] == "supplier_appointed"
        t = infer_timing([{"kind": "site_opening", "date": opens, "basis": "stated", "detail": "Due to open in 2027"}, clue], date(2026, 11, 16))
        assert t["phase"] == "engage_now" and t["blocked_until"] is None
        assert t["reasons"][0].startswith("New site opening: fire and security for a new site is usually procured three to twelve months before it opens")
        assert t["reasons"][1] == ("Building contractor appointed: a contractor appointed to build or fit out a site is not its fire and security "
                                   "maintenance supplier, so it does not hold contact back. Ask who installs those systems under the build and who "
                                   "will maintain them after handover.")
        assert [n["kind"] for n in t["notes"]] == ["contractor_appointed"] and all(w["kind"] != "supplier_appointed" for w in t["clues"])


def test_a_takeover_filed_as_a_supplier_is_an_acquisition():
    """Two saved leads said "A supplier was appointed recently" about a change of owner (fictional names, stored wording)."""
    for detail in ("Acquisition reported. Integration of Example Communities' operations is under way.", "Takeover completed and integration began."):
        clue = {"kind": "supplier_appointed", "date": "2026-03", "basis": "stated", "detail": detail}
        assert reclassify(clue)["kind"] == "acquisition"
        t = infer_timing([clue], date(2026, 11, 16))
        assert t["phase"] == "unknown" and t["blocked_until"] is None and not any("supplier was appointed" in r for r in t["reasons"])
        assert t["reasons"][0].startswith("Acquisition: a change of owner is a reason to ask whether inherited maintenance contracts")


def test_a_supplier_that_maintains_systems_still_holds_contact_back():
    """Only a builder or a takeover is reread: a maintenance, monitoring, guarding or facilities supplier keeps its first-year lock."""
    for detail in ("Example Fire Ltd appointed to maintain the fire alarms across the estate",
                   "Example Fire Ltd appointed after a group purchasing exercise",
                   "Security guarding provider changed to Example Shield.",
                   "Example Security appointed as security contractor for the new site",  # no building words
                   "Example Construction appointed under a construction and maintenance framework",
                   "Example FM appointed for facilities management at the developer's new offices",
                   "Example Alarms took over alarm monitoring"):
        clue = {"kind": "supplier_appointed", "date": "2026-05-01", "basis": "stated", "detail": detail}
        assert reclassify(clue) == clue, detail
        assert infer_timing([clue], TODAY)["phase"] == "not_yet", detail
