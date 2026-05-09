# CBAM Analysis

## About
An ongoing analytical project exploring the Carbon Border Adjustment 
Mechanism (CBAM) and its implications for global trade, industrial 
competitiveness, and decarbonization incentives. The project combines 
official EU regulatory data, trade statistics, emissions research, and 
grid carbon intensity data to build a picture of which countries face 
the greatest CBAM exposure, why, and what pathways exist to reduce it.

New analyses, charts, and data stories are added regularly as the 
project develops.

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
Cement, iron and steel, aluminium, fertilizers, electricity, hydrogen

## Data Sources
See `data/raw/README.md` for full source documentation and provenance.
Key sources include EU Commission CBAM default values, JRC technical 
reports, Eurostat COMEXT trade data, Worldsteel sustainability indicators, 
Ember yearly electricity data, and EU ETS carbon price data.

## Key Metrics
- CBAM default emission values by country and product (tCO2/t)
- Direct and indirect emission intensity split
- Implied CBAM cost exposure (euros per tonne)
- EU import volume by country and material
- Grid carbon intensity by country (gCO2/kWh)
- Steel production route emission intensities (BF-BOF, EAF, DRI)

## Repository Structure
```
cbam-analysis/
├── data/
│   ├── raw/          # untouched source files
│   └── processed/    # cleaned structured outputs
├── notebooks/        # exploration and EDA
├── src/              # reusable functions and modules
├── db/               # SQLite database (generated, not committed)
├── README.md
└── requirements.txt
```

## How to Reproduce
1. Clone the repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run notebooks 01 onwards in sequence to extract and process data
6. Run notebook 07 to build the SQLite database

## Status
Active and ongoing. See commit history for latest additions.
