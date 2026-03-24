import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Buscador AISC", layout="wide")

CSV_FILE = "AISC Shapes Database v13 (Estructurada) (1).csv"

PROPERTY_MAP = [
    ("W", ["W"]), ("A", ["A"]), ("Wno", ["WNO"]), ("Ix", ["IX"]),
    ("Iy", ["IY"]), ("J", ["J"]), ("Sw", ["SW"]),
    ("Zx", ["ZX"]), ("Sx", ["SX"]), ("Zy", ["ZY"]), ("Sy", ["SY"]),
    ("C", ["C"]), ("Qf", ["QF"]), ("Qw", ["QW"]),
    ("Ca", ["CA", "AW"]),
    ("d", ["D"]), ("ht", ["HT"]), ("iam_ex", ["OD"]),
    ("bf", ["BF"]), ("b", ["B"]), ("iam_in", ["ID"]),
    ("tw", ["TW"]), ("tf", ["TF"]), ("t", ["T"]),
    ("t_nom", ["TNOM"]), ("t_des", ["TDES"]),
    ("k_des", ["KDES"]), ("k_det", ["KDET"]), ("k1", ["K1"]),
    ("x_m", ["X"]), ("y_m", ["Y"]), ("e_0", ["E0"]),
    ("x_p", ["XP"]), ("y_p", ["YP"]),
    ("r_x", ["RX"]), ("r_y", ["RY"]), ("r_z", ["RZ"]), ("r_0", ["RO"]),
    ("bf/2tf", ["BF_2TF"]), ("b/t", ["B_T"]),
    ("h/tw", ["H_TW"]), ("h/t", ["H_T"]), ("d/t", ["D_T"]),
]

@st.cache_data
def load_data(csv_path: str) -> pd.DataFrame:
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
    return pd.NA

# 🔹 TABLA MATRIZ (derecha)
def build_matrix_table(row: pd.Series, group_size=11) -> pd.DataFrame:
    props = []
    values = []
    
    for label, candidates in PROPERTY_MAP:
        props.append(label)
        values.append(first_existing_value(row, candidates))

    rows = []
    for i in range(0, len(props), group_size):
        rows.append(props[i:i+group_size])
        rows.append(values[i:i+group_size])

    max_len = max(len(r) for r in rows)
    rows = [r + [""]*(max_len - len(r)) for r in rows]

    return pd.DataFrame(rows)

# 🔹 TEXTO PLANO (izquierda)
def build_text_output(row: pd.Series) -> str:
    lines = []
    for label, candidates in PROPERTY_MAP:
        val = first_existing_value(row, candidates)
        if pd.isna(val):
            val = None
        lines.append(f"{label} : {val}")
    return "\n".join(lines)

# ================= UI =================

st.title("Buscador de secciones AISC")

csv_path = Path(CSV_FILE)
if not csv_path.exists():
    st.error(f"No se encontró el archivo CSV: {CSV_FILE}")
    st.stop()

df = load_data(str(csv_path))

col1, col2 = st.columns([1, 2])

# 🔹 IZQUIERDA
with col1:
    st.subheader("🔍 Búsqueda")
    query = st.text_input("AISC_MANUAL_LABEL")

# 🔹 DERECHA
with col2:
    st.subheader("📊 Tabla de propiedades")

if query:
    q = normalize_label(query)
    mask = df["AISC_MANUAL_LABEL"].astype(str).map(normalize_label) == q
    matches = df.loc[mask]

    if matches.empty:
        st.warning("No se encontró esa sección.")
    else:
        row = matches.iloc[0]

        # IZQUIERDA → TEXTO
        with col1:
            st.markdown(f"### {row['AISC_MANUAL_LABEL']}")
            st.write(f"Tipo: {row.get('TYPE', '')}")

            text_output = build_text_output(row)
            st.code(text_output, language="text")

            st.download_button(
                "📥 Descargar TXT",
                data=text_output,
                file_name=f"{row['AISC_MANUAL_LABEL']}.txt",
                mime="text/plain"
            )

        # DERECHA → MATRIZ
        with col2:
            matrix_table = build_matrix_table(row)

            st.dataframe(
                matrix_table.style.set_properties(**{
                    "text-align": "center",
                    "font-size": "12px"
                }),
                use_container_width=True
            )

# 🔹 CSV abajo
st.markdown("---")
st.subheader("📁 Base de datos completa")

with st.expander("Ver CSV completo"):
    st.dataframe(df, use_container_width=True)