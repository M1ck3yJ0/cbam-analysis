# 01 — Which Countries Face the Biggest CBAM Bill?

**Part of the [CBAM Analysis Portfolio](../../README.md)**

---

## What This Is

The EU Carbon Border Adjustment Mechanism (CBAM) came into full effect on 1 January 2026. It requires companies importing certain goods into the EU to purchase carbon certificates based on the emissions embedded in those goods. In short: the dirtier the production, the higher the bill.

This project estimates the total CBAM certificate cost faced by each of the 119 countries covered by the regulation, using official EU default emission values and 2024 EU import volumes. The result is a country-level ranking of CBAM cost exposure across five sectors: iron and steel, aluminium, cement, fertilizers, and hydrogen.

**Top-line finding:** China, Turkey, India, and Russia account for the largest estimated CBAM bills, driven primarily by iron and steel exports to the EU.

---

## Methodology

### The Core Calculation

```
Estimated CBAM cost (EUR) = import volume (tonnes)
                            x default emission value (tCO2/t)
                            x certificate price (EUR/tCO2)
```

### Data Sources

| Input | Source | Notes |
|---|---|---|
| Default emission values | EU Commission, CBAM Regulation Annex | Official values per country, CN code, and production route. Already include the 2026 markup (10% most sectors, 1% fertilizers). |
| EU import volumes | Eurostat COMEXT, dataset DS-045409 | 2024 annual flows, QUANTITY_IN_TONNES indicator only |
| CBAM certificate price | European Commission, April 2026 | EUR 75.36/tCO2, first official published price |

### Key Decisions

**Default emission values used throughout.** The CBAM regulation gives importers two options: use the EU-published default values (which carry a penalty markup), or submit verified actual emissions from their supplier (no markup). This project uses defaults only, representing the baseline scenario where no importer has invested in verification. A follow-on project will model the verified emissions scenario and the gap between the two.

**Worst-case production route per country/product.** Some countries have multiple production routes published for the same CN code (e.g. both BF-BOF and Scrap-EAF for the same steel product). Where this occurs, the route with the highest default emission value is used. This gives a conservative upper-bound estimate.

**All 119 CBAM countries retained.** Countries with a published default but no recorded EU imports in 2024 appear in the output with a cost of zero. They are not excluded.

**Certificate price assumption.** EUR 75.36/tCO2 is the first official CBAM certificate price published by the European Commission in April 2026. This price tracks the EU ETS and will fluctuate. The price is parameterized in the calculations notebook and can be updated easily.

### Limitations

- Import volumes are from 2024, the last full year before CBAM's definitive phase. Trade patterns may shift as the regulation beds in.
- Default emission values carry a penalty markup precisely because they are conservative estimates. Countries whose actual production is cleaner than the default are overestimated here.
- 22 countries with published CBAM defaults had no recorded EU imports for CBAM-covered products in 2024. They appear with zero cost.

---

## Files

```
01_country_exposure/
    calculations.ipynb    — full calculation pipeline, outputs to db/cbam.db
    app.py                — Streamlit dashboard (coming soon)
    README.md             — this file
```

### Output Tables (written to `db/cbam.db`)

| Table | Grain | Rows |
|---|---|---|
| `cbam_cost_by_country_sector` | (country, sector, cn_code) | 10,641 |
| `cbam_cost_by_country` | country | 119 |
| `cbam_cost_by_sector` | sector | 5 |

---

## How to Run

**Prerequisites:** complete the database first by running notebook 08 in the `notebooks/` folder. This generates `db/cbam.db`.

```bash
# From repo root
cd projects/01_country_exposure
jupyter notebook calculations.ipynb
```

Or open `calculations.ipynb` directly in VS Code and run all cells. The notebook is fully idempotent and safe to re-run.

To launch the dashboard once `app.py` is complete:

```bash
streamlit run projects/01_country_exposure/app.py
```

---

## Part of a Larger Project

This is one piece of a portfolio suite exploring CBAM from multiple angles. The full data pipeline (extraction, cleaning, and database build) lives in the `notebooks/` folder and is shared across all projects.

Other projects in this suite will cover verified vs. default emissions gaps, grid electricity intensity exposure for aluminium and EAF steel producers, and trade flow trends over 2020 to 2024.