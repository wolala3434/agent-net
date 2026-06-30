"""
Billing Service — real-time charging, balance management, agent payouts.

Per trust-and-pricing.md:
  - Platform takes 15% commission
  - Agent free trial: 100 calls, then +50 if rating 2.5-3.9
  - User signup credit: $5.00
  - Agent monthly payout: 1st of month, $50 minimum
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import (
    Agent,
    BillingAccount,
    BillingTransaction,
    AgentPayout,
)
from ..constants import DEFAULT_USER_ID, DEFAULT_FREE_QUOTA


class FreeSource(str, Enum):
    agent_trial = "agent_trial"
    user_credit = "user_credit"


class PricingModel(str, Enum):
    per_call = "per_call"
    per_minute = "per_minute"
    per_token = "per_token"


@dataclass
class BillingResult:
    """Result of a charge calculation."""
    user_paid: float         # total charged to user
    agent_earning: float     # agent's share
    platform_fee: float      # platform's cut
    is_free: bool
    free_source: str | None  # 'agent_trial' | 'user_credit' | None


class BillingService:
    """
    Handles charge calculation, account management, and payout aggregation.

    Two-phase trial model (per trust-and-pricing.md):
      Phase 1: First 100 calls free
      Phase 2: If rating 2.5-3.9 after phase 1 → +50 free calls
    """

    def __init__(self, platform_fee_rate: float | None = None):
        self.platform_fee_rate = platform_fee_rate or settings.platform_fee_rate

    # ------------------------------------------------------------------
    # Charge calculation (pure logic, no DB)
    # ------------------------------------------------------------------

    def calculate_charge(
        self,
        agent: dict[str, Any],
        user_account: dict[str, Any] | None,
        units: float = 1.0,
    ) -> BillingResult:
        """
        Compute what the user pays, what the agent earns, and the platform cut.

        Priority: agent_trial > user_credit > normal charge.
        """
        unit_price = agent.get("unit_price", 0.0)

        # Check agent trial quota
        free_used = agent.get("free_quota_used", 0)
        free_total = agent.get("free_quota_total", DEFAULT_FREE_QUOTA)
        if free_used < free_total:
            return BillingResult(
                user_paid=0.0,
                agent_earning=0.0,
                platform_fee=0.0,
                is_free=True,
                free_source=FreeSource.agent_trial.value,
            )

        # Check user signup credit
        if user_account and user_account.get("free_credit", 0) > 0:
            charge = unit_price * units
            fee = round(charge * self.platform_fee_rate, 4)
            return BillingResult(
                user_paid=0.0,
                agent_earning=charge,  # platform pays agent during user credit period
                platform_fee=0.0,
                is_free=True,
                free_source=FreeSource.user_credit.value,
            )

        # Normal charge
        charge = round(unit_price * units, 4)
        fee = round(charge * self.platform_fee_rate, 4)
        return BillingResult(
            user_paid=round(charge + fee, 4),
            agent_earning=charge,
            platform_fee=fee,
            is_free=False,
            free_source=None,
        )

    def get_extra_trial_quota(self, avg_rating: float) -> int:
        """
        Phase 2 trial extension: if rating 2.5-3.9 after phase 1,
        grant 50 additional free calls (per trust-and-pricing.md).
        """
        if 2.5 <= avg_rating < 4.0:
            return 50
        return 0

    # ------------------------------------------------------------------
    # Account management (DB operations)
    # ------------------------------------------------------------------

    async def get_or_create_account(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> BillingAccount:
        """Get existing account or create one with signup credit."""
        result = await db.execute(
            select(BillingAccount).where(BillingAccount.user_id == user_id)
        )
        account = result.scalar_one_or_none()
        if account:
            return account

        account = BillingAccount(
            user_id=user_id,
            balance=0.0,
            total_deposited=0.0,
            total_spent=0.0,
            free_credit=settings.user_signup_credit,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    async def get_account(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Get account summary (balance, free_credit, totals)."""
        account = await self.get_or_create_account(db, user_id)
        return {
            "balance": account.balance,
            "free_credit": account.free_credit,
            "total_deposited": account.total_deposited,
            "total_spent": account.total_spent,
        }

    async def deposit(
        self,
        db: AsyncSession,
        user_id: str,
        amount: float,
        payment_method: str,
    ) -> dict[str, Any]:
        """Add funds to a user account. Payment is mocked for MVP."""
        account = await self.get_or_create_account(db, user_id)
        account.balance = round(account.balance + amount, 4)
        account.total_deposited = round(account.total_deposited + amount, 4)
        account.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(account)
        return {
            "balance": account.balance,
            "free_credit": account.free_credit,
            "total_deposited": account.total_deposited,
            "total_spent": account.total_spent,
        }

    # ------------------------------------------------------------------
    # Charging / transaction recording
    # ------------------------------------------------------------------

    async def charge(
        self,
        db: AsyncSession,
        task_id: str | None,
        session_id: str | None,
        user_id: str | None,
        agent_id: str,
        units: float = 1.0,
    ) -> dict[str, Any]:
        """
        Calculate and record a charge for an agent call — concurrency-safe.

        **FIXED (was TOCTOU):** Uses ``SELECT … FOR UPDATE`` to lock the
        billing account row *before* reading the balance, so concurrent
        requests cannot both see the same balance and double-spend.

        Sequence (all within a single DB transaction):
          1. Lock & read agent row (protects free_quota_used increment)
          2. Lock & read user billing account (protects balance deduction)
          3. Calculate charge (pure logic, no DB)
          4. Mutate locked rows
          5. Record transaction
          6. Single ``await db.commit()``

        **SQLite note:** ``FOR UPDATE`` locks the entire table in SQLite.
        This is acceptable for MVP; PostgreSQL migration will reduce it to
        row-level locking.
        """
        import json as _json

        # ── 1. Lock & read agent ──────────────────────────────────────
        agent_result = await db.execute(
            select(Agent).where(Agent.id == agent_id).with_for_update()
        )
        agent_model: Agent | None = agent_result.scalar_one_or_none()
        if not agent_model:
            raise ValueError(f"Agent {agent_id} not found")

        # Parse pricing once
        unit_price = 0.0
        pricing_model = PricingModel.per_call.value
        try:
            card = _json.loads(agent_model.card_json) if agent_model.card_json else {}
            pricing = card.get("pricing", {})
            unit_price = pricing.get("unit_price", 0.0)
            pricing_model = pricing.get("model", PricingModel.per_call.value)
        except (_json.JSONDecodeError, AttributeError):
            pass

        agent_dict = {
            "unit_price": unit_price,
            "pricing_model": pricing_model,
            "free_quota_used": agent_model.free_quota_used,
            "free_quota_total": agent_model.free_quota_total,
            "trial_status": agent_model.trial_status,
        }

        # ── 2. Lock & read user account ───────────────────────────────
        user_account: dict[str, Any] | None = None
        account_model: BillingAccount | None = None
        if user_id:
            account_model = await self._get_or_create_account_locked(db, user_id)
            user_account = {
                "free_credit": account_model.free_credit,
                "balance": account_model.balance,
            }

        # ── 3. Calculate charge (pure logic) ──────────────────────────
        result = self.calculate_charge(agent_dict, user_account, units)

        # ── 4. Mutate locked rows ─────────────────────────────────────
        if not result.is_free and user_id and result.user_paid > 0 and account_model:
            if account_model.balance < result.user_paid:
                raise ValueError(
                    f"Insufficient balance. Have ${account_model.balance:.2f}, "
                    f"need ${result.user_paid:.2f}"
                )
            account_model.balance = round(account_model.balance - result.user_paid, 4)
            account_model.total_spent = round(
                (account_model.total_spent or 0.0) + result.user_paid, 4
            )
            account_model.updated_at = datetime.now(timezone.utc)
            if result.free_source == FreeSource.user_credit.value:
                used_credit = min(account_model.free_credit or 0.0, result.user_paid)
                account_model.free_credit = round(
                    (account_model.free_credit or 0.0) - used_credit, 4
                )

        # Increment agent free_quota_used (trial)
        if result.is_free and result.free_source == FreeSource.agent_trial.value:
            agent_model.free_quota_used = (agent_model.free_quota_used or 0) + 1
            agent_model.updated_at = datetime.now(timezone.utc)

        # ── 5. Record transaction ─────────────────────────────────────
        tx = BillingTransaction(
            user_id=user_id or DEFAULT_USER_ID,
            agent_id=agent_id,
            task_id=task_id,
            session_id=session_id,
            amount=result.user_paid,
            agent_earning=result.agent_earning,
            platform_fee=result.platform_fee,
            pricing_model=pricing_model,
            unit_price=unit_price,
            units=units,
            is_free=1 if result.is_free else 0,
            free_source=result.free_source,
        )
        db.add(tx)

        # ── 6. Single atomic commit ───────────────────────────────────
        await db.commit()
        await db.refresh(tx)

        return {
            "transaction_id": tx.id,
            "amount": result.user_paid,
            "agent_earning": result.agent_earning,
            "platform_fee": result.platform_fee,
            "is_free": result.is_free,
            "free_source": result.free_source,
        }

    # ------------------------------------------------------------------
    # Internal: locked account fetch
    # ------------------------------------------------------------------

    async def _get_or_create_account_locked(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> BillingAccount:
        """Fetch or create a billing account with row-level lock held.

        Uses ``SELECT … FOR UPDATE`` so the row cannot be modified by
        another transaction until this one commits.
        """
        result = await db.execute(
            select(BillingAccount)
            .where(BillingAccount.user_id == user_id)
            .with_for_update()
        )
        account = result.scalar_one_or_none()
        if account:
            return account

        # Create new account (no lock needed — it doesn't exist yet)
        account = BillingAccount(
            user_id=user_id,
            balance=0.0,
            total_deposited=0.0,
            total_spent=0.0,
            free_credit=settings.user_signup_credit,
        )
        db.add(account)
        await db.flush()  # assign id without committing
        return account

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_transactions(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List billing transactions for a user."""
        query = (
            select(BillingTransaction)
            .where(BillingTransaction.user_id == user_id)
            .order_by(desc(BillingTransaction.created_at))
            .limit(limit)
        )
        result = await db.execute(query)
        transactions = result.scalars().all()
        return [
            {
                "id": t.id,
                "user_id": t.user_id,
                "agent_id": t.agent_id,
                "task_id": t.task_id,
                "session_id": t.session_id,
                "amount": t.amount,
                "agent_earning": t.agent_earning,
                "platform_fee": t.platform_fee,
                "pricing_model": t.pricing_model,
                "unit_price": t.unit_price,
                "units": t.units,
                "is_free": bool(t.is_free),
                "free_source": t.free_source,
                "created_at": t.created_at,
            }
            for t in transactions
        ]

    async def get_payouts(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> list[dict[str, Any]]:
        """List payout history for an agent."""
        query = (
            select(AgentPayout)
            .where(AgentPayout.agent_id == agent_id)
            .order_by(desc(AgentPayout.created_at))
        )
        result = await db.execute(query)
        payouts = result.scalars().all()
        return [
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "period_start": p.period_start,
                "period_end": p.period_end,
                "total_earned": p.total_earned,
                "platform_fee": p.platform_fee,
                "net_amount": p.net_amount,
                "status": p.status,
                "paid_at": p.paid_at,
                "stripe_payout_id": p.stripe_payout_id,
                "created_at": p.created_at,
            }
            for p in payouts
        ]

    async def check_agent_free_quota(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> dict[str, Any]:
        """Check agent's free trial status and remaining quota."""
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            return {"remaining": 0, "total": 0, "used": 0, "trial_status": None}

        remaining = max(0, agent.free_quota_total - agent.free_quota_used)
        extra = self.get_extra_trial_quota(agent.avg_rating)
        return {
            "remaining": remaining + extra,
            "total": agent.free_quota_total + extra,
            "used": agent.free_quota_used,
            "trial_status": agent.trial_status,
        }
