"""Sample-output generator: the single artifact a customer would actually see.
Writes CSV, a standalone HTML page, and a PDF from the same rows.

    from core.samples import write_all
    paths = write_all(rows, columns, out_dir, title="...", subtitle="...",
                      notes=[...], source_line="...")
columns: list of field names, or (field, "Label") tuples.
"""
import csv
import html
from datetime import date
from pathlib import Path

from .pdfmini import Pdf

CSS = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:24px;color:#1b1b1b;background:#fff}
h1{margin:0 0 4px;font-size:22px} .sub{color:#555;margin:0 0 16px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid #e3e3e3;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f3f3f3;position:sticky;top:0} tr:nth-child(even) td{background:#fafafa}
.note{font-size:12px;color:#555;margin:14px 0}
.foot{font-size:11px;color:#777;margin-top:22px;border-top:1px solid #ddd;padding-top:8px}
.kpi{display:inline-block;margin:0 18px 12px 0;padding:8px 12px;border:1px solid #ddd;border-radius:6px}
.kpi b{display:block;font-size:20px}
@media (prefers-color-scheme: dark){body{background:#111;color:#eee} th{background:#222}
 tr:nth-child(even) td{background:#181818} td,th{border-color:#333} .sub,.note,.foot{color:#aaa}}
"""


def _cols(columns):
    return [(c if isinstance(c, tuple) else (c, c)) for c in columns]


def _cell(r, k):
    v = r.get(k, "")
    return "" if v is None else str(v)


def write_csv(rows, columns, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _cols(columns)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([lbl for _, lbl in cols])
        for r in rows:
            w.writerow([_cell(r, k) for k, _ in cols])
    return path


def write_html(rows, columns, path, title, subtitle="", notes=(), source_line="", kpis=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _cols(columns)
    h = ["<!doctype html><html><head><meta charset='utf-8'>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'>",
         f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>",
         f"<h1>{html.escape(title)}</h1>", f"<p class='sub'>{html.escape(subtitle)}</p>"]
    if kpis:
        h.append("<div>" + "".join(
            f"<span class='kpi'><b>{html.escape(str(v))}</b>{html.escape(k)}</span>" for k, v in kpis) + "</div>")
    h.append("<table><thead><tr>" + "".join(f"<th>{html.escape(lbl)}</th>" for _, lbl in cols) + "</tr></thead><tbody>")
    for r in rows:
        h.append("<tr>" + "".join(f"<td>{html.escape(_cell(r, k))}</td>" for k, _ in cols) + "</tr>")
    h.append("</tbody></table>")
    for n in notes:
        h.append(f"<p class='note'>{html.escape(n)}</p>")
    h.append(f"<p class='foot'>{html.escape(source_line)} Generated {date.today().isoformat()} "
             "by Idea Factory (validation sample, not a live product).</p></body></html>")
    path.write_text("\n".join(h), encoding="utf-8")
    return path


def write_pdf(rows, columns, path, title, subtitle="", notes=(), source_line="", widths=None, max_rows=60,
              landscape=False, font_size=8, max_cell_lines=None):
    """widths: per-column point widths; usable width is 532pt portrait, 712pt landscape (Letter, 40pt margins).
    Cells wrap (real Helvetica metrics, see core.pdfmini); max_cell_lines caps a cell's height with '...'."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _cols(columns)
    pdf = Pdf(landscape=landscape)
    pdf.text(title, 16, bold=True)
    if subtitle:
        pdf.paragraph(subtitle, 10, color=(0.3, 0.3, 0.3))
    pdf.gap(6)
    pdf.table([lbl for _, lbl in cols], [[_cell(r, k) for k, _ in cols] for r in rows[:max_rows]], widths=widths,
              size=font_size, max_lines=max_cell_lines)
    if len(rows) > max_rows:
        pdf.gap(4)
        pdf.text(f"... {len(rows) - max_rows} more rows in the CSV.", 8)
    pdf.gap(8)
    for n in notes:
        pdf.paragraph(n, 9)
    pdf.gap(6)
    pdf.paragraph(f"{source_line} Generated {date.today().isoformat()} by Idea Factory (validation sample).", 8)
    pdf.save(path)
    return path


def write_all(rows, columns, out_dir, title, subtitle="", notes=(), source_line="", basename="sample",
              pdf_widths=None, kpis=None, landscape=False, pdf_font_size=8, pdf_max_cell_lines=None):
    out_dir = Path(out_dir)
    return {
        "csv": write_csv(rows, columns, out_dir / f"{basename}.csv"),
        "html": write_html(rows, columns, out_dir / f"{basename}.html", title, subtitle, notes, source_line, kpis),
        "pdf": write_pdf(rows, columns, out_dir / f"{basename}.pdf", title, subtitle, notes, source_line, pdf_widths,
                         landscape=landscape, font_size=pdf_font_size, max_cell_lines=pdf_max_cell_lines),
    }
