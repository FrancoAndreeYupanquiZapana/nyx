"""
⚙️ CONFIG WINDOW - Ventana de configuración
============================================
Ventana de configuración avanzada del sistema NYX.
Completamente integrada con la arquitectura del proyecto.
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
    QStackedWidget, QRadioButton, QButtonGroup
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
    """Pestaña de configuración de detectores."""
    
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
        camera_group = QGroupBox("Configuración de Cámara")
        camera_layout = QFormLayout()
        
        self.camera_device = QSpinBox()
        self.camera_device.setRange(0, 10)
        camera_layout.addRow("Dispositivo cámara:", self.camera_device)
        
        self.camera_width = QSpinBox()
        self.camera_width.setRange(320, 3840)
        self.camera_width.setSingleStep(160)
        camera_layout.addRow("Ancho (px):", self.camera_width)
        
        self.camera_height = QSpinBox()
        self.camera_height.setRange(240, 2160)
        self.camera_height.setSingleStep(120)
        camera_layout.addRow("Alto (px):", self.camera_height)
        
        self.camera_fps = QSpinBox()
        self.camera_fps.setRange(1, 60)
        camera_layout.addRow("FPS:", self.camera_fps)
        
        self.camera_mirror = QCheckBox("Espejar imagen")
        camera_layout.addRow(self.camera_mirror)
        
        camera_group.setLayout(camera_layout)
        scroll_layout.addWidget(camera_group)
        
        # ===== DETECCIÓN DE MANOS =====
        hand_group = QGroupBox("Detección de Manos (MediaPipe)")
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
        pose_group = QGroupBox("Detección de Postura")
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
        voice_group = QGroupBox("Reconocimiento de Voz")
        voice_layout = QFormLayout()
        
        self.voice_enabled = QCheckBox("Habilitar reconocimiento de voz")
        voice_layout.addRow(self.voice_enabled)
        
        self.voice_activation_word = QLineEdit()
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
    
    def _connect_signals(self):
        """Conecta todas las señales de cambio."""
        widgets = [
            self.camera_device, self.camera_width, self.camera_height,
            self.camera_fps, self.camera_mirror, self.hand_enabled,
            self.hand_max_hands, self.hand_detection_confidence,
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
    
    def apply_changes(self, changes: dict):
        """Aplica cambios en tiempo real (para sistema en ejecución)."""
        if 'detectors' in changes:
            # Aquí se podrían aplicar cambios en tiempo real
            logger.debug(f"Aplicando cambios de detectores: {changes['detectors'].keys()}")


class ControllersConfigTab(ConfigTabWidget):
    """Pestaña de configuración de controladores."""
    
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
        keyboard_group = QGroupBox("Controlador de Teclado")
        keyboard_layout = QFormLayout()
        
        self.keyboard_enabled = QCheckBox("Habilitar control de teclado")
        keyboard_layout.addRow(self.keyboard_enabled)
        
        self.keyboard_delay = QDoubleSpinBox()
        self.keyboard_delay.setRange(0.01, 2.0)
        self.keyboard_delay.setSingleStep(0.05)
        self.keyboard_delay.setSuffix(" segundos")
        keyboard_layout.addRow("Retardo entre teclas:", self.keyboard_delay)
        
        keyboard_group.setLayout(keyboard_layout)
        scroll_layout.addWidget(keyboard_group)
        
        # ===== MOUSE =====
        mouse_group = QGroupBox("Controlador de Mouse")
        mouse_layout = QFormLayout()
        
        self.mouse_enabled = QCheckBox("Habilitar control de mouse")
        mouse_layout.addRow(self.mouse_enabled)
        
        self.mouse_sensitivity = QDoubleSpinBox()
        self.mouse_sensitivity.setRange(0.1, 5.0)
        self.mouse_sensitivity.setSingleStep(0.1)
        mouse_layout.addRow("Sensibilidad:", self.mouse_sensitivity)
        
        self.mouse_acceleration = QCheckBox("Aceleración de mouse")
        mouse_layout.addRow(self.mouse_acceleration)
        
        mouse_group.setLayout(mouse_layout)
        scroll_layout.addWidget(mouse_group)
        
        # ===== ACCIONES RÁPIDAS =====
        quick_group = QGroupBox("Acciones Rápidas (Bash)")
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
            self.keyboard_enabled, self.keyboard_delay,
            self.mouse_enabled, self.mouse_sensitivity, self.mouse_acceleration,
            self.quick_screenshot, self.quick_volume_up,
            self.quick_volume_down, self.quick_mute
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
                'delay': self.keyboard_delay.value()
            },
            'mouse': {
                'enabled': self.mouse_enabled.isChecked(),
                'sensitivity': self.mouse_sensitivity.value(),
                'acceleration': self.mouse_acceleration.isChecked()
            },
            'quick_actions': {
                'screenshot': self.quick_screenshot.text(),
                'volume_up': self.quick_volume_up.text(),
                'volume_down': self.quick_volume_down.text(),
                'mute': self.quick_mute.text()
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
            
            # Configuración de la app
            self.keyboard_enabled.setChecked(settings.get('controllers.keyboard.enabled', True))
            self.keyboard_delay.setValue(settings.get('controllers.keyboard.delay', 0.1))
            
            self.mouse_enabled.setChecked(settings.get('controllers.mouse.enabled', True))
            self.mouse_sensitivity.setValue(settings.get('controllers.mouse.sensitivity', 1.5))
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
                'mute': self.quick_mute.text()
            }
            
            self.config_loader.update_system_config(system_config)
            self.config_loader.save_system_config()
            
            # Guardar en settings.yaml
            settings = {
                'controllers': {
                    'keyboard': {
                        'enabled': self.keyboard_enabled.isChecked(),
                        'delay': self.keyboard_delay.value()
                    },
                    'mouse': {
                        'enabled': self.mouse_enabled.isChecked(),
                        'sensitivity': self.mouse_sensitivity.value(),
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


class ProfilesConfigTab(ConfigTabWidget):
    """Pestaña de configuración de perfiles."""
    
    profile_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile_manager = ProfileManager()
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Splitter para lista y editor
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo: Lista de perfiles
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Lista de perfiles
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._on_profile_selected)
        left_layout.addWidget(QLabel("Perfiles disponibles:"))
        left_layout.addWidget(self.profile_list)
        
        # Botones de gestión
        btn_layout = QHBoxLayout()
        
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.clicked.connect(self._create_profile)
        btn_layout.addWidget(self.new_btn)
        
        self.duplicate_btn = QPushButton("Duplicar")
        self.duplicate_btn.clicked.connect(self._duplicate_profile)
        btn_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.clicked.connect(self._delete_profile)
        btn_layout.addWidget(self.delete_btn)
        
        left_layout.addLayout(btn_layout)
        
        # Panel derecho: Editor de perfil
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Información del perfil
        info_group = QGroupBox("Información del Perfil")
        info_layout = QFormLayout()
        
        self.profile_name = QLineEdit()
        info_layout.addRow("Nombre:", self.profile_name)
        
        self.profile_description = QTextEdit()
        self.profile_description.setMaximumHeight(80)
        self.profile_description.setPlaceholderText("Descripción del perfil...")
        info_layout.addRow("Descripción:", self.profile_description)
        
        self.profile_author = QLineEdit()
        info_layout.addRow("Autor:", self.profile_author)
        
        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)
        
        # Configuración del perfil
        config_group = QGroupBox("Configuración")
        config_layout = QFormLayout()
        
        self.profile_mouse_sensitivity = QDoubleSpinBox()
        self.profile_mouse_sensitivity.setRange(0.1, 5.0)
        self.profile_mouse_sensitivity.setSingleStep(0.1)
        config_layout.addRow("Sensibilidad mouse:", self.profile_mouse_sensitivity)
        
        self.profile_keyboard_delay = QDoubleSpinBox()
        self.profile_keyboard_delay.setRange(0.01, 1.0)
        self.profile_keyboard_delay.setSingleStep(0.01)
        self.profile_keyboard_delay.setSuffix(" segundos")
        config_layout.addRow("Retardo teclado:", self.profile_keyboard_delay)
        
        self.profile_gesture_cooldown = QDoubleSpinBox()
        self.profile_gesture_cooldown.setRange(0.0, 2.0)
        self.profile_gesture_cooldown.setSingleStep(0.1)
        self.profile_gesture_cooldown.setSuffix(" segundos")
        config_layout.addRow("Enfriamiento gestos:", self.profile_gesture_cooldown)
        
        config_group.setLayout(config_layout)
        right_layout.addWidget(config_group)
        
        # Módulos habilitados
        modules_group = QGroupBox("Módulos Habilitados")
        modules_layout = QVBoxLayout()
        
        self.module_hand = QCheckBox("Detección de manos")
        self.module_hand.setChecked(True)
        modules_layout.addWidget(self.module_hand)
        
        self.module_voice = QCheckBox("Reconocimiento de voz")
        self.module_voice.setChecked(True)
        modules_layout.addWidget(self.module_voice)
        
        self.module_keyboard = QCheckBox("Control de teclado")
        self.module_keyboard.setChecked(True)
        modules_layout.addWidget(self.module_keyboard)
        
        self.module_mouse = QCheckBox("Control de mouse")
        self.module_mouse.setChecked(True)
        modules_layout.addWidget(self.module_mouse)
        
        modules_group.setLayout(modules_layout)
        right_layout.addWidget(modules_group)
        
        # Botón guardar
        self.save_profile_btn = QPushButton("💾 Guardar Perfil")
        self.save_profile_btn.clicked.connect(self._save_profile)
        self.save_profile_btn.setEnabled(False)
        right_layout.addWidget(self.save_profile_btn)
        
        right_layout.addStretch()
        
        # Configurar splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        
        # Conectar señales de cambio
        self._connect_signals()
    
    def _connect_signals(self):
        """Conecta señales de cambio."""
        widgets = [
            self.profile_name, self.profile_description,
            self.profile_author, self.profile_mouse_sensitivity,
            self.profile_keyboard_delay, self.profile_gesture_cooldown,
            self.module_hand, self.module_voice,
            self.module_keyboard, self.module_mouse
        ]
        
        for widget in widgets:
            if hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._on_profile_changed)
            elif hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_profile_changed)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_profile_changed)
    
    def _on_profile_changed(self):
        """Manejador cuando cambia el perfil."""
        if self.profile_list.currentItem():
            self.save_profile_btn.setEnabled(True)
            self.changes = self.get_current_config()
            self.config_changed.emit({'profiles': self.changes})
    
    def _on_profile_selected(self, current, previous):
        """Manejador cuando se selecciona un perfil."""
        if current:
            profile_name = current.text()
            self._load_profile_data(profile_name)
            self.profile_selected.emit(profile_name)
            self.save_profile_btn.setEnabled(False)
    
    def _load_profile_data(self, profile_name: str):
        """Carga los datos de un perfil."""
        try:
            profile = self.profile_manager.load_profile(profile_name)
            
            self.profile_name.setText(profile.get('profile_name', ''))
            self.profile_description.setText(profile.get('description', ''))
            self.profile_author.setText(profile.get('author', 'Sistema'))
            
            settings = profile.get('settings', {})
            self.profile_mouse_sensitivity.setValue(settings.get('mouse_sensitivity', 1.5))
            self.profile_keyboard_delay.setValue(settings.get('keyboard_delay', 0.1))
            self.profile_gesture_cooldown.setValue(settings.get('gesture_cooldown', 0.3))
            
            modules = profile.get('enabled_modules', [])
            self.module_hand.setChecked('hand' in modules)
            self.module_voice.setChecked('voice' in modules)
            self.module_keyboard.setChecked('keyboard' in modules)
            self.module_mouse.setChecked('mouse' in modules)
            
        except Exception as e:
            logger.error(f"Error cargando perfil {profile_name}: {e}")
    
    def _create_profile(self):
        """Crea un nuevo perfil."""
        name, ok = QInputDialog.getText(
            self, "Nuevo Perfil",
            "Nombre del perfil:",
            QLineEdit.EchoMode.Normal,
            "nuevo_perfil"
        )
        
        if ok and name:
            # Crear perfil básico
            profile = {
                'profile_name': name,
                'description': 'Perfil personalizado',
                'version': '1.0.0',
                'author': 'Usuario',
                'gestures': {},
                'voice_commands': {},
                'settings': {
                    'mouse_sensitivity': 1.5,
                    'keyboard_delay': 0.1,
                    'gesture_cooldown': 0.3
                },
                'enabled_modules': ['hand', 'voice', 'keyboard', 'mouse']
            }
            
            # Guardar perfil
            self.profile_manager.save_profile(name, profile)
            
            # Actualizar lista
            self._refresh_profile_list()
            
            # Seleccionar nuevo perfil
            items = self.profile_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.profile_list.setCurrentItem(items[0])
    
    def _duplicate_profile(self):
        """Duplica el perfil seleccionado."""
        current = self.profile_list.currentItem()
        if not current:
            return
        
        original_name = current.text()
        new_name, ok = QInputDialog.getText(
            self, "Duplicar Perfil",
            f"Nombre para la copia de '{original_name}':",
            QLineEdit.EchoMode.Normal,
            f"{original_name}_copia"
        )
        
        if ok and new_name:
            try:
                profile = self.profile_manager.load_profile(original_name)
                profile['profile_name'] = new_name
                profile['description'] = f"Copia de {original_name}"
                
                self.profile_manager.save_profile(new_name, profile)
                self._refresh_profile_list()
                
            except Exception as e:
                logger.error(f"Error duplicando perfil: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo duplicar: {str(e)}")
    
    def _delete_profile(self):
        """Elimina el perfil seleccionado."""
        current = self.profile_list.currentItem()
        if not current:
            return
        
        profile_name = current.text()
        
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el perfil '{profile_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.profile_manager.delete_profile(profile_name)
                self._refresh_profile_list()
            except Exception as e:
                logger.error(f"Error eliminando perfil: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo eliminar: {str(e)}")
    
    def _save_profile(self):
        """Guarda el perfil actual."""
        try:
            profile_name = self.profile_name.text().strip()
            if not profile_name:
                QMessageBox.warning(self, "Error", "El nombre del perfil no puede estar vacío")
                return
            
            # Crear perfil
            profile = {
                'profile_name': profile_name,
                'description': self.profile_description.toPlainText(),
                'version': '1.0.0',
                'author': self.profile_author.text(),
                'gestures': {},  # Se cargaría del perfil original
                'voice_commands': {},  # Se cargaría del perfil original
                'settings': {
                    'mouse_sensitivity': self.profile_mouse_sensitivity.value(),
                    'keyboard_delay': self.profile_keyboard_delay.value(),
                    'gesture_cooldown': self.profile_gesture_cooldown.value()
                },
                'enabled_modules': []
            }
            
            # Agregar módulos
            if self.module_hand.isChecked():
                profile['enabled_modules'].append('hand')
            if self.module_voice.isChecked():
                profile['enabled_modules'].append('voice')
            if self.module_keyboard.isChecked():
                profile['enabled_modules'].append('keyboard')
            if self.module_mouse.isChecked():
                profile['enabled_modules'].append('mouse')
            
            # Guardar perfil
            self.profile_manager.save_profile(profile_name, profile)
            
            # Actualizar lista si cambió el nombre
            current = self.profile_list.currentItem()
            if current and current.text() != profile_name:
                self._refresh_profile_list()
            
            self.save_profile_btn.setEnabled(False)
            QMessageBox.information(self, "Éxito", f"Perfil '{profile_name}' guardado")
            
        except Exception as e:
            logger.error(f"Error guardando perfil: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {str(e)}")
    
    def _refresh_profile_list(self):
        """Actualiza la lista de perfiles."""
        self.profile_list.clear()
        profiles = self.profile_manager.list_profiles()
        for profile in profiles:
            self.profile_list.addItem(profile)
    
    def get_current_config(self) -> dict:
        """Obtiene la configuración actual."""
        return {
            'name': self.profile_name.text(),
            'description': self.profile_description.toPlainText(),
            'author': self.profile_author.text(),
            'mouse_sensitivity': self.profile_mouse_sensitivity.value(),
            'keyboard_delay': self.profile_keyboard_delay.value(),
            'gesture_cooldown': self.profile_gesture_cooldown.value()
        }
    
    def load_config(self):
        """Carga la configuración."""
        self._refresh_profile_list()
        
        # Seleccionar primer perfil si existe
        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)
    
    def save_config(self):
        """Guarda la configuración."""
        # Los perfiles ya se guardan individualmente
        pass


class UISettingsTab(ConfigTabWidget):
    """Pestaña de configuración de la interfaz."""
    
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
        appearance_group = QGroupBox("Apariencia")
        appearance_layout = QFormLayout()
        
        self.theme = QComboBox()
        self.theme.addItems(["Oscuro", "Claro", "Automático"])
        appearance_layout.addRow("Tema:", self.theme)
        
        self.language = QComboBox()
        self.language.addItems(["Español", "English", "Français", "Deutsch"])
        appearance_layout.addRow("Idioma:", self.language)
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 20)
        self.font_size.setSuffix(" pt")
        appearance_layout.addRow("Tamaño de fuente:", self.font_size)
        
        appearance_group.setLayout(appearance_layout)
        scroll_layout.addWidget(appearance_group)
        
        # ===== VISUALIZACIÓN =====
        display_group = QGroupBox("Visualización")
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
        behavior_group = QGroupBox("Comportamiento")
        behavior_layout = QFormLayout()
        
        self.start_minimized = QCheckBox("Iniciar minimizado")
        behavior_layout.addRow(self.start_minimized)
        
        self.always_on_top = QCheckBox("Siempre visible")
        behavior_layout.addRow(self.always_on_top)
        
        self.minimize_to_tray = QCheckBox("Minimizar a bandeja")
        behavior_layout.addRow(self.minimize_to_tray)
        
        behavior_group.setLayout(behavior_layout)
        scroll_layout.addWidget(behavior_group)
        
        # ===== LOGS =====
        logs_group = QGroupBox("Registros (Logs)")
        logs_layout = QFormLayout()
        
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        logs_layout.addRow("Nivel de log:", self.log_level)
        
        self.log_to_file = QCheckBox("Guardar logs en archivo")
        logs_layout.addRow(self.log_to_file)
        
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
            self.theme, self.language, self.font_size,
            self.show_fps, self.show_landmarks, self.show_gesture_info,
            self.camera_preview, self.start_minimized, self.always_on_top,
            self.minimize_to_tray, self.log_level, self.log_to_file
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
            'show_fps': self.show_fps.isChecked(),
            'show_landmarks': self.show_landmarks.isChecked(),
            'show_gesture_info': self.show_gesture_info.isChecked(),
            'camera_preview': self.camera_preview.isChecked(),
            'start_minimized': self.start_minimized.isChecked(),
            'always_on_top': self.always_on_top.isChecked(),
            'minimize_to_tray': self.minimize_to_tray.isChecked(),
            'log_level': self.log_level.currentText(),
            'log_to_file': self.log_to_file.isChecked()
        }
    
    def load_config(self):
        """Carga la configuración."""
        try:
            system_config = self.config_loader.get_system_config()
            settings = self.config_loader.get_settings()
            
            # Sistema
            general = system_config.get('general', {})
            
            theme_map = {'dark': 'Oscuro', 'light': 'Claro', 'auto': 'Automático'}
            current_theme = general.get('theme', 'dark')
            self.theme.setCurrentText(theme_map.get(current_theme, 'Oscuro'))
            
            lang_map = {'es-ES': 'Español', 'en-US': 'English', 'fr-FR': 'Français', 'de-DE': 'Deutsch'}
            current_lang = general.get('language', 'es-ES')
            self.language.setCurrentText(lang_map.get(current_lang, 'Español'))
            
            # UI settings
            ui_settings = system_config.get('ui', {})
            self.show_fps.setChecked(ui_settings.get('show_fps', True))
            self.show_landmarks.setChecked(ui_settings.get('show_landmarks', True))
            self.show_gesture_info.setChecked(ui_settings.get('show_gesture_info', True))
            self.camera_preview.setChecked(ui_settings.get('camera_preview', True))
            
            # App settings
            self.font_size.setValue(settings.get('ui.font_size', 10))
            self.start_minimized.setChecked(settings.get('ui.start_minimized', False))
            self.always_on_top.setChecked(settings.get('ui.always_on_top', False))
            self.minimize_to_tray.setChecked(settings.get('ui.minimize_to_tray', False))
            self.log_level.setCurrentText(settings.get('ui.log_level', 'INFO'))
            self.log_to_file.setChecked(settings.get('ui.log_to_file', True))
            
        except Exception as e:
            logger.error(f"Error cargando configuración de UI: {e}")
    
    def save_config(self):
        """Guarda la configuración."""
        try:
            # Actualizar system.yaml
            system_config = self.config_loader.get_system_config()
            
            # General
            theme_map = {'Oscuro': 'dark', 'Claro': 'light', 'Automático': 'auto'}
            lang_map = {'Español': 'es-ES', 'English': 'en-US', 'Français': 'fr-FR', 'Deutsch': 'de-DE'}
            
            system_config['general']['theme'] = theme_map.get(self.theme.currentText(), 'dark')
            system_config['general']['language'] = lang_map.get(self.language.currentText(), 'es-ES')
            
            # UI
            system_config['ui'] = {
                'show_fps': self.show_fps.isChecked(),
                'show_landmarks': self.show_landmarks.isChecked(),
                'show_gesture_info': self.show_gesture_info.isChecked(),
                'camera_preview': self.camera_preview.isChecked()
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
                    'log_level': self.log_level.currentText(),
                    'log_to_file': self.log_to_file.isChecked()
                }
            }
            
            self.config_loader.update_settings(settings)
            self.config_loader.save_settings()
            
            logger.info("Configuración de UI guardada")
            
        except Exception as e:
            logger.error(f"Error guardando configuración de UI: {e}")
            raise


class GesturesConfigTab(ConfigTabWidget):
    """Pestaña de configuración de gestos."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile = None
        self._init_ui()
        self.load_config()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Selección de perfil
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Perfil:"))
        
        self.profile_combo = QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_changed)
        profile_layout.addWidget(self.profile_combo)
        
        self.load_profile_btn = QPushButton("Cargar")
        self.load_profile_btn.clicked.connect(self._load_selected_profile)
        profile_layout.addWidget(self.load_profile_btn)
        
        profile_layout.addStretch()
        layout.addLayout(profile_layout)
        
        # Splitter para gestos y comandos de voz
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ===== GESTOS =====
        gestures_widget = QWidget()
        gestures_layout = QVBoxLayout(gestures_widget)
        
        gestures_layout.addWidget(QLabel("Gestos configurados:"))
        
        self.gestures_table = QTableWidget()
        self.gestures_table.setColumnCount(6)
        self.gestures_table.setHorizontalHeaderLabels([
            "Nombre", "Tipo", "Mano", "Confianza", "Acción", "Habilitado"
        ])
        self.gestures_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        gestures_layout.addWidget(self.gestures_table)
        
        # Botones para gestos
        gesture_btn_layout = QHBoxLayout()
        
        self.add_gesture_btn = QPushButton("➕ Agregar Gesto")
        self.add_gesture_btn.clicked.connect(self._add_gesture)
        gesture_btn_layout.addWidget(self.add_gesture_btn)
        
        self.edit_gesture_btn = QPushButton("✏️ Editar")
        self.edit_gesture_btn.clicked.connect(self._edit_gesture)
        gesture_btn_layout.addWidget(self.edit_gesture_btn)
        
        self.remove_gesture_btn = QPushButton("🗑️ Eliminar")
        self.remove_gesture_btn.clicked.connect(self._remove_gesture)
        gesture_btn_layout.addWidget(self.remove_gesture_btn)
        
        gestures_layout.addLayout(gesture_btn_layout)
        splitter.addWidget(gestures_widget)
        
        # ===== COMANDOS DE VOZ =====
        voice_widget = QWidget()
        voice_layout = QVBoxLayout(voice_widget)
        
        voice_layout.addWidget(QLabel("Comandos de voz:"))
        
        self.voice_table = QTableWidget()
        self.voice_table.setColumnCount(4)
        self.voice_table.setHorizontalHeaderLabels([
            "Comando", "Acción", "Descripción", "Habilitado"
        ])
        self.voice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        voice_layout.addWidget(self.voice_table)
        
        # Botones para comandos de voz
        voice_btn_layout = QHBoxLayout()
        
        self.add_voice_btn = QPushButton("➕ Agregar Comando")
        self.add_voice_btn.clicked.connect(self._add_voice_command)
        voice_btn_layout.addWidget(self.add_voice_btn)
        
        self.edit_voice_btn = QPushButton("✏️ Editar")
        self.edit_voice_btn.clicked.connect(self._edit_voice_command)
        voice_btn_layout.addWidget(self.edit_voice_btn)
        
        self.remove_voice_btn = QPushButton("🗑️ Eliminar")
        self.remove_voice_btn.clicked.connect(self._remove_voice_command)
        voice_btn_layout.addWidget(self.remove_voice_btn)
        
        voice_layout.addLayout(voice_btn_layout)
        splitter.addWidget(voice_widget)
        
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)
        
        # Botón guardar cambios
        self.save_changes_btn = QPushButton("💾 Guardar Cambios en Perfil")
        self.save_changes_btn.clicked.connect(self._save_profile_changes)
        self.save_changes_btn.setEnabled(False)
        layout.addWidget(self.save_changes_btn)
        
        self.setLayout(layout)
        
        # Conectar selección de tabla
        self.gestures_table.itemSelectionChanged.connect(self._on_gesture_selected)
        self.voice_table.itemSelectionChanged.connect(self._on_voice_selected)
    
    def _on_profile_changed(self, profile_name: str):
        """Manejador cuando cambia el perfil seleccionado."""
        self.current_profile = profile_name
        self.save_changes_btn.setEnabled(True)
    
    def _load_selected_profile(self):
        """Carga el perfil seleccionado."""
        profile_name = self.profile_combo.currentText()
        if profile_name:
            self._load_profile(profile_name)
    
    def _load_profile(self, profile_name: str):
        """Carga un perfil específico."""
        try:
            profile_manager = ProfileManager()
            profile = profile_manager.load_profile(profile_name)
            self.current_profile = profile
            
            # Cargar gestos en tabla
            self._load_gestures_to_table(profile.get('gestures', {}))
            
            # Cargar comandos de voz en tabla
            self._load_voice_commands_to_table(profile.get('voice_commands', {}))
            
            logger.debug(f"Perfil {profile_name} cargado para edición")
            
        except Exception as e:
            logger.error(f"Error cargando perfil {profile_name}: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo cargar el perfil: {str(e)}")
    
    def _load_gestures_to_table(self, gestures: dict):
        """Carga gestos en la tabla."""
        self.gestures_table.setRowCount(len(gestures))
        
        for i, (gesture_name, gesture_data) in enumerate(gestures.items()):
            self.gestures_table.setItem(i, 0, QTableWidgetItem(gesture_name))
            self.gestures_table.setItem(i, 1, QTableWidgetItem(gesture_data.get('type', 'hand')))
            self.gestures_table.setItem(i, 2, QTableWidgetItem(gesture_data.get('hand', 'right')))
            self.gestures_table.setItem(i, 3, QTableWidgetItem(str(gesture_data.get('confidence', 0.7))))
            
            action = f"{gesture_data.get('action', '')}:{gesture_data.get('command', '')}"
            self.gestures_table.setItem(i, 4, QTableWidgetItem(action))
            
            enabled = "Sí" if gesture_data.get('enabled', True) else "No"
            self.gestures_table.setItem(i, 5, QTableWidgetItem(enabled))
    
    def _load_voice_commands_to_table(self, voice_commands: dict):
        """Carga comandos de voz en la tabla."""
        self.voice_table.setRowCount(len(voice_commands))
        
        for i, (command, command_data) in enumerate(voice_commands.items()):
            self.voice_table.setItem(i, 0, QTableWidgetItem(command))
            self.voice_table.setItem(i, 1, QTableWidgetItem(command_data.get('action', '')))
            self.voice_table.setItem(i, 2, QTableWidgetItem(command_data.get('description', '')))
            
            enabled = "Sí" if command_data.get('enabled', True) else "No"
            self.voice_table.setItem(i, 3, QTableWidgetItem(enabled))
    
    def _add_gesture(self):
        """Abre diálogo para agregar un nuevo gesto."""
        from ui.gesture_editor import GestureEditorDialog
        
        dialog = GestureEditorDialog(self)
        if dialog.exec():
            new_gesture = dialog.get_gesture_data()
            # Agregar a la tabla
            row = self.gestures_table.rowCount()
            self.gestures_table.insertRow(row)
            
            self.gestures_table.setItem(row, 0, QTableWidgetItem(new_gesture['name']))
            self.gestures_table.setItem(row, 1, QTableWidgetItem(new_gesture['type']))
            self.gestures_table.setItem(row, 2, QTableWidgetItem(new_gesture['hand']))
            self.gestures_table.setItem(row, 3, QTableWidgetItem(str(new_gesture['confidence'])))
            self.gestures_table.setItem(row, 4, QTableWidgetItem(new_gesture['action']))
            self.gestures_table.setItem(row, 5, QTableWidgetItem("Sí" if new_gesture['enabled'] else "No"))
            
            self.save_changes_btn.setEnabled(True)
    
    def _edit_gesture(self):
        """Edita el gesto seleccionado."""
        selected = self.gestures_table.currentRow()
        if selected >= 0:
            # Obtener datos actuales
            name = self.gestures_table.item(selected, 0).text()
            
            from ui.gesture_editor import GestureEditorDialog
            
            dialog = GestureEditorDialog(self)
            # TODO: Cargar datos existentes en el diálogo
            if dialog.exec():
                updated_gesture = dialog.get_gesture_data()
                # Actualizar tabla
                self.gestures_table.setItem(selected, 0, QTableWidgetItem(updated_gesture['name']))
                self.gestures_table.setItem(selected, 1, QTableWidgetItem(updated_gesture['type']))
                self.gestures_table.setItem(selected, 2, QTableWidgetItem(updated_gesture['hand']))
                self.gestures_table.setItem(selected, 3, QTableWidgetItem(str(updated_gesture['confidence'])))
                self.gestures_table.setItem(selected, 4, QTableWidgetItem(updated_gesture['action']))
                self.gestures_table.setItem(selected, 5, QTableWidgetItem("Sí" if updated_gesture['enabled'] else "No"))
                
                self.save_changes_btn.setEnabled(True)
    
    def _remove_gesture(self):
        """Elimina el gesto seleccionado."""
        selected = self.gestures_table.currentRow()
        if selected >= 0:
            name = self.gestures_table.item(selected, 0).text()
            
            reply = QMessageBox.question(
                self, "Confirmar",
                f"¿Eliminar el gesto '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.gestures_table.removeRow(selected)
                self.save_changes_btn.setEnabled(True)
    
    def _add_voice_command(self):
        """Agrega un nuevo comando de voz."""
        from ui.voice_command_editor import VoiceCommandEditorDialog
        
        dialog = VoiceCommandEditorDialog(self)
        if dialog.exec():
            new_command = dialog.get_command_data()
            # Agregar a la tabla
            row = self.voice_table.rowCount()
            self.voice_table.insertRow(row)
            
            self.voice_table.setItem(row, 0, QTableWidgetItem(new_command['command']))
            self.voice_table.setItem(row, 1, QTableWidgetItem(new_command['action']))
            self.voice_table.setItem(row, 2, QTableWidgetItem(new_command['description']))
            self.voice_table.setItem(row, 3, QTableWidgetItem("Sí" if new_command['enabled'] else "No"))
            
            self.save_changes_btn.setEnabled(True)
    
    def _edit_voice_command(self):
        """Edita el comando de voz seleccionado."""
        selected = self.voice_table.currentRow()
        if selected >= 0:
            from ui.voice_command_editor import VoiceCommandEditorDialog
            
            dialog = VoiceCommandEditorDialog(self)
            if dialog.exec():
                updated_command = dialog.get_command_data()
                # Actualizar tabla
                self.voice_table.setItem(selected, 0, QTableWidgetItem(updated_command['command']))
                self.voice_table.setItem(selected, 1, QTableWidgetItem(updated_command['action']))
                self.voice_table.setItem(selected, 2, QTableWidgetItem(updated_command['description']))
                self.voice_table.setItem(selected, 3, QTableWidgetItem("Sí" if updated_command['enabled'] else "No"))
                
                self.save_changes_btn.setEnabled(True)
    
    def _remove_voice_command(self):
        """Elimina el comando de voz seleccionado."""
        selected = self.voice_table.currentRow()
        if selected >= 0:
            command = self.voice_table.item(selected, 0).text()
            
            reply = QMessageBox.question(
                self, "Confirmar",
                f"¿Eliminar el comando '{command}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.voice_table.removeRow(selected)
                self.save_changes_btn.setEnabled(True)
    
    def _save_profile_changes(self):
        """Guarda los cambios en el perfil."""
        if not self.current_profile:
            QMessageBox.warning(self, "Error", "No hay perfil seleccionado")
            return
        
        try:
            # Recolectar gestos de la tabla
            gestures = {}
            for row in range(self.gestures_table.rowCount()):
                name = self.gestures_table.item(row, 0).text()
                gestures[name] = {
                    'type': self.gestures_table.item(row, 1).text(),
                    'hand': self.gestures_table.item(row, 2).text(),
                    'confidence': float(self.gestures_table.item(row, 3).text()),
                    'action': self.gestures_table.item(row, 4).text().split(':')[0],
                    'command': self.gestures_table.item(row, 4).text().split(':')[1] if ':' in self.gestures_table.item(row, 4).text() else '',
                    'enabled': self.gestures_table.item(row, 5).text() == "Sí"
                }
            
            # Recolectar comandos de voz
            voice_commands = {}
            for row in range(self.voice_table.rowCount()):
                command = self.voice_table.item(row, 0).text()
                voice_commands[command] = {
                    'action': self.voice_table.item(row, 1).text(),
                    'description': self.voice_table.item(row, 2).text(),
                    'enabled': self.voice_table.item(row, 3).text() == "Sí"
                }
            
            # Actualizar perfil
            profile_manager = ProfileManager()
            profile = profile_manager.load_profile(self.current_profile)
            
            profile['gestures'] = gestures
            profile['voice_commands'] = voice_commands
            
            profile_manager.save_profile(self.current_profile, profile)
            
            self.save_changes_btn.setEnabled(False)
            QMessageBox.information(self, "Éxito", f"Perfil '{self.current_profile}' actualizado")
            
        except Exception as e:
            logger.error(f"Error guardando cambios en perfil: {e}")
            QMessageBox.critical(self, "Error", f"No se pudieron guardar los cambios: {str(e)}")
    
    def _on_gesture_selected(self):
        """Manejador cuando se selecciona un gesto."""
        self.edit_gesture_btn.setEnabled(self.gestures_table.currentRow() >= 0)
        self.remove_gesture_btn.setEnabled(self.gestures_table.currentRow() >= 0)
    
    def _on_voice_selected(self):
        """Manejador cuando se selecciona un comando de voz."""
        self.edit_voice_btn.setEnabled(self.voice_table.currentRow() >= 0)
        self.remove_voice_btn.setEnabled(self.voice_table.currentRow() >= 0)
    
    def load_config(self):
        """Carga la configuración."""
        # Cargar lista de perfiles
        profile_manager = ProfileManager()
        profiles = profile_manager.list_profiles()
        
        self.profile_combo.clear()
        for profile in profiles:
            self.profile_combo.addItem(profile)
        
        # Cargar perfil activo si existe
        active_profile = self.config_loader.get_setting('app.active_profile')
        if active_profile and active_profile in profiles:
            self.profile_combo.setCurrentText(active_profile)
            self._load_profile(active_profile)
    
    def save_config(self):
        """Guarda la configuración."""
        # Los cambios se guardan directamente en el perfil
        pass
    
    def get_changes(self) -> dict:
        """Obtiene los cambios realizados."""
        return {'gestures_updated': True}


class ConfigWindow(QDialog):
    """Ventana de configuración principal de NYX."""
    
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
        
        # Crear pestañas
        self.detectors_tab = DetectorsConfigTab()
        self.controllers_tab = ControllersConfigTab()
        self.profiles_tab = ProfilesConfigTab()
        self.gestures_tab = GesturesConfigTab()
        self.ui_tab = UISettingsTab()
        
        # Agregar pestañas
        self.tab_widget.addTab(self.detectors_tab, "🎥 Detectores")
        self.tab_widget.addTab(self.controllers_tab, "🎮 Controladores")
        self.tab_widget.addTab(self.profiles_tab, "📁 Perfiles")
        self.tab_widget.addTab(self.gestures_tab, "👋 Gestos")
        self.tab_widget.addTab(self.ui_tab, "🎨 Interfaz")
        
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
        """)
    
    def _connect_signals(self):
        """Conecta las señales de cambio de todas las pestañas."""
        tabs = [
            self.detectors_tab,
            self.controllers_tab,
            self.profiles_tab,
            self.gestures_tab,
            self.ui_tab
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
        """Aplica los cambios al sistema en tiempo real."""
        try:
            if not self.all_changes:
                return
            
            # Aplicar cambios a cada pestaña
            for tab in [self.detectors_tab, self.controllers_tab, 
                       self.profiles_tab, self.gestures_tab, self.ui_tab]:
                tab.apply_changes(self.all_changes)
            
            # Emitir señal para que el sistema principal aplique cambios
            self.config_applied.emit(self.all_changes)
            
            # Actualizar estado
            self.apply_button.setEnabled(False)
            self.status_bar.setText("✅ Cambios aplicados al sistema")
            
            logger.info(f"Cambios aplicados: {list(self.all_changes.keys())}")
            
        except Exception as e:
            logger.error(f"Error aplicando cambios: {e}")
            self.status_bar.setText(f"❌ Error aplicando cambios: {str(e)}")
    
    def _save_all(self):
        """Guarda todos los cambios en disco."""
        try:
            # Guardar cada pestaña
            self.detectors_tab.save_config()
            self.controllers_tab.save_config()
            self.profiles_tab.save_config()
            self.gestures_tab.save_config()
            self.ui_tab.save_config()
            
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
            
            # Resetear estado
            self.unsaved_changes = False
            self.all_changes.clear()
            
            self.apply_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.save_button.setText("💾 Guardar")
            
            self.status_bar.setText("🔄 Cambios restaurados")
    
    def show_tab(self, tab_name: str):
        """
        Muestra una pestaña específica.
        
        Args:
            tab_name: Nombre de la pestaña ('detectors', 'controllers', 'profiles', 'gestures', 'ui')
        """
        tab_map = {
            'detectors': 0,
            'controllers': 1,
            'profiles': 2,
            'gestures': 3,
            'ui': 4
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