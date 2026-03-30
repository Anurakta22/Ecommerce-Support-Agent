"""
Pydantic models for the E-Commerce Support Resolution Agent.
"""
from typing import List, Optional
from pydantic import BaseModel


class OrderContext(BaseModel):
    order_id: str
    order_date: str
    delivery_date: Optional[str] = None
    item_category: str          # perishable / apparel / electronics / hygiene / other
    fulfillment_type: str       # first-party / marketplace
    shipping_region: str        # US / EU / UK / other
    order_status: str           # placed / shipped / delivered / returned
    payment_method: Optional[str] = None


class TicketInput(BaseModel):
    ticket_text: str
    order_context: OrderContext


class AgentOutput(BaseModel):
    classification: str                    # refund / shipping / payment / promo / fraud / other
    confidence: str                        # high / medium / low
    clarifying_questions: List[str]        # empty list if none needed
    decision: str                          # approve / deny / partial / needs_escalation
    rationale: str
    citations: List[str]                   # ["doc_id > Section Name", ...]
    customer_response_draft: str
    next_steps: str
    unsupported_claims_flag: bool          # set by compliance agent
