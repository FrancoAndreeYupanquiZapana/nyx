"""
🏠 MAIN WINDOW - Ventana principal
==================================
Ventana principal del sistema de control por gestos.
Solo consume datos del GesturePipeline (arquitectura moderna).
"""

import sys
import time
from typing import Dict, Any, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTabWidget, QLabel, QPushButton,
    QGroupBox, QGridLayout, QStackedWidget, QFrame,
    QStatusBar, QMenuBar, QMenu, QToolBar,
    QMessageBox, QApplication, QComboBox, QCheckBox,
    QSlider, QSpinBox, QTextEdit, QListWidget, QListWidgetItem,
    QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QAction

from ui.styles import styles, get_color, get_font
from ui.config_window import ConfigWindow
from core.profile_manager import ProfileManager
from ui.profile_manager_window import ProfileManagerWindow
from utils.logger import logger
from utils.config_loader import config
from core.gesture_pipeline import GesturePipeline
from core.voice_recognizer import VoiceRecognizer
from core.action_executor import ActionExecutor


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
    
    def update_frame(self, frame, gestures: Dict[str, Any] = None):
        """
        Actualiza el frame mostrado.
        
        Args:
            frame: Imagen de la cámara
            gestures: Información de gestos detectados
        """
        if frame is None:
            return
        
        self.current_frame = frame
        
        # Convertir frame a QPixmap
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        from PyQt6.QtGui import QImage
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        
        # Escalar manteniendo aspecto
        self.image_label.setPixmap(pixmap.scaled(
            self.image_label.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        ))
        
        # Actualizar información
        if gestures:
            self.info_label.setText(
                f"Gestos: {len(gestures)} | "
                f"Manos: {gestures.get('hand_count', 0)} | "
                f"Confianza: {gestures.get('confidence', 0):.2f}"
            )
    
    def set_camera_status(self, active: bool, camera_id: int = 0):
        """Actualiza el estado de la cámara."""
        self.is_camera_active = active
        
        if active:
            self.info_label.setText(f"Cámara {camera_id} activa")
            self.info_label.setStyleSheet(f"color: {get_color('success')};")
        else:
            self.info_label.setText("Cámara inactiva")
            self.info_label.setStyleSheet(f"color: {get_color('error')};")


