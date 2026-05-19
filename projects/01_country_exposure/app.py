# ── CBAM Country Exposure Dashboard ──────────────────────────────────────────
# Project 01: Which countries face the biggest CBAM bill?
#
# Layout:
#   Sticky filter bar: certificate price slider, sector pills, country selectbox
#   5 KPI cards (dynamic, country-specific when selected)
#   Row 1: Choropleth map + top 10 bar chart (both respond to map metric toggle)
#   Row 2: Sector donut [1] | EAF scenario chart [2] | Grid capacity/utilization [2]
#
# Run from repo root:
#   streamlit run projects/01_country_exposure/app.py

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title            = 'CBAM Country Exposure',
    page_icon             = '🌍',
    layout                = 'wide',
    initial_sidebar_state = 'collapsed',
)

# ── Theme constants ───────────────────────────────────────────────────────────
BG         = '#f5f4f0'
BG_CARD    = '#ffffff'
BORDER     = '#d3d1c9'
TEXT_DARK  = '#18201a'
TEXT_MID   = '#908e86'
TEXT_LIGHT = '#b8b6ae'
ACCENT     = '#3a6b45'
ACCENT_MID = '#74b583'
ACCENT_POP = '#e83b2a'
MAP_MIN    = '#d3d1c9'
MAP_MAX    = '#3a6b45'

SECTOR_COLORS = {
    'Iron and Steel' : '#5c6b5e',
    'Aluminium'      : '#74b583',
    'Cement'         : '#8faa92',
    'Fertilizers'    : '#3a6b45',
    'Hydrogen'       : '#a8b5aa',
    'Electricity'    : '#d3d1c9',
}

FOSSIL_FUELS = ['Coal', 'Gas', 'Other Fossil']
CLEAN_FUELS  = ['Hydro', 'Wind', 'Solar', 'Nuclear', 'Other Renewables']
FUEL_COLORS  = {
    # Fossil fuels: neutral gray scale, dark to light
    'Coal'            : '#4a4a4a',
    'Gas'             : '#9e9e9e',
    'Other Fossil'    : '#bdbdbd',
    # Clean fuels: teal-green ramp, lightest to deepest.
    # Teal leans cooler than the brand greens so clean fuels read
    # as their own category without blending into the donut or EAF bars.
    'Other Renewables': '#b2dfcc',
    'Solar'           : '#6dbf9e',
    'Wind'            : '#2e9e7a',
    'Nuclear'         : '#1a7a5e',
    'Hydro'           : '#0d5c45',
}

# EAF scenario constants
EAF_ELECTRICITY_KWH_PER_T = 450     # kWh/t crude steel, scrap-EAF (IEA / Transition Asia)
CLEAN_GRID_INTENSITY       = 29.66  # gCO2/kWh, Norway 2024 (Ember)
CLEAN_GRID_COUNTRY         = 'Norway'
EAF_DIRECT_EMISSIONS       = 0.69   # tCO2/t, Worldsteel Scrap-EAF 2024
BOF_DIRECT_EMISSIONS       = 2.34   # tCO2/t, Worldsteel BF-BOF 2024

# Route dropdown options: label -> (eaf_code, bof_code)
ROUTE_OPTIONS = {
    'Carbon Steel'   : ('E', 'C'),
    'Low Alloy Steel': ('H', 'F'),
}

# ── Steel default lookup ─────────────────────────────────────────────────────
# Hoisted to module level so it can be called both from the KPI cards
# and from the EAF scenario chart without duplication.
# Returns avg_default_2026 tCO2/t for a given route code, optionally
# country-specific; falls back to global average if no country row exists.
def get_default(route_code, country=None):
    """Look up the CBAM default emission factor (tCO2/t) for a steel route."""
    # df_defaults_steel is loaded below; forward reference is fine at call time.
    df = df_defaults_steel[df_defaults_steel['route_code'] == route_code]
    if df.empty:
        return None
    if country:
        row = df[df['country'] == country]
        if not row.empty:
            val = float(row.iloc[0]['avg_default_2026'])
            return val if pd.notna(val) else None
    global_avg = float(df['avg_default_2026'].mean())
    return global_avg if pd.notna(global_avg) else None


# BASE_PRICE_EUR matches the notebook constant. Used only to rescale the
# per-sector convenience cost columns stored in cbam_cost_by_country.
BASE_PRICE = 75.36

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=DM+Serif+Display&display=swap');

:root {{ --primary-color: {ACCENT} !important; }}

html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif;
    color: {TEXT_DARK};
}}
h1, h2, h3 {{
    font-family: 'DM Serif Display', serif;
    color: {TEXT_DARK};
}}
.main, .block-container {{
    background-color: {BG};
}}
.block-container {{
    padding-top: 0 !important;
    padding-bottom: 2rem;
    max-width: 1400px;
}}
[data-testid="collapsedControl"] {{ display: none; }}
[data-testid="stSidebar"] {{ display: none; }}

.filter-bar {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    padding: 0.9rem 0 0.75rem 0;
    margin-bottom: 1.25rem;
}}
.streamlit-expanderContent {{
    padding: 0.5rem 15rem 0.7rem 15rem !important;
}}
.filter-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: {TEXT_LIGHT};
    margin-bottom: 0.15rem;
}}
.kpi-card {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    border-left: 4px solid {ACCENT};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
    min-height: 68px;
}}
.kpi-card-country {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    border-left: 4px solid {ACCENT_POP};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
    min-height: 68px;
}}
.kpi-card-neutral {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    border-left: 4px solid {BORDER};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
    min-height: 68px;
}}
.kpi-label {{
    font-size: 0.63rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: {TEXT_LIGHT};
    margin-bottom: 0.2rem;
}}
.kpi-value {{
    font-size: 1.15rem;
    font-weight: 500;
    color: {TEXT_DARK};
    line-height: 1.2;
}}
.kpi-sub {{
    font-size: 0.68rem;
    color: {TEXT_LIGHT};
    margin-top: 0.2rem;
    line-height: 1.4;
}}
.section-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: {TEXT_LIGHT};
    margin-bottom: 0.3rem;
    margin-top: 0.1rem;
}}
.method-note {{
    font-size: 0.62rem;
    color: {TEXT_LIGHT};
    margin-top: 0.3rem;
    line-height: 1.4;
    font-style: italic;
}}
[data-testid="stPills"] button {{
    font-size: 0.72rem !important;
    padding: 2px 10px !important;
    border-radius: 20px !important;
    border: 1px solid {BORDER} !important;
    background: transparent !important;
    color: {TEXT_MID} !important;
    font-family: 'DM Sans', sans-serif !important;
}}
[data-testid="stPills"] button[aria-pressed="true"] {{
    background: {ACCENT} !important;
    border-color: {ACCENT} !important;
    color: white !important;
}}
[data-testid="stPills"] button:hover {{
    border-color: {ACCENT} !important;
    color: {ACCENT} !important;
}}
[data-testid="stButton"] button {{
    font-size: 0.72rem !important;
    padding: 2px 8px !important;
    height: 24px !important;
    background: transparent !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT_MID} !important;
    border-radius: 4px !important;
}}
[data-testid="stSlider"] {{ padding-top: 0.1rem; padding-bottom: 0; }}
[data-testid="stDataFrame"] {{ border-radius: 6px; overflow: hidden; }}

/* ── Steel grade selectbox — compact sizing to match inline label ────────────
   Targets the select control input and its inner text span. The min-height
   override shrinks the overall widget height; font-size matches the 0.68rem
   "Steel grade" label rendered beside it.                                   */
[data-testid="stSelectbox"] div[data-baseweb="select"] {{
    min-height: 1.4rem !important;
    font-size: 0.62rem !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    min-height: 1.4rem !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    font-size: 0.62rem !important;
}}
[data-testid="stSelectbox"] span {{
    font-size: 0.62rem !important;
    color: {TEXT_DARK} !important;
}}

/* ── Info icon tooltip ──────────────────────────────────────────────────────
   .info-icon   : the ⓘ glyph, inline with the section label text.
   .info-tooltip: the pop-up box, hidden until hover.
   position:relative on the wrapper allows the tooltip to anchor correctly.
   z-index:1000 ensures it floats above Plotly chart canvases.         */
.info-wrap {{
    display: inline-flex;
    align-items: center;
    gap: 0.3em;
    position: relative;
}}
.info-icon {{
    font-size: 0.65rem;
    color: {TEXT_LIGHT};
    cursor: default;
    line-height: 1;
    user-select: none;
    /* keep the icon vertically aligned with the label caps */
    position: relative;
    top: -0.05em;
}}
.info-icon:hover {{
    color: {TEXT_MID};
}}
.info-tooltip {{
    display: none;
    position: absolute;
    width: 280px;
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 0.55rem 0.7rem;
    font-size: 0.62rem;
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    color: {TEXT_MID};
    line-height: 1.5;
    box-shadow: 0 4px 12px rgba(0,0,0,0.10);
    z-index: 1000;
    pointer-events: none;
    white-space: normal;
}}
/* Tooltip appears to the right of the icon, vertically centered.
   Used for: map, sector donut, EAF chart.                        */
