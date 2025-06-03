import streamlit as st
import pandas as pd
import csv
from pathlib import Path
from datetime import datetime
import paramiko
import time
import os
import logging
from PIL import Image

# Configuración de logging mejorada
logging.basicConfig(
    filename='tesis.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ====================
# CONFIGURACIÓN INICIAL
# ====================
class Config:
    def __init__(self):
        self.SMTP_SERVER = st.secrets.get("smtp_server")
        self.SMTP_PORT = st.secrets.get("smtp_port")
        self.EMAIL_USER = st.secrets.get("email_user")
        self.EMAIL_PASSWORD = st.secrets.get("email_password")
        self.NOTIFICATION_EMAIL = st.secrets.get("notification_email")
        self.CSV_FILENAME = "signos.csv"  # Archivo único para todos los registros
        self.TIMEOUT_SECONDS = 30
        self.HIGHLIGHT_COLOR = "#90EE90"
        self.LOGO_PATH = "escudo_COLOR.jpg"
        
        self.REMOTE = {
            'HOST': st.secrets.get("remote_host"),
            'USER': st.secrets.get("remote_user"),
            'PASSWORD': st.secrets.get("remote_password"),
            'PORT': st.secrets.get("remote_port"),
            'DIR': st.secrets.get("remote_dir")
        }

CONFIG = Config()

# ==================
# CLASE SSH MANAGER (igual que antes)
# ==================
class SSHManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # segundos

    @staticmethod
    def get_connection():
        """Establece conexión SSH segura con reintentos"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        for attempt in range(SSHManager.MAX_RETRIES):
            try:
                ssh.connect(
                    hostname=CONFIG.REMOTE['HOST'],
                    port=CONFIG.REMOTE['PORT'],
                    username=CONFIG.REMOTE['USER'],
                    password=CONFIG.REMOTE['PASSWORD'],
                    timeout=CONFIG.TIMEOUT_SECONDS
                )
                logging.info(f"Conexión SSH establecida (intento {attempt + 1})")
                return ssh
            except Exception as e:
                logging.warning(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logging.error("Fallo definitivo al conectar via SSH")
                    st.error(f"Error de conexión SSH después de {SSHManager.MAX_RETRIES} intentos: {str(e)}")
                    return None

    @staticmethod
    def verify_file_integrity(local_path, remote_path, sftp):
        """Verifica que el archivo se transfirió correctamente"""
        try:
            local_size = os.path.getsize(local_path)
            remote_size = sftp.stat(remote_path).st_size
            return local_size == remote_size
        except Exception as e:
            logging.error(f"Error verificando integridad: {str(e)}")
            return False

    @staticmethod
    def download_remote_file(remote_path, local_path):
        """Descarga un archivo con verificación de integridad"""
        for attempt in range(SSHManager.MAX_RETRIES):
            ssh = SSHManager.get_connection()
            if not ssh:
                return False
                
            try:
                with ssh.open_sftp() as sftp:
                    try:
                        sftp.stat(remote_path)
                    except FileNotFoundError:
                        # Crear archivo local con estructura correcta
                        columns = [
                            'timestamp', 'id_paciente', 'nombre_paciente', 
                            'presion_arterial', 'temperatura', 'oximetria', 
                            'estado'
                        ]
                        pd.DataFrame(columns=columns).to_csv(local_path, index=False)
                        logging.info(f"Archivo remoto no encontrado, creado local con estructura: {local_path}")
                        return True
                        
                    sftp.get(remote_path, local_path)
                    
                    if SSHManager.verify_file_integrity(local_path, remote_path, sftp):
                        logging.info(f"Archivo descargado correctamente: {remote_path} a {local_path}")
                        return True
                    else:
                        logging.warning(f"Error de integridad en descarga, reintentando... (intento {attempt + 1})")
                        if attempt < SSHManager.MAX_RETRIES - 1:
                            time.sleep(SSHManager.RETRY_DELAY)
                        else:
                            raise Exception("Fallo en verificación de integridad después de múltiples intentos")
                            
            except Exception as e:
                logging.error(f"Error en descarga (intento {attempt + 1}): {str(e)}")
                if attempt == SSHManager.MAX_RETRIES - 1:
                    st.error(f"Error descargando archivo remoto después de {SSHManager.MAX_RETRIES} intentos: {str(e)}")
                    return False
                    
            finally:
                ssh.close()

    @staticmethod
    def upload_remote_file(local_path, remote_path):
        """Sube un archivo con verificación de integridad"""
        if not os.path.exists(local_path):
            logging.error(f"Archivo local no existe: {local_path}")
            st.error("El archivo local no existe")
            return False
            
        for attempt in range(SSHManager.MAX_RETRIES):
            ssh = SSHManager.get_connection()
            if not ssh:
                return False
                
            try:
                with ssh.open_sftp() as sftp:
                    sftp.put(local_path, remote_path)
                    
                    if SSHManager.verify_file_integrity(local_path, remote_path, sftp):
                        logging.info(f"Archivo subido correctamente: {local_path} a {remote_path}")
                        return True
                    else:
                        logging.warning(f"Error de integridad en subida, reintentando... (intento {attempt + 1})")
                        if attempt < SSHManager.MAX_RETRIES - 1:
                            time.sleep(SSHManager.RETRY_DELAY)
                        else:
                            raise Exception("Fallo en verificación de integridad después de múltiples intentos")
                            
            except Exception as e:
                logging.error(f"Error en subida (intento {attempt + 1}): {str(e)}")
                if attempt == SSHManager.MAX_RETRIES - 1:
                    st.error(f"Error subiendo archivo remoto después de {SSHManager.MAX_RETRIES} intentos: {str(e)}")
                    return False
                    
            finally:
                ssh.close()

# ====================
# FUNCIONES PRINCIPALES MODIFICADAS
# ====================
def sync_with_remote():
    """Sincroniza el archivo local signos.csv con el remoto"""
    try:
        st.info("🔄 Sincronizando con el servidor remoto...")
        remote_path = os.path.join(CONFIG.REMOTE['DIR'], CONFIG.CSV_FILENAME)

        # Intenta descargar el archivo remoto
        download_success = SSHManager.download_remote_file(remote_path, CONFIG.CSV_FILENAME)

        if not download_success:
            # Si no existe el archivo remoto, crea uno local con estructura correcta
            columns = [
                'timestamp', 'id_paciente', 'nombre_paciente', 
                'presion_arterial', 'temperatura', 'oximetria', 
                'estado'
            ]

            # Verifica si el archivo local ya existe
            if not Path(CONFIG.CSV_FILENAME).exists():
                pd.DataFrame(columns=columns).to_csv(CONFIG.CSV_FILENAME, index=False)
                st.info("ℹ️ No se encontró archivo remoto. Se creó uno nuevo localmente con la estructura correcta.")
            else:
                # Si el archivo local existe pero está vacío o corrupto
                try:
                    df = pd.read_csv(CONFIG.CSV_FILENAME)
                    if df.empty:
                        pd.DataFrame(columns=columns).to_csv(CONFIG.CSV_FILENAME, index=False)
                except:
                    pd.DataFrame(columns=columns).to_csv(CONFIG.CSV_FILENAME, index=False)

            return False

        # Verifica que el archivo descargado no esté vacío
        try:
            df = pd.read_csv(CONFIG.CSV_FILENAME)
            if df.empty:
                st.warning("El archivo remoto está vacío")
        except pd.errors.EmptyDataError:
            st.warning("El archivo remoto está vacío o corrupto")
            columns = [
                'timestamp', 'id_paciente', 'nombre_paciente', 
                'presion_arterial', 'temperatura', 'oximetria', 
                'estado'
            ]
            pd.DataFrame(columns=columns).to_csv(CONFIG.CSV_FILENAME, index=False)
            return False

        st.success("✅ Sincronización con servidor remoto completada")
        return True

    except Exception as e:
        st.error(f"❌ Error en sincronización: {str(e)}")
        logging.error(f"Sync Error: {str(e)}")
        return False

def save_to_csv(data: dict):
    """Guarda los datos en el CSV local y remoto, eliminando registros con estado 'X'"""
    try:
        with st.spinner("Sincronizando datos con el servidor..."):
            if not sync_with_remote():
                st.warning("⚠️ Trabajando con copia local debido a problemas de conexión")

        columns = [
            'timestamp', 'id_paciente', 'nombre_paciente', 
            'presion_arterial', 'temperatura', 'oximetria', 
            'estado'
        ]

        # Verificar si el archivo existe y tiene contenido válido
        if not Path(CONFIG.CSV_FILENAME).exists():
            df_existing = pd.DataFrame(columns=columns)
        else:
            try:
                df_existing = pd.read_csv(
                    CONFIG.CSV_FILENAME,
                    encoding='utf-8-sig',
                    dtype={'id_paciente': str}
                )
                # Eliminar registros con estado 'X'
                df_existing = df_existing[df_existing['estado'] != 'X'].copy()
                
                # Verificar si el DataFrame está vacío
                if df_existing.empty:
                    df_existing = pd.DataFrame(columns=columns)
                # Verificar si tiene todas las columnas necesarias
                missing_cols = set(columns) - set(df_existing.columns)
                if missing_cols:
                    for col in missing_cols:
                        df_existing[col] = ""
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                df_existing = pd.DataFrame(columns=columns)

        # Preparar el nuevo registro
        df_new = pd.DataFrame([data])

        # Limpiar los datos del nuevo registro
        for col in df_new.columns:
            if df_new[col].dtype == object:
                df_new[col] = df_new[col].astype(str).str.replace(r'\r\n|\n|\r', ' ', regex=True).str.strip()

        # Combinar los datos existentes (sin los 'X') con los nuevos
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)

        # Asegurar que todas las columnas estén presentes
        for col in columns:
            if col not in df_combined.columns:
                df_combined[col] = ""

        # Reordenar columnas
        df_combined = df_combined[columns]

        # Guardar localmente
        df_combined.to_csv(CONFIG.CSV_FILENAME, index=False, encoding='utf-8-sig')

        # Intentar subir al servidor remoto
        with st.spinner("Subiendo datos al servidor remoto..."):
            remote_path = os.path.join(CONFIG.REMOTE['DIR'], CONFIG.CSV_FILENAME)
            if SSHManager.upload_remote_file(CONFIG.CSV_FILENAME, remote_path):
                st.success("✅ Registro guardado exitosamente en el servidor remoto!")
                return True
            else:
                st.error("❌ No se pudo subir el archivo al servidor remoto")
                st.info("ℹ️ Los datos se guardaron localmente y se intentará subir en la próxima sincronización")
                return False

    except Exception as e:
        st.error(f"❌ Error al guardar en CSV: {str(e)}")
        logging.error(f"Save CSV Error: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="Registro de Signos Vitales",
        page_icon="❤️",
        layout="centered"
    )

    # Mostrar logo si existe
    if Path(CONFIG.LOGO_PATH).exists():
        logo = Image.open(CONFIG.LOGO_PATH)
        st.image(logo, width=200)

    st.title("❤️ Registro de Signos Vitales")

    # Sincronización inicial
    with st.spinner("Conectando con el servidor remoto..."):
        sync_with_remote()

    # Cargar o inicializar el DataFrame
    if Path(CONFIG.CSV_FILENAME).exists():
        try:
            pacientes_df = pd.read_csv(CONFIG.CSV_FILENAME, encoding='utf-8-sig', dtype={'id_paciente': str})
            pacientes_df['id_paciente'] = pacientes_df['id_paciente'].astype(str).str.strip()

            # Asegurar que el campo 'estado' exista
            if 'estado' not in pacientes_df.columns:
                pacientes_df['estado'] = 'A'
            else:
                # Limpiar valores vacíos/nulos en el campo estado
                pacientes_df['estado'] = pacientes_df['estado'].fillna('A').str.strip().replace('', 'A')
        except Exception as e:
            st.error(f"Error al leer el archivo: {str(e)}")
            pacientes_df = pd.DataFrame(columns=[
                'timestamp', 'id_paciente', 'nombre_paciente', 
                'presion_arterial', 'temperatura', 'oximetria', 
                'estado'
            ])
    else:
        pacientes_df = pd.DataFrame(columns=[
            'timestamp', 'id_paciente', 'nombre_paciente', 
            'presion_arterial', 'temperatura', 'oximetria', 
            'estado'
        ])

    # Mostrar registros existentes si los hay
    if not pacientes_df.empty:
        st.subheader("📋 Registros médicos existentes")
        st.info("""
        **Instrucciones:**
        - Marque con 'X' los registros que desee dar de baja
        - Todos los demás deben mantenerse con 'A' (Activo)
        """)

        # Crear copia editable solo con las columnas necesarias
        columnas_mostrar = ['timestamp', 'id_paciente', 'nombre_paciente', 
                           'presion_arterial', 'temperatura', 'oximetria', 'estado']
        edited_df = pacientes_df[columnas_mostrar].copy()

        # Mostrar editor de tabla
        edited_df = st.data_editor(
            edited_df,
            column_config={
                "estado": st.column_config.SelectboxColumn(
                    "Estado",
                    options=["A", "X"],
                    required=True,
                    width="small"
                )
            },
            hide_index=True,
            use_container_width=True,
            key="editor_tabla"
        )

        # Verificar cambios en los estados
        if not edited_df.equals(pacientes_df[columnas_mostrar]):
            # Actualizar el estado en el DataFrame original
            pacientes_df['estado'] = edited_df['estado']

            # Identificar registros marcados para borrar
            registros_a_borrar = pacientes_df[pacientes_df['estado'] == 'X']

            if not registros_a_borrar.empty:
                st.warning(f"⚠️ Tiene {len(registros_a_borrar)} registro(s) marcado(s) para dar de baja")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Confirmar baja de registros", type="primary"):
                        # Filtrar solo los registros activos (estado 'A')
                        pacientes_df = pacientes_df[pacientes_df['estado'] == 'A'].copy()

                        # Guardar cambios en el archivo
                        pacientes_df.to_csv(CONFIG.CSV_FILENAME, index=False, encoding='utf-8-sig')

                        # Sincronizar con servidor remoto
                        with st.spinner("Guardando cambios..."):
                            remote_path = os.path.join(CONFIG.REMOTE['DIR'], CONFIG.CSV_FILENAME)
                            upload_success = SSHManager.upload_remote_file(CONFIG.CSV_FILENAME, remote_path)

                        if upload_success:
                            st.success("✅ Registros eliminados exitosamente del archivo!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Error al sincronizar con el servidor remoto")

                with col2:
                    if st.button("↩️ Cancelar operación"):
                        st.info("Operación cancelada - No se realizaron cambios")
                        st.rerun()

    # Preguntar si desea añadir nuevo registro
    st.divider()
    if st.radio("¿Desea registrar nuevos signos vitales?", ["No", "Sí"], index=0) == "Sí":
        # Formulario para nuevo registro
        st.subheader("📝 Nuevo registro médico")

        with st.form("nuevo_registro", clear_on_submit=True):
            # Obtener timestamp actual
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            id_paciente = st.text_input("📱 Número de celular del paciente (10 dígitos):")
            nombre_paciente = st.text_input("👤 Nombre completo del paciente:")
            presion_arterial = st.text_input("🩸 Presión arterial (ej. 120/80):")
            temperatura = st.text_input("🌡️ Temperatura corporal (°C):")
            oximetria = st.text_input("💓 Oximetría (%):")

            if st.form_submit_button("💾 Guardar registro médico"):
                # Validaciones
                if not id_paciente.isdigit() or len(id_paciente) != 10:
                    st.error("El número de celular debe contener exactamente 10 dígitos")
                elif not all([nombre_paciente, presion_arterial, temperatura, oximetria]):
                    st.error("Por favor complete todos los campos obligatorios")
                else:
                    nuevo_registro = {
                        'timestamp': timestamp,
                        'id_paciente': id_paciente,
                        'nombre_paciente': nombre_paciente,
                        'presion_arterial': presion_arterial,
                        'temperatura': temperatura,
                        'oximetria': oximetria,
                        'estado': 'A'  # Todos los nuevos registros se crean como activos
                    }

                    if save_to_csv(nuevo_registro):
                        st.success("✅ Registro guardado exitosamente!")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()

if __name__ == "__main__":
    main()
