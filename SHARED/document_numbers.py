"""Atomic increments in the caller's transaction; no counts, scans or max+1."""
from SHARED.models import DocumentCounter
from sqlalchemy import update


def next_document_number(db, scope, prefix, period, width):
    if scope not in {"cartridge", "repair"}:
        raise ValueError("Unknown document scope")
    value = db.execute(
        update(DocumentCounter).where(DocumentCounter.scope == scope)
        .values(last_value=DocumentCounter.last_value + 1)
        .returning(DocumentCounter.last_value)
    ).scalar_one_or_none()
    if value is None:
        raise RuntimeError("Document counter missing; apply Alembic migrations before startup")
    number = f"{prefix}{period}-{value:0{width}d}"
    if len(number) > 100:
        raise ValueError("Document prefix is too long")
    return number
