import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Buscador AISC", layout="wide")

CSV_FILE = "AISC Shapes Database v13 (Estructurada) (1).csv"

# Orden y nombres de salida
PROPERTY_MAP = [
    ("W", ["W"]),
    ("A", ["A"]),
    ("Wno", ["WNO"]),
    ("Ix", ["IX"]),
    ("Iy", ["IY"]),
    ("J", ["J"]),
    ("Sw", ["SW"]),
    ("Zx", ["ZX"]),
    ("Sx", ["SX"]),
    ("Zy", ["ZY"]),
    ("Sy", ["SY"]),
    ("C", ["C"]),
    ("Qf", ["QF"]),
    ("Qw", ["QW"]),
    ("Ca", ["CA", "AW"]),
    ("d", ["D"]),
    ("ht", ["HT"]),
    ("iam_ex", ["OD"]),
    ("bf", ["BF"]),
    ("b", ["B"]),
    ("iam_in", ["ID"]),
    ("tw", ["TW"]),
    ("tf", ["TF"]),
    ("t", ["T"]),
    ("t_nom", ["TNOM"]),
    ("t_des", ["TDES"]),
    ("k_des", ["KDES"]),
    ("k_det", ["KDET"]),
    ("k1", ["K1"]),
    ("x_m", ["X"]),
    ("y_m", ["Y"]),
    ("e_0", ["E0"]),
    ("x_p", ["XP"]),
    ("y_p", ["YP"]),
    ("r_x", ["RX"]),
    ("r_y", ["RY"]),
    ("r_z", ["RZ"]),
    ("r_0", ["RO"]),
    ("bf/2tf", ["BF_2TF"]),
    ("b/t", ["B_T"]),
    ("h/tw", ["H_TW"]),
    ("h/t", ["H_T"]),
    ("d/t", ["D_T"]),
]

@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
    # El archivo tiene una fila extra antes de los encabezados reales
    df = pd.read_csv(csv_path, header=1)
    df.columns = df.columns.str.strip()
    return df

def normalize_label(value: str) -> str:
    return str(value).strip().upper().replace("×", "X").replace(" ", "")

def first_existing_value(row: pd.Series, candidates: list[str]):
    for col in candidates:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                return val
    return None

def build_text_output(row: pd.Series) -> str:
    lines = []
    for label, candidates in PROPERTY_MAP:
        val = first_existing_value(row, candidates)
        lines.append(f"{label} : {val}")
    return "\n".join(lines)

def build_horizontal_table(row: pd.Series) -> pd.DataFrame:
    data = []
    for label, candidates in PROPERTY_MAP:
        data.append((label, first_existing_value(row, candidates)))
    out = pd.DataFrame(data, columns=["Prop.", "Valor"]).set_index("Prop.")
    return out

st.title("Buscador de secciones AISC")

csv_path = Path(CSV_FILE)
if not csv_path.exists():
    st.error(f"No se encontró el archivo CSV: {CSV_FILE}")
    st.stop()

df = load_data(str(csv_path))

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 Búsqueda")
    st.caption("Ej: W10X49, W14X34, C10X30, L3X3X3/16")
    query = st.text_input("AISC_MANUAL_LABEL")

    if query:
        q = normalize_label(query)
        mask = df["AISC_MANUAL_LABEL"].astype(str).map(normalize_label) == q
        matches = df.loc[mask]

        if matches.empty:
            st.warning("No se encontró esa sección.")
        else:
            row = matches.iloc[0]
            st.markdown(f"### {row['AISC_MANUAL_LABEL']}")
            st.write(f"Tipo: {row.get('TYPE', '')}")

            text_output = build_text_output(row)
            st.code(text_output, language="text")

            st.download_button(
                label="📥 Descargar TXT",
                data=text_output,
                file_name=f"{row['AISC_MANUAL_LABEL']}.txt",
                mime="text/plain",
            )
    else:
        st.info("Escribe una sección para ver sus propiedades.")

with col2:
    st.subheader("📊 Tabla de propiedades")
    if query:
        q = normalize_label(query)
        mask = df["AISC_MANUAL_LABEL"].astype(str).map(normalize_label) == q
        matches = df.loc[mask]

        if matches.empty:
            st.info("Sin resultados para mostrar.")
        else:
            row = matches.iloc[0]
            result_table = build_horizontal_table(row)
            st.dataframe(result_table, use_container_width=True, height=900)
    else:
        st.info("Aquí aparecerá la tabla cuando busques una sección.")

st.markdown("---")
st.subheader("📁 Base de datos completa")

with st.expander("Ver CSV completo"):
    st.dataframe(df, use_container_width=True)