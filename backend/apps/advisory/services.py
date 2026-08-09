"""Advisory service boundary over the existing crop advisory database."""
from Kultiva.advisory_db import CROP_ADVISORY_DB


def get_crop_advisory(crop_name):
    db = CROP_ADVISORY_DB[0] if isinstance(CROP_ADVISORY_DB, tuple) else CROP_ADVISORY_DB
    return db.get(str(crop_name).strip().title())


__all__ = ['CROP_ADVISORY_DB', 'get_crop_advisory']
