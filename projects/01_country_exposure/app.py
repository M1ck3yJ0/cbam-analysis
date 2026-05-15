# ── CBAM Country Exposure Dashboard ──────────────────────────────────────────
# Project 01: Which countries face the biggest CBAM bill?
#
# Layout:
#   Sticky filter bar: certificate price slider, sector pills, country selectbox
#   5 KPI cards (dynamic, country-specific when selected)
#   Row 1: Choropleth map + top 10 bar chart (both respond to map metric toggle)
#   Row 2: Sector donut + EAF scenario placeholder + Grid capacity/utilization
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

# Fuel type groupings for grid chart
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

/* Sticky filter bar */
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

/* KPI cards */
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

/* Section labels */
.section-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: {TEXT_LIGHT};
    margin-bottom: 0.3rem;
    margin-top: 0.1rem;
}}

/* Sector pills */
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

/* Clear + map toggle buttons */
[data-testid="stButton"] button {{
    font-size: 0.72rem !important;
    padding: 2px 8px !important;
    height: 24px !important;
    background: transparent !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT_MID} !important;
    border-radius: 4px !important;
}}

/* Placeholder box */
.placeholder-box {{
    background: {BG_CARD};
    border: 1px dashed {BORDER};
    border-radius: 8px;
    padding: 2rem 1rem;
    text-align: center;
    color: {TEXT_LIGHT};
    font-size: 0.82rem;
    height: 280px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}}

[data-testid="stSlider"] {{ padding-top: 0.1rem; padding-bottom: 0; }}
[data-testid="stDataFrame"] {{ border-radius: 6px; overflow: hidden; }}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────
BASE_PRICE = 75.36


# ── Database connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    db_path = Path(__file__).parent.parent.parent / 'db' / 'cbam.db'
    assert db_path.exists(), f'Database not found at {db_path.resolve()}.'
    return sqlite3.connect(db_path, check_same_thread=False)

con = get_connection()


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_country_data():
    return pd.read_sql("""
        SELECT c.country, c.iso2, cw.iso3,
            c.total_import_tonnes,
            c.total_import_value_eur,
            c.total_embedded_co2_high      AS embedded_co2_high,
            c.total_cbam_cost_high_route   AS cost_high,
            c.total_cbam_cost_low_route    AS cost_low,
            c.cbam_cost_pct_of_export_value_high AS cost_pct_export_high,
            c.cbam_cost_per_tonne_high     AS cost_per_tonne_high,
            c.has_any_route_variation
        FROM cbam_cost_by_country c
        LEFT JOIN country_crosswalk cw ON c.country = cw.country
        ORDER BY c.total_cbam_cost_high_route DESC
    """, con)

@st.cache_data
def load_granular_data():
    return pd.read_sql("""
        SELECT country, sector, has_route_variation,
            import_tonnes, import_value_eur,
            embedded_co2_high_route  AS co2_high,
            cbam_cost_eur_high_route AS cost_high,
            cbam_cost_eur_low_route  AS cost_low
        FROM cbam_cost_by_country_sector
    """, con)

@st.cache_data
def load_global_exports():
    return pd.read_sql("""
        SELECT country,
            SUM(export_value_eur) AS total_export_value_eur,
            SUM(export_tonnes)    AS total_export_tonnes
        FROM global_exports
        GROUP BY country
    """, con)

@st.cache_data
def load_grid_intensity():
    return pd.read_sql("""
        SELECT country, year, co2_intensity_gco2_kwh
        FROM grid_co2_intensity
        WHERE year = (SELECT MAX(year) FROM grid_co2_intensity)
    """, con)

@st.cache_data
def load_grid_capacity():
    return pd.read_sql("""
        SELECT country, year, fuel_type, subcategory, value, unit
        FROM grid_capacity
        WHERE year = (SELECT MAX(year) FROM grid_capacity)
          AND subcategory = 'Fuel'
    """, con)

@st.cache_data
def load_grid_generation():
    return pd.read_sql("""
        SELECT country, year, fuel_type, subcategory, value, unit
        FROM grid_generation
        WHERE year = (SELECT MAX(year) FROM grid_generation)
          AND subcategory = 'Fuel'
    """, con)

