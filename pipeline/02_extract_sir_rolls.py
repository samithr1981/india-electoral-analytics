"""
pipeline/02_extract_sir_rolls.py
==================================
Tier 1 Step 2: Extract structured data from downloaded SIR roll PDFs.

Each ECI electoral roll PDF (one per booth/part) contains:
- Header: State, District, Assembly Constituency, Part No., Booth Name
- Summary table: Total Male / Female / Third Gender electors
- Individual voter entries (name, EPIC, address, photo)

This script extracts the SUMMARY stats per booth (we don't need individual voters).

Output: data/processed/sir_rolls_extracted.csv
Columns: district, ac_code, ac_name, part_no, booth_name, male, female, third_gender, total

Usage:
    python 02_extract_sir_rolls.py --district Murshidabad
    python 02_extract_sir_rolls.py --district Murshidabad --ac_code 160  # single AC
"""

import re
import csv
import json
import logging
import argparse
from pathlib import Path
from typing import Optional

import pdfplumber
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/sir_rolls")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_booth_summary(pdf_path: Path) -> Optional[dict]:
    """
    Extract summary elector counts from a single booth PDF.
    ECI roll PDFs have a standardised header with key fields.
    Uses pdfplumber extract_words() to handle garbled text (as per your MF Dashboard approach).
    """
    result = {
        "part_no": None,
        "booth_name": None,
        "ac_name": None,
        "ac_code": None,
        "district": None,
        "male": 0,
        "female": 0,
        "third_gender": 0,
        "total": 0,
        "source_pdf": pdf_path.name,
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Use first page for header + summary
            page = pdf.pages[0]

            # Strategy: extract_words() handles garbled encoding better than extract_text()
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            full_text = " ".join(w["text"] for w in words)

            # Also try plain text as fallback
            plain_text = page.extract_text() or ""

            text = full_text if len(full_text) > len(plain_text) else plain_text

            # --- Extract Part Number ---
            part_match = re.search(r"[Pp]art\s*[Nn]o\.?\s*[:\-]?\s*(\d+)", text)
            if part_match:
                result["part_no"] = int(part_match.group(1))

            # --- Extract Booth Name ---
            # ECI format: "Polling Station Name: <name>" or "Booth Name: <name>"
            booth_match = re.search(
                r"(?:Polling Station Name|Booth Name|Name of Polling Station)\s*[:\-]\s*([^\n|]+)",
                text, re.IGNORECASE
            )
            if booth_match:
                result["booth_name"] = booth_match.group(1).strip()[:100]

            # --- Extract AC Name ---
            ac_match = re.search(
                r"(?:Assembly Constituency|Vidhan Sabha)\s*[:\-]\s*(\d+)\s*[–\-\s]+([^\n|]+)",
                text, re.IGNORECASE
            )
            if ac_match:
                result["ac_code"] = ac_match.group(1).strip()
                result["ac_name"] = ac_match.group(2).strip()[:60]

            # --- Extract District ---
            dist_match = re.search(r"District\s*[:\-]\s*([^\n|]+)", text, re.IGNORECASE)
            if dist_match:
                result["district"] = dist_match.group(1).strip()[:50]

            # --- Extract M/F/3rd Gender counts ---
            # ECI PDFs typically have a summary table with headers:
            # "Male | Female | Third Gender | Total" or similar
            # Try table extraction first (more reliable)
            for page_i in range(min(3, len(pdf.pages))):
                pg = pdf.pages[page_i]
                tables = pg.extract_tables()
                for table in tables:
                    for row in table:
                        if row is None:
                            continue
                        row_text = " ".join(str(c) for c in row if c).lower()
                        if any(k in row_text for k in ["male", "female", "total"]):
                            nums = re.findall(r"\d+", row_text)
                            if len(nums) >= 3:
                                try:
                                    # Typical order: Male, Female, 3rd, Total
                                    result["male"] = int(nums[-4]) if len(nums) >= 4 else int(nums[0])
                                    result["female"] = int(nums[-3]) if len(nums) >= 3 else int(nums[1])
                                    result["third_gender"] = int(nums[-2]) if len(nums) >= 2 else 0
                                    result["total"] = int(nums[-1])
                                    if result["total"] > 0:
                                        break
                                except (ValueError, IndexError):
                                    pass
                    if result["total"] > 0:
                        break

            # Fallback: regex on raw text for M/F counts
            if result["total"] == 0:
                # Pattern: "Total Electors: Male 412 Female 398 Third Gender 0 Total 810"
                total_match = re.search(
                    r"Total\s+Elector[s]?\s*[:\-]?\s*"
                    r"(?:Male\s+)?(\d+)\s+"
                    r"(?:Female\s+)?(\d+)\s+"
                    r"(?:Third\s+Gender\s+)?(\d+)\s+"
                    r"(?:Total\s+)?(\d+)",
                    text, re.IGNORECASE
                )
                if total_match:
                    result["male"] = int(total_match.group(1))
                    result["female"] = int(total_match.group(2))
                    result["third_gender"] = int(total_match.group(3))
                    result["total"] = int(total_match.group(4))

                # Second fallback: just find "Total" followed by a number
                if result["total"] == 0:
                    tot_match = re.search(r"\bTotal\b[^\d]*(\d{3,4})\b", text, re.IGNORECASE)
                    if tot_match:
                        result["total"] = int(tot_match.group(1))

            result["female_pct"] = (
                round(result["female"] / result["total"] * 100, 2)
                if result["total"] > 0 else 0
            )

    except Exception as e:
        log.warning(f"Error extracting {pdf_path}: {e}")
        return None

    return result


def extract_district(
    district: str,
    ac_code: Optional[str] = None,
    raw_dir: Path = RAW_DIR,
    out_dir: Path = OUT_DIR,
) -> pd.DataFrame:
    """Extract all booths for a district (or single AC) from downloaded PDFs."""

    dist_dir = raw_dir / district
    if not dist_dir.exists():
        log.error(f"No downloaded PDFs found at {dist_dir}")
        log.error("Run 01_download_sir_rolls.py first.")
        return pd.DataFrame()

    # Find all PDF files
    if ac_code:
        pattern = f"{ac_code}_*/*.pdf"
    else:
        pattern = "*/*.pdf"

    pdf_files = list(dist_dir.glob(pattern))
    log.info(f"Found {len(pdf_files)} PDFs in {dist_dir}")

    if not pdf_files:
        log.warning("No PDFs found. Check download step.")
        return pd.DataFrame()

    records = []
    for i, pdf_path in enumerate(pdf_files):
        if i % 50 == 0:
            log.info(f"  Processing {i}/{len(pdf_files)} — {pdf_path.parent.name}")

        # Infer AC from directory name (format: "{ac_code}_{ac_name}")
        dir_parts = pdf_path.parent.name.split("_", 1)
        inferred_ac_code = dir_parts[0] if len(dir_parts) >= 1 else None
        inferred_ac_name = dir_parts[1].replace("_", " ") if len(dir_parts) >= 2 else None

        rec = extract_booth_summary(pdf_path)
        if rec:
            # Prefer inferred over extracted (more reliable)
            if not rec["ac_code"]:
                rec["ac_code"] = inferred_ac_code
            if not rec["ac_name"]:
                rec["ac_name"] = inferred_ac_name
            if not rec["district"]:
                rec["district"] = district
            records.append(rec)

    df = pd.DataFrame(records)
    if df.empty:
        log.warning("No data extracted.")
        return df

    # Clean and sort
    df["ac_code"] = pd.to_numeric(df["ac_code"], errors="coerce")
    df["part_no"] = pd.to_numeric(df["part_no"], errors="coerce")
    df = df.sort_values(["ac_code", "part_no"]).reset_index(drop=True)

    # Save
    out_path = out_dir / f"sir_rolls_{district.lower().replace(' ', '_')}.csv"
    df.to_csv(out_path, index=False)
    log.info(f"\nSaved {len(df)} booth records → {out_path}")
    log.info(f"Total electors: {df['total'].sum():,} | Female: {df['female'].sum():,} ({df['female'].sum()/df['total'].sum()*100:.1f}%)")

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract WB SIR roll PDFs to structured CSV")
    parser.add_argument("--district", default="Murshidabad")
    parser.add_argument("--ac_code", default=None, help="Single AC code (optional)")
    args = parser.parse_args()

    df = extract_district(district=args.district, ac_code=args.ac_code)
    if not df.empty:
        print(df[["ac_name", "part_no", "booth_name", "male", "female", "third_gender", "total", "female_pct"]].head(20).to_string())
