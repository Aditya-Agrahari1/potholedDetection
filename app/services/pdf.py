import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def get_scaled_image(
    image_path: str,
    max_width: float = 3.2 * inch,
    max_height: float = 2.2 * inch,
) -> Optional[Image]:
    """Load image, calculate proportional dimensions preserving aspect ratio, and return Flowable Image."""
    if not os.path.exists(image_path):
        return None

    try:
        with PILImage.open(image_path) as img:
            orig_w, orig_h = img.size

        if orig_w == 0 or orig_h == 0:
            return None

        aspect = orig_w / float(orig_h)
        target_w = max_width
        target_h = target_w / aspect

        if target_h > max_height:
            target_h = max_height
            target_w = target_h * aspect

        return Image(image_path, width=target_w, height=target_h)
    except Exception:
        return None


def get_status_color(status: str) -> colors.Color:
    """Return thematic color for defect status."""
    status_lower = status.lower()
    if status_lower in ("worsened", "high"):
        return colors.HexColor("#DC2626")  # Red
    elif status_lower in ("improved", "resolved", "low"):
        return colors.HexColor("#16A34A")  # Green
    elif status_lower in ("persistent", "medium"):
        return colors.HexColor("#D97706")  # Amber
    elif status_lower == "new":
        return colors.HexColor("#2563EB")  # Blue
    return colors.HexColor("#475569")  # Slate gray


class NumberedCanvas:
    """Two-pass canvas to dynamically compute and draw page numbering and footer."""
    pass


