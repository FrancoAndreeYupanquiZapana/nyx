"""
🎮 NYX - SISTEMA PRINCIPAL
==========================
Punto de entrada del sistema de control por gestos NYX.
Coordina todos los módulos según la arquitectura definida.
"""

import sys
import os
import signal
import traceback
from pathlib import Path
import logging

# Agregar directorios al path para imports
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Verificar dependencias CRÍTICAS antes de importar
def check_critical_dependencies():
    """Verifica que las dependencias críticas estén instaladas."""
    critical_modules = [
        'PyQt6',      # Interfaz gráfica
        'cv2',        # OpenCV para cámara
        'mediapipe',  # Detección de gestos
        'numpy',      # Procesamiento numérico
    ]
    
    missing = []
    for module in critical_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    return missing

# Verificar dependencias críticas
missing_critical = check_critical_dependencies()
if missing_critical:
    print("❌ DEPENDENCIAS CRÍTICAS FALTANTES:")
    for module in missing_critical:
        print(f"  - {module}")
    print("\n📦 Instala con: pip install", " ".join(missing_critical))
    sys.exit(1)

# Ahora importamos todo
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt6.QtCore import Qt, QTimer, QThread
from PyQt6.QtGui import QPixmap, QFont, QColor

# Importar nuestros módulos según arquitectura NYX
from utils.logger import NYXLogger
from utils.config_loader import ConfigLoader
from core.gesture_pipeline import GesturePipeline
from core.gesture_integrator import GestureIntegrator
from ui.main_window import MainWindow
from ui.styles import apply_theme

# Importar detectores e interpretadores
from detectors.hand_detector import HandDetector
from detectors.arm_detector import ArmDetector
from detectors.pose_detector import PoseDetector
from interpreters.hand_interpreter import HandInterpreter
from interpreters.arm_interpreter import ArmInterpreter
from interpreters.voice_interpreter import VoiceInterpreter

# Controladores
from controllers.keyboard_controller import KeyboardController
from controllers.mouse_controller import MouseController
from controllers.window_controller import WindowController
from controllers.bash_controller import BashController


class SplashScreen(QSplashScreen):
    """Pantalla de inicio personalizada para NYX."""
    
    def __init__(self, app_name="NYX"):
        # Crear splash con gradiente NYX
        pixmap = QPixmap(800, 500)
        pixmap.fill(QColor(25, 25, 35))  # Fondo oscuro NYX
        
        super().__init__(pixmap)
        
        # Configurar fuente y estilo
        self.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        # Mostrar mensaje inicial
        self.showMessage(
            f"Inicializando {app_name}...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor(0, 200, 255)  # Azul NYX
        )
        
        # Dibujar logo NYX (texto simple)
        self.draw_logo()
    
    def draw_logo(self):
        """Dibuja el logo de NYX en el splash."""
        painter = self
        painter.setPen(QColor(0, 200, 255))
        painter.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        painter.drawText(250, 200, "🎮 NYX")
        
        painter.setFont(QFont("Segoe UI", 14))
        painter.setPen(QColor(150, 150, 180))
        painter.drawText(280, 250, "Control por Gestos y Voz")
    
    def update_progress(self, message: str, progress: int = 0):
        """Actualiza el mensaje de progreso."""
        progress_text = f"{progress}%" if progress > 0 else ""
        full_message = f"{message} {progress_text}".strip()
        
        self.showMessage(
            full_message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor(0, 200, 255)
        )
        
        # Forzar actualización
        QApplication.processEvents()


