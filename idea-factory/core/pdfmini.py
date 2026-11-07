"""Tiny dependency-free PDF writer: title, wrapped paragraphs and a wrapped table, Helvetica only.
Good enough for a one-page lead sheet or alert a customer would receive.

Text is measured with the real Helvetica / Helvetica-Bold glyph widths (standard AFM metrics), so
table cells wrap onto extra lines instead of overflowing into the next column. Rows grow to fit
their tallest cell; the header row repeats on every page.
"""

# Standard Adobe AFM advance widths (1/1000 em) for printable ASCII 32..126.
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
         1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
         333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
         556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELV_B = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
           556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
           975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
           667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
           333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
           611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]


def text_width(s, size, bold=False):
    """Width in points of s set in Helvetica(-Bold) at `size`."""
    tbl = _HELV_B if bold else _HELV
    w = 0
    for ch in str(s):
        o = ord(ch)
        w += tbl[o - 32] if 32 <= o <= 126 else 556
    return w * size / 1000.0


def wrap(s, width, size, bold=False):
    """Word-wrap s to lines no wider than `width` points. Over-long single words are split by character."""
    out = []
    for para in str(s if s is not None else "").split("\n"):
        line = ""
        for word in para.split():
            cand = word if not line else line + " " + word
            if text_width(cand, size, bold) <= width:
                line = cand
                continue
            if line:
                out.append(line)
            # word alone wider than the column: hard-break it
            while text_width(word, size, bold) > width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(word[:cut], size, bold) > width:
                    cut -= 1
                out.append(word[:cut])
                word = word[cut:]
            line = word
        out.append(line)
    return out or [""]


def _esc(s):
    return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _latin1(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")


class Pdf:
    W, H, M = 612, 792, 40  # US Letter portrait, 40pt margin

    def __init__(self, landscape=False):
        if landscape:  # US Letter landscape: wide tables (10+ columns) fit without truncation
            self.W, self.H = 792, 612
        self.pages = []
        self._new_page()

    @property
    def usable_width(self):
        return self.W - 2 * self.M

    def _new_page(self):
        self.ops = []
        self.y = self.H - self.M
        self.pages.append(self.ops)

    def _ensure(self, h):
        if self.y - h < self.M:
            self._new_page()
            return True
        return False

    def _put(self, s, x, y, size, bold=False, color=(0, 0, 0)):
        font = "/F2" if bold else "/F1"
        r, g, b = color
        self.ops.append(f"BT {font} {size} Tf {r} {g} {b} rg {x:.1f} {y:.1f} Td ({_esc(_latin1(s))}) Tj ET")

    def text(self, s, size=10, bold=False, x=None, color=(0, 0, 0)):
        """One line, not wrapped (use paragraph for running text)."""
        self._ensure(size + 4)
        self._put(s, x or self.M, self.y - size, size, bold, color)
        self.y -= size + 4

    def paragraph(self, s, size=10, bold=False, color=(0, 0, 0), width=None):
        for line in wrap(s, width or self.usable_width, size, bold):
            self.text(line, size, bold=bold, color=color)

    def gap(self, h=8):
        self.y -= h

    def rule(self, color=0.8):
        self.ops.append(f"{color} G 0.5 w {self.M} {self.y:.1f} m {self.M + self.usable_width} {self.y:.1f} l S 0 G")

    def table(self, headers, rows, widths=None, size=8, pad=3, max_lines=None):
        """Wrapped table. widths: points per column (default: equal split of the usable width).
        max_lines caps how many wrapped lines a cell may take (the last kept line ends in '...')."""
        n = len(headers)
        widths = widths or [self.usable_width / n] * n
        total = sum(widths)
        lh = size + 2  # line height inside a cell

        def cell_lines(c, w, bold):
            lines = wrap("" if c is None else c, w - 2 * pad, size, bold)
            if max_lines and len(lines) > max_lines:
                lines = lines[:max_lines]
                last = lines[-1]
                while last and text_width(last + "...", size, bold) > w - 2 * pad:
                    last = last[:last.rfind(" ")] if " " in last else last[:-1]
                lines[-1] = last.rstrip() + "..."
            return lines

        def draw_row(cells, bold=False, shade=False, header=False):
            cols = [cell_lines(c, w, bold) for c, w in zip(cells, widths)]
            rh = max(len(l) for l in cols) * lh + 2 * pad
            if shade or header:
                g = 0.88 if header else 0.95
                self.ops.append(f"{g} g {self.M} {self.y - rh:.1f} {total:.1f} {rh:.1f} re f 0 g")
            x = self.M
            for lines, w in zip(cols, widths):
                y = self.y - pad - size
                for ln in lines:
                    self._put(ln, x + pad, y, size, bold)
                    y -= lh
                x += w
            self.y -= rh
            self.ops.append(f"0.75 G 0.4 w {self.M} {self.y:.1f} m {self.M + total:.1f} {self.y:.1f} l S 0 G")

        def header_height():
            return max(len(cell_lines(h, w, True)) for h, w in zip(headers, widths)) * lh + 2 * pad

        draw_row(headers, bold=True, header=True)
        for i, r in enumerate(rows):
            cols = [cell_lines(c, w, False) for c, w in zip(r, widths)]
            rh = max(len(l) for l in cols) * lh + 2 * pad
            if self.y - rh < self.M:
                self._new_page()
                draw_row(headers, bold=True, header=True)
            draw_row(r, shade=(i % 2 == 1))

    def save(self, path):
        objs = []

        def add(b):
            objs.append(b)
            return len(objs)

        font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        pages_idx = add(b"PLACEHOLDER")
        page_ids = []
        for ops in self.pages:
            stream = "\n".join(ops).encode("latin-1", "replace")
            c = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
            p = add((f"<< /Type /Page /Parent {pages_idx} 0 R /MediaBox [0 0 {self.W} {self.H}] "
                     f"/Contents {c} 0 R /Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> >>").encode())
            page_ids.append(p)
        kids = " ".join(f"{p} 0 R" for p in page_ids)
        objs[pages_idx - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
        catalog = add(f"<< /Type /Catalog /Pages {pages_idx} 0 R >>".encode())

        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for i, o in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        with open(path, "wb") as f:
            f.write(out)
        return path
