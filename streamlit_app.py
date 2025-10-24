import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings # FIX: Explicitly import warnings to prevent KeyError

# CONFIGURATION
st.set_page_config(
    page_title="Dog Bite Analytics Portfolio",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CACHED DATA LOADING AND CLEANING
@st.cache_data
def load_and_clean_data(file_path):
    # Load the dataset
    df = pd.read_csv(file_path)

    # Date Conversion and Feature Creation (using explicit format)
    date_cols = ['Incident Date', 'Date Reported ']
    date_format = '%Y %b %d %I:%M:%S %p'

    for col in date_cols:
        df[col] = pd.to_datetime(df[col], format=date_format, errors='coerce')
        
    # NEW FEATURE: Report Delay (Days)
    df['Report Delay (Days)'] = (df['Date Reported '] - df['Incident Date']).dt.days
    df['Report Delay (Days)'] = df['Report Delay (Days)'].apply(lambda x: max(0, x))

    # NEW FEATURES: Time-based features
    df['Day of Week'] = df['Incident Date'].dt.day_name()
    df['Incident Hour'] = df['Incident Date'].dt.hour
    df['Incident Year'] = df['Incident Date'].dt.year

    def categorize_time(hour):
        if 5 <= hour < 12: return 'Morning'
        elif 12 <= hour < 17: return 'Afternoon'
        elif 17 <= hour < 21: return 'Evening'
        else: return 'Night'

    df['Time of Day'] = df['Incident Hour'].apply(categorize_time)
    df.drop(columns=['Incident Hour'], inplace=True, errors='ignore')

    # Victim Age Cleaning
    df['Victim Age'] = pd.to_numeric(
        df['Victim Age'].astype(str).str.extract(r'(\d+)')[0],
        errors='coerce'
    )
    median_age = df['Victim Age'].median()
    df['Victim Age'] = df['Victim Age'].fillna(median_age).astype(int)

    # Incident Location Extraction
    df['Incident Location'] = df['Incident Location'].fillna('')
    df['City'] = df['Incident Location'].apply(
        lambda x: x.split(',')[0].strip().split(' ')[-1] if ',' in x else 'UNKNOWN'
    )
    df['State'] = df['Incident Location'].str.extract(r'(\s[A-Z]{2}\s|\s[A-Z]{2}\d{5})')
    df['State'] = df['State'].str.strip().str[:2].fillna('UNKNOWN') 
    df.drop(columns=['Incident Location'], inplace=True, errors='ignore')

    # Text Standardization and Imputation
    text_cols = ['Victim Relationship', 'Bite Location', 'Bite Severity', 'Bite Circumstance', 'Controlled By', 'Bite Type']
    for col in text_cols:
        df[col] = df[col].astype(str).str.upper().str.strip().replace('NAN', 'UNKNOWN')
        
    # Treatment Cost and Final Review
    df['Treatment Cost'] = df['Treatment Cost'].fillna(0)
    df = df.dropna(subset=['Incident Date'])
    
    # Create Age Groups (matching Power BI logic)
    def create_age_group(age):
        if age <= 5: return "1_Child (0-5)"
        elif age <= 12: return "2_Child (6-12)"
        elif age <= 17: return "3_Teen (13-17)"
        elif age <= 35: return "4_Young Adult (18-35)"
        elif age <= 60: return "5_Adult (36-60)"
        else: return "6_Senior (61+)"
    df['Victim Age Group'] = df['Victim Age'].apply(create_age_group)

    # Rename columns for display consistency
    df.columns = [col.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_') for col in df.columns]
    df = df.rename(columns={'Incident_Date': 'Incident_Date', 'Date_Reported_': 'Date_Reported'})

    return df.copy()

# Load the data, assuming the file path based on previous interaction
try:
    df_raw = load_and_clean_data("Dog_Bite_Dataset.csv")
    df = df_raw.copy()
except FileNotFoundError:
    st.error("Error: 'Dog_Bite_Dataset.csv' not found. Please ensure the file is uploaded.")
    st.stop()


# UTILITY FUNCTIONS
def get_kpi_value(df_filtered, measure):
    """Calculates and formats KPI values."""
    if measure == 'Total_Incidents':
        return f"{len(df_filtered):,}"
    elif measure == 'Avg_Victim_Age':
        avg = df_filtered['Victim_Age'].mean()
        return f"{avg:.1f} Yrs" if not pd.isna(avg) else "N/A"
    elif measure == 'Total_Cost':
        cost = df_filtered['Treatment_Cost'].sum()
        return f"${cost:,.0f}"
    elif measure == 'Avg_Report_Delay':
        delay = df_filtered['Report_Delay_Days'].mean()
        return f"{delay:.1f} Days" if not pd.isna(delay) else "N/A"
    return "N/A"

# PAGE DEFINITIONS
def page_executive_summary(df_filtered):
    st.title("Executive Summary: Scope and Trends")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    # KPI Strip
    with col1:
        st.metric("Total Incidents", get_kpi_value(df_filtered, 'Total_Incidents'))
    with col2:
        st.metric("Avg Victim Age", get_kpi_value(df_filtered, 'Avg_Victim_Age'))
    with col3:
        st.metric("Total Cost", get_kpi_value(df_filtered, 'Total_Cost'))
    with col4:
        st.metric("Avg Report Delay", get_kpi_value(df_filtered, 'Avg_Report_Delay'))

    st.markdown("---")
    
    # Incident Trend Over Time (Line Chart)
    st.subheader("Monthly Incident Trend")
    df_trend = df_filtered.copy()
    df_trend['Month_Year'] = df_trend['Incident_Date'].dt.to_period('M').astype(str)
    
    monthly_counts = df_trend.groupby('Month_Year').size().reset_index(name='Incidents')
    
    fig_trend = px.line(
        monthly_counts, 
        x='Month_Year', 
        y='Incidents', 
        title='Monthly Dog Bite Incidents',
        labels={'Incidents': 'Number of Incidents', 'Month_Year': 'Month'},
        markers=True
    )
    fig_trend.update_layout(xaxis_tickangle=-45, height=400)
    st.plotly_chart(fig_trend, use_container_width=True)

    # Peak Activity Heatmap (Day vs Time)
    st.subheader("Peak Activity: Day of Week vs. Time of Day")
    
    # Define order for time categories
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    time_order = ['Morning', 'Afternoon', 'Evening', 'Night']
    
    df_heatmap = df_filtered.groupby(['Day_of_Week', 'Time_of_Day']).size().reset_index(name='Count')
    
    # Ensure all combinations exist for the pivot
    df_pivot = df_heatmap.pivot_table(index='Day_of_Week', columns='Time_of_Day', values='Count').reindex(day_order).fillna(0)
    df_pivot = df_pivot[time_order] # Re-index columns based on time order

    fig_heatmap = px.imshow(
        df_pivot.values,
        x=df_pivot.columns,
        y=df_pivot.index,
        color_continuous_scale="Reds",
        labels=dict(x="Time of Day", y="Day of Week", color="Total Incidents"),
        aspect="auto"
    )
    fig_heatmap.update_xaxes(side="top")
    fig_heatmap.update_layout(height=450, coloraxis_showscale=True)
    st.plotly_chart(fig_heatmap, use_container_width=True)


def page_risk_profile(df_filtered):
    st.title("Risk Profile: Demographics and Circumstances")
    st.markdown("---")

    # Victim Age Distribution (Column Chart)
    st.subheader("Victim Age Distribution")
    df_age = df_filtered.groupby('Victim_Age_Group').size().reset_index(name='Incidents')
    # Use the sorting number in the group name for correct plotting order
    df_age['Victim_Age_Group_Clean'] = df_age['Victim_Age_Group'].str.split('_').str[1]
    
    fig_age = px.bar(
        df_age, 
        x='Victim_Age_Group_Clean', 
        y='Incidents', 
        labels={'Victim_Age_Group_Clean': 'Victim Age Group'},
        color='Incidents',
        color_continuous_scale='Tealgrn'
    )
    fig_age.update_layout(height=400)
    st.plotly_chart(fig_age, use_container_width=True)

    col_severity, col_circumstance = st.columns(2)

    # Severity by Relationship (Stacked Bar Chart)
    with col_severity:
        st.subheader("Severity by Relationship")
        df_sev = df_filtered.groupby(['Victim_Relationship', 'Bite_Severity']).size().reset_index(name='Count')
        
        # Filter out 'UNKNOWN' and take top 8 relationships for clarity
        top_relations = df_sev[df_sev['Victim_Relationship'] != 'UNKNOWN']['Victim_Relationship'].value_counts().nlargest(8).index
        df_sev = df_sev[df_sev['Victim_Relationship'].isin(top_relations)]

        fig_sev = px.bar(
            df_sev, 
            x='Victim_Relationship', 
            y='Count', 
            color='Bite_Severity', 
            title='Proportion of Bite Severity by Top Relationship',
            barmode='stack', 
            color_discrete_sequence=px.colors.sequential.Inferno
        )
        fig_sev.update_layout(height=450, xaxis_tickangle=-45)
        st.plotly_chart(fig_sev, use_container_width=True)

    # Circumstance Breakdown (Treemap)
    with col_circumstance:
        st.subheader("Top Incident Circumstances")
        df_circ = df_filtered[df_filtered['Bite_Circumstance'] != 'UNKNOWN'].groupby('Bite_Circumstance').size().reset_index(name='Count')
        df_circ = df_circ.nlargest(10, 'Count')

        fig_circ = px.treemap(
            df_circ, 
            path=['Bite_Circumstance'], 
            values='Count',
            title='Top 10 Circumstances',
            color_continuous_scale='blues'
        )
        fig_circ.update_layout(height=450)
        st.plotly_chart(fig_circ, use_container_width=True)


def page_geography_control(df_filtered):
    st.title("Geographical Impact and Control Analysis")
    st.markdown("---")

    col_map, col_rank = st.columns([2, 1])

    # Geographical Hotspot (Scatter Mapbox)
    with col_map:
        st.subheader("Incident Hotspots by City")
        
        df_geo = df_filtered[df_filtered['State'] != 'UNKNOWN'].groupby(['City', 'State']).size().reset_index(name='Incidents')
        
        # NOTE: Since we don't have lat/long, we'll plot a bar chart grouped by City/State instead of a true map, 
        # which is the most reliable representation without external API calls.
        df_top_cities = df_geo.sort_values('Incidents', ascending=False).head(15)
        df_top_cities['City_State'] = df_top_cities['City'] + ' (' + df_top_cities['State'] + ')'

        fig_geo = px.bar(
            df_top_cities, 
            y='City_State', 
            x='Incidents', 
            orientation='h',
            title='Top 15 Cities with Incidents',
            color='Incidents',
            color_continuous_scale='Plasma'
        )
        fig_geo.update_layout(yaxis={'categoryorder':'total ascending'}, height=550)
        st.plotly_chart(fig_geo, use_container_width=True)

    # City Ranking Table
    with col_rank:
        st.subheader("Top City Metrics")
        df_metrics = df_filtered.groupby(['City']).agg(
            Incidents=('Bite_Number', 'count'),
            Avg_Cost=('Treatment_Cost', 'mean'),
            Avg_Delay=('Report_Delay_Days', 'mean')
        ).reset_index()
        
        df_metrics = df_metrics.sort_values('Incidents', ascending=False).head(10)
        
        st.dataframe(
            df_metrics,
            column_order=['City', 'Incidents', 'Avg_Cost', 'Avg_Delay'],
            column_config={
                "Avg_Cost": st.column_config.NumberColumn("Avg Cost", format="$%.2f"),
                "Avg_Delay": st.column_config.NumberColumn("Avg Delay", format="%.1f days"),
            },
            hide_index=True,
            use_container_width=True
        )

    # Responsible Party Analysis
    st.subheader("Analysis of Responsible Party")
    df_control = df_filtered[df_filtered['Controlled_By'] != 'UNKNOWN'].groupby('Controlled_By').size().reset_index(name='Count')
    
    fig_control = px.pie(
        df_control, 
        values='Count', 
        names='Controlled_By',
        title='Proportion of Incidents by Controlling Party',
        color_discrete_sequence=px.colors.sequential.Agsunset,
    )
    st.plotly_chart(fig_control, use_container_width=True)

# SIDEBAR SETUP AND FILTER LOGIC
page_names_to_funcs = {
    "1. Executive Summary": page_executive_summary,
    "2. Risk Profile & Demographics": page_risk_profile,
    "3. Geography & Control": page_geography_control,
}

def setup_sidebar(df):
    
    # NAVIGATION
    st.sidebar.title("Dashboard Navigation")
    selected_page = st.sidebar.radio("Go to:", page_names_to_funcs.keys())
    
    # FILTERING OPTIONS
    st.sidebar.header("Filter Dashboard Data")
    
    # --- Time Filter Expander (Collapsible) ---
    with st.sidebar.expander("Time Range Selection", expanded=False):
        # Date Range Filter (Applied to the full dataset before other filters)
        min_date = df['Incident_Date'].min().to_pydatetime().date()
        max_date = df['Incident_Date'].max().to_pydatetime().date()
        date_range = st.slider(
            "Incident Date Range",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
            format="YYYY-MM-DD"
        )
    
    # Apply date filter immediately after slider definition
    df_filtered = df[(df['Incident_Date'].dt.date >= date_range[0]) & (df['Incident_Date'].dt.date <= date_range[1])].copy()
    
    # --- Categorical Filters Expander (Collapsible) ---
    with st.sidebar.expander("Categorical Filters", expanded=False):
        
        # Severity Filter (Dropdown Select All)
        severity_options = sorted(df_filtered['Bite_Severity'].unique())
        display_severity_options = ["All Categories"] + severity_options
        
        # Set default selection to include "All Categories"
        initial_default_severity = ["All Categories"]

        selected_severity = st.multiselect(
            "Bite Severity", 
            display_severity_options, 
            default=initial_default_severity
        )
        
        # Apply filtering logic based on selection
        if "All Categories" in selected_severity:
            final_severity_selection = severity_options
        else:
            final_severity_selection = selected_severity

        df_filtered = df_filtered[df_filtered['Bite_Severity'].isin(final_severity_selection)].copy()

        # Relationship Filter (Dropdown Select All)
        relationship_options = sorted(df_filtered['Victim_Relationship'].unique())
        display_relationship_options = ["All Categories"] + relationship_options
        
        # Set default selection to include "All Categories"
        initial_default_relationship = ["All Categories"]

        selected_relationship = st.multiselect(
            "Victim Relationship", 
            display_relationship_options, 
            default=initial_default_relationship
        )
        
        # Apply filtering logic based on selection
        if "All Categories" in selected_relationship:
            final_relationship_selection = relationship_options
        else:
            final_relationship_selection = selected_relationship

        df_filtered = df_filtered[df_filtered['Victim_Relationship'].isin(final_relationship_selection)]
    
    # FOOTER
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"Data Filtered: {len(df_filtered)} / {len(df)} Incidents")
    st.sidebar.markdown("Data Source: Dog Bite Data, City of Dallas Open Data Portal, Department of Public Safety")
    st.sidebar.markdown("***Built By: Anushka Sharma***")

    return df_filtered, selected_page


# --- MAIN APP LOGIC ---

# Add top level title
st.title("Dog Bite Incidents Analytics")

# Setup Sidebar and Apply Filters
df_filtered, selected_page = setup_sidebar(df)

# Run selected page function
page_names_to_funcs[selected_page](df_filtered)
