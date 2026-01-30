import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, timedelta
from io import BytesIO

# ============================================================================
# CONFIGURACIÓN INICIAL
# ============================================================================
st.set_page_config(
    page_title="Sistema de Auditoría",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# BASE DE DATOS
# ============================================================================
def get_connection():
    """Crea y retorna una conexión a la base de datos"""
    return sqlite3.connect('auditoria.db', check_same_thread=False)

def init_db():
    """Inicializa las tablas de la base de datos"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Tabla de usuarios
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        rol TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabla de items del checklist
    cur.execute('''
    CREATE TABLE IF NOT EXISTS checklist_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        item TEXT NOT NULL,
        puntaje_max INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabla de resultados de auditorías
    cur.execute('''
    CREATE TABLE IF NOT EXISTS checklist_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE NOT NULL,
        area TEXT NOT NULL,
        auditor TEXT NOT NULL,
        categoria TEXT NOT NULL,
        item TEXT NOT NULL,
        puntaje INTEGER NOT NULL,
        observacion TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar base de datos
init_db()

# ============================================================================
# UTILIDADES
# ============================================================================
def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def login_user(user, pwd):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (user, hash_pass(pwd))
        )
        return cur.fetchone()
    finally:
        conn.close()

def crear_usuarios_por_defecto():
    """Crea usuarios por defecto si no existen"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        usuarios_default = [
            ("admin", "admin123", "admin"),
            ("auditor", "auditor123", "auditor"),
            ("supervisor", "supervisor123", "supervisor")
        ]
        
        for username, password, rol in usuarios_default:
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (username, password, rol) VALUES (?, ?, ?)",
                    (username, hash_pass(password), rol)
                )
        
        conn.commit()
    finally:
        conn.close()

# Crear usuarios por defecto
crear_usuarios_por_defecto()

# ============================================================================
# MANEJO DE SESIÓN
# ============================================================================
if "login" not in st.session_state:
    st.session_state.login = False
    st.session_state.user = ""
    st.session_state.rol = ""
    st.session_state.current_page = "checklist"

# ============================================================================
# PÁGINA DE LOGIN
# ============================================================================
def mostrar_login():
    """Muestra la página de login"""
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Sistema de Auditoría")
        st.markdown("---")
        
        # Tarjetas de credenciales
        st.subheader("👤 Credenciales de Prueba")
        
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**👑 Administrador**")
                st.code("admin / admin123")
            with col2:
                st.markdown("**✅ Auditor**")
                st.code("auditor / auditor123")
            with col3:
                st.markdown("**👁️ Supervisor**")
                st.code("supervisor / supervisor123")
        
        st.markdown("---")
        
        # Formulario de login
        with st.form("login_form", border=True):
            st.subheader("Iniciar Sesión")
            
            user = st.text_input("👤 Usuario", placeholder="Ingrese su usuario")
            pwd = st.text_input("🔒 Contraseña", type="password", placeholder="Ingrese su contraseña")
            
            col1, col2 = st.columns([1, 1])
            with col2:
                submitted = st.form_submit_button("🚀 Ingresar", use_container_width=True, type="primary")
            
            if submitted:
                if user and pwd:
                    with st.spinner("🔍 Verificando credenciales..."):
                        data = login_user(user, pwd)
                        if data:
                            st.session_state.login = True
                            st.session_state.user = user
                            st.session_state.rol = data[3]
                            st.session_state.current_page = "checklist"
                            st.success(f"✅ ¡Bienvenido, {user}!")
                            st.rerun()
                        else:
                            st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.warning("⚠️ Complete todos los campos")

