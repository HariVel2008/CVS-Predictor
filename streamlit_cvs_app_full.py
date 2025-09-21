import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
from fpdf import FPDF
import tempfile

# -----------------------------
# Config
# -----------------------------
MAPPING_FILE = "google_forms_mapping.json"
PDF_FILE = "CVS_Report.pdf"

STANDARD_COLUMNS = [
    "timestamp", "consent", "age_group", "age", "sex", "grade_level",
    "hours_academic", "hours_non_academic", "devices", "break_frequency",
    "screen_tools", "screen_tools_details", "eye_strain", "blurry_vision",
    "dry_eyes", "headaches", "neck_pain", "symptoms_worse", "lighting",
    "posture", "twenty_rule", "eye_level_screen", "visited_specialist",
    "impact_schoolwork", "mitigation_measures", "school_support_opinion"
]

# -----------------------------
# Functions
# -----------------------------
def load_mapping():
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_mapping(mapping):
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4)
    st.success(f"✅ Mapping saved to {MAPPING_FILE}")

def reset_mapping():
    if os.path.exists(MAPPING_FILE):
        os.remove(MAPPING_FILE)
        st.warning("⚠ Mapping reset — please remap on next upload.")

def map_google_forms(df):
    saved_mapping = load_mapping()
    if saved_mapping:
        st.info(f"ℹ️ Using saved mapping from {MAPPING_FILE}")
        return df.rename(columns=saved_mapping)

    st.subheader("🔧 Map Google Forms Columns")
    mapping = {}
    for std_col in STANDARD_COLUMNS:
        options = ["-- skip --"] + list(df.columns)
        choice = st.selectbox(f"Select column for: {std_col}", options)
        if choice != "-- skip --":
            mapping[choice] = std_col

    if st.button("Save Mapping"):
        save_mapping(mapping)
        return df.rename(columns=mapping)

    return df

def calculate_risk(row):
    score = 0
    try:
        hours = float(row.get("hours_academic", 0)) + float(row.get("hours_non_academic",0))
    except:
        hours = 0
    score += min(hours*10,50)  # max 50 points for hours

    symptoms = ["eye_strain","blurry_vision","dry_eyes","headaches","neck_pain"]
    symptom_count = sum([1 for s in symptoms if str(row.get(s,"No")).lower() in ["yes","sometimes"]])
    score += symptom_count*10  # 0-50 points

    if score < 30:
        risk = "Low"
    elif score < 60:
        risk = "Medium"
    else:
        risk = "High"
    return score, risk

def generate_charts(df):
    charts = {}
    # Symptoms frequency
    symptom_cols = ["eye_strain","blurry_vision","dry_eyes","headaches","neck_pain"]
    symptom_counts = {col: (df[col].str.lower() == "yes").sum() for col in symptom_cols}
    fig1, ax1 = plt.subplots()
    ax1.bar(symptom_counts.keys(), symptom_counts.values(), color='skyblue')
    ax1.set_title("Symptoms Frequency")
    ax1.set_ylabel("Count")
    charts['symptoms'] = fig1

    # Device usage pie
    device_counts = df['devices'].value_counts()
    fig2, ax2 = plt.subplots()
    ax2.pie(device_counts.values, labels=device_counts.index, autopct='%1.1f%%', startangle=90)
    ax2.set_title("Device Usage")
    charts['devices'] = fig2

    # Break frequency vs symptom count
    if 'break_frequency' in df.columns:
        fig3, ax3 = plt.subplots()
        df['break_frequency_numeric'] = df['break_frequency'].apply(lambda x: 0 if pd.isna(x) else int(str(x).replace('+','').replace('times','').strip()))
        df['symptom_score'] = df.apply(lambda r: sum([1 for s in symptom_cols if str(r.get(s,"No")).lower()=="yes"]), axis=1)
        ax3.scatter(df['break_frequency_numeric'], df['symptom_score'], color='green')
        ax3.set_xlabel("Break Frequency (per hour)")
        ax3.set_ylabel("Number of Symptoms")
        ax3.set_title("Break Frequency vs Symptoms")
        charts['breaks'] = fig3
    return charts

def generate_pdf(df, charts):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0,10,"Computer Vision Syndrome Survey Report", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0,10,"Summary Statistics:", ln=True)
    pdf.set_font("Arial","",11)
    try:
        avg_acad = df['hours_academic'].astype(float).mean()
        avg_nonacad = df['hours_non_academic'].astype(float).mean()
        pdf.cell(0,8,f"Average Academic Hours: {avg_acad:.2f}", ln=True)
        pdf.cell(0,8,f"Average Non-Academic Hours: {avg_nonacad:.2f}", ln=True)
    except:
        pdf.cell(0,8,"Average hours not available", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial","B",12)
    pdf.cell(0,10,"Student Risk Summary:", ln=True)
    pdf.set_font("Arial","",11)
    for i,row in df.iterrows():
        score, risk = calculate_risk(row)
        name = row.get("timestamp", f"Row {i+1}")
        pdf.cell(0,8,f"{name}: Score={score}, Risk={risk}", ln=True)

    for key, fig in charts.items():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            fig.savefig(tmpfile.name, bbox_inches='tight')
            pdf.add_page()
            pdf.set_font("Arial","B",12)
            pdf.cell(0,10,f"{key.capitalize()} Chart", ln=True)
            pdf.image(tmpfile.name, x=15, w=180)
            plt.close(fig)

    pdf.output(PDF_FILE)
    st.success(f"✅ PDF report generated: {PDF_FILE}")
    st.download_button("📥 Download PDF Report", PDF_FILE)

def analyze_data(df):
    st.subheader("📊 Data Preview")
    st.dataframe(df.head())
    df[['risk_score','risk_level']] = df.apply(lambda r: pd.Series(calculate_risk(r)), axis=1)
    st.subheader("📌 Risk Summary")
    st.dataframe(df[['timestamp','risk_score','risk_level']])
    charts = generate_charts(df)
    for key, fig in charts.items():
        st.pyplot(fig)
    generate_pdf(df, charts)

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("👀 Computer Vision Syndrome Survey App")

mode = st.radio("Select input mode:", ["Real-time Entry", "Google Forms CSV Upload"])

if mode == "Real-time Entry":
    st.subheader("📝 Enter Survey Response")
    response = {}
    for col in STANDARD_COLUMNS:
        response[col] = st.text_input(f"{col}:")
    if st.button("Submit Response"):
        st.success("✅ Response submitted!")
        df = pd.DataFrame([response])
        analyze_data(df)

elif mode == "Google Forms CSV Upload":
    st.subheader("📤 Upload Google Forms CSV")
    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
    if st.button("⚠ Reset Mapping"):
        reset_mapping()
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        df = map_google_forms(df)
        analyze_data(df)

