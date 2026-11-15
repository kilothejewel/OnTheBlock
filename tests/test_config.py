"""Settings: how the database URL in OTB_DATABASE_URL is read."""

import pytest

from app.core.config import Settings


def database_url(url):
    """The database URL the app uses when OTB_DATABASE_URL is `url`."""
    return Settings(DATABASE_URL=url, SECRET_KEY="test-secret-key-not-for-production").DATABASE_URL


@pytest.mark.parametrize("url", [
    "postgres://sam:pw@db.example.com/otb",
    "postgresql://sam:pw@db.example.com/otb",
])
def test_a_postgres_url_without_a_driver_uses_psycopg2(url):
    """
    The driver in requirements.txt, whatever SQLAlchemy's default is: hosts
    hand out "postgres://", and "postgresql://" means psycopg 3 from SQLAlchemy 2.1.
    """
    assert database_url(url) == "postgresql+psycopg2://sam:pw@db.example.com/otb"


def test_a_postgres_url_keeps_its_query_string():
    """Neon's URLs carry options such as sslmode."""
    assert (
        database_url("postgresql://sam:pw@db.example.com/otb?sslmode=require")
        == "postgresql+psycopg2://sam:pw@db.example.com/otb?sslmode=require"
    )


@pytest.mark.parametrize("url", [
    "postgresql+psycopg2://sam:pw@db.example.com/otb",
    "postgresql+psycopg://sam:pw@db.example.com/otb",
    "sqlite:///./ontheblock.db",
    "sqlite://",
])
def test_a_url_that_names_its_driver_or_another_database_is_left_alone(url):
    assert database_url(url) == url
