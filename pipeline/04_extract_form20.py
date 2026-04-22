"""
pipeline/04_extract_form20.py
================================
Tier 1 Step 3: Extract booth-wise election results from ECI Form 20 PDFs.

Source: results.eci.gov.in → West Bengal → each AC → Form 20
Available for: 2019 Lok Sabha, 2021 Assembly

Form 20 contains: Polling Station No. | Station Name | Votes per candidate
We want: booth × party × election → vote counts

Output: data/processed/form20_{district}.csv
Columns: district, ac_code, ac_name, part_no, booth_name,
         votes_tmc_2021, votes_bjp_2021, votes_left_2021, votes_inc_2021,
         votes_nota_2021, total_votes_2021,
         votes_tmc_2019, votes_bjp_2019, total_votes_2019,
         winner_2021, margin_2021, winner_2019, margin_2019,
         party_switch_19_21

Usage:
    python 04_extract_form20.py --district Murshidabad --year 2021
    python 04_extract_form20.py --district Murshidabad --year 2019
    python 04_extract_form20.py --district Murshidabad --merge  # merge both years
"""

import re
import logging
import argparse
from pathlib import Path

import pdfplumber
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_F20_DIR = Path("data/raw/form20")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RAW_F20_DIR.mkdir(parents=True, exist_ok=True)

# ECI Form 20 URLs (inspect network requests on results.eci.gov.in)
ECI_RESULTS_BASE = "https://results.eci.gov.in"

# Party name → canonical code mapping
PARTY_MAP = {
    # TMC variants
    "All India Trinamool Congress": "TMC",
    "AITC": "TMC",
    "Trinamool": "TMC",
    "TMC": "TMC",
    # BJP variants
    "Bharatiya Janata Party": "BJP",
    "BJP": "BJP",
    # Left/CPI variants
    "Communist Party of India  (Marxist)": "LEFT",
    "CPI(M)": "LEFT",
    "CPI": "LEFT",
    "CPIM": "LEFT",
    "Left Front": "LEFT",
    # Congress variants
    "Indian National Congress": "INC",
    "INC": "INC",
    "Congress": "INC",
    # Others
    "NOTA": "NOTA",
    "None of the above": "NOTA",
    "Independent": "IND",
}


def map_party(name: str) -> str:
    name = str(name).strip()
    for key, code in PARTY_MAP.items():
        if key.lower() in name.lower():
            return code
    return "OTH"


def extract_form20_pdf(pdf_path: Path, ac_code: int, ac_name: str, year: int) -> pd.DataFrame:
    """
    Parse a Form 20 PDF for a single AC.

    Form 20 structure:
    - First rows: candidate list with serial numbers
    - Main table: Polling Station | Votes per candidate (one column each) | Total
    
    Strategy:
    1. Parse candidate list from header (name → party → column index)
    2. Parse main table rows by polling station number
    3. Map column indices → party votes
    """
    candidate_cols = {}  # col_index → party_code
    records = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Pass 1: Find candidate → party mappings from first 2 pages
            for page_i in range(min(2, len(pdf.pages))):
                page = pdf.pages[page_i]
                text = page.extract_text() or ""
                words = page.extract_words(x_tolerance=3, y_tolerance=3)

                # Look for candidate table: Serial No | Candidate Name | Party
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 3:
                            continue
                        serial = str(row[0]).strip()
                        if not re.match(r"^\d+$", serial):
                            continue
                        candidate_name = str(row[1]).strip() if len(row) > 1 else ""
                        party_str = str(row[2]).strip() if len(row) > 2 else ""
                        party_code = map_party(party_str)
                        col_idx = int(serial) - 1  # 0-indexed
                        candidate_cols[col_idx] = {
                            "candidate": candidate_name,
                            "party": party_code,
                        }

            # Pass 2: Parse booth-level vote table
            for page_i in range(len(pdf.pages)):
                page = pdf.pages[page_i]
                tables = page.extract_tables()

                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        # First cell should be polling station number
                        first = str(row[0]).strip() if row[0] else ""
                        if not re.match(r"^\d{1,3}$", first):
                            continue

                        part_no = int(first)
                        booth_name = str(row[1]).strip()[:80] if len(row) > 1 else ""
                        votes = []
                        for cell in row[2:]:
                            try:
                                votes.append(int(str(cell).strip().replace(",", "")))
                            except (ValueError, AttributeError):
                                votes.append(0)

                        rec = {
                            "ac_code": ac_code,
                            "ac_name": ac_name,
                            "part_no": part_no,
                            "booth_name": booth_name,
                            "year": year,
                        }

                        # Map votes to parties
                        for col_i, v in enumerate(votes[:-1]):  # Exclude last (total)
                            party = candidate_cols.get(col_i, {}).get("party", f"P{col_i}")
                            existing = rec.get(f"votes_{party}", 0) or 0
                            rec[f"votes_{party}"] = existing + v

                        # Last numeric = total
                        if votes:
                            rec["total_votes"] = votes[-1] if votes[-1] > 0 else sum(votes[:-1])

                        records.append(rec)

    except Exception as e:
        log.warning(f"Error parsing Form 20 {pdf_path}: {e}")

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Ensure standard party columns exist
    for p in ["TMC", "BJP", "LEFT", "INC", "NOTA"]:
        if f"votes_{p}" not in df.columns:
            df[f"votes_{p}"] = 0

    df = df.fillna(0)

    # Compute winner and margin per booth
    party_cols = [c for c in df.columns if c.startswith("votes_") and c != "votes_total"]
    if party_cols:
        df["winner"] = df[party_cols].idxmax(axis=1).str.replace("votes_", "")
        df["second"] = df[party_cols].apply(
            lambda r: r.nlargest(2).index[-1] if len(r) >= 2 else r.index[0], axis=1
        ).str.replace("votes_", "")
        df["margin"] = df[party_cols].apply(
            lambda r: r.nlargest(2).iloc[0] - r.nlargest(2).iloc[1] if len(r) >= 2 else 0, axis=1
        ).astype(int)

    return df


