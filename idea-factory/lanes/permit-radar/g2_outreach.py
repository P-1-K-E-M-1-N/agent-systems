"""G2 demand test for permit-radar: build the outreach pack (targets.csv, emails.md, replies.md, needs_nick entry).
Run from repo root: python lanes/permit-radar/g2_outreach.py
Targets are businesses found in PUBLIC listings (company sites, BBB, HomeAdvisor/Expertise/Trane/Thumbtack
directories) on 2026-10-24. Business name, trade, city and a public contact/listing URL only; no personal names.
Nothing is sent; Nick sends by hand.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.outreach import write_outreach_pack  # noqa: E402

PRODUCT = dict(
    name="Permit Radar",
    subject="Question about Detroit permit leads",
    pitch=("The idea is a weekly list of Detroit permits in your trade. Every Monday you get last week's building, "
           "trades and demolition permits with the address, type and estimated job cost, pulled from the city's own "
           "public data, so you can see who is pulling permits near you without digging through the city portal."),
    sample_blurb="last week's list, I pulled the data from the City of Detroit's permit records today",
    sample_file="lanes/permit-radar/samples/lead_sheet.pdf",
)

TARGETS = [
    # roofers
    dict(business="Four Seasons Kanga Roof", type="roofer", city="Roseville, MI",
         contact_url="https://kanga-roof.com/contact-us/", source="company website (verified 2026-10-24)",
         why="large residential+commercial roofer serving metro Detroit; roof + solar rows"),
    dict(business="Pro Home Improvement", type="roofer", city="Ferndale, MI",
         contact_url="https://www.buildzoom.com/contractor/pro-home-improvement-ferndale", source="BuildZoom public listing",
         why="full-replacement roofing/siding; general + roofing rows are replacement candidates"),
    dict(business="Schoenherr Roofing", type="roofer", city="Romeo, MI (serves SE Michigan)",
         contact_url="https://www.buildzoom.com/contractor/schoenherr-roofing-mi", source="BuildZoom public listing",
         why="29-year SE Michigan roofer; competitor-map use of roofing rows"),
    dict(business="Tresnak Construction, Inc.", type="roofer", city="Royal Oak, MI",
         contact_url="https://www.bbb.org/us/mi/royal-oak/category/gutters", source="BBB category listing",
         why="local Royal Oak roofing/siding contractor; Nick's home turf"),
    # electricians
    dict(business="McChesney Electric", type="electrician", city="Ferndale, MI",
         contact_url="https://www.mcchesneyelectric.com/contact", source="company website (BBB link references Ferndale)",
         why="family-owned residential/commercial electrician; electrical + general rows"),
    dict(business="Superior Electric of Greater Detroit", type="electrician", city="Detroit, MI",
         contact_url="https://www.expertise.com/home-improvement/electricians/michigan/detroit", source="Expertise.com listing",
         why="50+ year tri-county electrical contractor; electrical rows (78/week)"),
    dict(business="KMR Construction Services", type="electrician", city="Detroit, MI",
         contact_url="https://homeguide.com/mi/detroit/electricians/", source="HomeGuide listing",
         why="in-house licensed electricians serving Detroit; renovation (general) rows"),
    # HVAC
    dict(business="Royal Oak Heating, Cooling, Electrical & Plumbing", type="HVAC contractor", city="Troy, MI",
         contact_url="https://royaloakheating.com/contact-us/", source="company website (verified 2026-10-24)",
         why="multi-trade since 1951; hvac rows are the biggest bucket (130/week)"),
    dict(business="Thornton & Grooms", type="HVAC contractor", city="Farmington Hills, MI",
         contact_url="https://thorntonandgrooms.com/about/contact", source="company website (verified 2026-10-24)",
         why="large HVAC+plumbing shop; tests whether a bigger firm values permit intel"),
    dict(business="Beyer Heating & Cooling", type="HVAC contractor", city="Ferndale, MI",
         contact_url="https://www.trane.com/residential/en/dealers/beyer-heating-and-cooling-ferndale-michigan-991506/",
         source="Trane dealer directory", why="small local HVAC since 1977; price sensitivity at $30"),
    dict(business="Winslow Heating & Cooling", type="HVAC contractor", city="Lincoln Park, MI",
         contact_url="https://www.thumbtack.com/mi/lincoln-park/hvac", source="Thumbtack listing",
         why="family-run, serves Wayne + Oakland; furnace replacement season"),
    dict(business="JLH Heating & Air Conditioning", type="HVAC contractor", city="Detroit, MI",
         contact_url="https://www.promptloop.com/directory/detroit-hvac", source="directory listing",
         why="Detroit-based residential furnace/boiler shop; in-city rows"),
    # plumbers
    dict(business="Cregger Plumbing, Heating & Cooling", type="plumber", city="Ferndale, MI",
         contact_url="https://www.creggerplumbing.com/contact-us/", source="company website (verified 2026-10-24)",
         why="large local plumbing/HVAC; plumbing + hvac rows"),
    dict(business="WaterWork Plumbing", type="plumber", city="Ferndale, MI",
         contact_url="https://waterworkplumbing.com/contact/", source="company website (verified 2026-10-24)",
         why="commercial+residential plumber in Detroit since 2006; hotel/commercial plumbing rows"),
    dict(business="Nelson Brothers Sewer & Plumbing", type="plumber", city="Royal Oak, MI",
         contact_url="https://www.nelsonbrothersplumbing.com/contact-us", source="company website + BBB profile",
         why="100-year Royal Oak plumber; sewer/back-water-valve rows"),
    dict(business="Mr. Rooter Plumbing of Detroit", type="plumber", city="Detroit, MI",
         contact_url="https://mrrooter.com/detroit", source="franchise website",
         why="franchise with marketing budget; tests franchise appetite"),
    # dumpster rental (strongest fit: demolition + renovation + new-construction rows)
    dict(business="Michigan Made Dumpster Rentals", type="dumpster rental", city="Brownstown Twp, MI",
         contact_url="https://michiganmadedumpsterrental.com/", source="company website",
         why="Wayne County roll-off company; demolition/dumpster rows (39/week) are direct leads"),
    dict(business="Bin There Dump That Southeast Michigan", type="dumpster rental", city="Metro Detroit, MI",
         contact_url="https://semichigan.bintheredumpthatusa.com/contactus", source="franchise website",
         why="residential-friendly dumpsters; renovation/rehab rows"),
    dict(business="Priority Waste", type="dumpster rental", city="Detroit, MI",
         contact_url="https://www.prioritywaste.com/cities-we-serve/dumpster-rental-detroit-mi", source="company website",
         why="Michigan hauler with Detroit roll-off page; demolition permits list the wrecking contractor"),
    dict(business="Discount Dumpster", type="dumpster rental", city="Detroit, MI",
         contact_url="https://discountdumpsterco.com/locations/detroit-dumpster-rental/", source="company website",
         why="greater-Detroit roll-off; tests whether permit timing beats their current lead sources"),
]

if __name__ == "__main__":
    out = write_outreach_pack("permit-radar", PRODUCT, TARGETS)
    print(f"wrote {len(TARGETS)} targets to {out}")
