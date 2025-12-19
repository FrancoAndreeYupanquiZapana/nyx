"""
⚙️ CONFIG WINDOW - Ventana de configuración mejorada
====================================================
Versión híbrida que combina lo mejor de ambas implementaciones.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QCheckBox, QSlider, QSpinBox,
    QDoubleSpinBox, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QListWidget, QListWidgetItem, QTreeWidget,
    QTreeWidgetItem, QSplitter, QScrollArea, QFrame,
    QMessageBox, QFileDialog, QInputDialog, QDialogButtonBox,
    QStackedWidget, QRadioButton, QButtonGroup, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPixmap

from ui.styles import get_color, get_font
from utils.logger import logger
from utils.config_loader import ConfigLoader
from core.profile_manager import ProfileManager


class ConfigTabWidget(QWidget):
    """Widget base para pestañas de configuración."""
    
    config_changed = pyqtSignal(dict)  # Señal con cambios específicos
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_loader = ConfigLoader()
        self.changes = {}
    
    def load_config(self):
        """Carga la configuración en el widget."""
        raise NotImplementedError
    
    def save_config(self):
        """Guarda la configuración desde el widget."""
        raise NotImplementedError
    
    def apply_changes(self, changes: dict):
        """Aplica cambios en tiempo real."""
        pass
    
    def get_changes(self) -> dict:
        """Obtiene los cambios realizados."""
        return self.changes.copy()
    
    def reset_changes(self):
        """Resetea los cambios no guardados."""
        self.changes.clear()


class DetectorsConfigTab(ConfigTabWidget):
    """Pestaña de configuración de detectores - MEJORADA."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # ===== CÁMARA =====
        camera_group = QGroupBox("📷 Configuración de Cámara")
        camera_layout = QFormLayout()
        
        self.camera_device = QSpinBox()
        self.camera_device.setRange(0, 10)
        camera_layout.addRow("Dispositivo cámara:", self.camera_device)
        
        # Añadido de la segunda versión: Resolución como combo
        self.camera_resolution = QComboBox()
        self.camera_resolution.addItems(["640x480", "800x600", "1024x768", "1280x720", "1920x1080"])
        camera_layout.addRow("Resolución:", self.camera_resolution)
        
        # Mantener width/height para compatibilidad
        res_layout = QHBoxLayout()
        self.camera_width = QSpinBox()
        self.camera_width.setRange(320, 3840)
        self.camera_width.setSingleStep(160)
        res_layout.addWidget(QLabel("Ancho:"))
        res_layout.addWidget(self.camera_width)
        
        self.camera_height = QSpinBox()
        self.camera_height.setRange(240, 2160)
        self.camera_height.setSingleStep(120)
        res_layout.addWidget(QLabel("Alto:"))
        res_layout.addWidget(self.camera_height)
        camera_layout.addRow("Dimensiones personalizadas:", res_layout)
        
        self.camera_fps = QSpinBox()
        self.camera_fps.setRange(1, 60)
        self.camera_fps.setSuffix(" FPS")
        camera_layout.addRow("FPS:", self.camera_fps)
        
        self.camera_mirror = QCheckBox("Espejar imagen")
        camera_layout.addRow(self.camera_mirror)
        
        camera_group.setLayout(camera_layout)
        scroll_layout.addWidget(camera_group)
        
        # ===== DETECCIÓN DE MANOS =====
        hand_group = QGroupBox("🖐️ Detección de Manos (MediaPipe)")
        hand_layout = QFormLayout()
        
        self.hand_enabled = QCheckBox("Habilitar detección de manos")
        hand_layout.addRow(self.hand_enabled)
        
        self.hand_max_hands = QSpinBox()
        self.hand_max_hands.setRange(1, 4)
        hand_layout.addRow("Máximo de manos:", self.hand_max_hands)
        
        self.hand_detection_confidence = QDoubleSpinBox()
        self.hand_detection_confidence.setRange(0.1, 1.0)
        self.hand_detection_confidence.setSingleStep(0.05)
        self.hand_detection_confidence.setDecimals(2)
        hand_layout.addRow("Confianza detección:", self.hand_detection_confidence)
        
        self.hand_tracking_confidence = QDoubleSpinBox()
        self.hand_tracking_confidence.setRange(0.1, 1.0)
        self.hand_tracking_confidence.setSingleStep(0.05)
        self.hand_tracking_confidence.setDecimals(2)
        hand_layout.addRow("Confianza seguimiento:", self.hand_tracking_confidence)
        
        self.hand_model_complexity = QSpinBox()
        self.hand_model_complexity.setRange(0, 2)
        hand_layout.addRow("Complejidad modelo:", self.hand_model_complexity)
        
        hand_group.setLayout(hand_layout)
        scroll_layout.addWidget(hand_group)
        
        # ===== DETECCIÓN DE BRAZOS/POSTURA =====
        pose_group = QGroupBox("💪 Detección de Postura")
        pose_layout = QFormLayout()
        
        self.pose_enabled = QCheckBox("Habilitar detección de postura")
        pose_layout.addRow(self.pose_enabled)
        
        self.pose_detection_confidence = QDoubleSpinBox()
        self.pose_detection_confidence.setRange(0.1, 1.0)
        self.pose_detection_confidence.setSingleStep(0.05)
        self.pose_detection_confidence.setDecimals(2)
        pose_layout.addRow("Confianza detección:", self.pose_detection_confidence)
        
        self.pose_tracking_confidence = QDoubleSpinBox()
        self.pose_tracking_confidence.setRange(0.1, 1.0)
        self.pose_tracking_confidence.setSingleStep(0.05)
        self.pose_tracking_confidence.setDecimals(2)
        pose_layout.addRow("Confianza seguimiento:", self.pose_tracking_confidence)
        
        pose_group.setLayout(pose_layout)
        scroll_layout.addWidget(pose_group)
        
        # ===== RECONOCIMIENTO DE VOZ =====
        voice_group = QGroupBox("🎤 Reconocimiento de Voz")
        voice_layout = QFormLayout()
        
        self.voice_enabled = QCheckBox("Habilitar reconocimiento de voz")
        voice_layout.addRow(self.voice_enabled)
        
        self.voice_activation_word = QLineEdit()
        self.voice_activation_word.setPlaceholderText("Ej: nyx")
        voice_layout.addRow("Palabra de activación:", self.voice_activation_word)
        
        self.voice_energy_threshold = QSpinBox()
        self.voice_energy_threshold.setRange(100, 5000)
        voice_layout.addRow("Umbral de energía:", self.voice_energy_threshold)
        
        self.voice_language = QComboBox()
        self.voice_language.addItems(["es-ES", "en-US", "fr-FR", "de-DE", "it-IT"])
        voice_layout.addRow("Idioma:", self.voice_language)
        
        self.voice_dynamic_energy = QCheckBox("Umbral dinámico")
        voice_layout.addRow(self.voice_dynamic_energy)
        
        voice_group.setLayout(voice_layout)
        scroll_layout.addWidget(voice_group)
        
        # Espaciador
        scroll_layout.addStretch()
        
        # Configurar scroll
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
        
        # Conectar señales de cambio
        self._connect_signals()
        
        # Conectar cambio de resolución para actualizar width/height
        self.camera_resolution.currentTextChanged.connect(self._on_resolution_changed)
    
    def _on_resolution_changed(self, resolution):
        """Actualiza width/height cuando cambia la resolución."""
        if 'x' in resolution:
            w, h = resolution.split('x')
            self.camera_width.setValue(int(w))
            self.camera_height.setValue(int(h))
    
    def _connect_signals(self):
        """Conecta todas las señales de cambio."""
        widgets = [
            self.camera_device, self.camera_resolution, self.camera_width,
            self.camera_height, self.camera_fps, self.camera_mirror,
            self.hand_enabled, self.hand_max_hands, self.hand_detection_confidence,
            self.hand_tracking_confidence, self.hand_model_complexity,
            self.pose_enabled, self.pose_detection_confidence,
            self.pose_tracking_confidence, self.voice_enabled,
            self.voice_activation_word, self.voice_energy_threshold,
            self.voice_language, self.voice_dynamic_energy
        ]
        
        for widget in widgets:
            if hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._on_config_changed)
    
    def _on_config_changed(self):
        """Manejador cuando hay cambios."""
        self.changes = self.get_current_config()
        self.config_changed.emit({'detectors': self.changes})
    
    def get_current_config(self) -> dict:
        """Obtiene la configuración actual del widget."""
        return {
            'camera': {
                'device_id': self.camera_device.value(),
                'resolution': self.camera_resolution.currentText(),
                'width': self.camera_width.value(),
                'height': self.camera_height.value(),
                'fps': self.camera_fps.value(),
                'mirror': self.camera_mirror.isChecked()
            },
            'hand_detection': {
                'enabled': self.hand_enabled.isChecked(),
                'max_num_hands': self.hand_max_hands.value(),
                'min_detection_confidence': self.hand_detection_confidence.value(),
                'min_tracking_confidence': self.hand_tracking_confidence.value(),
                'model_complexity': self.hand_model_complexity.value()
            },
            'arm_detection': {
                'enabled': self.pose_enabled.isChecked(),
                'min_detection_confidence': self.pose_detection_confidence.value(),
                'min_tracking_confidence': self.pose_tracking_confidence.value(),
                'model_complexity': 1
            },
            'voice_recognition': {
                'enabled': self.voice_enabled.isChecked(),
                'activation_word': self.voice_activation_word.text(),
                'energy_threshold': self.voice_energy_threshold.value(),
                'language': self.voice_language.currentText(),
                'dynamic_energy_threshold': self.voice_dynamic_energy.isChecked()
            }
        }
    
    def load_config(self):
        """Carga la configuración desde el sistema."""
        try:
            system_config = self.config_loader.get_system_config()
            
            # Cámara
            camera = system_config.get('camera', {})
            self.camera_device.setValue(camera.get('device_id', 0))
            
            # Nueva: resolución
            if 'resolution' in camera:
                self.camera_resolution.setCurrentText(camera['resolution'])
            else:
                # Calcular resolución más cercana
                width = camera.get('width', 1280)
                height = camera.get('height', 720)
                self.camera_resolution.setCurrentText(f"{width}x{height}")
            
            self.camera_width.setValue(camera.get('width', 1280))
            self.camera_height.setValue(camera.get('height', 720))
            self.camera_fps.setValue(camera.get('fps', 30))
            self.camera_mirror.setChecked(camera.get('mirror', True))
            
            # Manos
            hand = system_config.get('hand_detection', {})
            self.hand_enabled.setChecked(hand.get('enabled', True))
            self.hand_max_hands.setValue(hand.get('max_num_hands', 2))
            self.hand_detection_confidence.setValue(hand.get('min_detection_confidence', 0.7))
            self.hand_tracking_confidence.setValue(hand.get('min_tracking_confidence', 0.5))
            self.hand_model_complexity.setValue(hand.get('model_complexity', 1))
            
            # Postura/Brazos
            arm = system_config.get('arm_detection', {})
            self.pose_enabled.setChecked(arm.get('enabled', False))
            self.pose_detection_confidence.setValue(arm.get('min_detection_confidence', 0.5))
            self.pose_tracking_confidence.setValue(arm.get('min_tracking_confidence', 0.5))
            
            # Voz
            voice = system_config.get('voice_recognition', {})
            self.voice_enabled.setChecked(voice.get('enabled', True))
            self.voice_activation_word.setText(voice.get('activation_word', 'nyx'))
            self.voice_energy_threshold.setValue(voice.get('energy_threshold', 300))
            self.voice_language.setCurrentText(voice.get('language', 'es-ES'))
            self.voice_dynamic_energy.setChecked(voice.get('dynamic_energy_threshold', True))
            
            logger.debug("Configuración de detectores cargada")
            
        except Exception as e:
            logger.error(f"Error cargando configuración de detectores: {e}")
    
    def save_config(self):
        """Guarda la configuración en el sistema."""
        try:
            config = self.get_current_config()
            self.config_loader.update_system_config(config)
            self.config_loader.save_system_config()
            logger.info("Configuración de detectores guardada")
        except Exception as e:
            logger.error(f"Error guardando configuración de detectores: {e}")
            raise


