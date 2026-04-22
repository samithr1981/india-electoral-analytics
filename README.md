# Election Booth Intelligence
### Open-source electoral analytics platform for India

A civic technology tool that transforms publicly available Election Commission of India data into booth-level electoral intelligence. Built for researchers, journalists, political scientists, and civil society organisations.

> **Data disclaimer:** This tool uses exclusively public data published by the Election Commission of India, Census of India, and state Chief Electoral Officer portals. It is intended for electoral research, journalism, civic education, and transparency.

---

## What it does

Indian elections are decided at the polling booth level. The ECI publishes extraordinarily granular data — booth-wise voter counts, gender splits, turnout, candidate-wise results — but almost none of it is used systematically for research or analysis.

This tool aggregates, structures, and visualises that data so anyone can answer:

- Which booths in a constituency are genuinely competitive vs already decided?
- How have elector counts changed across elections in each district?
- Which booths have the highest proportion of voters whose rights are suspended under administrative review?
- What is the minimum vote count needed to win a given seat at different turnout scenarios?
- How have female voter participation rates changed over time?

---

## Dashboard tabs

| Tab | What you see |
|-----|-------------|
| State overview | All districts — elector trends, deletion map, adjudication summary |
| District deep dive | AC-level summary, demographic overlay, votes-to-win |
| Booth intelligence | Full booth table — searchable, sortable, all fields, CSV export |
| Adjudication crisis | Booths with suspended voters, restoration tracker |
| Swing analysis | Micro-swing booths, votes-to-win calculator, flip map |
| Campaign ops | Worker assignment, contact tracking, election day targets |
| Data pipeline | Run extraction scripts, check data status |

---

## Booth classification framework

Every polling booth is classified into one of four categories based on historical results:

| Category | Definition | Research implication |
|----------|-----------|---------------------|
| A — Secure | Dominant party >65% in last two elections | Stable, low volatility |
| B — Swing | Margin <50 votes OR winner flipped between elections | High volatility, outcome-determining |
| C — Unfavourable | Opposition >65% in last two elections | Stable opposition territory |
| D — Crisis | >10% of registered voters under administrative suspension | Enfranchisement risk |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/samithr1981/election-booth-intelligence.git
cd election-booth-intelligence

# 2. Install
pip install -r requirements.txt

# 3. Generate demo data (all districts, no PDFs needed)
python pipeline/00_generate_demo_data.py --all

# 4. Launch
streamlit run app.py
```

Demo data generates in under 60 seconds. No API keys or downloads required.

---

## Production mode — real ECI data

### Step 1 — Electoral rolls

1. Go to [voters.eci.gov.in](https://voters.eci.gov.in/download-eroll)
2. Select state → year → latest Final Roll → district → AC
3. Download all booth PDFs and save to: `data/raw/sir_rolls/{District}/`

```bash
python pipeline/02_extract_sir_rolls.py --district "District Name"
```

### Step 2 — Adjudication lists

1. Go to your state Chief Electoral Officer portal → SIR section
2. Download Adjudication Supplementary Lists for each AC

```bash
python pipeline/03_extract_adjudication.py --district "District Name"
```

### Step 3 — Form 20 booth-wise results

1. Go to [results.eci.gov.in](https://results.eci.gov.in)
2. Download Form 20 for each AC for last two elections

```bash
python pipeline/04_extract_form20.py --district "District Name" --year 2021
python pipeline/04_extract_form20.py --district "District Name" --merge
```

---

## Data sources — all public

| Source | URL | Data |
|--------|-----|------|
| ECI voter portal | voters.eci.gov.in | Electoral rolls, booth-level M/F counts |
| ECI results | results.eci.gov.in | Form 20 booth-level votes per candidate |
| State CEO portals | state-specific | Adjudication and suspension lists |
| Census of India 2011 | censusindia.gov.in | District demographics |

---

## Tech stack

- **Streamlit** — dashboard
- **pdfplumber** — PDF extraction
- **Plotly** — visualisations
- **pandas / numpy** — classification and analysis
- **Python 3.10+**

---

## Extending to other states

The framework works for any Indian state. Add district and AC mappings in the pipeline scripts and run for your target district. Pull requests welcome.

---

## Licence

MIT — free to use, modify, and distribute with attribution.

---

*Built with ECI open data · Census of India 2011 · Python · Streamlit*  
*Intended for electoral research, journalism, and civic education*
