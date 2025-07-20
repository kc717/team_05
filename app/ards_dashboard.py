import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os

# Set page config
st.set_page_config(
    page_title="ARDS Patient Dashboard",
    page_icon="🫁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme aesthetic
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
    }
    .stSidebar {
        background-color: #1E2329;
    }
    .patient-info-card {
        background-color: #1E2329;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #2D3339;
    }
    .metric-card {
        background-color: #1E2329;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        border: 1px solid #2D3339;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #FAFAFA;
    }
    .metric-label {
        font-size: 14px;
        color: #8B949E;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🫁 ARDS Patient Dashboard")
st.caption("Visualizing respiratory support, interventions, and outcomes for ARDS patients")
st.markdown("---")

# Define data paths
DATA_PATH = '/Users/kavenchhikara/Desktop/projects/SCCM/SCCM-Team2/ards_analysis/data'

def create_patient_timeline(patient_ts, patient_static):
    """Create the main patient timeline visualization similar to the screenshot"""
    
    # Convert hours to days for display
    patient_ts['days_from_admission'] = patient_ts['hours_from_icu_admission'] / 24
    
    # Create the main figure
    fig = go.Figure()
    
    # Calculate P/F ratio or S/F ratio for respiratory status
    patient_ts['pf_ratio'] = pd.to_numeric(patient_ts['pao2'], errors='coerce') / pd.to_numeric(patient_ts['fio2_set'], errors='coerce')
    patient_ts['sf_ratio'] = pd.to_numeric(patient_ts['spo2'], errors='coerce') / pd.to_numeric(patient_ts['fio2_set'], errors='coerce')
    
    # Use P/F if available, otherwise S/F
    patient_ts['respiratory_ratio'] = patient_ts['pf_ratio'].fillna(patient_ts['sf_ratio'])
    
    # Plot P/F or S/F ratio (main line)
    ratio_data = patient_ts.dropna(subset=['respiratory_ratio', 'days_from_admission'])
    if len(ratio_data) > 0:
        fig.add_trace(go.Scatter(
            x=ratio_data['days_from_admission'],
            y=ratio_data['respiratory_ratio'],
            mode='lines+markers',
            name='S/F Ratio',
            line=dict(color='#FFFFFF', width=3),  # White line for visibility
            marker=dict(size=6, color='#FFFFFF', line=dict(color='#000000', width=1)),
            yaxis='y1'
        ))
    
    # Plot PEEP (secondary y-axis)
    peep_data = patient_ts.dropna(subset=['peep_set', 'days_from_admission'])
    peep_data['peep_numeric'] = pd.to_numeric(peep_data['peep_set'], errors='coerce')
    peep_data = peep_data.dropna(subset=['peep_numeric'])
    
    if len(peep_data) > 0:
        fig.add_trace(go.Scatter(
            x=peep_data['days_from_admission'],
            y=peep_data['peep_numeric'],
            mode='lines+markers',
            name='PEEP',
            line=dict(color='#00BFFF', width=3),  # Bright blue for visibility
            marker=dict(size=4, color='#00BFFF'),
            yaxis='y2',
            fill='tonexty',
            fillcolor='rgba(0,191,255,0.2)'
        ))
    
    # Add intervention markers
    add_intervention_markers(fig, patient_ts, patient_static)
    
    # Add critical thresholds for S/F ratio ARDS categories
    fig.add_hline(y=235, line_dash="dash", line_color="orange", annotation_text="S/F = 235 (Mild/Moderate ARDS)")
    fig.add_hline(y=148, line_dash="dash", line_color="red", annotation_text="S/F = 148 (Moderate/Severe ARDS)")
    
    # Calculate ICU discharge time for timeline
    icu_discharge_day = (patient_static.get('discharge_datetime') - patient_ts['icu_in_time'].iloc[0]).total_seconds() / (24 * 3600) if hasattr(patient_static.get('discharge_datetime'), 'total_seconds') else None
    if icu_discharge_day is None:
        # Use ICU LOS if discharge time calculation fails
        icu_discharge_day = patient_static.get('icu_los_days', 7)
    
    # Add discharge marker
    if icu_discharge_day and icu_discharge_day > 0:
        fig.add_vline(x=icu_discharge_day, line_dash="solid", line_color="green", 
                     annotation_text="ICU Discharge", annotation_position="top")
    
    # Configure layout with transparent background
    fig.update_layout(
        title=dict(
            text=f"Patient {patient_static['hospitalization_id']} - Respiratory Timeline",
            font=dict(size=24, color='white')
        ),
        xaxis=dict(
            title=dict(text="Time (days since ICU admission)", font=dict(color='white', size=24)),
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            gridwidth=1,
            tickfont=dict(color='white', size=14),
            range=[0, max(patient_ts['days_from_admission'].max(), icu_discharge_day, 7)]
        ),
        yaxis=dict(
            title=dict(text="S/F Ratio", font=dict(color='white', size=24)),
            side="left",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            gridwidth=1,
            tickfont=dict(color='white', size=14),
            range=[0, max(500, patient_ts['respiratory_ratio'].max() * 1.1) if patient_ts['respiratory_ratio'].notna().any() else 500]
        ),
        yaxis2=dict(
            title=dict(text="PEEP (cmH2O)", font=dict(color='white', size=24)),
            side="right",
            overlaying="y",
            range=[0, 25],
            showgrid=False,
            tickfont=dict(color='white', size=14)
        ),
        plot_bgcolor='rgba(0,0,0,0)',  # Transparent plot background
        paper_bgcolor='rgba(0,0,0,0)',  # Transparent paper background
        height=600,
        hovermode='x unified',
        legend=dict(
            x=0.02, 
            y=0.98,
            bgcolor='rgba(0,0,0,0.5)',
            bordercolor='white',
            borderwidth=1,
            font=dict(color='white', size=14)
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Additional summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        icu_days = patient_static.get('icu_los_days', 0)
        st.metric("ICU Days", f"{icu_days:.1f}")
    
    with col2:
        min_ratio = patient_ts['respiratory_ratio'].min() if patient_ts['respiratory_ratio'].notna().any() else 0
        st.metric("Lowest S/F", f"{min_ratio:.0f}")
    
    with col3:
        max_peep = peep_data['peep_numeric'].max() if len(peep_data) > 0 else 0
        st.metric("Peak PEEP", f"{max_peep:.1f}")
    
    with col4:
        nmb_hours = ((patient_ts[['cisatracurium_dose', 'vecuronium_dose', 'rocuronium_dose', 'atracurium_dose', 'pancuronium_dose']] > 0).any(axis=1)).sum()
        st.metric("NMB Hours", f"{nmb_hours}")

def add_intervention_markers(fig, patient_ts, patient_static):
    """Add intervention markers to the timeline"""
    
    # ARDS onset
    ards_onset_day = patient_ts['hours_from_ards_onset'].notna().any()
    if ards_onset_day:
        ards_day = patient_ts[patient_ts['hours_from_ards_onset'].notna()]['days_from_admission'].iloc[0]
        fig.add_vline(x=ards_day, line_dash="dot", line_color="#FFA500", line_width=3,
                     annotation=dict(text="ARDS Onset", font=dict(color="white", size=14)))
    
    # Proning events - check for both numeric 1 and string values "prone"/"Prone"
    if 'prone_flag' in patient_ts.columns:
        # Create a binary prone position flag
        patient_ts['prone_position_flag'] = 0
        
        # Check for numeric 1
        numeric_prone = pd.to_numeric(patient_ts['prone_flag'], errors='coerce') == 1
        
        # Check for string values "prone" or "Prone"
        string_prone = patient_ts['prone_flag'].astype(str).str.lower() == 'prone'
        
        # Combine both conditions
        patient_ts['prone_position_flag'] = (numeric_prone | string_prone).astype(int)
        
        # Get prone events
        prone_events = patient_ts[patient_ts['prone_position_flag'] == 1]
        
        if len(prone_events) > 0:
            prone_days = prone_events['days_from_admission'].tolist()
            fig.add_scatter(
                x=prone_days,
                y=[300] * len(prone_days),  # Fixed height for prone markers
                mode='markers',
                marker=dict(symbol='square', size=15, color='#00FF00', line=dict(color='white', width=2)),
                name='Prone Position',
                showlegend=True
            )
    
    # Neuromuscular blockade
    nmb_cols = ['cisatracurium_dose', 'vecuronium_dose', 'rocuronium_dose', 'atracurium_dose', 'pancuronium_dose']
    nmb_events = patient_ts[(patient_ts[nmb_cols] > 0).any(axis=1)]
    if len(nmb_events) > 0:
        nmb_days = nmb_events['days_from_admission'].tolist()
        fig.add_scatter(
            x=nmb_days,
            y=[350] * len(nmb_days),  # Fixed height for NMB markers
            mode='markers',
            marker=dict(symbol='diamond', size=12, color='#FF00FF', line=dict(color='white', width=2)),
            name='Neuromuscular Blockade',
            showlegend=True
        )
    
    # Tracheostomy
    trach_events = patient_ts[pd.to_numeric(patient_ts['new_tracheostomy'], errors='coerce') == 1]
    if len(trach_events) > 0:
        trach_day = trach_events['days_from_admission'].iloc[0]
        fig.add_vline(x=trach_day, line_dash="solid", line_color="#8A2BE2", line_width=3,
                     annotation=dict(text="Tracheostomy", font=dict(color="white", size=14)))

# Load data with caching
@st.cache_data
def load_data():
    """Load time series and static data, filter to ARDS patients only"""
    try:
        # Load time series data with engine specification
        ts_path = os.path.join(DATA_PATH, 'time_series_analysis_table.parquet')
        static_path = os.path.join(DATA_PATH, 'static_analysis_table.parquet')
        
        # Check if files exist
        if not os.path.exists(ts_path):
            st.error(f"Time series file not found at: {ts_path}")
            return None, None
        if not os.path.exists(static_path):
            st.error(f"Static file not found at: {static_path}")
            return None, None
            
        # Load with explicit engine
        ts_data = pd.read_parquet(ts_path, engine='pyarrow')
        static_data = pd.read_parquet(static_path, engine='pyarrow')
        
        # Convert datetime columns
        ts_data['recorded_dttm'] = pd.to_datetime(ts_data['recorded_dttm'])
        ts_data['icu_in_time'] = pd.to_datetime(ts_data['icu_in_time'])
        ts_data['ARDS_onset_dttm'] = pd.to_datetime(ts_data['ARDS_onset_dttm'])
        
        static_data['admission_datetime'] = pd.to_datetime(static_data['admission_datetime'])
        static_data['discharge_datetime'] = pd.to_datetime(static_data['discharge_datetime'])
        
        # Filter to ARDS patients only (those with ARDS onset time)
        ards_patients = ts_data[ts_data['ARDS_onset_dttm'].notna()]['hospitalization_id'].unique()
        ts_data_ards = ts_data[ts_data['hospitalization_id'].isin(ards_patients)].copy()
        static_data_ards = static_data[static_data['hospitalization_id'].isin(ards_patients)].copy()
        
        # Calculate time from ICU admission in hours for visualization
        ts_data_ards['hours_from_icu_admission'] = (
            ts_data_ards['recorded_dttm'] - ts_data_ards['icu_in_time']
        ).dt.total_seconds() / 3600
        
        # Calculate time from ARDS onset in hours
        ts_data_ards.loc[ts_data_ards['ARDS_onset_dttm'].notna(), 'hours_from_ards_onset'] = (
            ts_data_ards.loc[ts_data_ards['ARDS_onset_dttm'].notna(), 'recorded_dttm'] - 
            ts_data_ards.loc[ts_data_ards['ARDS_onset_dttm'].notna(), 'ARDS_onset_dttm']
        ).dt.total_seconds() / 3600
        
        return ts_data_ards, static_data_ards
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None, None

# Load data
ts_data, static_data = load_data()

if ts_data is not None and static_data is not None:
    # Sidebar for patient selection and static info
    with st.sidebar:
        st.header("Patient Selection")
        
        # Get unique hospitalization IDs
        hosp_ids = sorted(static_data['hospitalization_id'].unique())
        
        # Patient selector
        selected_hosp_id = st.selectbox(
            "Select Hospitalization ID:",
            options=hosp_ids,
            format_func=lambda x: f"Patient {x}"
        )
        
        # Get patient data
        patient_static = static_data[static_data['hospitalization_id'] == selected_hosp_id].iloc[0]
        patient_ts = ts_data[ts_data['hospitalization_id'] == selected_hosp_id].copy()
        patient_ts = patient_ts.sort_values('recorded_dttm')
        
        # Check if patient has ARDS
        has_ards = patient_ts['ARDS_onset_dttm'].notna().any()
        
        # ARDS flag indicator
        st.markdown("### ARDS Status")
        if has_ards:
            st.success("✓ ARDS Positive")
            ards_onset = patient_ts['ARDS_onset_dttm'].iloc[0]
            st.caption(f"Onset: {ards_onset.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("○ ARDS Negative")
        
        # Patient demographics - check available columns first
        st.markdown("### Patient Information")
        
        
        # Use safe get method for columns that might not exist
        age = patient_static.get('age_at_admission', 'N/A')
        sex = patient_static.get('sex', 'N/A')
        ethnicity = patient_static.get('ethnicity', patient_static.get('race', 'N/A'))
        admit_source = patient_static.get('hospital_admit_source', 'N/A')
        disposition = patient_static.get('disposition_category', 'N/A')
        
        st.markdown(f"""
        <div class="patient-info-card">
            <b>Age:</b> {age}<br>
            <b>Sex:</b> {sex}<br>
            <b>Ethnicity:</b> {ethnicity}<br>
            <b>Admit Source:</b> {admit_source}<br>
            <b>Disposition:</b> {disposition}
        </div>
        """, unsafe_allow_html=True)
        
        # Outcomes
        st.markdown("### Outcomes")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("ICU LOS", f"{patient_static['icu_los_days']:.1f} days")
        with col2:
            st.metric("Hospital LOS", f"{patient_static['hospital_los_days']:.1f} days")
        
        st.metric("VFD-28", f"{patient_static['ventilator_free_days_28']:.0f} days")
        
        if patient_static['mortality'] == 1:
            st.error("⚠️ Mortality: Yes")
        else:
            st.success("✓ Survived")
    
    # Main content area
    st.subheader(f"ARDS Patient {selected_hosp_id} - Timeline Visualization")
    
    # Data check
    if len(patient_ts) == 0:
        st.warning("No time series data available for this patient.")
    else:
        # Create the main timeline visualization
        create_patient_timeline(patient_ts, patient_static)
        
        # Show data preview
        with st.expander("📊 View Raw Data Sample"):
            st.dataframe(patient_ts.head(10))
        
else:
    st.error("Failed to load data. Please check the data files exist in the correct location.")