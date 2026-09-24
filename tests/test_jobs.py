import jobhunt as fetch
import pytest
from jobhunt import FetchError, Job, build

FULL = {
    "title": "Data Engineer",
    "company": "Acme",
    "location": "Berlin",
    "workplace": "hybrid",
    "employment_type": "Full-time",
    "salary": "70-85k EUR",
    "description": "Build and own the pipelines that feed Acme's reporting stack. "
                   "You will work with the analytics team on ingestion and modelling, "
                   "and take part in on-call for the data platform.",
    "responsibilities": ["Own the ingestion pipelines", "Share on-call"],
    "requirements": ["3+ years with Python", "Strong SQL", "dbt or similar"],
    "nice_to_have": ["Kafka"],
    "keywords": ["Python", "SQL", "dbt", "Airflow"],
    "language": "en",
}


# --- normalise_url: people paste whatever they have ---

@pytest.mark.parametrize("given, expected", [
    ("https://boards.greenhouse.io/acme/jobs/1", "https://boards.greenhouse.io/acme/jobs/1"),
    ("  example.com/jobs/1  ", "https://example.com/jobs/1"),
    ("<https://example.com/jobs/1>", "https://example.com/jobs/1"),
    ("https://example.com/jobs/1.", "https://example.com/jobs/1"),
    ("http://example.com/x", "http://example.com/x"),
    # No dot in the host, but not a typo: this is how you fetch a page you are
    # serving yourself.
    ("http://localhost:8000/jobs/1", "http://localhost:8000/jobs/1"),
    ("http://127.0.0.1:8000/jobs/1", "http://127.0.0.1:8000/jobs/1"),
])
def test_urls_normalised(given, expected):
    assert fetch.normalise_url(given) == expected


@pytest.mark.parametrize("given, message", [
    ("", "No URL given"),
    ("   ", "No URL given"),
    ("file:///etc/passwd", "http and https"),
    ("javascript:alert(1)", "http and https"),
    ("mailto:jobs@acme.com", "http and https"),
    ("just some words", "does not look like"),
    ("notaurl", "does not look like"),
    ("http://notaurl:8000/jobs", "does not look like"),  # a port is not a host
])
def test_bad_urls_rejected(given, message):
    with pytest.raises(FetchError, match=message):
        fetch.normalise_url(given)


# --- _check: a page that loads is not necessarily a posting ---

def test_empty_page_tells_the_user_to_paste():
    with pytest.raises(FetchError, match="Paste the job description"):
        fetch.check_posting("https://example.com/j/1", "   ")


def test_login_wall_named_as_such():
    text = "Sign in to continue to your feed. " * 5
    with pytest.raises(FetchError, match="login or bot check"):
        fetch.check_posting("https://example.com/j/1", text)


def test_thin_page_reports_its_size():
    with pytest.raises(FetchError, match="characters came back"):
        fetch.check_posting("https://example.com/j/1", "Data Engineer. Apply now.")


def test_real_looking_page_passes():
    assert fetch.check_posting("https://example.com/j/1", "Data Engineer. " * 100) is None


# --- Job: shapes models actually return ---

def test_string_field_given_a_dict_keeps_the_numbers():
    job = build(Job, {"salary": {"min": 60000, "max": 80000, "currency": "EUR"}})
    assert job.salary == "min: 60000, max: 80000, currency: EUR"


def test_list_field_given_a_blob_splits_and_debullets():
    job = build(Job, {"requirements": "- Python\n* SQL\n1. dbt\n\n  \n- \n"})
    assert job.requirements == ["Python", "SQL", "dbt"]


def test_unknown_keys_dropped_and_overrides_win():
    job = build(Job, {"title": "Data Engineer", "url": "https://spam.example",
                      "confidence": 0.9},
                url="https://real.example/j/1")
    assert job.title == "Data Engineer"
    assert job.url == "https://real.example/j/1"  # we know this; the model guessed


def test_one_broken_field_does_not_lose_the_posting():
    job = build(Job, {"title": "Data Engineer", "requirements": object()})
    assert job.title == "Data Engineer"


def test_label_and_slug():
    job = Job(**FULL)
    assert job.label == "Data Engineer at Acme"
    assert job.slug == "acme-data-engineer"


def test_label_falls_back_through_what_is_known():
    assert Job(company="Acme").label == "Acme"
    assert Job(url="https://example.com/j/1").label == "https://example.com/j/1"
    assert Job().label == "Untitled job"


