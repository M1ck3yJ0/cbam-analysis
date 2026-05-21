# CBAM Analysis

End-to-end data engineering and analysis project exploring the economic
implications of the Carbon Border Adjustment Mechanism (CBAM) for global
trading partners, from raw regulatory and trade data through to a
structured relational database and interactive published outputs.

---

## Research Questions

- Which countries exporting CBAM-covered goods to the EU face the
  greatest carbon cost exposure, and how does that vary by material?
- How do production routes, grid carbon intensity, and trade volumes
  interact to determine a country's CBAM liability?
- Where does the gap between direct and indirect emissions reveal
  opportunities for decarbonization without changing production technology?
- What would shifting production routes or cleaning electricity grids
  mean for CBAM exposure over time?

---

## Outputs

### 01 | Country Exposure Dashboard
An interactive dashboard exploring CBAM cost exposure and EU export
dependency across 119 affected economies. Covers estimated CBAM bill
by country, cost per tonne, and sector-level breakdowns, with filters
by certificate price, sector, and country.

[View live dashboard](https://milcahjoseph-cbam-dashboard.streamlit.app/)

---

## Database Schema

The project consolidates six datasets into a normalized SQLite database.
The schema below shows table relationships across trade flows, emissions
defaults, production routes, grid intensity, and country reference data.

![Database schema diagram](db/schema_diagram.png)

---

## Data Sources

See `data/raw/README.md` for full source documentation and provenance.
Key sources include:

- EU Commission CBAM default values (Commission Implementing Regulation
  (EU) 2025/2621)
- JRC technical reports
- Eurostat COMEXT trade data (DS-045409)
- Worldsteel Sustainability Indicators 2025
- Ember Yearly Electricity Data

---

## Key Metrics

- CBAM default emission values by country and product (tCO2/t)
- Direct and indirect emission intensity split
- EU import volume by country and material (value in EUR, quantity in tonnes)
- Grid carbon intensity by country (gCO2/kWh)
- Steel production route emission intensities (BF-BOF, Scrap-EAF, DRI-EAF)
  sourced from Worldsteel global averages

---

## CBAM-Covered Materials

Cement, iron and steel, aluminium, fertilizers, hydrogen, electricity.

**Note on electricity:** Electricity is covered under CBAM but is treated
differently from the other five sectors. Rather than applying a per-tonne
default emission value, charges on imported electricity are based on the
carbon intensity of the exporting country's power grid. Electricity is
therefore excluded from the trade flow data, but grid carbon intensity
data from Ember is included in the dataset and covers all 215 countries.

---

## Repository Structure

```
cbam-analysis/
├── data/
│   ├── raw/          # source files (some large files not committed,
│   │                 # see data/raw/README.md for download instructions)
│   ├── processed/    # extraction outputs, committed
│   └── clean/        # cleaned and aligned outputs, committed
├── db/               # SQLite database (generated, committed)
├── notebooks/        # numbered pipeline notebooks (01-08) and analysis
├── projects/         # analytical outputs, one subdirectory per project
├── src/              # reusable functions and modules (planned)
├── README.md
└── requirements.txt
```

---

## Reproducing the Database

The compiled SQLite database is committed to this repo and can be used
directly. To reproduce it from source, run notebooks 01 through 08 in
sequence after installing dependencies (`pip install -r requirements.txt`)
and obtaining API keys for any data sources fetched programmatically
(see `data/raw/README.md`).

---

## Status

Data pipeline complete. All six datasets extracted, cleaned, and loaded
into a structured SQLite database. First analytical output published.
Further analysis in progress.