class ControllersConfigTab(ConfigTabWidget):
    """Pestaña de configuración de controladores - MEJORADA."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # ===== TECLADO =====
        keyboard_group = QGroupBox("⌨️ Controlador de Teclado")
        keyboard_layout = QFormLayout()
        
        self.keyboard_enabled = QCheckBox("Habilitar control de teclado")
        keyboard_layout.addRow(self.keyboard_enabled)
        
        self.keyboard_delay = QSpinBox()
        self.keyboard_delay.setRange(10, 1000)  # De 10ms a 1s
        self.keyboard_delay.setSuffix(" ms")
        keyboard_layout.addRow("Retardo entre teclas:", self.keyboard_delay)
        
        # Añadido de la segunda versión: Repetición de teclas
        self.keyboard_repeat = QCheckBox("Repetir teclas mantenidas")
        self.keyboard_repeat.setChecked(True)
        keyboard_layout.addRow(self.keyboard_repeat)
        
        keyboard_group.setLayout(keyboard_layout)
        scroll_layout.addWidget(keyboard_group)
        
        # ===== MOUSE =====
        mouse_group = QGroupBox("🖱️ Controlador de Mouse")
        mouse_layout = QFormLayout()
        
        self.mouse_enabled = QCheckBox("Habilitar control de mouse")
        mouse_layout.addRow(self.mouse_enabled)
        
        self.mouse_sensitivity = QDoubleSpinBox()
        self.mouse_sensitivity.setRange(0.1, 5.0)
        self.mouse_sensitivity.setSingleStep(0.1)
        mouse_layout.addRow("Sensibilidad:", self.mouse_sensitivity)
        
        # Añadido de la segunda versión: Suavizado de mouse
        self.mouse_smoothing = QSpinBox()
        self.mouse_smoothing.setRange(0, 10)
        self.mouse_smoothing.setSuffix(" frames")
        self.mouse_smoothing.setToolTip("Número de frames para suavizar el movimiento")
        mouse_layout.addRow("Suavizado:", self.mouse_smoothing)
        
        self.mouse_acceleration = QCheckBox("Aceleración de mouse")
        mouse_layout.addRow(self.mouse_acceleration)
        
        mouse_group.setLayout(mouse_layout)
        scroll_layout.addWidget(mouse_group)
        
        # ===== ACCIONES RÁPIDAS =====
        quick_group = QGroupBox("⚡ Acciones Rápidas (Bash)")
        quick_layout = QFormLayout()
        
        self.quick_screenshot = QLineEdit()
        self.quick_screenshot.setPlaceholderText("Comando para screenshot")
        quick_layout.addRow("Screenshot:", self.quick_screenshot)
        
        self.quick_volume_up = QLineEdit()
        self.quick_volume_up.setPlaceholderText("Comando para subir volumen")
        quick_layout.addRow("Volumen +:", self.quick_volume_up)
        
        self.quick_volume_down = QLineEdit()
        self.quick_volume_down.setPlaceholderText("Comando para bajar volumen")
        quick_layout.addRow("Volumen -:", self.quick_volume_down)
        
        self.quick_mute = QLineEdit()
        self.quick_mute.setPlaceholderText("Comando para silenciar")
        quick_layout.addRow("Silenciar:", self.quick_mute)
        
        # Añadir más acciones rápidas comunes
        self.quick_brightness_up = QLineEdit()
        self.quick_brightness_up.setPlaceholderText("Comando para subir brillo")
        quick_layout.addRow("Brillo +:", self.quick_brightness_up)
        
        self.quick_brightness_down = QLineEdit()
        self.quick_brightness_down.setPlaceholderText("Comando para bajar brillo")
        quick_layout.addRow("Brillo -:", self.quick_brightness_down)
        
        quick_group.setLayout(quick_layout)
        scroll_layout.addWidget(quick_group)
        
        # Espaciador
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.setLayout(layout)
        
        # Conectar señales
        self._connect_signals()
    
    def _connect_signals(self):
        """Conecta señales de cambio."""
        widgets = [
            self.keyboard_enabled, self.keyboard_delay, self.keyboard_repeat,
            self.mouse_enabled, self.mouse_sensitivity, self.mouse_smoothing,
            self.mouse_acceleration, self.quick_screenshot, self.quick_volume_up,
            self.quick_volume_down, self.quick_mute, self.quick_brightness_up,
            self.quick_brightness_down
        ]
        
        for widget in widgets:
            if hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._on_config_changed)
    
    def _on_config_changed(self):
        """Manejador cuando hay cambios."""
        self.changes = self.get_current_config()
        self.config_changed.emit({'controllers': self.changes})
    
    def get_current_config(self) -> dict:
        """Obtiene la configuración actual."""
        return {
            'keyboard': {
                'enabled': self.keyboard_enabled.isChecked(),
                'delay': self.keyboard_delay.value(),
                'repeat_enabled': self.keyboard_repeat.isChecked()
            },
            'mouse': {
                'enabled': self.mouse_enabled.isChecked(),
                'sensitivity': self.mouse_sensitivity.value(),
                'smoothing': self.mouse_smoothing.value(),
                'acceleration': self.mouse_acceleration.isChecked()
            },
            'quick_actions': {
                'screenshot': self.quick_screenshot.text(),
                'volume_up': self.quick_volume_up.text(),
                'volume_down': self.quick_volume_down.text(),
                'mute': self.quick_mute.text(),
                'brightness_up': self.quick_brightness_up.text(),
                'brightness_down': self.quick_brightness_down.text()
            }
        }
    
    def load_config(self):
        """Carga la configuración."""
        try:
            system_config = self.config_loader.get_system_config()
            settings = self.config_loader.get_settings()
            
            # Configuración del sistema
            general = system_config.get('general', {})
            
            # Acciones rápidas
            quick_actions = system_config.get('quick_actions', {})
            self.quick_screenshot.setText(quick_actions.get('screenshot', 'gnome-screenshot'))
            self.quick_volume_up.setText(quick_actions.get('volume_up', 'amixer set Master 5%+'))
            self.quick_volume_down.setText(quick_actions.get('volume_down', 'amixer set Master 5%-'))
            self.quick_mute.setText(quick_actions.get('mute', 'amixer set Master mute'))
            self.quick_brightness_up.setText(quick_actions.get('brightness_up', 'brightnessctl set +5%'))
            self.quick_brightness_down.setText(quick_actions.get('brightness_down', 'brightnessctl set 5%-'))
            
            # Configuración de la app
            self.keyboard_enabled.setChecked(settings.get('controllers.keyboard.enabled', True))
            self.keyboard_delay.setValue(settings.get('controllers.keyboard.delay', 50))
            self.keyboard_repeat.setChecked(settings.get('controllers.keyboard.repeat_enabled', True))
            
            self.mouse_enabled.setChecked(settings.get('controllers.mouse.enabled', True))
            self.mouse_sensitivity.setValue(settings.get('controllers.mouse.sensitivity', 1.5))
            self.mouse_smoothing.setValue(settings.get('controllers.mouse.smoothing', 3))
            self.mouse_acceleration.setChecked(settings.get('controllers.mouse.acceleration', False))
            
        except Exception as e:
            logger.error(f"Error cargando configuración de controladores: {e}")
    
    def save_config(self):
        """Guarda la configuración."""
        try:
            # Guardar en system.yaml
            system_config = self.config_loader.get_system_config()
            
            # Actualizar acciones rápidas
            system_config['quick_actions'] = {
                'screenshot': self.quick_screenshot.text(),
                'volume_up': self.quick_volume_up.text(),
                'volume_down': self.quick_volume_down.text(),
                'mute': self.quick_mute.text(),
                'brightness_up': self.quick_brightness_up.text(),
                'brightness_down': self.quick_brightness_down.text()
            }
            
            self.config_loader.update_system_config(system_config)
            self.config_loader.save_system_config()
            
            # Guardar en settings.yaml
            settings = {
                'controllers': {
                    'keyboard': {
                        'enabled': self.keyboard_enabled.isChecked(),
                        'delay': self.keyboard_delay.value(),
                        'repeat_enabled': self.keyboard_repeat.isChecked()
                    },
                    'mouse': {
                        'enabled': self.mouse_enabled.isChecked(),
                        'sensitivity': self.mouse_sensitivity.value(),
                        'smoothing': self.mouse_smoothing.value(),
                        'acceleration': self.mouse_acceleration.isChecked()
                    }
                }
            }
            
            self.config_loader.update_settings(settings)
            self.config_loader.save_settings()
            
            logger.info("Configuración de controladores guardada")
            
        except Exception as e:
            logger.error(f"Error guardando configuración de controladores: {e}")
            raise


class UISettingsTab(ConfigTabWidget):
    """Pestaña de configuración de la interfaz - MEJORADA."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # ===== APARIENCIA =====
        appearance_group = QGroupBox("🎨 Apariencia")
        appearance_layout = QFormLayout()
        
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light", "blue", "green", "purple", "auto"])
        appearance_layout.addRow("Tema:", self.theme)
        
        self.language = QComboBox()
        self.language.addItems(["es-ES", "en-US", "fr-FR", "de-DE", "it-IT"])
        appearance_layout.addRow("Idioma:", self.language)
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 20)
        self.font_size.setSuffix(" pt")
        appearance_layout.addRow("Tamaño de fuente:", self.font_size)
        
        # Añadido de la segunda versión: Opacidad de ventana
        self.window_opacity = QSpinBox()
        self.window_opacity.setRange(10, 100)
        self.window_opacity.setSuffix("%")
        self.window_opacity.setToolTip("Opacidad de la ventana principal")
        appearance_layout.addRow("Opacidad:", self.window_opacity)
        
        appearance_group.setLayout(appearance_layout)
        scroll_layout.addWidget(appearance_group)
        
        # ===== VISUALIZACIÓN =====
        display_group = QGroupBox("📊 Visualización")
        display_layout = QFormLayout()
        
        self.show_fps = QCheckBox("Mostrar FPS")
        display_layout.addRow(self.show_fps)
        
        self.show_landmarks = QCheckBox("Mostrar landmarks")
        display_layout.addRow(self.show_landmarks)
        
        self.show_gesture_info = QCheckBox("Mostrar información de gestos")
        display_layout.addRow(self.show_gesture_info)
        
        self.camera_preview = QCheckBox("Mostrar vista previa de cámara")
        display_layout.addRow(self.camera_preview)
        
        display_group.setLayout(display_layout)
        scroll_layout.addWidget(display_group)
        
        # ===== COMPORTAMIENTO =====
        behavior_group = QGroupBox("⚙️ Comportamiento")
        behavior_layout = QFormLayout()
        
        self.start_minimized = QCheckBox("Iniciar minimizado")
        behavior_layout.addRow(self.start_minimized)
        
        self.always_on_top = QCheckBox("Siempre visible")
        behavior_layout.addRow(self.always_on_top)
        
        self.minimize_to_tray = QCheckBox("Minimizar a bandeja")
        behavior_layout.addRow(self.minimize_to_tray)
        
        # Añadido de la segunda versión: Ocultar al iniciar
        self.hide_on_start = QCheckBox("Ocultar al iniciar")
        behavior_layout.addRow(self.hide_on_start)
        
        behavior_group.setLayout(behavior_layout)
        scroll_layout.addWidget(behavior_group)
        
        # ===== LOGS =====
        logs_group = QGroupBox("📝 Registros (Logs)")
        logs_layout = QFormLayout()
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        logs_layout.addRow("Nivel de log:", self.log_level)
        
        self.log_to_file = QCheckBox("Guardar logs en archivo")
        logs_layout.addRow(self.log_to_file)
        
        # Añadido de la segunda versión: Tamaño máximo de logs
        self.log_max_size = QSpinBox()
        self.log_max_size.setRange(1, 100)
        self.log_max_size.setSuffix(" MB")
        self.log_max_size.setToolTip("Tamaño máximo del archivo de log")
        logs_layout.addRow("Tamaño máximo:", self.log_max_size)
        
        logs_group.setLayout(logs_layout)
        scroll_layout.addWidget(logs_group)
        
        # Espaciador
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.setLayout(layout)
        
        # Conectar señales
        self._connect_signals()
    
    def _connect_signals(self):
        """Conecta señales de cambio."""
        widgets = [
            self.theme, self.language, self.font_size, self.window_opacity,
            self.show_fps, self.show_landmarks, self.show_gesture_info,
            self.camera_preview, self.start_minimized, self.always_on_top,
            self.minimize_to_tray, self.hide_on_start, self.log_level,
            self.log_to_file, self.log_max_size
        ]
        
        for widget in widgets:
            if hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_config_changed)
    
    def _on_config_changed(self):
        """Manejador cuando hay cambios."""
        self.changes = self.get_current_config()
        self.config_changed.emit({'ui': self.changes})
    
    def get_current_config(self) -> dict:
        """Obtiene la configuración actual."""
        return {
            'theme': self.theme.currentText(),
            'language': self.language.currentText(),
            'font_size': self.font_size.value(),
            'window_opacity': self.window_opacity.value(),
            'show_fps': self.show_fps.isChecked(),
            'show_landmarks': self.show_landmarks.isChecked(),
            'show_gesture_info': self.show_gesture_info.isChecked(),
            'camera_preview': self.camera_preview.isChecked(),
            'start_minimized': self.start_minimized.isChecked(),
            'always_on_top': self.always_on_top.isChecked(),
            'minimize_to_tray': self.minimize_to_tray.isChecked(),
            'hide_on_start': self.hide_on_start.isChecked(),
            'log_level': self.log_level.currentText(),
            'log_to_file': self.log_to_file.isChecked(),
            'log_max_size': self.log_max_size.value()
        }
    
    def load_config(self):
        """Carga la configuración."""
        try:
            system_config = self.config_loader.get_system_config()
            settings = self.config_loader.get_settings()
            
            # Sistema
            general = system_config.get('general', {})
            self.theme.setCurrentText(general.get('theme', 'dark'))
            self.language.setCurrentText(general.get('language', 'es-ES'))
            
            # UI settings
            ui_settings = system_config.get('ui', {})
            self.show_fps.setChecked(ui_settings.get('show_fps', True))
            self.show_landmarks.setChecked(ui_settings.get('show_landmarks', True))
            self.show_gesture_info.setChecked(ui_settings.get('show_gesture_info', True))
            self.camera_preview.setChecked(ui_settings.get('camera_preview', True))
            self.window_opacity.setValue(int(ui_settings.get('opacity', 1.0) * 100))
            
            # App settings
            self.font_size.setValue(settings.get('ui.font_size', 10))
            self.start_minimized.setChecked(settings.get('ui.start_minimized', False))
            self.always_on_top.setChecked(settings.get('ui.always_on_top', False))
            self.minimize_to_tray.setChecked(settings.get('ui.minimize_to_tray', False))
            self.hide_on_start.setChecked(settings.get('ui.hide_on_start', False))
            self.log_level.setCurrentText(settings.get('ui.log_level', 'INFO'))
            self.log_to_file.setChecked(settings.get('ui.log_to_file', True))
            self.log_max_size.setValue(settings.get('ui.log_max_size', 10))
            
        except Exception as e:
            logger.error(f"Error cargando configuración de UI: {e}")
    
    def save_config(self):
        """Guarda la configuración."""
        try:
            # Actualizar system.yaml
            system_config = self.config_loader.get_system_config()
            
            # General
            system_config['general']['theme'] = self.theme.currentText()
            system_config['general']['language'] = self.language.currentText()
            
            # UI
            system_config['ui'] = {
                'show_fps': self.show_fps.isChecked(),
                'show_landmarks': self.show_landmarks.isChecked(),
                'show_gesture_info': self.show_gesture_info.isChecked(),
                'camera_preview': self.camera_preview.isChecked(),
                'opacity': self.window_opacity.value() / 100.0
            }
            
            self.config_loader.update_system_config(system_config)
            self.config_loader.save_system_config()
            
            # Actualizar settings.yaml
            settings = {
                'ui': {
                    'font_size': self.font_size.value(),
                    'start_minimized': self.start_minimized.isChecked(),
                    'always_on_top': self.always_on_top.isChecked(),
                    'minimize_to_tray': self.minimize_to_tray.isChecked(),
                    'hide_on_start': self.hide_on_start.isChecked(),
                    'log_level': self.log_level.currentText(),
                    'log_to_file': self.log_to_file.isChecked(),
                    'log_max_size': self.log_max_size.value()
                }
            }
            
            self.config_loader.update_settings(settings)
            self.config_loader.save_settings()
            
            logger.info("Configuración de UI guardada")
            
        except Exception as e:
            logger.error(f"Error guardando configuración de UI: {e}")
            raise