.tip-right {{
    left: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%);
}}
/* Tooltip appears to the left of the icon, vertically centered.
   Used for: top 10 bar, grid generation mix.                     */
.tip-left {{
    right: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%);
}}
.info-icon:hover .info-tooltip,
.info-wrap:hover .info-tooltip {{
    display: block;
}}
</style>
""", unsafe_allow_html=True)


# ── Info label helper ─────────────────────────────────────────────────────────
# Renders a section label with an inline ⓘ icon. Hovering the icon shows
# the tooltip text above the label. Call wherever a section-label is rendered.
# Extra inline style overrides (e.g. margin) can be passed via extra_style.
def info_label(label: str, tooltip: str, extra_style: str = '',
               tip_side: str = 'tip-right') -> str:
    """Return an HTML string: LABEL text + hover info icon with tooltip.

    tip_side controls the tooltip direction:
      'tip-right' : tooltip opens to the right (map, donut, EAF chart)
      'tip-left'  : tooltip opens to the left  (top 10 bar, grid mix)
    """
    return (
        f'<p class="section-label" style="{extra_style}">'
        f'{label}'
        f'<span class="info-wrap" style="margin-left:0.4em;">'
        f'<span class="info-icon">ⓘ'
        f'<span class="info-tooltip {tip_side}">{tooltip}</span>'
        f'</span>'
        f'</span>'
        f'</p>'
    )


# ── Database connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    """Return a persistent cached SQLite connection."""
    db_path = Path(__file__).parent.parent.parent / 'db' / 'cbam.db'
    assert db_path.exists(), f'Database not found at {db_path.resolve()}.'
    return sqlite3.connect(db_path, check_same_thread=False)

con = get_connection()


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_country_data():
    """Country-level exposure data.

    iso3, global export value, and the price-independent exposure ratio are
    all pre-joined in cbam_cost_by_country by the calculations notebook.
    No additional joins needed here.
    """
    return pd.read_sql("""
        SELECT
            country,
            iso2,
            iso3,
            rank,
            total_import_tonnes,
            total_eu_import_value_eur,
            global_cbam_export_value_eur,
            total_embedded_co2_high      AS embedded_co2_high,
            total_embedded_co2_low       AS embedded_co2_low,
            cbam_eu_exposure_ratio_high  AS exposure_ratio_high,
            cbam_eu_exposure_ratio_low   AS exposure_ratio_low,
            has_any_route_variation,
            export_data_year,
            is_fallback_year
        FROM cbam_cost_by_country
        ORDER BY rank
    """, con)

@st.cache_data
def load_granular_data():
    """Granular country x sector x CN code exposure data.

    Euro costs are not stored in this table. They are computed at runtime
    from embedded_co2 x the user-selected certificate price, so they always
    reflect the current slider value.
    """
    return pd.read_sql("""
        SELECT
            country,
            sector,
            has_route_variation,
            import_tonnes,
            eu_import_value_eur,
            embedded_co2_high_route  AS co2_high,
            embedded_co2_low_route   AS co2_low
        FROM cbam_cost_by_country_sector
    """, con)

@st.cache_data
def load_sector_cost_pivots():
    """Per-sector cost convenience columns stored at BASE_PRICE = 75.36.

    These are used only for the sector donut chart. The app rescales them
    to the user-selected certificate price before rendering:
        cost_at_selected = cost_at_base * (cert_price / BASE_PRICE)
    """
    return pd.read_sql("""
        SELECT
            country,
            cost_aluminium_high_route_eur,
            cost_cement_high_route_eur,
            cost_fertilizers_high_route_eur,
            cost_hydrogen_high_route_eur,
            cost_iron_and_steel_high_route_eur,
            cost_aluminium_low_route_eur,
            cost_cement_low_route_eur,
            cost_fertilizers_low_route_eur,
            cost_hydrogen_low_route_eur,
            cost_iron_and_steel_low_route_eur
        FROM cbam_cost_by_country
    """, con)

@st.cache_data
def load_grid_intensity():
    """Latest grid CO2 intensity per country from Ember."""
    # 2024 only. Countries with no 2024 Ember data are excluded entirely
    # to keep the dataset year-consistent with trade_flows and global_exports.
    return pd.read_sql("""
        SELECT country, year, co2_intensity_gco2_kwh
        FROM grid_co2_intensity
        WHERE year = 2024
    """, con)

@st.cache_data
def load_grid_capacity():
    """Latest installed capacity by fuel type."""
    return pd.read_sql("""
        SELECT country, year, fuel_type, subcategory, value, unit
        FROM grid_capacity
        WHERE year = (SELECT MAX(year) FROM grid_capacity)
          AND subcategory = 'Fuel'
    """, con)

@st.cache_data
def load_grid_generation():
    """Latest electricity generation by fuel type."""
    # 2024 only, consistent with all other data sources.
    return pd.read_sql("""
        -- unit = 'TWh' ensures we sum generation volumes only.
        -- The same (country, year, fuel_type) row also exists as '%'
        -- in the Ember source; mixing units would corrupt the totals.
        SELECT country, year, fuel_type, subcategory, value, unit
        FROM grid_generation
        WHERE year = 2024
          AND subcategory = 'Fuel'
          AND unit = 'TWh'
    """, con)

@st.cache_data
def load_cbam_defaults_steel():
    """CBAM default values for steel EAF and BOF routes, averaged per country.

    production_route_code is stored with parentheses in the DB, e.g. '(C)', '(E)'.
    The ROUTE_OPTIONS dict uses bare letters as keys for readability. The SQL
    LIKE pattern handles both formats so the query is robust to either convention.
    A cleaned bare-letter column is returned so get_default() can match simply.
    """
    return pd.read_sql("""
        SELECT
            country,
            production_route_code,
            TRIM(production_route_code, '()') AS route_code,
            AVG(default_2026)                 AS avg_default_2026
        FROM cbam_defaults
        WHERE TRIM(production_route_code, '()') IN ('C', 'E', 'F', 'H')
        GROUP BY country, production_route_code
    """, con)

df_countries        = load_country_data()
df_granular         = load_granular_data()
df_sector_pivots    = load_sector_cost_pivots()
df_grid_intensity   = load_grid_intensity()
df_grid_capacity    = load_grid_capacity()
df_grid_generation  = load_grid_generation()
df_defaults_steel   = load_cbam_defaults_steel()
ALL_SECTORS         = sorted(df_granular['sector'].unique().tolist())

# Global average uses 2024 data only. Falls back to 0 if no 2024 rows
# exist (should not happen but prevents a crash on first run).
global_grid_avg = (
    df_grid_intensity['co2_intensity_gco2_kwh'].mean()
    if not df_grid_intensity.empty else 0
)


# ── Session state ─────────────────────────────────────────────────────────────
if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = None


# ── Sticky filter bar ─────────────────────────────────────────────────────────
st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

st.markdown(
    # Space above, enlarged subtitle, CBAM defaults added, credit line below
    f'<div style="text-align:center; padding:1.4rem 0 1.2rem 0;">'
    f'<div style="font-family:\'DM Serif Display\', serif; '
    f'font-size:2rem; color:{TEXT_DARK}; line-height:1;">'
    f'CBAM Country Exposure</div>'
    f'<div style="font-size:0.78rem; color:{TEXT_LIGHT}; margin-top:0.35rem;">'
    f'EU trade flows · UN Comtrade · EU Commission CBAM Defaults · Ember · 2024'
    f'</div>'
    f'<div style="font-size:0.78rem; margin-top:0.3rem;">'
    f'<a href="https://milcahjoseph.com" target="_blank" '
    f'style="color:{TEXT_MID}; text-decoration:none;">Analysis &amp; Design: Milcah M. Joseph</a>'
    f' &nbsp;·&nbsp; '
    f'<a href="https://github.com/M1ck3yJ0/cbam-analysis" target="_blank" '
    f'style="color:{TEXT_MID}; text-decoration:none;">Data Pipeline: GitHub</a>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True)

# ── Filter state initialisation ──────────────────────────────────────────────
# Each widget uses a dedicated key so Streamlit owns the value directly.
# This eliminates the double-interaction bug that occurs when both value=
# and manual session_state writes are used together.
# filters_open persists the expander state across reruns so interactions
# inside the expander do not cause it to collapse.
if 'filter_cert_price' not in st.session_state:
    st.session_state['filter_cert_price'] = BASE_PRICE
if 'filter_sectors' not in st.session_state:
    st.session_state['filter_sectors'] = ALL_SECTORS
if 'filters_open' not in st.session_state:
    st.session_state['filters_open'] = False

def _keep_open():
    st.session_state['filters_open'] = True

def _reset_filters():
    st.session_state['filter_cert_price'] = BASE_PRICE
    st.session_state['filter_sectors']    = ALL_SECTORS
    st.session_state['selected_country']  = None
    st.session_state['filters_open']      = True

with st.expander('Filters: Certificate Price · Sectors · Country',
                 expanded=st.session_state['filters_open']):
    _pad_l, fc1, _pad_l, fc2, fc3, _pad_r, fc4, _pad_r = st.columns([0.15, 2, 0.15, 4, 2, 0.10, 1.3, 0.10])

    with fc1:
        st.markdown('<p class="filter-label">Certificate price (€/tCO₂)</p>',
                    unsafe_allow_html=True)
        st.slider(
            'Certificate price',
            min_value=25.0, max_value=150.0, step=0.5, format='€%.2f',
            key='filter_cert_price',
            label_visibility='collapsed',
            help=f'Default: €{BASE_PRICE} — first official EC CBAM price, April 2026',
            on_change=_keep_open,
        )

    with fc2:
        st.markdown('<p class="filter-label">Sectors</p>',
                    unsafe_allow_html=True)
        st.pills(
            'Sectors', options=ALL_SECTORS,
            default=st.session_state['filter_sectors'],
            selection_mode='multi', label_visibility='collapsed',
            key='filter_sectors',
            on_change=_keep_open,
        )

    with fc3:
        st.markdown('<p class="filter-label">Country</p>',
                    unsafe_allow_html=True)
        country_options = ['All countries'] + sorted(df_countries['country'].tolist())
        current_idx     = 0
        if st.session_state['selected_country'] in country_options:
            current_idx = country_options.index(st.session_state['selected_country'])
        sidebar_country = st.selectbox(
            'Country', options=country_options,
            index=current_idx, label_visibility='collapsed',
            on_change=_keep_open,
        )
        st.session_state['selected_country'] = (
            None if sidebar_country == 'All countries' else sidebar_country
        )

    with fc4:
        st.markdown('<p class="filter-label">&nbsp;</p>', unsafe_allow_html=True)
        st.button('↺ Reset filters', on_click=_reset_filters,
                  use_container_width=True)

# Read filter values from their widget keys
cert_price = st.session_state['filter_cert_price']
selected_sectors = st.session_state['filter_sectors'] or ALL_SECTORS

st.markdown('</div>', unsafe_allow_html=True)


# ── Derived data ──────────────────────────────────────────────────────────────
# All euro costs are computed here from embedded CO2 x the selected certificate
# price. Nothing is read directly from a stored euro cost column as a final
# value (the sector pivot columns are rescaled from BASE_PRICE below).

# Filter granular table to selected sectors, then compute costs at current price
df_g = df_granular[df_granular['sector'].isin(selected_sectors)].copy()
df_g['cost_high'] = df_g['co2_high'] * cert_price
df_g['cost_low']  = df_g['co2_low']  * cert_price

# Aggregate to country level from the filtered granular table
df_c = (
    df_g.groupby('country', as_index=False)
    .agg(
        cost_high               = ('cost_high',           'sum'),
        cost_low                = ('cost_low',            'sum'),
        import_tonnes           = ('import_tonnes',       'sum'),
        eu_import_value_eur     = ('eu_import_value_eur', 'sum'),
        co2_high                = ('co2_high',            'sum'),
        has_any_route_variation = ('has_route_variation', 'any'),
    )
    .sort_values('cost_high', ascending=False)
    .reset_index(drop=True)
)

# Join iso3, global export value, exposure ratio, and data quality flags
# from the country table. export_data_year feeds the map tooltip.
df_c = df_c.merge(
    df_countries[[
        'country', 'iso3',
        'global_cbam_export_value_eur',
        'exposure_ratio_high', 'exposure_ratio_low',
        'export_data_year', 'is_fallback_year',
    ]],
    on='country', how='left'
)

# Join grid intensity for the EAF chart and KPI card 4
df_c = df_c.merge(
    df_grid_intensity[['country', 'co2_intensity_gco2_kwh']],
    on='country', how='left'
)

# Cost as % of global CBAM-sector exports.
# exposure_ratio_high = embedded_co2_high / global_cbam_export_value_eur (tCO2/EUR).
# Multiplying by cert_price gives cost / global_export_value, i.e. the share.
# This correctly uses total global exports as the denominator, not EU import
# value, so it reflects how significant the CBAM bill is relative to the
# country's full export activity in these sectors.
df_c['cost_pct_export'] = (
    df_c['exposure_ratio_high'] * cert_price * 100
).round(2)

# Cost per tonne of CBAM-sector goods imported by the EU
df_c['cost_per_tonne'] = (
    df_c['cost_high'] / df_c['import_tonnes'].replace(0, float('nan'))
).round(2)

# Global totals used in KPI cards
total_cost_high  = df_c['cost_high'].sum()
total_cost_low   = df_c['cost_low'].sum()
total_co2        = df_g['co2_high'].sum()
total_global_exp = df_countries['global_cbam_export_value_eur'].sum()
total_eu_imports = df_c['eu_import_value_eur'].sum()
global_pct_exp   = (total_eu_imports / total_global_exp * 100) if total_global_exp else None
n_exposed        = (df_c['cost_high'] > 0).sum()
top3_cost        = df_c.head(3)['cost_high'].sum()
top3_share       = top3_cost / total_cost_high * 100 if total_cost_high else 0
top3_names       = ', '.join(df_c.head(3)['country'].tolist())

selected = st.session_state['selected_country']

sel_cost = sel_co2 = sel_pct = sel_eu_imp = sel_global_exp = sel_grid = sel_rank = sel_data_year = None
sel_fallback = False
if selected:
    sel_row = df_c[df_c['country'] == selected]
    if len(sel_row) > 0:
        s              = sel_row.iloc[0]
        sel_cost       = s['cost_high']
        sel_co2        = s['co2_high']
        sel_pct        = s['cost_pct_export']
        sel_eu_imp     = s['eu_import_value_eur']
        sel_global_exp = s['global_cbam_export_value_eur']
        sel_grid       = s['co2_intensity_gco2_kwh']
        sel_rank       = int(sel_row.index[0]) + 1
        sel_data_year  = s.get('export_data_year', None)
        sel_fallback   = bool(s.get('is_fallback_year', 0))


# ── KPI 5: Steel CO2 saving calculation ──────────────────────────────────────
# Estimates CO2 saved if the country's (or global) iron & steel CBAM-sector
# exports all switched from BOF default to EAF Verified at current grid.
# Route: Carbon Steel BOF ('C') vs EAF ('E') — the dominant global route.
_bof_code_kpi = 'C'
_eaf_code_kpi = 'E'
_bof_def_kpi  = get_default(_bof_code_kpi, selected if selected else None)
_eaf_def_kpi  = get_default(_eaf_code_kpi, selected if selected else None)

# Dream scenario: EAF Verified at clean grid (Norway), not current grid.
# This is the full theoretical ceiling — switch to EAF + clean energy.
_kpi5_grid = CLEAN_GRID_INTENSITY
_eaf_verified_tco2_per_t = (
    EAF_DIRECT_EMISSIONS + EAF_ELECTRICITY_KWH_PER_T * CLEAN_GRID_INTENSITY * 1e-6
)

# Steel cost for the selected country or global total
_price_ratio_kpi5 = cert_price / BASE_PRICE
if selected:
    _pivot = df_sector_pivots[df_sector_pivots['country'] == selected]
    _steel_cost_kpi5 = (
        float(_pivot.iloc[0]['cost_iron_and_steel_high_route_eur']) * _price_ratio_kpi5
        if not _pivot.empty else None
    )
else:
    _steel_cost_kpi5 = (
        df_sector_pivots['cost_iron_and_steel_high_route_eur'].sum() * _price_ratio_kpi5
    )

# Derive euro bill saving if all steel tonnes switched BOF -> EAF Verified
_kpi5_saving_eur = None
_kpi5_pct        = None
if _bof_def_kpi and _steel_cost_kpi5 and _steel_cost_kpi5 > 0:
    _steel_tonnes_kpi5  = _steel_cost_kpi5 / (_bof_def_kpi * cert_price)
    _cost_eaf_verified  = _steel_tonnes_kpi5 * _eaf_verified_tco2_per_t * cert_price
    _eur_saving         = _steel_cost_kpi5 - _cost_eaf_verified
    _kpi5_saving_eur    = _eur_saving
    _kpi5_pct           = (_eur_saving / _steel_cost_kpi5 * 100) if _steel_cost_kpi5 else None

# ── KPI cards (5) ─────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    if selected and sel_cost is not None:
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Estimated CBAM Bill<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Total estimated CBAM certificate cost for this country&#39;s exports of steel, aluminium, cement, fertilizers, and hydrogen to the EU. Represents the country&#39;s aggregate financial exposure under CBAM at the current certificate price. Calc: embedded CO&#8322; in EU-bound exports &times; certificate price, using EU Commission high-route default emission factors.</span></span></span></div>'
            f'<div class="kpi-value">€{sel_cost/1e6:.1f}M</div>'
            f'<div class="kpi-sub">{sel_co2/1e6:.2f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True)
    elif selected:
        # Country selected but no cost data available in the filtered dataset
        st.markdown(
            f'<div class="kpi-card-neutral">'
            f'<div class="kpi-label">Estimated CBAM Bill<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Total estimated CBAM certificate cost for this country&#39;s exports of steel, aluminium, cement, fertilizers, and hydrogen to the EU. Represents the country&#39;s aggregate financial exposure under CBAM at the current certificate price. Calc: embedded CO&#8322; in EU-bound exports &times; certificate price, using EU Commission high-route default emission factors.</span></span></span></div>'
            f'<div class="kpi-value">N/A</div>'
            f'<div class="kpi-sub">No data for selected sectors</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Est. CBAM Bill — Global<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Total estimated CBAM certificate cost for this country&#39;s exports of steel, aluminium, cement, fertilizers, and hydrogen to the EU. Represents the country&#39;s aggregate financial exposure under CBAM at the current certificate price. Calc: embedded CO&#8322; in EU-bound exports &times; certificate price, using EU Commission high-route default emission factors.</span></span></span></div>'
            f'<div class="kpi-value">€{total_cost_high/1e9:.2f}B</div>'
            f'<div class="kpi-sub">{total_co2/1e6:.1f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True)

with k2:
    # CBAM cost as % of the country's total global CBAM-sector exports.
    # Matches the map's '% of exports' metric exactly.
    # Sub-line shows Global and EU CBAM export values on one compact line.
    if selected:
        # Build export sub-line only when both values are available
        sub_parts = []
        if sel_eu_imp:
            sub_parts.append(f'To EU €{sel_eu_imp/1e9:.2f}B')
        if sel_global_exp and pd.notna(sel_global_exp):
            sub_parts.append(f'To World €{sel_global_exp/1e9:.2f}B')
        sub_str = ' · '.join(sub_parts)
        if sel_pct is None or pd.isna(sel_pct):
            # No Comtrade export data for this country
            st.markdown(
                f'<div class="kpi-card-neutral">'
                f'<div class="kpi-label">CBAM-Sector Exports to EU<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Share of this country&#39;s total global CBAM-sector exports (by value) that are destined for the EU, and therefore subject to CBAM fees. A higher percentage indicates greater structural exposure &mdash; a larger portion of the country&#39;s industrial export base faces the carbon border adjustment. Exports to non-EU markets are unaffected. Source: UN Comtrade 2024.</span></span></span></div>'
                f'<div class="kpi-value">N/A</div>'
                f'<div class="kpi-sub">No 2024 Comtrade export data available</div>'
                f'</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="kpi-card-country">'
                f'<div class="kpi-label">CBAM-Sector Exports to EU<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Share of this country&#39;s total global CBAM-sector exports (by value) that are destined for the EU, and therefore subject to CBAM fees. A higher percentage indicates greater structural exposure &mdash; a larger portion of the country&#39;s industrial export base faces the carbon border adjustment. Exports to non-EU markets are unaffected. Source: UN Comtrade 2024.</span></span></span></div>'
                f'<div class="kpi-value">{sel_pct:.1f}%</div>'
                f'<div class="kpi-sub">{sub_str}</div>'
                f'</div>', unsafe_allow_html=True)
    else:
        pct_str = f'{global_pct_exp:.1f}%' if global_pct_exp else 'N/A'
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">CBAM-Sector Exports to EU<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">Share of this country&#39;s total global CBAM-sector exports (by value) that are destined for the EU, and therefore subject to CBAM fees. A higher percentage indicates greater structural exposure &mdash; a larger portion of the country&#39;s industrial export base faces the carbon border adjustment. Exports to non-EU markets are unaffected. Source: UN Comtrade 2024.</span></span></span></div>'
            f'<div class="kpi-value">{pct_str}</div>'
            f'<div class="kpi-sub">Total Global: €{total_global_exp/1e9:.1f}B; To EU: €{total_eu_imports/1e9:.1f}B</div>'
            f'</div>', unsafe_allow_html=True)

with k3:
    if selected and sel_cost is not None:
        country_share = sel_cost / total_cost_high * 100
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Share of Global CBAM Bill<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">This country&#39;s estimated CBAM bill as a proportion of the total estimated bill across all 119 CBAM-affected countries. Indicates relative significance within the global CBAM landscape. Calc: country bill &divide; global total bill.</span></span></span></div>'
            f'<div class="kpi-value">{country_share:.1f}%</div>'
            f'<div class="kpi-sub">Ranked #{sel_rank} globally</div>'
            f'</div>', unsafe_allow_html=True)
    elif selected:
        # Country selected but no cost data available in the filtered dataset
        st.markdown(
            f'<div class="kpi-card-neutral">'
            f'<div class="kpi-label">Share of Global CBAM Bill<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">This country&#39;s estimated CBAM bill as a proportion of the total estimated bill across all 119 CBAM-affected countries. Indicates relative significance within the global CBAM landscape. Calc: country bill &divide; global total bill.</span></span></span></div>'
            f'<div class="kpi-value">N/A</div>'
            f'<div class="kpi-sub">No data for selected sectors</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Top 3 Share of CBAM Bill<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-right" style="width:260px;">This country&#39;s estimated CBAM bill as a proportion of the total estimated bill across all 119 CBAM-affected countries. Indicates relative significance within the global CBAM landscape. Calc: country bill &divide; global total bill.</span></span></span></div>'
            f'<div class="kpi-value">{top3_share:.0f}%</div>'
            f'<div class="kpi-sub">{top3_names}</div>'
            f'</div>', unsafe_allow_html=True)

with k4:
    if selected and sel_grid is not None and pd.notna(sel_grid):
        diff     = sel_grid - global_grid_avg
        diff_str = f'{"+" if diff > 0 else ""}{diff:.0f} vs global avg ({global_grid_avg:.0f})'
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Grid Intensity<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-left" style="width:260px;">CO&#8322; intensity of the national electricity grid, measured in grams of CO&#8322; per kilowatt-hour. Grid intensity determines the indirect emissions component of electricity-intensive processes &mdash; most critically EAF steel &mdash; and therefore directly affects the verified CBAM cost for those sectors. Source: Ember 2024.</span></span></span></div>'
            f'<div class="kpi-value">{sel_grid:.0f}<span style="font-size:0.68rem; font-weight:400; color:{TEXT_DARK}; margin-left:0.2em;">gCO₂/kWh</span></div>'
            f'<div class="kpi-sub">{diff_str}</div>'
            f'</div>', unsafe_allow_html=True)
    elif selected:
        # Country selected but no 2024 Ember grid data available
        st.markdown(
            f'<div class="kpi-card-neutral">'
            f'<div class="kpi-label">Grid Intensity<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-left" style="width:260px;">CO&#8322; intensity of the national electricity grid, measured in grams of CO&#8322; per kilowatt-hour. Grid intensity determines the indirect emissions component of electricity-intensive processes &mdash; most critically EAF steel &mdash; and therefore directly affects the verified CBAM cost for those sectors. Source: Ember 2024.</span></span></span></div>'
            f'<div class="kpi-value">N/A</div>'
            f'<div class="kpi-sub">No 2024 Ember data available</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Global Avg Grid Intensity<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-left" style="width:260px;">CO&#8322; intensity of the national electricity grid, measured in grams of CO&#8322; per kilowatt-hour. Grid intensity determines the indirect emissions component of electricity-intensive processes &mdash; most critically EAF steel &mdash; and therefore directly affects the verified CBAM cost for those sectors. Source: Ember 2024.</span></span></span></div>'
            f'<div class="kpi-value">{global_grid_avg:.0f}<span style="font-size:0.68rem; font-weight:400; color:{TEXT_DARK}; margin-left:0.2em;">gCO₂/kWh</span></div>'
            f'<div class="kpi-sub">Source: Ember 2024</div>'
            f'</div>', unsafe_allow_html=True)

with k5:
    # Euro bill saving if all steel switched from BOF default to EAF Verified
    # at current grid intensity. Value formatted as M or B depending on scale.
    _grid_ctx = f'{_kpi5_grid:.0f} gCO₂/kWh'
    if _kpi5_saving_eur is not None and _kpi5_pct is not None:
        _saving_fmt = (
            f'€{_kpi5_saving_eur/1e9:.2f}B'
            if _kpi5_saving_eur >= 1e9
            else f'€{_kpi5_saving_eur/1e6:.1f}M'
        )
        _card_class = 'kpi-card-country' if selected else 'kpi-card'
        st.markdown(
            f'<div class="{_card_class}">'
            f'<div class="kpi-label">Steel Bill Savings<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-left" style="width:260px;">Estimated reduction in steel CBAM costs if the country&#39;s entire iron and steel export volume switched from blast furnace (BOF) default reporting to verified electric arc furnace (EAF) production on a Norway-level clean grid. This represents the upper-bound savings scenario. Calc: steel export tonnes derived from current BOF default cost; repriced at EAF verified direct emissions (0.69 tCO&#8322;/t) plus indirect emissions at clean grid intensity (29.66 gCO&#8322;/kWh, Norway 2024, Ember).</span></span></span></div>'
            f'<div class="kpi-value" style="color:{ACCENT}">{_saving_fmt}</div>'
            f'<div class="kpi-sub">−{_kpi5_pct:.0f}% vs BOF default'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card-neutral">'
            f'<div class="kpi-label">Steel Bill Savings<span class="info-wrap" style="margin-left:0.35em; vertical-align:middle;"><span class="info-icon">ⓘ<span class="info-tooltip tip-left" style="width:260px;">Estimated reduction in steel CBAM costs if the country&#39;s entire iron and steel export volume switched from blast furnace (BOF) default reporting to verified electric arc furnace (EAF) production on a Norway-level clean grid. This represents the upper-bound savings scenario. Calc: steel export tonnes derived from current BOF default cost; repriced at EAF verified direct emissions (0.69 tCO&#8322;/t) plus indirect emissions at clean grid intensity (29.66 gCO&#8322;/kWh, Norway 2024, Ember).</span></span></span></div>'
            f'<div class="kpi-value">N/A</div>'
            f'<div class="kpi-sub">Insufficient steel default data</div>'
            f'</div>', unsafe_allow_html=True)

st.markdown('<div style="padding-bottom:1.5rem;"></div>', unsafe_allow_html=True)

# ── Map metric toggle ────────────────────────────────────────────────────
# map_metric must be defined before METRIC_CONFIG and before col_map opens.
# The toggle renders in a two-column row: title label left, toggle right.
# col_bar section label sits at the same vertical level since both share
# this pre-chart row.
MAP_TITLES = {
    'Abs. cost'    : 'Estimated CBAM bill by country',
    'Cost / tonne' : 'Estimated CBAM cost per imported tonne',
    '% of exports' : 'CBAM cost as % of CBAM-sector exports',
}

# map_metric is read from session_state so METRIC_CONFIG can use it before
# col_map opens. The toggle widget inside col_map updates session_state on
# each interaction, triggering a rerun with the correct value.
if 'map_metric' not in st.session_state:
    st.session_state['map_metric'] = 'Abs. cost'
map_metric = st.session_state['map_metric']
map_title  = MAP_TITLES.get(map_metric, '')

METRIC_CONFIG = {
    '% of exports' : ('cost_pct_export', 'CBAM cost as % of CBAM-sector exports', '%.1f%%'),
    'Abs. cost'    : ('cost_high',        'Est. CBAM cost (€)',                    '€%.0f'),
    'Cost / tonne' : ('cost_per_tonne',   'Est. CBAM cost per tonne (€)',          '€%.2f'),
}
metric_col, metric_label, metric_fmt = METRIC_CONFIG.get(
    map_metric, METRIC_CONFIG['Abs. cost']
)


# ── Row 1: Map + top 10 bar ───────────────────────────────────────────────────
col_map, col_bar = st.columns([4, 1.6], gap='small')

with col_map:
    # Toggle and title inside col_map — aligns naturally with bar chart title
    # in col_bar since both are the first element in their column.
    _hdr_title, _hdr_toggle = st.columns([1.5, 1])
    with _hdr_toggle:
        _new_metric = st.segmented_control(
            '_map_metric',
            options          = ['Abs. cost', 'Cost / tonne', '% of exports'],
            default          = st.session_state['map_metric'],
            label_visibility = 'collapsed',
        )
        if _new_metric and _new_metric != st.session_state['map_metric']:
            st.session_state['map_metric'] = _new_metric
            st.rerun()
    with _hdr_title:
        # Map title includes the info icon and a subtitle hint on the line below.
        _map_tooltip = (
            'Choropleth shading reflects the active metric (toggle top-right). '
            'Absolute cost: total estimated CBAM certificate spend at the selected price. '
            'Cost per tonne: CBAM cost divided by EU-imported tonnes. '
            '% of exports: CBAM cost as a share of the country\'s total global '
            'CBAM-sector export value — the primary exposure indicator. '
            'All costs use the high-route embedded CO\u2082 figure. '
            'Data: Eurostat COMEXT, UN Comtrade, EU Commission defaults.'
        )
        st.markdown(
            info_label(map_title, _map_tooltip, 'margin-bottom:0.05rem;', tip_side='tip-right')
            + f'<p style="font-size:0.62rem; color:{TEXT_LIGHT}; margin:0;">'
            f'Click to select · click again to deselect</p>',
            unsafe_allow_html=True)
    df_map = df_c[df_c[metric_col].notna() & (df_c[metric_col] > 0)].copy()

    # Pre-format cost_high as a readable string (B or M) for the hover tooltip.
    df_map = df_map.copy()
    df_map['cost_high_fmt'] = df_map['cost_high'].apply(
        lambda v: f'€{v/1e9:.1f}B' if v >= 1e9 else f'€{v/1e6:.1f}M'
    )

    fig_map = px.choropleth(
        df_map,
        locations              = 'iso3',
        color                  = metric_col,
        hover_name             = 'country',
        custom_data            = ['cost_high_fmt', 'cost_pct_export', 'cost_per_tonne'],
        hover_data             = {'iso3': False, metric_col: False},
        color_continuous_scale = [
            [0.0, MAP_MIN], [0.2, '#bdc4bc'], [0.4, '#a0b6a4'],
            [0.6, '#7a9e86'], [0.8, '#52815d'], [1.0, MAP_MAX],
        ],
        range_color = [
            df_map[metric_col].quantile(0.05),
            df_map[metric_col].quantile(0.95),
        ],
        labels        = {metric_col: metric_label, 'cost_high': 'CBAM Cost (€)'},
    )
    # hovertemplate must be set post-creation; px.choropleth doesn't accept it directly.
    fig_map.update_traces(
        hovertemplate=(
            '<b>%{hovertext}</b><br>'
            'CBAM Cost: %{customdata[0]}<br>'
            'Cost/Tonne: €%{customdata[2]:,.2f}<br>'
            '% of Exports: %{customdata[1]:.1f}%'
            '<extra></extra>'
        ),
        selector=dict(type='choropleth'),
    )

    if selected:
        sel_iso3 = df_countries.loc[df_countries['country'] == selected, 'iso3'].values
        if len(sel_iso3) > 0:
            # hoverinfo='skip' keeps the main trace tooltip working after click.
            # Without this, the invisible highlight trace intercepts hover events
            # and shows a blank tooltip over the selected country.
            fig_map.add_trace(go.Choropleth(
                locations         = [sel_iso3[0]], z=[1],
                colorscale        = [[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
                showscale         = False,
                marker_line_color = '#e83b2a',
                marker_line_width = 2.5,
                hoverinfo         = 'skip',
            ))

    fig_map.update_layout(
        geo = dict(
            showframe=False, showcoastlines=True, coastlinecolor=BORDER,
            showland=True, landcolor='#eae8e2',
            showocean=True, oceancolor=BG, bgcolor=BG,
            projection_type='natural earth',
            # Clip Antarctica (below -58°) and reduce excess polar whitespace
            lataxis =dict(range=[-58, 85]),
            lonaxis =dict(range=[-180, 180]),
        ),
        coloraxis_colorbar = dict(
            title=dict(
                text=metric_label,
                side='right',
                font=dict(size=8, color=TEXT_MID),
            ),
            thickness=10, len=0.7,
            orientation='v',
            x=1.01, xanchor='left',
            y=0.5,  yanchor='middle',
            tickfont=dict(size=8, color=TEXT_MID),
        ),
        margin=dict(l=0, r=55, t=10, b=10),
        paper_bgcolor=BG, plot_bgcolor=BG, height=460,
    )

    map_event = st.plotly_chart(
        fig_map, use_container_width=True,
        on_select='rerun', key='map_chart',
    )

    if (map_event and map_event.get('selection')
            and map_event['selection'].get('points')):
        points = map_event['selection']['points']
        if points:
            clicked_iso3 = points[0].get('location')
            if clicked_iso3:
                match = df_countries[df_countries['iso3'] == clicked_iso3]
                if not match.empty:
                    clicked_name = match.iloc[0]['country']
                    if clicked_name != st.session_state['selected_country']:
                        st.session_state['selected_country'] = clicked_name
                    else:
                        st.session_state['selected_country'] = None
                    st.rerun()

with col_bar:
    bar_label = {
        '% of exports' : 'CBAM cost as % of CBAM-sector exports',
        'Abs. cost'    : 'Estimated CBAM cost (€)',
        'Cost / tonne' : 'Est. CBAM cost per tonne (€)',
    }.get(map_metric, 'Estimated CBAM cost (€)')

    # Top 10 bar chart info tooltip — placeholder text to be refined later.
    _bar_tooltip = (
        f'The 10 countries with the highest {bar_label.lower()}. '
        'Metric matches the active map toggle. '
        'Highlighted bar (orange) indicates the currently selected country. '
        'Placeholder: full methodology note to be added.'
    )
    st.markdown(
        info_label(f'Top 10 — {bar_label.lower()}', _bar_tooltip, tip_side='tip-left'),
        unsafe_allow_html=True)

    df_top10 = (
        df_c[df_c[metric_col].notna() & (df_c[metric_col] > 0)]
        .nlargest(10, metric_col)
    )

    # Scale x values and format axis labels based on the active metric.
    # Absolute cost is in EUR — divide by 1e9 for readable B labels.
    # Other metrics are already in human-readable units.
    if map_metric == 'Abs. cost':
        bar_x      = [v / 1e9 for v in df_top10[metric_col].tolist()]
        bar_xfmt   = '.2f'
        bar_xsuffix = 'B'
        bar_hover  = '<b>%{y}</b><br>€%{x:.2f}B<extra></extra>'
        bar_tickfmt = '.2f'
        bar_ticksuffix = 'B'
    elif map_metric == 'Cost / tonne':
        bar_x      = df_top10[metric_col].tolist()
        bar_hover  = '<b>%{y}</b><br>€%{x:,.0f}/t<extra></extra>'
        bar_tickfmt = ',.0f'
        bar_ticksuffix = ''
    else:  # % of exports
        bar_x      = df_top10[metric_col].tolist()
        bar_hover  = '<b>%{y}</b><br>%{x:.1f}%<extra></extra>'
        bar_tickfmt = '.1f'
        bar_ticksuffix = '%'

    fig_bar = go.Figure(go.Bar(
        y             = df_top10['country'].tolist(),
        x             = bar_x,
        orientation   = 'h',
        marker_color  = [ACCENT_POP if c == selected else ACCENT
                         for c in df_top10['country']],
        hovertemplate = bar_hover,
    ))

    # top margin matches the nested column header height inside col_map
    # (section-label + subtitle hint) so both charts start at the same level.
    fig_bar.update_layout(
        yaxis         = dict(autorange='reversed',
                             tickfont=dict(size=10, family='DM Sans', color=TEXT_DARK),
                             gridcolor='rgba(0,0,0,0)', automargin=True),
        xaxis         = dict(
            title=None,
            tickfont=dict(size=9, color=TEXT_MID),
            gridcolor='rgba(0,0,0,0)',
            side='top',
            tickformat=bar_tickfmt,
            ticksuffix=bar_ticksuffix,
        ),
        showlegend    = False,
        paper_bgcolor = BG, plot_bgcolor=BG,
        margin        = dict(l=10, r=10, t=80, b=40),
        height        = 460,
    )
    # on_select='rerun' fires a selection event when a bar is clicked.
    # The selected country name is read from the y-tick of the clicked bar.
    bar_event = st.plotly_chart(
        fig_bar, use_container_width=True, key='bar_chart',
        on_select='rerun', selection_mode='points',
    )

    # Handle bar click: select on first click, deselect on second.
    if (bar_event and bar_event.get('selection')
            and bar_event['selection'].get('points')):
        pt = bar_event['selection']['points'][0]
        clicked_name = pt.get('y') or pt.get('label')
        if clicked_name:
            if clicked_name != st.session_state['selected_country']:
                st.session_state['selected_country'] = clicked_name
            else:
                st.session_state['selected_country'] = None
            st.rerun()



# ── Row 2 narrative strip ─────────────────────────────────────────────────────
# Frames the three charts as a connected argument before the reader sees them.
_strip_l = 'Country bill breakdown' if selected else 'Global bill breakdown'
_strip_r = 'Country grid: the final lever' if selected else 'Global grid: the final lever'
_strip_m = 'What verified reporting and process change saves (e.g. steel)'

st.markdown(
    f'<div style="'
    f'display:flex; align-items:center; gap:0; '
    f'margin:1.6rem 0 0.5rem 0; '
    f'font-size:0.72rem; color:{TEXT_MID}; letter-spacing:0.06em; text-transform:uppercase;'
    f'">'
    # Left label: fixed width = donut column (2/8 = 25%).
    # Middle label: fixed width = EAF column (3/8 = 37.5%), aligns under EAF title.
    # Right label: fills remainder, aligns under grid title (starts at 5/8 = 62.5%).
    # Column ratio [2,3,3] with gap='large'. Gaps eat into the percentage
    # widths so we use calc() to subtract approximate gap space (1rem per gap).
    f'<span style="width:calc(28% - 1rem); display:inline-flex; align-items:center; gap:0.5em; white-space:nowrap;">'
    f'{_strip_l} <span style="color:{TEXT_LIGHT};">&#8594;</span></span>'
    f'<span style="width:calc(41% - 1rem); display:inline-flex; align-items:center; gap:0.5em; white-space:nowrap;">'
    f'{_strip_m} <span style="color:{TEXT_LIGHT};">&#8594;</span></span>'
    f'<span style="flex:1; display:inline-flex; align-items:center; gap:0.5em; white-space:nowrap;">'
    f'{_strip_r} <span style="color:{TEXT_LIGHT};">&#8594;</span></span>'
    f'</div>'
    f'<hr style="border:none; border-top:1px solid {BORDER}; margin:0 0 1rem 0;">',
    unsafe_allow_html=True,
)

# ── Row 2: Sector donut [1] | EAF chart [2] | Grid chart [2] ─────────────────
col_donut, col_eaf, col_grid = st.columns([2, 3, 3], gap='large')


# ── Sector donut ──────────────────────────────────────────────────────────────
with col_donut:
    donut_label = 'Cost by sector' if selected else 'Global cost by sector'
    # Sector donut info tooltip — placeholder text to be refined later.
    _donut_tooltip = (
        'Estimated CBAM cost broken down by sector, at the selected certificate price. '
        'Uses the high-route embedded CO\u2082 figure for each sector. '
        'Sector filter (top bar) controls which sectors appear here. '
        'Placeholder: full methodology note to be added.'
    )
    st.markdown(info_label(donut_label, _donut_tooltip, tip_side='tip-right'), unsafe_allow_html=True)

    # The sector pivot columns in df_sector_pivots are stored at BASE_PRICE.
    # Rescale to the current certificate price before rendering.
    price_ratio = cert_price / BASE_PRICE

    if selected:
        # Country-specific sector breakdown from the pivot columns
        pivot_row = df_sector_pivots[df_sector_pivots['country'] == selected]
        if not pivot_row.empty:
            r = pivot_row.iloc[0]
            df_ds = pd.DataFrame([
                {'sector': 'Iron and Steel', 'cost_high': r['cost_iron_and_steel_high_route_eur'] * price_ratio},
                {'sector': 'Aluminium',      'cost_high': r['cost_aluminium_high_route_eur']      * price_ratio},
                {'sector': 'Cement',         'cost_high': r['cost_cement_high_route_eur']         * price_ratio},
                {'sector': 'Fertilizers',    'cost_high': r['cost_fertilizers_high_route_eur']    * price_ratio},
                {'sector': 'Hydrogen',       'cost_high': r['cost_hydrogen_high_route_eur']       * price_ratio},
            ])
            # Filter to selected sectors only
            df_ds = df_ds[df_ds['sector'].isin(selected_sectors)]
        else:
            df_ds = pd.DataFrame(columns=['sector', 'cost_high'])
    else:
        # Global view: aggregate cost_high from the already-computed df_g
        df_ds = (
            df_g.groupby('sector', as_index=False)['cost_high'].sum()
            .sort_values('cost_high', ascending=False)
        )

    df_ds = df_ds[df_ds['cost_high'] > 0].sort_values('cost_high', ascending=False)

    # Compute total for threshold check; suppress text on slices under 2%
    # to avoid callout clipping on tiny segments like Hydrogen.
    _donut_total = df_ds['cost_high'].sum()
    _donut_pcts  = (df_ds['cost_high'] / _donut_total * 100).tolist() if _donut_total else []
    _donut_text  = [f'{p:.1f}%' if p >= 2 else '' for p in _donut_pcts]

    fig_donut = go.Figure(go.Pie(
        labels        = df_ds['sector'],
        values        = df_ds['cost_high'],
        hole          = 0.55,
        marker_colors = [SECTOR_COLORS.get(s, '#d3d1c9') for s in df_ds['sector']],
        text          = _donut_text,
        textinfo      = 'text',
        textfont      = dict(size=10),
        hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent:.1%}<extra></extra>',
    ))
    fig_donut.update_layout(
        showlegend    = True,
        legend        = dict(
            font=dict(size=9, color=TEXT_MID),
            orientation='h',
            x=0.5, xanchor='center',
            y=-0.12, yanchor='top',
        ),
        margin        = dict(l=0, r=0, t=10, b=65),
        paper_bgcolor = BG,
        height        = 240,
    )
    st.plotly_chart(fig_donut, use_container_width=True, key='donut_chart')


# ── EAF scenario chart ────────────────────────────────────────────────────────
with col_eaf:
    context_label = selected if selected else 'global avg'
    # EAF chart info tooltip — uses the existing method-note text as its source.
    _eaf_tooltip = (
        'Default bars use EU CBAM default values x certificate price. '
        'Verified EAF bars use Worldsteel Scrap-EAF direct emissions (0.69 tCO\u2082/t) '
        '+ indirect (450 kWh/t x grid intensity). '
        'No markup on verified submissions. '
        'Clean grid benchmark: Norway 29.66 gCO\u2082/kWh (Ember 2024). '
        'Switch steel grade via the dropdown to compare Carbon vs Low Alloy routes.'
    )
    # Title and dropdown share one row: title left, dropdown right.
    # Using a wide title col and narrow dropdown col keeps the dropdown
    # compact and flush with the chart title on the same baseline.
    _eaf_title_col, _eaf_dd_col = st.columns([5, 2], gap='small')
    with _eaf_title_col:
        st.markdown(
            info_label(
                'Steel CBAM cost per tonne',
                _eaf_tooltip,
                tip_side='tip-right',
            ),
            unsafe_allow_html=True)
    with _eaf_dd_col:
        eaf_route_label = st.selectbox(
            'Steel grade',
            options = list(ROUTE_OPTIONS.keys()),
            index   = 0,
            label_visibility='collapsed',
        )
    eaf_code, bof_code = ROUTE_OPTIONS[eaf_route_label]

    # get_default() is defined at module level above.

    bof_default = get_default(bof_code, selected)
    eaf_default = get_default(eaf_code, selected)

    # Grid intensity is required for the two verified EAF scenario bars.
    # If no 2024 Ember intensity data exists for the selected country,
    # replace the entire chart with an explanatory message card.
    # Falling back to global average would be misleading.
    grid_data_missing = selected and (sel_grid is None or pd.isna(sel_grid))

    if grid_data_missing:
        st.markdown(
            f'<div style="background:{BG_CARD}; border:1px solid {BORDER}; '
            f'border-radius:8px; padding:1.5rem; height:260px; '
            f'display:flex; flex-direction:column; justify-content:center; '
            f'align-items:center; text-align:center;">'
            f'<div style="font-size:0.65rem; font-weight:600; letter-spacing:0.09em; '
            f'text-transform:uppercase; color:{TEXT_LIGHT}; margin-bottom:0.5rem;">'
            f'EAF Scenario Chart</div>'
            f'<div style="font-size:1rem; color:{TEXT_DARK}; margin-bottom:0.4rem;">'
            f'No 2024 grid intensity data</div>'
            f'<div style="font-size:0.7rem; color:{TEXT_LIGHT}; line-height:1.5;">'
            f'Ember does not have a 2024 CO₂ intensity figure for {selected}.<br>'
            f'The verified EAF scenario requires grid intensity to compute<br>'
            f'indirect emissions. Chart unavailable for this country.'
            f'</div></div>',
            unsafe_allow_html=True)
    else:
        if selected and sel_grid is not None and pd.notna(sel_grid):
            current_grid  = sel_grid
            current_label = f'{selected}'
        else:
            current_grid  = global_grid_avg
            current_label = 'Global avg'

        def indirect_eur_per_t(grid_intensity):
            return EAF_ELECTRICITY_KWH_PER_T * grid_intensity * 1e-6 * cert_price

        v_bof_default = bof_default * cert_price if bof_default is not None else None
        v_eaf_default = eaf_default * cert_price if eaf_default is not None else None
        v_eaf_current = EAF_DIRECT_EMISSIONS * cert_price + indirect_eur_per_t(current_grid)
        v_eaf_clean   = EAF_DIRECT_EMISSIONS * cert_price + indirect_eur_per_t(CLEAN_GRID_INTENSITY)

        scenario_defs = [
            ('BOF Default',   v_bof_default, BORDER),
            ('EAF Default',   v_eaf_default, TEXT_MID),
            ('EAF Verified',  v_eaf_current, ACCENT),
            ('EAF Cleanest',  v_eaf_clean,   ACCENT_MID),
        ]
        # Grid context for the two verified bars: shown as right-side
        # annotations. Labels are distinct so y-string matching is reliable.
        _eaf_grid_notes = {
            'EAF Verified' : f'{current_label} ({current_grid:.0f} gCO₂/kWh)',
            'EAF Cleanest' : f'{CLEAN_GRID_COUNTRY} ({CLEAN_GRID_INTENSITY:.0f} gCO₂/kWh)',
        }
        scenarios  = [s for s, v, _ in scenario_defs if v is not None]
        values     = [v for _, v, _ in scenario_defs if v is not None]
        bar_colors = [c for _, v, c in scenario_defs if v is not None]

        missing_defaults = [s for s, v, _ in scenario_defs[:2] if v is None]
        if missing_defaults:
            route_name = eaf_route_label.split('(')[0].strip()
            st.caption(
                f'No CBAM default available for {route_name} '
                f'{"for " + selected if selected else "globally"}. '
                f'Default bars omitted.'
            )

        # Build bar text: value for all bars, grid context appended for verified bars.
        _bar_labels = []
        for s, v in zip(scenarios[::-1], values[::-1]):
            label = f'€{v:.1f}'
            if s == 'EAF Verified':
                label += f'  {_eaf_grid_notes["EAF Verified"]}'
            elif s == 'EAF Cleanest':
                label += f'  {_eaf_grid_notes["EAF Cleanest"]}'
            _bar_labels.append(label)

        fig_eaf = go.Figure()
        fig_eaf.add_trace(go.Bar(
            y                 = scenarios[::-1],
            x                 = values[::-1],
            orientation       = 'h',
            marker_color      = bar_colors[::-1],
            marker_line_width = 0,
            text              = _bar_labels,
            textposition      = 'outside',
            cliponaxis        = False,
            textfont          = dict(size=8, color=TEXT_MID),
            hovertemplate     = '<b>%{y}</b><br>€%{x:.2f} per tonne of steel<extra></extra>',
        ))

        # Ceiling rounds to nearest 25, plus one extra step for outside label room.
        import math
        _raw_max  = max((v for v in values if v is not None), default=0)
        eaf_x_max = math.ceil(_raw_max / 25) * 25 + 25


        fig_eaf.update_layout(
            xaxis = dict(visible=False,
                         autorange=False,
                         range=[0, eaf_x_max]),
            yaxis         = dict(tickfont=dict(size=9, color=TEXT_MID),
                                 gridcolor='rgba(0,0,0,0)',
                                 automargin=True),
            paper_bgcolor = BG, plot_bgcolor=BG,
            margin        = dict(l=10, r=10, t=0, b=50),
            height        = 240,
            showlegend    = False,
        )

        st.plotly_chart(fig_eaf, use_container_width=True, key='eaf_chart')


# ── Grid generation mix chart ────────────────────────────────────────────────
# Shows each fuel type as a share of total electricity generation (%).
# Two shaded background regions group fossil and clean fuels visually, so the
# fossil vs clean balance reads immediately without needing a separate legend.
# Group total percentages are annotated above each shaded region.
with col_grid:
    grid_label = 'Grid generation mix' if selected else 'Global grid generation mix'
    # Grid chart info tooltip — placeholder text to be refined later.
    _grid_tooltip = (
        'Share of total electricity generation by fuel type, from Ember 2024 data. '
        'Fossil group: Coal, Gas, Other Fossil. '
        'Clean group: Hydro, Wind, Solar, Nuclear, Other Renewables. '
        'Grid intensity (gCO\u2082/kWh) feeds directly into the EAF verified scenario bars. '
        'Placeholder: full methodology note to be added.'
    )
    st.markdown(info_label(grid_label, _grid_tooltip, tip_side='tip-left'), unsafe_allow_html=True)

    # Aggregate generation by fuel type for the selected country or globally.
    # If the selected country has no 2024 Ember generation data, show a
    # message rather than an empty or misleading chart.
    if selected:
        df_gen = df_grid_generation[df_grid_generation['country'] == selected].copy()
    else:
        df_gen = df_grid_generation.groupby('fuel_type', as_index=False)['value'].sum()

    grid_gen_available = not df_gen.empty
    if not grid_gen_available:
        st.markdown(
            f'<div style="background:{BG_CARD}; border:1px solid {BORDER}; '
            f'border-radius:8px; padding:1.5rem; height:320px; '
            f'display:flex; flex-direction:column; justify-content:center; '
            f'align-items:center; text-align:center;">'
            f'<div style="font-size:0.65rem; font-weight:600; letter-spacing:0.09em; '
            f'text-transform:uppercase; color:{TEXT_LIGHT}; margin-bottom:0.5rem;">'
            f'Grid Generation Mix</div>'
            f'<div style="font-size:1rem; color:{TEXT_DARK}; margin-bottom:0.4rem;">'
            f'No 2024 generation data</div>'
            f'<div style="font-size:0.7rem; color:{TEXT_LIGHT}; line-height:1.5;">'
            f'Ember does not have 2024 generation figures'
            f'{", for " + selected if selected else ""}.'
            f'</div></div>',
            unsafe_allow_html=True)

    gen_lookup = df_gen.set_index('fuel_type')['value'].to_dict()
    total_gen  = sum(gen_lookup.get(f, 0) for f in FOSSIL_FUELS + CLEAN_FUELS)

    # Keep only fuels with non-zero generation, preserving fossil-first order
    # All fuel types shown regardless of zero generation — keeps x-axis stable.
    fuels    = FOSSIL_FUELS + CLEAN_FUELS
    pct_vals = [gen_lookup.get(f, 0) / total_gen * 100 if total_gen else 0 for f in fuels]
    x_pos    = list(range(len(fuels)))

    fossil_pct = (
        sum(gen_lookup.get(f, 0) for f in FOSSIL_FUELS) / total_gen * 100
        if total_gen else 0
    )
    clean_pct = 100 - fossil_pct

    # Group shading uses scatter fill traces rather than layout shapes.
    # Streamlit's iframe pipeline strips SVG shapes before render; scatter
    # traces go through the normal Plotly compositing path and always show.
    # Each group is a filled rectangle drawn as a closed 4-point polygon.
    fossil_idx = list(range(len(FOSSIL_FUELS)))
    clean_idx  = list(range(len(FOSSIL_FUELS), len(FOSSIL_FUELS) + len(CLEAN_FUELS)))

    annotations = []
    _group_bands = [
        (fossil_idx, '#4a4a4a', 'Fossil', fossil_pct),
        (clean_idx,  '#3a6b45', 'Clean',  clean_pct),
    ]

    fig_grid = go.Figure()

    # Group labels (Fossil xx% / Clean xx%) as annotations above the chart,
    # and a thin vertical divider line between the two groups as the only
    # visual separator. Shading approaches all fail in Streamlit's pipeline.
    divider_x = len(FOSSIL_FUELS) - 0.5

    for indices, color, label, grp_pct in _group_bands:
        x0 = indices[0] - 0.45
        x1 = indices[-1] + 0.45
        annotations.append(dict(
            x=(x0 + x1) / 2, y=1.06,
            xref='x', yref='paper',
            text=f'<b>{label}</b> {grp_pct:.0f}%',
            showarrow=False,
            font=dict(size=10, color=color),
            xanchor='center',
        ))

    # Divider: a scatter trace drawing a single dashed vertical line between
    # the last fossil fuel and first clean fuel bar. Scatter traces render
    # reliably where shapes do not in Streamlit's SVG pipeline.
    fig_grid.add_trace(go.Scatter(
        x          = [divider_x, divider_x],
        y          = [0, 108],
        mode       = 'lines',
        line       = dict(color=BORDER, width=1.5, dash='dot'),
        hoverinfo  = 'skip',
        showlegend = False,
        cliponaxis = False,
    ))

    # Bar trace added after divider so bars render on top.
    fig_grid.add_trace(go.Bar(
        x                 = x_pos,
        y                 = pct_vals,
        marker_color      = [FUEL_COLORS.get(f, '#999') for f in fuels],
        marker_line_width = 0,
        text              = [f'{v:.1f}%' if v > 0 else '' for v in pct_vals],
        textposition      = 'outside',
        textfont          = dict(size=8, color=TEXT_MID),
        cliponaxis        = False,
        customdata        = fuels,
        hovertemplate     = '<b>%{customdata}</b><br>%{y:.1f}% of generation<extra></extra>',
    ))

    fig_grid.update_layout(
        annotations = annotations,
        xaxis       = dict(
            tickvals  = x_pos,
            # Wrap multi-word fuel names with <br> so labels stack vertically
            # instead of rotating diagonally. Single-word names are unchanged.
            ticktext  = [f.replace(' ', '<br>') for f in fuels],
            tickfont  = dict(size=8, color=TEXT_MID),
            tickangle = 0,
            gridcolor = 'rgba(0,0,0,0)',
        ),
        yaxis       = dict(
            title      = '% of total generation',
            title_font = dict(size=9, color=TEXT_MID),
            tickfont   = dict(size=8, color=TEXT_MID),
            gridcolor  = 'rgba(0,0,0,0)',
            # Dynamic range: 15% headroom above tallest bar for value labels.
            range      = [0, max(pct_vals) * 1.15 if pct_vals else 100],
        ),
        paper_bgcolor = BG,
        # plot_bgcolor must be transparent so the layout shapes (group shading)
        # are visible. An opaque bgcolor paints over layer='below' shapes.
        plot_bgcolor  = 'rgba(0,0,0,0)',
        margin        = dict(l=40, r=30, t=30, b=65),
        height        = 260,
        showlegend    = False,
        bargap        = 0.2,
    )

    if grid_gen_available:
        st.plotly_chart(fig_grid, use_container_width=True, key='grid_chart')



# ── Calls to action ─────────────────────────────────────────────────────────
# Three numbered insights that turn the dashboard data into actionable steps.
# Watermark-style numbers sit to the left of each item as visual anchors.
_ctas = [
    ('1', 'Get verified.',
     'Default emissions assumptions cost 2-4x more than actual verified figures. '
     'The difference is yours to keep.'),
    ('2', 'Switch to cleaner production routes where possible.',
     "Scrap-based electric arc furnace cuts steel's CBAM bill by ~50% vs BOF default."),
    ('3', 'Push for clean energy.',
     'Grid intensity is the last multiplier. '
     'Norway-level clean power cuts the EAF bill by a further ~20%.'),
]

_cta_cols = ''.join(
    f'<div style="display:flex; align-items:flex-start; gap:0.8em;">'
    f'<span style="font-size:2.2rem; font-weight:700; color:{TEXT_MID}; '
    f'line-height:1; flex-shrink:0;">{n}</span>'
    f'<p style="margin:0; font-size:1.1rem; color:{TEXT_MID}; line-height:1.6;">'
    f'<strong style="color:#e83b2a;">{lead}</strong> {body}</p>'
    f'</div>'
    for n, lead, body in _ctas
)

st.markdown(
    f'<hr style="border:none; border-top:1px solid {BORDER}; margin:-1.5rem 0 1rem 0;">'
    f'<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem;">'
    + _cta_cols +
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div style="display:flex; justify-content:space-between; align-items:baseline; '
    f'padding:2rem 0 0.6rem 0; border-top:1px solid {BORDER}; margin-top:0.5rem; '
    f'font-size:0.65rem; color:{TEXT_LIGHT};">'
    # Left: attribution with hyperlinks
    f'<span>'
    f'<a href="https://milcahjoseph.com" target="_blank" '
    f'style="color:{TEXT_MID}; text-decoration:none;">Analysis &amp; Design: Milcah M. Joseph</a>'
    f' &nbsp;·&nbsp; '
    f'<a href="https://github.com/M1ck3yJ0/cbam-analysis" target="_blank" '
    f'style="color:{TEXT_MID}; text-decoration:none;">Data Pipeline: GitHub</a>'
    f'</span>'
    # Right: sources
    f'<span style="text-align:right;">'
    f'Sources: EU Commission · Eurostat COMEXT · Worldsteel · UN Comtrade · Ember · '
    f'Certificate price: €{cert_price}/tCO₂'
    f'</span>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown('<div style="padding-bottom:1.5rem;"></div>', unsafe_allow_html=True)
