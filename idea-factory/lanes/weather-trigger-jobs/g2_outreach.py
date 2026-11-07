"""G2 demand test for weather-trigger-jobs: outreach pack. Run from repo root.
Targets are businesses from PUBLIC listings found 2026-10-29 (company sites, BBB, directories). Business name, trade,
city and a public contact/listing URL only; no personal names. Nothing is sent; Nick sends by hand.
Roofers are left out on purpose: they overlap storm-lead.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.outreach import write_outreach_pack  # noqa: E402

PRODUCT = dict(
    name="Weather Trigger Jobs",
    subject="Question about weather and your job schedule",
    pitch=("The idea is a simple go / risky / hold call for each day of the next week. It checks the National Weather "
           "Service forecast for rain, wind and frost against the hours you actually work, and tells you which days to "
           "keep, move or cancel before you call the crew or the client."),
    sample_blurb="what the daily outlook looks like, I pulled the forecast from the National Weather Service today",
    sample_file="lanes/weather-trigger-jobs/samples/job_day_outlook.pdf",
)

L = "landscaper"; P = "paving contractor"; T = "tent / event rental"; V = "outdoor event venue"
TARGETS = [
    dict(business="Elowsky Lawn Services", type=L, city="Waterford, MI", contact_url="https://elowskylawn.com/contact-us",
         source="company website (2026-10-29)", why="lawn and landscape, NE Oakland County; mowing days depend on rain"),
    dict(business="K and M Landscaping", type=L, city="Franklin, MI", contact_url="https://www.yourgreenpal.com/pro/k-and-m-landscaping",
         source="YourGreenPal listing", why="small landscaper, estimates by call or text"),
    dict(business="Michigan Gardens", type=L, city="Macomb/Oakland County, MI", contact_url="https://masteredgelawncare.yolasite.com/",
         source="company site", why="30-year family lawn company, small crew scheduling"),
    dict(business="Lawns of Distinction", type=L, city="Grand Rapids, MI", contact_url="https://www.angi.com/companylist/grand-rapids/lawn-care.htm",
         source="Angi directory listing", why="landscaping and snow removal since 1986; West Michigan test"),
    dict(business="Michlawn Services Inc", type=L, city="Grand Rapids, MI", contact_url="https://www.angi.com/companylist/us/mi/grand-rapids/landscaping.htm",
         source="Angi directory listing", why="family lawn business, 15+ years"),
    dict(business="Maxx Landscapes LLC", type=L, city="Grand Rapids, MI", contact_url="https://thebuildermarket.com/us/mi/grand-rapids/landscaping",
         source="BuilderMarket directory listing", why="lawn, design and tree care for homes and small businesses"),
    dict(business="Top Right Paving", type=P, city="Waterford, MI", contact_url="https://www.bbb.org/us/mi/category/asphalt",
         source="BBB category listing", why="asphalt and sealcoating; cannot pave or seal in rain or near frost"),
    dict(business="BEST Asphalt Paving & Sealcoating", type=P, city="Birmingham, MI",
         contact_url="https://www.houzz.com/profesionales/accesos-y-pavimentacion/best-asphalt-paving-y-sealcoating-pfvwus-pf~1293987353",
         source="Houzz listing", why="North Oakland County paving; temperature and rain gates"),
    dict(business="Birmingham Sealcoat, Inc.", type=P, city="Oxford, MI", contact_url="https://www.bbb.org/us/mi/category/asphalt",
         source="BBB category listing", why="sealcoating is highly weather dependent"),
    dict(business="Knights Tent & Party Rental", type=T, city="Metro Detroit, MI", contact_url="https://knightspartyrental.com/service-areas/mi/detroit/",
         source="company website (2026-10-29)", why="tent installs depend on wind and rain"),
    dict(business="Party Dreams Wedding & Event Rental", type=T, city="Sterling Heights, MI", contact_url="https://sites.google.com/view/partydreams/home",
         source="company site", why="tent and sidewall rentals; wind limits"),
    dict(business="Alpine Events", type=T, city="Metro Detroit, MI", contact_url="https://visitdetroit.com/directory/alpine-events/",
         source="Visit Detroit directory", why="tent and event rentals in metro Detroit"),
    dict(business="The Farm in Oxford", type=V, city="Oxford, MI", contact_url="https://www.zola.com/wedding-vendors/search/oakland-mi--wedding-venues--farms-barns-ranches",
         source="Zola venue listing", why="barn plus tented backyard; outdoor event go/no-go"),
    dict(business="Stillwater Stables", type=V, city="Ortonville, MI", contact_url="https://www.zola.com/wedding-vendors/search/oakland-mi--wedding-venues--farms-barns-ranches",
         source="Zola venue listing", why="outdoor horse-farm venue; weather decides ceremony site"),
]

if __name__ == "__main__":
    out = write_outreach_pack("weather-trigger-jobs", PRODUCT, TARGETS)
    print(f"wrote {len(TARGETS)} targets to {out}")
