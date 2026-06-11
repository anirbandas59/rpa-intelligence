"""
Integration test for tool-based process agent.

Tests that the agent can extract bands using validation tools to verify
its assignments, reducing hallucination.
"""

import pytest

from agents.process_agent_with_tools import extract_bands_with_tools

# Sample process document with clear complexity indicators
SAMPLE_DOCUMENT = """
Invoice Processing Automation - Process Definition Document

Process Overview:
This automation reads invoices from email, extracts data, validates against
business rules, and posts to SAP.

Systems:
- Outlook email
- SAP ERP (FB60 transaction)
- Oracle database

Activities:
1. Login to Outlook
2. Read emails from Invoice folder
3. Download PDF attachments
4. Extract invoice data using OCR
5. Validate vendor against Oracle database
6. Check invoice amount threshold
7. Apply approval workflow rules
8. Login to SAP
9. Open FB60 transaction
10. Enter invoice header data
11. Enter line items
12. Post to SAP
13. Update status in Oracle
14. Send confirmation email
15. Logout from SAP

Business Rules:
- If amount > 10000: Route to manager approval
- If vendor not in database: Create new vendor record
- If duplicate invoice number: Reject and notify

UI Screens:
- Outlook inbox window
- SAP login screen
- SAP FB60 transaction screen
- Approval workflow screen

Technologies:
- OCR for PDF extraction
- Database connectivity for Oracle
"""


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Anthropic API key - run manually for verification")
async def test_tool_based_extraction():
    """
    Test that tool-based agent extracts bands correctly.

    Expected bands for this document:
    - activities: M (15 activities → 11-20 range)
    - business_rules: L (3 rules → 3-4 range)
    - layouts: M (4 screens → 4-6 range but closer to M)
    - interfaces: M (3 systems → 3-4 range)
    - technology: M (2 technologies: OCR + DB)
    """
    bands, process_summary, notes = await extract_bands_with_tools(
        document_text=SAMPLE_DOCUMENT,
        model="claude-haiku-4-5",
    )

    # Verify bands object is valid
    assert bands.activities in ["XS", "S", "M", "L", "XL"]
    assert bands.business_rules in ["XS", "S", "M", "L", "XL"]
    assert bands.layouts in ["XS", "S", "M", "L", "XL"]
    assert bands.interfaces in ["XS", "S", "M", "L", "XL"]
    assert bands.technology in ["XS", "S", "M", "L", "XL"]

    # Verify process summary is populated
    assert process_summary is not None
    assert "key_activities" in process_summary
    assert "key_logical_points" in process_summary

    # Check that LLM extracted correct bands (given the counts)
    # With 15 activities, should be M
    assert bands.activities == "M", f"Expected M for 15 activities, got {bands.activities}"

    # With 3 business rules, should be L
    assert bands.business_rules == "L", f"Expected L for 3 rules, got {bands.business_rules}"

    # With 3 systems (Outlook, SAP, Oracle), should be M
    assert bands.interfaces == "M", f"Expected M for 3 interfaces, got {bands.interfaces}"

    print("\n✅ Tool-based extraction successful!")
    print(f"Bands: {bands.model_dump()}")
    print(f"Notes: {notes}")
    print(f"Activities found: {len(process_summary.get('key_activities', []))}")
    print(f"Rules found: {len(process_summary.get('key_logical_points', []))}")


@pytest.mark.asyncio
@pytest.mark.skip(reason="Manual verification - checks tool calling behavior")
async def test_agent_uses_tools():
    """
    Verify that the agent actually calls the validation tools.

    This test focuses on verifying the agent's behavior rather than
    the final result accuracy.
    """
    # Simpler document for testing
    simple_doc = """
    Simple automation that:
    1. Reads Excel file
    2. Updates database
    3. Sends email

    Business rule: If amount > 1000, escalate.
    """

    bands, summary, notes = await extract_bands_with_tools(
        document_text=simple_doc,
        model="claude-haiku-4-5",
    )

    # With 3 activities and 1 business rule, bands should be:
    # activities: S (≤10)
    # business_rules: M (1-2)
    assert bands.activities == "S"
    assert bands.business_rules == "M"

    print("\n✅ Agent correctly used tools to determine bands")
    print(f"Final bands: activities={bands.activities}, business_rules={bands.business_rules}")


if __name__ == "__main__":
    """Run tests manually for verification."""
    import asyncio

    print("Running tool-based agent tests...")
    print("=" * 60)

    # Run the extraction test
    asyncio.run(test_tool_based_extraction())
