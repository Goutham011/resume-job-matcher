from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

DATA_TABLE_MIN_CELLS = 2
DECORATIVE_IMAGE_MAX_AREA_RATIO = 0.005


def _iter_block_elements(parent_element):
    for child in parent_element.iterchildren():
        if child.tag == qn("w:p"):
            yield "paragraph", child
        elif child.tag == qn("w:tbl"):
            yield "table", child
        elif child.tag == qn("w:sdt"):
            for content in child.iterchildren(qn("w:sdtContent")):
                yield from _iter_block_elements(content)


def _append_line(lines, text):
    text = (text or "").strip()
    if text and (not lines or lines[-1] != text):
        lines.append(text)


def _textbox_lines(element, document):
    lines = []
    for box in element.iter(qn("w:txbxContent")):
        for box_paragraph in box.iter(qn("w:p")):
            _append_line(lines, Paragraph(box_paragraph, document).text)
    return lines


def _table_lines(table):
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_text = cell.text.strip()
            if cell_text and cell_text not in cells:
                cells.append(cell_text)
        if cells:
            _append_line(lines, " | ".join(cells))
    return lines


def _count_cells(table):
    try:
        return len(table.rows) * len(table.columns)
    except Exception:
        return 0


def _zone_lines(zone, document, has_text_boxes):
    lines = []
    try:
        paragraphs = zone.paragraphs
    except Exception:
        return lines, has_text_boxes

    for paragraph in paragraphs:
        _append_line(lines, paragraph.text)

    try:
        tables = zone.tables
    except Exception:
        tables = []
    for table in tables:
        for line in _table_lines(table):
            _append_line(lines, line)

    zone_element = getattr(zone, "_element", None)
    if zone_element is None:
        return lines, has_text_boxes

    if next(zone_element.iter(qn("w:txbxContent")), None) is not None:
        has_text_boxes = True
        for line in _textbox_lines(zone_element, document):
            _append_line(lines, line)
    return lines, has_text_boxes


def _section_zone_lines(document, has_text_boxes):
    lines = []
    for section in document.sections:
        for zone in (section.header, section.footer):
            zone_lines, has_text_boxes = _zone_lines(zone, document, has_text_boxes)
            for line in zone_lines:
                _append_line(lines, line)
    return lines, has_text_boxes


def _largest_image_area_ratio(document):
    page_area = 0.0
    for section in document.sections:
        width = section.page_width
        height = section.page_height
        if width and height:
            page_area = max(page_area, float(width) * float(height))
    if page_area <= 0:
        return 0.0

    largest = 0.0
    for drawing in document.element.body.iter(qn("w:drawing")):
        if next(drawing.iter(qn("w:txbxContent")), None) is not None:
            continue
        extent = next(drawing.iter(qn("wp:extent")), None)
        if extent is None:
            continue
        cx = float(extent.get("cx") or 0)
        cy = float(extent.get("cy") or 0)
        largest = max(largest, cx * cy)
    return largest / page_area


def _has_multi_column(document):
    for section in document.sections:
        for cols in section._sectPr.xpath("./w:cols"):
            num = cols.get(qn("w:num"))
            if num and int(num) > 1:
                return True
    return False


def build_docx_evidence(document):
    has_text_boxes = (
        next(document.element.body.iter(qn("w:txbxContent")), None) is not None
    )
    zone_lines, has_text_boxes = _section_zone_lines(document, has_text_boxes)

    body_lines = []
    data_table_count = 0

    for kind, element in _iter_block_elements(document.element.body):
        if kind == "paragraph":
            _append_line(body_lines, Paragraph(element, document).text)
        else:
            table = Table(element, document)
            if _count_cells(table) >= DATA_TABLE_MIN_CELLS:
                data_table_count += 1
            for line in _table_lines(table):
                _append_line(body_lines, line)

        for line in _textbox_lines(element, document):
            _append_line(body_lines, line)

    image_count = 0
    for drawing in document.element.body.iter(qn("w:drawing")):
        if next(drawing.iter(qn("w:txbxContent")), None) is None:
            image_count += 1
    for pict in document.element.body.iter(qn("w:pict")):
        if next(pict.iter(qn("w:txbxContent")), None) is None:
            image_count += 1

    return {
        "body_lines": body_lines,
        "zone_lines": zone_lines,
        "data_table_count": data_table_count,
        "has_text_boxes": has_text_boxes,
        "image_count": image_count,
        "largest_image_area_ratio": _largest_image_area_ratio(document),
        "multi_column": _has_multi_column(document),
    }
