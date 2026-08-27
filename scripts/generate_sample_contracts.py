"""
generate_sample_contracts.py

Generates sample supplier contracts, SLAs, pricing tables, and internal
procurement policies as PDF documents for the AutoStock-AI RAG pipeline.

Outputs:
  - data/raw/supplier_contracts/vendor_techcorp_msa.pdf
  - data/raw/supplier_contracts/vendor_globalparts_pricing.pdf
  - data/raw/supplier_contracts/vendor_apex_sla.pdf
  - data/raw/supplier_contracts/internal_procurement_policy.pdf
"""

from __future__ import annotations

import os
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    ListFlowable,
    ListItem,
)

OUTPUT_DIR = os.path.join("..", "data", "raw", "supplier_contracts")
# ----------------------------------------------------------------------
# Typography & Shared Styling
# ----------------------------------------------------------------------

_styles = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "DocTitle",
    parent=_styles["Title"],
    fontSize=16,
    spaceAfter=4,
    alignment=TA_LEFT,
)

STYLE_SUBTITLE = ParagraphStyle(
    "DocSubtitle",
    parent=_styles["Normal"],
    fontSize=9.5,
    textColor=colors.HexColor("#444444"),
    spaceAfter=12,
)

STYLE_H1 = ParagraphStyle(
    "H1",
    parent=_styles["Heading1"],
    fontSize=12,
    spaceBefore=12,
    spaceAfter=6,
    textColor=colors.HexColor("#1a1a1a"),
)

STYLE_BODY = ParagraphStyle(
    "Body",
    parent=_styles["BodyText"],
    fontSize=9,
    leading=12.5,
    alignment=TA_LEFT,
    spaceAfter=5,
)

STYLE_BULLET = ParagraphStyle(
    "Bullet",
    parent=STYLE_BODY,
    leftIndent=10,
    spaceAfter=2,
)

TABLE_HEADER_BG = colors.HexColor("#2c3e50")
TABLE_ALT_BG = colors.HexColor("#f8f9fa")


def make_table(header: List[str], rows: List[List[str]], col_widths=None) -> Table:
    """Creates a cleanly structured ReportLab Table."""
    data = [header] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_BG))
    t.setStyle(TableStyle(style))
    return t


def bullets(items: List[str]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(i, STYLE_BULLET), leftIndent=8) for i in items],
        bulletType="bullet",
        start="circle",
        leftIndent=12,
    )


def header_block(title: str, subtitle_lines: List[str]) -> List:
    flow = [Paragraph(title, STYLE_TITLE)]
    for line in subtitle_lines:
        flow.append(Paragraph(line, STYLE_SUBTITLE))
    return flow


def build_pdf(filename: str, story: List) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        title=filename,
    )
    doc.build(story)
    return path


# ----------------------------------------------------------------------
# 1. TechCorp Logistics -- Master Service Agreement (VEND-001)
# ----------------------------------------------------------------------

def build_techcorp_msa() -> str:
    story = []
    story += header_block(
        "Master Service Agreement — TechCorp Logistics",
        [
            "Vendor ID: VEND-001 | Category: Premium / Expedited Electronics Supplier",
            "Effective Scope: SKU-1001 – SKU-1005 (Electronics) | Payment Terms: Net 30",
        ],
    )

    story.append(Paragraph("1. Vendor Profile & Operations", STYLE_H1))
    story.append(Paragraph(
        "TechCorp Logistics is AutoStock-AI's premium electronics supplier, positioned for speed over cost. "
        "TechCorp guarantees the fastest standard lead time on the approved vendor list at a 15–30% premium.",
        STYLE_BODY,
    ))
    story.append(bullets([
        "Standard Lead Time: 3–5 business days from PO confirmation",
        "Expedited Lead Time: 24 hours from PO confirmation (+25% surcharge)",
        "Minimum Order Quantity (MOQ): 20–50 units, varies by SKU",
        "Payment Terms: Net 30 from invoice date",
        "Late Delivery Penalty: 1% of total order value per day of delay, capped at 10%",
    ]))

    story.append(Paragraph("2. Per-SKU Volume Pricing Schedule", STYLE_H1))
    rows = [
        ["SKU-1001", "Optical Sensor", "25", "$18.50", "$17.02", "$15.73"],
        ["SKU-1002", "Microcontroller Board", "20", "$12.75", "$11.73", "$10.84"],
        ["SKU-1003", "Lithium-Ion Battery Pack", "30", "$9.40", "$8.65", "$7.99"],
        ["SKU-1004", "USB-C Interface Module", "50", "$4.20", "$3.86", "$3.57"],
        ["SKU-1005", "OLED Display 128x64", "40", "$6.85", "$6.30", "$5.82"],
    ]
    story.append(make_table(
        ["SKU", "Item", "MOQ", "Tier 1 (MOQ-99)", "Tier 2 (100-249)", "Tier 3 (250+)"],
        rows,
        col_widths=[0.8 * inch, 1.8 * inch, 0.6 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch],
    ))

    story.append(Paragraph("3. Expedited Fulfillment & Reliability", STYLE_H1))
    story.append(bullets([
        "24-hour dispatch applies to eligible in-stock items confirmed before 2:00 PM local vendor time.",
        "Reliability Rating: Current internal score is 8.7 / 10.",
        "Designated preferred vendor for critical replenishments (stockout runway under 3 days).",
    ]))

    return build_pdf("vendor_techcorp_msa.pdf", story)


