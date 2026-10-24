"""Portable server-side exports using the existing Python application runtime."""

from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.models.living import Asset


def metadata(asset: Asset) -> str:
    generated = datetime.fromisoformat(asset.content["generated_at"]).strftime(
        "%d %b %Y, %H:%M UTC"
    )
    return f"MiSi | Version {asset.version} | {asset.review_status.upper()} | {generated} | Local review only"


def export_docx(asset: Asset) -> bytes:
    doc = Document()
    page = doc.sections[0]
    page.page_width, page.page_height = Inches(8.27), Inches(11.69)
    page.top_margin = page.bottom_margin = Inches(0.7)
    page.left_margin = page.right_margin = Inches(0.7)
    for name in ["Normal", "Title", "Subtitle", "Heading 1", "Heading 2"]:
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.color.rgb = RGBColor(0, 0, 0)
    doc.styles["Normal"].font.size = Pt(10)
    doc.styles["Normal"].paragraph_format.space_after = Pt(7)
    doc.styles["Heading 1"].font.size = Pt(15)
    doc.styles["Heading 1"].paragraph_format.keep_with_next = True
    doc.add_paragraph(asset.title.replace("&", "and"), "Title")
    doc.add_paragraph(metadata(asset), "Subtitle")
    page.header.paragraphs[0].text = "MiSi   /   Commercial intelligence"
    page.footer.paragraphs[0].text = (
        f"Version {asset.version} · {asset.review_status} · Source-bound working document"
    )
    for section in asset.content["sections"]:
        doc.add_heading(section["title"], level=1)
        for paragraph in section["paragraphs"]:
            doc.add_paragraph(str(paragraph))
        if section["columns"]:
            table = doc.add_table(rows=1, cols=len(section["columns"]))
            table.style = "Light Shading Accent 1"
            for i, heading in enumerate(section["columns"]):
                table.rows[0].cells[i].text = heading
                for run in table.rows[0].cells[i].paragraphs[0].runs:
                    run.bold = True
            from docx.oxml import OxmlElement

            repeat = OxmlElement("w:tblHeader")
            table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in section["rows"]:
                cells = table.add_row().cells
                for i, value in enumerate(row):
                    cells[i].text = str(value)
            doc.add_paragraph()
    doc.add_heading("Source register", level=1)
    for source in asset.content["sources"]:
        doc.add_paragraph(
            f"{source['reference']} · {source['title']} · {source['type']} · {source['timestamp']}"
            + (" · " + "; ".join(source.get("urls", [])) if source.get("urls") else "")
        )
    doc.core_properties.title = asset.title
    doc.core_properties.author = "MiSi"
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


