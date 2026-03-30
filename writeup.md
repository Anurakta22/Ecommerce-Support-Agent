# E-Commerce Support Resolution Agent — Project Write-Up

## Architecture Overview

The system is a **4-agent LangChain RAG pipeline** that ingests 13 policy documents, indexes them in a local FAISS vector store, and orchestrates four sequential agents to resolve customer support tickets.

```
Ticket Input (text + structured JSON order context)
        │
        ▼
┌─────────────────────┐
│  Agent 1: Triage    │  ── Classify issue type, detect blocking missing info
└────────┬────────────┘
         │ (only exits early if confidence=low AND questions exist)
         ▼
┌──────────────────────────┐
│  Agent 2: Policy         │  ── FAISS semantic search, top-6 chunks,
│  Retriever               │     doc_id > Section citations
└────────┬─────────────────┘
         ▼
┌──────────────────────────┐
│  Agent 3: Resolution     │  ── Evidence-only drafting; cites retrieved
│  Writer                  │     excerpts; selects approve/deny/partial/escalate
└────────┬─────────────────┘
         ▼
┌──────────────────────────┐
│  Agent 4: Compliance     │  ── Validates every claim against retrieved policy
│  Checker                 │     triggers rewrite once; forces escalation if
└──────────────────────────┘     compliance fails twice
```

**LLM:** `llama-3.3-70b-versatile` via Groq API (temperature=0 for determinism)
**Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (local CPU)
**Vector Store:** FAISS (local, no server required)
**Framework:** LangChain LCEL chains with `JsonOutputParser`

---

## Agent Responsibilities and Prompts

| Agent | Responsibility | Key Prompt Rules |
|---|---|---|
| **Triage** | Classify issue (refund/shipping/payment/promo/fraud/dispute/other), assess confidence, generate clarifying questions only when truly blocking | Never ask questions when situation is clear from ticket (e.g., "Final Sale," "wrong item"); includes concrete examples |
| **Policy Retriever** | FAISS semantic search returning top-6 policy chunks | Not LLM-based; Python function; returns `doc_id > Section` citation strings |
| **Resolution Writer** | Draft decision + rationale + 150-word customer response, grounded in retrieved excerpts | Hard rules: never invent policy; must cite exact doc+section; escalate if no coverage |
| **Compliance Checker** | Verify every factual claim is backed by citations; check for data leakage and consistency | Returns `passed`, `issues`, `corrected_decision`, `unsupported_claims_flag` |

---

## Data Sources

All 13 policy documents are **synthetic internal policy documents** authored specifically for this project, modeled after common e-commerce platform policies:

| Doc ID | Coverage |
|---|---|
| `policy_returns_exceptions` | Final sale, hygiene, perishable return exceptions |
| `policy_cancellations` | Pre/post-shipment cancellation, instant processing |
| `policy_shipping_lost` | Lost packages, delayed delivery, non-receipt claims |
| `policy_promotions` | Coupon rules, stacking, expiry, abuse |
| `policy_marketplace_seller` | Seller authority, platform override, conflict hierarchy |
| `policy_regional_eu` | EU 14-day withdrawal right, Article 16 exceptions |
| `policy_regional_us` | US 30-day standard policy, state-level variations |
| `policy_disputes_escalation` | Escalation triggers, SLAs, appeals process |
| `policy_fraud_abuse` | Staged enforcement, false claims, appeals |
| `policy_damaged_item` | Transit damage, defect, incorrect item resolution |
| `policy_missing_items` | Partial delivery, verification, high-value protocol |
| `policy_return_abuse_behavior` | Abuse indicators, tiered enforcement |
| `policy_order_context_interpretation` | Status/category/region interpretation rules |

**Total corpus**: ~25,000+ words across 13 documents.

---

## Chunking Strategy

**Primary splitter**: `MarkdownHeaderTextSplitter` on `##` headers — each chunk maps cleanly to one policy section, enabling citation-ready retrieval with `doc_id > Section Name` identifiers.

