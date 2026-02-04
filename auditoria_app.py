import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os
import shutil
import logging
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

# Configurar logging
logging.basicConfig(
    filename='auditoria.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_operacion(usuario, accion, detalles):
    """Registra operaciones importantes en el log"""
    logging.info(f"Usuario: {usuario} - Acción: {accion} - Detalles: {detalles}")

# ============================================================================
# BASE DE DATOS - CON RUTA ABSOLUTA PARA MAYOR SEGURIDAD
# ============================================================================
# Definir ruta para la base de datos
DB_PATH = 'auditoria.db'  # Puedes cambiarlo a una ruta absoluta si quieres

def get_connection():
    """Crea y retorna una conexión a la base de datos"""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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
    log_operacion("SISTEMA", "Inicialización BD", "Tablas creadas/verificadas")

# ============================================================================
# FUNCIONES DE AUTENTICACIÓN
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
        log_operacion("SISTEMA", "Crear usuarios default", "Usuarios creados/verificados")
    finally:
        conn.close()

# ============================================================================
# FUNCIONES DE PERSISTENCIA MEJORADAS
# ============================================================================
def verificar_permisos_bd():
    """Verifica que se puedan escribir archivos en el directorio"""
    try:
        # Verificar permisos en el directorio actual
        if not os.access('.', os.W_OK):
            return False, "Sin permisos para crear archivos en el directorio"
        
        # Si la BD existe, verificar permisos de escritura
        if os.path.exists(DB_PATH):
            if not os.access(DB_PATH, os.W_OK):
                return False, "Sin permisos para escribir en la base de datos"
        
        return True, "Permisos OK"
    except Exception as e:
        return False, f"Error de permisos: {e}"

def hacer_backup_bd():
    """Crea una copia de seguridad de la base de datos"""
    try:
        if os.path.exists(DB_PATH):
            # Crear directorio de backups si no existe
            os.makedirs('backups', exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backups/auditoria_backup_{timestamp}.db"
            
            # Copiar archivo
            shutil.copy2(DB_PATH, backup_file)
            
            # Mantener solo los últimos 10 backups
            backups = sorted([f for f in os.listdir('backups') if f.startswith('auditoria_backup_')])
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    try:
                        os.remove(f"backups/{old_backup}")
                    except:
                        pass
            
            log_operacion("SISTEMA", "Backup BD", f"Backup creado: {backup_file}")
            return True, f"✅ Backup creado: {backup_file}"
        else:
            return False, "❌ No existe la base de datos para hacer backup"
    except Exception as e:
        log_operacion("SISTEMA", "Error Backup", str(e))
        return False, f"❌ Error en backup: {e}"

def verificar_integridad_bd():
    """Verifica la integridad de la base de datos"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Verificar tabla de checklist_items
        cur.execute("SELECT COUNT(*) FROM checklist_items")
        total_items = cur.fetchone()[0]
        
        # Verificar tabla de resultados
        cur.execute("SELECT COUNT(*) FROM checklist_results")
        total_results = cur.fetchone()[0]
        
        # Verificar integridad
        cur.execute("PRAGMA integrity_check")
        result = cur.fetchone()[0]
        
        if result == "ok":
            return True, f"✅ Base de datos íntegra ({total_items} ítems, {total_results} auditorías)"
        else:
            return False, f"❌ Problemas de integridad: {result}"
            
    except Exception as e:
        return False, f"❌ Error verificando BD: {e}"
    finally:
        if conn:
            conn.close()

def verificar_backup_diario():
    """Verifica si ya se hizo backup hoy, si no, lo crea"""
    try:
        hoy = datetime.now().strftime("%Y%m%d")
        
        # Verificar si ya hay backup hoy
        if os.path.exists('backups'):
            import glob
            backups_hoy = glob.glob(f"backups/auditoria_backup_{hoy}_*.db")
            if not backups_hoy:
                hacer_backup_bd()
                return True
        return False
    except:
        return False

# ============================================================================
# FUNCIONES MEJORADAS PARA CRUD CON MANEJO DE ERRORES
# ============================================================================
def guardar_item_checklist(categoria, item, puntaje_max):
    """Guarda un nuevo ítem en el checklist con manejo de errores"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO checklist_items (categoria, item, puntaje_max)
            VALUES (?, ?, ?)
        """, (categoria, item, puntaje_max))
        conn.commit()
        
        if 'user' in st.session_state:
            log_operacion(st.session_state.user, "Agregar ítem", 
                         f"Categoría: {categoria}, Ítem: {item[:50]}...")
        return True, "✅ Ítem guardado exitosamente"
    except sqlite3.Error as e:
        if 'user' in st.session_state:
            log_operacion(st.session_state.user, "Error agregar ítem", str(e))
        return False, f"❌ Error al guardar: {e}"
    finally:
        if conn:
            conn.close()

def actualizar_item_checklist(item_id, categoria, item, puntaje_max):
    """Actualiza un ítem existente"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE checklist_items 
            SET categoria=?, item=?, puntaje_max=?
            WHERE id=?
        """, (categoria, item, puntaje_max, item_id))
        conn.commit()
        
        if 'user' in st.session_state:
            log_operacion(st.session_state.user, "Actualizar ítem", f"ID: {item_id}")
        return True, "✅ Cambios guardados"
    except sqlite3.Error as e:
        if 'user' in st.session_state:
            log_operacion(st.session_state.user, "Error actualizar ítem", str(e))
        return False, f"❌ Error al actualizar: {e}"
    finally:
        if conn:
            conn.close()

def eliminar_item_checklist(item_id):
    """Elimina un ítem del checklist"""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Primero obtener info del item para el log
        cur.execute("SELECT categoria, item FROM checklist_items WHERE id=?", (item_id,))
        item_info = cur.fetchone()
        
        # Eliminar el item
        cur.execute("DELETE FROM checklist_items WHERE id=?", (item_id,))
        conn.commit()
        
        if 'user' in st.session_state and item_info:
            log_operacion(st.session_state.user, "Eliminar ítem", 
                         f"ID: {item_id}, Categoría: {item_info[0]}, Ítem: {item_info[1][:50]}...")
        
        return True, "✅ Ítem eliminado"
    except sqlite3.Error as e:
        if 'user' in st.session_state:
            log_operacion(st.session_state.user, "Error eliminar ítem", str(e))
        return False, f"❌ Error al eliminar: {e}"
    finally:
        if conn:
            conn.close()

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
                            log_operacion(user, "Login exitoso", f"Rol: {data[3]}")
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
            <small style="color: #666;">Persistencia Mejorada</small>
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
        
        # Definir páginas según rol - AGREGAR NUEVA PÁGINA PARA ADMIN
        if st.session_state.rol == "admin":
            menu_items = [
                {"icon": "📋", "name": "Checklist", "page": "checklist"},
                {"icon": "⚙️", "name": "Administrar Checklist", "page": "administrar"},
                {"icon": "📊", "name": "Histórico", "page": "historico"},
                {"icon": "📤", "name": "Exportar", "page": "exportar"},
                {"icon": "👥", "name": "Gestión de Usuarios", "page": "usuarios"},
                {"icon": "🖥️", "name": "Estado Sistema", "page": "estado"}  # NUEVO
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
        
        # Estado del sistema (mini)
        if os.path.exists(DB_PATH):
            size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
            st.caption(f"💾 BD: {size_mb:.2f} MB")
        
        # Botón de cerrar sesión
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            log_operacion(st.session_state.user, "Cerrar sesión", "Usuario salió del sistema")
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
                    
                    # Registrar en log
                    log_operacion(st.session_state.user, "Guardar auditoría", 
                                f"Área: {area}, Resultado: {porcentaje}%")
                    
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
# PÁGINA: ADMINISTRAR CHECKLIST - ACTUALIZADA
# ============================================================================
def pagina_administrar():
    """Página de administración del checklist"""
    
    if st.session_state.rol != "admin":
        st.error("⛔ Acceso denegado. Solo administradores pueden acceder a esta sección.")
        return
    
    st.title("⚙️ Administrar Checklist")
    
    # Verificar permisos primero
    estado_permisos, mensaje_permisos = verificar_permisos_bd()
    if not estado_permisos:
        st.error(f"⚠️ {mensaje_permisos}")
        return
    
    # Pestañas para diferentes funciones
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Agregar Ítems", "📋 Ver Ítems", "✏️ Editar/Eliminar", "🛡️ Mantenimiento"])
    
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
                    # Usar la nueva función con manejo de errores
                    exito, mensaje = guardar_item_checklist(categoria, item, puntaje)
                    if exito:
                        st.success(mensaje)
                        st.rerun()
                    else:
                        st.error(mensaje)
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
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Total Ítems", len(df))
                with col2:
                    st.metric("📂 Categorías", df["categoria"].nunique())
                with col3:
                    st.metric("🎯 Puntaje Total", df["puntaje_max"].sum())
                with col4:
                    st.metric("💾 Estado", "🟢 Activo")
                
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
                            exito, mensaje = actualizar_item_checklist(
                                selected_item["id"], new_cat, new_item, new_puntaje
                            )
                            if exito:
                                st.success(mensaje)
                                st.rerun()
                            else:
                                st.error(mensaje)
                    
                    with col2:
                        if st.form_submit_button("🗑️ Eliminar Ítem", use_container_width=True, type="secondary"):
                            # Confirmación de eliminación
                            with st.expander("⚠️ Confirmar Eliminación", expanded=True):
                                st.warning(f"¿Está seguro de eliminar este ítem?")
                                st.code(f"{selected_item['categoria']} - {selected_item['item']}")
                                
                                col_confirm1, col_confirm2 = st.columns(2)
                                with col_confirm1:
                                    if st.button("✅ Sí, eliminar", use_container_width=True):
                                        exito, mensaje = eliminar_item_checklist(selected_item["id"])
                                        if exito:
                                            st.success(mensaje)
                                            st.rerun()
                                        else:
                                            st.error(mensaje)
                                with col_confirm2:
                                    if st.button("❌ Cancelar", use_container_width=True):
                                        st.info("Eliminación cancelada")
            else:
                st.info("ℹ️ No hay ítems para editar")
                
        finally:
            conn.close()
    
    with tab4:
        st.subheader("🛡️ Mantenimiento del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Verificar integridad
            if st.button("🔍 Verificar Integridad BD", use_container_width=True):
                estado, mensaje = verificar_integridad_bd()
                if estado:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
            
            # Crear backup manual
            if st.button("💾 Crear Backup Manual", use_container_width=True):
                estado, mensaje = hacer_backup_bd()
                if estado:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
        
        with col2:
            # Verificar permisos
            if st.button("🔐 Verificar Permisos", use_container_width=True):
                estado, mensaje = verificar_permisos_bd()
                if estado:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
            
            # Verificar backup diario
            if st.button("📅 Verificar Backup Diario", use_container_width=True):
                if verificar_backup_diario():
                    st.success("✅ Backup diario verificado/creado")
                else:
                    st.info("ℹ️ Ya existe backup hoy o hubo un error")
        
        # Mostrar info de backups
        if os.path.exists('backups'):
            backups = [f for f in os.listdir('backups') if f.startswith('auditoria_backup_')]
            if backups:
                st.subheader("📦 Backups Disponibles")
                
                # Ordenar por fecha (más reciente primero)
                backups.sort(reverse=True)
                
                for b in backups[:5]:  # Mostrar últimos 5
                    file_path = f"backups/{b}"
                    file_size = os.path.getsize(file_path) / 1024  # Tamaño en KB
                    
                    col_info1, col_info2, col_info3 = st.columns([3, 2, 1])
                    with col_info1:
                        st.code(b)
                    with col_info2:
                        st.caption(f"{file_size:.1f} KB")
                    with col_info3:
                        # Botón para restaurar (simplificado)
                        if st.button("🔄", key=f"restore_{b}"):
                            st.info(f"Funcionalidad de restauración para {b}")

# ============================================================================
# NUEVA PÁGINA: ESTADO DEL SISTEMA
# ============================================================================
def pagina_estado_sistema():
    """Muestra el estado del sistema y base de datos"""
    if st.session_state.rol != "admin":
        st.error("⛔ Acceso denegado. Solo administradores pueden acceder a esta sección.")
        return
    
    st.title("🖥️ Estado del Sistema")
    
    # Verificar backup diario automáticamente
    verificar_backup_diario()
    
    # Mostrar estado en tiempo real
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Estadísticas de Datos")
        conn = get_connection()
        try:
            # Contar ítems
            df_items = pd.read_sql("SELECT COUNT(*) as total FROM checklist_items", conn)
            df_results = pd.read_sql("SELECT COUNT(*) as total FROM checklist_results", conn)
            df_users = pd.read_sql("SELECT COUNT(*) as total FROM users", conn)
            
            # Obtener última auditoría
            df_last = pd.read_sql("""
                SELECT fecha, area, auditor 
                FROM checklist_results 
                ORDER BY fecha DESC LIMIT 1
            """, conn)
            
            st.metric("📋 Ítems Checklist", df_items.iloc[0]['total'])
            st.metric("📊 Auditorías Realizadas", df_results.iloc[0]['total'])
            st.metric("👥 Usuarios Registrados", df_users.iloc[0]['total'])
            
            if not df_last.empty:
                st.metric("📅 Última Auditoría", 
                         df_last.iloc[0]['fecha'],
                         delta=df_last.iloc[0]['area'])
            
        finally:
            conn.close()
    
    with col2:
        st.subheader("🔧 Estado del Sistema")
        
        # Verificar permisos
        estado_perm, mensaje_perm = verificar_permisos_bd()
        if estado_perm:
            st.success("🔐 Permisos: OK")
        else:
            st.error(f"🔐 Permisos: {mensaje_perm}")
        
        # Verificar integridad
        estado_int, mensaje_int = verificar_integridad_bd()
        if estado_int:
            st.success("✅ Integridad BD: OK")
        else:
            st.error(f"✅ Integridad BD: {mensaje_int}")
        
        # Tamaño de la BD
        if os.path.exists(DB_PATH):
            size_kb = os.path.getsize(DB_PATH) / 1024
            st.info(f"💾 Tamaño BD: {size_kb:.1f} KB")
        
        # Backups disponibles
        if os.path.exists('backups'):
            backups = [f for f in os.listdir('backups') if f.startswith('auditoria_backup_')]
            st.info(f"📦 Backups: {len(backups)} disponibles")
    
    st.divider()
    
    # Información técnica
    st.subheader("📋 Información Técnica")
    
    col_info1, col_info2, col_info3 = st.columns(3)
    
    with col_info1:
        st.metric("🗄️ Base de Datos", DB_PATH)
        st.metric("🐍 Python", "3.x")
    
    with col_info2:
        st.metric("📚 Streamlit", st.__version__)
        st.metric("📊 Pandas", pd.__version__)
    
    with col_info3:
        # Últimas operaciones del log (simplificado)
        if os.path.exists('auditoria.log'):
            try:
                with open('auditoria.log', 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        st.caption("📝 Última operación:")
                        st.code(last_line[:100] + "..." if len(last_line) > 100 else last_line)
            except:
                pass

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
        
        # Usar tupla en lugar de lista
        rango_fechas = st.date_input(
            "📅 Rango de fechas:",
            (fecha_max - timedelta(days=30), fecha_max),  # TUPLA
            min_value=fecha_min,
            max_value=fecha_max
        )
    
    with col3:
        auditores = ["Todos"] + sorted(df["auditor"].unique().tolist())
        auditor_filtro = st.selectbox("👤 Auditor:", auditores)
    
    # Aplicar filtros
    if area_filtro != "Todas":
        df = df[df["area"] == area_filtro]
    
    # Manejar rango y fecha única
    if len(rango_fechas) == 2:
        df = df[
            (df["fecha"].dt.date >= rango_fechas[0]) & 
            (df["fecha"].dt.date <= rango_fechas[1])
        ]
    elif len(rango_fechas) == 1:
        # Si solo selecciona una fecha
        df = df[df["fecha"].dt.date == rango_fechas[0]]
    
    if auditor_filtro != "Todos":
        df = df[df["auditor"] == auditor_filtro]
    
    if df.empty:
        st.warning("⚠️ No hay datos con los filtros seleccionados")
        return
    
    # Resto del código sigue igual...
    
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
                            
                            log_operacion(st.session_state.user, "Crear usuario", 
                                        f"Usuario: {username}, Rol: {rol}")
                            
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
                                    
                                    log_operacion(st.session_state.user, "Actualizar rol usuario", 
                                                f"Usuario: {usuario_data['username']}, Nuevo rol: {nuevo_rol}")
                                    
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
                                
                                log_operacion(st.session_state.user, "Resetear contraseña", 
                                            f"Usuario: {usuario_data['username']}")
                                
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
# RUTEO PRINCIPAL - AGREGAR NUEVA RUTA
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
        elif st.session_state.current_page == "estado":  # NUEVO
            pagina_estado_sistema()
        else:
            pagina_checklist()

# ============================================================================
# INICIALIZACIÓN MEJORADA
# ============================================================================
# Inicializar base de datos
init_db()

# Crear usuarios por defecto
crear_usuarios_por_defecto()

# Verificar backup diario al inicio (solo si es admin o primera vez)
verificar_backup_diario()

# ============================================================================
# EJECUCIÓN
# ============================================================================
if __name__ == "__main__":
    main()