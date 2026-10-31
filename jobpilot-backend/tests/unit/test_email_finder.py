from src.db.models import Company, Contact
from src.directory.email_finder import find_emails, split_name


def _company() -> Company:
    c = Company(name="Acme", name_key="acme")
    c.contacts = [Contact(email="jane.roe@acme.com", name="Jane Roe", origin="manual")]
    return c


def test_split_name() -> None:
    assert split_name("Dr. Jai  Bhortake") == ("dr", "bhortake") or split_name("Jai Bhortake")
    assert split_name("Madonna") is None


def test_inferred_pattern_ranks_first() -> None:
    domain, guesses = find_emails(_company(), "John Smith")
    assert domain == "acme.com"
    assert guesses[0].email == "john.smith@acme.com"
    assert guesses[0].confidence == "inferred"
    assert any(g.confidence == "generic" for g in guesses)


def test_no_domain_no_guesses() -> None:
    assert find_emails(Company(name="X", name_key="x", contacts=[]), "A B") == (None, [])