def generate_pdf_report(
    report_id: int,
    location_id: int,
    latitude: float,
    longitude: float,
    timestamp: datetime,
    status: str,
    detection_data: Dict[str, Any],
    current_photo_path: str,
    previous_photo_path: Optional[str] = None,
    previous_report_id: Optional[int] = None,
    previous_timestamp: Optional[datetime] = None,
) -> bytes:
    """Generate a high-quality PDF report with metadata, photos, and AI analysis."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
    )
    badge_style = ParagraphStyle(
        "StatusBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        alignment=1,  # Centered
        textColor=colors.white,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    caption_style = ParagraphStyle(
        "ImageCaption",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # 1. HEADER SECTION
    status_bg = get_status_color(status)
    status_badge_text = f"STATUS: {status.upper()}"
    badge_cell = Paragraph(f"<b>{status_badge_text}</b>", badge_style)

    header_table_data = [
        [
            Paragraph("<b>AUTOMATED POTHOLE INSPECTION REPORT</b>", title_style),
            badge_cell,
        ],
        [
            Paragraph(
                "City Infrastructure & Road Surface Defect Monitoring System",
                subtitle_style,
            ),
            "",
        ],
    ]

    header_table = Table(header_table_data, colWidths=[410, 130])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (1, 0), (1, 0), status_bg),
            ("PADDING", (1, 0), (1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E1"), spaceAfter=12))

    # 2. METADATA SUMMARY TABLE
    iso_date = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    prev_info = f"Report #{previous_report_id}" if previous_report_id else "None (Initial Baseline)"
    if previous_timestamp:
        prev_info += f" ({previous_timestamp.strftime('%Y-%m-%d %H:%M')})"

    meta_data = [
        [
            Paragraph("<b>Report ID:</b>", body_style),
            Paragraph(f"#{report_id}", body_style),
            Paragraph("<b>Location ID:</b>", body_style),
            Paragraph(f"#{location_id}", body_style),
        ],
        [
            Paragraph("<b>Latitude:</b>", body_style),
            Paragraph(f"{latitude:.6f}°", body_style),
            Paragraph("<b>Longitude:</b>", body_style),
            Paragraph(f"{longitude:.6f}°", body_style),
        ],
        [
            Paragraph("<b>Inspection Date:</b>", body_style),
            Paragraph(iso_date, body_style),
            Paragraph("<b>Baseline Reference:</b>", body_style),
            Paragraph(prev_info, body_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[90, 180, 110, 160])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 3. PHOTO SECTION
    story.append(Paragraph("<b>Photographic Evidence & Visual Documentation</b>", section_heading))
    story.append(Spacer(1, 6))

    if previous_photo_path and os.path.exists(previous_photo_path):
        # Two-photo comparison view
        old_img = get_scaled_image(previous_photo_path, max_width=3.6 * inch, max_height=2.3 * inch)
        new_img = get_scaled_image(current_photo_path, max_width=3.6 * inch, max_height=2.3 * inch)

        prev_label = f"BASELINE INSPECTION (Report #{previous_report_id or ''})"
        curr_label = f"CURRENT INSPECTION (Report #{report_id})"

        photo_cells = [
            [
                old_img if old_img else Paragraph("Baseline image not found", body_style),
                new_img if new_img else Paragraph("Current image not found", body_style),
            ],
            [
                Paragraph(f"<b>{prev_label}</b>", caption_style),
                Paragraph(f"<b>{curr_label}</b>", caption_style),
            ],
        ]
        photo_table = Table(photo_cells, colWidths=[270, 270])
        photo_table.setStyle(
            TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(photo_table)
    else:
        # Single photo view
        curr_img = get_scaled_image(current_photo_path, max_width=5.5 * inch, max_height=3.0 * inch)
        if curr_img:
            photo_table = Table(
                [[curr_img], [Paragraph(f"<b>INSPECTION IMAGE (Report #{report_id})</b>", caption_style)]],
                colWidths=[540],
            )
            photo_table.setStyle(
                TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(photo_table)
        else:
            story.append(Paragraph("<i>Inspection photo file not found on disk.</i>", body_style))

    story.append(Spacer(1, 14))

    # 4. AI ANALYSIS & CHANGE TRACKING RESULTS
    story.append(Paragraph("<b>Gemini Multimodal Analysis & Defect Assessment</b>", section_heading))
    story.append(Spacer(1, 6))

    analysis_rows = []
    if previous_photo_path:
        # Comparison metrics
        area_change = detection_data.get("area_change_percent", "N/A")
        if isinstance(area_change, (int, float)):
            area_str = f"{area_change:+.1f}%"
        else:
            area_str = str(area_change)

        sev_change = str(detection_data.get("severity_change", "N/A")).capitalize()
        reasoning = str(detection_data.get("reasoning", "Comparative change tracked between timestamps."))

        analysis_rows = [
            [
                Paragraph("<b>Progression Status:</b>", body_style),
                Paragraph(f"<b>{status.capitalize()}</b>", body_style),
                Paragraph("<b>Area Change (%):</b>", body_style),
                Paragraph(f"<b>{area_str}</b>", body_style),
            ],
            [
                Paragraph("<b>Severity Change:</b>", body_style),
                Paragraph(f"<b>{sev_change}</b>", body_style),
                Paragraph("<b>Comparative Notes:</b>", body_style),
                Paragraph(reasoning, body_style),
            ],
        ]
    else:
        # Single-image detection metrics
        count = detection_data.get("count", len(detection_data.get("detections", [])))
        overall_sev = str(detection_data.get("overall_severity", "medium")).capitalize()
        potholes_found = "Yes" if detection_data.get("potholes_detected", True) else "No"

        analysis_rows = [
            [
                Paragraph("<b>Potholes Detected:</b>", body_style),
                Paragraph(f"<b>{potholes_found}</b>", body_style),
                Paragraph("<b>Defect Count:</b>", body_style),
                Paragraph(f"<b>{count}</b>", body_style),
            ],
            [
                Paragraph("<b>Overall Severity:</b>", body_style),
                Paragraph(f"<b>{overall_sev}</b>", body_style),
                Paragraph("<b>Classification:</b>", body_style),
                Paragraph("New Baseline Registration", body_style),
            ],
        ]

    analysis_table = Table(analysis_rows, colWidths=[120, 150, 120, 150])
    analysis_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(analysis_table)
    story.append(Spacer(1, 12))

    # 5. REPORT SUMMARY BOX
    story.append(Paragraph("<b>Executive Summary & Recommended Maintenance Action</b>", section_heading))
    story.append(Spacer(1, 6))

    summary_text = detection_data.get(
        "report_summary",
        "Visual road inspection complete. Automated defect classification processed by Gemini AI.",
    )
    summary_cell = Paragraph(f"<b>AI Inspection Findings:</b><br/>{summary_text}", body_style)

    summary_box = Table([[summary_cell]], colWidths=[540])
    summary_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(summary_box)
    story.append(Spacer(1, 16))

    # 6. FOOTER NOTICE
    footer_text = (
        "<i>Notice: This document is automatically generated by the Automated Pothole Detection & Change-Tracking System. "
        "Road authority engineers should cross-verify prior to structural civil repairs.</i>"
    )
    story.append(Paragraph(footer_text, subtitle_style))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
