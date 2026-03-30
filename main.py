"""
main.py — Interactive single-ticket runner.

Usage: python main.py
Prompts user for ticket text, uses a hardcoded sample order context,
then prints the full AgentOutput as formatted JSON.
"""
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on the path when running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from src.models import TicketInput, OrderContext
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

SAMPLE_ORDER = OrderContext(
    order_id="ORD-20250301-9823",
    order_date="2025-02-25",
    delivery_date="2025-03-05",
    item_category="perishable",
    fulfillment_type="first-party",
    shipping_region="US",
    order_status="delivered",
    payment_method="credit_card",
)


def main():
    print("=" * 60)
    print("  E-Commerce Support Resolution Agent")
    print("=" * 60)
    print("\nUsing sample order context:")
    print(f"  Order ID     : {SAMPLE_ORDER.order_id}")
    print(f"  Item Category: {SAMPLE_ORDER.item_category}")
    print(f"  Region       : {SAMPLE_ORDER.shipping_region}")
    print(f"  Status       : {SAMPLE_ORDER.order_status}")
    print()

    print("Enter your support ticket text (press Enter twice when done):")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)

    ticket_text = "\n".join(lines).strip()
    if not ticket_text:
        print("❌ No ticket text provided. Exiting.")
        sys.exit(1)

    print("\n⏳ Processing ticket through 4-agent pipeline…\n")

    ticket_input = TicketInput(
        ticket_text=ticket_text,
        order_context=SAMPLE_ORDER,
    )

    try:
        result = run_pipeline(ticket_input)
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        raise

    print("\n" + "=" * 60)
    print("  RESOLUTION OUTPUT")
    print("=" * 60 + "\n")
    print(json.dumps(result.model_dump(), indent=2))
    print()


if __name__ == "__main__":
    main()