def test_slug_never_empty_and_is_filesystem_safe():
    assert Job(title="Sr. C++ Dev (m/w/d) — Remote!").slug == "sr-c-dev-m-w-d-remote"
    assert Job().slug == "job"


# --- missing(): is there enough here to tailor against? ---

def test_full_posting_is_usable():
    assert Job(**FULL).missing() is None
    assert Job(**FULL).is_usable


def test_posting_with_no_description_at_all():
    assert "no description to work from" in (Job(title="Data Engineer").missing() or "")


def test_fragment_posting_flagged():
    job = Job(title="Data Engineer", description="We are hiring.", requirements=["Python"])
    assert "fragment" in (job.missing() or "")


def test_requirements_alone_are_enough():
    job = Job(title="Data Engineer", requirements=["Python", "SQL", "dbt"])
    assert job.is_usable  # a bulleted posting with no prose still tailors fine


# --- brief(): the one way a job enters a prompt ---

def test_brief_includes_every_stated_fact():
    brief = Job(**FULL).brief()
    for expected in ("Data Engineer", "Acme", "Berlin - hybrid", "70-85k EUR",
                     "- Strong SQL", "- Kafka", "Keywords: Python, SQL, dbt, Airflow"):
        assert expected in brief


def test_brief_omits_empty_sections():
    brief = Job(title="Data Engineer", requirements=["Python"]).brief()
    assert "Nice to have" not in brief
    assert "Salary" not in brief
    assert "Company" not in brief


def test_brief_of_empty_job_is_empty_not_a_skeleton():
    assert Job().brief() == ""


# --- trim(): postings run long ---

def test_short_text_untouched():
    assert fetch.trim("Data Engineer at Acme") == "Data Engineer at Acme"


def test_long_text_keeps_both_ends():
    text = "TITLE Data Engineer\n" + ("boilerplate " * 5000) + "\nREQUIRED Python"
    trimmed = fetch.trim(text)
    assert len(trimmed) < len(text)
    assert "TITLE Data Engineer" in trimmed   # the role is at the top
    assert "REQUIRED Python" in trimmed       # the requirements are at the bottom
    assert "characters omitted" in trimmed


# --- html_to_text: what replaced innerText ---------------------------------

def test_whitespace_between_inline_tags_survives():
    """`<bdi>$405,000</bdi> <bdi>USD</bdi>` - the space is all that separates them.

    Found by scraping a real posting both ways: dropping whitespace-only data
    because it strips to nothing ran the salary into its currency.
    """
    body, _, _ = fetch.html_to_text(
        "<p><bdi>$320,000</bdi> - <bdi>$405,000</bdi> <bdi>USD</bdi></p>")
    assert body == "$320,000 - $405,000 USD"


def test_a_bulleted_list_keeps_one_requirement_per_line():
    body, _, _ = fetch.html_to_text("<ul><li>Strong Python</li><li>Strong SQL</li></ul>")
    assert body.splitlines() == ["Strong Python", "Strong SQL"]


def test_page_furniture_is_dropped():
    body, _, _ = fetch.html_to_text(
        "<nav>Home Jobs</nav><script>track()</script><style>a{}</style>"
        "<main>Data Engineer</main><footer>Privacy</footer>")
    assert body == "Data Engineer"


def test_the_title_and_theme_colour_are_read_not_guessed():
    _, title, brand = fetch.html_to_text(
        '<head><title>Data Engineer - Acme</title>'
        '<meta name="theme-color" content="#7B2FF7"></head><body>x</body>')
    assert title == "Data Engineer - Acme"
    assert brand == "#7b2ff7"


def test_a_theme_colour_that_is_not_a_colour_is_dropped():
    """It reaches a stylesheet, so it is validated at the door."""
    _, _, brand = fetch.html_to_text('<meta name="theme-color" content="red;}body{">')
    assert brand == ""


def test_entities_are_decoded():
    body, _, _ = fetch.html_to_text("<p>R&amp;D at Zeta &mdash; 35&#37; faster</p>")
    assert body == "R&D at Zeta — 35% faster"


def test_a_page_that_never_closes_is_still_read():
    body, _, _ = fetch.html_to_text("<html><body><p>Data Engineer at Acme")
    assert "Data Engineer at Acme" in body
