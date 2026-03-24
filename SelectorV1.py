
import math
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Selector y Diseñador AISC", layout="wide")

CSV_FILE = "AISC Shapes Database v13 (Estructurada) (1).csv"

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

DEFAULT_FY = 50.0
DEFAULT_E = 29000.0

st.title("Buscador y verificador AISC")

csv_path = Path(CSV_FILE)
if not csv_path.exists():
    st.error(f"No se encontró el archivo CSV: {CSV_FILE}")
    st.stop()


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=1)
    df.columns = df.columns.str.strip()
    return df


def normalize_label(value: str) -> str:
    return (
        str(value)
        .strip()
        .upper()
        .replace("×", "X")
        .replace(" ", "")
    )


def to_float(value, default=None):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def first_existing_value(row: pd.Series, candidates: list[str]):
    for col in candidates:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                return val
    return pd.NA


def fmt_num(value, ndigits=3):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "None"
    try:
        v = float(value)
        if abs(v) >= 1000 or (abs(v) > 0 and abs(v) < 0.001):
            return f"{v:.3e}"
        return f"{v:.{ndigits}f}"
    except Exception:
        return str(value)


def build_property_dict(row: pd.Series) -> dict:
    props = {}
    for label, candidates in PROPERTY_MAP:
        val = first_existing_value(row, candidates)
        props[label] = None if pd.isna(val) else val
    return props


def build_text_output(props: dict) -> str:
    lines = []
    for label, _ in PROPERTY_MAP:
        lines.append(f"{label} : {props.get(label)}")
    return "\n".join(lines)


def get_shape_type(row: pd.Series) -> str:
    return str(row.get("TYPE", "")).strip().upper()


def get_relevant_ratio_names(shape_type: str) -> list[str]:
    if shape_type.startswith("HSS"):
        return ["b/t", "h/tw", "d/t"]
    if shape_type.startswith("PIPE"):
        return ["d/t"]
    if shape_type.startswith("L"):
        return ["b/t", "h/t", "d/t"]
    if shape_type.startswith("2L"):
        return ["b/t", "h/t", "d/t", "bf/2tf", "h/tw"]
    if shape_type.startswith(("W", "HP", "S", "M", "MC", "WT", "C", "ST")):
        return ["bf/2tf", "h/tw", "b/t"]
    return ["bf/2tf", "b/t", "h/tw", "h/t", "d/t"]


def get_ratio_value(props: dict, ratio_name: str):
    return to_float(props.get(ratio_name), None)


def local_slenderness_checks(props: dict, shape_type: str, fy: float, e_mod: float, coeffs: dict):
    relevant = get_relevant_ratio_names(shape_type)
    checks = []
    q_components = []

    for ratio_name in relevant:
        actual = get_ratio_value(props, ratio_name)
        if actual is None or actual <= 0:
            continue

        if ratio_name == "bf/2tf":
            coeff = coeffs["flange"]
            element = "Patín"
        elif ratio_name == "h/tw":
            coeff = coeffs["web"]
            element = "Alma"
        elif ratio_name in ("b/t", "h/t", "d/t"):
            if shape_type.startswith("HSS"):
                coeff = coeffs["hss"]
                element = "HSS / pared"
            elif shape_type.startswith("L"):
                coeff = coeffs["angle"]
                element = "Ángulo"
            elif shape_type.startswith("PIPE"):
                coeff = coeffs["pipe"]
                element = "Tubo / Pipe"
            else:
                coeff = coeffs["generic"]
                element = "Elemento"
        else:
            coeff = coeffs["generic"]
            element = "Elemento"

        limit = coeff * math.sqrt(e_mod / fy) if fy > 0 else None
        slender = bool(limit is not None and actual > limit)
        q_component = 1.0 if not slender else max(0.05, min(1.0, limit / actual))
        q_components.append(q_component)

        checks.append({
            "elemento": element,
            "ratio_name": ratio_name,
            "actual": actual,
            "limit": limit,
            "slender": slender,
            "q_component": q_component,
        })

    q_auto = min(q_components) if q_components else 1.0
    return checks, q_auto


