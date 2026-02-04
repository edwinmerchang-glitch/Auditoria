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
                    os.remove(f"backups/{old_backup}")
            
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
        
        log_operacion(st.session_state.user, "Agregar ítem", 
                     f"Categoría: {categoria}, Ítem: {item[:50]}...")
        return True, "✅ Ítem guardado exitosamente"
    except sqlite3.Error as e:
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
        
        log_operacion(st.session_state.user, "Actualizar ítem", f"ID: {item_id}")
        return True, "✅ Cambios guardados"
    except sqlite3.Error as e:
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
        
        if item_info:
            log_operacion(st.session_state.user, "Eliminar ítem", 
                         f"ID: {item_id}, Categoría: {item_info[0]}, Ítem: {item_info[1][:50]}...")
        
        return True, "✅ Ítem eliminado"
    except sqlite3.Error as e:
        log_operacion(st.session_state.user, "Error eliminar ítem", str(e))
        return False, f"❌ Error al eliminar: {e}"
    finally:
        if conn:
            conn.close()

# ============================================================================
# RESTA DEL CÓDIGO IGUAL HASTA LA PÁGINA DE ADMINISTRAR CHECKLIST
# ============================================================================
# ... (todo el código anterior de hash_pass, login_user, crear_usuarios_por_defecto, 
# manejo de sesión, mostrar_login, mostrar_sidebar, pagina_checklist) se mantiene igual ...

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
# MODIFICAR LA BARRA LATERAL PARA AGREGAR NUEVA PÁGINA
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