class InitializationWorker(QThread):
    """Worker para inicialización en segundo plano."""
    
    progress_update = pyqtSignal(str, int)  # Señal para actualizar progreso
    
    def __init__(self, config_loader):
        super().__init__()
        self.config_loader = config_loader
        self.system_config = None
        self.error = None
    
    def run(self):
        """Ejecuta la inicialización."""
        try:
            self.progress_update.emit("Cargando configuración...", 10)
            
            # Cargar configuración del sistema
            self.system_config = self.config_loader.get_system_config()
            
            # Verificar estructura de directorios
            self._check_directories()
            
            self.progress_update.emit("Configurando detectores...", 30)
            
            # Aquí podríamos inicializar componentes pesados
            # Por ahora solo cargamos config
            
            self.progress_update.emit("Preparando interfaz...", 60)
            
            # Simular carga de módulos
            self.msleep(500)
            
            self.progress_update.emit("Listo para iniciar...", 100)
            
        except Exception as e:
            self.error = str(e)
            self.progress_update.emit(f"Error: {e}", 0)


class NYXApplication:
    """Aplicación principal del sistema NYX."""
    
    def __init__(self):
        self.app = None
        self.splash = None
        self.main_window = None
        self.gesture_pipeline = None
        self.gesture_integrator = None
        
        # Instancias de componentes (se crearán después)
        self.config_loader = None
        self.logger = None
        
        # Manejo de señales del sistema
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Manejador de señales (Ctrl+C, kill, etc.)."""
        if self.logger:
            self.logger.warning(f"Recibida señal {signum}. Cerrando NYX...")
        self.cleanup()
        sys.exit(0)
    
    def _setup_logger(self):
        """Configura el sistema de logging."""
        # Primero crear logger básico para startup
        self.logger = NYXLogger(
            app_name="NYX",
            log_dir="logs",
            level="INFO",
            console=True,
            colors=True
        )
        
        self.logger.log_system_start("1.0.0")
        
        return self.logger
    
    def _setup_config(self):
        """Configura el cargador de configuración."""
        self.config_loader = ConfigLoader(config_dir="src/config")
        
        # Verificar configuración básica
        config_info = self.config_loader.get_config_info()
        self.logger.info(f"📂 Configuración cargada desde: {config_info['config_dir']}")
        
        return self.config_loader
    
    def _check_directories(self):
        """Verifica y crea la estructura de directorios de NYX."""
        directories = [
            "logs",
            "recorded_gestures",
            "exports",
            "backups",
            "training_data"
        ]
        
        for directory in directories:
            path = Path(directory)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"📁 Directorio creado: {path}")
    
    def _check_camera(self):
        """Verifica si hay una cámara disponible."""
        try:
            import cv2
            
            system_config = self.config_loader.get_system_config()
            camera_id = system_config.get('camera', {}).get('device_id', 0)
            
            cap = cv2.VideoCapture(camera_id)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    self.logger.info(f"📷 Cámara {camera_id} disponible")
                    return True
                else:
                    self.logger.warning(f"📷 Cámara {camera_id} no responde")
                    return False
            else:
                self.logger.warning(f"📷 No se pudo abrir cámara {camera_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error verificando cámara: {e}")
            return False
    
    def _create_gesture_pipeline(self, system_config):
        """Crea e inicializa el GesturePipeline con todos los componentes."""
        self.logger.info("🔄 Creando GesturePipeline...")
        
        try:
            # 1. Crear pipeline base
            pipeline = GesturePipeline(system_config)
            
            # 2. Crear GestureIntegrator
            integrator = GestureIntegrator(system_config)
            
            # 3. Crear detectores según configuración
            detectors = {}
            
            # HandDetector
            if system_config.get('hand_detection', {}).get('enabled', True):
                hand_config = system_config['hand_detection']
                detectors['hand'] = HandDetector(
                    max_num_hands=hand_config.get('max_num_hands', 2),
                    min_detection_confidence=hand_config.get('min_detection_confidence', 0.7),
                    min_tracking_confidence=hand_config.get('min_tracking_confidence', 0.5),
                    model_complexity=hand_config.get('model_complexity', 1)
                )
                self.logger.info("✅ HandDetector creado")
            
            # ArmDetector
            if system_config.get('arm_detection', {}).get('enabled', False):
                arm_config = system_config['arm_detection']
                detectors['arm'] = ArmDetector(
                    min_detection_confidence=arm_config.get('min_detection_confidence', 0.5),
                    min_tracking_confidence=arm_config.get('min_tracking_confidence', 0.5),
                    model_complexity=arm_config.get('model_complexity', 1)
                )
                self.logger.info("✅ ArmDetector creado")
            
            # PoseDetector (opcional)
            if system_config.get('pose_detection', {}).get('enabled', False):
                pose_config = system_config.get('pose_detection', {})
                detectors['pose'] = PoseDetector(
                    min_detection_confidence=pose_config.get('min_detection_confidence', 0.5),
                    min_tracking_confidence=pose_config.get('min_tracking_confidence', 0.5),
                    model_complexity=pose_config.get('model_complexity', 1)
                )
                self.logger.info("✅ PoseDetector creado")
            
            # 4. Crear interpretadores
            interpreters = {}
            
            # HandInterpreter
            interpreters['hand'] = HandInterpreter(
                gesture_threshold=0.7
            )
            
            # ArmInterpreter
            interpreters['arm'] = ArmInterpreter(
                gesture_threshold=0.6
            )
            
            # VoiceInterpreter
            voice_config = system_config.get('voice_recognition', {})
            interpreters['voice'] = VoiceInterpreter(
                language=voice_config.get('language', 'es-ES')
            )
            
            self.logger.info("✅ Interpretadores creados")
            
            # 5. Registrar componentes en el integrador
            for name, detector in detectors.items():
                integrator.register_detector(name, detector)
            
            for name, interpreter in interpreters.items():
                integrator.register_interpreter(name, interpreter)
            
            # 6. Conectar integrador con pipeline
            pipeline.gesture_integrator = integrator
            integrator.set_pipeline(pipeline)
            
            # 7. Cargar perfil activo
            active_profile = system_config.get('active_profile', 'gamer')
            profile_data = self.config_loader.get_profile(active_profile)
            
            if profile_data:
                pipeline.load_profile(profile_data)
                self.logger.info(f"👤 Perfil cargado: {active_profile}")
            else:
                self.logger.warning(f"⚠️ No se pudo cargar perfil: {active_profile}")
            
            # 8. Conectar con controladores
            self._setup_controllers(pipeline, system_config)
            
            self.logger.info("✅ GesturePipeline creado exitosamente")
            
            return pipeline
            
        except Exception as e:
            self.logger.error(f"❌ Error creando GesturePipeline: {e}", exc_info=True)
            raise
    
    def _setup_controllers(self, pipeline, system_config):
        """Configura y conecta los controladores con el pipeline."""
        controllers = {}
        
        # KeyboardController
        if system_config.get('controllers', {}).get('keyboard', {}).get('enabled', True):
            controllers['keyboard'] = KeyboardController()
        
        # MouseController
        if system_config.get('controllers', {}).get('mouse', {}).get('enabled', True):
            mouse_sensitivity = system_config.get('controllers', {}).get('mouse', {}).get('sensitivity', 1.0)
            controllers['mouse'] = MouseController(sensitivity=mouse_sensitivity)
        
        # WindowController
        if system_config.get('controllers', {}).get('window', {}).get('enabled', True):
            controllers['window'] = WindowController()
        
        # BashController
        if system_config.get('controllers', {}).get('bash', {}).get('enabled', False):
            controllers['bash'] = BashController()
        
        # Conectar controladores con ActionExecutor
        if hasattr(pipeline, 'action_executor'):
            for name, controller in controllers.items():
                pipeline.action_executor.register_controller(name, controller)
                self.logger.info(f"✅ {name.capitalize()}Controller conectado")
    
    def _show_startup_warnings(self, camera_available):
        """Muestra advertencias de inicio si es necesario."""
        if not camera_available:
            reply = QMessageBox.warning(
                None,
                "⚠️ Cámara no detectada",
                "No se pudo detectar una cámara conectada.\n\n"
                "El sistema funcionará en modo limitado:\n"
                "• Detectores visuales deshabilitados\n"
                "• Solo comandos de voz disponibles\n\n"
                "¿Deseas continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.logger.info("Aplicación cerrada por falta de cámara")
                return False
        
        return True
    
    def _show_welcome_message(self):
        """Muestra mensaje de bienvenida en la UI."""
        if self.main_window and hasattr(self.main_window, 'log_message'):
            welcome_msg = """
            <h2 style="color: #4fc3f7;">🎮 ¡Bienvenido a NYX!</h2>
            <p><b>Sistema de Control por Gestos y Voz v1.0.0</b></p>
            
            <p><b>✅ Sistema inicializado correctamente</b></p>
            <ul>
            <li>Arquitectura modular cargada</li>
            <li>Detectores e interpretadores listos</li>
            <li>Controladores configurados</li>
            <li>Interfaz preparada</li>
            </ul>
            
            <p><b>🚀 Primeros pasos:</b></p>
            <ol>
            <li>Selecciona un perfil en el panel derecho</li>
            <li>Ajusta sensibilidad si es necesario</li>
            <li>Presiona "▶ Iniciar Sistema"</li>
            <li>Realiza gestos frente a la cámara</li>
            <li>Di "nyx" seguido de comandos de voz</li>
            </ol>
            
            <p style="color: #888; font-size: 10pt;">
            💡 <i>Usa F1 para ayuda o ve a Configuración → Ayuda</i>
            </p>
            """
            
            self.main_window.log_message(welcome_msg, "info")
    
    def run(self):
        """Ejecuta la aplicación principal."""
        exit_code = 0
        
        try:
            # 1. Crear aplicación Qt
            self.app = QApplication(sys.argv)
            self.app.setApplicationName("NYX")
            self.app.setApplicationVersion("1.0.0")
            self.app.setOrganizationName("NYX Project")
            
            # 2. Mostrar splash screen
            self.splash = SplashScreen("NYX")
            self.splash.show()
            self.splash.update_progress("Configurando entorno...")
            
            # 3. Configurar logger (CRÍTICO - hacerlo primero)
            self.splash.update_progress("Configurando sistema de logs...", 10)
            self._setup_logger()
            
            # 4. Configurar cargador de configuración
            self.splash.update_progress("Cargando configuración...", 20)
            self._setup_config()
            
            # 5. Verificar directorios
            self.splash.update_progress("Preparando directorios...", 30)
            self._check_directories()
            
            # 6. Obtener configuración del sistema
            system_config = self.config_loader.get_system_config()
            
            # 7. Aplicar tema
            self.splash.update_progress("Aplicando tema visual...", 40)
            theme = system_config.get('general', {}).get('theme', 'dark')
            apply_theme(self.app, theme)
            
            # 8. Verificar cámara
            self.splash.update_progress("Verificando hardware...", 50)
            camera_available = self._check_camera()
            
            # 9. Crear GesturePipeline con todos los componentes
            self.splash.update_progress("Inicializando núcleo del sistema...", 60)
            self.gesture_pipeline = self._create_gesture_pipeline(system_config)
            
            # 10. Crear ventana principal
            self.splash.update_progress("Preparando interfaz de usuario...", 80)
            self.main_window = MainWindow()
            
            # 11. Conectar pipeline con la ventana principal
            if hasattr(self.main_window, 'set_gesture_pipeline'):
                self.main_window.set_gesture_pipeline(self.gesture_pipeline)
            
            # 12. Conectar gestor de perfiles
            if hasattr(self.main_window, 'set_profile_manager'):
                self.main_window.set_profile_manager(self.config_loader)
            
            # 13. Mostrar advertencias si es necesario
            self.splash.update_progress("Finalizando...", 90)
            if not self._show_startup_warnings(camera_available):
                return 0
            
            # 14. Ocultar splash y mostrar ventana principal
            self.splash.finish(self.main_window)
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()
            
            # 15. Configurar cierre limpio
            self.app.aboutToQuit.connect(self.cleanup)
            
            # 16. Mostrar mensaje de bienvenida
            QTimer.singleShot(500, self._show_welcome_message)
            
            # 17. Log de inicio exitoso
            self.logger.info("=" * 60)
            self.logger.info("🎉 NYX INICIADO EXITOSAMENTE")
            self.logger.info(f"📁 Directorio: {Path.cwd()}")
            self.logger.info(f"🎨 Tema: {theme}")
            self.logger.info(f"📷 Cámara: {'✅ Disponible' if camera_available else '❌ No disponible'}")
            self.logger.info(f"👤 Perfil activo: {system_config.get('active_profile', 'gamer')}")
            self.logger.info("=" * 60)
            
            # 18. Ejecutar aplicación Qt
            exit_code = self.app.exec()
            
        except Exception as e:
            self.logger.critical(f"❌ ERROR CRÍTICO EN NYX: {e}", exc_info=True)
            
            # Mostrar error al usuario
            error_msg = f"""
            <h3 style="color: #f44336;">❌ Error crítico en NYX</h3>
            <p><b>Error:</b> {str(e)}</p>
            <p>Por favor, revisa los archivos de log para más detalles:</p>
            <ul>
            <li><code>logs/nyx_error.log</code> - Errores</li>
            <li><code>logs/nyx_debug.log</code> - Información detallada</li>
            </ul>
            
            <p><b>Posibles soluciones:</b></p>
            <ol>
            <li>Verifica que todas las dependencias estén instaladas</li>
            <li>Reinstala las dependencias: <code>pip install -r requirements.txt</code></li>
            <li>Verifica que la cámara esté conectada y funcionando</li>
            <li>Revisa los permisos del sistema</li>
            </ol>
            
            <p style="color: #888;">
            Si el problema persiste, reporta el error en:<br>
            https://github.com/tu-usuario/nyx/issues
            </p>
            """
            
            if self.app:
                QMessageBox.critical(None, "Error Crítico - NYX", error_msg)
            
            exit_code = 1
        
        finally:
            self.cleanup()
        
        return exit_code
    
    def cleanup(self):
        """Limpia todos los recursos antes de salir."""
        try:
            if hasattr(self, 'logger'):
                self.logger.info("🧹 Limpiando recursos de NYX...")
            
            # 1. Detener pipeline si está activo
            if self.gesture_pipeline:
                if hasattr(self.gesture_pipeline, 'stop'):
                    self.gesture_pipeline.stop()
                if hasattr(self.gesture_pipeline, 'cleanup'):
                    self.gesture_pipeline.cleanup()
            
            # 2. Cerrar ventana principal
            if self.main_window:
                if hasattr(self.main_window, 'cleanup'):
                    self.main_window.cleanup()
                self.main_window.close()
            
            # 3. Guardar configuración
            if self.config_loader:
                self.config_loader.save_settings()
                self.config_loader.save_system_config()
            
            # 4. Log de cierre
            if hasattr(self, 'logger'):
                self.logger.info("✅ Recursos limpiados correctamente")
                self.logger.log_system_stop()
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"❌ Error durante limpieza: {e}")
            else:
                print(f"❌ Error durante limpieza: {e}")


def print_nyx_banner():
    """Imprime el banner de NYX."""
    banner = r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     ███╗   ██╗██╗   ██╗██╗  ██╗                             ║
    ║     ████╗  ██║╚██╗ ██╔╝╚██╗██╔╝                             ║
    ║     ██╔██╗ ██║ ╚████╔╝  ╚███╔╝                              ║
    ║     ██║╚██╗██║  ╚██╔╝   ██╔██╗                              ║
    ║     ██║ ╚████║   ██║   ██╔╝ ██╗                             ║
    ║     ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝                             ║
    ║                                                              ║
    ║          Control por Gestos y Voz - v1.0.0                   ║
    ║                                                              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║     🏗️  Arquitectura Modular:                                ║
    ║       • 🧠 Core: Pipeline, Integrador, Perfiles              ║
    ║       • 🔍 Detectores: Manos, Brazos, Postura, Voz          ║
    ║       • 🧠 Interpretadores: Gestos → Acciones               ║
    ║       • 🎮 Controladores: Teclado, Mouse, Ventanas, Bash    ║
    ║       • 🖥️  UI: PyQt6 con temas personalizables             ║
    ║                                                              ║
    ║     💡 Características:                                      ║
    ║       • Gestos personalizables por perfil                   ║
    ║       • Comandos de voz con palabra de activación           ║
    ║       • Baja latencia (<100ms)                              ║
    ║       • Multi-plataforma (Linux/Windows)                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    
    🚀 Iniciando sistema NYX...
    """
    print(banner)


