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
ACCENT_POP = '#c1653a'
MAP_MIN    = '#d3d1c9'
MAP_MAX    = '#3a6b45'

SECTOR_COLORS = {
    'Iron and Steel' : '#5c6b5e',
    'Aluminium'      : '#74b583',
    'Cement'         : '#c1653a',
    'Fertilizers'    : '#3a6b45',
    'Hydrogen'       : '#a8b5aa',
    'Electricity'    : '#d3d1c9',
}

FOSSIL_FUELS = ['Coal', 'Gas', 'Other Fossil']
CLEAN_FUELS  = ['Hydro', 'Wind', 'Solar', 'Nuclear', 'Other Renewables']
FUEL_COLORS  = {
    'Coal'            : '#4a4a4a',
    'Gas'             : '#9e9e9e',
    'Other Fossil'    : '#bdbdbd',
    'Hydro'           : '#457b9d',
    'Wind'            : '#74b583',
    'Solar'           : '#e9c46a',
    'Nuclear'         : '#a8b5aa',
    'Other Renewables': '#2a9d8f',
}

# EAF scenario constants
EAF_ELECTRICITY_KWH_PER_T = 450     # kWh/t crude steel, scrap-EAF (IEA / Transition Asia)
CLEAN_GRID_INTENSITY       = 29.66  # gCO2/kWh, Norway 2024 (Ember)
CLEAN_GRID_COUNTRY         = 'Norway'
EAF_DIRECT_EMISSIONS       = 0.69   # tCO2/t, Worldsteel Scrap-EAF 2024
BOF_DIRECT_EMISSIONS       = 2.34   # tCO2/t, Worldsteel BF-BOF 2024

