"""
pipeline/03_extract_adjudication.py
=====================================
Tier 1 Step 2b: Download and parse "Under Adjudication" lists from
CEO West Bengal website for each AC in target district.

Source: ceowestbengal.wb.gov.in/SIR
Files: "Adjudication Supplementary List No. 15A" etc. (per AC PDFs)

Output: data/processed/adjudication_{district}.csv
Columns: district, ac_code, ac_name, part_no, booth_name, adj_count, adj_pct_of_booth

Then merges with sir_rolls_*.csv to create:
  data/processed/booths_classified_{district}.csv  ← master booth file
"""

import re
import logging
import argparse
import requests
from pathlib import Path

import pdfplumber
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_ADJ_DIR = Path("data/raw/adjudication")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RAW_ADJ_DIR.mkdir(parents=True, exist_ok=True)

# CEO WB adjudication list URLs — update with live URLs from ceowestbengal.wb.gov.in/SIR
# Format: district → ac_code → [list of PDF URLs for each adjudication round]
# As of Feb-Mar 2026, multiple rounds (No. 1 through 15A) have been published.
# Check: https://ceowestbengal.wb.gov.in/SIR for latest
CEO_WB_SIR_BASE = "https://ceowestbengal.wb.gov.in/SIR"

MURSHIDABAD_AC_CODES = {
    153:"Farakka", 154:"Samserganj", 155:"Suti", 156:"Jangipur",
    157:"Raghunathganj", 158:"Uday Hossain Khan", 159:"Sagardighi", 160:"Lalgola",
    161:"Bhagawangola", 162:"Raninagar", 163:"Murshidabad-Jiaganj", 164:"Nabagram",
    165:"Khargram", 166:"Berhampore", 167:"Baharampur", 168:"Hariharpara",
    169:"Rejinagar", 170:"Beldanga", 171:"Bharatpur", 172:"Burwan",
    173:"Kandi", 174:"Nowda",
}


