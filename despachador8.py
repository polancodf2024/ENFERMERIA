import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import paramiko
import time
import os
import logging
from PIL import Image

# Configuración de logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configuración de la aplicación
class Config:
    def __init__(self):
        # Configuración local desde secrets.toml
        self.CSV_FILENAME = st.secrets["csv_materias_file"]     
        self.ECG_FOLDER = st.secrets["ecg_folder"]              
        self.LOGO_PATH = "escudo_COLOR.jpg"                    
        self.HIGHLIGHT_COLOR = "#90EE90"
        self.TIMEOUT = 30  # segundos para conexiones

        # Configuración remota desde secrets.toml
        self.REMOTE = {
            'HOST': st.secrets["remote_host"],
            'USER': st.secrets["remote_user"],
            'PASSWORD': st.secrets["remote_password"],
            'PORT': int(st.secrets.get("remote_port")),
            'DIR': st.secrets["remote_dir"],
            'ECG_DIR': st.secrets.get("remote_ecg_dir", st.secrets["ecg_folder"])
        }


CONFIG = Config()

# Crear carpetas locales si no existen
if not os.path.exists(CONFIG.ECG_FOLDER):
    os.makedirs(CONFIG.ECG_FOLDER)

# Clase para manejo SSH mejorado
class SSHManager:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # segundos entre reintentos

    @staticmethod
    def get_connection():
        """Establece conexión SSH con reintentos"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        for attempt in range(SSHManager.MAX_RETRIES):
            try:
                ssh.connect(
                    hostname=CONFIG.REMOTE['HOST'],
                    port=CONFIG.REMOTE['PORT'],
                    username=CONFIG.REMOTE['USER'],
                    password=CONFIG.REMOTE['PASSWORD'],
                    timeout=CONFIG.TIMEOUT
                )
                logging.info("Conexión SSH establecida")
                return ssh
            except Exception as e:
                logging.warning(f"Intento {attempt + 1} fallido: {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logging.error("Fallo definitivo al conectar via SSH")
                    return None

    @staticmethod
    def ensure_remote_folder(sftp, remote_path):
        """Asegura que la carpeta remota exista"""
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            sftp.mkdir(remote_path)
            logging.info(f"Creada carpeta remota: {remote_path}")

    @staticmethod
    def upload_file(local_path, remote_path):
        """Sube un archivo con verificación de integridad"""
        if not os.path.exists(local_path):
            logging.error(f"Archivo local no existe: {local_path}")
            return False
            
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                # Verificar tamaño local
                local_size = os.path.getsize(local_path)
                
                # Subir archivo
                sftp.put(local_path, remote_path)
                
                # Verificar tamaño remoto
                remote_size = sftp.stat(remote_path).st_size
                
                if local_size == remote_size:
                    logging.info(f"Archivo subido correctamente: {local_path} -> {remote_path}")
                    return True
                else:
                    logging.error(f"Error de integridad en transferencia: {local_path}")
                    try:
                        sftp.remove(remote_path)  # Eliminar archivo corrupto
                    except:
                        pass
                    return False
        except Exception as e:
            logging.error(f"Error en upload_file: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def download_file(remote_path, local_path):
        """Descarga un archivo con verificación de integridad"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                try:
                    # Verificar si existe remotamente
                    sftp.stat(remote_path)
                    
                    # Descargar archivo
                    sftp.get(remote_path, local_path)
                    
                    # Verificar integridad
                    remote_size = sftp.stat(remote_path).st_size
                    local_size = os.path.getsize(local_path)
                    
                    if remote_size == local_size:
                        logging.info(f"Archivo descargado correctamente: {remote_path} -> {local_path}")
                        return True
                    else:
                        logging.error(f"Error de integridad en descarga: {remote_path}")
                        os.remove(local_path)  # Eliminar archivo corrupto
                        return False
                        
                except FileNotFoundError:
                    logging.info(f"Archivo remoto no encontrado: {remote_path}")
                    return False
        except Exception as e:
            logging.error(f"Error en download_file: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def sync_with_remote(show_status=True):
        """Sincroniza todos los archivos con el servidor remoto"""
        try:
            if show_status:
                st.info("🔄 Sincronizando con servidor remoto...")
            
            # 1. Sincronizar CSV
            remote_csv_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.CSV_FILENAME}"
            
            # Descargar CSV remoto si existe
            if not Path(CONFIG.CSV_FILENAME).exists():
                if not SSHManager.download_file(remote_csv_path, CONFIG.CSV_FILENAME):
                    # Crear CSV vacío si no existe
                    columns = [
                        'timestamp', 'id_paciente', 'nombre_paciente', 
                        'presion_arterial', 'temperatura', 'oximetria', 
                        'estado'
                    ]
                    pd.DataFrame(columns=columns).to_csv(CONFIG.CSV_FILENAME, index=False)
            
            # 2. Sincronizar carpeta de ECGs
            remote_ecg_dir = f"{CONFIG.REMOTE['DIR']}/{CONFIG.REMOTE['ECG_DIR']}"
            
            # Crear conexión para operaciones múltiples
            ssh = SSHManager.get_connection()
            if not ssh:
                return False
                
            with ssh.open_sftp() as sftp:
                # Asegurar que existe la carpeta remota
                SSHManager.ensure_remote_folder(sftp, remote_ecg_dir)
                
                # Subir archivos locales que no existan remotamente
                local_ecgs = set(os.listdir(CONFIG.ECG_FOLDER))
                try:
                    remote_ecgs = set(sftp.listdir(remote_ecg_dir))
                except:
                    remote_ecgs = set()
                
                for ecg in local_ecgs - remote_ecgs:
                    local_path = f"{CONFIG.ECG_FOLDER}/{ecg}"
                    remote_path = f"{remote_ecg_dir}/{ecg}"
                    if not SSHManager.upload_file(local_path, remote_path):
                        logging.error(f"Fallo al subir ECG: {ecg}")
            
                # Subir CSV actualizado
                if not SSHManager.upload_file(CONFIG.CSV_FILENAME, remote_csv_path):
                    logging.error("Fallo al subir archivo CSV")
                    return False
            
            if show_status:
                st.success("✅ Sincronización completada")
            return True
            
        except Exception as e:
            logging.error(f"Error en sync_with_remote: {str(e)}")
            if show_status:
                st.error("❌ Error en sincronización con servidor remoto")
            return False

