"""
Pipeline orchestrator: Runs all 4 agents in sequence to resolve a support ticket.

Flow:
  1. Triage Agent → classification + clarifying_questions
  2. If clarifying_questions → return early with partial AgentOutput
  3. Policy Retriever → retrieved_excerpts
  4. Resolution Writer → draft resolution
  5. Compliance Agent → validate resolution
  6. If failed → rewrite once with issues; if fails again → escalate
  7. Return final AgentOutput
"""
import logging
from typing import Optional

from src.models import TicketInput, AgentOutput, OrderContext
from src.agents import (
    run_triage_agent,
    run_policy_retriever,
    run_resolution_writer,
    run_compliance_agent,
)
from src.retriever import load_retriever

logger = logging.getLogger(__name__)

# Lazy-load the retriever once and reuse
_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = load_retriever(k=6)
    return _retriever


def _format_order_context(ctx: OrderContext) -> str:
    """Format OrderContext as a readable string for LLM prompts."""
    return (
        f"Order ID: {ctx.order_id}\n"
        f"Order Date: {ctx.order_date}\n"
        f"Delivery Date: {ctx.delivery_date or 'N/A'}\n"
        f"Item Category: {ctx.item_category}\n"
        f"Fulfillment Type: {ctx.fulfillment_type}\n"
        f"Shipping Region: {ctx.shipping_region}\n"
        f"Order Status: {ctx.order_status}\n"
        f"Payment Method: {ctx.payment_method or 'N/A'}"
    )


def run_pipeline(ticket_input: TicketInput) -> AgentOutput:
    """
    End-to-end pipeline: from ticket to structured AgentOutput.
    """
    ticket_text = ticket_input.ticket_text
    order_context_str = _format_order_context(ticket_input.order_context)

    # ── Step 1: Triage ─────────────────────────────────────────────────
    logger.info("Running Triage Agent…")
    triage_result = run_triage_agent(ticket_text, order_context_str)

    classification = triage_result.get("classification", "other")
    confidence = triage_result.get("confidence", "low")
    clarifying_questions = triage_result.get("clarifying_questions", [])

    # ── Step 2: Early exit only if truly blocked ───────────────────────
    # Only stop for clarifying questions when confidence is also low.
    # If confidence is medium/high, the situation is clear enough to proceed.
    truly_blocked = bool(clarifying_questions) and confidence == "low"
    if truly_blocked:
        logger.info(f"Triage flagged missing info. Returning with {len(clarifying_questions)} questions.")
        return AgentOutput(
            classification=classification,
            confidence=confidence,
            clarifying_questions=clarifying_questions,
            decision="needs_escalation",
            rationale="Additional information is required to process this ticket.",
            citations=[],
            customer_response_draft=(
                "Thank you for reaching out. To help you better, we have a few questions:\n"
                + "\n".join(f"- {q}" for q in clarifying_questions)
            ),
            next_steps="Await customer response to clarifying questions before proceeding.",
            unsupported_claims_flag=False,
        )


    # ── Step 3: Policy Retrieval ────────────────────────────────────────
    logger.info("Running Policy Retriever…")
    retriever = _get_retriever()
    retrieved_excerpts = run_policy_retriever(ticket_text, classification, retriever)

    # ── Step 4: Resolution Writer ───────────────────────────────────────
    logger.info("Running Resolution Writer (attempt 1)…")
    resolution = run_resolution_writer(
        ticket_text=ticket_text,
        order_context=order_context_str,
        retrieved_excerpts=retrieved_excerpts,
        classification=classification,
    )

    # ── Step 5: Compliance Check ────────────────────────────────────────
    logger.info("Running Compliance Agent…")
    compliance = run_compliance_agent(resolution, retrieved_excerpts)

    unsupported_claims_flag = compliance.get("unsupported_claims_flag", False)

    # ── Step 6: Retry if compliance failed ─────────────────────────────
    if not compliance.get("passed", True):
        issues = compliance.get("issues", [])
        corrected_decision = compliance.get("corrected_decision")
        issues_note = (
            "COMPLIANCE ISSUES FOUND — fix these before writing:\n"
            + "\n".join(f"- {i}" for i in issues)
        )

        logger.warning(f"Compliance failed. Issues: {issues}. Retrying resolution…")
        resolution = run_resolution_writer(
            ticket_text=ticket_text,
            order_context=order_context_str,
            retrieved_excerpts=retrieved_excerpts,
            classification=classification,
            issues_note=issues_note,
        )

        # Second compliance check
        compliance2 = run_compliance_agent(resolution, retrieved_excerpts)
        unsupported_claims_flag = compliance2.get("unsupported_claims_flag", False)

        if not compliance2.get("passed", True):
            logger.warning("Compliance still failed after retry. Forcing escalation.")
            resolution["decision"] = "needs_escalation"
            resolution["rationale"] = (
                "Could not produce a compliant resolution after retry. "
                "Manual review required. Original issues: "
                + "; ".join(issues)
            )
            resolution["customer_response_draft"] = (
                "We're sorry for the inconvenience. Your case is being escalated "
                "to our specialist support team for a manual review. "
                "We'll get back to you within 24 hours."
            )
            unsupported_claims_flag = True

    # ── Step 7: Assemble final AgentOutput ─────────────────────────────
    decision = resolution.get("decision", "needs_escalation")
    rationale = resolution.get("rationale", "")
    citations = resolution.get("citations", [])
    customer_response_draft = resolution.get("customer_response_draft", "")

    # Determine next_steps based on decision
    next_steps_map = {
        "approve": "Process the approved resolution per standard workflow.",
        "deny": "Notify customer of denial with policy references. Close ticket.",
        "partial": "Process partial resolution. Log outcome for QA review.",
        "needs_escalation": "Escalate to Tier 2 support team for manual review.",
    }
    next_steps = next_steps_map.get(decision, "Review and take appropriate action.")

    return AgentOutput(
        classification=classification,
        confidence=confidence,
        clarifying_questions=[],
        decision=decision,
        rationale=rationale,
        citations=citations,
        customer_response_draft=customer_response_draft,
        next_steps=next_steps,
        unsupported_claims_flag=unsupported_claims_flag,
    )
