"""
🏠 MAIN WINDOW - Ventana principal NYX
=======================================
Ventana principal completamente integrada con ConfigWindow.
Controla todo el sistema de control por gestos.
"""

import sys
import time
import cv2
import webbrowser
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame,
    QStatusBar, QMenuBar, QMenu,
    QMessageBox, QApplication, QComboBox, QCheckBox,
    QSlider, QTextEdit, QLineEdit, QSystemTrayIcon,
    QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QAction, QImage

from ui.styles import styles, get_color, get_font
from ui.config_window import ConfigWindow
from core.profile_manager import ProfileManager
from ui.profile_manager_window import ProfileManagerWindow
from ui.quick_script_menu import QuickScriptMenu
from utils.logger import logger
from utils.config_loader import config
from core.gesture_pipeline import GesturePipeline


class CameraView(QFrame):
    """Widget para mostrar la cámara con superposición de gestos."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CameraView")
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Etiqueta para la imagen de la cámara
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.layout.addWidget(self.image_label)
        
        # Etiqueta para información
        self.info_label = QLabel("Cámara no inicializada")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet(f"color: {get_color('text_secondary')};")
        self.layout.addWidget(self.info_label)
        
        # Estado de la cámara
        self.is_camera_active = False
        self.current_frame = None
        self.current_gestures = {}
    
    def update_frame(self, frame, gestures: Dict[str, Any] = None):
        """
        Actualiza el frame mostrado.
        
        Args:
            frame: Imagen de la cámara
            gestures: Información de gestos detectados
        """
        if frame is None:
            return
        
        # SOLO guardar datos
        self.current_frame = frame
        self.current_gestures = gestures or {}
        
        # Actualizar información
        if gestures:
            if isinstance(gestures, list):
                hand_count = len(gestures)
                # Calculate average confidence if list
                confs = [g.get('confidence', 0) for g in gestures if isinstance(g, dict)]
                confidence = sum(confs) / len(confs) if confs else 0.0
                gesture_count = len(gestures) # Simplified count
            elif isinstance(gestures, dict):
                hand_count = gestures.get('hand_count', 0)
                confidence = gestures.get('confidence', 0.0)
                gesture_count = len(gestures.get('detected_gestures', []))
            
            self.info_label.setText(
                f"Gestos: {gesture_count} | "
                f"Manos: {hand_count} | "
                f"Confianza: {confidence:.1%}"
            )
            self.info_label.setStyleSheet(f"color: {get_color('success')};")
    
    def render_frame(self, frame):
        """Renderiza un frame en el widget de cámara."""
        if frame is None or not self.isVisible():
            return
        
        try:
            # Verificar que la imagen sea válida
            if frame.size == 0:
                return
            
            h, w, ch = frame.shape
            if w == 0 or h == 0:
                return
            
            # Convertir BGR a RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            bytes_per_line = ch * w
            
            # Crear QImage
            # CRÍTICO: Usar .copy() para evitar que el recolector de basura 
            # elimine los datos antes de que QPixmap los use
            qimg = QImage(
                rgb.data,
                w,
                h,
                bytes_per_line,
                QImage.Format.Format_RGB888
            ).copy()
            
            # Crear QPixmap
            pixmap = QPixmap.fromImage(qimg)
            
            # Escalar manteniendo aspecto
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            logger.debug(f"Error renderizando frame: {e}")
    
    def set_camera_status(self, active: bool, camera_id: int = 0):
        """Actualiza el estado de la cámara."""
        self.is_camera_active = active
        
        if active:
            self.info_label.setText(f"Cámara {camera_id} activa")
            self.info_label.setStyleSheet(f"color: {get_color('success')};")
        else:
            self.info_label.setText("Cámara inactiva")
            self.info_label.setStyleSheet(f"color: {get_color('error')};")

    def clear_view(self):
        """Limpia la vista de cámara de forma segura."""
        try:
            # Limpiar datos
            self.current_frame = None
            self.current_gestures = {}
            
            # Limpiar UI de forma segura
            if self.image_label:
                self.image_label.clear()
            
            self.info_label.setText("Cámara detenida")
            self.info_label.setStyleSheet(f"color: {get_color('text_secondary')};")
            
        except Exception as e:
            logger.debug(f"Error limpiando vista de cámara: {e}")


class GestureStatusWidget(QGroupBox):
    """Widget para mostrar el estado de los gestos."""
    
    def __init__(self, parent=None):
        super().__init__("Estado de Gestos", parent)
        self.setObjectName("GestureStatus")
        
        layout = QGridLayout()
        self.setLayout(layout)
        
        # Stats removed, keeping clean UI
        pass
        
        # Último gesto detectado
        self.last_gesture_label = QLabel("Último gesto: Ninguno")
        self.last_gesture_label.setFont(get_font('subheading'))
        layout.addWidget(self.last_gesture_label, 2, 0, 1, 2)
        
        # Acción ejecutada
        self.last_action_label = QLabel("Última acción: Ninguna")
        self.last_action_label.setFont(get_font('body'))
        layout.addWidget(self.last_action_label, 3, 0, 1, 2)
        
        # Tiempo desde último gesto
        self.time_label = QLabel("Tiempo: 0.0s")
        layout.addWidget(self.time_label, 4, 0, 1, 2)
        
        self.last_update_time = time.time()
    
    # Removed _create_status_widget and update_detector_status
    
    def update_detector_status(self, detector_name: str, active: bool, confidence: float = 0.0):
        # Stub method to prevent errors if called elsewhere
        pass
    
    def update_gesture_info(self, gesture_name: str, action: str = ""):
        """Actualiza información del último gesto."""
        self.last_gesture_label.setText(f"Último gesto: {gesture_name}")
        
        if action:
            self.last_action_label.setText(f"Última acción: {action}")
        
        current_time = time.time()
        elapsed = current_time - self.last_update_time
        self.time_label.setText(f"Tiempo: {elapsed:.1f}s")
        
        # Resetear timer
        self.last_update_time = current_time
    
    def reset(self):
        """Reinicia todos los estados."""
        # Resetear todos los estados
        pass
        
        self.last_gesture_label.setText("Último gesto: Ninguno")
        self.last_action_label.setText("Última acción: Ninguna")
        self.time_label.setText("Tiempo: 0.0s")
        self.last_update_time = time.time()


class ProfileSelector(QGroupBox):
    """Selector de perfiles."""
    
    profile_changed = pyqtSignal(str)  # Señal cuando cambia el perfil
    
    def __init__(self, parent=None):
        super().__init__("Perfil Activo", parent)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Combo box para seleccionar perfil
        self.profile_combo = QComboBox()
        self.profile_combo.setFont(get_font('body'))
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        layout.addWidget(self.profile_combo)
        
        # Descripción del perfil
        self.description_label = QLabel("Selecciona un perfil para comenzar")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(f"""
            color: {get_color('text_secondary')};
            padding: 10px;
            background-color: {get_color('surface')};
            border-radius: 4px;
        """)
        layout.addWidget(self.description_label)
        
        # Botón para gestionar perfiles
        self.manage_button = QPushButton("Gestionar Perfiles...")
        self.manage_button.clicked.connect(self._open_profile_manager)
        layout.addWidget(self.manage_button)
        
        # Cargar perfiles
        self.load_profiles()
    
    def load_profiles(self):
        """Carga los perfiles disponibles."""
        self.profile_combo.clear()
        
        try:
            from core.profile_manager import ProfileManager
            profile_manager = ProfileManager()
            # Forzar recarga para detectar nuevos archivos JSON
            profile_manager.load_all_profiles()
            profiles = profile_manager.get_profile_names()
            
            if not profiles:
                self.profile_combo.addItem("Sin perfiles")
                self.profile_combo.setEnabled(False)
                return
            
            self.profile_combo.setEnabled(True)
            for profile in profiles:
                self.profile_combo.addItem(profile)
            
            # Seleccionar el primero o el último usado
            # Usar el config singleton para persistencia de settings
            from utils.config_loader import config
            last_profile = config.get_setting('app.last_profile')
            
            if last_profile and last_profile in profiles:
                self.profile_combo.setCurrentText(last_profile)
            elif profiles:
                self.profile_combo.setCurrentIndex(0)
        except Exception as e:
            logger.error(f"Error cargando perfiles en selector: {e}")
            self.profile_combo.addItem("Error cargando perfiles")
            self.profile_combo.setEnabled(False)
    
    def _on_profile_changed(self, profile_name: str):
        """Manejador cuando cambia el perfil."""
        if profile_name and profile_name != "Sin perfiles":
            self.profile_changed.emit(profile_name)
            
            # Actualizar descripción
            profile_data = config.get_profile(profile_name)
            if profile_data:
                desc = profile_data.get('description', 'Sin descripción')
                self.description_label.setText(desc)
            else:
                self.description_label.setText("Perfil sin descripción")
            
            # Guardar como último perfil usado
            config.update_setting('app.last_profile', profile_name)
            config.save_settings()
    
    def _open_profile_manager(self):
        """Abre el gestor de perfiles."""
        # Esto se conectará desde MainWindow
        pass
    
    def get_current_profile(self) -> str:
        """Obtiene el perfil actualmente seleccionado."""
        return self.profile_combo.currentText()
    
    def set_profile(self, profile_name: str):
        """Establece un perfil específico."""
        index = self.profile_combo.findText(profile_name)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)


class ControlPanel(QGroupBox):
    """Panel de control principal."""
    
    def __init__(self, parent=None):
        super().__init__("Controles", parent)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Botón de inicio/detención
        self.toggle_button = QPushButton("▶ Iniciar Sistema")
        self.toggle_button.setFont(get_font('heading'))
        self.toggle_button.setStyleSheet("""
            QPushButton {
                padding: 15px;
                font-size: 14pt;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)
        layout.addWidget(self.toggle_button)
        
        # Estado del sistema
        self.status_label = QLabel("Sistema detenido")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Configuración rápida
        config_layout = QGridLayout()
        
        # Sensibilidad
        config_layout.addWidget(QLabel("Sensibilidad:"), 0, 0)
        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        self.sensitivity_slider.setValue(70)
        config_layout.addWidget(self.sensitivity_slider, 0, 1)
        
        self.sensitivity_label = QLabel("70%")
        config_layout.addWidget(self.sensitivity_label, 0, 2)
        
        # Palabra de activación
        config_layout.addWidget(QLabel("Palabra clave:"), 1, 0)
        self.activation_word = QLineEdit("nyx")
        config_layout.addWidget(self.activation_word, 1, 1, 1, 2)
        
        # Checkboxes para detectores
        self.hand_checkbox = QCheckBox("Detección de Manos")
        self.hand_checkbox.setChecked(True)
        config_layout.addWidget(self.hand_checkbox, 2, 0, 1, 3)
        
        self.arm_checkbox = QCheckBox("Detección de Brazos")
        config_layout.addWidget(self.arm_checkbox, 3, 0, 1, 3)
        
        self.voice_checkbox = QCheckBox("Reconocimiento de Voz")
        self.voice_checkbox.setChecked(True)
        config_layout.addWidget(self.voice_checkbox, 4, 0, 1, 3)
        
        layout.addLayout(config_layout)
        
        # Botón de configuración avanzada
        self.advanced_button = QPushButton("⚙️ Configuración Avanzada...")
        self.advanced_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(self.advanced_button)
        
        # Conectar señales
        self.sensitivity_slider.valueChanged.connect(
            lambda v: self.sensitivity_label.setText(f"{v}%")
        )
    
    def set_system_status(self, running: bool):
        """Actualiza el estado del sistema."""
        if running:
            self.toggle_button.setText("⏸ Detener Sistema")
            self.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('error')};
                    color: white;
                    padding: 15px;
                    font-size: 14pt;
                    font-weight: bold;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {get_color('error_dark')};
                }}
            """)
            self.status_label.setText("Sistema activo")
            self.status_label.setStyleSheet(f"color: {get_color('success')}; font-weight: bold;")
        else:
            self.toggle_button.setText("▶ Iniciar Sistema")
            self.toggle_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('success')};
                    color: white;
                    padding: 15px;
                    font-size: 14pt;
                    font-weight: bold;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background-color: {get_color('success_dark')};
                }}
            """)
            self.status_label.setText("Sistema detenido")
            self.status_label.setStyleSheet(f"color: {get_color('text_secondary')};")
    
    def get_settings(self) -> Dict[str, Any]:
        """Obtiene la configuración actual del panel."""
        return {
            'sensitivity': self.sensitivity_slider.value() / 100.0,
            'activation_word': self.activation_word.text(),
            'hand_enabled': self.hand_checkbox.isChecked(),
            'arm_enabled': self.arm_checkbox.isChecked(),
            'voice_enabled': self.voice_checkbox.isChecked()
        }
    
    def load_settings(self, settings: Dict[str, Any]):
        """Carga configuración en el panel."""
        if 'sensitivity' in settings:
            self.sensitivity_slider.setValue(int(settings['sensitivity'] * 100))
        
        if 'activation_word' in settings:
            self.activation_word.setText(settings['activation_word'])
        
        if 'hand_enabled' in settings:
            self.hand_checkbox.setChecked(settings['hand_enabled'])
        
        if 'arm_enabled' in settings:
            self.arm_checkbox.setChecked(settings['arm_enabled'])
        
        if 'voice_enabled' in settings:
            self.voice_checkbox.setChecked(settings['voice_enabled'])


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación NYX."""
    
    # Señales principales
    system_started = pyqtSignal()
    system_stopped = pyqtSignal()
    profile_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # Configuración inicial
        self.setWindowTitle("NYX - Control por Gestos")
        self.setGeometry(100, 100, 1400, 900)
        
        # Componentes principales
        self.gesture_pipeline = None
        
        # Ventanas secundarias
        self.config_window = None
        self.profile_manager = ProfileManager()
        self.profile_window = None
        
        # Estado del sistema
        self.is_system_running = False
        self.current_profile = None
        self.last_frame_time = time.time()
        self.fps_counter = 0

        # Icono de la ventana
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "Nyx.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # Timers
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self._update_ui)

        self.pipeline_check_timer = QTimer()
        self.pipeline_check_timer.timeout.connect(self._check_pipeline_status)
        
        # Frame buffer para la cámara
        self.frame_buffer = None
        self.gesture_buffer = None
        
        # Inicializar UI
        self._init_ui()
        self._setup_menu()
        self._connect_signals()
        self._setup_tray_icon()
        
        # Cargar configuración
        self._load_config()
        
        logger.info("✅ Ventana principal de NYX inicializada")
    
    def set_gesture_pipeline(self, pipeline):
        """Establece la instancia del pipeline de gestos."""
        self.gesture_pipeline = pipeline
        logger.info("🎮 Pipeline de gestos conectado a la UI")
        
        # Conectar señal del quick menu
        if hasattr(pipeline, 'quick_menu_requested'):
            pipeline.quick_menu_requested.connect(self._on_quick_menu_requested)
            logger.info("⚡ Quick Menu conectado al pipeline")
        
    def set_profile_manager(self, manager):
        """Establece la instancia del gestor de perfiles."""
        # Si recibimos el config_loader (como sucede en main.py), lo usamos
        # pero mantenemos nuestro singleton ProfileManager si es posible.
        # En realidad, ProfileManager es un singleton, así que podemos ignorar
        # el parámetro si queremos, pero lo guardamos por compatibilidad.
        self.external_manager = manager
        logger.info("👤 Gestor de perfiles conectado a la UI")
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter izquierda-derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (cámara y estado)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Vista de cámara
        self.camera_view = CameraView()
        left_layout.addWidget(self.camera_view, 3)
        
        # Estado de gestos
        self.gesture_status = GestureStatusWidget()
        left_layout.addWidget(self.gesture_status, 1)
        
        # Panel derecho (controles)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Selector de perfil
        self.profile_selector = ProfileSelector()
        right_layout.addWidget(self.profile_selector)
        
        # Panel de control
        self.control_panel = ControlPanel()
        right_layout.addWidget(self.control_panel)
        
        # Consola de logs
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(200)
        self.log_console.setPlaceholderText("Registros del sistema NYX...")
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {get_color('surface_dark')};
                color: {get_color('text_primary')};
                font-family: 'Monospace', 'Consolas', 'Courier New';
                font-size: 11px;
                border: 1px solid {get_color('border')};
                border-radius: 4px;
                padding: 5px;
            }}
        """)
        right_layout.addWidget(self.log_console)
        
        # Agregar paneles al splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([900, 500])
        
        main_layout.addWidget(splitter)
        
        # Barra de estado
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Elementos de la barra de estado
        self.fps_label = QLabel("FPS: 0")
        self.camera_label = QLabel("Cámara: ❌")
        self.profile_label = QLabel("Perfil: Ninguno")
        self.pipeline_status_label = QLabel("Pipeline: ❌")
        self.memory_label = QLabel("Mem: --")
        
        self.status_bar.addPermanentWidget(self.memory_label)
        self.status_bar.addPermanentWidget(self.pipeline_status_label)
        self.status_bar.addPermanentWidget(self.fps_label)
        self.status_bar.addPermanentWidget(self.camera_label)
        self.status_bar.addPermanentWidget(self.profile_label)
        
        # Mostrar mensaje inicial
        self.status_bar.showMessage("NYX listo. Selecciona un perfil y haz clic en 'Iniciar Sistema'.", 5000)
        
        # Aplicar estilos
        self._apply_styles()
    
    def _apply_styles(self):
        """Aplica estilos generales a la ventana."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {get_color('background')};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {get_color('border')};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {get_color('primary')};
            }}
            QLabel {{
                color: {get_color('text_primary')};
            }}
            QPushButton {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: 4px;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {get_color('surface_hover')};
            }}
            QPushButton:pressed {{
                background-color: {get_color('surface_active')};
            }}
        """)
    
    def _setup_menu(self):
        """Configura la barra de menú."""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("📁 Archivo")
        
        new_profile_action = QAction("📄 Nuevo Perfil...", self)
        new_profile_action.triggered.connect(self._new_profile)
        new_profile_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_profile_action)
        
        load_profile_action = QAction("📂 Cargar Perfil...", self)
        load_profile_action.triggered.connect(self._load_profile)
        load_profile_action.setShortcut("Ctrl+O")
        file_menu.addAction(load_profile_action)
        
        file_menu.addSeparator()
        
        import_action = QAction("⬆️ Importar Configuración...", self)
        import_action.triggered.connect(self._import_config)
        file_menu.addAction(import_action)
        
        export_action = QAction("⬇️ Exportar Configuración...", self)
        export_action.triggered.connect(self._export_config)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        save_config_action = QAction("💾 Guardar Configuración", self)
        save_config_action.triggered.connect(self._save_config)
        save_config_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_config_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("🚪 Salir", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Ctrl+Q")
        file_menu.addAction(exit_action)
        
        # Menú Configuración
        config_menu = menubar.addMenu("⚙️ Configuración")
        
        system_config_action = QAction("🎛️ Configuración del Sistema...", self)
        system_config_action.triggered.connect(self._open_config_window)
        system_config_action.setShortcut("Ctrl+Shift+S")
        config_menu.addAction(system_config_action)
        
        config_menu.addSeparator()
        
        detectors_action = QAction("🎯 Detectores...", self)
        detectors_action.triggered.connect(lambda: self._open_config_tab('detectors'))
        config_menu.addAction(detectors_action)
        
        controllers_action = QAction("🎮 Controladores...", self)
        controllers_action.triggered.connect(lambda: self._open_config_tab('controllers'))
        config_menu.addAction(controllers_action)
        
        profiles_action = QAction("📁 Perfiles...", self)
        profiles_action.triggered.connect(lambda: self._open_config_tab('profiles'))
        config_menu.addAction(profiles_action)
        
        gestures_action = QAction("👋 Gestos...", self)
        gestures_action.triggered.connect(lambda: self._open_config_tab('gestures'))
        config_menu.addAction(gestures_action)
        
        ui_action = QAction("🎨 Interfaz...", self)
        ui_action.triggered.connect(lambda: self._open_config_tab('ui'))
        config_menu.addAction(ui_action)
        
        # Menú Herramientas
        tools_menu = menubar.addMenu("🛠️ Herramientas")
        
        recorder_action = QAction("🎥 Grabadora de Gestos...", self)
        recorder_action.triggered.connect(self._open_gesture_recorder)
        tools_menu.addAction(recorder_action)
        
        calibration_action = QAction("🎯 Calibrar Cámara...", self)
        calibration_action.triggered.connect(self._calibrate_camera)
        tools_menu.addAction(calibration_action)
        
        test_action = QAction("🧪 Probar Controladores...", self)
        test_action.triggered.connect(self._test_controllers)
        tools_menu.addAction(test_action)
        
        tools_menu.addSeparator()
        
        log_viewer_action = QAction("📊 Visor de Logs...", self)
        log_viewer_action.triggered.connect(self._show_log_viewer)
        tools_menu.addAction(log_viewer_action)
        
        # Menú Ayuda
        help_menu = menubar.addMenu("❓ Ayuda")
        
        docs_action = QAction("📚 Documentación", self)
        docs_action.triggered.connect(self._show_docs)
        docs_action.setShortcut("F1")
        help_menu.addAction(docs_action)
        
        help_menu.addSeparator()
        
        check_updates_action = QAction("🔄 Buscar Actualizaciones", self)
        check_updates_action.triggered.connect(self._check_updates)
        help_menu.addAction(check_updates_action)
        
        about_action = QAction("ℹ️ Acerca de NYX...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_tray_icon(self):
        """Configura el icono de la bandeja del sistema."""
        try:
            self.tray_icon = QSystemTrayIcon(self)
            
            # Crear menú para el icono de bandeja
            tray_menu = QMenu()
            
            show_action = QAction("Mostrar", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            hide_action = QAction("Ocultar", self)
            hide_action.triggered.connect(self.hide)
            tray_menu.addAction(hide_action)
            
            tray_menu.addSeparator()
            
            start_action = QAction("Iniciar Sistema", self)
            start_action.triggered.connect(self._toggle_system)
            tray_menu.addAction(start_action)
            
            tray_menu.addSeparator()
            
            exit_action = QAction("Salir", self)
            exit_action.triggered.connect(self.close)
            tray_menu.addAction(exit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            
            # Establecer icono
            self.tray_icon.setIcon(self.windowIcon())
            self.tray_icon.setToolTip("NYX - Control por Gestos")
            self.tray_icon.show()
            
        except Exception as e:
            logger.warning(f"No se pudo crear el icono de bandeja: {e}")
    
    def _connect_signals(self):
        """Conecta todas las señales."""
        # Botón de inicio/detención
        self.control_panel.toggle_button.clicked.connect(self._toggle_system)
        
        # Selector de perfil
        self.profile_selector.profile_changed.connect(self._on_profile_changed)
        self.profile_selector.manage_button.clicked.connect(self._open_profile_manager)
        
        # Botón de configuración avanzada
        self.control_panel.advanced_button.clicked.connect(self._open_config_window)
        
        # Conectar señales del sistema
        self.system_started.connect(self._on_system_started)
        self.system_stopped.connect(self._on_system_stopped)
    
    def _load_config(self):
        """Carga la configuración inicial."""
        try:
            # Cargar configuración del panel de control
            panel_settings = {
                'sensitivity': config.get_setting('detectors.hand.sensitivity', 0.7),
                'activation_word': config.get_setting('app.activation_word', 'nyx'),
                'hand_enabled': config.get_setting('detectors.hand.enabled', True),
                'arm_enabled': config.get_setting('detectors.arm.enabled', False),
                'voice_enabled': config.get_setting('detectors.voice.enabled', True)
            }
            self.control_panel.load_settings(panel_settings)
            
            # Actualizar perfil
            last_profile = config.get_setting('app.last_profile')
            if last_profile:
                self.profile_selector.set_profile(last_profile)
                self.current_profile = last_profile
                self.profile_label.setText(f"Perfil: {last_profile}")
            
            logger.info("Configuración cargada correctamente")
            
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
    
    # ===== MÉTODOS DE CONTROL DEL SISTEMA =====
    
    def _toggle_system(self):
        """Inicia o detiene el sistema."""
        if not self.is_system_running:
            self._start_system()
        else:
            self._stop_system()
    
    def _start_system(self):
        """Inicia el sistema de control por gestos usando GesturePipeline."""
        try:
            # 1. Verificar que haya un perfil seleccionado
            profile_name = self.profile_selector.get_current_profile()
            if not profile_name or profile_name == "Sin perfiles":
                QMessageBox.warning(
                    self, 
                    "Perfil requerido",
                    "Selecciona un perfil antes de iniciar el sistema."
                )
                return
            
            logger.info(f"🚀 Iniciando sistema NYX con perfil: {profile_name}")
            
            # 2. Obtener configuración COMPLETA del sistema
            system_config = config.get_system_config()
            
            # 3. Actualizar config con settings del panel
            panel_settings = self.control_panel.get_settings()
            
            # Actualizar detección de manos
            if 'hand_detection' in system_config:
                system_config['hand_detection']['enabled'] = panel_settings['hand_enabled']
            
            # Actualizar detección de brazos
            if 'arm_detection' in system_config:
                system_config['arm_detection']['enabled'] = panel_settings['arm_enabled']
            
            # Actualizar reconocimiento de voz
            if 'voice_recognition' in system_config:
                system_config['voice_recognition']['enabled'] = panel_settings['voice_enabled']
                system_config['voice_recognition']['activation_word'] = panel_settings['activation_word']
            
            # 4. Establecer perfil activo
            system_config['active_profile'] = profile_name
            
            logger.info("📋 Configuración del sistema cargada")
            
            # 5. Usar instancia existente o crear una nueva si es necesario
            if self.gesture_pipeline:
                logger.info("🎮 Reutilizando instancia de GesturePipeline existente")
                # Actualizar configuración si es necesario
                if hasattr(self.gesture_pipeline, 'config'):
                    self.gesture_pipeline.config.update(system_config)
            else:
                logger.warning("⚠️ No se encontró GesturePipeline configurado, creando uno nuevo...")
                self.gesture_pipeline = GesturePipeline(system_config)
            
            # 6. Conectar señales del pipeline
            if hasattr(self.gesture_pipeline, 'gesture_detected'):
                self.gesture_pipeline.gesture_detected.connect(self._on_gesture_detected)
            
            if hasattr(self.gesture_pipeline, 'action_executed'):
                self.gesture_pipeline.action_executed.connect(self._on_action_executed)
            
            if hasattr(self.gesture_pipeline, 'frame_available'):
                self.gesture_pipeline.frame_available.connect(self._on_frame_available)
            
            if hasattr(self.gesture_pipeline, 'profile_changed'):
                self.gesture_pipeline.profile_changed.connect(self._on_pipeline_profile_changed)
            
            # 7. Cargar perfil en el pipeline
            logger.info(f"🔧 Cargando perfil en pipeline: {profile_name}")
            logger.info("DEBUG: Calling internal load_profile...")
            success = self.gesture_pipeline.load_profile(profile_name)
            logger.info(f"DEBUG: Internal load_profile returned: {success}")
            
            if not success:
                raise Exception(f"No se pudo cargar el perfil: {profile_name}")
            
            # 8. Iniciar pipeline
            logger.info("DEBUG: Calling pipeline.start()...")
            success = self.gesture_pipeline.start()
            logger.info(f"DEBUG: pipeline.start() returned: {success}")
            
            if not success:
                raise Exception("No se pudo iniciar el GesturePipeline")
            
            # 9. Iniciar timers
            if not self.ui_update_timer.isActive():
                self.ui_update_timer.start(30)  # ~33 FPS para UI
            
            if not self.pipeline_check_timer.isActive():
                self.pipeline_check_timer.start(1000)  # 1 segundo para chequear estado
            
            # 10. Actualizar estado
            self.is_system_running = True
            self.current_profile = profile_name
            
            # 11. Actualizar UI
            self.control_panel.set_system_status(True)
            self.camera_view.set_camera_status(True)
            self.profile_label.setText(f"Perfil: {profile_name}")
            self.pipeline_status_label.setText("Pipeline: ✅")
            self.pipeline_status_label.setStyleSheet(f"color: {get_color('success')};")
            
            # 12. Emitir señal de sistema iniciado
            self.system_started.emit()
            
            self._log_to_console(f"🚀 Sistema NYX iniciado con perfil: {profile_name}", get_color('success'))
            self.status_bar.showMessage(f"Sistema activo - Perfil: {profile_name}", 3000)
            
            logger.info("✅ Sistema NYX iniciado exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error iniciando sistema: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error al iniciar",
                f"No se pudo iniciar el sistema:\n{str(e)}"
            )
            
            # Limpiar en caso de error
            self._cleanup_pipeline()
    
    def _stop_system(self):
        """Detiene el sistema de control por gestos."""
        try:
            logger.info("🛑 Deteniendo sistema NYX...")
            
            # 1. Detener timers
            self.ui_update_timer.stop()
            self.pipeline_check_timer.stop()
            
            # 2. Detener pipeline
            if self.gesture_pipeline:
                self.gesture_pipeline.stop()
                self.gesture_pipeline = None
            
            # 3. Actualizar estado
            self.is_system_running = False
            
            # 4. Actualizar UI
            self.control_panel.set_system_status(False)
            self.camera_view.set_camera_status(False)
            self.gesture_status.reset()
            self.pipeline_status_label.setText("Pipeline: ❌")
            self.pipeline_status_label.setStyleSheet(f"color: {get_color('error')};")
            
            # 5. Limpiar vista de cámara de forma segura
            QTimer.singleShot(0, self.camera_view.clear_view)
            self.frame_buffer = None
            self.gesture_buffer = None
            
            # 6. Emitir señal de sistema detenido
            self.system_stopped.emit()
            
            self._log_to_console("🛑 Sistema NYX detenido", get_color('text_secondary'))
            self.status_bar.showMessage("Sistema detenido", 3000)
            
            logger.info("✅ Sistema NYX detenido correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error deteniendo sistema: {e}", exc_info=True)
    
    def _cleanup_pipeline(self):
        """Limpia el pipeline en caso de error."""
        try:
            if self.gesture_pipeline:
                self.gesture_pipeline.stop()
                self.gesture_pipeline = None
        except:
            pass
        
        self.is_system_running = False
        self.control_panel.set_system_status(False)
        self.camera_view.set_camera_status(False)
        self.ui_update_timer.stop()
        self.pipeline_check_timer.stop()
    
    # ===== MÉTODOS DE SEÑALES =====
    
    def _on_frame_available(self, data: dict):
        """Manejador cuando hay un nuevo frame disponible del pipeline."""
        try:
            # Fix: La clave correcta enviada por GesturePipeline es 'image', no 'frame'
            frame = data.get('image')
            gestures = data.get('gestures', {})

            if frame is not None:
                # Almacenar en buffer para UI
                self.frame_buffer = frame.copy()
                self.gesture_buffer = gestures.copy() if gestures else {}
            
            # Actualizar FPS
            self._update_fps_counter()
            
        except Exception as e:
            logger.error(f"Error procesando frame: {e}")
    
    def _on_gesture_detected(self, gesture_data: Dict[str, Any]):
        """Manejador cuando se detecta un gesto."""
        try:
            gesture_name = gesture_data.get('gesture_name') or gesture_data.get('gesture', 'Desconocido')
            confidence = gesture_data.get('confidence', 0.0)
            action_name = gesture_data.get('action_name', '')
            
            self._log_to_console(
                f"👋 Gesto detectado: {gesture_name} ({confidence:.0%}) → {action_name}",
                get_color('gesture_active')
            )
            
            # Actualizar UI
            self.gesture_status.update_gesture_info(gesture_name, action_name)
            
            # Actualizar estado de detectores
            if 'hand_detected' in gesture_data:
                self.gesture_status.update_detector_status(
                    'Manos', 
                    gesture_data['hand_detected'],
                    gesture_data.get('hand_confidence', 0.0)
                )
            
        except Exception as e:
            logger.error(f"Error procesando gesto detectado: {e}")
    
    def _on_action_executed(self, action_data: Dict[str, Any], success: bool):
        """Manejador cuando se ejecuta una acción."""
        try:
            action_name = action_data.get('action_name', 'Desconocida')
            action_type = action_data.get('action_type', '')
            
            if success:
                self._log_to_console(
                    f"✅ Acción ejecutada: {action_name} ({action_type})",
                    get_color('success')
                )
            else:
                self._log_to_console(
                    f"❌ Falló acción: {action_name} ({action_type})",
                    get_color('error')
                )
            
        except Exception as e:
            logger.error(f"Error procesando acción ejecutada: {e}")
    
    def _on_pipeline_profile_changed(self, profile_name: str):
        """Manejador cuando el pipeline cambia de perfil."""
        logger.info(f"🔄 Pipeline cambió a perfil: {profile_name}")
        self.current_profile = profile_name
        self.profile_label.setText(f"Perfil: {profile_name}")
    
    def _on_system_started(self):
        """Manejador cuando el sistema se inicia."""
        # Notificación de bandeja
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "NYX Iniciado",
                f"Sistema de control por gestos activo\nPerfil: {self.current_profile}",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
    
    def _on_system_stopped(self):
        """Manejador cuando el sistema se detiene."""
        # Notificación de bandeja
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "NYX Detenido",
                "Sistema de control por gestos detenido",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
    
    # ===== MÉTODOS DE UI =====
    
    def _update_ui(self):
        """Actualiza la interfaz de usuario con datos del pipeline."""
        try:
            if not self.is_system_running:
                return
            
            # 1. Actualizar frame de cámara si hay datos en buffer
            if self.frame_buffer is not None:
                # Actualizar información de gestos en la vista
                self.camera_view.update_frame(self.frame_buffer, self.gesture_buffer)
                # Renderizar el frame
                self.camera_view.render_frame(self.frame_buffer)
            
            # 2. Actualizar FPS en barra de estado
            current_time = time.time()
            elapsed = current_time - self.last_frame_time
            if elapsed > 0.5:  # Actualizar cada medio segundo
                if self.fps_counter > 0:
                    fps = self.fps_counter / elapsed
                    self.fps_label.setText(f"FPS: {fps:.1f}")
                    self.fps_counter = 0
                    self.last_frame_time = current_time
            
            # 3. Actualizar uso de memoria
            self._update_memory_usage()
            
            # 4. Verificar estado del pipeline
            if hasattr(self.gesture_pipeline, 'is_running'):
                if not self.gesture_pipeline.is_running:
                    self._log_to_console("⚠️ Pipeline detenido inesperadamente", get_color('warning'))
                    self._stop_system()
            
            # 5. Actualizar estado de cámara
            if hasattr(self.gesture_pipeline, 'is_camera_active'):
                camera_active = self.gesture_pipeline.is_camera_active()
                camera_status = "✅" if camera_active else "❌"
                self.camera_label.setText(f"Cámara: {camera_status}")
                self.camera_view.set_camera_status(camera_active)
            
        except Exception as e:
            logger.error(f"❌ Error actualizando UI: {e}", exc_info=True)
    
    def _update_fps_counter(self):
        """Actualiza el contador de FPS."""
        self.fps_counter += 1
    
    def _update_memory_usage(self):
        """Actualiza el uso de memoria en la barra de estado."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_label.setText(f"Mem: {memory_mb:.1f} MB")
        except ImportError:
            self.memory_label.setText("Mem: --")
        except Exception:
            self.memory_label.setText("Mem: --")
    
    def _check_pipeline_status(self):
        """Verifica periódicamente el estado del pipeline."""
        try:
            if not self.gesture_pipeline or not self.is_system_running:
                return
            
            # Verificar si el pipeline sigue activo
            if hasattr(self.gesture_pipeline, 'is_running'):
                if not self.gesture_pipeline.is_running:
                    self._log_to_console("⚠️ Pipeline se detuvo inesperadamente", get_color('error'))
                    self._stop_system()
            
        except Exception as e:
            logger.error(f"Error verificando estado del pipeline: {e}")
    
    # ===== MÉTODOS DE PERFILES =====
    
    def _on_profile_changed(self, profile_name: str):
        """Manejador cuando cambia el perfil en el selector."""
        try:
            logger.info(f"🔄 Cambiando perfil a: {profile_name}")
            
            self.current_profile = profile_name
            self.profile_label.setText(f"Perfil: {profile_name}")
            
            # Si el sistema está corriendo, actualizar pipeline
            if self.is_system_running and self.gesture_pipeline:
                logger.info(f"🚀 Pipeline activo, cambiando perfil...")
                if hasattr(self.gesture_pipeline, 'set_active_profile'):
                    success = self.gesture_pipeline.set_active_profile(profile_name)
                    if success:
                        self._log_to_console(f"🔄 Perfil cambiado a: {profile_name}", get_color('info'))
                    else:
                        self._log_to_console(f"❌ Error cambiando perfil", get_color('error'))
            
            # Guardar como último perfil usado
            config.update_setting('app.last_profile', profile_name)
            config.save_settings()
            
            logger.info("💾 Perfil guardado en settings")
            
        except Exception as e:
            logger.error(f"Error cambiando perfil: {e}")
            self._log_to_console(f"❌ Error cambiando perfil: {str(e)}", get_color('error'))
    
    def _on_quick_menu_requested(self, profile_os: str):
        """Manejador cuando se solicita el quick menu por gesto."""
        try:
            logger.info(f"⚡ Quick Menu solicitado (OS: {profile_os})")
            
            # Crear y mostrar el modal
            quick_menu = QuickScriptMenu(profile_os=profile_os, parent=self)
            
            # Conectar señal de script ejecutado
            quick_menu.script_executed.connect(self._on_script_executed)
            
            # Mostrar modal
            quick_menu.exec()
            
        except Exception as e:
            logger.error(f"❌ Error mostrando Quick Menu: {e}")
            self._log_to_console(f"❌ Error en Quick Menu: {str(e)}", get_color('error'))
    
    def _on_script_executed(self, script_id: str):
        """Manejador cuando se ejecuta un script desde el quick menu."""
        try:
            logger.info(f"✅ Script ejecutado desde Quick Menu: {script_id}")
            self._log_to_console(f"⚡ Script ejecutado: {script_id}", get_color('success'))
        except Exception as e:
            logger.error(f"Error en callback de script ejecutado: {e}")
    
    # ===== MÉTODOS DE CONFIGURACIÓN =====
    
    def _open_config_window(self):
        """Abre la ventana de configuración."""
        try:
            if self.config_window is None:
                self.config_window = ConfigWindow(self, self.gesture_pipeline)
                
                # Conectar señal de cambios aplicados
                self.config_window.config_applied.connect(self._on_config_applied)
            
            self.config_window.show()
            self.config_window.raise_()
            
        except Exception as e:
            logger.error(f"Error abriendo ventana de configuración: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo abrir la configuración:\n{str(e)}")
    
    def _open_config_tab(self, tab_name: str):
        """Abre la ventana de configuración en una pestaña específica."""
        self._open_config_window()
        if self.config_window:
            self.config_window.show_tab(tab_name)
    
    def _on_config_applied(self, changes: dict):
        """Manejador cuando se aplican cambios desde ConfigWindow."""
        try:
            logger.info(f"📋 Aplicando cambios desde ConfigWindow: {list(changes.keys())}")
            
            if self.gesture_pipeline and self.is_system_running:
                # Reconfigurar pipeline con nuevos ajustes
                if hasattr(self.gesture_pipeline, 'reconfigure'):
                    self.gesture_pipeline.reconfigure(changes)
                
                self._log_to_console("⚙️ Configuración actualizada en tiempo real", get_color('info'))
            
            # Recargar configuración en MainWindow si es necesario
            if 'ui' in changes or 'general' in changes:
                self._load_config()
            
        except Exception as e:
            logger.error(f"Error aplicando cambios: {e}")
            self._log_to_console(f"❌ Error aplicando cambios: {str(e)}", get_color('error'))
    
    # ===== MÉTODOS DE GESTIÓN DE PERFILES =====
    
    def _open_profile_manager(self):
        """Abre el gestor de perfiles."""
        try:
            if self.profile_window is None:
                self.profile_window = ProfileManagerWindow(self.profile_manager, self)
                
                # Cuando se guarda un perfil → recargar selector
                self.profile_window.profile_saved.connect(self.profile_selector.load_profiles)
                
                # Cuando se selecciona un perfil → actualizar selector (visual)
                self.profile_window.profile_selected.connect(self.profile_selector.set_profile)
            
                # Cuando se activa un perfil → cambiar perfil activo
                self.profile_window.profile_activated.connect(self.profile_selector.set_profile)
            
            self.profile_window.show()
            self.profile_window.raise_()
            
        except Exception as e:
            logger.error(f"Error abriendo gestor de perfiles: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo abrir el gestor de perfiles:\n{str(e)}")
    
    # ===== MÉTODOS DE LOGS =====
    
    def _log_to_console(self, message: str, color: str = None):
        """Agrega un mensaje a la consola de logs."""
        try:
            timestamp = time.strftime("%H:%M:%S")
            
            if color:
                html = f'<span style="color: {color}">[{timestamp}] {message}</span>'
            else:
                html = f'<span style="color: {get_color("text_primary")}">[{timestamp}] {message}</span>'
            
            self.log_console.append(html)
            
            # Auto-scroll al final
            scrollbar = self.log_console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # Limitar cantidad de líneas
            max_lines = 500
            while self.log_console.document().lineCount() > max_lines:
                cursor = self.log_console.textCursor()
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.select(cursor.SelectionType.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
                
        except Exception as e:
            logger.error(f"Error escribiendo en consola: {e}")
    
    # ===== MÉTODOS DE MENÚ (IMPLEMENTACIÓN) =====
    
    def _new_profile(self):
        """Crea un nuevo perfil."""
        try:
            from ui.profile_editor import ProfileEditorDialog
            
            dialog = ProfileEditorDialog(self)
            if dialog.exec():
                new_profile = dialog.get_profile_data()
                # Guardar perfil
                self.profile_manager.save_profile(new_profile['name'], new_profile)
                # Recargar lista de perfiles
                self.profile_selector.load_profiles()
                self._log_to_console(f"📄 Nuevo perfil creado: {new_profile['name']}", get_color('success'))
        except ImportError:
            QMessageBox.information(self, "Función en desarrollo", "Editor de perfiles no disponible.")
        except Exception as e:
            logger.error(f"Error creando perfil: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo crear el perfil:\n{str(e)}")
    
    def _load_profile(self):
        """Carga un perfil desde archivo."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Cargar Perfil",
                "",
                "Archivos JSON (*.json);;Todos los archivos (*.*)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    import json
                    profile_data = json.load(f)
                
                profile_name = profile_data.get('profile_name', Path(file_path).stem)
                
                # Guardar en el sistema
                self.profile_manager.save_profile(profile_name, profile_data)
                
                # Recargar lista de perfiles
                self.profile_selector.load_profiles()
                
                self._log_to_console(f"📂 Perfil cargado: {profile_name}", get_color('success'))
                
        except Exception as e:
            logger.error(f"Error cargando perfil: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo cargar el perfil:\n{str(e)}")
    
    def _save_config(self):
        """Guarda la configuración actual."""
        try:
            # Guardar configuración del panel
            panel_settings = self.control_panel.get_settings()
            
            config.update_setting('detectors.hand.sensitivity', panel_settings['sensitivity'])
            config.update_setting('app.activation_word', panel_settings['activation_word'])
            config.update_setting('detectors.hand.enabled', panel_settings['hand_enabled'])
            config.update_setting('detectors.arm.enabled', panel_settings['arm_enabled'])
            config.update_setting('detectors.voice.enabled', panel_settings['voice_enabled'])
            
            config.save_settings()
            
            self._log_to_console("✅ Configuración guardada", get_color('success'))
            self.status_bar.showMessage("Configuración guardada", 3000)
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{str(e)}")
    
    def _import_config(self):
        """Importa configuración desde archivo."""
        QMessageBox.information(self, "Importar", "Función en desarrollo...")
    
    def _export_config(self):
        """Exporta configuración a archivo."""
        QMessageBox.information(self, "Exportar", "Función en desarrollo...")
    
    def _open_gesture_recorder(self):
        """Abre la grabadora de gestos."""
        QMessageBox.information(self, "Grabadora", "Función en desarrollo...")
    
    def _calibrate_camera(self):
        """Abre la calibración de cámara."""
        QMessageBox.information(self, "Calibrar", "Función en desarrollo...")
    
    def _test_controllers(self):
        """Abre la prueba de controladores."""
        QMessageBox.information(self, "Probar", "Función en desarrollo...")
    
    def _show_log_viewer(self):
        """Muestra el visor de logs avanzado."""
        QMessageBox.information(self, "Visor de Logs", "Función en desarrollo...")
    
    def _show_docs(self):
        """Muestra la documentación."""
        url = "https://lunexacorp.github.io/#/nyx/docs"
        webbrowser.open(url)
        # QMessageBox.information(self, "Documentación", "Función en desarrollo...")
    
    def _check_updates(self):
        """Busca actualizaciones."""
        QMessageBox.information(self, "Actualizaciones", "Función en desarrollo...")
    
    def _show_about(self):
        """Muestra el diálogo 'Acerca de NYX'."""
        about_text = f"""
        <div style="text-align: center;">
            <h1 style="color: {get_color('primary')}; margin-bottom: 10px;">NYX</h1>
            <h3 style="color: {get_color('text_secondary')}; margin-top: 0;">
                Sistema de Control por Gestos
            </h3>
            
            <div style="background-color: {get_color('surface')}; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p><b>Versión:</b> 2.0.0</p>
                <p><b>Arquitectura:</b> Modular y extensible</p>
                <p><b>Estado:</b> {'✅ Activo' if self.is_system_running else '⏸ Detenido'}</p>
                <p><b>Perfil actual:</b> {self.current_profile or 'Ninguno'}</p>
            </div>
            
            <div style="margin: 15px 0;">
                <h4>Módulos disponibles:</h4>
                <p>• 🎯 Detección de manos (MediaPipe)</p>
                <p>• 🎤 Reconocimiento de voz</p>
                <p>• ⌨️ Control de teclado</p>
                <p>• 🖱️ Control de mouse</p>
                <p>• 🪟 Control de ventanas</p>
                <p>• 💻 Ejecución de comandos</p>
            </div>
            
            <hr style="border-color: {get_color('border')}; margin: 20px 0;">
            
            <p style="color: {get_color('text_secondary')}; font-size: 12px;">
                Desarrollado con Python, PyQt6 y MediaPipe<br>
                © 2025 - Sistema de Control por Gestos NYX
            </p>
        </div>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Acerca de NYX")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(about_text)
        # msg_box.setIconPixmap(QPixmap(":/icons/nyx_logo.png") if hasattr(self, 'nyx_logo') else QPixmap())
        msg_box.exec()
    
    # ===== EVENTOS =====
    
    def closeEvent(self, event):
        """Manejador cuando se cierra la ventana."""
        try:
            logger.info("🔒 Cerrando aplicación NYX...")
            
            # Detener todos los timers primero
            self.ui_update_timer.stop()
            self.pipeline_check_timer.stop()
            
            # Detener sistema si está corriendo
            if self.is_system_running:
                self._stop_system()
            
            # Cerrar ventanas hijas
            if self.config_window:
                self.config_window.close()
                self.config_window = None
            
            if self.profile_window:
                self.profile_window.close()
                self.profile_window = None
            
            # Guardar configuración
            self._save_config()
            
            # Ocultar icono de bandeja
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            
            logger.info("✅ Aplicación NYX cerrada correctamente")
            event.accept()
            
        except Exception as e:
            logger.error(f"❌ Error cerrando aplicación: {e}")
            event.accept()


# Función para ejecutar la aplicación
def run_app():
    """Ejecuta la aplicación principal NYX."""
    app = QApplication(sys.argv)
    
    # Establecer información de la aplicación
    app.setApplicationName("NYX")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("NYX Project")
    
    # Aplicar tema
    styles.apply_to_app(app)
    
    # Crear y mostrar ventana principal
    window = MainWindow()
    window.show()
    
    # Ejecutar aplicación
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()