class PerformanceConfigTab(ConfigTabWidget):
    """Pestaña de configuración de rendimiento - NUEVA (de la segunda versión)."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # ===== RENDIMIENTO =====
        performance_group = QGroupBox("⚡ Rendimiento")
        performance_layout = QFormLayout()
        
        self.processing_threads = QSpinBox()
        self.processing_threads.setRange(1, 8)
        self.processing_threads.setToolTip("Número de hilos para procesamiento paralelo")
        performance_layout.addRow("Hilos de procesamiento:", self.processing_threads)
        
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(1, 10)
        self.buffer_size.setSuffix(" frames")
        self.buffer_size.setToolTip("Tamaño del buffer para procesamiento")
        performance_layout.addRow("Tamaño de buffer:", self.buffer_size)
        
        self.latency_target = QSpinBox()
        self.latency_target.setRange(10, 200)
        self.latency_target.setSuffix(" ms")
        self.latency_target.setToolTip("Latencia objetivo para procesamiento")
        performance_layout.addRow("Latencia objetivo:", self.latency_target)
        
        performance_group.setLayout(performance_layout)
        scroll_layout.addWidget(performance_group)
        
        # ===== RED =====
        network_group = QGroupBox("🌐 Red")
        network_layout = QFormLayout()
        
        self.enable_network = QCheckBox("Habilitar funciones de red")
        self.enable_network.setToolTip("Habilita funciones de red y servidor")
        network_layout.addRow(self.enable_network)
        
        self.server_port = QSpinBox()
        self.server_port.setRange(1024, 65535)
        self.server_port.setValue(8080)
        self.server_port.setToolTip("Puerto para el servidor interno")
        network_layout.addRow("Puerto del servidor:", self.server_port)
        
        network_group.setLayout(network_layout)
        scroll_layout.addWidget(network_group)
        
        # ===== AVANZADO =====
        advanced_group = QGroupBox("🔧 Avanzado")
        advanced_layout = QFormLayout()
        
        self.enable_hardware_acceleration = QCheckBox("Aceleración por hardware")
        self.enable_hardware_acceleration.setToolTip("Usar GPU para procesamiento cuando esté disponible")
        advanced_layout.addRow(self.enable_hardware_acceleration)
        
        self.cache_size = QSpinBox()
        self.cache_size.setRange(10, 1000)
        self.cache_size.setSuffix(" MB")
        self.cache_size.setToolTip("Tamaño de caché para datos de gestos")
        advanced_layout.addRow("Tamaño de caché:", self.cache_size)
        
        self.enable_telemetry = QCheckBox("Enviar datos de uso anónimos")
        self.enable_telemetry.setToolTip("Ayuda a mejorar NYX enviando datos de uso anónimos")
        advanced_layout.addRow(self.enable_telemetry)
        
        advanced_group.setLayout(advanced_layout)
        scroll_layout.addWidget(advanced_group)
        
        # Espaciador
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.setLayout(layout)
        
        # Conectar señales
        self._connect_signals()
    
    def _connect_signals(self):
        """Conecta señales de cambio."""
        widgets = [
            self.processing_threads, self.buffer_size, self.latency_target,
            self.enable_network, self.server_port, self.enable_hardware_acceleration,
            self.cache_size, self.enable_telemetry
        ]
        
        for widget in widgets:
            if hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_config_changed)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_config_changed)
    
    def _on_config_changed(self):
        """Manejador cuando hay cambios."""
        self.changes = self.get_current_config()
        self.config_changed.emit({'performance': self.changes})
    
    def get_current_config(self) -> dict:
        """Obtiene la configuración actual."""
        return {
            'processing_threads': self.processing_threads.value(),
            'buffer_size': self.buffer_size.value(),
            'latency_target': self.latency_target.value(),
            'enable_network': self.enable_network.isChecked(),
            'server_port': self.server_port.value(),
            'enable_hardware_acceleration': self.enable_hardware_acceleration.isChecked(),
            'cache_size': self.cache_size.value(),
            'enable_telemetry': self.enable_telemetry.isChecked()
        }
    
    def load_config(self):
        """Carga la configuración."""
        try:
            system_config = self.config_loader.get_system_config()
            settings = self.config_loader.get_settings()
            
            # Configuración de rendimiento
            performance = system_config.get('performance', {})
            self.processing_threads.setValue(performance.get('processing_threads', 2))
            self.buffer_size.setValue(performance.get('buffer_size', 3))
            self.latency_target.setValue(performance.get('latency_target', 100))
            
            # Configuración de red
            network = system_config.get('network', {})
            self.enable_network.setChecked(network.get('enabled', False))
            self.server_port.setValue(network.get('server_port', 8080))
            
            # Configuración avanzada
            advanced = settings.get('advanced', {})
            self.enable_hardware_acceleration.setChecked(advanced.get('hardware_acceleration', True))
            self.cache_size.setValue(advanced.get('cache_size', 100))
            self.enable_telemetry.setChecked(advanced.get('telemetry', False))
            
        except Exception as e:
            logger.error(f"Error cargando configuración de rendimiento: {e}")
    
    def save_config(self):
        """Guarda la configuración."""
        try:
            # Actualizar system.yaml
            system_config = self.config_loader.get_system_config()
            
            # Rendimiento
            system_config['performance'] = {
                'processing_threads': self.processing_threads.value(),
                'buffer_size': self.buffer_size.value(),
                'latency_target': self.latency_target.value()
            }
            
            # Red
            system_config['network'] = {
                'enabled': self.enable_network.isChecked(),
                'server_port': self.server_port.value()
            }
            
            self.config_loader.update_system_config(system_config)
            self.config_loader.save_system_config()
            
            # Actualizar settings.yaml
            settings = {
                'advanced': {
                    'hardware_acceleration': self.enable_hardware_acceleration.isChecked(),
                    'cache_size': self.cache_size.value(),
                    'telemetry': self.enable_telemetry.isChecked()
                }
            }
            
            self.config_loader.update_settings(settings)
            self.config_loader.save_settings()
            
            logger.info("Configuración de rendimiento guardada")
            
        except Exception as e:
            logger.error(f"Error guardando configuración de rendimiento: {e}")
            raise


class ConfigWindow(QDialog):
    """Ventana de configuración principal de NYX - MEJORADA."""
    
    config_applied = pyqtSignal(dict)  # Señal cuando se aplica configuración
    
    def __init__(self, parent=None, gesture_pipeline=None):
        super().__init__(parent)
        
        self.parent = parent
        self.gesture_pipeline = gesture_pipeline
        
        self.setWindowTitle("⚙️ Configuración de NYX")
        self.setGeometry(200, 200, 1100, 750)
        
        self.unsaved_changes = False
        self.all_changes = {}
        
        self._init_ui()
        self._connect_signals()
        
        logger.info("Ventana de configuración inicializada")
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Título
        title_label = QLabel("Configuración del Sistema NYX")
        title_label.setFont(get_font('heading'))
        title_label.setStyleSheet(f"color: {get_color('primary')}; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Tabs principales
        self.tab_widget = QTabWidget()
        
        # Crear pestañas (manteniendo ProfilesConfigTab y GesturesConfigTab originales)
        self.detectors_tab = DetectorsConfigTab()
        self.controllers_tab = ControllersConfigTab()
        self.profiles_tab = ProfilesConfigTab()  # Mantener original
        self.gestures_tab = GesturesConfigTab()  # Mantener original
        self.ui_tab = UISettingsTab()
        self.performance_tab = PerformanceConfigTab()  # Nueva pestaña
        
        # Agregar pestañas
        self.tab_widget.addTab(self.detectors_tab, "🎥 Detectores")
        self.tab_widget.addTab(self.controllers_tab, "🎮 Controladores")
        self.tab_widget.addTab(self.profiles_tab, "📁 Perfiles")
        self.tab_widget.addTab(self.gestures_tab, "👋 Gestos")
        self.tab_widget.addTab(self.ui_tab, "🎨 Interfaz")
        self.tab_widget.addTab(self.performance_tab, "⚡ Rendimiento")
        
        layout.addWidget(self.tab_widget, 1)
        
        # Barra de estado
        self.status_bar = QLabel("Listo")
        self.status_bar.setStyleSheet(f"""
            padding: 5px;
            background-color: {get_color('surface')};
            color: {get_color('text_secondary')};
            border-top: 1px solid {get_color('border')};
        """)
        layout.addWidget(self.status_bar)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("✅ Aplicar")
        self.apply_button.setToolTip("Aplica los cambios al sistema en ejecución")
        self.apply_button.clicked.connect(self._apply_changes)
        self.apply_button.setEnabled(False)
        button_layout.addWidget(self.apply_button)
        
        self.save_button = QPushButton("💾 Guardar")
        self.save_button.setToolTip("Guarda los cambios en disco")
        self.save_button.clicked.connect(self._save_all)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("🔄 Restaurar")
        self.reset_button.setToolTip("Restaura los cambios no guardados")
        self.reset_button.clicked.connect(self._reset_changes)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("✖ Cerrar")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Aplicar estilos
        self._apply_styles()
    
    def _apply_styles(self):
        """Aplica estilos a la ventana."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
            }}
            QTabWidget::pane {{
                border: 1px solid {get_color('border')};
                border-radius: 6px;
                margin: 2px;
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                margin-right: 2px;
                background-color: {get_color('surface')};
                color: {get_color('text_secondary')};
                border-radius: 4px;
                border: 1px solid transparent;
            }}
            QTabBar::tab:selected {{
                background-color: {get_color('primary')};
                color: white;
                font-weight: bold;
                border-color: {get_color('primary_dark')};
            }}
            QTabBar::tab:hover {{
                background-color: {get_color('surface_hover')};
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
            }}
            QPushButton {{
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
    
    def _connect_signals(self):
        """Conecta las señales de cambio de todas las pestañas."""
        tabs = [
            self.detectors_tab,
            self.controllers_tab,
            self.profiles_tab,
            self.gestures_tab,
            self.ui_tab,
            self.performance_tab
        ]
        
        for tab in tabs:
            tab.config_changed.connect(self._on_tab_config_changed)
        
        # Conectar señal de perfil seleccionado
        self.profiles_tab.profile_selected.connect(self._on_profile_selected)
    
    def _on_tab_config_changed(self, changes: dict):
        """Manejador cuando hay cambios en una pestaña."""
        self.unsaved_changes = True
        self.all_changes.update(changes)
        
        # Actualizar estado de botones
        self.apply_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.save_button.setText("💾 Guardar*")
        
        # Actualizar barra de estado
        change_count = len(self.all_changes)
        self.status_bar.setText(f"⚠️ {change_count} cambio(s) pendiente(s) - No guardado")
    
    def _on_profile_selected(self, profile_name: str):
        """Manejador cuando se selecciona un perfil en la pestaña de perfiles."""
        # Actualizar pestaña de gestos con el perfil seleccionado
        if hasattr(self.gestures_tab, '_load_profile'):
            self.gestures_tab._load_profile(profile_name)
    
    def _apply_changes(self):
        """Aplica los cambios al sistema en tiempo real - MEJORADO."""
        try:
            if not self.all_changes:
                return
            
            # Aplicar cambios a cada pestaña
            for tab in [self.detectors_tab, self.controllers_tab, 
                       self.profiles_tab, self.gestures_tab, 
                       self.ui_tab, self.performance_tab]:
                tab.apply_changes(self.all_changes)
            
            # Métodos específicos de aplicación (de la segunda versión)
            if 'detectors' in self.all_changes and self.gesture_pipeline:
                self.apply_detector_changes(self.all_changes['detectors'])
            
            if 'controllers' in self.all_changes and self.gesture_pipeline:
                self.apply_controller_changes(self.all_changes['controllers'])
            
            # Emitir señal para que el sistema principal aplique cambios
            self.config_applied.emit(self.all_changes)
            
            # Actualizar estado
            self.apply_button.setEnabled(False)
            self.status_bar.setText("✅ Cambios aplicados al sistema")
            
            logger.info(f"Cambios aplicados: {list(self.all_changes.keys())}")
            
        except Exception as e:
            logger.error(f"Error aplicando cambios: {e}")
            self.status_bar.setText(f"❌ Error aplicando cambios: {str(e)}")
    
    def apply_detector_changes(self, detector_changes):
        """Aplica cambios en los detectores en tiempo real - DE LA SEGUNDA VERSIÓN."""
        if not self.gesture_pipeline:
            return
        
        try:
            # Actualizar configuración de detectores
            if hasattr(self.gesture_pipeline, 'gesture_integrator'):
                integrator = self.gesture_pipeline.gesture_integrator
                
                # Manos
                if 'hand_detection' in detector_changes:
                    hand_config = detector_changes['hand_detection']
                    if hasattr(integrator, 'detectors') and 'hand' in integrator.detectors:
                        hand_detector = integrator.detectors['hand']
                        if hasattr(hand_detector, 'update_config'):
                            hand_detector.update_config(hand_config)
                
                # Cámara
                if 'camera' in detector_changes:
                    camera_config = detector_changes['camera']
                    # Actualizar configuración de cámara si existe
                    if hasattr(self.gesture_pipeline, 'camera'):
                        camera = self.gesture_pipeline.camera
                        if hasattr(camera, 'update_config'):
                            camera.update_config(camera_config)
            
            logger.debug("Cambios de detectores aplicados en tiempo real")
            
        except Exception as e:
            logger.error(f"Error aplicando cambios de detectores: {e}")
    
    def apply_controller_changes(self, controller_changes):
        """Aplica cambios en los controladores en tiempo real - DE LA SEGUNDA VERSIÓN."""
        if not self.gesture_pipeline:
            return
        
        try:
            # Actualizar configuración de controladores
            if hasattr(self.gesture_pipeline, 'action_executor'):
                executor = self.gesture_pipeline.action_executor
                
                # Mouse
                if 'mouse' in controller_changes:
                    mouse_config = controller_changes['mouse']
                    if hasattr(executor, 'controllers') and 'mouse' in executor.controllers:
                        mouse_controller = executor.controllers['mouse']
                        if hasattr(mouse_controller, 'update_config'):
                            mouse_controller.update_config(mouse_config)
                
                # Teclado
                if 'keyboard' in controller_changes:
                    keyboard_config = controller_changes['keyboard']
                    if hasattr(executor, 'controllers') and 'keyboard' in executor.controllers:
                        keyboard_controller = executor.controllers['keyboard']
                        if hasattr(keyboard_controller, 'update_config'):
                            keyboard_controller.update_config(keyboard_config)
            
            logger.debug("Cambios de controladores aplicados en tiempo real")
            
        except Exception as e:
            logger.error(f"Error aplicando cambios de controladores: {e}")
    
    def _save_all(self):
        """Guarda todos los cambios en disco."""
        try:
            # Guardar cada pestaña
            self.detectors_tab.save_config()
            self.controllers_tab.save_config()
            self.profiles_tab.save_config()
            self.gestures_tab.save_config()
            self.ui_tab.save_config()
            self.performance_tab.save_config()
            
            # Resetear estado
            self.unsaved_changes = False
            self.all_changes.clear()
            
            self.apply_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.save_button.setText("💾 Guardar")
            
            self.status_bar.setText("✅ Configuración guardada en disco")
            
            logger.info("Toda la configuración guardada en disco")
            
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            self.status_bar.setText(f"❌ Error guardando: {str(e)}")
    
    def _reset_changes(self):
        """Restaura los cambios no guardados."""
        if not self.unsaved_changes:
            return
        
        reply = QMessageBox.question(
            self, "Restaurar cambios",
            "¿Restaurar todos los cambios no guardados?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Recargar configuración desde disco
            self.detectors_tab.load_config()
            self.controllers_tab.load_config()
            self.profiles_tab.load_config()
            self.gestures_tab.load_config()
            self.ui_tab.load_config()
            self.performance_tab.load_config()
            
            # Resetear estado
            self.unsaved_changes = False
            self.all_changes.clear()
            
            self.apply_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.save_button.setText("💾 Guardar")
            
            self.status_bar.setText("🔄 Cambios restaurados")
    
    def cleanup(self):
        """Limpia recursos antes de cerrar - DE LA SEGUNDA VERSIÓN."""
        logger.info("Cerrando ventana de configuración")
    
    def show_tab(self, tab_name: str):
        """
        Muestra una pestaña específica.
        
        Args:
            tab_name: Nombre de la pestaña ('detectors', 'controllers', 'profiles', 'gestures', 'ui', 'performance')
        """
        tab_map = {
            'detectors': 0,
            'controllers': 1,
            'profiles': 2,
            'gestures': 3,
            'ui': 4,
            'performance': 5
        }
        
        if tab_name in tab_map:
            self.tab_widget.setCurrentIndex(tab_map[tab_name])
    
    def set_gesture_pipeline(self, pipeline):
        """Establece el gesture pipeline para aplicar cambios en tiempo real."""
        self.gesture_pipeline = pipeline
    
    def closeEvent(self, event):
        """Manejador cuando se cierra la ventana."""
        if self.unsaved_changes:
            reply = QMessageBox.question(
                self, "Cambios sin guardar",
                "Hay cambios sin guardar. ¿Qué quieres hacer?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_all()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            self.cleanup()
            event.accept()
    
    def get_changes(self) -> dict:
        """Obtiene todos los cambios pendientes."""
        return self.all_changes.copy()


# Función para abrir la ventana de configuración
def open_config_window(parent=None, gesture_pipeline=None):
    """
    Abre la ventana de configuración.
    
    Args:
        parent: Ventana padre
        gesture_pipeline: Instancia del GesturePipeline para aplicar cambios en tiempo real
    
    Returns:
        ConfigWindow: Instancia de la ventana de configuración
    """
    window = ConfigWindow(parent, gesture_pipeline)
    window.exec()
    return window


if __name__ == "__main__":
    # Para pruebas independientes
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    config_window = ConfigWindow()
    config_window.show()
    sys.exit(app.exec())