# Route dropdown options: label -> (eaf_code, bof_code)
ROUTE_OPTIONS = {
    'Carbon Steel (Scrap-EAF vs BF-BOF)'   : ('E', 'C'),
    'Low Alloy Steel (Scrap-EAF vs BF-BOF)': ('H', 'F'),
}

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
    min-height: 100px;
}}
.kpi-card-country {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    border-left: 4px solid {ACCENT_POP};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
    min-height: 100px;
}}
.kpi-card-neutral {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    border-left: 4px solid {BORDER};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
    min-height: 100px;
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
    font-size: 1.4rem;
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
</style>
""", unsafe_allow_html=True)


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
            has_any_route_variation
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
    return pd.read_sql("""
        SELECT country, year, co2_intensity_gco2_kwh
        FROM grid_co2_intensity
        WHERE year = (SELECT MAX(year) FROM grid_co2_intensity)
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
    return pd.read_sql("""
        SELECT country, year, fuel_type, subcategory, value, unit
        FROM grid_generation
        WHERE year = (SELECT MAX(year) FROM grid_generation)
          AND subcategory = 'Fuel'
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

global_grid_avg = df_grid_intensity['co2_intensity_gco2_kwh'].mean()


# ── Session state ─────────────────────────────────────────────────────────────
if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = None


# ── Sticky filter bar ─────────────────────────────────────────────────────────
st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

fc1, _gap, fc2, fc3 = st.columns([1.5, 0.4, 4, 1.5])

with fc1:
    st.markdown('<p class="filter-label">Certificate Price (€/tCO₂)</p>',
                unsafe_allow_html=True)
    cert_price = st.slider(
        '_cert', min_value=25.0, max_value=150.0,
        value=BASE_PRICE, step=0.5, format='€%.2f',
        label_visibility='collapsed',
        help=f'Default: €{BASE_PRICE} — first official EC CBAM price, April 2026',
    )

with fc2:
    st.markdown('<p class="filter-label">Sectors</p>', unsafe_allow_html=True)
    selected_sectors = st.pills(
        '_sectors', options=ALL_SECTORS, default=ALL_SECTORS,
        selection_mode='multi', label_visibility='collapsed',
    )
    if not selected_sectors:
        selected_sectors = ALL_SECTORS

with fc3:
    st.markdown('<p class="filter-label">Country</p>', unsafe_allow_html=True)
    country_options = ['All countries'] + sorted(df_countries['country'].tolist())
    current_idx     = 0
    if st.session_state['selected_country'] in country_options:
        current_idx = country_options.index(st.session_state['selected_country'])
    sidebar_country = st.selectbox(
        '_country', options=country_options,
        index=current_idx, label_visibility='collapsed',
    )
    st.session_state['selected_country'] = (
        None if sidebar_country == 'All countries' else sidebar_country
    )

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

# Join iso3, global export value, and exposure ratio from the country table
df_c = df_c.merge(
    df_countries[[
        'country', 'iso3',
        'global_cbam_export_value_eur',
        'exposure_ratio_high', 'exposure_ratio_low',
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

sel_cost = sel_co2 = sel_pct = sel_eu_imp = sel_global_exp = sel_grid = sel_rank = None
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


# ── KPI cards (5) ─────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    if selected and sel_cost is not None:
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Est. CBAM Bill — {selected}</div>'
            f'<div class="kpi-value">€{sel_cost/1e6:.1f}M</div>'
            f'<div class="kpi-sub">{sel_co2/1e6:.2f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Total Est. CBAM Bill</div>'
            f'<div class="kpi-value">€{total_cost_high/1e9:.2f}B</div>'
            f'<div class="kpi-sub">{total_co2/1e6:.1f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True)

with k2:
    # Cost as % of total global CBAM-sector exports (not EU import value only).
    # The denominator is the country's worldwide exports in CBAM-covered goods.
    if selected and sel_pct is not None and pd.notna(sel_pct):
        eu_str  = f'EU imports: €{sel_eu_imp/1e9:.2f}B' if sel_eu_imp else ''
        exp_str = (f'Global CBAM exports: €{sel_global_exp/1e9:.2f}B'
                   if sel_global_exp and pd.notna(sel_global_exp) else '')
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">CBAM Cost as % of Global CBAM Exports — {selected}</div>'
            f'<div class="kpi-value">{sel_pct:.1f}%</div>'
            f'<div class="kpi-sub">{eu_str}<br>{exp_str}</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        pct_str = f'{global_pct_exp:.1f}%' if global_pct_exp else 'N/A'
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">CBAM-Sector EU Imports as % of Global Exports</div>'
            f'<div class="kpi-value">{pct_str}</div>'
            f'<div class="kpi-sub">Global CBAM exports: €{total_global_exp/1e9:.1f}B'
            f' · EU imports: €{total_eu_imports/1e9:.1f}B</div>'
            f'</div>', unsafe_allow_html=True)

with k3:
    if selected and sel_cost is not None:
        country_share = sel_cost / total_cost_high * 100
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Share of Global CBAM Bill — {selected}</div>'
            f'<div class="kpi-value">{country_share:.1f}%</div>'
            f'<div class="kpi-sub">Ranked #{sel_rank} globally</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Top 3 Countries — Share of Global Bill</div>'
            f'<div class="kpi-value">{top3_share:.0f}%</div>'
            f'<div class="kpi-sub">{top3_names}</div>'
            f'</div>', unsafe_allow_html=True)

with k4:
    if selected and sel_grid is not None and pd.notna(sel_grid):
        diff     = sel_grid - global_grid_avg
        diff_str = f'{"+" if diff > 0 else ""}{diff:.0f} vs global avg ({global_grid_avg:.0f})'
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Grid Intensity — {selected}</div>'
            f'<div class="kpi-value">{sel_grid:.0f} gCO₂/kWh</div>'
            f'<div class="kpi-sub">{diff_str}</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Global Avg Grid Intensity</div>'
            f'<div class="kpi-value">{global_grid_avg:.0f} gCO₂/kWh</div>'
            f'<div class="kpi-sub">Source: Ember latest year</div>'
            f'</div>', unsafe_allow_html=True)

with k5:
    st.markdown(
        f'<div class="kpi-card-neutral">'
        f'<div class="kpi-label">EAF + Clean Grid Potential</div>'
        f'<div class="kpi-value">—</div>'
        f'<div class="kpi-sub">Estimated CO₂ reduction vs current.<br>Coming soon.</div>'
        f'</div>', unsafe_allow_html=True)

st.markdown('<br>', unsafe_allow_html=True)


# ── Map metric toggle + clear button ──────────────────────────────────────────
map_label_col, toggle_col, clear_col = st.columns([3, 2, 2])

with map_label_col:
    st.markdown('<p class="section-label">Click a country to filter</p>',
                unsafe_allow_html=True)

with toggle_col:
    map_metric = st.segmented_control(
        '_map_metric',
        options          = ['% of exports', 'Abs. cost', 'Cost / tonne'],
        default          = '% of exports',
        label_visibility = 'collapsed',
    )

with clear_col:
    if selected:
        if st.button(f'✕\u2002Clear filter:\u2002{selected}',
                     key='clear_map', type='tertiary'):
            st.session_state['selected_country'] = None
            st.rerun()
    else:
        st.empty()

METRIC_CONFIG = {
    '% of exports' : ('cost_pct_export', 'CBAM cost as % of global CBAM exports', '%.1f%%'),
    'Abs. cost'    : ('cost_high',        'Est. CBAM cost (€)',                    '€%.0f'),
    'Cost / tonne' : ('cost_per_tonne',   'Est. CBAM cost per tonne (€)',          '€%.2f'),
}
metric_col, metric_label, metric_fmt = METRIC_CONFIG.get(
    map_metric, METRIC_CONFIG['% of exports']
)


# ── Row 1: Map + top 10 bar ───────────────────────────────────────────────────
col_map, col_bar = st.columns([3, 2], gap='large')

with col_map:
    df_map = df_c[df_c[metric_col].notna() & (df_c[metric_col] > 0)].copy()

    fig_map = px.choropleth(
        df_map,
        locations              = 'iso3',
        color                  = metric_col,
        hover_name             = 'country',
        hover_data             = {'iso3': False, metric_col: True, 'cost_high': ':,.0f'},
        color_continuous_scale = [
            [0.0, MAP_MIN], [0.2, '#bdc4bc'], [0.4, '#a0b6a4'],
            [0.6, '#7a9e86'], [0.8, '#52815d'], [1.0, MAP_MAX],
        ],
        range_color = [
            df_map[metric_col].quantile(0.05),
            df_map[metric_col].quantile(0.95),
        ],
        labels = {metric_col: metric_label, 'cost_high': 'CBAM Cost (€)'},
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
                marker_line_color = ACCENT_POP,
                marker_line_width = 2.5,
                hoverinfo         = 'skip',
            ))

    fig_map.update_layout(
        geo = dict(
            showframe=False, showcoastlines=True, coastlinecolor=BORDER,
            showland=True, landcolor='#eae8e2',
            showocean=True, oceancolor=BG, bgcolor=BG,
            projection_type='natural earth',
        ),
        coloraxis_colorbar = dict(
            title=metric_label, thickness=10, len=0.5,
            x=1.0, xanchor='left',
            tickfont=dict(size=9, color=TEXT_MID),
            title_font=dict(size=9, color=TEXT_MID),
        ),
        margin=dict(l=0, r=60, t=0, b=0),
        paper_bgcolor=BG, plot_bgcolor=BG, height=380,
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
                        st.rerun()

with col_bar:
    bar_label = {
        '% of exports' : 'CBAM cost as % of global CBAM exports',
        'Abs. cost'    : 'Estimated CBAM cost (€)',
        'Cost / tonne' : 'Est. CBAM cost per tonne (€)',
    }.get(map_metric, 'Estimated CBAM cost (€)')

    st.markdown(
        f'<p class="section-label">Top 10 countries — {bar_label.lower()}</p>',
        unsafe_allow_html=True)

    df_top10 = (
        df_c[df_c[metric_col].notna() & (df_c[metric_col] > 0)]
        .nlargest(10, metric_col)
    )

    fig_bar = go.Figure(go.Bar(
        y             = df_top10['country'].tolist(),
        x             = df_top10[metric_col].tolist(),
        orientation   = 'h',
        marker_color  = [ACCENT_POP if c == selected else ACCENT
                         for c in df_top10['country']],
        hovertemplate = '<b>%{y}</b><br>' + bar_label + ': %{x:,.2f}<extra></extra>',
    ))

    fig_bar.update_layout(
        yaxis         = dict(autorange='reversed',
                             tickfont=dict(size=10, family='DM Sans', color=TEXT_DARK),
                             gridcolor=BORDER, automargin=True),
        xaxis         = dict(title=bar_label,
                             tickfont=dict(size=9, color=TEXT_MID),
                             gridcolor=BORDER, tickformat='.2s',
                             title_font=dict(size=10, color=TEXT_MID)),
        showlegend    = False,
        paper_bgcolor = BG, plot_bgcolor=BG,
        margin        = dict(l=10, r=10, t=10, b=50),
        height        = 380,
    )
    st.plotly_chart(fig_bar, use_container_width=True, key='bar_chart')


st.markdown('<br>', unsafe_allow_html=True)


# ── Row 2: Sector donut [1] | EAF chart [2] | Grid chart [2] ─────────────────
col_donut, col_eaf, col_grid = st.columns([1, 2, 2], gap='large')


# ── Sector donut ──────────────────────────────────────────────────────────────
with col_donut:
    donut_label = f'Cost by sector — {selected}' if selected else 'Global cost by sector'
    st.markdown(f'<p class="section-label">{donut_label}</p>',
                unsafe_allow_html=True)

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

    fig_donut = go.Figure(go.Pie(
        labels        = df_ds['sector'],
        values        = df_ds['cost_high'],
        hole          = 0.55,
        marker_colors = [SECTOR_COLORS.get(s, '#d3d1c9') for s in df_ds['sector']],
        textinfo      = 'percent',
        textfont      = dict(size=10),
        hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
    ))
    fig_donut.update_layout(
        showlegend    = True,
        legend        = dict(font=dict(size=9, color=TEXT_MID),
                             orientation='v', x=1.0),
        margin        = dict(l=0, r=90, t=10, b=0),
        paper_bgcolor = BG,
        height        = 320,
    )
    st.plotly_chart(fig_donut, use_container_width=True, key='donut_chart')


# ── EAF scenario chart ────────────────────────────────────────────────────────
with col_eaf:
    context_label = selected if selected else 'global avg'
    st.markdown(
        f'<p class="section-label">Steel CBAM cost per tonne — '
        f'default vs verified · {context_label}</p>',
        unsafe_allow_html=True)

    # Route dropdown — above the chart, full width of this column
    eaf_route_label = st.selectbox(
        'Steel grade',
        options = list(ROUTE_OPTIONS.keys()),
        index   = 0,
    )
    eaf_code, bof_code = ROUTE_OPTIONS[eaf_route_label]

    # Helper: get default_2026 for a route, country-specific or global avg.
    # Matches on the cleaned 'route_code' column (parentheses stripped in SQL).
    # Returns None if no matching rows exist so the caller can handle gracefully.
    def get_default(route_code, country=None):
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

    bof_default = get_default(bof_code, selected)
    eaf_default = get_default(eaf_code, selected)

    # Grid intensity for the current scenario bar
    if selected and sel_grid is not None and pd.notna(sel_grid):
        current_grid  = sel_grid
        current_label = f'{selected}'
    else:
        current_grid  = global_grid_avg
        current_label = 'Global avg'

    # Indirect EAF cost: kWh/t x gCO2/kWh x 1e-6 x EUR/tCO2 = EUR/t steel
    def indirect_eur_per_t(grid_intensity):
        return EAF_ELECTRICITY_KWH_PER_T * grid_intensity * 1e-6 * cert_price

    # Four bar values in EUR/t of steel.
    # bof_default and eaf_default may be None if the country has no matching
    # route code in cbam_defaults. Guard each value individually so the
    # verified EAF bars always render even when defaults are unavailable.
    v_bof_default = bof_default * cert_price if bof_default is not None else None
    v_eaf_default = eaf_default * cert_price if eaf_default is not None else None
    v_eaf_current = EAF_DIRECT_EMISSIONS * cert_price + indirect_eur_per_t(current_grid)
    v_eaf_clean   = EAF_DIRECT_EMISSIONS * cert_price + indirect_eur_per_t(CLEAN_GRID_INTENSITY)

    # Build bar list, skipping any scenario where the value is unavailable
    scenario_defs = [
        ('BOF\nDefault',                      v_bof_default, BORDER),
        ('EAF\nDefault',                      v_eaf_default, TEXT_MID),
        (f'EAF Verified\n{current_label} grid', v_eaf_current, ACCENT),
        (f'EAF Verified\n{CLEAN_GRID_COUNTRY} grid', v_eaf_clean, ACCENT_MID),
    ]
    scenarios  = [s for s, v, _ in scenario_defs if v is not None]
    values     = [v for _, v, _ in scenario_defs if v is not None]
    bar_colors = [c for _, v, c in scenario_defs if v is not None]

    # Show a warning if default route values are missing for this selection
    missing_defaults = [s for s, v, _ in scenario_defs[:2] if v is None]
    if missing_defaults:
        route_name = eaf_route_label.split('(')[0].strip()
        st.caption(
            f'No CBAM default available for {route_name} '
            f'{"for " + selected if selected else "globally"}. '
            f'Default bars omitted.'
        )

    fig_eaf = go.Figure()

    fig_eaf.add_trace(go.Bar(
        x             = scenarios,
        y             = values,
        marker_color  = bar_colors,
        marker_line_width = 0,
        text          = [f'€{v:.1f}' for v in values],
        textposition  = 'outside',
        textfont      = dict(size=9, color=TEXT_MID),
        hovertemplate = '<b>%{x}</b><br>€%{y:.2f} per tonne of steel<extra></extra>',
    ))

    # Dashed reference line at EAF default level, only when available
    if v_eaf_default is not None:
        fig_eaf.add_hline(
            y                   = v_eaf_default,
            line_dash           = 'dash',
            line_color          = TEXT_LIGHT,
            line_width          = 1,
            annotation_text     = 'EAF default',
            annotation_position = 'top right',
            annotation_font     = dict(size=8, color=TEXT_LIGHT),
        )

    # Y-axis range is fixed so the chart does not jump when switching countries.
    # Floor of 600 EUR/t covers the highest BOF defaults at base price.
    # Scales up with cert_price if the slider is moved significantly higher.
    eaf_y_max = max(600, max((v for v in values if v is not None), default=0) * 1.25)

    fig_eaf.update_layout(
        xaxis         = dict(tickfont=dict(size=9, color=TEXT_MID),
                             gridcolor=BORDER),
        yaxis         = dict(title='€ / tonne of steel',
                             title_font=dict(size=9, color=TEXT_MID),
                             tickfont=dict(size=9, color=TEXT_MID),
                             gridcolor=BORDER, zeroline=False,
                             range=[0, eaf_y_max]),
        paper_bgcolor = BG, plot_bgcolor=BG,
        margin        = dict(l=40, r=10, t=40, b=10),
        height        = 280,
        showlegend    = False,
    )

    st.plotly_chart(fig_eaf, use_container_width=True, key='eaf_chart')

    st.markdown(
        f'<p class="method-note">'
        f'Default bars use EU CBAM default values × certificate price. '
        f'Verified EAF bars use Worldsteel Scrap-EAF direct emissions '
        f'(0.69 tCO₂/t) + indirect ({EAF_ELECTRICITY_KWH_PER_T} kWh/t × grid intensity). '
        f'No markup on verified submissions. '
        f'Clean grid: {CLEAN_GRID_COUNTRY} {CLEAN_GRID_INTENSITY} gCO₂/kWh (Ember 2024).'
        f'</p>',
        unsafe_allow_html=True)


# ── Grid generation mix chart ────────────────────────────────────────────────
# Shows each fuel type as a share of total electricity generation (%).
# Two shaded background regions group fossil and clean fuels visually, so the
# fossil vs clean balance reads immediately without needing a separate legend.
# Group total percentages are annotated above each shaded region.
with col_grid:
    grid_label = (f'Grid generation mix — {selected}'
                  if selected else 'Global grid generation mix')
    st.markdown(f'<p class="section-label">{grid_label}</p>',
                unsafe_allow_html=True)

    # Aggregate generation by fuel type for the selected country or globally
    if selected:
        df_gen = df_grid_generation[df_grid_generation['country'] == selected].copy()
    else:
        df_gen = df_grid_generation.groupby('fuel_type', as_index=False)['value'].sum()

    gen_lookup = df_gen.set_index('fuel_type')['value'].to_dict()
    total_gen  = sum(gen_lookup.get(f, 0) for f in FOSSIL_FUELS + CLEAN_FUELS)

    # Keep only fuels with non-zero generation, preserving fossil-first order
    fuels    = [f for f in FOSSIL_FUELS + CLEAN_FUELS if gen_lookup.get(f, 0) > 0]
    pct_vals = [gen_lookup[f] / total_gen * 100 if total_gen else 0 for f in fuels]
    x_pos    = list(range(len(fuels)))

    fossil_pct = (
        sum(gen_lookup.get(f, 0) for f in FOSSIL_FUELS) / total_gen * 100
        if total_gen else 0
    )
    clean_pct = 100 - fossil_pct

    # Shaded background rectangles identifying fossil and clean groups.
    # Drawn on the plot layer below bars using Plotly shapes.
    shapes, annotations = [], []
    fossil_idx = [i for i, f in enumerate(fuels) if f in FOSSIL_FUELS]
    clean_idx  = [i for i, f in enumerate(fuels) if f in CLEAN_FUELS]

    for indices, bg_color, label, grp_pct in [
        (fossil_idx, '#4a4a4a', 'Fossil', fossil_pct),
        (clean_idx,  '#3a6b45', 'Clean',  clean_pct),
    ]:
        if not indices:
            continue
        x0, x1 = indices[0] - 0.45, indices[-1] + 0.45
        shapes.append(dict(
            type='rect', layer='below',
            x0=x0, x1=x1, y0=0, y1=1,
            xref='x', yref='paper',
            fillcolor=bg_color, opacity=0.07, line_width=0,
        ))
        annotations.append(dict(
            x=(x0 + x1) / 2, y=1.05,
            xref='x', yref='paper',
            text=f'<b>{label}</b> {grp_pct:.0f}%',
            showarrow=False,
            font=dict(size=8, color=TEXT_MID),
            xanchor='center',
        ))

    fig_grid = go.Figure()
    fig_grid.add_trace(go.Bar(
        x                 = x_pos,
        y                 = pct_vals,
        marker_color      = [FUEL_COLORS.get(f, '#999') for f in fuels],
        marker_line_width = 0,
        text              = [f'{v:.1f}%' if v >= 2 else '' for v in pct_vals],
        textposition      = 'outside',
        textfont          = dict(size=8, color=TEXT_MID),
        customdata        = fuels,
        hovertemplate     = '<b>%{customdata}</b><br>%{y:.1f}% of generation<extra></extra>',
    ))

    fig_grid.update_layout(
        shapes      = shapes,
        annotations = annotations,
        xaxis       = dict(
            tickvals  = x_pos,
            ticktext  = fuels,
            tickfont  = dict(size=8, color=TEXT_MID),
            tickangle = -30,
            gridcolor = 'rgba(0,0,0,0)',
        ),
        yaxis       = dict(
            title      = '% of total generation',
            title_font = dict(size=9, color=TEXT_MID),
            tickfont   = dict(size=8, color=TEXT_MID),
            gridcolor  = BORDER,
            range      = [0, min(max(pct_vals) * 1.3, 105)] if pct_vals else [0, 100],
        ),
        paper_bgcolor = BG, plot_bgcolor = BG,
        margin        = dict(l=40, r=10, t=30, b=65),
        height        = 320,
        showlegend    = False,
        bargap        = 0.35,
    )

    st.plotly_chart(fig_grid, use_container_width=True, key='grid_chart')


st.markdown('<br>', unsafe_allow_html=True)
st.caption(
    'Sources: EU Commission · Eurostat COMEXT · Worldsteel · UN Comtrade · Ember · '
    f'Certificate price: €{cert_price}/tCO₂'
)
