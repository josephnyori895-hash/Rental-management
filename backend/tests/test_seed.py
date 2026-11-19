"""
The demo seeder must not touch an operator that is not the demo.

`seed.py` replaces the previous demo business on every run, and deleting a
business cascades to everything it owns. The risk these tests pin down is that
the wipe stays scoped to `DEMO_SLUG`: another business, and the rows under it,
must survive a reseed.
"""

from __future__ import annotations

from sqlalchemy import func, select

from scripts.seed import DEMO_SLUG, seed
from tests.conftest import requires_db


async def _count(session, model, **where) -> int:
    statement = select(func.count()).select_from(model)
    for column, value in where.items():
        statement = statement.where(getattr(model, column) == value)
    return (await session.execute(statement)).scalar_one()


@requires_db
async def test_reseeding_the_demo_leaves_another_operator_alone(businesses, db_session):
    from app.models.billing import Invoice, Payment
    from app.models.business import Business, User
    from app.models.lease import Lease
    from app.models.property import Property

    first, second = businesses

    await seed(db_session)

    for seeded in (first, second):
        assert await _count(db_session, Business, id=seeded.business.id) == 1
        assert await _count(db_session, Property, id=seeded.property.id) == 1
        assert await _count(db_session, Lease, id=seeded.lease.id) == 1
        assert await _count(db_session, Invoice, id=seeded.invoice.id) == 1
        assert await _count(db_session, User, id=seeded.user.id) == 1
        assert await _count(db_session, Payment, id=seeded.unmatched_payment.id) == 1

    assert await _count(db_session, Business, slug=DEMO_SLUG) == 1


@requires_db
async def test_reseeding_replaces_the_demo_rather_than_stacking_copies(db_session):
    from app.models.business import Business
    from app.models.property import Property

    await seed(db_session)
    old_id = (
        await db_session.execute(select(Business.id).where(Business.slug == DEMO_SLUG))
    ).scalar_one()

    await seed(db_session)

    ids = (
        (
            await db_session.execute(
                select(Business.id).where(Business.slug == DEMO_SLUG)
            )
        )
        .scalars()
        .all()
    )
    assert len(ids) == 1
    assert ids[0] != old_id
    assert await _count(db_session, Property, business_id=old_id) == 0
    assert await _count(db_session, Property, business_id=ids[0]) == 2
