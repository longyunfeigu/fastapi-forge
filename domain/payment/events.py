"""
Payment domain events.

Dataclass events record important payment lifecycle facts for downstream handling
(e.g., messaging, projections). Domain remains free of infrastructure imports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class PaymentEvent:
    order_id: str
    provider: str
    provider_ref: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaymentSucceeded(PaymentEvent):
    pass


@dataclass
class PaymentFailed(PaymentEvent):
    reason: Optional[str] = None


@dataclass
class PaymentRefunded(PaymentEvent):
    refund_id: str = ""
    amount: str = ""


@dataclass
class PaymentCanceled(PaymentEvent):
    pass

