"""
Billing & payments API — per api-spec.md section 6.

Endpoints:
  GET    /api/v1/billing/account
  POST   /api/v1/billing/deposit
  GET    /api/v1/billing/transactions
  GET    /api/v1/billing/payouts
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.billing import BillingService
from ..database import async_session
from ..schemas import BillingDepositRequest, BillingAccountResponse

router = APIRouter()

billing_service = BillingService()


async def get_db() -> AsyncSession:
    """Yield an async database session."""
    async with async_session() as db:
        yield db


@router.get("/billing/account", response_model=BillingAccountResponse)
async def get_account(
    user_id: str = Query(..., description="User ID to look up"),
    db: AsyncSession = Depends(get_db),
):
    """Get billing account balance and summary for a user."""
    account = await billing_service.get_account(db, user_id)
    return account


@router.post("/billing/deposit")
async def deposit(
    body: BillingDepositRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add funds to a user account.

    For MVP, payment is mocked — no real Stripe integration.
    The payment_method field is accepted for future compatibility.
    """
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    account = await billing_service.deposit(
        db,
        user_id=body.user_id,
        amount=body.amount,
        payment_method=body.payment_method,
    )
    return account


@router.get("/billing/transactions")
async def list_transactions(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List billing transactions for a user."""
    return await billing_service.get_transactions(db, user_id, limit=limit)


@router.get("/billing/payouts")
async def get_payouts(
    agent_id: str = Query(..., description="Agent ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get agent provider payout history."""
    return await billing_service.get_payouts(db, agent_id)
