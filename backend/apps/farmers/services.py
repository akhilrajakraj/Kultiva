"""Farmer-domain direct trade services."""
from __future__ import annotations

from backend.apps.trade.services import TradeService
from backend.core.legacy.models import DirectTradeProposal, User


class FarmerTradeService:
    """Farmer-facing facade over the canonical direct-trade lifecycle."""

    @classmethod
    def respond_to_proposal(cls, *, farmer: User, proposal_id: int, action: str) -> DirectTradeProposal:
        return TradeService.farmer_respond(farmer=farmer, proposal_id=proposal_id, action=action)

    @classmethod
    def cancel_proposal(cls, *, farmer: User, proposal_id: int) -> DirectTradeProposal:
        return TradeService.cancel_farmer_proposal(farmer=farmer, proposal_id=proposal_id)

    @classmethod
    def schedule_pickup(cls, *, farmer: User, proposal_id: int, pickup_date) -> DirectTradeProposal:
        return TradeService.schedule_pickup(farmer=farmer, proposal_id=proposal_id, pickup_date=pickup_date)

    @classmethod
    def proposals(cls, *, farmer: User):
        return TradeService.get_farmer_proposals(farmer=farmer)


__all__ = ["FarmerTradeService"]