def effective_compression_q(props: dict, shape_type: str, fy: float, e_mod: float, coeffs: dict, q_override_enabled: bool, q_override: float):
    checks, q_auto = local_slenderness_checks(props, shape_type, fy, e_mod, coeffs)
    q_used = q_override if q_override_enabled else q_auto
    q_used = max(0.05, min(1.0, q_used))
    return checks, q_auto, q_used


def compute_column_capacity(props: dict, shape_type: str, inputs: dict, coeffs: dict):
    ag = to_float(props.get("A"), None)
    rx = to_float(props.get("r_x"), None)
    ry = to_float(props.get("r_y"), None)

    fx = inputs["fy"]
    e = inputs["e"]
    q_override_enabled = inputs["use_q_override"]
    q_override = inputs["q_override"]

    checks, q_auto, q_used = effective_compression_q(props, shape_type, fx, e, coeffs, q_override_enabled, q_override)

    klx_ft = inputs["kx"] * inputs["lx"]
    kly_ft = inputs["ky"] * inputs["ly"]

    klr_x = (klx_ft * 12.0 / rx) if rx and rx > 0 else None
    klr_y = (kly_ft * 12.0 / ry) if ry and ry > 0 else None
    klr = None
    if klr_x is not None and klr_y is not None:
        klr = max(klr_x, klr_y)
    elif klr_x is not None:
        klr = klr_x
    elif klr_y is not None:
        klr = klr_y

    pu = inputs["pu"]
    fe = (math.pi ** 2 * e / (klr ** 2)) if klr and klr > 0 else None
    lim = (4.71 * math.sqrt(e / (q_used * fx))) if (q_used > 0 and fx > 0) else None

    if fe is None:
        fcr = None
    else:
        if lim is not None and klr <= lim:
            fcr = q_used * ((0.658 ** (q_used * fx / fe)) * fx)
        else:
            fcr = 0.877 * fe

    phi_c = 0.90
    phi_pn = (phi_c * fcr * ag) if (fcr is not None and ag is not None) else None
    efficiency = (pu / phi_pn * 100.0) if (pu is not None and phi_pn not in (None, 0)) else None
    passes = bool(phi_pn is not None and pu is not None and phi_pn >= pu)

    details = {
        "Ag": ag,
        "rx": rx,
        "ry": ry,
        "KLx_ft": klx_ft,
        "KLy_ft": kly_ft,
        "KLr_x": klr_x,
        "KLr_y": klr_y,
        "KLr": klr,
        "Fe": fe,
        "Lim": lim,
        "Fcr": fcr,
        "phiPn": phi_pn,
        "efficiency_pct": efficiency,
        "passes": passes,
        "q_auto": q_auto,
        "q_used": q_used,
        "q_checks": checks,
    }
    return details


