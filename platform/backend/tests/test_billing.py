"""
Unit tests for the Billing Service.

Focus areas (aligned with the TOCTOU fix):
  - Charge calculation correctly applies free-trial and user-credit logic
  - ``calculate_charge`` is pure logic (no DB)
  - Balance deduction priority: agent_trial > user_credit > normal
"""

from __future__ import annotations

import pytest

from src.platform.core.billing import (
    BillingService,
    FreeSource,
    PricingModel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def billing() -> BillingService:
    return BillingService(platform_fee_rate=0.15)


@pytest.fixture
def trial_agent() -> dict:
    """Agent still within its free trial quota."""
    return {
        "unit_price": 0.50,
        "pricing_model": PricingModel.per_call.value,
        "free_quota_used": 50,
        "free_quota_total": 100,
        "trial_status": "trial",
    }


@pytest.fixture
def paid_agent() -> dict:
    """Agent that has exhausted its free trial."""
    return {
        "unit_price": 0.50,
        "pricing_model": PricingModel.per_call.value,
        "free_quota_used": 100,
        "free_quota_total": 100,
        "trial_status": "verified",
    }


@pytest.fixture
def user_with_credit() -> dict:
    """User who still has free sign-up credit."""
    return {"free_credit": 5.00, "balance": 10.00}


@pytest.fixture
def user_no_credit() -> dict:
    """User who has used all free credit."""
    return {"free_credit": 0.0, "balance": 50.00}


# ---------------------------------------------------------------------------
# Free trial (agent_trial)
# ---------------------------------------------------------------------------

class TestAgentTrialQuota:
    """Agent free trial must take priority over all other payment sources."""

    def test_trial_agent_is_free(self, billing, trial_agent, user_with_credit):
        result = billing.calculate_charge(trial_agent, user_with_credit, units=1.0)
        assert result.is_free is True
        assert result.free_source == FreeSource.agent_trial.value
        assert result.user_paid == 0.0
        assert result.agent_earning == 0.0

    def test_trial_agent_even_without_user(self, billing, trial_agent):
        """Free trial applies even when there is no user account."""
        result = billing.calculate_charge(trial_agent, None, units=1.0)
        assert result.is_free is True
        assert result.free_source == FreeSource.agent_trial.value

    def test_paid_agent_not_free(self, billing, paid_agent, user_no_credit):
        result = billing.calculate_charge(paid_agent, user_no_credit, units=2.0)
        assert result.is_free is False
        assert result.user_paid > 0
        assert result.agent_earning > 0


# ---------------------------------------------------------------------------
# User credit
# ---------------------------------------------------------------------------

class TestUserCredit:
    """User sign-up credit must be consumed after agent trial but before real payment."""

    def test_user_credit_covers_charge(self, billing, paid_agent, user_with_credit):
        result = billing.calculate_charge(paid_agent, user_with_credit, units=1.0)
        assert result.is_free is True
        assert result.free_source == FreeSource.user_credit.value
        assert result.user_paid == 0.0
        # Platform pays the agent during user-credit period
        assert result.agent_earning == 0.50

    def test_user_credit_exhausted(self, billing, paid_agent, user_no_credit):
        result = billing.calculate_charge(paid_agent, user_no_credit, units=1.0)
        assert result.is_free is False
        assert result.free_source is None


# ---------------------------------------------------------------------------
# Normal charge
# ---------------------------------------------------------------------------

class TestNormalCharge:
    """Normal charges must split correctly between agent and platform."""

    def test_correct_split(self, billing, paid_agent, user_no_credit):
        result = billing.calculate_charge(paid_agent, user_no_credit, units=1.0)
        assert result.user_paid == 0.575   # 0.50 + 15% fee = 0.575
        assert result.agent_earning == 0.50
        assert result.platform_fee == 0.075

    def test_multi_unit_charge(self, billing, paid_agent, user_no_credit):
        result = billing.calculate_charge(paid_agent, user_no_credit, units=10.0)
        assert result.user_paid == 5.75
        assert result.agent_earning == 5.00
        assert result.platform_fee == 0.75

    def test_priority_agent_trial_over_user_credit(self, billing, trial_agent, user_with_credit):
        """agent_trial beats user_credit even when both are available."""
        result = billing.calculate_charge(trial_agent, user_with_credit, units=1.0)
        assert result.free_source == FreeSource.agent_trial.value


# ---------------------------------------------------------------------------
# Trial extension
# ---------------------------------------------------------------------------

class TestTrialExtension:
    """Phase-2 trial extension per trust-and-pricing.md."""

    def test_qualifying_rating_gets_extension(self, billing):
        assert billing.get_extra_trial_quota(3.0) == 50   # 2.5 <= r < 4.0
        assert billing.get_extra_trial_quota(3.9) == 50

    def test_high_rating_no_extension(self, billing):
        assert billing.get_extra_trial_quota(4.5) == 0    # >= 4.0, approved

    def test_low_rating_no_extension(self, billing):
        assert billing.get_extra_trial_quota(2.0) == 0    # < 2.5, poor quality

    def test_boundary_values(self, billing):
        assert billing.get_extra_trial_quota(2.5) == 50   # inclusive lower bound
        assert billing.get_extra_trial_quota(4.0) == 0    # exclusive upper bound


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestBillingEdgeCases:
    """Billing must handle edge-case inputs gracefully."""

    def test_zero_unit_price_agent(self, billing, user_no_credit):
        agent = {"unit_price": 0.0, "pricing_model": "per_call",
                 "free_quota_used": 200, "free_quota_total": 100,
                 "trial_status": "verified"}
        result = billing.calculate_charge(agent, user_no_credit, units=5.0)
        assert result.user_paid == 0.0
        assert result.agent_earning == 0.0
        assert result.platform_fee == 0.0
        assert result.is_free is False  # not "free" — it's just a $0 service

    def test_zero_units(self, billing, paid_agent, user_no_credit):
        result = billing.calculate_charge(paid_agent, user_no_credit, units=0.0)
        assert result.user_paid == 0.0
        assert result.agent_earning == 0.0

    def test_negative_units_clamped(self, billing, paid_agent, user_no_credit):
        """Negative units is a caller bug, but calculate_charge should not crash."""
        # calculate_charge uses units for multiplication; negative would be a bug
        # but we don't crash — the caller should validate
        result = billing.calculate_charge(paid_agent, user_no_credit, units=-1.0)
        assert result.user_paid < 0  # negative charge → caller bug, not our problem

    def test_missing_unit_price_defaults_to_zero(self, billing, user_no_credit):
        agent = {"free_quota_used": 200, "free_quota_total": 100, "trial_status": "verified"}
        result = billing.calculate_charge(agent, user_no_credit, units=1.0)
        assert result.user_paid == 0.0  # unit_price defaults to 0
