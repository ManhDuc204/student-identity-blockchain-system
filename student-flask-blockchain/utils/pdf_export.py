import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def export_students_pdf(students_list, output_dir: str = None) -> str:
    """Export a simple PDF table-like list.

    Returns absolute path to generated pdf.
    """
    # Default output under static/exports
    if output_dir is None:
        # caller typically passes file paths; keep conservative.
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "exports")

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"students_{ts}.pdf"
    pdf_path = os.path.join(output_dir, filename)

    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    x_margin = 40
    y = height - 60
    line_height = 16

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_margin, y, "Students Export")
    y -= 24
    c.setFont("Helvetica", 10)
    c.drawString(x_margin, y, f"Generated: {datetime.utcnow().isoformat()}Z")
    y -= 24

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_margin, y, "Student ID")
    c.drawString(x_margin + 120, y, "Full Name")
    c.drawString(x_margin + 330, y, "Class")
    y -= 18

    c.setFont("Helvetica", 10)
    for s in students_list:
        if y < 80:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 60

        c.drawString(x_margin, y, (s.student_id or "")[:18])
        c.drawString(x_margin + 120, y, (s.full_name or "")[:28])
        c.drawString(x_margin + 330, y, (s.student_class or "")[:18])
        y -= line_height

    c.save()
    return pdf_path

