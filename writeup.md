# 🛍️ E-Commerce Support Resolution Agent — Project Write-Up

[![Hugging Face Spaces](https://img.shields.io/badge/🤗%20Hugging%20Face-Live%20Demo-blue)](https://huggingface.co/spaces/Anurakta/Ecommerce-support-agent)
[![Video Walkthrough](https://img.shields.io/badge/▶️%20Video-Walkthrough-red)](https://drive.google.com/file/d/1UNdLrF9vmBfTU1BakFzyQLbPjpDmVcbj/view?usp=sharing)

## Architecture Overview

The system is a highly advanced **4-agent LangChain RAG pipeline** that ingests 13 core policy documents, dynamically indexes them in a local FAISS vector store, and orchestrates four sequential agents to securely resolve complex customer support tickets.

```text
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
**Vector Store:** FAISS (Dynamic, Auto-Generated)  
**Framework:** LangChain LCEL chains strictly typing outputs to Pydantic via `JsonOutputParser`

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

All 13 policy documents are **comprehensive synthetic policy documents** authored specifically for this project, heavily modeled after real-world e-commerce platforms (Amazon, Shopify):

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

**Primary splitter**: `MarkdownHeaderTextSplitter` on `##` headers — each chunk maps cleanly to one policy section, enabling citation-ready retrieval with explicit `doc_id > Section Name` identifiers.

**Secondary splitter**: `RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)` — gracefully handles sections exceeding standard token limits. 600 characters efficiently captures a full policy clause; the 80-char overlap prevents clause splits from losing cross-sentence contextual framing.

**Rationale**: Header-based chunking preserves semantic coherence within discrete sections and keeps backend citation generation deterministic. The 600/80 character configuration was chosen through systematic iteration to precisely balance retrieval granularity against semantic context loss.

**Retriever settings**: Top-6 chunks (`k=6`) using FAISS `L2` similarity search. No metadata pre-filtering is currently applied at retrieval time; the Resolution Writer effectively filters by relevance through its strict evidence-only prompt methodology.

---

## No-Hallucination Controls

Four layered safety controls prevent fabricated policy claims:

1. **Evidence-Only Generation Prompt** — The Resolution Writer's system prompt contains hard rules: *"Every claim in your rationale MUST be supported by one of the provided policy excerpts"* and *"Never invent policy, timelines, percentages, or exceptions not present in the excerpts."*
2. **Independent Compliance Verification** — Agent 4 independently checks every factual claim against the natively retrieved excerpts. It aggressively flags `unsupported_claims_flag=true` when hallucinated statements are found.
3. **Automatic Rewrite Loop** — If compliance fails, the Resolution Writer is immediately called again with the specific compliance issues explicitly listed in its prompt. This feeds the model a clear, deterministic corrective signal.
4. **Forced Escalation Fallback** — If compliance fails a second time, the system hard-codes the decision to `needs_escalation` and preserves the `unsupported_claims_flag`, guaranteeing that the output is never blindly propagated to human agents as a confident resolution.

---

## Evaluation Summary

**Test Database**: 21 specifically crafted tickets — 8 standard cases, 6 exception-heavy cases, 3 conflict cases, 3 out-of-policy cases, and 1 catch-all edge case.

| Metric | Goal | Description |
|---|---|---|
| **Citation coverage rate** | 100% | % of outputs that include at least one exact `doc_id > Section` citation |
| **Decision accuracy** | 100% | % of decisions matching expected outcomes (`expected_decision` field) |
| **Correct escalation rate** | >95% | % of high-conflict tickets that correctly receive `needs_escalation` |
| **Unsupported claims rate** | <5% | % of final outputs flagged by the Compliance Agent |

**Key Iteration Highlights:**
- **High citation coverage (~85–95%)** on standard cases is consistently achieved via the Compliance Agent rewrite loop.
- **Complex Conflict tickets (T016–T018)** are appropriately and intelligently prioritized for agent escalation when insufficient cross-policy coverage exists.
- **Triage Optimization:** Early iterations caused the Triage Agent to block the pipeline with unnecessary tracking questions (like asking for a photo of a "Final Sale" item). The pipeline's logic gate was aggressively tightened to securely bypass blocking unless both confidence is low *and* a relevant question is returned.

---

## Technical Future-Proofing

1. **Metadata Filtering:** Adding `region` and `category` metadata filters to the FAISS retriever index to immediately drop out-of-scope policies for faster similarity mapping.
2. **Streaming Output:** Replacing the blocking `chain.invoke()` execution stream with `chain.astream()` to allow for real-time typewriter generation inside the Streamlit user interface.
3. **Automated LLM Judges:** Phasing out manual `evaluate.py` tracking by introducing an LLM as a Judge architecture to seamlessly compare the entire 21 ticket dataset during CI/CD.
4. **CrewAI Migration:** Native migration to CrewAI to provide long-term thread memory and direct tool capability access to the Triage Agent.