df_countries      = load_country_data()
df_granular       = load_granular_data()
df_global_exports = load_global_exports()
df_grid_intensity = load_grid_intensity()
df_grid_capacity  = load_grid_capacity()
df_grid_generation= load_grid_generation()
ALL_SECTORS       = sorted(df_granular['sector'].unique().tolist())

# Global grid avg
global_grid_avg = df_grid_intensity['co2_intensity_gco2_kwh'].mean()


# ── Session state ─────────────────────────────────────────────────────────────
if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = None
if 'map_metric' not in st.session_state:
    st.session_state['map_metric'] = 'pct_export'


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
price_ratio = cert_price / BASE_PRICE

df_g = df_granular[df_granular['sector'].isin(selected_sectors)].copy()
df_g['cost_high'] = df_g['cost_high'] * price_ratio
df_g['cost_low']  = df_g['cost_low']  * price_ratio

df_c = (
    df_g.groupby('country', as_index=False)
    .agg(
        cost_high               = ('cost_high',           'sum'),
        cost_low                = ('cost_low',            'sum'),
        import_tonnes           = ('import_tonnes',       'sum'),
        import_value_eur        = ('import_value_eur',    'sum'),
        co2_high                = ('co2_high',            'sum'),
        has_any_route_variation = ('has_route_variation', 'any'),
    )
    .sort_values('cost_high', ascending=False)
    .reset_index(drop=True)
)

df_c = df_c.merge(df_countries[['country', 'iso3']], on='country', how='left')
df_c = df_c.merge(
    df_global_exports[['country', 'total_export_value_eur', 'total_export_tonnes']],
    on='country', how='left'
)
df_c = df_c.merge(
    df_grid_intensity[['country', 'co2_intensity_gco2_kwh']],
    on='country', how='left'
)

df_c['cost_pct_export'] = (
    df_c['cost_high'] / df_c['import_value_eur'].replace(0, float('nan')) * 100
).round(2)

df_c['cost_per_tonne'] = (
    df_c['cost_high'] / df_c['import_tonnes'].replace(0, float('nan'))
).round(2)

# Global headline numbers
total_cost_high   = df_c['cost_high'].sum()
total_cost_low    = df_c['cost_low'].sum()
total_co2         = df_g['co2_high'].sum()
total_eu_imports  = df_c['import_value_eur'].sum()
total_eu_tonnes   = df_c['import_tonnes'].sum()
total_global_exp  = df_global_exports['total_export_value_eur'].sum()
global_pct_export = (total_eu_imports / total_global_exp * 100) if total_global_exp else None
n_exposed         = (df_c['cost_high'] > 0).sum()

# Top 3 countries share
top3_cost  = df_c.head(3)['cost_high'].sum()
top3_share = top3_cost / total_cost_high * 100 if total_cost_high else 0
top3_names = ', '.join(df_c.head(3)['country'].tolist())

selected = st.session_state['selected_country']

# Country-specific metrics
sel_cost = sel_co2 = sel_pct = sel_eu_imp = sel_total_exp = sel_grid = sel_rank = None
if selected:
    sel_row = df_c[df_c['country'] == selected]
    if len(sel_row) > 0:
        s            = sel_row.iloc[0]
        sel_cost     = s['cost_high']
        sel_co2      = s['co2_high']
        sel_pct      = s['cost_pct_export']
        sel_eu_imp   = s['import_value_eur']
        sel_total_exp= s['total_export_value_eur']
        sel_grid     = s['co2_intensity_gco2_kwh']
        sel_rank     = int(sel_row.index[0]) + 1


# ── KPI cards (5) ─────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

# Card 1: total CBAM bill / country bill
with k1:
    if selected and sel_cost is not None:
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Est. CBAM Bill — {selected}</div>'
            f'<div class="kpi-value">€{sel_cost/1e6:.1f}M</div>'
            f'<div class="kpi-sub">{sel_co2/1e6:.2f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Total Est. CBAM Bill</div>'
            f'<div class="kpi-value">€{total_cost_high/1e9:.2f}B</div>'
            f'<div class="kpi-sub">{total_co2/1e6:.1f} MtCO₂ embedded</div>'
            f'</div>', unsafe_allow_html=True
        )

