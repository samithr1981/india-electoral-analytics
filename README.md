# WB 2026 Election Strategy Intelligence
### Booth-level campaign ops tool — Murshidabad first, all 23 districts ready

---

## What this does

A full-stack election strategy tool covering the 3-tier framework:

| Tier | What | Scripts |
|------|------|---------|
| 1 — Data acquisition | Download SIR 2026 rolls + adjudication lists + Form 20 results | pipeline/01–04 |
| 2 — Booth classification | A/B/C/D categories (Stronghold/Swing/Hostile/SIR-adj) | pipeline/03 |
| 3 — Campaign ops | Worker assignment, daily contact targets, D-Day tracker | app.py |

---

## Quick start (demo mode — no PDFs needed)

```bash
# 1. Install
pip install -r requirements.txt

# 2. Generate realistic demo data for Murshidabad
python pipeline/00_generate_demo_data.py

# 3. Launch
streamlit run app.py
```

---

## Production mode (real ECI data)

### Step 1 — Download SIR 2026 electoral rolls

**Manual (recommended):**
1. Go to https://voters.eci.gov.in/download-eroll
2. State: West Bengal | Year: 2026 | Roll type: **SIR FinalRoll-Rev2 - 2026**
3. For each AC in your target district, download all booth PDFs
4. Save as: `data/raw/sir_rolls/{District}/{ac_code}_{ac_name}/part_NNN.pdf`

**Automated:**
```bash
python pipeline/01_download_sir_rolls.py --district Murshidabad --max_acs 3 --delay 2.0
# Check output, then run full:
python pipeline/01_download_sir_rolls.py --district Murshidabad --all_acs --delay 1.5
```

Each PDF = 1 booth/part. Contains: part number, booth name, M/F/3rd gender elector counts.

### Step 2 — Extract PDF data

```bash
python pipeline/02_extract_sir_rolls.py --district Murshidabad
```
Output: `data/processed/sir_rolls_murshidabad.csv`

### Step 3 — Download adjudication lists

1. Go to https://ceowestbengal.wb.gov.in/SIR
2. For each AC: download **Adjudication Supplementary List No. 15A** (latest)
3. Save as: `data/raw/adjudication/Murshidabad/{ac_code}/adj_latest.pdf`

```bash
python pipeline/03_extract_adjudication.py --district Murshidabad
```
Output: `data/processed/adjudication_murshidabad.csv`

### Step 4 — Get Form 20 booth-wise results

1. Go to https://results.eci.gov.in → West Bengal
2. For each AC: download Form 20 for **2021 Assembly** AND **2019 Lok Sabha**
3. Save as: `data/raw/form20/Murshidabad/{2021 or 2019}/{ac_code}_ACName.pdf`

```bash
python pipeline/04_extract_form20.py --district Murshidabad --year 2021
python pipeline/04_extract_form20.py --district Murshidabad --year 2019
python pipeline/04_extract_form20.py --district Murshidabad --merge
```
Output: `data/processed/form20_murshidabad.csv`

### Step 5 — Classify all booths (master file)

```bash
python pipeline/03_extract_adjudication.py --district Murshidabad
```
Output: `data/processed/booths_classified_murshidabad.csv`

---

## Dashboard tabs

| Tab | Content |
|-----|---------|
| District overview | KPIs, elector trends (2016–2026), AC summary table, category distribution |
| Booth intelligence | Full booth table — searchable, sortable, exportable, all 32 fields |
| SIR adjudication | District-wise adj %, booth-level crisis map, Form 6 tracker |
| Swing analysis | Micro-swing booths, votes-to-win calculator, party switch map |
| Campaign ops | Worker assignment, daily contact tracking, D-Day hourly targets |
| Data pipeline | Run scripts, check data status, see instructions |

---

## Booth classification logic

| Category | Criteria | Campaign priority |
|----------|----------|-------------------|
| A — Stronghold | Party >65% share in both 2019 + 2021 | Maintain 85%+ turnout |
| B — Swing | Margin <50 votes OR party flipped 2019→2021 | 3× door-to-door min |
| C — Hostile | Opposition >65% share | Suppress consolidation |
| D — SIR adjudicated | >10% electors under adjudication | Form 6 restoration NOW |

**Priority order: D > B > C > A**

---

## Extending to other districts

```python
# In pipeline/01_download_sir_rolls.py, add AC mapping:
MY_DISTRICT_ACS = {
    "201": "AC Name 1",
    "202": "AC Name 2",
    # ... (get codes from voters.eci.gov.in)
}

# Then run:
python pipeline/01_download_sir_rolls.py --district "North 24 Parganas" --all_acs
```

---

## Key data sources

| Source | URL | Data |
|--------|-----|------|
| ECI voter portal | voters.eci.gov.in | SIR 2026 rolls (booth-level M/F counts) |
| ECI results | results.eci.gov.in | Form 20 (booth-level votes per candidate) |
| CEO West Bengal | ceowestbengal.wb.gov.in/SIR | Adjudication lists per AC |
| TCPD Lok Dhaba | tcpd.ashoka.edu.in | Historical constituency results |
| Census 2011 | censusindia.gov.in | District demographics |

---

## Critical SIR 2026 context

- **6.44 crore** confirmed electors statewide (SIR Final Roll, Feb 28 2026)
- **60.06 lakh** voters on roll but voting suspended (under adjudication)
- Top 5 districts: Murshidabad (11L), Malda (8.3L), Uttar Dinajpur (4.8L), N24P (5.9L), S24P (5.2L)
- Demographic skew: Muslim-majority booths disproportionately flagged
- For any party strategy in these districts: **Form 6 restoration = highest ROI**

---

## Deploy to Streamlit Cloud

```
# requirements.txt already included
# Point to app.py as entry point
# Set secrets if needed (none required for demo mode)
```
