---
title: Ecommerce Support Agent
emoji: 🛍️
colorFrom: blue
colorTo: green
sdk: streamlit
app_file: app.py
pinned: false
---

# 🛍️ E-Commerce Support Resolution Agent

[![Hugging Face Spaces](https://img.shields.io/badge/🤗%20Hugging%20Face-Live%20Demo-blue)](https://huggingface.co/spaces/Anurakta/Ecommerce-support-agent)
[![Video Walkthrough](https://img.shields.io/badge/▶️%20Video-Walkthrough-red)](https://drive.google.com/file/d/1UNdLrF9vmBfTU1BakFzyQLbPjpDmVcbj/view?usp=sharing)

An advanced **4-agent LangChain RAG pipeline** designed to autonomously resolve e-commerce customer support tickets. Powered by FAISS and Groq's high-speed LLaMA-3.3-70B, it reads an embedded policy knowledge base and drafts precise, citation-backed resolutions to enforce company rules without hallucination.

---

## 🚀 Live Demo & Deployment

This project is fully deployed and hosted on **Hugging Face Spaces**. You do not need to install anything locally to see it in action!

- **Live Application:** [Hugging Face Space Dashboard](https://huggingface.co/spaces/Anurakta/Ecommerce-support-agent)
- **Video Walkthrough:** [Google Drive Demo Recording](https://drive.google.com/file/d/1UNdLrF9vmBfTU1BakFzyQLbPjpDmVcbj/view?usp=sharing)

*Note: The Hugging Face server automatically generates the required FAISS vector database from the internal Markdown documents on startup. The app is completely self-sufficient. If the Space shows "Building," it is simply compiling the database.*

---

## 🧠 Architecture

```text
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

## 🛡️ No-Hallucination Controls

1. **Evidence-only prompt** — The Resolution Writer is instructed to cite only retrieved excerpts.
2. **Compliance Agent** — Independently verifies every single claim against the retrieved policy text.
3. **Automatic escalation** — A failed compliance check triggers one automatic rewrite; a second failure forces a `needs_escalation` outcome.
4. **`unsupported_claims_flag`** — Persistently tracked in every output for security monitoring.

---

## 💻 Running Locally (Optional)

If you prefer to run the codebase on your own machine instead of using the live Hugging Face deployment, follow these local setup steps:

### 1. Clone / Navigate to the project
```bash
cd ecommerce-support-agent
```

### 2. Create and activate a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 5. Build the Vector Index (Optional)
The FAISS vector database will automatically generate the first time you run the application. However, you can also build it manually using:
```bash
python src/ingest.py
```
Expected output: `✅ Indexed chunks into vectorstore/`

### 6. Run the Application
**Single ticket (CLI):**
```bash
python main.py
```
Prompts for ticket text, uses a sample order context, and prints the full resolution as JSON.

**Full evaluation (21 tickets):**
```bash
python evaluate.py
```
Runs all test tickets, prints a metrics report, and saves results to `outputs/eval_results.json`.

---

## 📚 Policy Sources

All 13 synthetic policy documents are highly detailed and designed specifically for this vector database. They cover edge cases like Return Abuse, Regional Consumer Rights, Promotional Abuse, Seller Disputes, and Cancellations.

## 🏗️ Project Structure

```text
ecommerce-support-agent/
├── policies/           ← 13 policy .md files
├── src/
│   ├── models.py       ← Pydantic models
│   ├── ingest.py       ← Build FAISS index
│   ├── retriever.py    ← Load FAISS + retriever
│   ├── agents.py       ← 4 LangChain agents
│   └── pipeline.py     ← Orchestration
├── data/               ← 21 test tickets
├── outputs/            ← JSON eval results
├── vectorstore/        ← Auto-generated FAISS index
├── main.py             ← CLI runner
├── evaluate.py         ← Evaluation suite
├── requirements.txt    
└── .env.example
```
