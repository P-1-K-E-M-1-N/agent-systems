"""G2 demand test for Storm Lead: write the outreach pack (targets.csv, emails.md, needs_nick entry).
Targets come from public business listings found by web search on 2026-10-24 (company sites,
contractor directories, chamber/BBB-style listings). Business name, type, city and a public
contact URL only; no personal names. Nothing is sent.

    python lanes/storm-lead/g2_outreach.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.outreach import write_outreach_pack  # noqa: E402

PRODUCT = dict(
    name="Storm Lead",
    subject="Question about storm leads in Michigan",
    pitch=("The idea is a morning-after storm alert. When hail or damaging wind hits Michigan overnight, you get an "
           "email listing the counties and ZIP codes that were hit, built from National Weather Service storm "
           "reports, so your crews know where to go first."),
    sample_blurb="what one morning's alert looks like, I pulled the data from National Weather Service storm reports for a real storm night",
    sample_file="lanes/storm-lead/samples/storm_lead_alert.pdf",
)

T = []


def add(business, kind, city, url, source, why):
    T.append(dict(business=business, type=kind, city=city, contact_url=url, source=source, why=why))


add("Storm Guard Roofing of Metro Detroit North", "storm restoration roofer", "Lake Orion",
    "https://stormguardrc.com", "company site via ProjectMap It listing",
    "Markets storm restoration and insurance-claim help across Oakland and Macomb; exactly the buyer profile.")
add("Stable Roofing", "residential roofer", "Southeast Michigan",
    "https://stableroof.com", "company press release (June 2026)", "500+ repairs/replacements incl. storm restorations.")
add("Paramount Roofing", "roofer", "Macomb",
    "https://projectmapit.com/paramount-roofing", "ProjectMap It portfolio listing", "Lists storm damage repair; Macomb County recurs in the backtest.")
add("Billy's Roofing", "roofer", "Metro Detroit",
    "https://projectmapit.com/billys-roofing-1", "ProjectMap It portfolio listing", "35+ years, storm roof repair service page.")
add("Tresnak Construction (Tresnak Roofing)", "roofer / siding", "Royal Oak",
    "https://projectmapit.com/tresnak-roofing", "ProjectMap It listing", "Nick's home town; roofing and vinyl siding.")
add("United Roofing", "roofer, storm damage and insurance claims", "Troy",
    "https://thebuildermarket.com/us/mi/troy/siding-stucco", "The Builder Market directory", "Explicitly sells storm damage roof replacement and claim navigation.")
add("Mr. Roof", "roofer (storm inspections)", "Grand Rapids / Ann Arbor",
    "https://www.mrroof.com", "company site (storm damage inspection campaign page)", "Runs paid storm-inspection campaigns; would value a trigger.")
add("Original Roofing Company", "storm damage restoration roofer", "Grand Rapids",
    "https://roofcalc.org/roofers/companies/mi/original-roofing-company", "RoofCalc directory + Birdeye reviews", "Says it specializes in storm damage restoration.")
add("Irish Roofing & Exteriors", "roofer / exteriors, storm and insurance", "Grand Rapids / Kalamazoo",
    "https://downtobid.com/contractors/roofing/kalamazoo/3", "Downtobid directory", "Assists with storm damage and insurance claims in West Michigan.")
add("DRYmedic Restoration of Grand Rapids", "restoration contractor", "Grand Rapids",
    "https://drymedic.com/locations/grand-rapids/services/storm-damage", "company site", "Storm damage service line with 24/7 hotline.")
add("Paul Davis Restoration of West Michigan", "restoration contractor", "Grand Rapids",
    "https://westmichigan.pauldavis.com", "company site", "Emergency storm damage restoration.")
add("Legacy Roofing and Restorations", "roofer / restoration", "Grand Haven",
    "https://web.grandrapids.org/atb/Contractors", "Grand Rapids Chamber directory", "Lakeshore roofer; Ottawa County appears in the backtest.")
add("CS Roofing Company (FixRoof)", "roofer, urgent storm repair", "Lansing",
    "https://fixroof.com", "company site via Google Business listing", "Serves Lansing, Jackson, Battle Creek, Kalamazoo; lists urgent storm damage repair.")
add("Exteriors of Lansing", "exterior contractor (roofing, siding, windows)", "Grand Ledge",
    "https://downtobid.com/contractors/roofing/lansing/3", "Downtobid directory", "37 years in Greater Lansing; Eaton/Ingham counties recur.")
add("Lyster Exteriors", "roofer / exteriors", "Kalamazoo",
    "https://downtobid.com/contractors/roofing/kalamazoo/3", "Downtobid directory", "Roof repair and replacement since 1998 in SW Michigan.")
add("Tichenor Inc.", "roofer", "Battle Creek",
    "https://downtobid.com/contractors/roofing/kalamazoo/3", "Downtobid directory", "Residential and commercial roofing since 1928; Calhoun County recurs.")
add("Roach Home Improvement", "roofer, storm damage response", "Jackson",
    "https://sociallifemagazine.com/the-archive/best-roofing-companies-in-jackson-for-reliable-roof-repairs-and-installations/",
    "local directory article", "Storm damage response and insurance help, GAF certified.")
add("Billy White Roofing LLC", "roofer", "Jackson / Ann Arbor",
    "https://projectmapit.com/billy-white-roofing-llc", "ProjectMap It listing", "Family roofer since 1994 with free inspections.")
add("GoTo Roofing, Inc.", "roofer / exteriors", "Ann Arbor",
    "https://projectmapit.com/goto-roofing-inc", "ProjectMap It listing", "Wide Washtenaw/Livingston/Wayne service area.")
add("Roofing Pros", "roofer, emergency storm repair", "Flint",
    "https://thebuildermarket.com/us/mi/flint/roofing", "The Builder Market directory", "Emergency tarping after storms; Genesee County coverage.")

if __name__ == "__main__":
    out = write_outreach_pack("storm-lead", PRODUCT, T)
    print(f"wrote {len(T)} targets and drafts to {out}")
