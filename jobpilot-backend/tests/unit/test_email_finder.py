from src.db.models import Company, Contact
from src.directory.email_finder import Corpus, find_emails, split_name
from src.directory.email_import import match_company, parse_pasted, registrable_label


def _contacts(rows: list[tuple[str, str | None]]) -> list[Contact]:
    return [Contact(email=e, name=n, origin="verified") for e, n in rows]


ROWS = [
    ("jennifer.kowalski@acme.com", None), ("michael.thompson@acme.com", None),
    ("priyanka.deshpande@acme.com", None),
    ("pkrishnappa@pure.com", None), ("ppaulm@pure.com", None), ("pdembla@pure.com", None),
    ("shruti_girde@under.com", None), ("mallika_sinha@under.com", None),
    ("careers@acme.com", None), ("careers@pure.com", None),
]


def test_split_name() -> None:
    assert split_name("Jai Bhortake") == ("jai", "bhortake")
    assert split_name("Madonna") is None


def test_shape_is_learned_per_domain() -> None:
    contacts = _contacts(ROWS)
    corpus = Corpus.build(contacts)
    assert corpus.domain_shapes("acme.com").most_common(1)[0][0] == "first.last"
    assert corpus.domain_shapes("pure.com").most_common(1)[0][0] == "flast"
    assert corpus.domain_shapes("under.com").most_common(1)[0][0] == "first_last"
    assert "careers" in corpus.role_tokens


def test_guesses_follow_the_domain() -> None:
    contacts = _contacts(ROWS)
    co = Company(name="Pure", name_key="pure", contacts=contacts[4:7])
    domain, guesses = find_emails(co, "Sam Smith", contacts)
    assert domain == "pure.com"
    assert guesses[0].email == "ssmith@pure.com" and guesses[0].confidence == "learned"
    assert any(g.email == "careers@pure.com" for g in guesses)


def test_new_data_changes_the_answer() -> None:
    contacts = _contacts(ROWS[:4])
    co = Company(name="Acme", name_key="acme", contacts=contacts)
    assert find_emails(co, "Sam Smith", contacts)[1][0].email == "sam.smith@acme.com"


def test_no_domain_no_guesses() -> None:
    assert find_emails(Company(name="X", name_key="x", contacts=[]), "A B", []) == (None, [])


def test_parse_pasted_handles_mail_client_format() -> None:
    text = (
        '"a@x.com" <a@x.com>, Kavita Bisht <kb@alpha.com>, "SHENDE, SHRADDHA" <s@siemens.com>, '
        "plain@y.org, 𝐧𝐞𝐡𝐚.𝐧𝐞𝐠𝐢@u.com, A@X.com"
    )
    got = {p.email: p.name for p in parse_pasted(text)}
    assert got["a@x.com"] is None
    assert got["kb@alpha.com"] == "Kavita Bisht"
    assert got["s@siemens.com"] == "Shraddha Shende"
    assert "neha.negi@u.com" in got
    assert len(got) == 5


def test_company_matching_from_domain() -> None:
    cos = [Company(name=n, name_key=n.lower()) for n in ("palo alto", "HP", "Citibank", "HCL")]
    assert registrable_label("sisc.in.sony.com.sg") == "sony"
    assert match_company(registrable_label("paloaltonetworks.com"), cos) is cos[0]
    assert match_company(registrable_label("india.hp.com"), cos) is cos[1]
    assert match_company(registrable_label("citi.com"), cos) is cos[2]
    assert match_company(registrable_label("hcl-software.com"), cos) is cos[3]
    assert match_company("rakuten", cos) is None