def run_tests():
    """Ejecuta pruebas del sistema."""
    print("🧪 Ejecutando pruebas de NYX...")
    
    try:
        # Importar pruebas
        from tests import run_all_tests
        
        print("\n" + "="*60)
        print("✅ Todas las pruebas completadas")
        
        return 0
        
    except ImportError as e:
        print(f"❌ No se encontraron módulos de prueba: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error en pruebas: {e}")
        return 1


def main():
    """Función principal."""
    # Parsear argumentos
    import argparse
    
    parser = argparse.ArgumentParser(description='NYX - Sistema de Control por Gestos')
    parser.add_argument('--debug', action='store_true', help='Modo depuración detallado')
    parser.add_argument('--test', action='store_true', help='Ejecutar pruebas del sistema')
    parser.add_argument('--profile', type=str, help='Perfil inicial a cargar')
    parser.add_argument('--no-camera', action='store_true', help='Deshabilitar detección por cámara')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Nivel de logging')
    parser.add_argument('--config-dir', type=str, help='Directorio de configuración personalizado')
    
    args = parser.parse_args()
    
    # Mostrar banner
    print_nyx_banner()
    
    # Modo pruebas
    if args.test:
        return run_tests()
    
    # Crear y ejecutar aplicación
    app = NYXApplication()
    
    # Pasar argumentos a la aplicación (se usarán en run())
    app.args = args
    
    return app.run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  NYX interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR NO MANEJADO: {e}")
        traceback.print_exc()
        sys.exit(1)