class GestureStatusWidget(QGroupBox):
    """Widget para mostrar el estado de los gestos."""
    
    def __init__(self, parent=None):
        super().__init__("Estado de Gestos", parent)
        self.setObjectName("GestureStatus")
        
        layout = QGridLayout()
        self.setLayout(layout)
        
        # Indicadores por tipo de detector
        self.detector_status = {}
        
        # Manos
        self.hand_status = self._create_status_widget("Manos", "hand_detected")
        layout.addWidget(self.hand_status, 0, 0)
        
        # Brazos
        self.arm_status = self._create_status_widget("Brazos", "arm_detected")
        layout.addWidget(self.arm_status, 0, 1)
        
        # Voz
        self.voice_status = self._create_status_widget("Voz", "voice_active")
        layout.addWidget(self.voice_status, 1, 0)
        
        # Postura
        self.pose_status = self._create_status_widget("Postura", "accent")
        layout.addWidget(self.pose_status, 1, 1)
        
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
    
    def _create_status_widget(self, name: str, color_name: str) -> QWidget:
        """Crea un widget de estado individual."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Indicador de estado (círculo)
        self.detector_status[name] = {
            'active': False,
            'confidence': 0.0,
            'label': QLabel(name),
            'indicator': QLabel("●"),
            'confidence_bar': QLabel("0%")
        }
        
        status = self.detector_status[name]
        status['label'].setAlignment(Qt.AlignmentFlag.AlignCenter)
        status['indicator'].setAlignment(Qt.AlignmentFlag.AlignCenter)
        status['indicator'].setStyleSheet(f"""
            font-size: 24px;
            color: {get_color('text_disabled')};
        """)
        status['confidence_bar'].setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(status['label'])
        layout.addWidget(status['indicator'])
        layout.addWidget(status['confidence_bar'])
        
        return widget
    
    def update_detector_status(self, detector_name: str, active: bool, confidence: float = 0.0):
        """Actualiza el estado de un detector."""
        if detector_name not in self.detector_status:
            return
        
        status = self.detector_status[detector_name]
        status['active'] = active
        status['confidence'] = confidence
        
        color = get_color('gesture_active' if active else 'text_disabled')
        status['indicator'].setStyleSheet(f"""
            font-size: 24px;
            color: {color};
            font-weight: bold;
        """)
        
        status['confidence_bar'].setText(f"{confidence*100:.0f}%")
        status['confidence_bar'].setStyleSheet(f"""
            color: {get_color('text_primary')};
            font-weight: {'bold' if active else 'normal'};
        """)
    
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
        for name in self.detector_status:
            self.update_detector_status(name, False, 0.0)
        
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
        
        profiles = config.list_profiles()
        if not profiles:
            self.profile_combo.addItem("Sin perfiles")
            self.profile_combo.setEnabled(False)
            return
        
        for profile in profiles:
            self.profile_combo.addItem(profile)
        
        # Seleccionar el primero o el último usado
        last_profile = config.get_setting('app.last_profile')
        if last_profile and last_profile in profiles:
            self.profile_combo.setCurrentText(last_profile)
    
    def _on_profile_changed(self, profile_name: str):
        """Manejador cuando cambia el perfil."""
        if profile_name and profile_name != "Sin perfiles":
            self.profile_changed.emit(profile_name)
            
            # Actualizar descripción
            profile_data = config.get_profile(profile_name)
            if profile_data:
                desc = profile_data.get('description', 'Sin descripción')
                self.description_label.setText(desc)
            
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
        self.advanced_button = QPushButton("Configuración Avanzada...")
        layout.addWidget(self.advanced_button)
        
        # Conectar señales
        self.sensitivity_slider.valueChanged.connect(
            lambda v: self.sensitivity_label.setText(f"{v}%")
        )
    
    def set_system_status(self, running: bool):
        """Actualiza el estado del sistema."""
        if running:
            self.toggle_button.setText("⏸ Detener Sistema")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    padding: 15px;
                    font-size: 14pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #D32F2F;
                }
            """)
            self.status_label.setText("Sistema activo")
            self.status_label.setStyleSheet(f"color: {get_color('success')};")
        else:
            self.toggle_button.setText("▶ Iniciar Sistema")
            self.toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    padding: 15px;
                    font-size: 14pt;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #388E3C;
                }
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
    """Ventana principal de la aplicación."""
    gesture_detected = pyqtSignal(dict)
    action_executed = pyqtSignal(dict, bool)  # (action_data, success)

    def __init__(self):
        super().__init__()
        
        # Configuración inicial
        self.setWindowTitle("Gesture Control System")
        self.setGeometry(100, 100, 1400, 900)
        
        # Componentes principales
        self.gesture_pipeline = None
        
        self.config_window = None
        self.profile_manager = ProfileManager()
        self.profile_window = None
        
        # Estado
        self.is_system_running = False
        self.current_profile = None
        self.last_frame_time = time.time()
        
        # Timer para actualizaciones
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self._update_ui)

        # Timer para actualizar estado del pipeline
        self.pipeline_check_timer = QTimer()
        self.pipeline_check_timer.timeout.connect(self._check_pipeline_status)
        
        # Inicializar UI
        self._init_ui()
        self._setup_menu()
        self._connect_signals()
        
        # Cargar configuración
        self._load_config()
        
        logger.info("Ventana principal inicializada")

        # Conectar señales
        self.gesture_detected.connect(self._on_gesture_detected)
        self.action_executed.connect(self._on_action_executed)

        logger.info(" -> Ventana principal inicializada")
    
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
        
        # Consola de logs (expandible)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        self.log_console.setPlaceholderText("Logs del sistema...")
        self.log_console.setStyleSheet(f"""
            background-color: {get_color('surface_dark')};
            color: {get_color('text_primary')};
            font-family: 'Monospace';
            font-size: 11px;
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
        self.camera_label = QLabel("Cámara: Desconectada")
        self.profile_label = QLabel("Perfil: Ninguno")
        self.pipeline_status_label = QLabel("Pipeline: X")
        
        self.status_bar.addPermanentWidget(self.pipeline_status_label)
        self.status_bar.addPermanentWidget(self.fps_label)
        self.status_bar.addPermanentWidget(self.camera_label)
        self.status_bar.addPermanentWidget(self.profile_label)
        
        # Mostrar mensaje inicial
        self.status_bar.showMessage("Sistema listo. Selecciona un perfil e inicia el sistema.", 5000)
    
    def _setup_menu(self):
        """Configura la barra de menú."""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("Archivo")
        
        new_profile_action = QAction("Nuevo Perfil...", self)
        new_profile_action.triggered.connect(self._new_profile)
        file_menu.addAction(new_profile_action)
        
        load_profile_action = QAction("Cargar Perfil...", self)
        load_profile_action.triggered.connect(self._load_profile)
        file_menu.addAction(load_profile_action)
        
        file_menu.addSeparator()
        
        save_config_action = QAction("Guardar Configuración", self)
        save_config_action.triggered.connect(self._save_config)
        file_menu.addAction(save_config_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menú Configuración
        config_menu = menubar.addMenu("Configuración")
        
        detectors_action = QAction("Detectores...", self)
        detectors_action.triggered.connect(self._open_detectors_config)
        config_menu.addAction(detectors_action)
        
        controllers_action = QAction("Controladores...", self)
        controllers_action.triggered.connect(self._open_controllers_config)
        config_menu.addAction(controllers_action)
        
        gestures_action = QAction("Gestos...", self)
        gestures_action.triggered.connect(self._open_gestures_config)
        config_menu.addAction(gestures_action)
        
        config_menu.addSeparator()
        
        themes_action = QAction("Temas...", self)
        themes_action.triggered.connect(self._open_themes_config)
        config_menu.addAction(themes_action)
        
        # Menú Herramientas
        tools_menu = menubar.addMenu("Herramientas")
        
        recorder_action = QAction("Grabadora de Gestos...", self)
        recorder_action.triggered.connect(self._open_gesture_recorder)
        tools_menu.addAction(recorder_action)
        
        calibration_action = QAction("Calibrar Cámara...", self)
        calibration_action.triggered.connect(self._calibrate_camera)
        tools_menu.addAction(calibration_action)
        
        test_action = QAction("Probar Controladores...", self)
        test_action.triggered.connect(self._test_controllers)
        tools_menu.addAction(test_action)
        
        # Menú Ayuda
        help_menu = menubar.addMenu("Ayuda")
        
        docs_action = QAction("Documentación", self)
        docs_action.triggered.connect(self._show_docs)
        help_menu.addAction(docs_action)
        
        about_action = QAction("Acerca de...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        pass
    
    def _connect_signals(self):
        """Conecta todas las señales."""
        # Botón de inicio/detención
        self.control_panel.toggle_button.clicked.connect(self._toggle_system)
        
        # Selector de perfil
        self.profile_selector.profile_changed.connect(self._on_profile_changed)
        self.profile_selector.manage_button.clicked.connect(self._open_profile_manager)
        
        # Botón de configuración avanzada
        self.control_panel.advanced_button.clicked.connect(self._open_config_window)
    
    def _load_config(self):
        """Carga la configuración inicial."""
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
            
            logger.info(f"🚀 Iniciando sistema con perfil: {profile_name}")
            
            # 2. Obtener configuración COMPLETA del sistema
            system_config = config.get_system_config()
            
            # 3. Actualizar config con settings del panel
            panel_settings = self.control_panel.get_settings()
            
            system_config['hand_detection']['enabled'] = panel_settings['hand_enabled']
            system_config['arm_detection']['enabled'] = panel_settings['arm_enabled']
            system_config['voice_recognition']['enabled'] = panel_settings['voice_enabled']
            system_config['voice_recognition']['activation_word'] = panel_settings['activation_word']
            
            # 4. Establecer perfil activo
            system_config['active_profile'] = profile_name
            
            logger.info(f"📋 Configuración del sistema cargada")
            
            # 5. Crear e iniciar GesturePipeline
            self.gesture_pipeline = GesturePipeline(system_config)

            logger.info(f"🔧 Cargando perfil en pipeline: {profile_name}")
            success = self.gesture_pipeline.load_profile(profile_name)

            if not success:
                raise Exception(f"No se pudo cargar el perfil: {profile_name}")
            
            # 6. Conectar señales del pipeline
            if hasattr(self.gesture_pipeline, 'gesture_detected'):
                self.gesture_pipeline.gesture_detected.connect(self.gesture_detected)
            
            if hasattr(self.gesture_pipeline, 'action_executed'):
                self.gesture_pipeline.action_executed.connect(self.action_executed)
            
            # 7. Iniciar pipeline
            success = self.gesture_pipeline.start()
            
            if not success:
                raise Exception("No se pudo iniciar el GesturePipeline")
            
            # 8. Iniciar timers
            if hasattr(self, 'ui_update_timer'):
                self.ui_update_timer.start(30)  # ~33 FPS para UI
            elif hasattr(self, 'update_timer'):
                self.update_timer.start(30)  # Nombre alternativo
            
            self.pipeline_check_timer.start(1000)  # 1 segundo para chequear estado
            
            # 9. Actualizar estado
            self.is_system_running = True
            self.current_profile = profile_name
            
            # 10. Actualizar UI
            self.control_panel.set_system_status(True)
            self.camera_view.set_camera_status(True)
            self.profile_label.setText(f"Perfil: {profile_name}")
            self.pipeline_status_label.setText("Pipeline: ✅")
            self.pipeline_status_label.setStyleSheet(f"color: {get_color('success')};")
            
            self._log_to_console(f"🚀 Sistema iniciado con perfil: {profile_name}", get_color('success'))
            self.status_bar.showMessage(f"Sistema activo - Perfil: {profile_name}", 3000)
            
            logger.info(f"✅ Sistema iniciado exitosamente")
            
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
            logger.info("🛑 Deteniendo sistema...")
            
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
            
            # 5. Limpiar vista de cámara
            self.camera_view.update_frame(None)
            
            self._log_to_console("🛑 Sistema detenido", get_color('text_secondary'))
            self.status_bar.showMessage("Sistema detenido", 3000)
            
            logger.info("✅ Sistema detenido correctamente")
            
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


    def _update_ui(self):
        """Actualiza la interfaz de usuario con datos del pipeline."""
        try:
            if not self.gesture_pipeline or not self.is_system_running:
                return
            
            # 1. Obtener el frame más reciente del pipeline
            latest_data = self.gesture_pipeline.get_latest_frame()
            
            if not latest_data:
                # No hay datos nuevos
                return
            
            # 2. Extraer datos
            frame = latest_data.get('data')
            gestures = latest_data.get('gestures', [])
            
            # 3. Actualizar vista de cámara
            if frame is not None:
                self.camera_view.update_frame(frame, gestures)
            
            # 4. Calcular FPS simple
            current_time = time.time()
            elapsed = current_time - self.last_frame_time
            if elapsed > 0:
                fps = 1.0 / elapsed
                self.fps_label.setText(f"FPS: {fps:.1f}")
            self.last_frame_time = current_time
            
            # 5. Actualizar estado de detectores desde gestos
            #if gestures:
            #   self._update_detector_status_from_gestures(gestures)
            
            # 6. Actualizar estado del pipeline
            if hasattr(self.gesture_pipeline, 'is_running'):
                is_running = self.gesture_pipeline.is_running
                if not is_running:
                    self._log_to_console("⚠️ Pipeline detenido inesperadamente", get_color('warning'))
                    self._stop_system()
            
        except Exception as e:
            logger.error(f"❌ Error actualizando UI: {e}", exc_info=True)
    

    def _update_detector_status_from_gestures(self, gestures: Dict[str, Any]):
        """Actualiza el estado de detectores basado en gestos."""
        try:
            # Manos
            if 'hand_detected' in gestures:
                self.gesture_status.update_detector_status(
                    'Manos', 
                    gestures['hand_detected'],
                    gestures.get('hand_confidence', 0.0)
                )
            
            # Brazos
            if 'arm_detected' in gestures:
                self.gesture_status.update_detector_status(
                    'Brazos',
                    gestures['arm_detected'],
                    gestures.get('arm_confidence', 0.0)
                )
            
            # Voz (si está en los gestos)
            if 'voice_active' in gestures:
                self.gesture_status.update_detector_status(
                    'Voz',
                    gestures['voice_active'],
                    gestures.get('voice_confidence', 0.0)
                )
            
            # Postura
            if 'pose_detected' in gestures:
                self.gesture_status.update_detector_status(
                    'Postura',
                    gestures['pose_detected'],
                    gestures.get('pose_confidence', 0.0)
                )
            
            # Último gesto
            if 'gesture_name' in gestures and gestures['gesture_name']:
                self.gesture_status.update_gesture_info(
                    gestures['gesture_name'],
                    gestures.get('action_name', '')
                )
                
        except Exception as e:
            logger.error(f"Error actualizando estado de detectores: {e}")
    
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
            
            # Actualizar etiqueta de cámara
            if hasattr(self.gesture_pipeline, 'is_camera_active'):
                camera_active = self.gesture_pipeline.is_camera_active()
                self.camera_label.setText(f"Cámara: {'Activa' if camera_active else 'Inactiva'}")
                self.camera_view.set_camera_status(camera_active)
            
        except Exception as e:
            logger.error(f"Error verificando estado del pipeline: {e}")
    
    def _on_gesture_detected(self, gesture_data: Dict[str, Any]):
        """Manejador cuando se detecta un gesto."""
        try:
            gesture_name = gesture_data.get('gesture_name', 'Desconocido')
            confidence = gesture_data.get('confidence', 0.0)
            
            self._log_to_console(
                f"👋 Gestos: {gesture_name} ({confidence:.0%})",
                get_color('gesture_active')
            )
            
            # Actualizar UI
            self.gesture_status.update_gesture_info(
                gesture_name,
                gesture_data.get('action_name', '')
            )
            
        except Exception as e:
            logger.error(f"Error procesando gesto detectado: {e}")
    
    def _on_action_executed(self, action_data: Dict[str, Any], success: bool):
        """Manejador cuando se ejecuta una acción."""
        try:
            action_name = action_data.get('action_name', 'Desconocida')
            
            if success:
                self._log_to_console(
                    f"✅ Acción: {action_name}",
                    get_color('success')
                )
            else:
                self._log_to_console(
                    f"❌ Falló acción: {action_name}",
                    get_color('error')
                )
            
        except Exception as e:
            logger.error(f"Error procesando acción ejecutada: {e}")
            

    def _log_to_console(self, message: str, color: str = None):
        """Agrega un mensaje a la consola de logs."""
        try:
            timestamp = time.strftime("%H:%M:%S")
            
            if color:
                self.log_console.append(
                    f'<span style="color: {color}">[{timestamp}] {message}</span>'
                )
            else:
                self.log_console.append(f"[{timestamp}] {message}")
            
            #if color:
            #    html = f'<span style="color: {color}">[{timestamp}] {message}</span>'
            #else:
            #    html = f'<span style="color: {get_color(\"text_primary\")}">[{timestamp}] {message}</span>'
            #self.log_console.append(html)
                
                
            # Auto-scroll al final
            self.log_console.verticalScrollBar().setValue(
                self.log_console.verticalScrollBar().maximum()
            )

            # Limitar cantidad de líneas
            max_lines = 200
            while self.log_console.document().lineCount() > max_lines:
                    cursor = self.log_console.textCursor()
                    cursor.movePosition(cursor.MoveOperation.Start)
                    cursor.select(cursor.SelectionType.LineUnderCursor)
                    cursor.removeSelectedText()
                    cursor.deleteChar()
        except Exception as e:
            logger.error(f"Error escribiendo en consola: {e}")
    
    def _on_profile_changed(self, profile_name: str):
        """Manejador cuando cambia el perfil."""
        try:
            print(f"🔄 [MainWindow] Cambiando perfil a: {profile_name}")

            self.current_profile = profile_name
            self.profile_label.setText(f"Perfil: {profile_name}")

            # DEBUG: Verificar qué hay en config
            from utils.config_loader import config
            print(f"📂 [MainWindow] Config path: {config.config_dir}")
            
            # Si el sistema está corriendo, actualizar pipeline
            if self.is_system_running and self.gesture_pipeline:
                print(f"🚀 [MainWindow] Pipeline activo, cambiando perfil...")
                if hasattr(self.gesture_pipeline, 'set_active_profile'):
                    success = self.gesture_pipeline.set_active_profile(profile_name)
                    print(f"✅ [MainWindow] set_active_profile result: {success}")
                
                self._log_to_console(
                    f"🔄 Perfil cambiado a: {profile_name}",
                    get_color('info')
                )
            
            # Guardar como último perfil usado
            config.update_setting('app.last_profile', profile_name)
            config.save_settings()

            print(f"💾 [MainWindow] Perfil guardado en settings")

        except Exception as e:
            logger.error(f"Error cambiando perfil: {e}")
            print(f"❌ [MainWindow] Error cambiando perfil: {e}")
            import traceback
            traceback.print_exc()

    
    def _open_config_window(self):
        """Abre la ventana de configuración."""
        if self.config_window is None:
            self.config_window = ConfigWindow(self)
        
        self.config_window.show()
        self.config_window.raise_()
    
    def _open_profile_manager(self):
        """Abre el gestor de perfiles."""

        if self.profile_window is None:
            print(f"🔄 [MainWindow] Cambiando perfil")  # ← ESTO SÍ VA AQUÍ

            self.profile_window = ProfileManagerWindow(
                self.profile_manager,
                self
            )

            # Cuando se guarda un perfil → recargar selector
            self.profile_window.profile_saved.connect(
                self.profile_selector.load_profiles
            )

            self.profile_window.show()
        self.profile_window.raise_()

    
    # Métodos de menú (implementación básica)
    def _new_profile(self):
        """Crea un nuevo perfil."""
        QMessageBox.information(self, "Nuevo Perfil", "Función en desarrollo...")
    
    def _load_profile(self):
        """Carga un perfil desde archivo."""
        QMessageBox.information(self, "Cargar Perfil", "Función en desarrollo...")
    
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
    
    def _open_detectors_config(self):
        """Abre configuración de detectores."""
        self._open_config_window()
        if self.config_window:
            self.config_window.show_tab('detectors')
    
    def _open_controllers_config(self):
        """Abre configuración de controladores."""
        self._open_config_window()
        if self.config_window:
            self.config_window.show_tab('controllers')
    
    def _open_gestures_config(self):
        """Abre configuración de gestos."""
        self._open_config_window()
        if self.config_window:
            self.config_window.show_tab('gestures')
    
    def _open_themes_config(self):
        """Abre configuración de temas."""
        QMessageBox.information(self, "Temas", "Función en desarrollo...")
    
    def _open_gesture_recorder(self):
        """Abre la grabadora de gestos."""
        QMessageBox.information(self, "Grabadora", "Función en desarrollo...")
    
    def _calibrate_camera(self):
        """Abre la calibración de cámara."""
        QMessageBox.information(self, "Calibrar", "Función en desarrollo...")
    
    def _test_controllers(self):
        """Abre la prueba de controladores."""
        QMessageBox.information(self, "Probar", "Función en desarrollo...")
    
    def _show_docs(self):
        """Muestra la documentación."""
        QMessageBox.information(self, "Documentación", "Función en desarrollo...")
    
    def _show_about(self):
        """Muestra el diálogo 'Acerca de'."""
        about_text = """
        <h2>Nyx</h2>
        <p><b>Versión:</b> 2.0.0</p>
        <p><b>Descripción:</b> Sistema de control por gestos para computadora</p>
        <p><b>Arquitectura:</b> Modular y extensible</p>
        <p><b>Módulos:</b> Manos, Brazos, Voz, Teclado, Mouse, Ventanas</p>
        <hr>
        <p>Desarrollado con Python, PyQt6 y MediaPipe</p>
        <p>© 2025 - Sistema de Control por Gestos</p>
        """
        
        QMessageBox.about(self, "Acerca de", about_text)
    
    def closeEvent(self, event):
        """Manejador cuando se cierra la ventana."""
        try:
            logger.info("🔒 Cerrando aplicación...")
            
            # Detener sistema si está corriendo
            if self.is_system_running:
                self._stop_system()
            
            # Cerrar ventanas hijas
            if self.config_window:
                self.config_window.close()
            
            if self.profile_window:
                self.profile_window.close()
            
            # Guardar configuración
            self._save_config()
            
            logger.info("✅ Aplicación cerrada correctamente")
            event.accept()
            
        except Exception as e:
            logger.error(f"❌ Error cerrando aplicación: {e}")
            event.accept()
        """Manejador cuando se cierra la ventana."""
        # Detener sistema si está corriendo
        if self.is_system_running:
            self._stop_system()
        
        # Cerrar ventanas hijas
        if self.config_window:
            self.config_window.close()
        
        if self.profile_window:
            self.profile_window.close()
        
        # Guardar configuración
        self._save_config()
        
        logger.info("Aplicación cerrada")
        event.accept()


# Función para ejecutar la aplicación
def run_app():
    """Ejecuta la aplicación principal."""
    app = QApplication(sys.argv)
    
    # Aplicar tema
    styles.apply_to_app(app)
    
    # Crear y mostrar ventana principal
    window = MainWindow()
    window.show()
    
    # Ejecutar aplicación
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()