def compute_bending_x(props: dict, inputs: dict):
    fy = inputs["fy"]
    e = inputs["e"]
    cb = inputs["cb"]
    lb_ft = inputs["lb"]
    z_x = to_float(props.get("Zx"), None)
    s_x = to_float(props.get("Sx"), None)
    i_y = to_float(props.get("Iy"), None)
    j = to_float(props.get("J"), None)
    c_w = to_float(props.get("C"), None)
    if c_w is None:
        c_w = to_float(props.get("CW"), None)
    r_y = to_float(props.get("r_y"), None)
    d = to_float(props.get("d"), None)
    tf = to_float(props.get("tf"), None)

    phi_b = 0.90
    mp = fy * z_x if z_x is not None else None
    h_o = max((d - tf), 0.0) if (d is not None and tf is not None) else None

    if i_y is not None and c_w not in (None, 0) and s_x not in (None, 0):
        r_ts = math.sqrt(math.sqrt(i_y * c_w) / s_x)
    else:
        r_ts = r_y

    lp = 1.76 * r_y * math.sqrt(e / fy) if (r_y is not None and fy > 0) else None
    if r_ts is not None and s_x not in (None, 0) and h_o not in (None, 0) and j is not None:
        term = j / (s_x * h_o)
        lr = 1.95 * r_ts * (e / (0.7 * fy)) * math.sqrt(term + math.sqrt(term ** 2 + 6.76 * (0.7 * fy / e) ** 2))
    else:
        lr = None

    lb_in = lb_ft * 12.0
    if mp is None or s_x is None:
        mn = None
        zone = "Sin datos"
    else:
        if lp is None or lb_in <= lp:
            mn = mp
            zone = "Zona 1 (Fluencia)"
        elif lr is not None and lb_in <= lr:
            mn = cb * (mp - (mp - 0.7 * fy * s_x) * ((lb_in - lp) / (lr - lp)))
            zone = "Zona 2 (LTB inelástico)"
        else:
            # aproximación elástica
            if r_ts is not None and r_ts > 0:
                fe = (math.pi ** 2 * e) / ((lb_in / r_ts) ** 2)
                mn = cb * 0.877 * fe * s_x
            else:
                mn = cb * mp
            zone = "Zona 3 (LTB elástico)"

    phi_mn = (phi_b * mn / 12.0) if mn is not None else None
    mu = inputs["mu_x"]
    passes = bool(phi_mn is not None and mu is not None and phi_mn >= mu)
    ratio = (mu / phi_mn * 100.0) if (mu is not None and phi_mn not in (None, 0)) else None
    return {
        "Zx": z_x,
        "Sx": s_x,
        "Iy": i_y,
        "J": j,
        "Cw": c_w,
        "r_ts": r_ts,
        "Mp_kipin": mp,
        "Lp_in": lp,
        "Lr_in": lr,
        "Lb_in": lb_in,
        "Mn_kipin": mn,
        "phiMn_kipft": phi_mn,
        "zone": zone,
        "passes": passes,
        "util_pct": ratio,
    }


def compute_bending_y(props: dict, inputs: dict):
    fy = inputs["fy"]
    z_y = to_float(props.get("Zy"), None)
    s_y = to_float(props.get("Sy"), None)
    phi_b = 0.90
    mn = fy * z_y if z_y is not None else None
    phi_mn = (phi_b * mn / 12.0) if mn is not None else None
    mu = inputs["mu_y"]
    passes = bool(phi_mn is not None and mu is not None and phi_mn >= mu)
    ratio = (mu / phi_mn * 100.0) if (mu is not None and phi_mn not in (None, 0)) else None
    return {
        "Zy": z_y,
        "Sy": s_y,
        "Mn_kipin": mn,
        "phiMn_kipft": phi_mn,
        "passes": passes,
        "util_pct": ratio,
    }


def compute_biaxial(props: dict, inputs: dict, x_result: dict, y_result: dict):
    mux = inputs["mu_x"]
    muy = inputs["mu_y"]
    phix = x_result["phiMn_kipft"]
    phiy = y_result["phiMn_kipft"]
    if mux is None or muy is None or phix in (None, 0) or phiy in (None, 0):
        inter = None
        passes = False
    else:
        inter = mux / phix + muy / phiy
        passes = inter <= 1.0
    return {"interaction": inter, "passes": passes}


def compute_deflection(props: dict, inputs: dict):
    ix = to_float(props.get("Ix"), None)
    l_ft = inputs["l_service"]
    w_serv = inputs["cm"] + inputs["cv"]
    denom = inputs["defl_denom"]
    if l_ft is None or ix is None or denom is None or denom <= 0:
        return {"Ireq": None, "delta_max": None, "passes": False, "util_pct": None}
    delta_max_in = (l_ft * 12.0) / denom
    # formula user's note: x1728 converts ft^4 to in^4 while keeping w in kip/ft and L in ft
    ireq = (5.0 * w_serv * (l_ft ** 4) / (384.0 * inputs["e"] * delta_max_in)) * 1728.0
    passes = ix >= ireq
    util = (ireq / ix * 100.0) if ix not in (None, 0) else None
    return {
        "Ireq": ireq,
        "delta_max": delta_max_in,
        "passes": passes,
        "util_pct": util,
        "Ix": ix,
    }


def calc_direct_uniform_loads(inputs: dict):
    cm = inputs["cm"]
    cv = inputs["cv"]
    wu = 1.2 * cm + 1.6 * cv
    ws = cm + cv
    mux = (wu * inputs["l_span"] ** 2 / 8.0) if inputs["l_span"] is not None else None
    vux = (wu * inputs["l_span"] / 2.0) if inputs["l_span"] is not None else None
    return {"wu": wu, "ws": ws, "mux": mux, "vux": vux}


