import streamlit as st
import pandas as pd
import sqlite3
import os
import urllib.parse
from datetime import datetime
from io import BytesIO
from PIL import Image

# --- CONFIGURACIÓN ---
st.set_page_config(
    page_title="Control de Seguridad Digital",
    layout="wide",
    page_icon="🛡️"
)

# --- ESTILOS ---
st.markdown("""
<style>
body { background-color: #F4F6F9; }

.main-title {
    font-size: 32px;
    font-weight: 700;
    color: white;
    background: linear-gradient(90deg, #0E4667, #1C7ED6);
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 25px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E4667, #1C7ED6);
}
[data-testid="stSidebar"] * {
    color: white !important;
}

.stButton>button {
    width: 100%;
    border-radius: 8px;
    background: linear-gradient(90deg, #1C7ED6, #0E4667);
    color: white;
}
</style>
""", unsafe_allow_html=True)

# --- DB ---
DB_NAME = "gestion_seguridad.db"
UPLOAD_DIR = "evidencias"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS gestiones
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  equipo TEXT, usuario TEXT, fecha_reporte TEXT, 
                  captura_path TEXT, fecha_atencion TEXT, 
                  comentarios TEXT)''')
    conn.commit()
    conn.close()

def update_full_db(id_reg, f_atencion, comentario, nuevo_path=None):
    conn = sqlite3.connect(DB_NAME)
    if nuevo_path:
        conn.execute("UPDATE gestiones SET fecha_atencion=?, comentarios=?, captura_path=? WHERE id=?", 
                  (f_atencion, comentario, nuevo_path, id_reg))
    else:
        conn.execute("UPDATE gestiones SET fecha_atencion=?, comentarios=? WHERE id=?", 
                  (f_atencion, comentario, id_reg))
    conn.commit()
    conn.close()

def delete_record(id_reg):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM gestiones WHERE id=?", (id_reg,))
    conn.commit()
    conn.close()

# --- EXPORTACIÓN ---
def exportar_excel_pro(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
        workbook, worksheet = writer.book, writer.sheets['Reporte']

        worksheet.set_column('A:D', 15)
        worksheet.set_column('F:G', 30)

        max_w = 20
        for i, path in enumerate(df['captura_path']):
            row = i + 1
            if path and os.path.exists(path):
                with Image.open(path) as img:
                    w_px, h_px = img.size

                scale = 400 / h_px if h_px > 400 else 1.0
                worksheet.set_row(row, h_px * scale * 0.75)

                w_chars = (w_px * scale) / 7
                if w_chars > max_w:
                    max_w = min(w_chars, 100)

                worksheet.insert_image(row, 4, path,
                    {'x_scale': scale, 'y_scale': scale})

                worksheet.write(row, 4, "")

        worksheet.set_column(4, 4, max_w)

    return output.getvalue()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## 🛡️ Panel de Control")
    st.markdown("---")
    opcion = st.radio(
        "Seleccione Operación:",
        ["GESTIÓN DE VULNERABILIDADES TÉCNICAS",
         "GESTIÓN DE ...",
         "GESTION DE..."]
    )

# --- TÍTULO ---
st.markdown('<div class="main-title">🛡️ CONTROLES DE SEGURIDAD DIGITAL</div>', unsafe_allow_html=True)

# --- CONTENIDO ---
if opcion == "GESTIÓN DE VULNERABILIDADES TÉCNICAS":

    init_db()

    col_izq, col_der = st.columns([1, 2.2])

    # -------- IZQUIERDA --------
    with col_izq:
        st.markdown("### 📝 Registro")

        with st.form("nuevo", clear_on_submit=True):
            eq = st.text_input("Equipo")
            us = st.text_input("Usuario")
            f_r = st.date_input("Fecha Reporte", datetime.now())
            evid = st.file_uploader("Evidencia", type=['png', 'jpg'])

            if st.form_submit_button("💾 Guardar"):
                if eq and us:
                    p = os.path.abspath(os.path.join(
                        UPLOAD_DIR,
                        f"{eq}_{datetime.now().strftime('%H%M%S')}.png"
                    )) if evid else ""

                    if evid:
                        with open(p, "wb") as f:
                            f.write(evid.getbuffer())

                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("""
                        INSERT INTO gestiones 
                        (equipo, usuario, fecha_reporte, captura_path, fecha_atencion, comentarios)
                        VALUES (?,?,?,?,?,?)
                    """, (eq, us, f_r.strftime("%Y-%m-%d"), p, "", ""))
                    conn.commit()
                    conn.close()

                    st.success("Guardado ✅")
                    st.rerun()

        # Dashboard
        st.markdown("### 📊 Dashboard")

        conn = sqlite3.connect(DB_NAME)
        df_dash = pd.read_sql_query("SELECT * FROM gestiones", conn)
        conn.close()

        if not df_dash.empty:
            total = len(df_dash)
            atendidos = df_dash[df_dash["fecha_atencion"] != ""].shape[0]
            pendientes = df_dash[df_dash["fecha_atencion"] == ""].shape[0]

            d1, d2, d3 = st.columns(3)
            d1.metric("Total", total)
            d2.metric("Atendidos", atendidos)
            d3.metric("Pendientes", pendientes)

            st.bar_chart(pd.DataFrame({
                "Estado": ["Atendidos", "Pendientes"],
                "Cantidad": [atendidos, pendientes]
            }).set_index("Estado"))
        else:
            st.info("Sin datos")

    # -------- DERECHA --------
    with col_der:
        st.markdown("### 📋 Seguimiento")

        conn = sqlite3.connect(DB_NAME)
        df_db = pd.read_sql_query("SELECT * FROM gestiones", conn)
        conn.close()

        if not df_db.empty:

            for _, row in df_db.iterrows():

                estado = "🟢 Atendido" if row['fecha_atencion'] else "🔴 Pendiente"

                with st.expander(f"{row['equipo']} | {row['usuario']} | {estado}"):

                    c1, c2, c3, c4 = st.columns([1.5, 2, 1, 1.2])

                    with c1:
                        if row['captura_path']:
                            st.image(row['captura_path'], use_container_width=True)

                        nueva_img = st.file_uploader("Actualizar", key=f"img_{row['id']}")

                    with c2:
                        st.text_input("Fecha Reporte", value=row['fecha_reporte'], disabled=True, key=f"fr_{row['id']}")
                        f_at = st.text_input("Fecha Atención", value=row['fecha_atencion'], key=f"f_{row['id']}")
                        com = st.text_area("Comentarios", value=row['comentarios'], key=f"c_{row['id']}")

                        if st.button("Guardar", key=f"b_{row['id']}"):
                            update_full_db(row['id'], f_at, com)
                            st.rerun()

                    with c3:
                        if st.button("Eliminar", key=f"del_{row['id']}"):
                            delete_record(row['id'])
                            st.rerun()

                    #  CORREO SIN RECARGA
                    with c4:
                        asunto = f"Actualizar sistema operativo - {row['equipo']}"
                        cuerpo = f"""Estimados Señores,

Por medio del presente, me dirijo a ustedes para solicitar su apoyo en la actualización del sistema operativo del siguiente equipo, de Windows 10 a Windows 11.

Esta solicitud se origina debido a que Microsoft ha finalizado el soporte y las actualizaciones de seguridad para Windows 10, tal como se indica en la referencia adjunta.

Saludos cordiales.
"""

                        mail_url = f"mailto:yaliaga@mincetur.gob.pe?subject={urllib.parse.quote(asunto)}&body={urllib.parse.quote(cuerpo)}"

                        st.markdown(f"""
                            <a href="{mail_url}" target="_blank">
                                <button style="
                                    width: 100%;
                                    padding: 8px;
                                    border-radius: 8px;
                                    border: none;
                                    background: linear-gradient(90deg, #28a745, #218838);
                                    color: white;
                                    font-weight: 600;
                                    cursor: pointer;">
                                    📧 Enviar Correo
                                </button>
                            </a>
                        """, unsafe_allow_html=True)

            st.divider()

            excel = exportar_excel_pro(df_db)
            st.download_button("📥 Descargar Excel", excel, "reporte.xlsx")

        else:
            st.info("No hay datos")

elif opcion == "GESTIÓN DE ...":
    st.subheader("Próximamente...")

elif opcion == "GESTION DE...":
    st.subheader("Próximamente...")