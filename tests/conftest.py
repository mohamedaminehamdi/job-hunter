import sys
from pathlib import Path

# `core/jobhunt.py` is the source of truth; the copies under
# plugins/*/skills/*/lib/ are generated from it by tools/sync.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

"""Fixtures shared across the suite.

There is no model to stub any more - Claude Code writes JSON files and Python
reads them, so every test here runs on real code with fixture input.
"""

import pytest

from job_hunter.jobs.models import Job
from job_hunter.profile.models import (
    Certification,
    Education,
    Language,
    Personal,
    Profile,
    Project,
    Role,
)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated JOB_HUNTER_HOME, set in the environment as well as returned."""
    directory = tmp_path / "home"
    directory.mkdir()
    monkeypatch.setenv("JOB_HUNTER_HOME", str(directory))
    monkeypatch.setenv("JOB_HUNTER_MODEL", "test/model")
    monkeypatch.setenv("JOB_HUNTER_API_KEY", "test-key")
    return directory


@pytest.fixture
def profile():
    return Profile(
        personal=Personal(name="Ada", surname="Lovelace", headline="Data Engineer",
                          email="ada@example.com", city="Berlin", country="Germany"),
        summary="Data engineer who builds pipelines that stay up.",
        skills=["Python", "SQL", "dbt"],
        experience=[
            Role(position="Data Engineer", company="Acme", start="2021", end="2024",
                 location="Berlin", skills=["Airflow"],
                 bullets=["Cut ETL runtime by 35% by rewriting the dbt models.",
                          "Mentored two junior analysts."]),
            Role(position="Analyst", company="Beta", start="2019", end="2021",
                 bullets=["Built the finance dashboards used by 40 people."]),
        ],
        education=[Education(level="MSc", institution="TU Berlin",
                             field_of_study="Computer Science", start="2017", end="2019")],
        projects=[Project(name="pipe", description="A tiny scheduler.", tech=["Python"])],
        certifications=[Certification(name="dbt Analytics Engineer", issuer="dbt Labs")],
        languages=[Language(name="English", level="fluent")],
    )


@pytest.fixture
def job():
    return Job(
        title="Senior Data Engineer", company="Zeta", location="Berlin",
        workplace="hybrid", employment_type="Full-time", language="en",
        brand_color="#7b2ff7", url="https://example.com/jobs/42",
        fetched_at="2026-09-07T10:00:00+00:00",
        description="Zeta runs a data platform for logistics customers. You would own "
                    "the ingestion pipelines and share the on-call rota for the platform.",
        requirements=["Strong Python", "Strong SQL", "Experience with dbt",
                      "3+ years in data engineering"],
        responsibilities=["Own the ingestion pipelines"],
        nice_to_have=["Kafka", "Terraform"],
        keywords=["Python", "SQL", "dbt", "Kafka"],
        source_text="Senior Data Engineer at Zeta ...",
    )