def merge_years(district: str, df_2021: pd.DataFrame, df_2019: pd.DataFrame) -> pd.DataFrame:
    """Merge 2021 and 2019 Form 20 data, compute party switch and swing metrics."""
    if df_2021.empty and df_2019.empty:
        return pd.DataFrame()

    merge_keys = ["ac_code", "part_no"]

    if not df_2021.empty:
        df_2021 = df_2021.rename(columns={
            c: f"{c}_2021" for c in df_2021.columns
            if c not in merge_keys + ["ac_name", "booth_name", "year"]
        })
        df_2021 = df_2021.drop(columns=["year"], errors="ignore")

    if not df_2019.empty:
        df_2019 = df_2019.rename(columns={
            c: f"{c}_2019" for c in df_2019.columns
            if c not in merge_keys + ["ac_name", "booth_name", "year"]
        })
        df_2019 = df_2019.drop(columns=["year", "ac_name", "booth_name"], errors="ignore")

    if df_2021.empty:
        return df_2019
    if df_2019.empty:
        return df_2021

    merged = df_2021.merge(df_2019, on=merge_keys, how="outer")

    # Party switch flag
    if "winner_2021" in merged.columns and "winner_2019" in merged.columns:
        merged["party_switch_19_21"] = merged["winner_2021"] != merged["winner_2019"]

    # TMC swing between elections
    if "votes_TMC_2021" in merged.columns and "votes_TMC_2019" in merged.columns:
        merged["tmc_swing"] = (
            (merged["votes_TMC_2021"] / merged["total_votes_2021"].clip(1)) -
            (merged["votes_TMC_2019"] / merged["total_votes_2019"].clip(1))
        ).round(3)

    out_path = PROCESSED_DIR / f"form20_{district.lower().replace(' ', '_')}.csv"
    merged.to_csv(out_path, index=False)
    log.info(f"Saved Form 20 merged data → {out_path} ({len(merged)} booths)")
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", default="Murshidabad")
    parser.add_argument("--year", type=int, choices=[2019, 2021], default=2021)
    parser.add_argument("--merge", action="store_true", help="Merge 2019 and 2021")
    args = parser.parse_args()

    d = args.district.lower().replace(" ", "_")

    # Process each AC PDF
    dfs = []
    raw_dir = RAW_F20_DIR / args.district / str(args.year)
    if not raw_dir.exists():
        log.error(f"No Form 20 PDFs at {raw_dir}")
        log.error(f"Download them manually from results.eci.gov.in → WB → {args.district}")
    else:
        for pdf_path in sorted(raw_dir.glob("*.pdf")):
            ac_match = re.search(r"(\d{3})", pdf_path.stem)
            if ac_match:
                ac_code = int(ac_match.group(1))
                ac_name = pdf_path.stem.replace(str(ac_code), "").strip("_- ")
                df = extract_form20_pdf(pdf_path, ac_code, ac_name, args.year)
                if not df.empty:
                    dfs.append(df)
                    log.info(f"  AC {ac_code} — {ac_name}: {len(df)} booths")

    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        out = PROCESSED_DIR / f"form20_{d}_{args.year}.csv"
        combined.to_csv(out, index=False)
        log.info(f"Saved {len(combined)} booth results → {out}")

    if args.merge:
        df_21_path = PROCESSED_DIR / f"form20_{d}_2021.csv"
        df_19_path = PROCESSED_DIR / f"form20_{d}_2019.csv"
        df_21 = pd.read_csv(df_21_path) if df_21_path.exists() else pd.DataFrame()
        df_19 = pd.read_csv(df_19_path) if df_19_path.exists() else pd.DataFrame()
        merge_years(args.district, df_21, df_19)