def extract_adjudication_from_pdf(pdf_path: Path, ac_code: int, ac_name: str) -> pd.DataFrame:
    """
    Parse an adjudication supplementary list PDF.
    These PDFs list individual voters with their part/booth number.
    We aggregate to booth level: count of adjudicated voters per part_no.
    """
    records = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Use extract_words for robustness
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                text = " ".join(w["text"] for w in words)

                # Try table extraction — adjudication lists are tabular
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        row_clean = [str(c).strip() if c else "" for c in row]
                        # Look for rows with a part number pattern
                        part_no = None
                        for cell in row_clean:
                            pm = re.match(r"^(\d{1,3})$", cell)
                            if pm and 1 <= int(pm.group(1)) <= 500:
                                part_no = int(pm.group(1))
                                break
                        if part_no:
                            # Extract voter name from row (typically first text column)
                            voter_name = row_clean[1] if len(row_clean) > 1 else ""
                            if len(voter_name) > 2:
                                records.append({
                                    "ac_code": ac_code,
                                    "ac_name": ac_name,
                                    "part_no": part_no,
                                    "voter_name": voter_name[:60],
                                })
    except Exception as e:
        log.warning(f"Error extracting adjudication PDF {pdf_path}: {e}")

    if not records:
        log.warning(f"No adjudication records extracted from {pdf_path.name}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # Aggregate to booth level
    agg = df.groupby(["ac_code", "ac_name", "part_no"]).size().reset_index(name="adj_count")
    return agg


def download_adjudication_pdfs(district: str, ac_codes: dict) -> list:
    """
    Attempt to download adjudication PDFs from CEO West Bengal SIR page.
    
    IMPORTANT: The CEO WB website requires manual navigation or authenticated API.
    This function provides the framework; you may need to manually download and
    place PDFs in data/raw/adjudication/{district}/{ac_code}/ directory.
    
    Instructions for manual download:
    1. Go to: https://ceowestbengal.wb.gov.in/SIR
    2. Select district → Murshidabad
    3. Select AC → download all "Adjudication Supplementary List" PDFs
       (there are multiple rounds, get the latest numbered one, e.g. "No. 15A")
    4. Save as: data/raw/adjudication/Murshidabad/{ac_code}_adjudication.pdf
    """
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    downloaded = []

    for ac_code, ac_name in ac_codes.items():
        ac_dir = RAW_ADJ_DIR / district / str(ac_code)
        ac_dir.mkdir(parents=True, exist_ok=True)

        # Try common URL patterns for CEO WB SIR adjudication lists
        url_patterns = [
            f"{CEO_WB_SIR_BASE}/{district}/{ac_code}/adj_supp_15a.pdf",
            f"{CEO_WB_SIR_BASE}/adjudication/{district}_{ac_code}.pdf",
        ]

        for url in url_patterns:
            out_path = ac_dir / "adj_latest.pdf"
            if out_path.exists():
                downloaded.append(out_path)
                break
            try:
                r = session.get(url, timeout=30)
                if r.status_code == 200 and b"%PDF" in r.content[:10]:
                    out_path.write_bytes(r.content)
                    log.info(f"Downloaded adjudication list: {ac_name}")
                    downloaded.append(out_path)
                    break
            except Exception:
                pass

    log.info(f"Downloaded {len(downloaded)} adjudication PDFs")
    return downloaded


def merge_and_classify_booths(
    district: str,
    sir_csv: Path,
    adj_csv: Path,
    form20_csv: Path,
) -> pd.DataFrame:
    """
    Master merge: SIR rolls + adjudication counts + Form 20 results → classified booths.
    
    Output columns per booth:
    - Basic: district, ac_code, ac_name, part_no, booth_name
    - Electors: total_2026, male_2026, female_2026, female_pct_2026
    - Adjudication: adj_count, adj_pct
    - Election results (from Form 20): votes_2021_tmc, votes_2021_bjp, ...
    - Derived: margin_2021, winner_2021, party_switch_19_21
    - Classification: booth_category (A/B/C/D), priority_score
    """
    # Load SIR rolls
    if not sir_csv.exists():
        log.error(f"SIR rolls CSV not found: {sir_csv}")
        log.error("Run 02_extract_sir_rolls.py first.")
        return pd.DataFrame()

    sir_df = pd.read_csv(sir_csv)
    log.info(f"SIR rolls: {len(sir_df)} booths")

    # Load adjudication (optional)
    if adj_csv.exists():
        adj_df = pd.read_csv(adj_csv)
        sir_df = sir_df.merge(
            adj_df[["ac_code", "part_no", "adj_count"]],
            on=["ac_code", "part_no"], how="left"
        )
        sir_df["adj_count"] = sir_df["adj_count"].fillna(0).astype(int)
        sir_df["adj_pct"] = (sir_df["adj_count"] / sir_df["total"].clip(1) * 100).round(1)
    else:
        log.warning("No adjudication CSV found — adj_count will be 0")
        sir_df["adj_count"] = 0
        sir_df["adj_pct"] = 0.0

    # Load Form 20 results (optional)
    if form20_csv.exists():
        f20_df = pd.read_csv(form20_csv)
        sir_df = sir_df.merge(
            f20_df,
            on=["ac_code", "part_no"], how="left"
        )
    else:
        log.warning("No Form 20 CSV found — election results will be empty")
        for col in ["votes_tmc_2021", "votes_bjp_2021", "votes_tmc_2019", "votes_bjp_2019",
                    "total_votes_2021", "total_votes_2019"]:
            sir_df[col] = pd.NA

    # --- Booth Classification ---
    def classify_booth(row):
        """
        A: Stronghold (our party >65% in both 2019 and 2021)
        B: Swing (margin < 50 votes OR party flipped)
        C: Hostile (opposition >65%)
        D: SIR-adjudicated (>10% electors under adjudication)
        Priority: D > B > C > A
        """
        # D: SIR crisis booth
        if row.get("adj_pct", 0) > 10:
            return "D"

        tmc_21 = row.get("votes_tmc_2021", None)
        bjp_21 = row.get("votes_bjp_2021", None)
        total_21 = row.get("total_votes_2021", None)
        tmc_19 = row.get("votes_tmc_2019", None)
        bjp_19 = row.get("votes_bjp_2019", None)
        total_19 = row.get("total_votes_2019", None)

        if pd.isna(tmc_21) or pd.isna(total_21) or total_21 == 0:
            return "B"  # Unknown = treat as swing

        tmc_share_21 = tmc_21 / total_21
        bjp_share_21 = bjp_21 / total_21 if not pd.isna(bjp_21) else 0
        margin_21 = abs(tmc_21 - (bjp_21 or 0))

        # B: margin < 50 votes
        if margin_21 < 50:
            return "B"

        # Check for flip between 2019 and 2021
        if not pd.isna(tmc_19) and not pd.isna(bjp_19) and total_19 and total_19 > 0:
            winner_21 = "TMC" if tmc_share_21 > bjp_share_21 else "BJP"
            winner_19 = "TMC" if tmc_19 / total_19 > bjp_19 / total_19 else "BJP"
            if winner_21 != winner_19:
                return "B"  # Flipped

        # A: stronghold
        if tmc_share_21 > 0.65:
            if not pd.isna(tmc_19) and total_19 and tmc_19 / total_19 > 0.65:
                return "A"

        # C: hostile
        if bjp_share_21 > 0.65:
            return "C"

        return "B"  # Default to swing

    sir_df["booth_category"] = sir_df.apply(classify_booth, axis=1)

    # Priority score (higher = more campaign resources)
    priority_map = {"D": 4, "B": 3, "C": 2, "A": 1}
    sir_df["priority_score"] = sir_df["booth_category"].map(priority_map)

    # Votes needed to win at this booth
    sir_df["votes_to_win_est"] = (sir_df["total"] * 0.84 * 0.501).round(0).astype(int)

    # Save
    out_path = PROCESSED_DIR / f"booths_classified_{district.lower().replace(' ', '_')}.csv"
    sir_df.to_csv(out_path, index=False)
    log.info(f"\nSaved classified booths → {out_path}")
    log.info(sir_df["booth_category"].value_counts().to_string())

    return sir_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", default="Murshidabad")
    args = parser.parse_args()

    d = args.district.lower().replace(" ", "_")
    merge_and_classify_booths(
        district=args.district,
        sir_csv=PROCESSED_DIR / f"sir_rolls_{d}.csv",
        adj_csv=PROCESSED_DIR / f"adjudication_{d}.csv",
        form20_csv=PROCESSED_DIR / f"form20_{d}.csv",
    )