# Card 2: % exports exposed / country pct
with k2:
    if selected and sel_pct is not None and pd.notna(sel_pct):
        eu_str  = f'EU imports: €{sel_eu_imp/1e9:.2f}B' if sel_eu_imp else ''
        tot_str = f'Total exports: €{sel_total_exp/1e9:.2f}B' if sel_total_exp and pd.notna(sel_total_exp) else ''
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">CBAM Cost as % of Exports — {selected}</div>'
            f'<div class="kpi-value">{sel_pct:.1f}%</div>'
            f'<div class="kpi-sub">{eu_str}<br>{tot_str}</div>'
            f'</div>', unsafe_allow_html=True
        )
    else:
        pct_str = f'{global_pct_export:.1f}%' if global_pct_export else 'N/A'
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">CBAM-Sector Exports Reaching EU</div>'
            f'<div class="kpi-value">{pct_str}</div>'
            f'<div class="kpi-sub">Total: €{total_global_exp/1e9:.1f}B · EU: €{total_eu_imports/1e9:.1f}B</div>'
            f'</div>', unsafe_allow_html=True
        )

# Card 3: global top 3 share / country rank share
with k3:
    if selected and sel_cost is not None:
        country_share = sel_cost / total_cost_high * 100
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Share of Global CBAM Bill — {selected}</div>'
            f'<div class="kpi-value">{country_share:.1f}%</div>'
            f'<div class="kpi-sub">Ranked #{sel_rank} globally</div>'
            f'</div>', unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Top 3 Countries — Share of Global Bill</div>'
            f'<div class="kpi-value">{top3_share:.0f}%</div>'
            f'<div class="kpi-sub">{top3_names}</div>'
            f'</div>', unsafe_allow_html=True
        )

# Card 4: grid intensity
with k4:
    if selected and sel_grid is not None and pd.notna(sel_grid):
        diff     = sel_grid - global_grid_avg
        diff_str = f'{"+" if diff > 0 else ""}{diff:.0f} vs global avg ({global_grid_avg:.0f})'
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Grid Intensity — {selected}</div>'
            f'<div class="kpi-value">{sel_grid:.0f} gCO₂/kWh</div>'
            f'<div class="kpi-sub">{diff_str}</div>'
            f'</div>', unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Global Avg Grid Intensity</div>'
            f'<div class="kpi-value">{global_grid_avg:.0f} gCO₂/kWh</div>'
            f'<div class="kpi-sub">Source: Ember latest year</div>'
            f'</div>', unsafe_allow_html=True
        )

# Card 5: placeholder
with k5:
    st.markdown(
        f'<div class="kpi-card-neutral">'
        f'<div class="kpi-label">EAF + Clean Grid Potential</div>'
        f'<div class="kpi-value">—</div>'
        f'<div class="kpi-sub">Estimated CO₂ reduction vs current.<br>Coming soon.</div>'
        f'</div>', unsafe_allow_html=True
    )

st.markdown('<br>', unsafe_allow_html=True)


# ── Map metric toggle ─────────────────────────────────────────────────────────
map_label_col, toggle_col, clear_col = st.columns([3, 2, 2])

with map_label_col:
    st.markdown('<p class="section-label">Click a country to filter</p>',
                unsafe_allow_html=True)

