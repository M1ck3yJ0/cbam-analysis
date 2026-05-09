# Raw Data Sources

## CBAM Default Values Legal Basis (Definitive Period)
- File: not stored locally (40MB). Access via official source link below.
- Source: EUR-Lex, Official Journal of the European Union
- URL: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202502621
- ELI: http://data.europa.eu/eli/reg_impl/2025/2621/oj
- Citation: Commission Implementing Regulation (EU) 2025/2621 of 16 December 
  2025 laying down rules for the application of Regulation (EU) 2023/956 
  of the European Parliament and of the Council as regards the establishment 
  of default values
- Notes: Authoritative legal source for all definitive period default values.
  Reference this when citing CBAM threshold figures.

## JRC GHG Emission Intensities Report
- File: `JRC134682.pdf`
- Source: European Commission, Joint Research Centre
- URL: https://publications.jrc.ec.europa.eu/repository/handle/JRC134682
- DOI: https://data.europa.eu/doi/10.2760/359533
- Citation: Vidovic, D., Marmier, A., Zore, L. and Moya, J., Greenhouse gas 
  emission intensities of the steel, fertilisers, aluminium and cement 
  industries in the EU and its main trading partners, Publications Office 
  of the European Union, Luxembourg, 2023
- Downloaded: 2025-05-07
- Notes: Primary source for country-level emission intensities by material 
  and production route. Underpins CBAM default values.
  
## JRC GHG Emission Intensity of Hydrogen Production
- File: `JRC135067.pdf`
- Source: European Commission, Joint Research Centre
- URL: https://publications.jrc.ec.europa.eu/repository/handle/JRC135067
- DOI: https://data.europa.eu/doi/10.2760/744837
- Citation: Dolci, F. and Arrigoni, A., Estimation of the global average 
  GHG emission intensity of hydrogen production, Publications Office of 
  the European Union, Luxembourg, 2023
- Downloaded: 2025-05-07
- Notes: Hydrogen-specific emission intensity data to complement JRC134682. 
  Covers global average only, not country-level breakdown.

## Ember Yearly Electricity Data
- File: `yearly_full_release_long_format.csv`
- Source: Ember Energy
- URL: https://ember-energy.org/data/yearly-electricity-data/
- Downloaded: 2026-05-08
- License: Creative Commons Attribution 4.0 (CC BY 4.0)
- Notes: Long format file containing multiple electricity variables across
  200+ geographies from 2000 onwards. Will be filtered in extraction
  notebook to three variable types:

  1. CO2 intensity (gCO2/kWh): Category = "Power sector emissions",
     Subcategory = "CO2 intensity", Variable = "CO2 intensity"
     Primary metric for contextualizing indirect emissions in CBAM defaults.

  2. Installed capacity by fuel type (GW): Category = "Capacity",
     Subcategory = "Fuel", Variables = Coal, Gas, Hydro, Nuclear, Solar,
     Wind, Other Renewables. Plus Aggregate Clean and Fossil totals.
     Used to assess clean energy infrastructure in place.

  3. Electricity generation by fuel type (TWh): Category = "Electricity
     generation", Subcategory = "Fuel", same variables as capacity.
     Used to compare actual generation against installed capacity,
     revealing utilization gaps and grid composition.

  Together these three layers support analysis of not just how dirty a
  country's grid is, but why, and how much structural capacity exists
  for improvement.
  
  ## Eurostat COMEXT Trade Data
- File: not stored locally (API pull)
- Source: Eurostat COMEXT Database
- Dataset: DS-045409 - EU trade since 1988 by HS2-4-6 and CN8
- API endpoint: https://ec.europa.eu/eurostat/api/comext/dissemination
- Accessed via: eurostat Python package (pip install eurostat)
- Pulled: 2026-05-09
- License: Eurostat open data, free reuse with attribution
- Notes: EU27 aggregate imports only (reporter = EU27_2020), flow = 1
  (imports). All partner countries returned. CBAM-covered CN codes only,
  batched by material group. Years 2020-2024. Both VALUE_IN_EUROS and
  QUANTITY_IN_100KG (converted to tonnes in processed output).
  Electricity excluded from scope. Dataset DS-059322 previously
  referenced in planning is no longer available for API dissemination
  as of May 2026, replaced by DS-045409.
