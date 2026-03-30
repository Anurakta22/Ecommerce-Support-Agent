"""
Four LangChain agents for the E-Commerce Support Resolution Agent:
  1. Triage Agent
  2. Policy Retriever (Python function, not a prompt chain)
  3. Resolution Writer Agent
  4. Compliance / Safety Agent
"""
import os
import json
import logging
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

load_dotenv()

logger = logging.getLogger(__name__)

# ── LLM ───────────────────────────────────────────────────────────────────
def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=2048,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )


def _safe_json_parse(raw: Any, fallback: dict) -> dict:
    """
    Try to parse raw as JSON dict. If it's already a dict (from JsonOutputParser),
    return it. Otherwise, attempt json.loads. On failure, return fallback.
    """
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"JSON parse failure: {e}\nRaw output: {raw}")
        return fallback


# ══════════════════════════════════════════════════
# AGENT 1: Triage Agent
# ══════════════════════════════════════════════════
TRIAGE_SYSTEM_PROMPT = """You are a support ticket triage agent for an e-commerce platform.

Given a customer support ticket and order context, your job is to:
1. Classify the issue type: refund, shipping, payment, promo, fraud, dispute, other
2. Assign confidence: high / medium / low
3. Identify ONLY truly blocking missing information (see strict rules below)

━━ STRICT RULES FOR clarifying_questions ━━
Leave clarifying_questions EMPTY [] unless ALL of the following are true:
  a) The missing info would completely change which policy applies
  b) It cannot be inferred AT ALL from the ticket text or order context
  c) Without it, no policy lookup can be performed

NEVER ask a clarifying question when:
  • The ticket mentions "Final Sale" → the policy applies unconditionally; condition is irrelevant
  • The ticket mentions "wrong item", "not delivered", "damaged" → situation is clear
  • The item category is already known from order context
  • The question is about customer preference (refund vs store credit) — that comes later
  • You would merely be confirming something obvious or already stated

━━ CONCRETE EXAMPLES ━━
Ticket: "I want to return the lipstick. It was marked Final Sale."
→ classification: refund, confidence: high, clarifying_questions: []
   REASON: Final Sale policy applies regardless of condition. No information is missing.

Ticket: "I have a promo code that didn't work."
→ classification: promo, confidence: medium, clarifying_questions: ["What is the promo code you used?"]
   REASON: The code itself is needed to look up whether it's valid.

Ticket: "My order hasn't arrived."
→ classification: shipping, confidence: high, clarifying_questions: []
   REASON: Order status and shipping region are in the order context.

Respond ONLY in valid JSON:
{{
  "classification": "<type>",
  "confidence": "<high|medium|low>",
  "clarifying_questions": []
}}
No preamble, no markdown, no explanation outside the JSON."""
TRIAGE_HUMAN_PROMPT = """Ticket:
{ticket_text}

Order Context:
{order_context}"""


def run_triage_agent(ticket_text: str, order_context: str) -> dict:
    """
    Classify the support ticket and identify missing info.

    Returns:
        {classification, confidence, clarifying_questions}
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", TRIAGE_SYSTEM_PROMPT),
        ("human", TRIAGE_HUMAN_PROMPT),
    ])
    chain = prompt | llm | JsonOutputParser()

    fallback = {
        "classification": "other",
        "confidence": "low",
        "clarifying_questions": [],
    }

    try:
        result = chain.invoke({
            "ticket_text": ticket_text,
            "order_context": order_context,
        })
        return _safe_json_parse(result, fallback)
    except Exception as e:
        logger.error(f"Triage agent error: {e}")
        return fallback


# ══════════════════════════════════════════════════
# AGENT 2: Policy Retriever (Python function)
# ══════════════════════════════════════════════════

def run_policy_retriever(ticket_text: str, classification: str, retriever) -> str:
    """
    Query FAISS vectorstore and return formatted policy excerpts with citations.

    Returns:
        Formatted string: "[doc_id > Section]: content\n..."
    """
    query = f"{classification} policy: {ticket_text[:200]}"
    docs = retriever.invoke(query)

    if not docs:
        return "No relevant policy excerpts found."

    formatted_parts = []
    for doc in docs:
        meta = doc.metadata
        doc_id = meta.get("doc_id", "unknown")
        section = meta.get("section", "General")
        citation = f"{doc_id} > {section}"
        formatted_parts.append(f"[{citation}]:\n{doc.page_content.strip()}")

    return "\n\n".join(formatted_parts)


# ══════════════════════════════════════════════════
# AGENT 3: Resolution Writer Agent
# ══════════════════════════════════════════════════
RESOLUTION_SYSTEM_PROMPT = """You are a resolution writer for an e-commerce customer support team.

