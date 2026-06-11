import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path

st.set_page_config(page_title="NYC Taxi Dashboard 2025 - Complete", layout="wide")

@st.cache_data
def load_all_data():
    df = pd.read_parquet(r"C:\Users\HessaM\Desktop\nyc_taxi_dashboard\aggregated\all_2025_cleaned.parquet")
    
    zone_lookup = pd.read_csv(r"C:\Users\HessaM\Desktop\dataset\taxi_zone_lookup.csv")
    zone_lookup = zone_lookup[['LocationID', 'Zone', 'Borough']]
    
    df = df.merge(zone_lookup, left_on='PULocationID', right_on='LocationID', how='left')
    
    geojson_path = Path(r"C:\Users\HessaM\Desktop\dataset\nyc_taxi_zones.geojson")
    with open(geojson_path, 'r') as f:
        geojson = json.load(f)
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df['day_name'] = df['day_of_week'].map(lambda x: day_names[x])
    
    return df, geojson, zone_lookup

df, geojson, zone_lookup = load_all_data()

st.sidebar.header("🎛️ Dashboard Controls")

selected_months = st.sidebar.multiselect(
    "Select Months",
    options=sorted(df['month'].unique()),
    default=list(range(1, 13)),
    format_func=lambda x: f"Month {x}"
)

selected_hour_range = st.sidebar.slider(
    "Hour Range",
    min_value=0, max_value=23,
    value=(6, 20),
    help="Filter trips by pickup hour"
)
borough_options = sorted([b for b in df['Borough'].dropna().unique() if b != 'Unknown'])

selected_boroughs = st.sidebar.multiselect(
    "Borough Filter",
    options=borough_options,
    default=[],
    help="Leave empty to show all boroughs"
)

min_trips = st.sidebar.slider(
    "Minimum Trips per Zone",
    min_value=0, max_value=50000, value=1000,
    step=1000,
    help="Hide zones with fewer trips"
)

filtered = df[
    (df['month'].isin(selected_months)) &
    (df['hour'] >= selected_hour_range[0]) &
    (df['hour'] <= selected_hour_range[1])
]

filtered = filtered[filtered['Borough'] != 'Unknown']
if selected_boroughs:
    filtered = filtered[filtered['Borough'].isin(selected_boroughs)]

zone_agg = filtered.groupby('PULocationID').agg({
    'trip_count': 'sum',
    'total_fare': 'sum',
    'total_tip': 'sum',
    'total_congestion_fee': 'sum',
    'avg_fare': 'mean',
    'avg_tip': 'mean',
    'Zone': 'first',
    'Borough': 'first'
}).reset_index()

zone_agg = zone_agg[zone_agg['trip_count'] >= min_trips]

st.title("🗽 NYC Taxi Trip Analysis 2025")
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    total_trips = filtered['trip_count'].sum()
    st.metric("🚕 Total Trips", f"{total_trips:,.0f}")
with col2:
    avg_fare = filtered['avg_fare'].mean()
    st.metric("💰 Avg Fare", f"${avg_fare:.2f}")
with col3:
    avg_tip = filtered['avg_tip'].mean()
    st.metric("💵 Avg Tip", f"${avg_tip:.2f}")
with col4:
    tip_pct = (avg_tip / avg_fare * 100) if avg_fare > 0 else 0
    st.metric("📊 Tip %", f"{tip_pct:.1f}%")
with col5:
    congestion_total = filtered['total_congestion_fee'].sum()
    st.metric("🏙️ Congestion Fees", f"${congestion_total:,.0f}")

st.markdown("---")

col_map, col_stats = st.columns([2.5, 1])

with col_map:
    st.subheader("🗺️ Trip Volume by Taxi Zone")
    
    color_metric = st.radio(
        "Color map by:",
        ['Total Trips', 'Average Fare', 'Average Tip', 'Total Congestion Fee'],
        horizontal=True
    )
    
    metric_map = {
        'Total Trips': 'trip_count',
        'Average Fare': 'avg_fare',
        'Average Tip': 'avg_tip',
        'Total Congestion Fee': 'total_congestion_fee'
    }
    
    fig = px.choropleth_mapbox(
        zone_agg,
        geojson=geojson,
        locations='PULocationID',
        featureidkey="properties.locationid",
        color=metric_map[color_metric],
        color_continuous_scale="Plasma",
        mapbox_style="carto-positron",
        zoom=9.5,
        center={"lat": 40.75, "lon": -73.98},
        opacity=0.7,
        hover_name='Zone',
        hover_data={
            'trip_count': ':,.0f',
            'avg_fare': ':$%.2f',
            'avg_tip': ':$%.2f',
            'total_congestion_fee': ':$%.0f',
            'PULocationID': False
        },
        labels={
            'trip_count': 'Total Trips',
            'avg_fare': 'Avg Fare',
            'avg_tip': 'Avg Tip',
            'total_congestion_fee': 'Congestion Fees'
        }
    )
    
    fig.update_layout(
        margin={"r":0, "t":0, "l":0, "b":0},
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)

