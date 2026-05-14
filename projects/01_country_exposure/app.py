# ── CBAM Country Exposure Dashboard ──────────────────────────────────────────
# Project 01: Which countries face the biggest CBAM bill?
#
# Layout:
#   - Sticky filter bar: certificate price slider, sector multiselect,
#     country selectbox — all in one row, coordinated with map clicks
#   - KPI cards (4 columns)
#   - Choropleth map (click to filter country)
#   - Horizontal bar chart (all countries, scrollable 600px container,
#     outer bar stacked by sector high route,
#     inner shaded bar = low route where variation exists)
#   - Drill-down panel (global overview until country selected, then
#     sector donut + high/low route grouped bar)
#   Tab 2: Grid Decarbonization (placeholder)
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
BG_SIDEBAR = '#eae8e2'
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

/* Hide native sidebar toggle entirely */
[data-testid="collapsedControl"] {{
    display: none;
}}
[data-testid="stSidebar"] {{
    display: none;
}}

/* Tabs */
[data-testid="stTabs"] button {{
    font-family: 'DM Sans', sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    color: {TEXT_MID};
}}
[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

/* Sticky filter bar */
.filter-bar {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: {BG_CARD};
    border-bottom: 1px solid {BORDER};
    padding: 0.65rem 0 0.5rem 0;
    margin-bottom: 1.25rem;
}}

/* Filter bar labels */
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

/* Drill-down */
.drill-header {{
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
    color: {TEXT_DARK};
    margin-bottom: 0.15rem;
}}
.drill-sub {{
    font-size: 0.78rem;
    color: {TEXT_MID};
    margin-bottom: 0.6rem;
}}

