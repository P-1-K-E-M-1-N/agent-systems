"""Turn a lane's G2 outreach pack into a one-sitting send job for Nick. Nothing is sent here.

Reads  lanes/<slug>/outreach/targets.csv (optional `email` and `status` columns) and emails.md (core.outreach).
Writes lanes/<slug>/outreach/mailmerge.csv   one row per target WITH an email address (email, business, type,
                                              city, subject, body) for any mail-merge tool
       lanes/<slug>/outreach/send_sheet.md   every target in send order: contact link, subject, body to paste
                                              into a web contact form (most small businesses only have a form)
       --eml DIR                              one finished .eml draft per email target, attachment included,
                                              plain text plus a restrained HTML layout (--plain for text only).
                                              Open in Thunderbird (File > Open > Saved Message, or
                                              thunderbird.exe -file "x.eml"), check it, press Send.

    python -m core.mailmerge <slug> [--eml DIR] [--from "Name <addr>"]
"""
import argparse
import csv
import html
import mimetypes
import re
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from . import LANES, ROOT
from .outreach import ATTACH_LEAD, SENDER, SENDER_EMAIL, SENDER_ORG

FORM_SWAP = "If you want to see a sample, reply with an email address and I will send one over."


def parse_emails_md(text):
    """{heading: {"contact": url, "subject": s, "body": b}} from core.outreach's emails.md."""
    out = {}
    attach = re.search(r"^Attach:\s*`([^`]+)`", text, re.M)
    for part in re.split(r"^### ", text, flags=re.M)[1:]:
        name = part.splitlines()[0].strip()  # "Business (type, city)"; matched by prefix in build()
        contact = re.search(r"Contact page:\s*(\S+)", part)
        block = re.search(r"```[a-z]*\r?\n(.*?)```", part, re.S)
        if not block:
            continue
        body = block.group(1)
        subj = re.search(r"^Subject:\s*(.+)$", body, re.M)
        body = re.sub(r"^Subject:.*\r?\n\r?\n?", "", body, count=1, flags=re.M).strip()
        out[name] = {"contact": contact.group(1) if contact else "", "subject": subj.group(1).strip() if subj else "",
                     "body": body}
    return out, (attach.group(1) if attach else "")


def form_body(body):
    """Web forms have no attachment box: offer the sample instead of claiming it is attached."""
    return re.sub(re.escape(ATTACH_LEAD) + r"[^\n]*", FORM_SWAP, body)