with col_stats:
    st.subheader("📊 Borough Statistics")
    
    borough_stats = zone_agg.groupby('Borough').agg({
        'trip_count': 'sum',
        'avg_fare': 'mean',
        'avg_tip': 'mean'
    }).round(2)
    
    borough_stats['trips_pct'] = (borough_stats['trip_count'] / borough_stats['trip_count'].sum() * 100).round(1)
    borough_stats = borough_stats.sort_values('trip_count', ascending=False)
    
    st.dataframe(
        borough_stats.style.format({
            'trip_count': '{:,.0f}',
            'avg_fare': '${:.2f}',
            'avg_tip': '${:.2f}',
            'trips_pct': '{:.1f}%'
        }),
        use_container_width=True
    )
    
    st.subheader("🏆 Top 5 Zones")
    top_zones = zone_agg.nlargest(5, 'trip_count')[['Zone', 'trip_count', 'avg_fare']]
    for idx, row in top_zones.iterrows():
        st.metric(
            label=row['Zone'],
            value=f"{row['trip_count']:,.0f} trips",
            delta=f"${row['avg_fare']:.2f} avg fare"
        )

st.markdown("---")

col_hour, col_day = st.columns(2)

with col_hour:
    st.subheader("⏰ Hourly Trip Distribution")
    hourly = filtered.groupby('hour')['trip_count'].sum().reset_index()
    fig = px.bar(hourly, x='hour', y='trip_count', 
                 title="Trips by Hour of Day",
                 labels={'hour': 'Hour (0-23)', 'trip_count': 'Total Trips'},
                 color='trip_count',
                 color_continuous_scale='Viridis')
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_day:
    st.subheader("📅 Weekly Pattern")
    daily = filtered.groupby('day_name')['trip_count'].sum().reset_index()
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily['day_name'] = pd.Categorical(daily['day_name'], categories=day_order, ordered=True)
    daily = daily.sort_values('day_name')
    
    fig = px.line(daily, x='day_name', y='trip_count', 
                  markers=True, title="Trips by Day of Week",
                  labels={'day_name': '', 'trip_count': 'Total Trips'})
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

col_congestion, col_monthly = st.columns(2)

with col_congestion:
    st.subheader("🏙️ Congestion Pricing Impact")
    
    fee_hour = filtered.groupby('hour')['total_congestion_fee'].sum().reset_index()
    fig = px.area(fee_hour, x='hour', y='total_congestion_fee',
                  title="Total Congestion Fees by Hour",
                  labels={'hour': 'Hour', 'total_congestion_fee': 'Total Fees ($)'},
                  color_discrete_sequence=['#FF6B6B'])
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Zones with Highest Congestion Fees")
    top_congestion = zone_agg.nlargest(10, 'total_congestion_fee')[['Zone', 'total_congestion_fee', 'trip_count']]
    fig = px.bar(top_congestion, x='total_congestion_fee', y='Zone', 
                 orientation='h', title="Top 10 Zones by Congestion Fees",
                 labels={'total_congestion_fee': 'Total Congestion Fees ($)', 'Zone': ''})
    st.plotly_chart(fig, use_container_width=True)

with col_monthly:
    st.subheader("📈 Monthly Trends 2025")
    monthly = filtered.groupby('month').agg({
        'trip_count': 'sum',
        'avg_fare': 'mean',
        'total_congestion_fee': 'sum'
    }).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['trip_count'], 
                             mode='lines+markers', name='Total Trips',
                             line=dict(color='blue', width=2)))
    fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['total_congestion_fee'], 
                             mode='lines+markers', name='Congestion Fees',
                             line=dict(color='red', width=2), yaxis='y2'))
    
    fig.update_layout(
        title="Monthly Comparison",
        xaxis=dict(title="Month", tickmode='linear', tick0=1, dtick=1),
        yaxis=dict(title="Total Trips", side='left'),
        yaxis2=dict(title="Congestion Fees ($)", overlaying='y', side='right'),
        legend=dict(x=0.02, y=0.98)
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

st.subheader("💰 Fare Analysis by Zone")
col_fare1, col_fare2 = st.columns(2)

with col_fare1:
    high_fare_zones = zone_agg[zone_agg['trip_count'] > 1000].nlargest(10, 'avg_fare')[['Zone', 'avg_fare', 'trip_count']]
    fig = px.bar(high_fare_zones, x='avg_fare', y='Zone', 
                 orientation='h', title="Highest Average Fare Zones (>1000 trips)",
                 labels={'avg_fare': 'Average Fare ($)', 'Zone': ''},
                 color='avg_fare', color_continuous_scale='Reds')
    st.plotly_chart(fig, use_container_width=True)

with col_fare2:
    zone_agg['tip_percentage'] = (zone_agg['avg_tip'] / zone_agg['avg_fare'] * 100).fillna(0)
    high_tip_zones = zone_agg[zone_agg['trip_count'] > 1000].nlargest(10, 'tip_percentage')[['Zone', 'tip_percentage', 'trip_count']]
    fig = px.bar(high_tip_zones, x='tip_percentage', y='Zone', 
                 orientation='h', title="Highest Tip Percentage Zones",
                 labels={'tip_percentage': 'Tip (% of fare)', 'Zone': ''},
                 color='tip_percentage', color_continuous_scale='Greens')
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("📊 Data source: NYC TLC Yellow Taxi Trip Records 2025 | Dashboard shows aggregated zone-hour data")
st.caption(f"🗺️ Total zones shown: {len(zone_agg)} | Total trips in filtered period: {total_trips:,}")