def export_pdf(asset: Asset) -> bytes:
    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=(210 * mm, 297 * mm),
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=22 * mm,
        bottomMargin=19 * mm,
        title=asset.title,
        author="MiSi",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Subtitle",
            parent=styles["BodyText"],
            fontSize=10,
            textColor=colors.HexColor("#436054"),
            spaceAfter=10,
        )
    )
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 24
    styles["Title"].leading = 28
    styles["Heading1"].fontSize = 14
    styles["Heading1"].leading = 18
    styles["Heading1"].spaceBefore = 15
    styles["BodyText"].fontSize = 10
    styles["BodyText"].leading = 14
    styles["BodyText"].spaceAfter = 7
    small = ParagraphStyle(
        "Cell", parent=styles["BodyText"], fontSize=8, leading=11, spaceAfter=0
    )
    head = ParagraphStyle(
        "HeaderCell", parent=small, textColor=colors.white, fontName="Helvetica-Bold"
    )

    def p(text, style="BodyText"):
        return Paragraph(
            escape(str(text)).replace("\n", "<br/>"),
            styles[style] if isinstance(style, str) else style,
        )

    story = [
        p("COMMERCIAL INTELLIGENCE / MiSi", "Subtitle"),
        p(asset.title, "Title"),
        p(metadata(asset), small),
        Spacer(1, 8 * mm),
    ]
    for section in asset.content["sections"]:
        story.append(p(section["title"], "Heading1"))
        story.extend(p(paragraph) for paragraph in section["paragraphs"])
        if section["columns"]:
            n = len(section["columns"])
            rows = [[p(c, head) for c in section["columns"]]] + [
                [p(v, small) for v in row] for row in section["rows"]
            ]
            widths = [176 * mm / n] * n
            if n == 5:
                widths = [34 * mm, 55 * mm, 30 * mm, 29 * mm, 28 * mm]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17342d")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.HexColor("#f1f5f3"), colors.white],
                        ),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 7),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story += [table, Spacer(1, 3 * mm)]
    story.append(p("Source register", "Heading1"))
    for source in asset.content["sources"]:
        story.append(
            p(
                f"{source['reference']} | {source['title']} | {source['type']} | {source['timestamp']}"
                + (
                    " | " + "; ".join(source.get("urls", []))
                    if source.get("urls")
                    else ""
                ),
                small,
            )
        )
        story.append(Spacer(1, 2 * mm))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#436054"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            17 * mm,
            13 * mm,
            f"MiSi  |  {asset.review_status.upper()}  |  Version {asset.version}",
        )
        canvas.drawRightString(193 * mm, 13 * mm, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def safe_text(value):
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def export_xlsx(asset: Asset) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    currency_format = '"£"#,##0.00;[Red]("£"#,##0.00);"£"0.00'

    def sheet(name, headings, rows, money_columns=()):
        ws = wb.create_sheet(name)
        ws.append([safe_text(h) for h in headings])
        for row in rows:
            ws.append([safe_text(v) for v in row])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.sheet_view.showGridLines = False
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="17342D")
            cell.font = Font(color="FFFFFF", bold=True, size=11)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[1].height = 34
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(
                    name="Calibri",
                    size=11,
                    color=(
                        "174A74" if isinstance(cell.value, (int, float)) else "25362E"
                    ),
                )
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                if cell.column in money_columns:
                    cell.number_format = currency_format
            ws.row_dimensions[row[0].row].height = 36
        for col in range(1, len(headings) + 1):
            ws.column_dimensions[get_column_letter(col)].width = (
                26 if col in money_columns else 34
            )
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:1"
        return ws

    content = asset.content
    finance = content["finance"]
    summary = sheet(
        "Summary",
        ["Measure", "GBP or detail", "Basis"],
        [
            ["Asset", asset.title, metadata(asset)],
            ["Financial year", finance["financial_year"], "April to March"],
            [
                "Secured revenue",
                finance["secured_revenue"],
                "Recorded won work; not cash received",
            ],
            [
                "Weighted open revenue",
                finance["open_weighted_revenue"],
                "FY open revenue × probability",
            ],
            [
                "Risk adjusted open revenue",
                finance["risk_adjusted_revenue"],
                "Weighted open less recorded risk adjustment",
            ],
            [
                "LE1 revenue",
                finance["forecast_to_financial_year_end"],
                "Secured + risk adjusted open",
            ],
            [
                "LE1 margin",
                finance["forecast_margin_to_financial_year_end"],
                "From existing backend finance service",
            ],
            [
                "Review status",
                asset.review_status,
                "Local review is not authenticated enterprise approval",
            ],
        ],
        (2,),
    )
    secured = finance["secured_work"]
    opened = finance["open_opportunities"]

    # Preserve the service's columns without guessing finance field definitions.
    def records_sheet(name, records):
        if not records:
            return sheet(name, ["Status"], [["No recorded rows"]])
        keys = list(records[0])
        return sheet(
            name,
            [key.replace("_", " ") for key in keys],
            [
                [
                    (
                        r.get(k)
                        if not isinstance(r.get(k), (dict, list))
                        else str(r.get(k))
                    )
                    for k in keys
                ]
                for r in records
            ],
        )

    records_sheet("Secured work", secured)
    records_sheet("Open pipeline", opened)
    monthly = sheet(
        "Monthly forecast",
        ["Month", "Revenue GBP", "Margin GBP"],
        [
            [r["month"], r["value"], m["value"]]
            for r, m in zip(
                finance["monthly_revenue"], finance["monthly_margin"], strict=True
            )
        ],
        (2, 3),
    )
    monthly.append(["FY total", "=SUM(B2:B13)", "=SUM(C2:C13)"])
    monthly["B14"].number_format = monthly["C14"].number_format = currency_format
    summary.append(
        [
            "Revenue reconciliation",
            "='Monthly forecast'!B14-B7",
            "Should equal zero within £0.02 monthly rounding tolerance",
        ]
    )
    # Correct row references: LE1 is summary row 7; margin is row 8.
    summary.append(
        [
            "Margin reconciliation",
            "='Monthly forecast'!C14-B8",
            "Should equal zero within £0.02 monthly rounding tolerance",
        ]
    )
    records_sheet("Movement", content["movements"]["changes"])
    sources = [
        [
            s["reference"],
            s["title"],
            s["type"],
            s["timestamp"],
            "; ".join(s.get("urls", [])),
        ]
        for s in content["sources"]
    ]
    sheet(
        "Sources",
        ["Record ID", "Title", "Provenance", "Captured", "Source URLs"],
        sources,
    )
    sheet(
        "Validation",
        ["Warning", "Required action"],
        [
            [
                "Forecast definitions await Finance approval",
                "Reconcile with approved LE1 policies before use",
            ],
            [
                "Synthetic fixtures are not market evidence",
                "Validate against approved source records",
            ],
            [
                "Scenario shares and cost ratios are hypotheses",
                "Obtain Operations and Finance review",
            ],
            [
                "Local reviewer is unauthenticated",
                "Enterprise deployment requires Entra ID and server roles",
            ],
        ],
    )
    if content["scenario"]:
        s = content["scenario"]
        a = s["assumptions"]
        inputs = sheet(
            "Scenario inputs",
            ["Assumption", "Value", "Source"],
            [
                ["Annual revenue", float(a["annual_revenue"]), a["assumption_note"]],
                [
                    "Baseline self delivery",
                    float(a["baseline_share"]),
                    "Saved user modelling input; unverified",
                ],
                [
                    "Proposed self delivery",
                    float(a["proposed_share"]),
                    "Saved user modelling input; unverified",
                ],
                [
                    "In house cost ratio",
                    float(a["inhouse_cost_ratio"]),
                    "Hypothesis to validate",
                ],
                [
                    "Subcontract cost ratio",
                    float(a["subcontract_cost_ratio"]),
                    "Hypothesis to validate",
                ],
                ["Probability", float(a["probability"]), "Recorded user assumption"],
                [
                    "Bid expenditure",
                    float(a["bid_cost"]),
                    "Incurred irrespective of award",
                ],
                [
                    "Mobilisation",
                    float(a["mobilisation_cost"]),
                    "Incremental proposed cost on award",
                ],
                [
                    "Payment delay days",
                    a["payment_delay_days"],
                    "Working capital proxy only",
                ],
            ],
        )
        for r in range(3, 8):
            inputs.cell(r, 2).number_format = "0.0%"
        for r in [2, 8, 9]:
            inputs.cell(r, 2).number_format = currency_format
        model = sheet(
            "Scenario model",
            ["Measure", "Baseline GBP", "Proposed GBP", "Difference GBP"],
            [
                ["Annual gross margin", None, None, None],
                ["Expected contribution", None, None, None],
            ],
            (2, 3, 4),
        )
        model["B2"] = (
            "='Scenario inputs'!B2*(1-'Scenario inputs'!B3*'Scenario inputs'!B5-(1-'Scenario inputs'!B3)*'Scenario inputs'!B6)"
        )
        model["C2"] = (
            "='Scenario inputs'!B2*(1-'Scenario inputs'!B4*'Scenario inputs'!B5-(1-'Scenario inputs'!B4)*'Scenario inputs'!B6)"
        )
        model["D2"] = "=C2-B2"
        model["B3"] = "='Scenario inputs'!B7*B2-'Scenario inputs'!B8"
        model["C3"] = (
            "='Scenario inputs'!B7*(C2-'Scenario inputs'!B9)-'Scenario inputs'!B8"
        )
        model["D3"] = "=C3-B3"
        sheet(
            "Sensitivity",
            ["In house ratio", "Annual margin GBP", "Expected contribution GBP"],
            [
                [
                    float(r["inhouse_cost_ratio"]),
                    float(r["gross_margin"]),
                    float(r["expected_contribution"]),
                ]
                for r in s["result"]["sensitivity"]
            ],
            (2, 3),
        )
    wb.calculation.fullCalcOnLoad = True
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