You will be given:
- A customer support ticket
- Order context (structured data)
- Retrieved policy excerpts with citations

Your job is to produce a structured resolution.

HARD RULES — NEVER VIOLATE:
1. Every claim in your rationale MUST be supported by one of the provided policy excerpts
2. If the policy excerpts do not cover the situation, set decision to "needs_escalation" and say "I don't have policy coverage for this situation"
3. Never invent policy, timelines, percentages, or exceptions not present in the excerpts
4. Never make promises about outcomes not explicitly stated in the policy
5. The customer_response_draft must be professional, empathetic, and concise (max 150 words)
6. Citations must reference the exact doc_id and section name from the provided excerpts

Decision options: approve / deny / partial / needs_escalation

Respond ONLY in valid JSON with keys: decision, rationale, citations (list), customer_response_draft
No preamble, no markdown, no explanation outside the JSON.

Retrieved Policy Excerpts:
{retrieved_excerpts}"""

RESOLUTION_HUMAN_PROMPT = """Ticket:
{ticket_text}

Order Context:
{order_context}

Classification: {classification}

{issues_note}"""


def run_resolution_writer(
    ticket_text: str,
    order_context: str,
    retrieved_excerpts: str,
    classification: str,
    issues_note: str = "",
) -> dict:
    """
    Draft a customer-facing resolution grounded in retrieved policy excerpts.

    Returns:
        {decision, rationale, citations, customer_response_draft}
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", RESOLUTION_SYSTEM_PROMPT),
        ("human", RESOLUTION_HUMAN_PROMPT),
    ])
    chain = prompt | llm | JsonOutputParser()

    fallback = {
        "decision": "needs_escalation",
        "rationale": "Unable to generate resolution due to a processing error.",
        "citations": [],
        "customer_response_draft": (
            "We're sorry for the inconvenience. Your case has been escalated "
            "to our support team for manual review."
        ),
    }

    try:
        result = chain.invoke({
            "retrieved_excerpts": retrieved_excerpts,
            "ticket_text": ticket_text,
            "order_context": order_context,
            "classification": classification,
            "issues_note": issues_note,
        })
        return _safe_json_parse(result, fallback)
    except Exception as e:
        logger.error(f"Resolution writer error: {e}")
        return fallback


# ══════════════════════════════════════════════════
# AGENT 4: Compliance / Safety Agent
# ══════════════════════════════════════════════════
COMPLIANCE_SYSTEM_PROMPT = """You are a compliance checker for an e-commerce support AI system.

You will be given:
- A proposed resolution (decision + rationale + citations + customer response)
- The policy excerpts that were retrieved

Your job is to verify:
1. Every factual claim in the rationale is supported by the provided policy excerpts
2. All citations are real and reference actual content from the excerpts
3. The customer response does not contain promises not backed by policy
4. No sensitive data (order IDs, payment details) is leaked unnecessarily
5. The decision (approve/deny/partial/needs_escalation) is consistent with the policy

If you find issues, list them clearly. If the resolution should be escalated instead, say so.

Respond ONLY in valid JSON:
{{
  "passed": true/false,
  "issues": ["issue 1", "issue 2"],
  "corrected_decision": "needs_escalation" or null,
  "unsupported_claims_flag": true/false
}}
No preamble, no markdown, no explanation outside the JSON."""

COMPLIANCE_HUMAN_PROMPT = """Proposed Resolution:
{resolution}

Retrieved Policy Excerpts:
{retrieved_excerpts}"""


def run_compliance_agent(resolution: dict, retrieved_excerpts: str) -> dict:
    """
    Verify the resolution has no unsupported claims or policy violations.

    Returns:
        {passed, issues, corrected_decision, unsupported_claims_flag}
    """
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", COMPLIANCE_SYSTEM_PROMPT),
        ("human", COMPLIANCE_HUMAN_PROMPT),
    ])
    chain = prompt | llm | JsonOutputParser()

    fallback = {
        "passed": False,
        "issues": ["Compliance check failed due to processing error."],
        "corrected_decision": "needs_escalation",
        "unsupported_claims_flag": True,
    }

    try:
        result = chain.invoke({
            "resolution": json.dumps(resolution, indent=2),
            "retrieved_excerpts": retrieved_excerpts,
        })
        return _safe_json_parse(result, fallback)
    except Exception as e:
        logger.error(f"Compliance agent error: {e}")
        return fallback