# ----------------------------------------------------------------------
# 2. GlobalParts Direct -- Pricing & SLA (VEND-002)
# ----------------------------------------------------------------------

def build_globalparts_pricing() -> str:
    story = []
    story += header_block(
        "Master Pricing Schedule — GlobalParts Direct",
        [
            "Vendor ID: VEND-002 | Category: Bulk / Low-Cost Volume Supplier",
            "Effective Scope: SKU-1001 – SKU-1005 & SKU-2001 – SKU-2005 | Payment Terms: 2/10 Net 60",
        ],
    )

    story.append(Paragraph("1. Vendor Profile & Operations", STYLE_H1))
    story.append(Paragraph(
        "GlobalParts Direct offers the lowest per-unit pricing across the full ten-SKU catalog in exchange for "
        "longer lead times and higher minimum order quantities. Ideal for planned bulk restocking.",
        STYLE_BODY,
    ))
    story.append(bullets([
        "Standard Lead Time: 14–21 business days, scaling upward with volume tiers",
        "Expedited Fulfillment: Not available under current contract tier",
        "Minimum Order Quantity (MOQ): 100–250 units depending on SKU",
        "Payment Terms: 2/10 Net 60 (2% discount within 10 days; 30% deposit required for Tier 2/3)",
        "Delay Compensation: Fixed $200 credit per delayed PO, triggered after 5 days of delay",
    ]))

    story.append(Paragraph("2. Per-SKU Volume Pricing Schedule", STYLE_H1))
    rows = [
        ["SKU-1001", "Optical Sensor", "100", "$14.80 / 14d", "$12.95 / 17d", "$10.65 / 21d"],
        ["SKU-1002", "Microcontroller Board", "100", "$10.20 / 14d", "$8.92 / 17d", "$7.34 / 21d"],
        ["SKU-1003", "Lithium-Ion Battery Pack", "150", "$7.55 / 18d", "$6.61 / 20d", "$5.44 / 21d"],
        ["SKU-1004", "USB-C Interface Module", "200", "$3.35 / 14d", "$2.93 / 16d", "$2.41 / 18d"],
        ["SKU-1005", "OLED Display 128x64", "150", "$5.48 / 15d", "$4.79 / 18d", "$3.95 / 21d"],
        ["SKU-2001", "NEMA 17 Stepper Motor", "100", "$11.90 / 16d", "$10.41 / 19d", "$8.57 / 21d"],
        ["SKU-2002", "Linear Rail 300mm", "100", "$8.75 / 16d", "$7.66 / 19d", "$6.30 / 21d"],
        ["SKU-2003", "Aluminum Extrusion 2020", "250", "$2.15 / 14d", "$1.88 / 17d", "$1.55 / 20d"],
        ["SKU-2004", "Ball Bearing 8mm", "250", "$0.62 / 14d", "$0.54 / 16d", "$0.45 / 18d"],
        ["SKU-2005", "Timing Belt GT2", "200", "$1.95 / 15d", "$1.71 / 18d", "$1.40 / 20d"],
    ]
    story.append(make_table(
        ["SKU", "Item", "MOQ", "Tier 1", "Tier 2", "Tier 3"],
        rows,
        col_widths=[0.75 * inch, 1.7 * inch, 0.55 * inch, 1.25 * inch, 1.25 * inch, 1.25 * inch],
    ))

    story.append(Paragraph("3. Reliability Notes", STYLE_H1))
    story.append(Paragraph(
        "Current internal reliability rating: 6.4 / 10. Suitable for orders where stockout runway exceeds 21 days.",
        STYLE_BODY,
    ))

    return build_pdf("vendor_globalparts_pricing.pdf", story)


