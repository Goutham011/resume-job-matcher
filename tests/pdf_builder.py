from io import BytesIO


def make_pdf(items, width=612, height=792):
    parts = []
    for x, y_top, text in items:
        y = height - y_top
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        parts.append(f"BT /F1 11 Tf {x} {y} Td ({escaped}) Tj ET")

    content = "\n".join(parts).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ).encode(),
        (
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = b"%PDF-1.4\n"
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()

    return out


def pdf_bytes(items, width=612, height=792):
    return BytesIO(make_pdf(items, width, height))


CLEAN_LINES = [
    (50, 60, "Goutham Sai"),
    (50, 80, "goutham@example.com | +1 555 123 4567 | linkedin.com/in/goutham"),
    (50, 120, "Experience"),
    (50, 140, "Built REST API services in Python and FastAPI for three years."),
    (50, 160, "Led a team of three engineers migrating twelve services to Docker."),
    (50, 180, "Designed PostgreSQL schemas processing over ten thousand orders."),
    (50, 200, "Automated nightly data checks saving the team ten hours weekly."),
    (50, 220, "Mentored two junior developers and reviewed hundreds of pull requests."),
    (50, 240, "Cut cloud costs by aligning AWS instances with real demand."),
    (50, 280, "Skills"),
    (50, 300, "Python, FastAPI, SQL, Docker, AWS, Git, Linux, Kubernetes"),
    (50, 340, "Education"),
    (50, 360, "Bachelor of Technology in Computer Science, 2022"),
]
