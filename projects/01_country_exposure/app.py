# ── CBAM Country Exposure Dashboard ──────────────────────────────────────────
# Project 01: Which countries face the biggest CBAM bill?
#
# Streamlit dashboard with:
#   Tab 1 — CBAM Cost Exposure
#     - Choropleth map: CBAM cost as share of export value (log scale)
#     - Horizontal bar chart: top 10 countries, outer bar = high route stacked
#       by sector, inner shaded bar = low route total where variation exists
#     - Drill-down panel: sector breakdown + route variation by sector
#       for selected country (global view when no country selected)
#   Tab 2 — Grid Decarbonization Potential (placeholder, built later)
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
# Must be the first Streamlit call.

st.set_page_config(
    page_title            = 'CBAM Country Exposure',
    page_icon             = '🌍',
    layout                = 'wide',
    initial_sidebar_state = 'expanded',
)

# ── Styling ───────────────────────────────────────────────────────────────────
# DM Sans for body text, DM Serif Display for headlines.
# Warm off-white background, slate text, EU blue accent (#003399).

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=DM+Serif+Display&display=swap');

html, body, [class*="css"]  { font-family: 'DM Sans', sans-serif; }
h1, h2, h3                  { font-family: 'DM Serif Display', serif; color: #1a2332; }
.main                        { background-color: #f8f7f4; }
.block-container             { padding-top: 1.5rem; padding-bottom: 2rem; }

.kpi-card {
    background: white;
    border-radius: 8px;
    padding: 1.1rem 1.4rem;
    border-left: 4px solid #003399;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}
.kpi-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 0.2rem;
}
.kpi-value {
    font-size: 1.6rem;
    font-weight: 500;
    color: #1a2332;
    line-height: 1.2;
}
.kpi-sub {
    font-size: 0.75rem;
    color: #9ca3af;
    margin-top: 0.2rem;
}
.section-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #9ca3af;
    margin-bottom: 0.4rem;
}
.drill-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
    color: #1a2332;
    margin-bottom: 0.25rem;
}
.drill-sub {
    font-size: 0.8rem;
    color: #6b7280;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────
# BASE_PRICE is the certificate price used in the calculations notebook.
# All cost columns in the DB are based on this price.
# The sidebar slider rescales costs proportionally at runtime.

BASE_PRICE = 75.36

# Sector color palette — consistent across all charts in this dashboard.
SECTOR_COLORS = {
    'Iron and Steel' : '#1d3557',
    'Aluminium'      : '#457b9d',
    'Cement'         : '#e9c46a',
    'Fertilizers'    : '#2a9d8f',
    'Hydrogen'       : '#e76f51',
    'Electricity'    : '#a8dadc',
}


# ── Database connection ───────────────────────────────────────────────────────
# Cached at resource level so the connection persists across reruns.

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
# All queries cached with st.cache_data. Streamlit reruns on every interaction
# so caching prevents redundant DB reads.

@st.cache_data
def load_country_data():
    """Country-level aggregated costs. One row per country, 119 rows."""
    return pd.read_sql("""
        SELECT
            country,
            iso2,
            iso3,
            rank,
            total_import_tonnes,
            total_import_value_eur,
            total_embedded_co2_high      AS embedded_co2_high,
            total_embedded_co2_low       AS embedded_co2_low,
            total_cbam_cost_high_route   AS cost_high,
            total_cbam_cost_low_route    AS cost_low,
            cbam_cost_pct_of_export_value_high AS cost_pct_export_high,
            cbam_cost_pct_of_export_value_low  AS cost_pct_export_low,
            cbam_cost_per_tonne_high     AS cost_per_tonne_high,
            cbam_cost_per_tonne_low      AS cost_per_tonne_low,
            has_any_route_variation
        FROM cbam_cost_by_country
        ORDER BY total_cbam_cost_high_route DESC
    """, con)

@st.cache_data
def load_sector_totals():
    """Global sector-level aggregated costs. One row per sector."""
    return pd.read_sql("""
        SELECT
            sector,
            n_countries,
            total_import_tonnes,
            total_cbam_cost_high_route  AS cost_high,
            total_cbam_cost_low_route   AS cost_low,
            pct_of_total_high
        FROM cbam_cost_by_sector
        ORDER BY cost_high DESC
    """, con)

@st.cache_data
def load_granular_data():
    """Granular country x sector x CN code data. Source for all drill-downs."""
    return pd.read_sql("""
        SELECT
            country,
            sector,
            cn_code,
            production_route_high,
            production_route_low,
            has_route_variation,
            import_tonnes,
            import_value_eur,
            default_2026_high_route,
            default_2026_low_route,
            embedded_co2_high_route  AS co2_high,
            embedded_co2_low_route   AS co2_low,
            cbam_cost_eur_high_route AS cost_high,
            cbam_cost_eur_low_route  AS cost_low
        FROM cbam_cost_by_country_sector
    """, con)

df_countries = load_country_data()
df_sectors   = load_sector_totals()
df_granular  = load_granular_data()

ALL_SECTORS = sorted(df_granular['sector'].unique().tolist())


# ── Session state initialisation ──────────────────────────────────────────────
# selected_country persists across reruns and is updated by both the sidebar
# selectbox and map click events.

if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = None


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## CBAM Exposure")
    st.markdown(
        "Estimated certificate costs under EU CBAM default emission values. "
        "2024 trade flows · April 2026 price."
    )
    st.divider()

    # Certificate price slider
    st.markdown('<p class="section-label">Certificate Price (€/tCO₂)</p>',
                unsafe_allow_html=True)
    cert_price = st.slider(
        label            = '_cert',
        min_value        = 25.0,
        max_value        = 150.0,
        value            = BASE_PRICE,
        step             = 0.5,
        format           = '€%.2f',
        label_visibility = 'collapsed',
    )
    st.caption(f'Default: €{BASE_PRICE} — first official EC CBAM price, April 2026')

    st.divider()

    # Sector multiselect
    st.markdown('<p class="section-label">Sectors</p>', unsafe_allow_html=True)
    selected_sectors = st.multiselect(
        label            = '_sectors',
        options          = ALL_SECTORS,
        default          = ALL_SECTORS,
        label_visibility = 'collapsed',
    )
    if not selected_sectors:
        selected_sectors = ALL_SECTORS

    st.divider()

    # Country selector (coordinates with map click)
    st.markdown('<p class="section-label">Country</p>', unsafe_allow_html=True)
    country_options = ['All countries'] + sorted(df_countries['country'].tolist())
    sidebar_country = st.selectbox(
        label            = '_country',
        options          = country_options,
        index            = 0 if st.session_state['selected_country'] is None
                           else country_options.index(
                               st.session_state['selected_country']
                           ) if st.session_state['selected_country'] in country_options
                           else 0,
        label_visibility = 'collapsed',
    )
    # Sync sidebar selection to session state
    st.session_state['selected_country'] = (
        None if sidebar_country == 'All countries' else sidebar_country
    )

    if st.session_state['selected_country'] is not None:
        if st.button('✕  Clear selection', use_container_width=True):
            st.session_state['selected_country'] = None
            st.rerun()

    st.divider()
    st.caption(
        "Sources: EU Commission · Eurostat COMEXT · "
        "Worldsteel · UN Comtrade · Ember"
    )


# ── Derived data: apply filters and rescale to slider price ───────────────────
# Filter by selected sectors and rescale all cost columns proportionally.
# This keeps the slider responsive without rerunning DB queries.

price_ratio = cert_price / BASE_PRICE

df_g = df_granular[df_granular['sector'].isin(selected_sectors)].copy()
df_g['cost_high'] = df_g['cost_high'] * price_ratio
df_g['cost_low']  = df_g['cost_low']  * price_ratio

# Re-aggregate country totals from filtered granular data
df_c = (
    df_g.groupby('country', as_index=False)
    .agg(
        cost_high             = ('cost_high', 'sum'),
        cost_low              = ('cost_low',  'sum'),
        import_tonnes         = ('import_tonnes', 'sum'),
        import_value_eur      = ('import_value_eur', 'sum'),
        has_any_route_variation = ('has_route_variation', 'any'),
    )
    .sort_values('cost_high', ascending=False)
    .reset_index(drop=True)
)

# Merge iso3 back in for map
df_c = df_c.merge(
    df_countries[['country', 'iso3', 'cost_pct_export_high']],
    on='country', how='left'
)

# Recalculate cost as pct of export value with current price
df_c['cost_pct_export'] = (
    df_c['cost_high'] / df_c['import_value_eur'].replace(0, float('nan')) * 100
).round(2)

# Global headline numbers
total_cost_high  = df_c['cost_high'].sum()
total_cost_low   = df_c['cost_low'].sum()
total_co2        = (df_granular[df_granular['sector'].isin(selected_sectors)]['co2_high'] * price_ratio).sum()
n_exposed        = (df_c['cost_high'] > 0).sum()
top_country      = df_c.iloc[0]['country'] if len(df_c) > 0 else 'N/A'
top_country_cost = df_c.iloc[0]['cost_high'] if len(df_c) > 0 else 0


# ── Tab layout ────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(['🌍  CBAM Cost Exposure', '⚡  Grid Decarbonization'])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — CBAM COST EXPOSURE
# ════════════════════════════════════════════════════════════════════════════

with tab1:

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total CBAM Bill (High Route)</div>
            <div class="kpi-value">€{total_cost_high/1e9:.2f}B</div>
            <div class="kpi-sub">Low route: €{total_cost_low/1e9:.2f}B</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Embedded CO₂</div>
            <div class="kpi-value">{total_co2/1e6:.1f} MtCO₂</div>
            <div class="kpi-sub">Across all CBAM-covered imports</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Countries with Exposure</div>
            <div class="kpi-value">{n_exposed}</div>
            <div class="kpi-sub">of 119 countries with CBAM defaults</div>
        </div>""", unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Highest Single Country Bill</div>
            <div class="kpi-value">€{top_country_cost/1e9:.2f}B</div>
            <div class="kpi-sub">{top_country}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Choropleth map ────────────────────────────────────────────────────────
    # Countries shaded by CBAM cost as % of export value, log scale.
    # Clicking a country updates session state and filters all other charts.

    st.markdown('<p class="section-label">CBAM Cost as Share of Export Value — click a country to filter</p>',
                unsafe_allow_html=True)

    df_map = df_c[df_c['cost_pct_export'].notna() & (df_c['cost_pct_export'] > 0)].copy()

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
            [0.0,  '#dbeafe'],
            [0.25, '#93c5fd'],
            [0.5,  '#3b82f6'],
            [0.75, '#1d4ed8'],
            [1.0,  '#1e3a8a'],
        ],
        range_color        = [
            df_map['cost_pct_export'].quantile(0.05),
            df_map['cost_pct_export'].quantile(0.95),
        ],
        labels             = {
            'cost_high'       : 'CBAM Cost (€)',
            'cost_pct_export' : 'Cost as % of exports',
            'import_tonnes'   : 'Import volume (t)',
        },
    )

    fig_map.update_layout(
        geo = dict(
            showframe      = False,
            showcoastlines = True,
            coastlinecolor = '#e5e7eb',
            showland       = True,
            landcolor      = '#f3f4f6',
            showocean      = True,
            oceancolor     = '#f8f7f4',
            bgcolor        = '#f8f7f4',
            projection_type = 'natural earth',
        ),
        coloraxis_colorbar = dict(
            title      = '% of exports',
            thickness  = 12,
            len        = 0.6,
            tickfont   = dict(size=10),
            titlefont  = dict(size=10),
        ),
        margin     = dict(l=0, r=0, t=0, b=0),
        paper_bgcolor = '#f8f7f4',
        plot_bgcolor  = '#f8f7f4',
        height     = 380,
    )

    # Highlight selected country if one is active
    if st.session_state['selected_country']:
        selected_iso3 = df_countries.loc[
            df_countries['country'] == st.session_state['selected_country'], 'iso3'
        ].values
        if len(selected_iso3) > 0:
            fig_map.add_trace(go.Choropleth(
                locations       = [selected_iso3[0]],
                z               = [1],
                colorscale      = [[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
                showscale       = False,
                marker_line_color = '#003399',
                marker_line_width = 2.5,
            ))

    map_event = st.plotly_chart(
        fig_map,
        use_container_width = True,
        on_select           = 'rerun',
        key                 = 'map_chart',
    )

    # Handle map click: update selected_country from click event
    if map_event and map_event.get('selection') and map_event['selection'].get('points'):
        clicked_iso3 = map_event['selection']['points'][0].get('location')
        if clicked_iso3:
            match = df_countries[df_countries['iso3'] == clicked_iso3]
            if not match.empty:
                clicked_name = match.iloc[0]['country']
                if clicked_name != st.session_state['selected_country']:
                    st.session_state['selected_country'] = clicked_name
                    st.rerun()

    # ── Bar chart + drill-down panel ──────────────────────────────────────────
    col_bar, col_drill = st.columns([3, 2], gap='large')

    # ── Bar chart ─────────────────────────────────────────────────────────────
    with col_bar:
        st.markdown('<p class="section-label">Top 10 Countries by Estimated CBAM Cost</p>',
                    unsafe_allow_html=True)

        # Build top 10 from filtered + rescaled data
        df_top10 = df_c.head(10).copy()

        # Get sector breakdown for each top-10 country
        df_top10_sectors = (
            df_g[df_g['country'].isin(df_top10['country'])]
            .groupby(['country', 'sector'], as_index=False)['cost_high']
            .sum()
        )

        fig_bar = go.Figure()

        # Outer bars: stacked by sector (high route)
        for sector in ALL_SECTORS:
            if sector not in selected_sectors:
                continue
            df_s = df_top10_sectors[df_top10_sectors['sector'] == sector]
            # Align to top10 order
            vals = []
            for country in df_top10['country']:
                row = df_s[df_s['country'] == country]
                vals.append(row['cost_high'].values[0] if len(row) > 0 else 0)

            fig_bar.add_trace(go.Bar(
                name        = sector,
                y           = df_top10['country'].tolist(),
                x           = vals,
                orientation = 'h',
                marker_color = SECTOR_COLORS.get(sector, '#cccccc'),
                hovertemplate = f'<b>%{{y}}</b><br>{sector}: €%{{x:,.0f}}<extra></extra>',
            ))

        # Inner bar: low route total (only where route variation exists)
        df_top10_varied = df_top10[df_top10['has_any_route_variation']]
        if len(df_top10_varied) > 0:
            fig_bar.add_trace(go.Bar(
                name         = 'Low route (best case)',
                y            = df_top10_varied['country'].tolist(),
                x            = df_top10_varied['cost_low'].tolist(),
                orientation  = 'h',
                marker_color = 'rgba(255,255,255,0.35)',
                marker_line_color = 'rgba(255,255,255,0.7)',
                marker_line_width = 1,
                showlegend   = True,
                hovertemplate = '<b>%{y}</b><br>Low route: €%{x:,.0f}<extra></extra>',
            ))

        # Highlight selected country
        if st.session_state['selected_country'] and \
           st.session_state['selected_country'] in df_top10['country'].values:
            fig_bar.add_hline(
                y             = st.session_state['selected_country'],
                line_color    = '#003399',
                line_width    = 2,
                line_dash     = 'dot',
            )

        fig_bar.update_layout(
            barmode       = 'stack',
            yaxis         = dict(
                autorange     = 'reversed',
                tickfont      = dict(size=11, family='DM Sans'),
                gridcolor     = '#f3f4f6',
            ),
            xaxis         = dict(
                title         = 'Estimated CBAM Cost (€)',
                tickfont      = dict(size=10),
                gridcolor     = '#e5e7eb',
                tickformat    = ',.0f',
            ),
            legend        = dict(
                orientation   = 'h',
                yanchor       = 'bottom',
                y             = -0.25,
                xanchor       = 'left',
                x             = 0,
                font          = dict(size=10),
            ),
            paper_bgcolor = '#f8f7f4',
            plot_bgcolor  = '#f8f7f4',
            margin        = dict(l=0, r=10, t=10, b=10),
            height        = 420,
        )

        st.plotly_chart(fig_bar, use_container_width=True, key='bar_chart')

    # ── Drill-down panel ──────────────────────────────────────────────────────
    with col_drill:
        selected = st.session_state['selected_country']

        if selected:
            st.markdown(f'<p class="drill-header">{selected}</p>',
                        unsafe_allow_html=True)

            df_drill = df_g[df_g['country'] == selected].copy()
            df_drill_sector = (
                df_drill.groupby('sector', as_index=False)
                .agg(cost_high=('cost_high','sum'), cost_low=('cost_low','sum'))
                .sort_values('cost_high', ascending=False)
            )
            df_drill_sector['has_variation'] = (
                df_drill_sector['cost_high'] != df_drill_sector['cost_low']
            )

            # Left chart: sector cost breakdown donut
            st.markdown('<p class="section-label">Cost by sector</p>',
                        unsafe_allow_html=True)
            fig_donut = go.Figure(go.Pie(
                labels       = df_drill_sector['sector'],
                values       = df_drill_sector['cost_high'],
                hole         = 0.55,
                marker_colors = [
                    SECTOR_COLORS.get(s, '#cccccc')
                    for s in df_drill_sector['sector']
                ],
                textinfo     = 'percent',
                hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
            ))
            fig_donut.update_layout(
                showlegend    = True,
                legend        = dict(font=dict(size=10), orientation='v'),
                margin        = dict(l=0, r=0, t=10, b=0),
                paper_bgcolor = '#f8f7f4',
                height        = 180,
            )
            st.plotly_chart(fig_donut, use_container_width=True, key='donut_chart')

            # Right chart: high vs low route by sector (only sectors with variation)
            df_varied = df_drill_sector[df_drill_sector['has_variation']]
            if len(df_varied) > 0:
                st.markdown('<p class="section-label">Route variation by sector</p>',
                            unsafe_allow_html=True)
                fig_range = go.Figure()
                fig_range.add_trace(go.Bar(
                    name         = 'High route',
                    x            = df_varied['sector'],
                    y            = df_varied['cost_high'],
                    marker_color = '#1d3557',
                    hovertemplate = '%{x}<br>High: €%{y:,.0f}<extra></extra>',
                ))
                fig_range.add_trace(go.Bar(
                    name         = 'Low route',
                    x            = df_varied['sector'],
                    y            = df_varied['cost_low'],
                    marker_color = '#a8dadc',
                    hovertemplate = '%{x}<br>Low: €%{y:,.0f}<extra></extra>',
                ))
                fig_range.update_layout(
                    barmode       = 'group',
                    xaxis         = dict(tickfont=dict(size=9)),
                    yaxis         = dict(
                        tickformat = ',.0f',
                        tickfont   = dict(size=9),
                        gridcolor  = '#e5e7eb',
                    ),
                    legend        = dict(font=dict(size=9), orientation='h',
                                        y=-0.3),
                    paper_bgcolor = '#f8f7f4',
                    plot_bgcolor  = '#f8f7f4',
                    margin        = dict(l=0, r=0, t=10, b=0),
                    height        = 180,
                )
                st.plotly_chart(fig_range, use_container_width=True,
                                key='range_chart')
            else:
                st.caption('No route variation for this country — '
                           'only one production route published per product.')

        else:
            # Global view when no country selected
            st.markdown('<p class="drill-header">Global Overview</p>',
                        unsafe_allow_html=True)
            st.markdown('<p class="drill-sub">Select a country on the map or '
                        'bar chart to drill down.</p>',
                        unsafe_allow_html=True)

            # Sector share donut — global
            st.markdown('<p class="section-label">Global cost by sector</p>',
                        unsafe_allow_html=True)
            df_sec_filtered = (
                df_g.groupby('sector', as_index=False)['cost_high'].sum()
                .sort_values('cost_high', ascending=False)
            )
            fig_global_donut = go.Figure(go.Pie(
                labels        = df_sec_filtered['sector'],
                values        = df_sec_filtered['cost_high'],
                hole          = 0.55,
                marker_colors = [
                    SECTOR_COLORS.get(s, '#cccccc')
                    for s in df_sec_filtered['sector']
                ],
                textinfo      = 'percent',
                hovertemplate = '<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>',
            ))
            fig_global_donut.update_layout(
                showlegend    = True,
                legend        = dict(font=dict(size=10)),
                margin        = dict(l=0, r=0, t=10, b=0),
                paper_bgcolor = '#f8f7f4',
                height        = 200,
            )
            st.plotly_chart(fig_global_donut, use_container_width=True,
                            key='global_donut')

            # Top 5 summary table
            st.markdown('<p class="section-label">Top 5 countries</p>',
                        unsafe_allow_html=True)
            df_top5 = df_c.head(5)[['country', 'cost_high']].copy()
            df_top5['cost_high'] = df_top5['cost_high'].apply(
                lambda x: f'€{x/1e9:.2f}B'
            )
            df_top5.columns = ['Country', 'Est. CBAM Cost']
            st.dataframe(df_top5, hide_index=True, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — GRID DECARBONIZATION POTENTIAL (placeholder)
# ════════════════════════════════════════════════════════════════════════════

with tab2:
    st.markdown("### Grid Decarbonization Potential")
    st.markdown(
        "This tab will show the BF-BOF vs. EAF scenario chart and grid "
        "electricity mix analysis. Coming in the next build."
    )

    col_a, col_b, col_c = st.columns(3)
    for col, label in zip(
        [col_a, col_b, col_c],
        ['BF-BOF vs. EAF Scenario', 'Grid Generation Mix', 'CO₂ Intensity Trend']
    ):
        with col:
            st.markdown(
                f'<div style="background:#f3f4f6;border-radius:8px;padding:3rem 1rem;'
                f'text-align:center;color:#9ca3af;font-size:0.85rem;">'
                f'📊<br><br>{label}<br><br><em>Coming soon</em></div>',
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        "Tab 2 requires: electricity consumption per tonne by route (kWh/t), "
        "grid CO₂ intensity from Ember, and steel production route mix from Worldsteel. "
        "All data is available in the database."
    )
