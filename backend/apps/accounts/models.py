"""Account-domain compatibility exports.

Canonical ownership remains in the legacy migration app until the database
migration is completed and verified.
"""
from backend.core.legacy.models import User, Address

__all__ = ['User', 'Address']
