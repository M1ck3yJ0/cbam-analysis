# CBAM Analysis

## About
An ongoing analytical project exploring the Carbon Border Adjustment
Mechanism (CBAM) and its implications for global trade, industrial
competitiveness, and decarbonization incentives. The project combines
official EU regulatory data, trade statistics, emissions research, and
grid carbon intensity data to build a picture of which countries face
the greatest CBAM exposure, why, and what pathways exist to reduce it.

## Research Questions
- Which countries exporting CBAM-covered goods to the EU face the
  greatest carbon cost exposure, and how does that vary by material?
- How do production routes, grid carbon intensity, and trade volumes
  interact to determine a country's CBAM liability?
- Where does the gap between direct and indirect emissions reveal
  opportunities for decarbonization without changing production technology?
- What would shifting production routes or cleaning electricity grids
  mean for CBAM exposure over time?

## CBAM-Covered Materials
Cement, iron and steel, aluminium, fertilizers, hydrogen, electricity

**Note on electricity:** Electricity is covered by CBAM but works
differently from the other five sectors. Rather than using a per-tonne
default emission value, CBAM charges on imported electricity are based
on how carbon-intensive the exporting country's power grid is. For this
reason, electricity is excluded from the trade flow data but grid carbon
intensity data from Ember is included in the dataset and covers all
215 countries.

## Data Sources
See `data/raw/README.md` for full source documentation and provenance.
Key sources include EU Commission CBAM default values (Commission
Implementing Regulation (EU) 2025/2621), JRC technical reports,
Eurostat COMEXT trade data (DS-045409), Worldsteel Sustainability
Indicators 2025, and Ember Yearly Electricity Data.

## Key Metrics
- CBAM default emission values by country and product (tCO2/t)
- Direct and indirect emission intensity split
- EU import volume by country and material (value in EUR and quantity
  in tonnes)
- Grid carbon intensity by country (gCO2/kWh)
- Steel production route emission intensities (BF-BOF, Scrap-EAF,
  DRI-EAF) sourced from Worldsteel global averages

## Repository Structure
```
cbam-analysis/
├── data/
│   ├── raw/          # source files (some large files not committed,
│   │                 # see data/raw/README.md for download instructions)
│   ├── processed/    # extraction outputs, committed
│   └── clean/        # cleaned and aligned outputs, committed
├── notebooks/        # numbered pipeline notebooks (01-08) and analysis
├── src/              # reusable functions and modules (planned)
├── db/               # SQLite database (generated, not committed)
├── README.md
└── requirements.txt
```

## How to Reproduce
1. Clone the repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Download any large raw files not committed to the repo
   (see `data/raw/README.md` for sources and instructions)
6. Run notebooks 01 through 07 in sequence to extract, process,
   and clean all datasets
7. Run notebook 08 to build and verify the SQLite database

Note: `data/processed/` and `data/clean/` are committed and can be
used directly to skip to step 7 (nb_08) if you do not need to re-run
extraction and cleaning.

## Status
Data pipeline complete (notebooks 01-08). All datasets extracted,
cleaned, and loaded into a SQLite database. Analysis and dashboard
layer in progress. See commit history for latest additions.