/* Multiselect tags — match palette */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
    background-color: {ACCENT} !important;
    color: white !important;
    border-radius: 4px !important;
}}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {{
    color: white !important;
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
            c.country,
            c.iso2,
            cw.iso3,
            c.rank,
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
            production_route_high, production_route_low,
            has_route_variation,
            import_tonnes, import_value_eur,
            default_2026_high_route,
            default_2026_low_route,
            embedded_co2_high_route  AS co2_high,
            embedded_co2_low_route   AS co2_low,
            cbam_cost_eur_high_route AS cost_high,
            cbam_cost_eur_low_route  AS cost_low
        FROM cbam_cost_by_country_sector
    """, con)

df_countries = load_country_data()
df_granular  = load_granular_data()
ALL_SECTORS  = sorted(df_granular['sector'].unique().tolist())


# ── Session state ─────────────────────────────────────────────────────────────
if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = None


# ── Sticky filter bar ─────────────────────────────────────────────────────────
# Rendered before tabs so it sits above everything and stays sticky.
# Three controls in one row: certificate price slider, sector multiselect,
# country selectbox. Country selectbox stays in sync with map clicks.

st.markdown('<div class="filter-bar">', unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns([2, 2, 2])

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
    selected_sectors = st.multiselect(
        label            = '_sectors',
        options          = ALL_SECTORS,
        default          = ALL_SECTORS,
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
# Filter by selected sectors and rescale costs to slider certificate price.

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

df_c = df_c.merge(
    df_countries[['country', 'iso3']],
    on='country', how='left'
)

df_c['cost_pct_export'] = (
    df_c['cost_high'] / df_c['import_value_eur'].replace(0, float('nan')) * 100
).round(2)

total_cost_high  = df_c['cost_high'].sum()
total_cost_low   = df_c['cost_low'].sum()
total_co2        = df_g['co2_high'].sum()
n_exposed        = (df_c['cost_high'] > 0).sum()
top_country      = df_c.iloc[0]['country'] if len(df_c) > 0 else 'N/A'
top_country_cost = df_c.iloc[0]['cost_high'] if len(df_c) > 0 else 0


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(['🌍  CBAM Cost Exposure', '⚡  Grid Decarbonization'])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CBAM COST EXPOSURE
# ════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    for col, label, value, sub in [
        (k1, 'Total CBAM Bill (High Route)',
             f'€{total_cost_high/1e9:.2f}B',
             f'Low route: €{total_cost_low/1e9:.2f}B'),
        (k2, 'Embedded CO₂',
             f'{total_co2/1e6:.1f} MtCO₂',
             'Across all CBAM-covered imports'),
        (k3, 'Countries with Exposure',
             str(n_exposed),
             'of 119 countries with CBAM defaults'),
        (k4, 'Highest Single Country Bill',
             f'€{top_country_cost/1e9:.2f}B',
             top_country),
    ]:
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f'<div class="kpi-sub">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Choropleth map ────────────────────────────────────────────────────────
    st.markdown(
        '<p class="section-label">CBAM cost as share of export value — click a country to filter</p>',
        unsafe_allow_html=True
    )

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

    if st.session_state['selected_country']:
        sel_iso3 = df_countries.loc[
            df_countries['country'] == st.session_state['selected_country'], 'iso3'
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
        height        = 360,
    )

    map_event = st.plotly_chart(
        fig_map,
        use_container_width = True,
        on_select           = 'rerun',
        key                 = 'map_chart',
    )

    # Handle map click: sync to country filter
    if (map_event and map_event.get('selection')
            and map_event['selection'].get('points')):
        clicked_iso3 = map_event['selection']['points'][0].get('location')
        if clicked_iso3:
            match = df_countries[df_countries['iso3'] == clicked_iso3]
            if not match.empty:
                clicked_name = match.iloc[0]['country']
                if clicked_name != st.session_state['selected_country']:
                    st.session_state['selected_country'] = clicked_name
                    st.rerun()

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Bar chart + drill-down ────────────────────────────────────────────────
    col_bar, col_drill = st.columns([3, 2], gap='large')

    with col_bar:
        st.markdown(
            '<p class="section-label">Estimated CBAM cost by country — '
            'outer bar = high route stacked by sector · '
            'inner shaded bar = low route where cheaper route exists</p>',
            unsafe_allow_html=True
        )

        n_countries = len(df_c)
        bar_height  = max(n_countries * 22, 400)

        df_all_sectors = (
            df_g.groupby(['country', 'sector'], as_index=False)['cost_high'].sum()
        )

        fig_bar = go.Figure()

        for sector in ALL_SECTORS:
            if sector not in selected_sectors:
                continue
            df_s = df_all_sectors[df_all_sectors['sector'] == sector]
            vals = []
            for country in df_c['country']:
                row = df_s[df_s['country'] == country]
                vals.append(row['cost_high'].values[0] if len(row) > 0 else 0)

            fig_bar.add_trace(go.Bar(
                name          = sector,
                y             = df_c['country'].tolist(),
                x             = vals,
                orientation   = 'h',
                marker_color  = SECTOR_COLORS.get(sector, '#d3d1c9'),
                hovertemplate = f'<b>%{{y}}</b><br>{sector}: €%{{x:,.0f}}<extra></extra>',
            ))

        # Inner low-route bar where variation exists
        df_varied = df_c[df_c['has_any_route_variation']]
        if len(df_varied) > 0:
            fig_bar.add_trace(go.Bar(
                name          = 'Low route (best case)',
                y             = df_varied['country'].tolist(),
                x             = df_varied['cost_low'].tolist(),
                orientation   = 'h',
                marker_color  = 'rgba(255,255,255,0.28)',
                marker_line_color = 'rgba(255,255,255,0.45)',
                marker_line_width = 1,
                hovertemplate = '<b>%{y}</b><br>Low route: €%{x:,.0f}<extra></extra>',
            ))

        # Highlight selected country
        if st.session_state['selected_country']:
            sel = st.session_state['selected_country']
            if sel in df_c['country'].values:
                sel_cost = df_c.loc[df_c['country'] == sel, 'cost_high'].values[0]
                fig_bar.add_shape(
                    type  = 'line',
                    x0    = 0, x1 = sel_cost,
                    y0    = sel, y1 = sel,
                    line  = dict(color=ACCENT_POP, width=2, dash='dot'),
                )

        fig_bar.update_layout(
            barmode       = 'stack',
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
            legend        = dict(
                orientation = 'h',
                yanchor     = 'bottom',
                y           = 1.01,
                xanchor     = 'left',
                x           = 0,
                font        = dict(size=9, color=TEXT_MID),
                bgcolor     = 'rgba(0,0,0,0)',
            ),
            paper_bgcolor = BG_CARD,
            plot_bgcolor  = BG_CARD,
            margin        = dict(l=10, r=10, t=40, b=40),
            height        = bar_height,
        )

        # Native Streamlit scrollable container — reliable for Plotly charts
        with st.container(height=600):
            st.plotly_chart(fig_bar, use_container_width=True, key='bar_chart')

    # ── Drill-down panel ──────────────────────────────────────────────────────
    with col_drill:
        selected = st.session_state['selected_country']

        if selected:
            st.markdown(f'<p class="drill-header">{selected}</p>',
                        unsafe_allow_html=True)
            row = df_c[df_c['country'] == selected]
            if len(row) > 0:
                r = row.iloc[0]
                pct_str = (
                    f'{r["cost_pct_export"]:.1f}% of export value'
                    if pd.notna(r['cost_pct_export']) else 'export value N/A'
                )
                st.markdown(
                    f'<p class="drill-sub">'
                    f'Est. bill: €{r["cost_high"]/1e6:.1f}M &nbsp;·&nbsp; {pct_str}'
                    f'</p>',
                    unsafe_allow_html=True
                )

            df_drill = df_g[df_g['country'] == selected].copy()
            df_ds = (
                df_drill.groupby('sector', as_index=False)
                .agg(cost_high=('cost_high','sum'), cost_low=('cost_low','sum'))
                .sort_values('cost_high', ascending=False)
            )
            df_ds['has_variation'] = df_ds['cost_high'] != df_ds['cost_low']

            # Sector cost donut
            st.markdown('<p class="section-label">Cost by sector</p>',
                        unsafe_allow_html=True)
            fig_donut = go.Figure(go.Pie(
                labels        = df_ds['sector'],
                values        = df_ds['cost_high'],
                hole          = 0.55,
                marker_colors = [
                    SECTOR_COLORS.get(s, '#d3d1c9') for s in df_ds['sector']
                ],
                textinfo      = 'percent',
                textfont      = dict(size=10),
                hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
            ))
            fig_donut.update_layout(
                showlegend    = True,
                legend        = dict(
                    font        = dict(size=9, color=TEXT_MID),
                    orientation = 'v',
                    x           = 1.0,
                ),
                margin        = dict(l=0, r=90, t=10, b=0),
                paper_bgcolor = BG,
                height        = 210,
            )
            st.plotly_chart(fig_donut, use_container_width=True,
                            key='donut_chart')

            # High vs low route by sector
            df_varied_drill = df_ds[df_ds['has_variation']]
            if len(df_varied_drill) > 0:
                st.markdown(
                    '<p class="section-label">High vs low route by sector</p>',
                    unsafe_allow_html=True
                )
                fig_range = go.Figure()
                fig_range.add_trace(go.Bar(
                    name          = 'High route',
                    x             = df_varied_drill['sector'],
                    y             = df_varied_drill['cost_high'],
                    marker_color  = '#5c6b5e',
                    hovertemplate = '%{x}<br>High: €%{y:,.0f}<extra></extra>',
                ))
                fig_range.add_trace(go.Bar(
                    name          = 'Low route',
                    x             = df_varied_drill['sector'],
                    y             = df_varied_drill['cost_low'],
                    marker_color  = '#a8b5aa',
                    hovertemplate = '%{x}<br>Low: €%{y:,.0f}<extra></extra>',
                ))
                fig_range.update_layout(
                    barmode       = 'group',
                    xaxis         = dict(
                        tickfont  = dict(size=9, color=TEXT_MID),
                        tickangle = -20,
                    ),
                    yaxis         = dict(
                        tickformat = '.2s',
                        tickfont   = dict(size=9, color=TEXT_MID),
                        gridcolor  = BORDER,
                    ),
                    legend        = dict(
                        font        = dict(size=9, color=TEXT_MID),
                        orientation = 'h',
                        y           = -0.28,
                        bgcolor     = 'rgba(0,0,0,0)',
                    ),
                    paper_bgcolor = BG,
                    plot_bgcolor  = BG,
                    margin        = dict(l=0, r=0, t=10, b=70),
                    height        = 220,
                )
                st.plotly_chart(fig_range, use_container_width=True,
                                key='range_chart')
            else:
                st.caption(
                    'No route variation for this country — '
                    'single production route published per product.'
                )

        else:
            # Global overview until a country is selected
            st.markdown('<p class="drill-header">Global Overview</p>',
                        unsafe_allow_html=True)
            st.markdown(
                '<p class="drill-sub">'
                'Select a country on the map or use the country filter '
                'to drill down into sector breakdown and route variation.'
                '</p>',
                unsafe_allow_html=True
            )

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
                marker_colors = [
                    SECTOR_COLORS.get(s, '#d3d1c9') for s in df_sec['sector']
                ],
                textinfo      = 'percent',
                textfont      = dict(size=10),
                hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
            ))
            fig_gd.update_layout(
                showlegend    = True,
                legend        = dict(
                    font        = dict(size=9, color=TEXT_MID),
                    orientation = 'v',
                    x           = 1.0,
                ),
                margin        = dict(l=0, r=90, t=10, b=0),
                paper_bgcolor = BG,
                height        = 210,
            )
            st.plotly_chart(fig_gd, use_container_width=True,
                            key='global_donut')

            # Global high vs low route by sector
            st.markdown(
                '<p class="section-label">Global high vs low route by sector</p>',
                unsafe_allow_html=True
            )
            df_global_route = (
                df_g.groupby('sector', as_index=False)
                .agg(cost_high=('cost_high','sum'), cost_low=('cost_low','sum'))
                .sort_values('cost_high', ascending=False)
            )
            fig_gr = go.Figure()
            fig_gr.add_trace(go.Bar(
                name          = 'High route',
                x             = df_global_route['sector'],
                y             = df_global_route['cost_high'],
                marker_color  = '#5c6b5e',
                hovertemplate = '%{x}<br>High: €%{y:,.0f}<extra></extra>',
            ))
            fig_gr.add_trace(go.Bar(
                name          = 'Low route',
                x             = df_global_route['sector'],
                y             = df_global_route['cost_low'],
                marker_color  = '#a8b5aa',
                hovertemplate = '%{x}<br>Low: €%{y:,.0f}<extra></extra>',
            ))
            fig_gr.update_layout(
                barmode       = 'group',
                xaxis         = dict(
                    tickfont  = dict(size=9, color=TEXT_MID),
                    tickangle = -20,
                ),
                yaxis         = dict(
                    tickformat = '.2s',
                    tickfont   = dict(size=9, color=TEXT_MID),
                    gridcolor  = BORDER,
                    title      = '€',
                    title_font = dict(size=9, color=TEXT_MID),
                ),
                legend        = dict(
                    font        = dict(size=9, color=TEXT_MID),
                    orientation = 'h',
                    y           = -0.28,
                    bgcolor     = 'rgba(0,0,0,0)',
                ),
                paper_bgcolor = BG,
                plot_bgcolor  = BG,
                margin        = dict(l=30, r=0, t=10, b=70),
                height        = 220,
            )
            st.plotly_chart(fig_gr, use_container_width=True,
                            key='global_range_chart')

        # Data sources caption at bottom of drill-down
        st.markdown('<br>', unsafe_allow_html=True)
        st.caption(
            'Sources: EU Commission · Eurostat COMEXT · '
            'Worldsteel · UN Comtrade · Ember'
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — GRID DECARBONIZATION POTENTIAL (placeholder)
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Grid Decarbonization Potential")
    st.markdown(
        "This tab will show the BF-BOF vs. EAF scenario chart, "
        "grid generation mix, installed capacity mix, and CO₂ intensity "
        "trend for a selected country."
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    for col, label in zip(
        [col_a, col_b, col_c],
        ['BF-BOF vs. EAF Scenario', 'Grid Generation Mix', 'CO₂ Intensity Trend']
    ):
        with col:
            st.markdown(
                f'<div style="background:{BG_CARD};border-radius:8px;'
                f'padding:3rem 1rem;text-align:center;color:{TEXT_LIGHT};'
                f'font-size:0.85rem;border:1px solid {BORDER};">'
                f'📊<br><br>{label}<br><br><em>Coming soon</em></div>',
                unsafe_allow_html=True
            )
    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        "Requires: electricity consumption per tonne by route (kWh/t), "
        "grid CO₂ intensity from Ember, steel production route mix from Worldsteel. "
        "All data is available in the database."
    )
