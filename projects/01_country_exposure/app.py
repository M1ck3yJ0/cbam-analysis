# ── CBAM Country Exposure Dashboard ──────────────────────────────────────────
# Project 01: Which countries face the biggest CBAM bill?
#
# Layout:
#   - Sticky filter bar: certificate price slider, sector pills, country selectbox
#   - KPI cards: first two global always, last two country-specific when selected
#   - Two-column layout:
#     Left (wider): choropleth map
#     Right: sector donut stacked above top-10 bar chart
#   - Drill-down: country name + bill summary shown above right column charts
#
# Run from repo root:
#   streamlit run projects/01_country_exposure/app.py

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    padding: 1rem 1.25rem;
    border-left: 4px solid {ACCENT};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
}}
.kpi-card-country {{
    background: {BG_CARD};
    border-radius: 8px;
    padding: 1rem 1.25rem;
    border-left: 4px solid {ACCENT_POP};
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    height: 100%;
}}
.kpi-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: {TEXT_LIGHT};
    margin-bottom: 0.2rem;
}}
.kpi-value {{
    font-size: 1.5rem;
    font-weight: 500;
    color: {TEXT_DARK};
    line-height: 1.2;
}}
.kpi-sub {{
    font-size: 0.72rem;
    color: {TEXT_LIGHT};
    margin-top: 0.2rem;
}}
.kpi-formula {{
    font-size: 0.78rem;
    color: {TEXT_MID};
    font-family: 'DM Serif Display', serif;
    margin-top: 0.3rem;
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

/* Country drill header */
.drill-header {{
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
    color: {TEXT_DARK};
    margin-bottom: 0.15rem;
}}
.drill-sub {{
    font-size: 0.78rem;
    color: {TEXT_MID};
    margin-bottom: 0.4rem;
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

/* Clear button */
[data-testid="stButton"] button {{
    font-size: 0.72rem !important;
    padding: 2px 8px !important;
    height: 24px !important;
    float: right;
    background: transparent !important;
    border: 1px solid {BORDER} !important;
    color: {TEXT_MID} !important;
    border-radius: 4px !important;
}}

/* Slim slider */
[data-testid="stSlider"] {{
    padding-top: 0.1rem;
    padding-bottom: 0;
}}

[data-testid="stDataFrame"] {{
    border-radius: 6px;
    overflow: hidden;
}}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────
BASE_PRICE = 75.36


# ── Database connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    """Return a persistent cached SQLite connection."""
    db_path = Path(__file__).parent.parent.parent / 'db' / 'cbam.db'
    assert db_path.exists(), (
        f'Database not found at {db_path.resolve()}. '
        f'Run notebook 08 first to generate cbam.db.'
    )
    return sqlite3.connect(db_path, check_same_thread=False)

con = get_connection()


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_country_data():
    """Country-level aggregated costs joined with iso3 from crosswalk."""
    return pd.read_sql("""
        SELECT
            c.country, c.iso2, cw.iso3,
            c.total_import_tonnes,
            c.total_import_value_eur,
            c.total_embedded_co2_high      AS embedded_co2_high,
            c.total_embedded_co2_low       AS embedded_co2_low,
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
    """Granular country x sector x CN code cost data."""
    return pd.read_sql("""
        SELECT
            country, sector, cn_code,
            has_route_variation,
            import_tonnes, import_value_eur,
            embedded_co2_high_route  AS co2_high,
            cbam_cost_eur_high_route AS cost_high,
            cbam_cost_eur_low_route  AS cost_low
        FROM cbam_cost_by_country_sector
    """, con)

@st.cache_data
def load_global_exports():
    """Total global exports per country from Comtrade."""
    return pd.read_sql("""
        SELECT
            country,
            SUM(export_value_eur)  AS total_export_value_eur,
            SUM(export_tonnes)     AS total_export_tonnes
        FROM global_exports
        GROUP BY country
    """, con)

df_countries     = load_country_data()
df_granular      = load_granular_data()
df_global_exports = load_global_exports()
ALL_SECTORS      = sorted(df_granular['sector'].unique().tolist())


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
        label            = '_cert',
        min_value        = 25.0,
        max_value        = 150.0,
        value            = BASE_PRICE,
        step             = 0.5,
        format           = '€%.2f',
        label_visibility = 'collapsed',
        help             = f'Default: €{BASE_PRICE} — first official EC CBAM price, April 2026',
    )

with fc2:
    st.markdown('<p class="filter-label">Sectors</p>',
                unsafe_allow_html=True)
    selected_sectors = st.pills(
        label            = '_sectors',
        options          = ALL_SECTORS,
        default          = ALL_SECTORS,
        selection_mode   = 'multi',
        label_visibility = 'collapsed',
    )
    if not selected_sectors:
        selected_sectors = ALL_SECTORS

with fc3:
    st.markdown('<p class="filter-label">Country</p>',
                unsafe_allow_html=True)
    country_options = ['All countries'] + sorted(df_countries['country'].tolist())
    current_idx     = 0
    if st.session_state['selected_country'] in country_options:
        current_idx = country_options.index(st.session_state['selected_country'])

    selected_country_filter = st.selectbox(
        label            = '_country',
        options          = country_options,
        index            = current_idx,
        label_visibility = 'collapsed',
    )
    st.session_state['selected_country'] = (
        None if selected_country_filter == 'All countries'
        else selected_country_filter
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
        has_any_route_variation = ('has_route_variation', 'any'),
    )
    .sort_values('cost_high', ascending=False)
    .reset_index(drop=True)
)

df_c = df_c.merge(df_countries[['country', 'iso3']], on='country', how='left')
df_c = df_c.merge(df_global_exports[['country', 'total_export_value_eur']],
                  on='country', how='left')

df_c['cost_pct_export'] = (
    df_c['cost_high'] / df_c['import_value_eur'].replace(0, float('nan')) * 100
).round(2)

# Headline globals
total_cost_high  = df_c['cost_high'].sum()
total_cost_low   = df_c['cost_low'].sum()
total_co2        = df_g['co2_high'].sum()
total_eu_imports = df_c['import_value_eur'].sum()
n_exposed        = (df_c['cost_high'] > 0).sum()
top_country      = df_c.iloc[0]['country'] if len(df_c) > 0 else 'N/A'
top_country_cost = df_c.iloc[0]['cost_high'] if len(df_c) > 0 else 0

selected = st.session_state['selected_country']

# Country-specific metrics
if selected:
    sel_row = df_c[df_c['country'] == selected]
    if len(sel_row) > 0:
        s = sel_row.iloc[0]
        sel_cost         = s['cost_high']
        sel_pct          = s['cost_pct_export']
        sel_eu_imports   = s['import_value_eur']
        sel_total_exports = s['total_export_value_eur']
    else:
        sel_cost = sel_pct = sel_eu_imports = sel_total_exports = None


# ── KPI cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

# Card 1: always global total CBAM bill
with k1:
    st.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">Total CBAM Bill (High Route)</div>'
        f'<div class="kpi-value">€{total_cost_high/1e9:.2f}B</div>'
        f'<div class="kpi-sub">Low route: €{total_cost_low/1e9:.2f}B</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# Card 2: always global embedded CO2
with k2:
    st.markdown(
        f'<div class="kpi-card">'
        f'<div class="kpi-label">Embedded CO₂</div>'
        f'<div class="kpi-value">{total_co2/1e6:.1f} MtCO₂</div>'
        f'<div class="kpi-sub">Across all CBAM-covered imports</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# Card 3: country-specific CBAM cost, or global EU imports
with k3:
    if selected and sel_cost is not None:
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">Est. CBAM Bill — {selected}</div>'
            f'<div class="kpi-value">€{sel_cost/1e6:.1f}M</div>'
            f'<div class="kpi-sub">EU imports: €{sel_eu_imports/1e6:.1f}M</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">Total EU Imports (CBAM sectors)</div>'
            f'<div class="kpi-value">€{total_eu_imports/1e9:.2f}B</div>'
            f'<div class="kpi-sub">{n_exposed} countries with non-zero exposure</div>'
            f'</div>',
            unsafe_allow_html=True
        )

# Card 4: country-specific cost as % of exports, or formula
with k4:
    if selected and sel_pct is not None and pd.notna(sel_pct):
        total_exp_str = (
            f'Total exports: €{sel_total_exports/1e9:.2f}B'
            if sel_total_exports and pd.notna(sel_total_exports)
            else 'Total export data unavailable'
        )
        st.markdown(
            f'<div class="kpi-card-country">'
            f'<div class="kpi-label">CBAM Cost as % of Exports — {selected}</div>'
            f'<div class="kpi-value">{sel_pct:.1f}%</div>'
            f'<div class="kpi-sub">{total_exp_str}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">How CBAM Cost is Estimated</div>'
            f'<div class="kpi-formula">Import volume (t)<br>'
            f'× Default emission value (tCO₂/t)<br>'
            f'× Certificate price (€/tCO₂)</div>'
            f'</div>',
            unsafe_allow_html=True
        )

st.markdown('<br>', unsafe_allow_html=True)


# ── Map label + clear button ───────────────────────────────────────────────────
map_label_col, clear_col = st.columns([6, 1])
with map_label_col:
    st.markdown(
        '<p class="section-label">CBAM cost as share of total export value — '
        'click a country to filter</p>',
        unsafe_allow_html=True
    )
with clear_col:
    if selected:
        if st.button(
            f'✕\u2002Clear filter:\u2002{selected}',
            key='clear_map',
            type='tertiary',
        ):
            st.session_state['selected_country'] = None
            st.rerun()
    else:
        st.empty()


# ── Two-column layout: map left, charts right ─────────────────────────────────
col_map, col_charts = st.columns([3, 2], gap='large')

with col_map:

    # Choropleth map
    df_map = df_c[
        df_c['cost_pct_export'].notna() & (df_c['cost_pct_export'] > 0)
    ].copy()

    fig_map = px.choropleth(
        df_map,
        locations          = 'iso3',
        color              = 'cost_pct_export',
        hover_name         = 'country',
        hover_data         = {
            'iso3'            : False,
            'cost_high'       : ':,.0f',
            'cost_pct_export' : ':.2f',
            'import_tonnes'   : ':,.0f',
        },
        color_continuous_scale = [
            [0.0,  MAP_MIN],
            [0.2,  '#bdc4bc'],
            [0.4,  '#a0b6a4'],
            [0.6,  '#7a9e86'],
            [0.8,  '#52815d'],
            [1.0,  MAP_MAX],
        ],
        range_color = [
            df_map['cost_pct_export'].quantile(0.05),
            df_map['cost_pct_export'].quantile(0.95),
        ],
        labels = {
            'cost_high'       : 'CBAM Cost (€)',
            'cost_pct_export' : 'Cost as % of exports',
            'import_tonnes'   : 'Import volume (t)',
        },
    )

    if selected:
        sel_iso3 = df_countries.loc[
            df_countries['country'] == selected, 'iso3'
        ].values
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
            showframe       = False,
            showcoastlines  = True,
            coastlinecolor  = BORDER,
            showland        = True,
            landcolor       = '#eae8e2',
            showocean       = True,
            oceancolor      = BG,
            bgcolor         = BG,
            projection_type = 'natural earth',
        ),
        coloraxis_colorbar = dict(
            title      = '% of exports',
            thickness  = 10,
            len        = 0.5,
            x          = 1.0,
            xanchor    = 'left',
            tickfont   = dict(size=9, color=TEXT_MID),
            title_font = dict(size=9, color=TEXT_MID),
        ),
        margin        = dict(l=0, r=60, t=0, b=0),
        paper_bgcolor = BG,
        plot_bgcolor  = BG,
        height        = 420,
    )

    map_event = st.plotly_chart(
        fig_map,
        use_container_width = True,
        on_select           = 'rerun',
        key                 = 'map_chart',
    )

    # Handle map click
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


with col_charts:

    if selected:
        # Country name and summary
        row = df_c[df_c['country'] == selected]
        if len(row) > 0:
            r = row.iloc[0]
            pct_str = (
                f'{r["cost_pct_export"]:.1f}% of export value'
                if pd.notna(r.get('cost_pct_export')) else ''
            )
            st.markdown(
                f'<p class="drill-header">{selected}</p>',
                unsafe_allow_html=True
            )
            st.markdown(
                f'<p class="drill-sub">'
                f'Est. CBAM bill: €{r["cost_high"]/1e6:.1f}M'
                f'{" · " + pct_str if pct_str else ""}'
                f'</p>',
                unsafe_allow_html=True
            )

        # Sector cost donut
        st.markdown('<p class="section-label">Cost by sector</p>',
                    unsafe_allow_html=True)
        df_drill = df_g[df_g['country'] == selected]
        df_ds = (
            df_drill.groupby('sector', as_index=False)['cost_high'].sum()
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
            height        = 200,
        )
        st.plotly_chart(fig_donut, use_container_width=True, key='donut_chart')

    else:
        # Global sector donut
        st.markdown('<p class="section-label">Global cost by sector</p>',
                    unsafe_allow_html=True)
        df_sec = (
            df_g.groupby('sector', as_index=False)['cost_high'].sum()
            .sort_values('cost_high', ascending=False)
        )
        fig_gd = go.Figure(go.Pie(
            labels        = df_sec['sector'],
            values        = df_sec['cost_high'],
            hole          = 0.55,
            marker_colors = [SECTOR_COLORS.get(s, '#d3d1c9') for s in df_sec['sector']],
            textinfo      = 'percent',
            textfont      = dict(size=10),
            hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
        ))
        fig_gd.update_layout(
            showlegend    = True,
            legend        = dict(font=dict(size=9, color=TEXT_MID),
                                 orientation='v', x=1.0),
            margin        = dict(l=0, r=90, t=10, b=0),
            paper_bgcolor = BG,
            height        = 200,
        )
        st.plotly_chart(fig_gd, use_container_width=True, key='global_donut')

    # Top 10 bar chart — always shows global top 10, highlights selected country
    st.markdown(
        '<p class="section-label">Top 10 countries by estimated CBAM cost</p>',
        unsafe_allow_html=True
    )

    df_top10 = df_c.head(10).copy()

    fig_bar = go.Figure()

    fig_bar.add_trace(go.Bar(
        name          = 'High route cost',
        y             = df_top10['country'].tolist(),
        x             = df_top10['cost_high'].tolist(),
        orientation   = 'h',
        marker_color  = [
            ACCENT_POP if c == selected else ACCENT
            for c in df_top10['country']
        ],
        hovertemplate = '<b>%{y}</b><br>€%{x:,.0f}<extra></extra>',
    ))

    fig_bar.update_layout(
        yaxis         = dict(
            autorange  = 'reversed',
            tickfont   = dict(size=10, family='DM Sans', color=TEXT_DARK),
            gridcolor  = BORDER,
            automargin = True,
        ),
        xaxis         = dict(
            title      = 'Estimated CBAM Cost (€)',
            tickfont   = dict(size=9, color=TEXT_MID),
            gridcolor  = BORDER,
            tickformat = '.2s',
            title_font = dict(size=10, color=TEXT_MID),
        ),
        showlegend    = False,
        paper_bgcolor = BG,
        plot_bgcolor  = BG,
        margin        = dict(l=10, r=10, t=10, b=40),
        height        = 260,
    )

    st.plotly_chart(fig_bar, use_container_width=True, key='bar_chart')

    st.markdown('<br>', unsafe_allow_html=True)
    st.caption(
        'Sources: EU Commission · Eurostat COMEXT · '
        'Worldsteel · UN Comtrade · Ember'
    )
