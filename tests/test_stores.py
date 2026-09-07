"""Persistence: jobs and generated documents as YAML on disk.

Same rule as the profile store: a file that cannot be read is missing, not fatal.
"""

from job_hunter.generate import cover_letter, cv
from job_hunter.generate import store as doc_store
from job_hunter.generate.answers import Answer
from job_hunter.jobs import store as job_store

CV_REPLY = {"summary": "Engineer.", "roles": [{"index": 0}], "projects": [], "skills": ["Python"]}


def test_a_job_round_trips(home, job):
    path = job_store.save(job, home)
    assert path.name == "zeta-senior-data-engineer.yaml"

    loaded = job_store.load(job.slug, home)
    assert loaded.title == job.title
    assert loaded.requirements == job.requirements
    assert loaded.brand_color == "#7b2ff7"
    assert loaded.source_text == job.source_text  # kept for review


def test_missing_and_broken_jobs_read_as_none(home):
    assert job_store.load("ghost", home) is None
    broken = job_store.jobs_dir(home)
    broken.mkdir(parents=True, exist_ok=True)
    (broken / "bad.yaml").write_text("{[not yaml", encoding="utf-8")
    assert job_store.load("bad", home) is None
    assert job_store.all_jobs(home) == []


def test_jobs_list_newest_first(home, job):
    job_store.save(job.model_copy(update={"company": "Older",
                                          "fetched_at": "2020-01-01T00:00:00+00:00"}), home)
    job_store.save(job.model_copy(update={"company": "Newer",
                                          "fetched_at": "2030-01-01T00:00:00+00:00"}), home)
    assert [j.company for j in job_store.all_jobs(home)] == ["Newer", "Older"]


def test_saving_the_same_job_twice_overwrites(home, job):
    job_store.save(job, home)
    job_store.save(job.model_copy(update={"salary": "100k"}), home)
    assert len(job_store.all_jobs(home)) == 1
    assert job_store.load(job.slug, home).salary == "100k"


def test_delete(home, job):
    job_store.save(job, home)
    assert job_store.delete(job.slug, home) is True
    assert job_store.delete(job.slug, home) is False


def test_documents_round_trip(home, profile, job):
    document = cv.assemble(profile, job, CV_REPLY)
    doc_store.save(document, job.slug, "cv", home)
    loaded = doc_store.load(job.slug, "cv", home)

    assert isinstance(loaded, cv.TailoredCV)
    assert loaded.summary == document.summary
    assert loaded.job_label == document.job_label
    assert [r.company for r in loaded.experience] == ["Acme"]


def test_letters_round_trip_with_their_issues(home, profile, job):
    letter = cover_letter.assemble(profile, job, {
        "greeting": "Dear Hiring Team,",
        "paragraphs": ["I have run Kubernetes for years."],
        "closing": "Kind regards,"})
    doc_store.save(letter, job.slug, "letter", home)
    loaded = doc_store.load(job.slug, "letter", home)

    assert isinstance(loaded, cover_letter.CoverLetter)
    assert loaded.issues  # the guard's findings survive the round trip
    assert loaded.body == letter.body


def test_unknown_kind_and_missing_document_read_as_none(home, job):
    assert doc_store.load(job.slug, "cv", home) is None
    assert doc_store.load(job.slug, "nonsense", home) is None


def test_answers_accumulate_and_deduplicate(home, job):
    first = Answer(question="Why us?", text="Because of the pipelines.")
    second = Answer(question="Notice period?", text="Two months.")
    doc_store.add_answer(first, job.slug, home)
    doc_store.add_answer(second, job.slug, home)
    assert [a.question for a in doc_store.load_answers(job.slug, home)] == \
        ["Why us?", "Notice period?"]

    doc_store.add_answer(Answer(question="Why us?", text="Rewritten."), job.slug, home)
    kept = doc_store.load_answers(job.slug, home)
    assert len(kept) == 2
    assert kept[-1].text == "Rewritten."  # the newest answer to that question


def test_answers_of_an_unknown_job_are_empty(home):
    assert doc_store.load_answers("ghost", home) == []
