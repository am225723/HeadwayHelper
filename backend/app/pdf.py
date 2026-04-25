def html_to_pdf_bytes(html: str) -> bytes:
    text = _strip_tags(html)
    stream = f"BT /F1 10 Tf 50 760 Td 14 TL ({_escape_pdf(text[:3500])}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode())} >> stream\n{stream}\nendstream endobj",
    ]
    body = "%PDF-1.4\n" + "\n".join(objects) + "\n"
    offsets = [0]
    cursor = len("%PDF-1.4\n")
    for obj in objects:
        offsets.append(cursor)
        cursor += len((obj + "\n").encode())
    xref_start = len(body.encode())
    xref = ["xref", f"0 {len(offsets)}", "0000000000 65535 f "]
    xref.extend(f"{offset:010d} 00000 n " for offset in offsets[1:])
    trailer = f"\ntrailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    return (body + "\n".join(xref) + trailer).encode()


def _strip_tags(html: str) -> str:
    out: list[str] = []
    inside = False
    for char in html:
        if char == "<":
            inside = True
            out.append(" ")
        elif char == ">":
            inside = False
        elif not inside:
            out.append(char)
    return " ".join("".join(out).split())


def _escape_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
