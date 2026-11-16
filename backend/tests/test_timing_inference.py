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
    assert opening["phase"] == "engage_now" and opening["window"]["end"] == date(2028, 3, 1)  # six months after it opens
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
        assert t["reasons"][0].startswith("New site opening: fire and security for a new site is usually installed in the year before it opens")
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


NOW = date(2026, 11, 16)
LATE = ("New site opening: installation is usually already bought this close to opening, but maintenance must be in place from handover, and "
        "BS 5839-1 recommends servicing fire alarms at least every six months. Ask whether the site will join an existing estate-wide maintenance "
        "contract or be let locally.")


def opening(when: str, basis: str = "stated", detail: str = "Due to open.") -> dict:
    return infer_timing([{"kind": "site_opening", "date": when, "basis": basis, "detail": detail}], NOW)


def test_a_new_site_stays_open_for_maintenance_until_six_months_after_it_opens():
    """Live, 16 November 2026: a hotel opening in January 2027 said "Timing unknown" because the installation window had closed,
    though its maintenance was still to be arranged. Cases below are the live ones with fictional wording."""
    soon = opening("2027-01")  # two months away: installation is probably bought, maintenance is the open question
    assert soon["phase"] == "engage_now" and soon["window"] == {"start": NOW, "end": date(2027, 7, 15)}
    assert soon["reasons"][0] == f"{LATE[:-1]}. Window open until July 2027."
    opened = opening("2026-08")  # went live three months ago
    assert opened["phase"] == "engage_now" and opened["reasons"][0].startswith(LATE[:-1]) and "February 2027" in opened["reasons"][0]
    assert opening("2026-04")["phase"] == "unknown"  # seven months ago: the first service is past, the window has closed
    early = opening("2027-09")  # ten months away: installation is still being decided
    assert early["phase"] == "engage_now" and early["reasons"][0] == ("New site opening: fire and security for a new site is usually installed in the year "
                                                                       "before it opens, and its maintenance arranged by handover. Window open until March 2028.")
    later = opening("2028-06")  # nineteen months away
    assert later["phase"] == "prepare" and later["reasons"][0].endswith("Window opens June 2027.") and "installed in the year before it opens" in later["reasons"][0]
    assert opening("2026-09", basis="inferred")["phase"] == "prepare"  # an opening nobody states is still only a reason to confirm


def test_a_completion_still_to_come_is_an_opening_not_the_age_of_systems():
    """Live: a distribution centre "completion early 2027" was read as systems installed in 2027, due for replacement from 2035."""
    t = infer_timing([{"kind": "building_completed", "date": "2027-02", "basis": "stated", "detail": "Completion early 2027"}], NOW)
    assert t["phase"] == "engage_now" and t["reasons"][0].startswith(LATE[:-1]) and not any("Replacement" in r or "2035" in r for r in t["reasons"])
    assert [w["kind"] for w in t["clues"]] == ["site_opening"] and t["clues"][0]["label"] == "New site opening"
    built = infer_timing([{"kind": "building_completed", "date": "2024", "basis": "stated"}], NOW)  # a completion that has happened keeps its meaning
    assert built["phase"] == "unknown" and built["reasons"][0].startswith("Replacement, a separate sale:")


def test_sites_transferring_to_a_new_operator_are_a_change_of_owner():
    """Live: six sites due to transfer to a new operator were filed as a site opening (fictional names, stored wording)."""
    transfer = {"kind": "site_opening", "date": "2026-09", "basis": "stated",
                "detail": "The six sites, including Example Town, were due to transfer to Example Logistics in September 2026."}
    assert reclassify(transfer)["kind"] == "acquisition"
    t = infer_timing([transfer], NOW)
    assert t["phase"] == "unknown" and t["reasons"][0].startswith("Acquisition: a change of owner is a reason to ask")
    moving = {"kind": "site_opening", "date": "2027-05", "basis": "stated", "detail": "Operations transfer to the new site in May 2027."}
    assert reclassify(moving)["kind"] == "site_opening"  # a move into a new building is still an opening
