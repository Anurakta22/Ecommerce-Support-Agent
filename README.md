# E-Commerce Support Resolution Agent

A **4-agent LangChain RAG pipeline** that resolves e-commerce customer support tickets using a policy knowledge base powered by FAISS and Groq LLaMA-3.3-70B.

---

## Architecture

```
Ticket Input
    │
    ▼
┌──────────────────┐
│  Agent 1: Triage │  ── Classify issue, detect missing info
└────────┬─────────┘
         │ (if info missing → return clarifying questions)
         ▼
┌──────────────────────────┐
│  Agent 2: Policy Retriever│  ── Query FAISS, return top-6 policy chunks
└────────┬─────────────────┘
         ▼
┌─────────────────────────────┐
│  Agent 3: Resolution Writer │  ── Draft decision + rationale + citations
└────────┬────────────────────┘
         ▼
┌────────────────────────────┐
│  Agent 4: Compliance Check │  ── Verify no unsupported claims
└────────┬───────────────────┘
         │ (if failed → rewrite once → escalate if still fails)
         ▼
    AgentOutput
```

**LLM:** `llama-3.3-70b-versatile` via Groq API  
**Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (local, CPU)  
**Vector Store:** FAISS (local)  
**Framework:** LangChain LCEL chains

---

## Setup

### 1. Clone / navigate to the project
```bash
cd ecommerce-support-agent
```

### 2. Create and activate virtual environment
```bash
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API key
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 5. Build the vector index
```bash
python src/ingest.py
```
Expected output: `✅ Indexed N chunks into vectorstore/`

---

## Run

### Streamlit Dashboard (Interactive UI)
We highly recommend running the provided Streamlit app for a visual, interactive demonstration of the system:
```bash
streamlit run app.py
```
This will open `http://localhost:8501` in your browser where you can test different order contexts and ticket permutations.

### Single ticket (CLI)
```bash
python main.py
```
Prompts for ticket text, uses a sample order context, and prints the full resolution as JSON.

### Full evaluation (20 tickets)
```bash
python evaluate.py
```
Runs all test tickets, prints a metrics report, and saves results to `outputs/eval_results.json`.

---

## Policy Sources

All policy documents use the following source URLs and were last accessed on **2025-01-15**:

| doc_id | Source URL | Coverage |
|--------|------------|----------|
| `policy_return_abuse_behavior` | `https://www.example-ecommerce.com/policies/abuse-behavior` | Return abuse detection, account restrictions |
| `policy_returns_exceptions` | `https://www.example-ecommerce.com/policies/returns-exceptions` | Final sale, hygiene, perishable exceptions |
| `policy_cancellations` | `https://www.example-ecommerce.com/policies/cancellations` | Pre/post-shipment cancellation rules |
| `policy_shipping_lost` | `https://www.example-ecommerce.com/policies/shipping` | Lost/delayed shipment handling |
| `policy_marketplace_seller` | `https://www.example-ecommerce.com/policies/marketplace` | Third-party seller dispute procedures |
| `policy_damaged_item` | `https://www.example-ecommerce.com/policies/damaged-items` | Transit damage, replacement eligibility |
| `policy_missing_items` | `https://www.example-ecommerce.com/policies/missing-items` | Partial order, missing item resolution |
| `policy_promotions` | `https://www.example-ecommerce.com/policies/promotions` | Promo code rules, stacking restrictions |
| `policy_regional_eu` | `https://www.example-ecommerce.com/policies/eu-consumer-rights` | EU consumer rights, 14-day right of withdrawal |
| `policy_regional_us` | `https://www.example-ecommerce.com/policies/us-consumer-rights` | US-specific return and refund rules |
| `policy_disputes_escalation` | `https://www.example-ecommerce.com/policies/disputes` | Dispute workflow, escalation triggers |
| `policy_fraud_abuse` | `https://www.example-ecommerce.com/policies/fraud` | Fraud detection, account action |
| `policy_order_context_interpretation` | `https://www.example-ecommerce.com/policies/order-context` | Order status interpretation guidelines |

---

## Chunking Strategy

**Primary:** `MarkdownHeaderTextSplitter` on `##` headers — each chunk maps cleanly to one policy section, enabling citation-ready retrieval with `doc_id > Section Name` references.

**Secondary:** `RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)` — handles sections exceeding token limits. 600 chars captures a full policy clause; 80-char overlap prevents clause splits from losing context.

---

## No-Hallucination Controls

1. **Evidence-only prompt** — Resolution Writer is instructed to cite only retrieved excerpts
2. **Compliance Agent** — verifies every claim against retrieved policy text
3. **Automatic escalation** — failed compliance triggers one rewrite; second failure forces `needs_escalation`
4. **`unsupported_claims_flag`** — tracked in every output for monitoring

---

## Project Structure

```
ecommerce-support-agent/
├── policies/           ← 13 policy .md files
├── src/
│   ├── models.py       ← Pydantic models
│   ├── ingest.py       ← Build FAISS index
│   ├── retriever.py    ← Load FAISS + retriever
│   ├── agents.py       ← 4 LangChain agents
│   └── pipeline.py     ← Orchestration
├── data/
│   └── test_tickets.json
├── outputs/
│   └── eval_results.json
├── vectorstore/        ← Auto-generated FAISS index
├── main.py
├── evaluate.py
├── requirements.txt
└── .env.example
```