with toggle_col:
    map_metric = st.segmented_control(
        '_map_metric',
        options        = ['% of exports', 'Abs. cost', 'Cost / tonne'],
        default        = '% of exports',
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

# Map metric config
METRIC_CONFIG = {
    '% of exports' : ('cost_pct_export',  'CBAM cost as % of exports',    '%.1f%%'),
    'Abs. cost'    : ('cost_high',         'Est. CBAM cost (€)',            '€%.0f'),
    'Cost / tonne' : ('cost_per_tonne',    'Est. CBAM cost per tonne (€)',  '€%.2f'),
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
        hover_data             = {
            'iso3'       : False,
            metric_col   : True,
            'cost_high'  : ':,.0f',
        },
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
            fig_map.add_trace(go.Choropleth(
                locations         = [sel_iso3[0]],
                z                 = [1],
                colorscale        = [[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
                showscale         = False,
                marker_line_color = ACCENT_POP,
                marker_line_width = 2.5,
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
        margin        = dict(l=0, r=60, t=0, b=0),
        paper_bgcolor = BG,
        plot_bgcolor  = BG,
        height        = 380,
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
    # Top 10 bar — metric matches map toggle
    bar_label = {
        '% of exports' : 'CBAM cost as % of exports',
        'Abs. cost'    : 'Estimated CBAM cost (€)',
        'Cost / tonne' : 'Est. CBAM cost per tonne (€)',
    }.get(map_metric, 'Estimated CBAM cost (€)')

    st.markdown(
        f'<p class="section-label">Top 10 countries — {bar_label.lower()}</p>',
        unsafe_allow_html=True
    )

    df_top10 = (
        df_c[df_c[metric_col].notna() & (df_c[metric_col] > 0)]
        .nlargest(10, metric_col)
    )

    fig_bar = go.Figure(go.Bar(
        y             = df_top10['country'].tolist(),
        x             = df_top10[metric_col].tolist(),
        orientation   = 'h',
        marker_color  = [
            ACCENT_POP if c == selected else ACCENT
            for c in df_top10['country']
        ],
        hovertemplate = '<b>%{y}</b><br>' + bar_label + ': %{x:,.2f}<extra></extra>',
    ))

    tick_fmt = '.1%' if metric_col == 'cost_pct_export' else '.2s'

    fig_bar.update_layout(
        yaxis         = dict(
            autorange  = 'reversed',
            tickfont   = dict(size=10, family='DM Sans', color=TEXT_DARK),
            gridcolor  = BORDER, automargin=True,
        ),
        xaxis         = dict(
            title      = bar_label,
            tickfont   = dict(size=9, color=TEXT_MID),
            gridcolor  = BORDER,
            tickformat = '.2s',
            title_font = dict(size=10, color=TEXT_MID),
        ),
        showlegend    = False,
        paper_bgcolor = BG,
        plot_bgcolor  = BG,
        margin        = dict(l=10, r=10, t=10, b=50),
        height        = 380,
    )

    st.plotly_chart(fig_bar, use_container_width=True, key='bar_chart')


st.markdown('<br>', unsafe_allow_html=True)


# ── Row 2: Sector donut + EAF placeholder + Grid capacity/utilization ─────────
col_donut, col_eaf, col_grid = st.columns([1, 1, 1.4], gap='large')

with col_donut:
    donut_label = f'Cost by sector — {selected}' if selected else 'Global cost by sector'
    st.markdown(f'<p class="section-label">{donut_label}</p>',
                unsafe_allow_html=True)

    df_donut = df_g[df_g['country'] == selected] if selected else df_g
    df_ds = (
        df_donut.groupby('sector', as_index=False)['cost_high'].sum()
        .sort_values('cost_high', ascending=False)
    )

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
        height        = 280,
    )
    st.plotly_chart(fig_donut, use_container_width=True, key='donut_chart')


with col_eaf:
    st.markdown('<p class="section-label">EAF grid scenario — coming soon</p>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="placeholder-box">'
        f'⚡<br><br>'
        f'<strong>EAF Indirect Cost by Grid Scenario</strong><br><br>'
        f'Cleanest grid · Dirtiest grid · '
        f'{"Selected country" if selected else "Global avg"}'
        f'<br><br><em>Placeholder — coming soon</em>'
        f'</div>',
        unsafe_allow_html=True
    )


with col_grid:
    grid_label = (
        f'Grid capacity & utilization — {selected}'
        if selected else 'Global grid capacity & utilization'
    )
    st.markdown(f'<p class="section-label">{grid_label}</p>',
                unsafe_allow_html=True)

    # Filter grid data for selected country or global aggregate
    if selected:
        df_cap = df_grid_capacity[df_grid_capacity['country'] == selected].copy()
        df_gen = df_grid_generation[df_grid_generation['country'] == selected].copy()
    else:
        df_cap = df_grid_capacity.groupby('fuel_type', as_index=False)['value'].sum()
        df_gen = df_grid_generation.groupby('fuel_type', as_index=False)['value'].sum()

    # Aggregate into fossil and clean groups with sub-fuel breakdown
    def group_fuels(df, value_col='value'):
        fossil = df[df['fuel_type'].isin(FOSSIL_FUELS)].copy()
        clean  = df[df['fuel_type'].isin(CLEAN_FUELS)].copy()
        return fossil, clean

    cap_fossil, cap_clean = group_fuels(df_cap)
    gen_fossil, gen_clean = group_fuels(df_gen)

    fig_grid = go.Figure()

    # Capacity bars by fuel type, grouped as fossil/clean
    for fuel in FOSSIL_FUELS:
        cap_val = cap_fossil[cap_fossil['fuel_type'] == fuel]['value'].sum()
        gen_val = gen_fossil[gen_fossil['fuel_type'] == fuel]['value'].sum() if len(gen_fossil) else 0
        if cap_val > 0:
            fig_grid.add_trace(go.Bar(
                name         = f'{fuel} (capacity)',
                x            = [f'Fossil — {fuel}'],
                y            = [cap_val],
                marker_color = FUEL_COLORS.get(fuel, '#999'),
                opacity      = 0.9,
                hovertemplate = f'<b>{fuel}</b><br>Capacity: %{{y:,.1f}}<extra></extra>',
                legendgroup  = fuel,
            ))
            if gen_val > 0:
                fig_grid.add_trace(go.Bar(
                    name         = f'{fuel} (generation)',
                    x            = [f'Fossil — {fuel}'],
                    y            = [gen_val],
                    marker_color = FUEL_COLORS.get(fuel, '#999'),
                    opacity      = 0.5,
                    hovertemplate = f'<b>{fuel}</b><br>Generation: %{{y:,.1f}}<extra></extra>',
                    legendgroup  = fuel,
                    showlegend   = False,
                ))

    for fuel in CLEAN_FUELS:
        cap_val = cap_clean[cap_clean['fuel_type'] == fuel]['value'].sum()
        gen_val = gen_clean[gen_clean['fuel_type'] == fuel]['value'].sum() if len(gen_clean) else 0
        if cap_val > 0:
            fig_grid.add_trace(go.Bar(
                name         = f'{fuel} (capacity)',
                x            = [f'Clean — {fuel}'],
                y            = [cap_val],
                marker_color = FUEL_COLORS.get(fuel, '#74b583'),
                opacity      = 0.9,
                hovertemplate = f'<b>{fuel}</b><br>Capacity: %{{y:,.1f}}<extra></extra>',
                legendgroup  = fuel,
            ))
            if gen_val > 0:
                fig_grid.add_trace(go.Bar(
                    name         = f'{fuel} (generation)',
                    x            = [f'Clean — {fuel}'],
                    y            = [gen_val],
                    marker_color = FUEL_COLORS.get(fuel, '#74b583'),
                    opacity      = 0.5,
                    hovertemplate = f'<b>{fuel}</b><br>Generation: %{{y:,.1f}}<extra></extra>',
                    legendgroup  = fuel,
                    showlegend   = False,
                ))

    fig_grid.update_layout(
        barmode       = 'overlay',
        xaxis         = dict(
            tickfont  = dict(size=8, color=TEXT_MID),
            tickangle = -30,
            gridcolor = BORDER,
        ),
        yaxis         = dict(
            title      = 'GW / TWh',
            title_font = dict(size=9, color=TEXT_MID),
            tickfont   = dict(size=9, color=TEXT_MID),
            gridcolor  = BORDER,
        ),
        legend        = dict(
            font        = dict(size=8, color=TEXT_MID),
            orientation = 'h',
            y           = -0.35,
            bgcolor     = 'rgba(0,0,0,0)',
        ),
        paper_bgcolor = BG,
        plot_bgcolor  = BG,
        margin        = dict(l=30, r=0, t=10, b=80),
        height        = 280,
        annotations   = [dict(
            text      = 'Dark bar = capacity · Light bar = generation',
            x         = 0, y = 1.04,
            xref      = 'paper', yref = 'paper',
            showarrow = False,
            font      = dict(size=8, color=TEXT_LIGHT),
            xanchor   = 'left',
        )],
    )

    st.plotly_chart(fig_grid, use_container_width=True, key='grid_chart')

st.markdown('<br>', unsafe_allow_html=True)
st.caption(
    'Sources: EU Commission · Eurostat COMEXT · Worldsteel · UN Comtrade · Ember · '
    f'Certificate price: €{BASE_PRICE}/tCO₂ (EC, April 2026)'
)