# ============================================================================
# BARRA LATERAL
# ============================================================================
def mostrar_sidebar():
    """Muestra la barra lateral con navegación"""
    
    with st.sidebar:
        # Logo y título
        st.markdown("""
        <div style="text-align: center;">
            <h1>✅</h1>
            <h3>Auditoría App</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Información del usuario
        rol_colors = {
            "admin": "#FF6B6B",
            "auditor": "#4ECDC4",
            "supervisor": "#FFD166"
        }
        rol_color = rol_colors.get(st.session_state.rol, "#95A5A6")
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, {rol_color}20 0%, {rol_color}10 100%);
                    padding: 15px;
                    border-radius: 10px;
                    border-left: 5px solid {rol_color};
                    margin: 10px 0;">
            <h4 style="margin: 0; color: {rol_color};">👤 {st.session_state.user}</h4>
            <p style="margin: 5px 0 0 0; color: #666;">{st.session_state.rol.upper()}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Menú de navegación
        st.markdown("### 🗺️ Navegación")
        
        # Definir páginas según rol
        if st.session_state.rol == "admin":
            menu_items = [
                {"icon": "📋", "name": "Checklist", "page": "checklist"},
                {"icon": "⚙️", "name": "Administrar Checklist", "page": "administrar"},
                {"icon": "📊", "name": "Histórico", "page": "historico"},
                {"icon": "📤", "name": "Exportar", "page": "exportar"},
                {"icon": "👥", "name": "Gestión de Usuarios", "page": "usuarios"}
            ]
        elif st.session_state.rol == "auditor":
            menu_items = [
                {"icon": "📋", "name": "Checklist", "page": "checklist"},
                {"icon": "📊", "name": "Histórico", "page": "historico"},
                {"icon": "📤", "name": "Exportar", "page": "exportar"}
            ]
        else:  # supervisor
            menu_items = [
                {"icon": "📊", "name": "Histórico", "page": "historico"},
                {"icon": "📤", "name": "Exportar", "page": "exportar"}
            ]
        
        # Botones de navegación
        for item in menu_items:
            if st.button(
                f"{item['icon']} {item['name']}",
                key=f"nav_{item['page']}",
                use_container_width=True,
                type="primary" if st.session_state.current_page == item['page'] else "secondary"
            ):
                st.session_state.current_page = item['page']
                st.rerun()
        
        st.markdown("---")
        
        # Botón de cerrar sesión
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ============================================================================
# PÁGINA: CHECKLIST
# ============================================================================
def pagina_checklist():
    """Página principal del checklist"""
    
    st.title("📋 Checklist de Auditoría")
    
    # Tarjeta informativa
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Auditor", st.session_state.user)
        with col2:
            st.metric("Rol", st.session_state.rol)
        with col3:
            st.metric("Fecha", datetime.now().strftime("%d/%m/%Y"))
    
    with st.form("auditoria_form", border=True):
        # Encabezado del formulario
        col1, col2 = st.columns(2)
        with col1:
            area = st.text_input(
                "📍 Área a auditar*",
                placeholder="Ej: Producción, Almacén, Calidad...",
                help="Especifique el área donde se realiza la auditoría"
            )
        with col2:
            fecha = st.date_input(
                "📅 Fecha de auditoría*",
                datetime.today(),
                help="Fecha en que se realiza la auditoría"
            )
        
        st.divider()
        
        # Obtener items del checklist
        conn = get_connection()
        try:
            items = pd.read_sql("SELECT * FROM checklist_items ORDER BY categoria", conn)
        finally:
            conn.close()
        
        if items.empty:
            st.warning("""
            ⚠️ **No hay ítems configurados en el checklist**
            
            Para comenzar a realizar auditorías, un administrador debe:
            1. Ir a **⚙️ Administrar Checklist**
            2. Agregar categorías e ítems
            3. Asignar puntajes máximos
            """)
            return
        
        total = 0
        max_total = items["puntaje_max"].sum()
        respuestas = []
        
        st.markdown("### 📝 Ítems de Auditoría")
        st.caption(f"📊 Total de ítems: {len(items)} | 🎯 Puntaje máximo posible: {max_total}")
        
        # Mostrar cada ítem agrupado por categoría
        categorias = items["categoria"].unique()
        
        for categoria in categorias:
            with st.expander(f"**{categoria}**", expanded=True):
                items_cat = items[items["categoria"] == categoria]
                
                for idx, row in items_cat.iterrows():
                    col1, col2, col3 = st.columns([6, 2, 4])
                    
                    with col1:
                        st.markdown(f"**{row['item']}**")
                        st.caption(f"🎯 Máximo: {row['puntaje_max']} puntos")
                    
                    with col2:
                        # Selectbox para puntaje
                        p = st.selectbox(
                            "Puntaje",
                            list(range(0, row["puntaje_max"] + 1)),
                            key=f"p_{row['id']}_{idx}",
                            label_visibility="collapsed"
                        )
                    
                    with col3:
                        obs = st.text_area(
                            "Observaciones",
                            key=f"o_{row['id']}_{idx}",
                            placeholder="Agregue observaciones si es necesario...",
                            height=60,
                            label_visibility="collapsed"
                        )
                    
                    respuestas.append((row, p, obs))
                    total += p
        
        st.divider()
        
        # Mostrar resultados
        porcentaje = round((total / max_total) * 100, 2) if max_total > 0 else 0
        
        # Tarjetas de resultados
        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.metric("🎯 Puntaje Obtenido", f"{total}/{max_total}")
        
        with col2:
            with st.container(border=True):
                st.metric("📈 Porcentaje", f"{porcentaje}%")
        
        with col3:
            with st.container(border=True):
                if porcentaje >= 90:
                    st.success(f"🟢 Excelente")
                    st.caption(f"{porcentaje}% Cumplimiento")
                elif porcentaje >= 70:
                    st.warning(f"🟡 Aceptable")
                    st.caption(f"{porcentaje}% Cumplimiento")
                else:
                    st.error(f"🔴 Crítico")
                    st.caption(f"{porcentaje}% Cumplimiento")
        
        # Botones de acción
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button(
                "💾 **Guardar Auditoría**",
                use_container_width=True,
                type="primary"
            )
        
        if submitted:
            if not area:
                st.error("❌ Debe especificar el área auditada")
            else:
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    
                    # Guardar cada respuesta
                    for r, p, obs in respuestas:
                        cur.execute("""
                        INSERT INTO checklist_results 
                        (fecha, area, auditor, categoria, item, puntaje, observacion)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fecha.strftime("%Y-%m-%d"),
                            area,
                            st.session_state.user,
                            r["categoria"],
                            r["item"],
                            p,
                            obs if obs else ""
                        ))
                    
                    conn.commit()
                    
                    # Mostrar mensaje de éxito
                    st.success(f"""
                    ✅ **Auditoría guardada exitosamente**
                    
                    **📍 Área:** {area}
                    **📅 Fecha:** {fecha.strftime('%d/%m/%Y')}
                    **👤 Auditor:** {st.session_state.user}
                    **📊 Resultado:** {porcentaje}% cumplimiento
                    """)
                    
                    # Mostrar botón para nueva auditoría
                    if st.button("🔄 Realizar otra auditoría", use_container_width=True):
                        st.rerun()
                    
                finally:
                    conn.close()

