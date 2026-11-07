"""Outreach-draft generator for G2 revenue tests. Nothing is ever sent; drafts are written
to lanes/<slug>/outreach/ and surfaced in the lane's needs_nick.md, which the board
rolls up into ops/NEEDS_NICK.md for Nick to send by hand (via core.mailmerge).

    from core.outreach import write_outreach_pack
    write_outreach_pack("permit-radar",
        product=dict(name=..., pitch=..., price=..., sample_file=..., sample_blurb=..., subject=...),
        targets=[{"business": "...", "type": "roofer", "city": "...", "source": "...", "contact_url": "...",
                  "email": "..."}])

product keys:
  name          product name (used in the file header, not pushed into the email)
  pitch         2-4 plain sentences, second person, what they get and what they send. No marketing words.
  trial         what Nick offers in return for feedback (default "a free trial for 6 months"); never a price
  sample_file   repo path of the attachment (PDF)
  sample_blurb  describes the attachment, in Nick's voice: "what that sheet looks like for a typical 20-car lot,
                I pulled the data from NHTSA today" (optional)
  subject       subject line; may use {business}, {kind}, {city} (optional; default is a plain question)

Tone rules (Nick, 2026-10-24, after reading two drafts): write it the way Nick talks. "My name is Nick and I am
planning to do some solo development work..." Say the real reason for writing: feedback, not a sale. One short
paragraph on the idea, no bullet lists of questions, no prices at all. Offer a free 6-month trial in return for
user stories. Close with "If you could respond it would be greatly appreciated, but no response will be
understood as a no." Nothing that sounds like a template.
"""
import csv
from datetime import date
from pathlib import Path

from . import LANES

# The factory mailbox Nick set up on 2026-10-24 (ops/needs_nick_global.md). Only Nick sends from it.
SENDER = "Nick Lektzian"
SENDER_ORG = "AIA Digital Services"
SENDER_CITY = "Royal Oak, MI"
SENDER_EMAIL = "nick.aiadigital@gmail.com"

SURVEY = [
    "Would this be useful to you? (yes / no / maybe)",
    "Would you try it free for 6 months and tell me how it goes?",
]

# The attachment sentence must start with this so core.mailmerge can swap it for web-form targets.
ATTACH_LEAD = "I've attached"


def draft_email(product, target, sender=SENDER, city=SENDER_CITY, org=SENDER_ORG, reply_to=SENDER_EMAIL):
    """Nick's wording (2026-10-24): plain intro, say why we're reaching out (feedback, not a sale), one short
    paragraph on the idea, the attachment, a free 6-month trial in return for honest feedback, no prices,
    and his closing line. No question lists."""
    business = target.get("business", "there")
    kind = target.get("type", "business")
    tcity = target.get("city", "")
    subj = (product.get("subject") or "Quick question for {business}").format(business=business, kind=kind, city=tcity)
    first = sender.split()[0]
    where = f"around {tcity}" if tcity and tcity != city.split(",")[0] else "here in the area"
    blurb = product.get("sample_blurb") or "a sample built from this week's public data"
    pitch = product["pitch"].strip()
    trial = product.get("trial", "a free trial for 6 months")

    body = f"""Subject: {subj}

Hello,

My name is {first} and I am planning to do some solo development work for small {kind}s {where}. Before I build anything I want to hear from the people who would actually use it, so I am reaching out to a few shops for some honest feedback.

{pitch}

{ATTACH_LEAD} {blurb}. The report can be customized as well if there is something you would want added or laid out differently.

If this is something that would interest you, I can set you up with {trial}. All I would ask in return is some feedback on how it works for you day to day.

If you could respond it would be greatly appreciated, but no response will be understood as a no.

Thanks,
{sender}
{org}, {city}
{reply_to}
"""
    return subj, body


def write_outreach_pack(slug, product, targets, sender=SENDER, preamble=""):
    out = LANES / slug / "outreach"
    out.mkdir(parents=True, exist_ok=True)

    # 1. target list as CSV (public business listings only; business email addresses only, never personal ones)
    cols = ["business", "type", "city", "contact_url", "email", "source", "why"]
    if any(t.get("status") for t in targets):
        cols.append("status")
    with open(out / "targets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for t in targets:
            w.writerow({c: t.get(c, "") for c in cols})

    # 2. one email draft per target
    lines = [f"# Outreach drafts for {product['name']} ({date.today().isoformat()})", "",
             "**Nothing here has been sent.** Nick sends by hand after review "
             f"(`python -m core.mailmerge {slug}` makes the send sheet and .eml drafts)."]
    if preamble:
        lines += ["", preamble.strip()]
    lines += ["", f"Attach: `{product['sample_file']}`", "", "## What every email asks", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(product.get("ask") or SURVEY, 1)]
    lines += ["", "## Emails", ""]
    for t in targets:
        subj, body = draft_email(product, t, sender)
        how = f"Email: {t['email']}" if t.get("email") else f"Contact page: {t.get('contact_url', '(find on their site)')}"
        lines += [f"### {t.get('business','?')} ({t.get('type','')}, {t.get('city','')})", how]
        if t.get("note"):
            lines.append(t["note"])
        lines += ["", "```", body.rstrip(), "```", ""]
    (out / "emails.md").write_text("\n".join(lines), encoding="utf-8")

    # 3. needs_nick entry (board rolls these up)
    nn = LANES / slug / "needs_nick.md"
    entry = (f"- [ ] **Send G2 outreach** ({date.today().isoformat()}): {len(targets)} draft emails in "
             f"`lanes/{slug}/outreach/emails.md`, targets in `targets.csv`, attach `{product['sample_file']}`. "
             f"Reply tally goes in `lanes/{slug}/outreach/replies.md`.\n")
    existing = nn.read_text(encoding="utf-8") if nn.exists() else f"# Needs Nick: {slug}\n\n"
    if "Send G2 outreach" not in existing:
        nn.write_text(existing + entry, encoding="utf-8")
    (out / "replies.md").touch()
    from .scoring import _stamp_gate
    _stamp_gate(slug, "G2", finished=True, note=f"outreach pack: {len(targets)} targets drafted")
    return out