df = load_data(str(csv_path))
df["AISC_MANUAL_LABEL"] = df["AISC_MANUAL_LABEL"].astype(str)
df["AISC_NORM"] = df["AISC_MANUAL_LABEL"].map(normalize_label)
df["TYPE"] = df["TYPE"].astype(str).str.strip().str.upper()

st.caption("Busca, selecciona el perfil y luego revisa compresión, flexión y servicio con las propiedades del CSV.")

with st.sidebar:
    st.header("Filtros")
    type_options = sorted([t for t in df["TYPE"].dropna().unique().tolist() if t and t != "NAN"])
    selected_types = st.multiselect("Tipo de perfil", type_options, default=[])

filtered_df = df.copy()
if selected_types:
    filtered_df = filtered_df[filtered_df["TYPE"].isin(selected_types)]

shape_options = filtered_df["AISC_MANUAL_LABEL"].dropna().astype(str).drop_duplicates().tolist()
shape_options = sorted(shape_options, key=lambda x: normalize_label(x))

if not shape_options:
    st.warning("No hay perfiles con el filtro actual.")
    st.stop()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 Selección y datos")

    query = st.selectbox(
        "Selecciona una sección",
        shape_options,
        index=None,
        placeholder="Empieza a escribir aquí..."
    )

    st.markdown("### Material")
    fy = st.number_input("F_y (ksi)", min_value=1.0, value=DEFAULT_FY, step=1.0)
    e_mod = st.number_input("E (ksi)", min_value=1000.0, value=DEFAULT_E, step=100.0)

    st.markdown("### Compresión")
    cm = st.number_input("CM", value=0.0, step=0.5, help="Carga muerta en kips")
    cv = st.number_input("CV", value=0.0, step=0.5, help="Carga viva en kips")
    kx = st.number_input("Kx", value=1.0, step=0.05)
    ky = st.number_input("Ky", value=1.0, step=0.05)
    lx = st.number_input("Lx (ft)", value=0.0, step=0.5)
    ly = st.number_input("Ly (ft)", value=0.0, step=0.5)

    st.markdown("### Flexión")
    l_span = st.number_input("L / claro (ft)", value=0.0, step=0.5)
    lb = st.number_input("Lb (ft)", value=0.0, step=0.5)
    cb = st.number_input("Cb", value=1.0, step=0.05)
    mu_x_direct = st.number_input("Mu_x directo (kip-ft)", value=0.0, step=1.0)
    mu_y_direct = st.number_input("Mu_y directo (kip-ft)", value=0.0, step=1.0)

    st.markdown("### Servicio")
    defl_denom = st.number_input("Límite de flecha (denominador)", value=360.0, step=10.0)

    st.markdown("### Q local")
    use_q_override = st.checkbox("Usar Q manual", value=False)
    q_override = st.number_input("Q manual", value=1.0, min_value=0.05, max_value=1.0, step=0.05)
    c_flange = st.number_input("Coef. patín", value=0.56, step=0.01)
    c_web = st.number_input("Coef. alma", value=1.49, step=0.01)
    c_hss = st.number_input("Coef. HSS", value=1.40, step=0.01)
    c_angle = st.number_input("Coef. ángulo", value=0.45, step=0.01)
    c_generic = st.number_input("Coef. genérico", value=0.56, step=0.01)