# ============================================================================
# PÁGINA: ADMINISTRAR CHECKLIST
# ============================================================================
def pagina_administrar():
    """Página de administración del checklist"""
    
    if st.session_state.rol != "admin":
        st.error("⛔ Acceso denegado. Solo administradores pueden acceder a esta sección.")
        return
    
    st.title("⚙️ Administrar Checklist")
    
    # Pestañas para diferentes funciones
    tab1, tab2, tab3 = st.tabs(["➕ Agregar Ítems", "📋 Ver Ítems", "✏️ Editar/Eliminar"])
    
    with tab1:
        st.subheader("Agregar Nuevo Ítem al Checklist")
        
        with st.form("agregar_item_form", border=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                categoria = st.text_input(
                    "📂 Categoría*",
                    placeholder="Ej: Seguridad, Calidad, Documentación...",
                    help="Grupo al que pertenece el ítem"
                )
            
            with col2:
                puntaje = st.number_input(
                    "🎯 Puntaje Máximo*",
                    min_value=1,
                    max_value=100,
                    value=5,
                    help="Puntaje máximo para este ítem"
                )
            
            item = st.text_area(
                "📝 Descripción del Ítem*",
                placeholder="Describa el punto a auditar...",
                height=100,
                help="Descripción detallada del ítem a evaluar"
            )
            
            col1, col2 = st.columns([3, 1])
            with col2:
                submitted = st.form_submit_button(
                    "➕ Agregar Ítem",
                    use_container_width=True,
                    type="primary"
                )
            
            if submitted:
                if categoria and item:
                    conn = get_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO checklist_items (categoria, item, puntaje_max)
                            VALUES (?, ?, ?)
                        """, (categoria, item, puntaje))
                        conn.commit()
                        st.success(f"✅ Ítem agregado a la categoría '{categoria}'")
                        st.rerun()
                    finally:
                        conn.close()
                else:
                    st.warning("⚠️ Complete todos los campos obligatorios (*)")
    
    with tab2:
        st.subheader("Ítems Actuales del Checklist")
        
        conn = get_connection()
        try:
            df = pd.read_sql("""
                SELECT categoria, item, puntaje_max 
                FROM checklist_items 
                ORDER BY categoria, item
            """, conn)
            
            if not df.empty:
                # Mostrar estadísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total Ítems", len(df))
                with col2:
                    st.metric("📂 Categorías", df["categoria"].nunique())
                with col3:
                    st.metric("🎯 Puntaje Total", df["puntaje_max"].sum())
                
                # Mostrar tabla con estilo
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "categoria": "📂 Categoría",
                        "item": "📝 Ítem",
                        "puntaje_max": "🎯 Puntaje Máx"
                    }
                )
                
                # Exportar a CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Descargar Checklist",
                    csv,
                    "checklist_items.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("ℹ️ No hay ítems en el checklist")
                
        finally:
            conn.close()
    
    with tab3:
        st.subheader("Editar o Eliminar Ítems")
        
        conn = get_connection()
        try:
            df = pd.read_sql("SELECT * FROM checklist_items ORDER BY categoria", conn)
            
            if not df.empty:
                # Seleccionar ítem a editar
                item_seleccionado = st.selectbox(
                    "🔍 Seleccionar ítem a modificar:",
                    df.apply(lambda x: f"{x['categoria']} - {x['item']}", axis=1)
                )
                
                # Obtener el ítem seleccionado
                selected_index = df.apply(
                    lambda x: f"{x['categoria']} - {x['item']}", axis=1
                ).tolist().index(item_seleccionado)
                
                selected_item = df.iloc[selected_index]
                
                # Formulario de edición
                with st.form("editar_item_form", border=True):
                    st.markdown(f"**✏️ Editando:** {selected_item['item']}")
                    
                    new_cat = st.text_input("📂 Categoría", value=selected_item["categoria"])
                    new_item = st.text_area("📝 Ítem", value=selected_item["item"], height=80)
                    new_puntaje = st.number_input(
                        "🎯 Puntaje Máximo",
                        value=int(selected_item["puntaje_max"]),
                        min_value=1,
                        max_value=100
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                            conn2 = get_connection()
                            try:
                                cur = conn2.cursor()
                                cur.execute("""
                                    UPDATE checklist_items 
                                    SET categoria=?, item=?, puntaje_max=?
                                    WHERE id=?
                                """, (new_cat, new_item, new_puntaje, selected_item["id"]))
                                conn2.commit()
                                st.success("✅ Cambios guardados")
                                st.rerun()
                            finally:
                                conn2.close()
                    
                    with col2:
                        if st.form_submit_button("🗑️ Eliminar Ítem", use_container_width=True, type="secondary"):
                            conn2 = get_connection()
                            try:
                                cur = conn2.cursor()
                                cur.execute("DELETE FROM checklist_items WHERE id=?", (selected_item["id"],))
                                conn2.commit()
                                st.success("✅ Ítem eliminado")
                                st.rerun()
                            finally:
                                conn2.close()
            else:
                st.info("ℹ️ No hay ítems para editar")
                
        finally:
            conn.close()

# ============================================================================
# PÁGINA: HISTÓRICO
# ============================================================================
def pagina_historico():
    """Muestra el histórico de auditorías"""
    
    st.title("📊 Histórico de Auditorías")
    
    # Obtener datos
    conn = get_connection()
    try:
        df = pd.read_sql("""
            SELECT fecha, area, auditor, categoria, item, puntaje, observacion 
            FROM checklist_results 
            ORDER BY fecha DESC
        """, conn)
    finally:
        conn.close()
    
    if df.empty:
        st.info("""
        📭 **No hay auditorías registradas**
        
        Para ver datos en el histórico, primero debe:
        1. Ir a **📋 Checklist**
        2. Realizar una auditoría
        3. Guardar los resultados
        """)
        return
    
    # Convertir fecha
    df["fecha"] = pd.to_datetime(df["fecha"])
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        areas = ["Todas"] + sorted(df["area"].unique().tolist())
        area_filtro = st.selectbox("📍 Área:", areas)
    
    with col2:
        fecha_min = df["fecha"].min().date()
        fecha_max = df["fecha"].max().date()
        
        rango_fechas = st.date_input(
            "📅 Rango de fechas:",
            [fecha_max - timedelta(days=30), fecha_max],
            min_value=fecha_min,
            max_value=fecha_max
        )
    
    with col3:
        auditores = ["Todos"] + sorted(df["auditor"].unique().tolist())
        auditor_filtro = st.selectbox("👤 Auditor:", auditores)
    
    # Aplicar filtros
    if area_filtro != "Todas":
        df = df[df["area"] == area_filtro]
    
    if len(rango_fechas) == 2:
        df = df[
            (df["fecha"].dt.date >= rango_fechas[0]) & 
            (df["fecha"].dt.date <= rango_fechas[1])
        ]
    
    if auditor_filtro != "Todos":
        df = df[df["auditor"] == auditor_filtro]
    
    if df.empty:
        st.warning("⚠️ No hay datos con los filtros seleccionados")
        return
    
    # Resumen estadístico
    st.subheader("📈 Resumen Estadístico")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Auditorías", df["fecha"].nunique())
    with col2:
        st.metric("📍 Áreas Auditadas", df["area"].nunique())
    with col3:
        st.metric("👤 Auditores", df["auditor"].nunique())
    with col4:
        st.metric("🎯 Puntaje Promedio", f"{df['puntaje'].mean():.1f}")
    
    # Tab detallada
    st.subheader("📋 Detalle de Auditorías")
    
    # Formatear dataframe para visualización
    df_display = df.copy()
    df_display["fecha"] = df_display["fecha"].dt.strftime("%d/%m/%Y")
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "fecha": "📅 Fecha",
            "area": "📍 Área",
            "auditor": "👤 Auditor",
            "categoria": "📂 Categoría",
            "item": "📝 Ítem",
            "puntaje": "🎯 Puntaje",
            "observacion": "📝 Observación"
        }
    )
    
    # Estadísticas por área
    st.subheader("📊 Estadísticas por Área")
    stats_area = df.groupby("area").agg({
        "puntaje": ["count", "mean", "min", "max"]
    }).round(2)
    
    stats_area.columns = ["📊 Cantidad", "📈 Promedio", "📉 Mínimo", "📈 Máximo"]
    st.dataframe(stats_area, use_container_width=True)

# ============================================================================
# PÁGINA: EXPORTAR
# ============================================================================
def pagina_exportar():
    """Muestra la página de exportación de datos"""
    
    st.title("📤 Exportar Datos")
    
    st.info("Exporte los datos de auditorías en diferentes formatos para su análisis externo.")
    
    # Obtener datos
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM checklist_results", conn)
    finally:
        conn.close()
    
    if df.empty:
        st.warning("⚠️ No hay datos para exportar")
        return
    
    # Formatear fechas
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
    
    # Mostrar vista previa
    st.subheader("📋 Vista Previa de Datos")
    st.dataframe(df.head(10), use_container_width=True)
    
    st.divider()
    
    # Opciones de exportación
    st.subheader("⚙️ Opciones de Exportación")
    
    col1, col2 = st.columns(2)
    
    with col1:
        formato = st.radio(
            "📁 Formato de archivo:",
            ["Excel (.xlsx)", "CSV (.csv)"],
            horizontal=True
        )
    
    with col2:
        incluir_todo = st.checkbox("📊 Incluir todos los datos", value=True)
        if not incluir_todo:
            limite = st.number_input(
                "🔢 Número de registros:",
                min_value=1,
                max_value=len(df),
                value=100
            )
            df_export = df.head(limite)
        else:
            df_export = df
    
    st.divider()
    
    # Sección de descarga
    st.subheader("📥 Descargar Archivo")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if formato == "Excel (.xlsx)":
        # Crear Excel
        excel = BytesIO()
        with pd.ExcelWriter(excel, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditorias')
            
            # Agregar hoja de resumen
            resumen = df_export.groupby("area").agg({
                "puntaje": ["count", "mean", "min", "max"]
            }).round(2)
            resumen.to_excel(writer, sheet_name='Resumen')
        
        excel.seek(0)
        
        st.download_button(
            "⬇️ Descargar Archivo Excel",
            excel,
            f"auditorias_{timestamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
        
        st.caption("📎 El archivo incluye: Hoja de datos completos + Hoja de resumen")
    
    else:  # CSV
        # Crear CSV
        csv = df_export.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            "⬇️ Descargar Archivo CSV",
            csv,
            f"auditorias_{timestamp}.csv",
            "text/csv",
            use_container_width=True,
            type="primary"
        )
        
        st.caption("📎 Archivo de texto separado por comas, compatible con Excel y otras herramientas")
    
    # Estadísticas del archivo
    st.divider()
    st.subheader("📊 Estadísticas del Archivo")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📄 Registros", len(df_export))
    with col2:
        st.metric("📍 Áreas", df_export["area"].nunique())
    with col3:
        st.metric("👤 Auditores", df_export["auditor"].nunique())

# ============================================================================
# PÁGINA: GESTIÓN DE USUARIOS
# ============================================================================
def pagina_usuarios():
    """Muestra la página de gestión de usuarios"""
    
    if st.session_state.rol != "admin":
        st.error("⛔ Acceso denegado. Solo administradores pueden acceder a esta sección.")
        return
    
    st.title("👥 Gestión de Usuarios")
    
    # Pestañas para diferentes funciones
    tab1, tab2, tab3 = st.tabs(["👤 Crear Usuario", "📋 Lista de Usuarios", "🔧 Editar Usuario"])
    
    with tab1:
        st.subheader("Crear Nuevo Usuario")
        
        with st.form("crear_usuario_form", border=True):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input(
                    "👤 Nombre de Usuario*",
                    placeholder="Ej: juan.perez",
                    help="Nombre único para identificar al usuario"
                )
                
                rol = st.selectbox(
                    "🎭 Rol*",
                    ["auditor", "admin", "supervisor"],
                    help="Define los permisos del usuario"
                )
            
            with col2:
                password = st.text_input(
                    "🔒 Contraseña*",
                    type="password",
                    help="Mínimo 6 caracteres"
                )
                
                confirm_password = st.text_input(
                    "🔒 Confirmar Contraseña*",
                    type="password"
                )
            
            col1, col2 = st.columns([3, 1])
            with col2:
                submitted = st.form_submit_button(
                    "👤 Crear Usuario",
                    use_container_width=True,
                    type="primary"
                )
            
            if submitted:
                # Validaciones
                if not username or not password:
                    st.error("❌ Complete todos los campos obligatorios")
                elif password != confirm_password:
                    st.error("❌ Las contraseñas no coinciden")
                elif len(password) < 6:
                    st.error("❌ La contraseña debe tener al menos 6 caracteres")
                else:
                    # Verificar si usuario ya existe
                    conn = get_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT * FROM users WHERE username=?", (username,))
                        
                        if cur.fetchone():
                            st.error("❌ Este nombre de usuario ya existe")
                        else:
                            # Crear usuario
                            cur.execute(
                                """INSERT INTO users 
                                (username, password, rol, created_at) 
                                VALUES (?, ?, ?, ?)""",
                                (username, hash_pass(password), rol, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            )
                            conn.commit()
                            
                            st.success(f"""
                            ✅ **Usuario creado exitosamente**
                            
                            **👤 Usuario:** {username}
                            **🎭 Rol:** {rol}
                            **📅 Fecha de creación:** {datetime.now().strftime("%d/%m/%Y %H:%M")}
                            """)
                            
                            # Limpiar formulario
                            st.rerun()
                    finally:
                        conn.close()
    
    with tab2:
        st.subheader("Usuarios Registrados")
        
        conn = get_connection()
        try:
            df_usuarios = pd.read_sql("""
                SELECT 
                    username,
                    rol,
                    created_at
                FROM users 
                ORDER BY created_at DESC
            """, conn)
            
            if not df_usuarios.empty:
                # Estadísticas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Total Usuarios", len(df_usuarios))
                with col2:
                    admins = len(df_usuarios[df_usuarios["rol"] == "admin"])
                    st.metric("👑 Administradores", admins)
                with col3:
                    st.metric("📅 Último Registro", df_usuarios["created_at"].iloc[0][:10])
                
                # Mostrar tabla formateada
                st.dataframe(
                    df_usuarios,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "username": "👤 Usuario",
                        "rol": "🎭 Rol",
                        "created_at": "📅 Fecha Registro"
                    }
                )
            else:
                st.info("ℹ️ No hay usuarios registrados")
                
        finally:
            conn.close()
    
    with tab3:
        st.subheader("Editar Información de Usuario")
        
        conn = get_connection()
        try:
            df_usuarios = pd.read_sql("SELECT id, username, rol FROM users ORDER BY username", conn)
            
            if not df_usuarios.empty:
                # Seleccionar usuario
                usuario_seleccionado = st.selectbox(
                    "🔍 Seleccionar usuario a editar:",
                    df_usuarios["username"]
                )
                
                # Obtener datos del usuario seleccionado
                usuario_data = df_usuarios[df_usuarios["username"] == usuario_seleccionado].iloc[0]
                
                # Formulario de edición
                with st.form("editar_usuario_form", border=True):
                    st.markdown(f"**✏️ Editando usuario:** {usuario_data['username']}")
                    
                    nuevo_rol = st.selectbox(
                        "🎭 Nuevo Rol",
                        ["auditor", "admin", "supervisor"],
                        index=["auditor", "admin", "supervisor"].index(usuario_data["rol"])
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.form_submit_button("💾 Actualizar Rol", use_container_width=True):
                            if nuevo_rol != usuario_data["rol"]:
                                conn2 = get_connection()
                                try:
                                    cur = conn2.cursor()
                                    cur.execute(
                                        "UPDATE users SET rol=? WHERE id=?",
                                        (nuevo_rol, usuario_data["id"])
                                    )
                                    conn2.commit()
                                    st.success(f"✅ Rol actualizado a '{nuevo_rol}'")
                                    st.rerun()
                                finally:
                                    conn2.close()
                            else:
                                st.info("ℹ️ No se realizaron cambios")
                    
                    with col2:
                        if st.form_submit_button("🔄 Resetear Contraseña", use_container_width=True, type="secondary"):
                            nueva_pass = "temp123"  # Contraseña temporal
                            conn2 = get_connection()
                            try:
                                cur = conn2.cursor()
                                cur.execute(
                                    "UPDATE users SET password=? WHERE id=?",
                                    (hash_pass(nueva_pass), usuario_data["id"])
                                )
                                conn2.commit()
                                
                                st.warning(f"""
                                ⚠️ **Contraseña reseteada**
                                
                                **👤 Usuario:** {usuario_data['username']}
                                **🔒 Nueva contraseña:** {nueva_pass}
                                """)
                                st.rerun()
                            finally:
                                conn2.close()
            else:
                st.info("ℹ️ No hay usuarios para editar")
                
        finally:
            conn.close()

# ============================================================================
# RUTEO PRINCIPAL
# ============================================================================
def main():
    """Función principal que maneja el routing de la aplicación"""
    
    if not st.session_state.login:
        mostrar_login()
    else:
        # Mostrar barra lateral
        mostrar_sidebar()
        
        # Mostrar la página actual basada en el estado
        if st.session_state.current_page == "checklist":
            pagina_checklist()
        elif st.session_state.current_page == "administrar":
            pagina_administrar()
        elif st.session_state.current_page == "historico":
            pagina_historico()
        elif st.session_state.current_page == "exportar":
            pagina_exportar()
        elif st.session_state.current_page == "usuarios":
            pagina_usuarios()
        else:
            pagina_checklist()

# ============================================================================
# EJECUCIÓN
# ============================================================================
if __name__ == "__main__":
    main()