def build(slug):
    od = LANES / slug / "outreach"
    targets = list(csv.DictReader(open(od / "targets.csv", encoding="utf-8", newline="")))
    drafts, attach = parse_emails_md((od / "emails.md").read_text(encoding="utf-8"))
    rows, sheet = [], []
    for t in targets:
        b = t["business"].strip().lower()
        d = next((v for k, v in drafts.items() if k.lower() == b or k.lower().startswith(b + " (")), None)
        if not d:
            continue
        email = (t.get("email") or "").strip()
        if (t.get("status") or "").strip().lower() in ("drop", "dropped"):
            continue
        if email:
            rows.append({"email": email, "business": t["business"], "type": t.get("type", ""), "city": t.get("city", ""),
                         "subject": d["subject"], "body": d["body"]})
        sheet.append((bool(email), t, d, email))
    with open(od / "mailmerge.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["email", "business", "type", "city", "subject", "body"])
        w.writeheader()
        w.writerows(rows)
    sheet.sort(key=lambda s: (not s[0], s[1]["business"]))
    lines = [f"# Send sheet: {slug}", "",
             f"**Nothing here has been sent.** {len(rows)} target(s) have an email address (`mailmerge.csv`, or "
             f"`python -m core.mailmerge {slug} --eml <folder>` for ready-to-send drafts). "
             f"{len(sheet) - len(rows)} target(s) only have a web contact form: click the link, paste subject and body.", ""]
    if attach:
        lines += [f"Attach where possible: `{attach}` (forms have no attachment box; the form version of the body "
                  "offers the sample on request instead).", ""]
    for has_email, t, d, email in sheet:
        how = f"EMAIL {email}" if has_email else f"FORM {t.get('contact_url') or d['contact'] or '(find contact page)'}"
        body = d["body"] if has_email else form_body(d["body"])
        lines += [f"## {t['business']} ({t.get('type','')}, {t.get('city','')})", f"- Send via: {how}",
                  f"- Subject: {d['subject']}", "", "```", body, "```", ""]
    (od / "send_sheet.md").write_text("\n".join(lines), encoding="utf-8")
    return rows, len(sheet) - len(rows), attach


FONT = "Segoe UI,Helvetica,Arial,sans-serif"
TAGLINE = "Custom software and data tools for small local businesses."  # footer line under the signature


def html_body(body, org=SENDER_ORG, city="Royal Oak, Michigan", accent="#1f3a5f"):
    """A restrained HTML version of the plain-text body: company wordmark, readable type, a signature block.
    No images, no buttons, no links except the mailto, so it reads as a small business writing a note and not
    as a campaign (images, buttons and tracking links are what spam filters and people flag). The plain text
    stays in the same message as the alternative part."""
    paras = [p_.strip() for p_ in re.split(r"\n\s*\n", body.strip()) if p_.strip()]
    sig_at = next((i for i, p_ in enumerate(paras) if re.match(r"^(Thanks|Best|Regards|Cheers)\b", p_)), None)
    text_paras = paras if sig_at is None else paras[:sig_at]
    sig_lines = [] if sig_at is None else "\n".join(paras[sig_at:]).split("\n")
    name = sig_lines[1] if len(sig_lines) > 1 else SENDER

    def esc(t):
        return html.escape(t, quote=False)

    para = (f'<p style="margin:0 0 14px 0;font-family:{FONT};font-size:15px;line-height:1.55;color:#222222;">{{}}</p>')
    parts = [para.format(esc(p_).replace("\n", "<br>")) for p_ in text_paras]
    if sig_lines:
        rest = []
        for ln in sig_lines[2:]:
            ln = ln.strip()
            if "@" in ln and " " not in ln:
                rest.append(f'<a href="mailto:{esc(ln)}" style="color:{accent};text-decoration:none;">{esc(ln)}</a>')
            else:
                rest.append(esc(ln))
        parts.append(f'<p style="margin:18px 0 8px 0;font-family:{FONT};font-size:15px;color:#222222;">{esc(sig_lines[0])}</p>')
        parts.append(f'<table role="presentation" cellpadding="0" cellspacing="0" style="border-left:3px solid {accent};">'
                     f'<tr><td style="padding:2px 0 2px 12px;font-family:{FONT};font-size:14px;line-height:1.5;color:#333333;">'
                     f'<strong style="font-size:15px;color:#111111;">{esc(name)}</strong><br>' + "<br>".join(rest) +
                     "</td></tr></table>")
    inner = "\n".join(parts)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e3e5e8;border-radius:6px;">
<tr><td style="padding:18px 28px 14px 28px;border-bottom:2px solid {accent};">
<span style="font-family:{FONT};font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:{accent};font-weight:600;">{esc(org)}</span>
</td></tr>
<tr><td style="padding:24px 28px 10px 28px;">
{inner}
</td></tr>
<tr><td style="padding:12px 28px 18px 28px;border-top:1px solid #eceef1;font-family:{FONT};font-size:12px;line-height:1.5;color:#7a7f87;">
Sent personally by {esc(name)}, {esc(org)}, {esc(city)}. {esc(TAGLINE)}
</td></tr>
</table></td></tr></table>
</body></html>
"""


def write_eml(rows, attach, out_dir, sender, plain=False):
    """One .eml per email target, marked unsent, attachment included. Returns the paths written.
    Default: plain-text part plus the styled HTML part from html_body(); plain=True writes text only."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attach_path = (ROOT / attach) if attach else None
    data = attach_path.read_bytes() if attach_path and attach_path.exists() else None
    written = []
    for i, r in enumerate(rows, 1):
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = r["email"]
        msg["Subject"] = r["subject"]
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg["X-Unsent"] = "1"
        msg.set_content(r["body"] + "\n")
        if not plain:
            msg.add_alternative(html_body(r["body"]), subtype="html")
        if data:
            ctype = mimetypes.guess_type(attach_path.name)[0] or "application/octet-stream"
            main, sub = ctype.split("/", 1)
            msg.add_attachment(data, maintype=main, subtype=sub, filename=attach_path.name)
        safe = re.sub(r"[^A-Za-z0-9 &'._-]", "", r["business"]).strip()
        p = out_dir / f"{i:02d} {safe}.eml"
        p.write_bytes(msg.as_bytes())
        written.append(p)
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Send sheet, mail-merge CSV and optional .eml drafts for a lane")
    ap.add_argument("slug")
    ap.add_argument("--eml", metavar="DIR", help="also write one ready-to-send .eml per email target into DIR")
    ap.add_argument("--from", dest="sender", default=f"{SENDER}, {SENDER_ORG} <{SENDER_EMAIL}>")
    ap.add_argument("--plain", action="store_true", help="text-only .eml (default adds a styled HTML part)")
    a = ap.parse_args()
    rows, n_form, attach = build(a.slug)
    print(f"{a.slug}: {len(rows)} by email (outreach/mailmerge.csv), {n_form} by web form (outreach/send_sheet.md)")
    if a.eml:
        for p in write_eml(rows, attach, a.eml, a.sender, plain=a.plain):
            print("  wrote", p, p.stat().st_size, "bytes")
