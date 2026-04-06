"""
evaluate.py — Run all 21 test tickets through the pipeline and generate a report.

Usage: python evaluate.py
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from src.models import TicketInput, OrderContext
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")

DATA_FILE = Path(__file__).resolve().parent / "data" / "test_tickets.json"
OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)
RESULTS_FILE = OUTPUTS_DIR / "eval_results.json"

# Tickets to print full transcript for
TRANSCRIPT_IDS = {"T006", "T016", "T019"}


def build_order_context(ctx: dict) -> OrderContext:
    return OrderContext(
        order_id=ctx["order_id"],
        order_date=ctx["order_date"],
        delivery_date=ctx.get("delivery_date"),
        item_category=ctx["item_category"],
        fulfillment_type=ctx["fulfillment_type"],
        shipping_region=ctx["shipping_region"],
        order_status=ctx["order_status"],
        payment_method=ctx.get("payment_method"),
    )


def evaluate():
    tickets = json.loads(DATA_FILE.read_text())
    total = len(tickets)

    results = []
    decision_correct = 0
    citation_covered = 0
    escalation_correct = 0
    escalation_total = 0
    unsupported_count = 0

    print(f"\n🔍 Running evaluation on {total} tickets…\n")

    for idx, ticket in enumerate(tickets, 1):
        tid = ticket["id"]
        print(f"  [{idx:02d}/{total}] {tid} ({ticket['category']}) … ", end="", flush=True)

        order_ctx = build_order_context(ticket["order_context"])
        ticket_input = TicketInput(
            ticket_text=ticket["ticket_text"],
            order_context=order_ctx,
        )

        try:
            output = run_pipeline(ticket_input)
            error = None
        except Exception as e:
            error = str(e)
            print(f"❌ ERROR: {e}")
            results.append({
                "id": tid,
                "category": ticket["category"],
                "error": error,
            })
            time.sleep(1)
            continue

        # ── Scoring ────────────────────────────────────────────────────
        expected_decision = ticket.get("expected_decision", "")
        expected_escalation = ticket.get("expected_escalation", False)
        should_abstain = ticket.get("should_abstain", False)

        # Decision accuracy
        decision_match = output.decision == expected_decision
        if decision_match:
            decision_correct += 1

        # Citation coverage
        has_citations = len(output.citations) > 0
        if has_citations:
            citation_covered += 1

        # Escalation rate (for conflict + not-in-policy tickets)
        if expected_escalation or should_abstain:
            escalation_total += 1
            if output.decision == "needs_escalation":
                escalation_correct += 1

        # Unsupported claims
        if output.unsupported_claims_flag:
            unsupported_count += 1

        status = "✅" if decision_match else "⚠️ "
        print(f"{status} decision={output.decision} (expected={expected_decision})")

        result_entry = {
            "id": tid,
            "category": ticket["category"],
            "ticket_text": ticket["ticket_text"],
            "expected_decision": expected_decision,
            "actual_decision": output.decision,
            "decision_match": decision_match,
            "classification": output.classification,
            "confidence": output.confidence,
            "citations": output.citations,
            "has_citations": has_citations,
            "rationale": output.rationale,
            "customer_response_draft": output.customer_response_draft,
            "next_steps": output.next_steps,
            "unsupported_claims_flag": output.unsupported_claims_flag,
            "clarifying_questions": output.clarifying_questions,
        }
        results.append(result_entry)

        # Rate limit buffer
        time.sleep(1)

    # ── Compute metrics ────────────────────────────────────────────────
    processed = len([r for r in results if "error" not in r])
    citation_rate = (citation_covered / processed * 100) if processed else 0
    decision_accuracy = (decision_correct / processed * 100) if processed else 0
    escalation_rate = (escalation_correct / escalation_total * 100) if escalation_total else 0
    unsupported_rate = (unsupported_count / processed * 100) if processed else 0

    report = {
        "run_timestamp": datetime.now().isoformat(),
        "total_tickets": total,
        "processed": processed,
        "metrics": {
            "citation_coverage_rate": round(citation_rate, 1),
            "decision_accuracy": round(decision_accuracy, 1),
            "correct_escalation_rate": round(escalation_rate, 1),
            "unsupported_claims_rate": round(unsupported_rate, 1),
        },
        "results": results,
    }

    RESULTS_FILE.write_text(json.dumps(report, indent=2))

    # ── Print report ───────────────────────────────────────────────────
    print("\n" + "=" * 42)
    print("==== EVALUATION REPORT ====")
    print(f"Total tickets: {total}")
    print(f"Processed:     {processed}")
    print(f"Citation coverage rate:   {citation_rate:.1f}%")
    print(f"Decision accuracy:        {decision_accuracy:.1f}%")
    print(f"Correct escalation rate:  {escalation_rate:.1f}%")
    print(f"Unsupported claims rate:  {unsupported_rate:.1f}%")
    print("=" * 42)
    print(f"\n💾 Full results saved to: {RESULTS_FILE}\n")

    # ── Print selected transcripts ─────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FULL TRANSCRIPTS — Selected Cases")
    print("=" * 60)

    for r in results:
        if r.get("id") in TRANSCRIPT_IDS and "error" not in r:
            print(f"\n── {r['id']} ({r['category'].upper()}) ───────────────────────────")
            print(f"Ticket  : {r['ticket_text']}")
            print(f"Class   : {r['classification']} (confidence: {r['confidence']})")
            print(f"Decision: {r['actual_decision']} (expected: {r['expected_decision']})")
            print(f"Rationale: {r['rationale']}")
            print(f"Citations: {', '.join(r['citations']) if r['citations'] else 'none'}")
            print(f"Response:\n  {r['customer_response_draft']}")
            print(f"Next Steps: {r['next_steps']}")
            print(f"Unsupported Claims Flag: {r['unsupported_claims_flag']}")


if __name__ == "__main__":
    evaluate()