**Secondary splitter**: `RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)` — handles sections exceeding token limits. 600 characters captures a full policy clause; 80-char overlap prevents clause splits from losing cross-sentence context.

**Rationale**: Header-based chunking preserves semantic coherence within sections and makes citation generation deterministic. The 600/80 character configuration was chosen to balance retrieval granularity (chunked by clause) against context loss (overlap prevents mid-sentence breaks).

**Retriever settings**: Top-6 chunks (`k=6`) using FAISS `L2` similarity search. No metadata pre-filtering is applied at retrieval time; instead, the Resolution Writer filters by relevance through its evidence-only prompt.

---

## No-Hallucination Controls

Four layered controls prevent fabricated policy claims:

1. **Evidence-only generation prompt** — The Resolution Writer's system prompt contains hard rules: "Every claim in your rationale MUST be supported by one of the provided policy excerpts" and "Never invent policy, timelines, percentages, or exceptions not present in the excerpts."
2. **Compliance Agent verification** — Agent 4 independently checks every factual claim against the retrieved excerpts and flags `unsupported_claims_flag=true` when unsupported statements are found.
3. **Automatic rewrite loop** — If compliance fails, the Resolution Writer is called again with the specific compliance issues listed in its prompt. This gives the model a clear corrective signal.
4. **Forced escalation on double failure** — If compliance fails twice, the decision is hard-coded to `needs_escalation` and the `unsupported_claims_flag` is set, ensuring the output is never propagated as a confident resolution.

---

## Evaluation Summary

**Test set**: 21 tickets — 8 standard, 6 exception-heavy, 3 conflict, 3 not-in-policy, 1 catch-all.

| Metric | Description |
|---|---|
| **Citation coverage rate** | % of outputs that include at least one `doc_id > Section` citation |
| **Decision accuracy** | % of decisions matching expected outcomes (`expected_decision` field) |
| **Correct escalation rate** | % of conflict/not-in-policy tickets that correctly receive `needs_escalation` |
| **Unsupported claims rate** | % of outputs flagged by the Compliance Agent |

**Key observations** (illustrative from evaluation runs):
- High citation coverage (~85–95%) on standard and exception cases after the Compliance Agent loop
- Conflict cases (T016–T018) appropriately escalated due to insufficient policy coverage for cross-policy resolution
- Not-in-policy cases (T019–T021) consistently escalated because policy retrieval returns no relevant excerpts, triggering the Resolution Writer's "no policy coverage → escalate" rule

### Key Failure Modes

1. **Triage over-questioning**: Early prompt versions caused the Triage Agent to generate unnecessary clarifying questions (e.g., asking about packaging condition for Final Sale items where policy applies unconditionally), blocking pipeline flow
2. **Compliance prompt escape**: Using `{...}` instead of `{{...}}` in prompt templates caused LangChain to misinterpret JSON keys as variable placeholders, crashing the Compliance Agent
3. **Confidence threshold sensitivity**: The pipeline's early-exit condition (block on clarifying questions) was too aggressive; refined to only exit when both questions exist and confidence is `low`

---

## What Would Be Improved Next

1. **Metadata filtering on retrieval** — Add `region` and `category` metadata filters to the FAISS retriever to surface region-specific and category-specific policy chunks more reliably (e.g., prioritize EU docs for EU-region tickets)
2. **Streaming output** — Replace blocking `chain.invoke()` with `chain.astream()` for real-time customer response generation in a UI context
3. **Evaluation rubric automation** — Automate the unsupported-claims assessment using a dedicated LLM judge that compares each rationale sentence against the retrieved excerpts, eliminating manual review dependency
4. **Multi-turn ticket threads** — Extend the input format to handle multi-message ticket threads (customer replies with answers to clarifying questions) rather than single-shot resolution only
5. **CrewAI migration** — Refactor to CrewAI for native agent memory, role assignment, and inter-agent tool sharing, which would better support the fraud detection and return abuse monitoring use cases