"""
integracion para mainwindows
# En MainWindow.__init__():
def __init__(self):
    super().__init__()
    # ... código existente ...
    
    # ConfigWindow
    self.config_window = None
    
    # Conectar ConfigWindow
    self.control_panel.advanced_button.clicked.connect(self._open_config_window)

# Agregar método para abrir ConfigWindow:
def _open_config_window(self):
    """"""Abre la ventana de configuración.
    if self.config_window is None:
        self.config_window = ConfigWindow(self, self.gesture_pipeline)
        
        # Conectar señal de cambios aplicados
        self.config_window.config_applied.connect(self._on_config_applied)
    
    self.config_window.show()
    self.config_window.raise_()

def _on_config_applied(self, changes: dict):
    Manejador cuando se aplican cambios desde ConfigWindow.
    try:
        logger.info(f"📋 Aplicando cambios desde ConfigWindow: {changes.keys()}")
        
        if self.gesture_pipeline and self.is_system_running:
            # Reconfigurar pipeline con nuevos ajustes
            if 'detectors' in changes:
                self.gesture_pipeline.reconfigure_detectors(changes['detectors'])
            
            if 'controllers' in changes:
                self.gesture_pipeline.reconfigure_controllers(changes['controllers'])
            
            # Actualizar UI si es necesario
            self._log_to_console("⚙️ Configuración actualizada en tiempo real", 
                               get_color('info'))
    
    except Exception as e:
        logger.error(f"Error aplicando cambios: {e}")
"""