from src.apply.match import FieldIn, match_field, norm_question


def _f(label: str, kind: str = "text", options: list[str] | None = None) -> FieldIn:
    return FieldIn(id="x", label=label, kind=kind, options=options or [])


DETAILS = {"first_name": "Jai", "email": "jai@example.com", "phone": "+91 99999 00000",
           "notice_period": "Immediate"}


def test_profile_field_by_synonym() -> None:
    assert match_field(_f("First Name *"), DETAILS, {}).value == "Jai"
    r = match_field(_f("Mobile number"), DETAILS, {})
    assert (r.value, r.confidence, r.source) == ("+91 99999 00000", "high", "profile")


def test_token_match_not_substring() -> None:
    # "email" must not match a question that only contains it inside another word
    assert match_field(_f("Emailing preference"), DETAILS, {}).value is None


def test_answer_bank_exact_and_fuzzy() -> None:
    bank = {norm_question("Are you willing to relocate?"): "Yes"}
    assert match_field(_f("Are you willing to relocate?"), {}, bank).confidence == "high"
    fuzzy = match_field(_f("Willing to relocate to Pune?"), {}, bank)
    assert (fuzzy.value, fuzzy.confidence) == ("Yes", "medium")


def test_select_option_is_chosen_from_options() -> None:
    bank = {norm_question("Do you need visa sponsorship?"): "no"}
    r = match_field(_f("Do you need visa sponsorship?", "select", ["Yes", "No"]), {}, bank)
    assert r.value == "No"


def test_unknown_is_low() -> None:
    r = match_field(_f("Favourite colour"), DETAILS, {})
    assert r.value is None and r.confidence == "low"


def test_norm_question_strips_noise() -> None:
    assert norm_question("  Notice Period (days) * ") == norm_question("notice period days")


def test_profile_beats_a_saved_answer_and_details_are_not_bank_questions() -> None:
    from src.apply.match import is_detail_question

    bank = {norm_question("Email"): "old@example.com"}
    assert match_field(_f("Email"), DETAILS, bank).value == "jai@example.com"
    assert is_detail_question("Phone number *") and not is_detail_question("Why Acme?")
