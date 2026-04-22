"""
pipeline/01_download_sir_rolls.py
==================================
Tier 1 Step 1: Download SIR FinalRoll-Rev2 2026 PDFs from voters.eci.gov.in
for West Bengal — district by district, AC by AC, booth by booth.

Usage:
    python 01_download_sir_rolls.py --district "Murshidabad" --max_acs 5
    python 01_download_sir_rolls.py --district "Murshidabad" --all_acs

Output: data/raw/sir_rolls/{district}/{ac_code}/part_{n}.pdf
"""

import os
import time
import json
import requests
import argparse
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ECI voter portal base URLs
ECI_BASE = "https://voters.eci.gov.in"
ROLL_DOWNLOAD_BASE = "https://voters.eci.gov.in/download-eroll"

# West Bengal state code
WB_STATE_CODE = "S25"

# All 23 WB district codes (as used in ECI portal)
WB_DISTRICTS = {
    "Alipurduar":          "S2522",
    "Bankura":             "S2519",
    "Birbhum":             "S2521",
    "Cooch Behar":         "S2501",
    "Dakshin Dinajpur":    "S2505",
    "Darjeeling":          "S2503",
    "Hooghly":             "S2515",
    "Howrah":              "S2514",
    "Jalpaiguri":          "S2502",
    "Jhargram":            "S2524",
    "Kalimpong":           "S2523",
    "Kolkata North":       "S2512",
    "Kolkata South":       "S2511",
    "Malda":               "S2506",
    "Murshidabad":         "S2507",
    "Nadia":               "S2508",
    "North 24 Parganas":   "S2509",
    "Paschim Bardhaman":   "S2525",
    "Paschim Medinipur":   "S2517",
    "Purba Bardhaman":     "S2520",
    "Purba Medinipur":     "S2516",
    "Purulia":             "S2518",
    "South 24 Parganas":   "S2510",
    "Uttar Dinajpur":      "S2504",
}

# Murshidabad ACs (22 Assembly Constituencies, codes 153–174)
MURSHIDABAD_ACS = {
    "153": "Farakka",
    "154": "Samserganj",
    "155": "Suti",
    "156": "Jangipur",
    "157": "Raghunathganj",
    "158": "Uday Hossain Khan",
    "159": "Sagardighi",
    "160": "Lalgola",
    "161": "Bhagawangola",
    "162": "Raninagar",
    "163": "Murshidabad",
    "164": "Nabagram",
    "165": "Khargram",
    "166": "Berhampore",
    "167": "Baharampur",
    "168": "Hariharpara",
    "169": "Rejinagar",
    "170": "Beldanga",
    "171": "Bharatpur",
    "172": "Burwan",
    "173": "Kandi",
    "174": "Nowda",
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": ECI_BASE,
    })
    return s


