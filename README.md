# CBAM Analysis

## Research Question
Which countries exporting goods to the EU face the greatest 
carbon cost exposure under CBAM, and what does that mean 
for trade competitiveness?

## Data Sources
- EU JRC Report JRC134682: emission intensities by country and production route
- Eurostat COMEXT: EU import volumes by country and CBAM-covered product category
- European Energy Exchange: EU ETS carbon price history

## Key Metrics
- Emission intensity (tonnes CO2 per tonne of material)
- CBAM threshold per material category
- Implied CBAM cost exposure (euros per tonne)
- EU import volume by country and material (tonnes, 2024)

## CBAM-Covered Materials
Cement, iron and steel, aluminium, fertilizers, electricity, hydrogen

## Project Structure
- data/raw: untouched source files
- data/processed: cleaned and structured outputs
- notebooks: exploration and EDA
- src: reusable functions and modules
- db: SQLite database created from processed data
