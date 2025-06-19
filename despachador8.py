import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import paramiko
import time
import os
import logging
from PIL import Image
import io


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
        self.CSV_FILENAME = st.secrets["csv_signos_file"]     
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

# Crear carpeta local para ECGs si no existe
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
                    timeout=CONFIG.TIMEOUT,
                    banner_timeout=200
                )
                logging.info("Conexión SSH establecida")
                return ssh
            except paramiko.AuthenticationException:
                logging.error("Error de autenticación SSH")
                return None
            except paramiko.SSHException as e:
                logging.warning(f"Intento {attempt + 1} fallido (SSHException): {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logging.error("Fallo definitivo al conectar via SSH")
                    return None
            except Exception as e:
                logging.warning(f"Intento {attempt + 1} fallido (Error general): {str(e)}")
                if attempt < SSHManager.MAX_RETRIES - 1:
                    time.sleep(SSHManager.RETRY_DELAY)
                else:
                    logging.error("Fallo definitivo al conectar via SSH")
                    return None

    @staticmethod
    def upload_file(local_path, remote_path):
        """Sube un archivo al servidor remoto"""
        ssh = SSHManager.get_connection()
        if not ssh:
            return False
            
        try:
            with ssh.open_sftp() as sftp:
                # Verificar si existe el directorio remoto, si no, crearlo
                remote_dir = os.path.dirname(remote_path)
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    sftp.mkdir(remote_dir)
                
                # Subir el archivo
                sftp.put(local_path, remote_path)
                logging.info(f"Archivo subido exitosamente: {local_path} -> {remote_path}")
                return True
        except Exception as e:
            logging.error(f"Error al subir archivo: {str(e)}")
            return False
        finally:
            ssh.close()

    @staticmethod
    def append_to_remote_csv(data):
        """Añade un registro al CSV remoto con el campo correo=0"""
        ssh = SSHManager.get_connection()
        if not ssh:
            logging.error("No se pudo establecer conexión SSH")
            return False
            
        try:
            remote_csv_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.CSV_FILENAME}"
            
            # Crear una línea CSV del registro (incluyendo número económico y correo=0)
            csv_line = (
                f"{data['timestamp']},"
                f"{data['id_paciente']},"
                f"\"{data['nombre_paciente']}\","
                f"\"{data['numero_economico']}\","
                f"{data['presion_arterial']},"
                f"{data['temperatura']},"
                f"{data['oximetria']},"
                f"{data['estado']},"
                f"0\n"  # Campo correo siempre con valor 0
            )
            
            # Verificar si el archivo existe remotamente
            sftp = ssh.open_sftp()
            try:
                sftp.stat(remote_csv_path)
                file_exists = True
            except FileNotFoundError:
                file_exists = False
            
            if file_exists:
                # Si el archivo existe, añadir la línea al final
                with sftp.file(remote_csv_path, 'a') as remote_file:
                    remote_file.write(csv_line)
            else:
                # Si no existe, crear el archivo con cabeceras (incluyendo número económico y correo)
                header = (
                    "timestamp,id_paciente,nombre_paciente,numero_economico,"
                    "presion_arterial,temperatura,oximetria,estado,correo\n"
                )
                with sftp.file(remote_csv_path, 'w') as remote_file:
                    remote_file.write(header)
                    remote_file.write(csv_line)
            
            logging.info("Registro añadido al CSV remoto correctamente")
            return True
            
        except Exception as e:
            logging.error(f"Error en append_to_remote_csv: {str(e)}")
            return False
        finally:
            try:
                sftp.close()
            except:
                pass
            ssh.close()

# Funciones principales
def save_record(data, ecg_file=None):
    """Guarda el registro en el servidor remoto"""
    try:
        # 1. Guardar ECG local y remotamente si existe
        if ecg_file is not None:
            timestamp_str = data['timestamp'].replace(":", "-").replace(" ", "_")
            ecg_filename = f"{timestamp_str}_{data['id_paciente']}.pdf"
            local_ecg_path = f"{CONFIG.ECG_FOLDER}/{ecg_filename}"
            remote_ecg_path = f"{CONFIG.REMOTE['DIR']}/{CONFIG.REMOTE['ECG_DIR']}/{ecg_filename}"
            
            # Guardar localmente
            with open(local_ecg_path, "wb") as f:
                f.write(ecg_file.getbuffer())
            
            # Subir al servidor remoto
            if not SSHManager.upload_file(local_ecg_path, remote_ecg_path):
                st.error("❌ Error al subir el ECG al servidor remoto")
                return False
            
            data['estado'] = 'A'  # Con ECG
        else:
            data['estado'] = 'N'  # Sin ECG

        # 2. Añadir registro al CSV remoto (incluirá número económico y correo=0 automáticamente)
        if SSHManager.append_to_remote_csv(data):
            st.success("✅ Registro guardado correctamente en el servidor remoto")
            return True
        else:
            st.error("❌ Error al guardar el registro en el servidor remoto. Verifica la conexión.")
            return False

    except Exception as e:
        logging.error(f"Error en save_record: {str(e)}")
        st.error(f"❌ Error inesperado al guardar el registro: {str(e)}")
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

    # Formulario de captura
    with st.form("registro_form"):
        st.subheader("Nuevo Registro")
        
        # Campos del formulario
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        id_paciente = st.text_input("📱 Número de celular (10 dígitos):", max_chars=10)
        nombre_paciente = st.text_input("👤 Nombre completo del paciente:")
        numero_economico = st.text_input("🏥 Número económico:", placeholder="Ej: NE-001, ECO-123")
        
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
                st.error("❌ El ID debe ser un número de celular de 10 dígitos")
            elif not all([nombre_paciente, numero_economico, presion_arterial, temperatura, oximetria]):
                st.error("❌ Complete todos los campos obligatorios")
            else:
                data = {
                    'timestamp': timestamp,
                    'id_paciente': id_paciente,
                    'nombre_paciente': nombre_paciente.strip(),
                    'numero_economico': numero_economico.strip(),
                    'presion_arterial': presion_arterial.strip(),
                    'temperatura': temperatura.strip(),
                    'oximetria': oximetria.strip()
                }
                
                if save_record(data, ecg_file):
                    st.balloons()
                    time.sleep(2)
                    st.rerun()

if __name__ == "__main__":
    main()