def download_booth_pdf(
    session: requests.Session,
    district_code: str,
    ac_code: str,
    part_no: int,
    out_path: Path,
    roll_type: str = "SIR FinalRoll-Rev2 - 2026",
    language: str = "English",
) -> bool:
    """
    Attempt to download a single booth part PDF.
    ECI portal requires: state + district + AC + roll_type + part_no + language
    Returns True on success.
    
    NOTE: ECI portal uses a multi-step API:
    1. GET /download-eroll → get CSRF token
    2. POST to get available parts list
    3. POST to download specific part PDF
    
    The actual API endpoints and parameters must be inspected from the
    browser network tab on voters.eci.gov.in → this script provides the
    structural framework; update ECI_API_* constants to match live endpoints.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        log.info(f"  Skip (exists): {out_path.name}")
        return True

    # Step 1: Fetch CSRF token
    try:
        resp = session.get(f"{ECI_BASE}/download-eroll", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"Failed to reach ECI portal: {e}")
        return False

    # Step 2: Get parts list for this AC
    # NOTE: Update this endpoint by inspecting network requests on voters.eci.gov.in
    parts_url = f"{ECI_BASE}/api/eroapi/getAcPartsEroll"
    payload = {
        "stateCode": WB_STATE_CODE,
        "districtCode": district_code,
        "acCode": ac_code,
        "revisionType": roll_type,
        "language": language,
    }
    try:
        resp = session.post(parts_url, json=payload, timeout=30)
        parts_data = resp.json()
        log.debug(f"Parts response: {parts_data}")
    except Exception as e:
        log.warning(f"Failed to get parts list for AC {ac_code}: {e}")
        return False

    # Step 3: Download specific part
    # NOTE: Update this endpoint and params based on live API inspection
    download_url = f"{ECI_BASE}/api/eroapi/downloadErollPdf"
    dl_payload = {
        **payload,
        "partNo": part_no,
    }
    try:
        resp = session.post(download_url, json=dl_payload, timeout=60, stream=True)
        if resp.status_code == 200 and b"%PDF" in resp.content[:10]:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            log.info(f"  Downloaded: {out_path.name} ({len(resp.content)//1024}KB)")
            return True
        else:
            log.warning(f"  Non-PDF response for part {part_no}: status {resp.status_code}")
            return False
    except Exception as e:
        log.warning(f"  Download error part {part_no}: {e}")
        return False


def download_district_rolls(
    district: str,
    acs: Optional[dict] = None,
    max_acs: Optional[int] = None,
    parts_per_ac: int = 400,  # ~400 booths per AC max
    delay: float = 1.5,
    out_base: Path = Path("data/raw/sir_rolls"),
):
    """
    Download all booth PDFs for a district.
    Uses known AC codes for Murshidabad; adaptable for all districts.
    """
    district_code = WB_DISTRICTS.get(district)
    if not district_code:
        raise ValueError(f"Unknown district: {district}. Available: {list(WB_DISTRICTS.keys())}")

    if acs is None:
        if district == "Murshidabad":
            acs = MURSHIDABAD_ACS
        else:
            raise ValueError(f"AC mapping for {district} not yet defined. Add to script.")

    session = get_session()
    ac_list = list(acs.items())
    if max_acs:
        ac_list = ac_list[:max_acs]

    log.info(f"Starting download: {district} | {len(ac_list)} ACs | up to {parts_per_ac} parts each")
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    for ac_code, ac_name in ac_list:
        log.info(f"\nAC {ac_code} — {ac_name}")
        ac_dir = out_base / district / f"{ac_code}_{ac_name.replace(' ', '_')}"
        ac_dir.mkdir(parents=True, exist_ok=True)

        for part_no in range(1, parts_per_ac + 1):
            out_path = ac_dir / f"part_{part_no:03d}.pdf"
            success = download_booth_pdf(
                session=session,
                district_code=district_code,
                ac_code=ac_code,
                part_no=part_no,
                out_path=out_path,
            )
            if success:
                total_downloaded += 1
            else:
                total_failed += 1
                if part_no > 10:  # Stop if many consecutive failures
                    consecutive_fails = sum(
                        1 for p in range(max(1, part_no - 5), part_no + 1)
                        if not (ac_dir / f"part_{p:03d}.pdf").exists()
                    )
                    if consecutive_fails >= 5:
                        log.info(f"  Stopping AC {ac_code} at part {part_no} (5 consecutive failures)")
                        break

            time.sleep(delay)

    log.info(f"\nDone. Downloaded: {total_downloaded} | Failed: {total_failed}")
    return total_downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download WB SIR 2026 electoral roll PDFs")
    parser.add_argument("--district", default="Murshidabad", help="District name")
    parser.add_argument("--max_acs", type=int, default=None, help="Limit number of ACs")
    parser.add_argument("--all_acs", action="store_true", help="Download all ACs in district")
    parser.add_argument("--parts_per_ac", type=int, default=400)
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    args = parser.parse_args()

    download_district_rolls(
        district=args.district,
        max_acs=None if args.all_acs else args.max_acs,
        parts_per_ac=args.parts_per_ac,
        delay=args.delay,
    )