# Funciones principales
def save_record(data, ecg_file=None):
    """Guarda el registro localmente y sincroniza con el servidor remoto"""
    try:
        # 1. Guardar ECG si existe
        if ecg_file is not None:
            timestamp_str = data['timestamp'].replace(":", "-").replace(" ", "_")
            ecg_filename = f"{timestamp_str}_{data['id_paciente']}.pdf"
            ecg_path = f"{CONFIG.ECG_FOLDER}/{ecg_filename}"
            
            with open(ecg_path, "wb") as f:
                f.write(ecg_file.getbuffer())
            
            data['estado'] = 'A'  # Con ECG
        else:
            data['estado'] = 'N'  # Sin ECG

        # 2. Guardar en CSV
        record_df = pd.DataFrame([{
            'timestamp': data['timestamp'],
            'id_paciente': data['id_paciente'],
            'nombre_paciente': data['nombre_paciente'],
            'presion_arterial': data['presion_arterial'],
            'temperatura': data['temperatura'],
            'oximetria': data['oximetria'],
            'estado': data['estado']
        }])

        if not Path(CONFIG.CSV_FILENAME).exists():
            record_df.to_csv(CONFIG.CSV_FILENAME, index=False)
        else:
            existing_df = pd.read_csv(CONFIG.CSV_FILENAME)
            updated_df = pd.concat([existing_df, record_df], ignore_index=True)
            updated_df.to_csv(CONFIG.CSV_FILENAME, index=False)

        # 3. Sincronizar con servidor remoto (sin mostrar mensaje)
        if SSHManager.sync_with_remote(show_status=False):
            st.success("Registro guardado y sincronizado correctamente")
            return True
        else:
            st.warning("Registro guardado localmente (error en sincronización remota)")
            return False

    except Exception as e:
        logging.error(f"Error en save_record: {str(e)}")
        st.error("Error al guardar el registro")
        return False

# Interfaz de usuario
def main():
    st.set_page_config(
        page_title="Registro de Signos Vitales",
        page_icon="❤️",
        layout="centered"
    )

    # Logo
    if Path(CONFIG.LOGO_PATH).exists():
        st.image(Image.open(CONFIG.LOGO_PATH), width=200)

    st.title("Registro de Signos Vitales")

    # Sincronización automática al inicio
    if not st.session_state.get('initial_sync_done', False):
        with st.spinner("🔄 Sincronizando con servidor remoto..."):
            SSHManager.sync_with_remote(show_status=False)
        st.session_state.initial_sync_done = True

    # Formulario de captura
    with st.form("registro_form"):
        st.subheader("Nuevo Registro")
        
        # Campos del formulario
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        id_paciente = st.text_input("📱 Número de celular (10 dígitos):", max_chars=10)
        nombre_paciente = st.text_input("👤 Nombre completo del paciente:")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            presion_arterial = st.text_input("🩸 Presión arterial (mmHg):", placeholder="120/80")
        with col2:
            temperatura = st.text_input("🌡️ Temperatura (°C):", placeholder="36.5")
        with col3:
            oximetria = st.text_input("💓 Oximetría (%):", placeholder="98")
        
        ecg_file = st.file_uploader("📄 Subir ECG (PDF):", type=["pdf"])
        
        submitted = st.form_submit_button("💾 Guardar Registro")
        
        if submitted:
            # Validaciones
            if not id_paciente.isdigit() or len(id_paciente) != 10:
                st.error("El ID debe ser un número de celular de 10 dígitos")
            elif not all([nombre_paciente, presion_arterial, temperatura, oximetria]):
                st.error("Complete todos los campos obligatorios")
            else:
                data = {
                    'timestamp': timestamp,
                    'id_paciente': id_paciente,
                    'nombre_paciente': nombre_paciente,
                    'presion_arterial': presion_arterial,
                    'temperatura': temperatura,
                    'oximetria': oximetria
                }
                
                if save_record(data, ecg_file):
                    st.balloons()
                    time.sleep(2)
                    st.rerun()


if __name__ == "__main__":
    main()