with col2:
    st.subheader("📌 Perfil seleccionado")
    if query:
        row_match = filtered_df[filtered_df["AISC_MANUAL_LABEL"] == query]
        if row_match.empty:
            st.warning("No se encontró el perfil seleccionado con el filtro actual.")
            st.stop()
        row = row_match.iloc[0]
        props = build_property_dict(row)
        shape_type = get_shape_type(row)

        st.write(f"**AISC_MANUAL_LABEL:** {row['AISC_MANUAL_LABEL']}")
        st.write(f"**TYPE:** {shape_type}")
        st.code(build_text_output(props), language="text")

        inputs = {
            "fy": fy,
            "e": e_mod,
            "cm": cm,
            "cv": cv,
            "kx": kx,
            "ky": ky,
            "lx": lx,
            "ly": ly,
            "l_span": l_span,
            "lb": lb,
            "cb": cb,
            "mu_x": mu_x_direct if mu_x_direct > 0 else None,
            "mu_y": mu_y_direct if mu_y_direct > 0 else None,
            "l_service": l_span if l_span > 0 else None,
            "defl_denom": defl_denom,
            "pu": (1.2 * cm + 1.6 * cv) if (cm is not None and cv is not None) else None,
            "use_q_override": use_q_override,
            "q_override": q_override,
        }

        coeffs = {
            "flange": c_flange,
            "web": c_web,
            "hss": c_hss,
            "angle": c_angle,
            "pipe": c_hss,
            "generic": c_generic,
        }

        loads = calc_direct_uniform_loads(inputs)

        # If direct moments are not supplied, derive a conservative estimate from uniform load for simple span
        if inputs["mu_x"] is None and loads["mux"] is not None and loads["mux"] > 0:
            inputs["mu_x"] = loads["mux"]
        if inputs["mu_y"] is None:
            inputs["mu_y"] = 0.0

        col_res = compute_column_capacity(props, shape_type, inputs, coeffs)
        bx_res = compute_bending_x(props, inputs)
        by_res = compute_bending_y(props, inputs)
        biax_res = compute_biaxial(props, inputs, bx_res, by_res)
        defl_res = compute_deflection(props, inputs)

        st.markdown("### Resumen rápido")
        summary_cols = st.columns(4)
        summary_cols[0].metric("Pu", fmt_num(inputs["pu"], 2), "kips")
        summary_cols[1].metric("φPn", fmt_num(col_res["phiPn"], 2), "kips")
        summary_cols[2].metric("φMn x", fmt_num(bx_res["phiMn_kipft"], 2), "kip-ft")
        summary_cols[3].metric("Ireq", fmt_num(defl_res["Ireq"], 2), "in^4")

        with st.expander("Detalles de cargas"):
            st.write(f"**w_u** = 1.2CM + 1.6CV = {fmt_num(loads['wu'], 3)} kips/ft")
            st.write(f"**w_serv** = CM + CV = {fmt_num(loads['ws'], 3)} kips/ft")
            st.write(f"**Mux** estimado = {fmt_num(loads['mux'], 3)} kip-ft")
            st.write(f"**Vux** estimado = {fmt_num(loads['vux'], 3)} kips")

        with st.expander("Compresión"):
            st.write(f"**A_g** = {fmt_num(col_res['Ag'], 3)} in²")
            st.write(f"**KLx** = {fmt_num(col_res['KLx_ft'], 3)} ft")
            st.write(f"**KLy** = {fmt_num(col_res['KLy_ft'], 3)} ft")
            st.write(f"**(KL/r)x** = {fmt_num(col_res['KLr_x'], 3)}")
            st.write(f"**(KL/r)y** = {fmt_num(col_res['KLr_y'], 3)}")
            st.write(f"**Q auto** = {fmt_num(col_res['q_auto'], 3)}")
            st.write(f"**Q usado** = {fmt_num(col_res['q_used'], 3)}")
            st.write(f"**F_e** = {fmt_num(col_res['Fe'], 3)} ksi")
            st.write(f"**Límite** = {fmt_num(col_res['Lim'], 3)}")
            st.write(f"**F_cr** = {fmt_num(col_res['Fcr'], 3)} ksi")
            st.write(f"**φP_n** = {fmt_num(col_res['phiPn'], 3)} kips")
            st.write(f"**Eficiencia** = {fmt_num(col_res['efficiency_pct'], 2)} %")
            st.success("Cumple compresión" if col_res["passes"] else "No cumple compresión")

            if col_res["q_checks"]:
                q_df = pd.DataFrame(col_res["q_checks"])
                q_df["actual"] = q_df["actual"].map(lambda x: fmt_num(x, 3))
                q_df["limit"] = q_df["limit"].map(lambda x: fmt_num(x, 3))
                q_df["q_component"] = q_df["q_component"].map(lambda x: fmt_num(x, 3))
                st.dataframe(q_df, use_container_width=True, hide_index=True)

        with st.expander("Flexión eje X"):
            st.write(f"**Zx** = {fmt_num(bx_res['Zx'], 3)} in³")
            st.write(f"**Sx** = {fmt_num(bx_res['Sx'], 3)} in³")
            st.write(f"**r_ts** = {fmt_num(bx_res['r_ts'], 3)} in")
            st.write(f"**Mp** = {fmt_num(bx_res['Mp_kipin'], 3)} kip-in")
            st.write(f"**Lp** = {fmt_num(bx_res['Lp_in'], 3)} in")
            st.write(f"**Lr** = {fmt_num(bx_res['Lr_in'], 3)} in")
            st.write(f"**Lb** = {fmt_num(bx_res['Lb_in'], 3)} in")
            st.write(f"**Zona** = {bx_res['zone']}")
            st.write(f"**Mn** = {fmt_num(bx_res['Mn_kipin'], 3)} kip-in")
            st.write(f"**φM_nx** = {fmt_num(bx_res['phiMn_kipft'], 3)} kip-ft")
            st.write(f"**Utilización** = {fmt_num(bx_res['util_pct'], 2)} %")
            st.success("Cumple flexión X" if bx_res["passes"] else "No cumple flexión X")

        with st.expander("Flexión eje Y"):
            st.write(f"**Zy** = {fmt_num(by_res['Zy'], 3)} in³")
            st.write(f"**Sy** = {fmt_num(by_res['Sy'], 3)} in³")
            st.write(f"**φM_ny** = {fmt_num(by_res['phiMn_kipft'], 3)} kip-ft")
            st.write(f"**Utilización** = {fmt_num(by_res['util_pct'], 2)} %")
            st.success("Cumple flexión Y" if by_res["passes"] else "No cumple flexión Y")

        with st.expander("Interacción biaxial"):
            st.write(f"**Mux** = {fmt_num(inputs['mu_x'], 3)} kip-ft")
            st.write(f"**Muy** = {fmt_num(inputs['mu_y'], 3)} kip-ft")
            st.write(f"**φM_nx** = {fmt_num(bx_res['phiMn_kipft'], 3)} kip-ft")
            st.write(f"**φM_ny** = {fmt_num(by_res['phiMn_kipft'], 3)} kip-ft")
            st.write(f"**Interacción** = {fmt_num(biax_res['interaction'], 3)}")
            st.success("Cumple interacción" if biax_res["passes"] else "No cumple interacción")

        with st.expander("Servicio / deflexión"):
            st.write(f"**I_x** = {fmt_num(defl_res['Ix'], 3)} in⁴")
            st.write(f"**Δ_max** = {fmt_num(defl_res['delta_max'], 3)} in")
            st.write(f"**I_req** = {fmt_num(defl_res['Ireq'], 3)} in⁴")
            st.write(f"**Utilización** = {fmt_num(defl_res['util_pct'], 2)} %")
            st.success("Cumple servicio" if defl_res["passes"] else "No cumple servicio")

        st.markdown("### Conclusión")
        conclusion_lines = []
        conclusion_lines.append(f"Compresión: {'Cumple' if col_res['passes'] else 'No cumple'}")
        conclusion_lines.append(f"Flexión X: {'Cumple' if bx_res['passes'] else 'No cumple'}")
        conclusion_lines.append(f"Flexión Y: {'Cumple' if by_res['passes'] else 'No cumple'}")
        conclusion_lines.append(f"Biaxial: {'Cumple' if biax_res['passes'] else 'No cumple'}")
        conclusion_lines.append(f"Servicio: {'Cumple' if defl_res['passes'] else 'No cumple'}")
        st.code("\n".join(conclusion_lines), language="text")

    else:
        st.info("Selecciona una sección para ver las propiedades y correr la verificación.")

st.markdown("---")
st.subheader("Base de datos completa")
with st.expander("Ver CSV completo"):
    st.dataframe(df.drop(columns=["AISC_NORM"]), use_container_width=True, height=450)