# ----------------------------------------------------------------------
# 3. Apex Supply Co. -- Service Level Agreement (VEND-003)
# ----------------------------------------------------------------------

def build_apex_sla() -> str:
    story = []
    story += header_block(
        "Service Level Agreement — Apex Supply Co.",
        [
            "Vendor ID: VEND-003 | Category: Balanced Mid-Tier Hardware Supplier",
            "Effective Scope: SKU-2001 – SKU-2005 (Hardware) | Payment Terms: Net 45",
        ],
    )

    story.append(Paragraph("1. Vendor Profile & Operations", STYLE_H1))
    story.append(Paragraph(
        "Apex Supply Co. provides balanced hardware component replenishment with flat 50-unit MOQs and moderate "
        "lead times. Apex does not supply Electronics SKUs.",
        STYLE_BODY,
    ))
    story.append(bullets([
        "Standard Lead Time: 7–10 business days from PO confirmation",
        "Expedited Fulfillment: Not offered under current tier",
        "Minimum Order Quantity (MOQ): Flat 50 units across all contracted SKUs",
        "Payment Terms: Net 45 from invoice date (ACH / wire transfer)",
        "Late Delivery Penalty: None specified; tracked via vendor scorecard",
    ]))

    story.append(Paragraph("2. Hardware Pricing Schedule", STYLE_H1))
    rows = [
        ["SKU-2001", "NEMA 17 Stepper Motor", "50", "$10.15", "$9.24", "8 business days"],
        ["SKU-2002", "Linear Rail 300mm", "50", "$7.60", "$6.92", "9 business days"],
        ["SKU-2003", "Aluminum Extrusion 2020", "50", "$2.85", "$2.59", "7 business days"],
        ["SKU-2004", "Ball Bearing 8mm", "50", "$0.79", "$0.72", "7 business days"],
        ["SKU-2005", "Timing Belt GT2", "50", "$2.35", "$2.14", "10 business days"],
    ]
    story.append(make_table(
        ["SKU", "Item", "MOQ", "Standard (50-199)", "Bulk (200+)", "Lead Time"],
        rows,
        col_widths=[0.75 * inch, 1.8 * inch, 0.55 * inch, 1.3 * inch, 1.2 * inch, 1.2 * inch],
    ))

    story.append(Paragraph("3. Reliability Score", STYLE_H1))
    story.append(Paragraph(
        "Current internal reliability rating: 7.5 / 10. Designated default supplier for standard hardware replenishment.",
        STYLE_BODY,
    ))

    return build_pdf("vendor_apex_sla.pdf", story)


# ----------------------------------------------------------------------
# 4. Internal Procurement Policy
# ----------------------------------------------------------------------

def build_internal_policy() -> str:
    story = []
    story += header_block(
        "Internal Procurement Policy & Governance",
        [
            "Document: Governance Rules & Spending Thresholds",
            "Applies To: Autonomous PO Generation & Supplier Routing",
        ],
    )

    story.append(Paragraph("1. Autonomous Authority Thresholds", STYLE_H1))
    story.append(bullets([
        "Maximum Autonomous PO Value: $5,000.00 total order value. Any order > $5,000 requires human manager approval.",
        "Target Safety Stock Buffer: 14 days of coverage at current daily sales velocity.",
        "Critical Runway Alert: Runway < 3 days triggers priority fast-fulfillment routing.",
        "Mandatory Multi-Quote: Non-critical orders > $1,500 must evaluate at least 2 approved vendors.",
        "Vendor Reliability Floor: Minimum acceptable score is 6.0 / 10.",
    ]))

    return build_pdf("internal_procurement_policy.pdf", story)


# ----------------------------------------------------------------------
# Execution Entry Point
# ----------------------------------------------------------------------

def main() -> None:
    generated = [
        build_techcorp_msa(),
        build_globalparts_pricing(),
        build_apex_sla(),
        build_internal_policy(),
    ]
    print(f"Successfully generated {len(generated)} PDF document(s) in '{OUTPUT_DIR}':")
    for path in generated:
        size_kb = os.path.getsize(path) / 1024
        print(f"  - {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()