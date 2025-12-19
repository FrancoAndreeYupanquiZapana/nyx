"""
📁 PROFILE MANAGER WINDOW - Gestor de Perfiles NYX
==================================================
Ventana para gestionar perfiles del sistema de control por gestos.
Completamente integrada con la arquitectura de NYX.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QFileDialog, QInputDialog,
    QGroupBox, QFormLayout, QLineEdit, QTextEdit, QCheckBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget, QWidget,
    QSplitter, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialogButtonBox, QProgressBar, QToolBar
)

from PyQt6.QtCore import (
    Qt, pyqtSignal, QSize, QTimer
)

from PyQt6.QtGui import (
    QAction, QIcon, QFont, QPixmap, QColor
)

from ui.styles import get_color, get_font
from utils.logger import logger
#from utils.config_loader import config
from utils.config_loader import ConfigLoader
from core.profile_manager import ProfileManager
from core.gesture_pipeline import GesturePipeline


class ProfileEditorWidget(QWidget):
    """Widget para editar un perfil."""
    
    profile_updated = pyqtSignal(dict)  # Señal cuando se actualiza el perfil
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_profile = None
        self.original_profile_data = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # ===== INFORMACIÓN BÁSICA =====
        basic_group = QGroupBox("Información del Perfil")
        basic_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre del perfil...")
        basic_layout.addRow("Nombre:", self.name_input)
        
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.setPlaceholderText("Descripción del perfil...")
        basic_layout.addRow("Descripción:", self.description_input)
        
        self.author_input = QLineEdit()
        self.author_input.setPlaceholderText("Autor del perfil...")
        basic_layout.addRow("Autor:", self.author_input)
        
        basic_group.setLayout(basic_layout)
        scroll_layout.addWidget(basic_group)
        
        # ===== CONFIGURACIÓN =====
        config_group = QGroupBox("Configuración")
        config_layout = QFormLayout()
        
        self.mouse_sensitivity = QDoubleSpinBox()
        self.mouse_sensitivity.setRange(0.1, 5.0)
        self.mouse_sensitivity.setSingleStep(0.1)
        self.mouse_sensitivity.setValue(1.5)
        config_layout.addRow("Sensibilidad mouse:", self.mouse_sensitivity)
        
        self.keyboard_delay = QDoubleSpinBox()
        self.keyboard_delay.setRange(0.01, 1.0)
        self.keyboard_delay.setSingleStep(0.01)
        self.keyboard_delay.setSuffix(" segundos")
        self.keyboard_delay.setValue(0.1)
        config_layout.addRow("Retardo teclado:", self.keyboard_delay)
        
        self.gesture_cooldown = QDoubleSpinBox()
        self.gesture_cooldown.setRange(0.0, 2.0)
        self.gesture_cooldown.setSingleStep(0.1)
        self.gesture_cooldown.setSuffix(" segundos")
        self.gesture_cooldown.setValue(0.3)
        config_layout.addRow("Enfriamiento gestos:", self.gesture_cooldown)
        
        config_group.setLayout(config_layout)
        scroll_layout.addWidget(config_group)
        
        # ===== MÓDULOS HABILITADOS =====
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
        
        self.module_window = QCheckBox("Control de ventanas")
        self.module_window.setChecked(False)
        modules_layout.addWidget(self.module_window)
        
        self.module_bash = QCheckBox("Ejecución de comandos")
        self.module_bash.setChecked(False)
        modules_layout.addWidget(self.module_bash)
        
        modules_group.setLayout(modules_layout)
        scroll_layout.addWidget(modules_group)
        
        # ===== GESTOS PRE-DEFINIDOS =====
        gestures_group = QGroupBox("Gestos Pre-definidos (Plantilla)")
        gestures_layout = QVBoxLayout()
        
        self.use_template = QCheckBox("Usar plantilla de gestos básicos")
        self.use_template.setChecked(True)
        gestures_layout.addWidget(self.use_template)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Gaming", "Productividad", "Navegación", "Personalizado"])
        gestures_layout.addWidget(self.template_combo)
        
        gestures_group.setLayout(gestures_layout)
        scroll_layout.addWidget(gestures_group)
        
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
            self.name_input, self.description_input, self.author_input,
            self.mouse_sensitivity, self.keyboard_delay, self.gesture_cooldown,
            self.module_hand, self.module_voice, self.module_keyboard,
            self.module_mouse, self.module_window, self.module_bash,
            self.use_template, self.template_combo
        ]
        
        for widget in widgets:
            if hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._on_profile_changed)
            elif hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._on_profile_changed)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._on_profile_changed)
            elif hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._on_profile_changed)
    
    def _on_profile_changed(self):
        """Manejador cuando cambia algún campo del perfil."""
        if self.current_profile:
            profile_data = self.get_profile_data()
            self.profile_updated.emit(profile_data)
    
    def load_profile(self, profile_name: str, profile_data: Dict[str, Any]):
        """Carga un perfil para edición."""
        self.current_profile = profile_name
        self.original_profile_data = profile_data.copy()
        
        # Información básica
        self.name_input.setText(profile_data.get('profile_name', ''))
        self.description_input.setPlainText(profile_data.get('description', ''))
        self.author_input.setText(profile_data.get('author', 'Sistema'))
        
        # Configuración
        settings = profile_data.get('settings', {})
        self.mouse_sensitivity.setValue(settings.get('mouse_sensitivity', 1.5))
        self.keyboard_delay.setValue(settings.get('keyboard_delay', 0.1))
        self.gesture_cooldown.setValue(settings.get('gesture_cooldown', 0.3))
        
        # Módulos habilitados
        modules = profile_data.get('enabled_modules', [])
        self.module_hand.setChecked('hand' in modules)
        self.module_voice.setChecked('voice' in modules)
        self.module_keyboard.setChecked('keyboard' in modules)
        self.module_mouse.setChecked('mouse' in modules)
        self.module_window.setChecked('window' in modules)
        self.module_bash.setChecked('bash' in modules)
        
        logger.debug(f"Perfil '{profile_name}' cargado para edición")
    
    def get_profile_data(self) -> Dict[str, Any]:
        """Obtiene los datos del perfil desde la UI."""
        # Módulos habilitados
        enabled_modules = []
        if self.module_hand.isChecked():
            enabled_modules.append('hand')
        if self.module_voice.isChecked():
            enabled_modules.append('voice')
        if self.module_keyboard.isChecked():
            enabled_modules.append('keyboard')
        if self.module_mouse.isChecked():
            enabled_modules.append('mouse')
        if self.module_window.isChecked():
            enabled_modules.append('window')
        if self.module_bash.isChecked():
            enabled_modules.append('bash')
        
        # Plantilla de gestos
        gestures_template = {}
        if self.use_template.isChecked():
            gestures_template = self._get_template_gestures(self.template_combo.currentText())
        
        # Construir perfil
        profile_data = {
            'profile_name': self.name_input.text().strip(),
            'description': self.description_input.toPlainText().strip(),
            'version': '1.0.0',
            'author': self.author_input.text().strip(),
            'gestures': gestures_template,
            'voice_commands': self._get_template_voice_commands(),
            'settings': {
                'mouse_sensitivity': self.mouse_sensitivity.value(),
                'keyboard_delay': self.keyboard_delay.value(),
                'gesture_cooldown': self.gesture_cooldown.value()
            },
            'enabled_modules': enabled_modules
        }
        
        return profile_data
    
    def _get_template_gestures(self, template_name: str) -> Dict[str, Any]:
        """Obtiene gestos pre-definidos según la plantilla."""
        templates = {
            'Gaming': {
                'fist': {
                    'action': 'keyboard',
                    'command': 'space',
                    'description': 'Saltar/Disparar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'peace': {
                    'action': 'keyboard',
                    'command': 'r',
                    'description': 'Recargar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'thumbs_up': {
                    'action': 'keyboard',
                    'command': 'e',
                    'description': 'Interactuar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.6
                }
            },
            'Productividad': {
                'fist': {
                    'action': 'keyboard',
                    'command': 'ctrl+s',
                    'description': 'Guardar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'peace': {
                    'action': 'keyboard',
                    'command': 'ctrl+c',
                    'description': 'Copiar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'thumbs_up': {
                    'action': 'keyboard',
                    'command': 'ctrl+v',
                    'description': 'Pegar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.6
                }
            },
            'Navegación': {
                'fist': {
                    'action': 'mouse',
                    'command': 'click',
                    'description': 'Click izquierdo',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'peace': {
                    'action': 'mouse',
                    'command': 'right_click',
                    'description': 'Click derecho',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'thumbs_up': {
                    'action': 'keyboard',
                    'command': 'browser_back',
                    'description': 'Atrás en navegador',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.6
                }
            },
            'Personalizado': {}
        }
        
        return templates.get(template_name, {})
    
    def _get_template_voice_commands(self) -> Dict[str, Any]:
        """Obtiene comandos de voz pre-definidos."""
        return {
            'nyx screenshot': {
                'action': 'bash',
                'command': 'gnome-screenshot -a',
                'description': 'Tomar screenshot',
                'enabled': True
            },
            'nyx mute': {
                'action': 'bash',
                'command': 'amixer set Master mute',
                'description': 'Silenciar audio',
                'enabled': True
            },
            'nyx volume up': {
                'action': 'bash',
                'command': 'amixer set Master 5%+',
                'description': 'Subir volumen',
                'enabled': True
            },
            'nyx volume down': {
                'action': 'bash',
                'command': 'amixer set Master 5%-',
                'description': 'Bajar volumen',
                'enabled': True
            }
        }
    
    def has_changes(self) -> bool:
        """Verifica si hay cambios sin guardar."""
        if not self.current_profile or not self.original_profile_data:
            return False
        
        current_data = self.get_profile_data()
        return current_data != self.original_profile_data


class ProfileManagerWindow(QDialog):
    """
    📁 Ventana de Gestión de Perfiles NYX
    ======================================
    Permite crear, editar, eliminar y activar perfiles.
    """
    
    # Señales
    profile_saved = pyqtSignal(str)      # Señal cuando se guarda un perfil (nombre)
    profile_selected = pyqtSignal(str)   # Señal cuando se selecciona un perfil
    profile_deleted = pyqtSignal(str)    # Señal cuando se elimina un perfil
    profile_activated = pyqtSignal(str)  # Señal cuando se activa un perfil
    
    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        
        self.profile_manager = profile_manager
        self.parent = parent

        self.config = ConfigLoader() 
        
        self.setWindowTitle("📁 Gestor de Perfiles NYX")
        self.setMinimumSize(800, 600)
        
        # Estado
        self.current_profile = None
        self.has_unsaved_changes = False
        
        # Inicializar UI
        self._init_ui()
        self._setup_toolbar()
        self._load_profiles()
        
        logger.info("✅ Gestor de perfiles inicializado")
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout(self)
        
        # Barra de herramientas
        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ===== PANEL IZQUIERDO: Lista de perfiles =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Título
        title_label = QLabel("📁 Perfiles Disponibles")
        title_label.setFont(get_font('heading'))
        title_label.setStyleSheet(f"""
            color: {get_color('primary')};
            padding: 10px;
            border-bottom: 2px solid {get_color('border')};
        """)
        left_layout.addWidget(title_label)
        
        # Lista de perfiles
        self.profile_list = QListWidget()
        self.profile_list.setAlternatingRowColors(True)
        self.profile_list.currentItemChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self.profile_list, 1)
        
        # Información del perfil seleccionado
        self.profile_info_label = QLabel("Selecciona un perfil para ver detalles")
        self.profile_info_label.setWordWrap(True)
        self.profile_info_label.setStyleSheet(f"""
            padding: 10px;
            background-color: {get_color('surface')};
            border: 1px solid {get_color('border')};
            border-radius: 4px;
            margin: 5px;
        """)
        left_layout.addWidget(self.profile_info_label)
        
        # Botones de acción rápidos
        quick_btn_layout = QHBoxLayout()
        
        self.btn_activate = QPushButton("🎮 Activar")
        self.btn_activate.setToolTip("Activar este perfil en el sistema")
        self.btn_activate.clicked.connect(self._activate_profile)
        self.btn_activate.setEnabled(False)
        quick_btn_layout.addWidget(self.btn_activate)
        
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.setToolTip("Editar este perfil")
        self.btn_edit.clicked.connect(self._edit_profile)
        self.btn_edit.setEnabled(False)
        quick_btn_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton("🗑️ Eliminar")
        self.btn_delete.setToolTip("Eliminar este perfil")
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_delete.setEnabled(False)
        quick_btn_layout.addWidget(self.btn_delete)
        
        left_layout.addLayout(quick_btn_layout)
        
        # ===== PANEL DERECHO: Editor de perfil =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Título del editor
        editor_title = QLabel("✏️ Editor de Perfil")
        editor_title.setFont(get_font('heading'))
        editor_title.setStyleSheet(f"""
            color: {get_color('primary')};
            padding: 10px;
            border-bottom: 2px solid {get_color('border')};
        """)
        right_layout.addWidget(editor_title)
        
        # Widget de edición
        self.profile_editor = ProfileEditorWidget()
        self.profile_editor.profile_updated.connect(self._on_profile_updated)
        right_layout.addWidget(self.profile_editor, 1)
        
        # Botones del editor
        editor_btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("💾 Guardar")
        self.btn_save.setToolTip("Guardar cambios en el perfil")
        self.btn_save.clicked.connect(self._save_profile)
        self.btn_save.setEnabled(False)
        editor_btn_layout.addWidget(self.btn_save)
        
        self.btn_save_as = QPushButton("💾 Guardar como...")
        self.btn_save_as.setToolTip("Guardar como nuevo perfil")
        self.btn_save_as.clicked.connect(self._save_profile_as)
        self.btn_save_as.setEnabled(False)
        editor_btn_layout.addWidget(self.btn_save_as)
        
        self.btn_cancel = QPushButton("❌ Cancelar")
        self.btn_cancel.setToolTip("Cancelar cambios")
        self.btn_cancel.clicked.connect(self._cancel_edit)
        self.btn_cancel.setEnabled(False)
        editor_btn_layout.addWidget(self.btn_cancel)
        
        right_layout.addLayout(editor_btn_layout)
        
        # ===== CONFIGURAR SPLITTER =====
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        
        layout.addWidget(splitter, 1)
        
        # ===== BARRA DE ESTADO =====
        self.status_bar = QLabel("Listo")
        self.status_bar.setStyleSheet(f"""
            padding: 5px;
            background-color: {get_color('surface')};
            color: {get_color('text_secondary')};
            border-top: 1px solid {get_color('border')};
        """)
        layout.addWidget(self.status_bar)
        
        # Aplicar estilos
        self._apply_styles()
    
    def _setup_toolbar(self):
        """Configura la barra de herramientas."""
        # Acción: Nuevo perfil
        new_action = QAction("📄 Nuevo", self)
        new_action.setToolTip("Crear nuevo perfil")
        new_action.triggered.connect(self._create_profile)
        self.toolbar.addAction(new_action)
        
        self.toolbar.addSeparator()
        
        # Acción: Importar perfil
        import_action = QAction("📥 Importar", self)
        import_action.setToolTip("Importar perfil desde archivo")
        import_action.triggered.connect(self._import_profile)
        self.toolbar.addAction(import_action)
        
        # Acción: Exportar perfil
        export_action = QAction("📤 Exportar", self)
        export_action.setToolTip("Exportar perfil a archivo")
        export_action.triggered.connect(self._export_profile)
        export_action.setEnabled(False)
        self.toolbar.addAction(export_action)
        
        self.toolbar.addSeparator()
        
        # Acción: Refrescar
        refresh_action = QAction("🔄 Refrescar", self)
        refresh_action.setToolTip("Refrescar lista de perfiles")
        refresh_action.triggered.connect(self._load_profiles)
        self.toolbar.addAction(refresh_action)
        
        self.toolbar.addSeparator()
        
        # Acción: Cerrar
        close_action = QAction("🚪 Cerrar", self)
        close_action.setToolTip("Cerrar gestor de perfiles")
        close_action.triggered.connect(self.close)
        self.toolbar.addAction(close_action)
    
    def _apply_styles(self):
        """Aplica estilos a la ventana."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {get_color('background')};
                color: {get_color('text_primary')};
            }}
            QListWidget {{
                background-color: {get_color('surface')};
                border: 1px solid {get_color('border')};
                border-radius: 4px;
                padding: 5px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {get_color('border')};
            }}
            QListWidget::item:selected {{
                background-color: {get_color('primary')};
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background-color: {get_color('surface_hover')};
            }}
            QToolBar {{
                background-color: {get_color('surface')};
                border-bottom: 1px solid {get_color('border')};
                padding: 5px;
                spacing: 5px;
            }}
            QToolButton {{
                padding: 5px 10px;
                border: 1px solid transparent;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {get_color('surface_hover')};
                border-color: {get_color('border')};
            }}
        """)
    
    def _load_profiles(self):
        """Carga la lista de perfiles disponibles."""
        self.profile_list.clear()
        
        profiles = self.profile_manager.list_profiles()
        
        if not profiles:
            item = QListWidgetItem("⚠ No hay perfiles disponibles")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor(get_color('text_disabled')))
            self.profile_list.addItem(item)
            return
        
        # Obtener perfil activo actual
        active_profile = self.config.get_setting('app.last_profile', '')
        
        for profile_name in profiles:
            item = QListWidgetItem(profile_name)
            
            # Resaltar perfil activo
            if profile_name == active_profile:
                item.setText(f"🎮 {profile_name} (ACTIVO)")
                item.setForeground(QColor(get_color('success')))
                item.setFont(get_font('subheading'))
            
            # Cargar información del perfil para tooltip
            try:
                profile_data = self.profile_manager.load_profile(profile_name)
                description = profile_data.get('description', 'Sin descripción')
                author = profile_data.get('author', 'Desconocido')
                gestures_count = len(profile_data.get('gestures', {}))
                
                tooltip = f"""<b>{profile_name}</b><br>
                <i>{description}</i><br><br>
                <b>Autor:</b> {author}<br>
                <b>Gestos:</b> {gestures_count}<br>
                <b>Módulos:</b> {len(profile_data.get('enabled_modules', []))}"""
                
                item.setToolTip(tooltip)
                
            except Exception as e:
                logger.error(f"Error cargando perfil {profile_name}: {e}")
            
            self.profile_list.addItem(item)
        
        self.status_bar.setText(f"✅ {len(profiles)} perfiles cargados")
        logger.info(f"📂 Lista de perfiles cargada: {len(profiles)} perfiles")
    
    def _on_profile_selected(self, current, previous):
        """Manejador cuando se selecciona un perfil en la lista."""
        if not current:
            self._clear_editor()
            return
        
        profile_name = current.text().replace("🎮 ", "").replace(" (ACTIVO)", "")
        
        # Verificar si es el item de "no hay perfiles"
        if profile_name == "⚠ No hay perfiles disponibles":
            return
        
        try:
            # Cargar datos del perfil
            profile_data = self.profile_manager.load_profile(profile_name)
            self.current_profile = profile_name
            
            # Actualizar información del perfil
            description = profile_data.get('description', 'Sin descripción')
            author = profile_data.get('author', 'Desconocido')
            version = profile_data.get('version', '1.0.0')
            gestures_count = len(profile_data.get('gestures', {}))
            voice_commands = len(profile_data.get('voice_commands', {}))
            
            info_text = f"""
            <b>{profile_name}</b> (v{version})<br>
            <i>{description}</i><br><br>
            <b>Autor:</b> {author}<br>
            <b>Gestos:</b> {gestures_count}<br>
            <b>Comandos voz:</b> {voice_commands}<br>
            <b>Última modificación:</b> {profile_data.get('last_modified', 'Desconocida')}
            """
            
            self.profile_info_label.setText(info_text)
            
            # Cargar en editor
            self.profile_editor.load_profile(profile_name, profile_data)
            
            # Habilitar botones
            self.btn_activate.setEnabled(True)
            self.btn_edit.setEnabled(True)
            self.btn_delete.setEnabled(True)
            
            # Habilitar exportación
            for action in self.toolbar.actions():
                if action.text() == "📤 Exportar":
                    action.setEnabled(True)
            
            self.status_bar.setText(f"📂 Perfil '{profile_name}' seleccionado")
            
        except Exception as e:
            logger.error(f"Error seleccionando perfil {profile_name}: {e}")
            self.status_bar.setText(f"❌ Error cargando perfil: {str(e)}")
    
    def _on_profile_updated(self, profile_data: Dict[str, Any]):
        """Manejador cuando se actualiza el perfil en el editor."""
        self.has_unsaved_changes = True
        self.btn_save.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.status_bar.setText("⚠ Cambios sin guardar")
    
    def _create_profile(self):
        """Crea un nuevo perfil."""
        name, ok = QInputDialog.getText(
            self, 
            "📄 Nuevo Perfil",
            "Nombre del nuevo perfil:",
            QLineEdit.EchoMode.Normal,
            "nuevo_perfil"
        )
        
        if ok and name:
            # Verificar si ya existe
            if name in self.profile_manager.list_profiles():
                QMessageBox.warning(
                    self,
                    "Perfil existente",
                    f"El perfil '{name}' ya existe. Usa otro nombre."
                )
                return
            
            # Crear perfil básico
            profile_data = {
                'profile_name': name,
                'description': 'Nuevo perfil personalizado',
                'version': '1.0.0',
                'author': 'Usuario',
                'gestures': {},
                'voice_commands': {},
                'settings': {
                    'mouse_sensitivity': 1.5,
                    'keyboard_delay': 0.1,
                    'gesture_cooldown': 0.3
                },
                'enabled_modules': ['hand', 'voice', 'keyboard', 'mouse'],
                'created_at': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Guardar perfil
            self.profile_manager.save_profile(name, profile_data)
            
            # Recargar lista
            self._load_profiles()
            
            # Seleccionar nuevo perfil
            items = self.profile_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.profile_list.setCurrentItem(items[0])
            
            self.status_bar.setText(f"✅ Perfil '{name}' creado")
            self.profile_saved.emit(name)
            
            logger.info(f"📄 Nuevo perfil creado: {name}")
    
    def _edit_profile(self):
        """Habilita la edición del perfil seleccionado."""
        if self.current_profile:
            self.btn_edit.setEnabled(False)
            self.status_bar.setText(f"✏️ Editando perfil '{self.current_profile}'")
    
    def _save_profile(self):
        """Guarda los cambios del perfil editado."""
        if not self.current_profile:
            return
        
        try:
            profile_data = self.profile_editor.get_profile_data()
            profile_name = profile_data['profile_name']
            
            # Verificar si cambió el nombre
            if profile_name != self.current_profile:
                # Es un cambio de nombre, preguntar al usuario
                reply = QMessageBox.question(
                    self,
                    "Cambiar nombre",
                    f"¿Cambiar nombre del perfil de '{self.current_profile}' a '{profile_name}'?\n\n"
                    "Esto creará un nuevo perfil y mantendrá el original.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Guardar como nuevo perfil
                    self.profile_manager.save_profile(profile_name, profile_data)
                    
                    # Recargar lista
                    self._load_profiles()
                    
                    # Seleccionar nuevo perfil
                    items = self.profile_list.findItems(profile_name, Qt.MatchFlag.MatchExactly)
                    if items:
                        self.profile_list.setCurrentItem(items[0])
                    
                    self.status_bar.setText(f"✅ Perfil guardado como '{profile_name}'")
                    self.profile_saved.emit(profile_name)
                    
                    logger.info(f"💾 Perfil guardado con nuevo nombre: {profile_name}")
                    return
            
            # Actualizar fecha de modificación
            profile_data['last_modified'] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Guardar perfil (actualización)
            self.profile_manager.save_profile(self.current_profile, profile_data)
            
            # Actualizar estado
            self.has_unsaved_changes = False
            self.btn_save.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            
            # Recargar lista
            self._load_profiles()
            
            self.status_bar.setText(f"✅ Perfil '{self.current_profile}' guardado")
            self.profile_saved.emit(self.current_profile)
            
            logger.info(f"💾 Perfil guardado: {self.current_profile}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando perfil: {e}")
            self.status_bar.setText(f"❌ Error guardando: {str(e)}")
            QMessageBox.critical(self, "Error", f"No se pudo guardar el perfil:\n{str(e)}")
    
    def _save_profile_as(self):
        """Guarda el perfil actual con un nuevo nombre."""
        if not self.current_profile:
            return
        
        profile_data = self.profile_editor.get_profile_data()
        current_name = profile_data['profile_name']
        
        new_name, ok = QInputDialog.getText(
            self,
            "💾 Guardar como...",
            "Nuevo nombre para el perfil:",
            QLineEdit.EchoMode.Normal,
            f"{current_name}_copia"
        )
        
        if ok and new_name:
            # Verificar si ya existe
            if new_name in self.profile_manager.list_profiles():
                QMessageBox.warning(
                    self,
                    "Perfil existente",
                    f"El perfil '{new_name}' ya existe. Usa otro nombre."
                )
                return
            
            # Actualizar nombre en datos
            profile_data['profile_name'] = new_name
            
            # Guardar como nuevo perfil
            self.profile_manager.save_profile(new_name, profile_data)
            
            # Recargar lista
            self._load_profiles()
            
            # Seleccionar nuevo perfil
            items = self.profile_list.findItems(new_name, Qt.MatchFlag.MatchExactly)
            if items:
                self.profile_list.setCurrentItem(items[0])
            
            self.status_bar.setText(f"✅ Perfil guardado como '{new_name}'")
            self.profile_saved.emit(new_name)
    
    def _cancel_edit(self):
        """Cancela la edición actual."""
        if self.current_profile and self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Cancelar cambios",
                "¿Descartar los cambios no guardados?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Recargar perfil original
                profile_data = self.profile_manager.load_profile(self.current_profile)
                self.profile_editor.load_profile(self.current_profile, profile_data)
                
                # Resetear estado
                self.has_unsaved_changes = False
                self.btn_save.setEnabled(False)
                self.btn_cancel.setEnabled(False)
                
                self.status_bar.setText("❌ Cambios descartados")
    
    def _activate_profile(self):
        """Activa el perfil seleccionado."""
        if not self.current_profile:
            return
        
        try:
            # Cargar perfil para activarlo
            success = self.profile_manager.load_profile(self.current_profile)
            
            if success:
                # Emitir señal de perfil activado
                self.profile_activated.emit(self.current_profile)
                
                # Actualizar configuración
                self.config.update_setting('app.last_profile', self.current_profile)
                self.config.save_settings()
                
                # Actualizar UI
                self._load_profiles()  # Para mostrar "ACTIVO"
                
                self.status_bar.setText(f"🎮 Perfil '{self.current_profile}' activado")
                
                # Mostrar mensaje en parent si existe
                if self.parent and hasattr(self.parent, '_log_to_console'):
                    self.parent._log_to_console(
                        f"🎮 Perfil activado: {self.current_profile}",
                        get_color('success')
                    )
                
                logger.info(f"🎮 Perfil activado: {self.current_profile}")
                
            else:
                self.status_bar.setText(f"❌ No se pudo activar el perfil")
                QMessageBox.warning(self, "Error", f"No se pudo activar el perfil '{self.current_profile}'")
                
        except Exception as e:
            logger.error(f"❌ Error activando perfil: {e}")
            self.status_bar.setText(f"❌ Error activando: {str(e)}")
    
    def _delete_profile(self):
        """Elimina el perfil seleccionado."""
        if not self.current_profile:
            return
        
        # Confirmar eliminación
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar permanentemente el perfil '{self.current_profile}'?\n\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Eliminar perfil
                success = self.profile_manager.delete_profile(self.current_profile)
                
                if success:
                    # Emitir señal
                    self.profile_deleted.emit(self.current_profile)
                    
                    # Limpiar editor
                    self._clear_editor()
                    
                    # Recargar lista
                    self._load_profiles()
                    
                    self.status_bar.setText(f"🗑️ Perfil '{self.current_profile}' eliminado")
                    logger.info(f"🗑️ Perfil eliminado: {self.current_profile}")
                    
                    # Mostrar mensaje en parent si existe
                    if self.parent and hasattr(self.parent, '_log_to_console'):
                        self.parent._log_to_console(
                            f"🗑️ Perfil eliminado: {self.current_profile}",
                            get_color('warning')
                        )
                    
                else:
                    QMessageBox.warning(self, "Error", f"No se pudo eliminar el perfil '{self.current_profile}'")
                    
            except Exception as e:
                logger.error(f"❌ Error eliminando perfil: {e}")
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el perfil:\n{str(e)}")
    
    def _import_profile(self):
        """Importa un perfil desde archivo JSON."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "📥 Importar Perfil",
            "",
            "Archivos JSON (*.json);;Todos los archivos (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    import json
                    profile_data = json.load(f)
                
                # Verificar estructura básica
                if 'profile_name' not in profile_data:
                    profile_name = Path(file_path).stem
                    profile_data['profile_name'] = profile_name
                else:
                    profile_name = profile_data['profile_name']
                
                # Verificar si ya existe
                if profile_name in self.profile_manager.list_profiles():
                    reply = QMessageBox.question(
                        self,
                        "Perfil existente",
                        f"El perfil '{profile_name}' ya existe. ¿Sobreescribir?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.No:
                        return
                
                # Guardar perfil
                self.profile_manager.save_profile(profile_name, profile_data)
                
                # Recargar lista
                self._load_profiles()
                
                self.status_bar.setText(f"📥 Perfil '{profile_name}' importado")
                self.profile_saved.emit(profile_name)
                
                logger.info(f"📥 Perfil importado: {profile_name}")
                
            except Exception as e:
                logger.error(f"❌ Error importando perfil: {e}")
                QMessageBox.critical(
                    self,
                    "Error de importación",
                    f"No se pudo importar el perfil:\n{str(e)}"
                )
    
    def _export_profile(self):
        """Exporta el perfil seleccionado a archivo JSON."""
        if not self.current_profile:
            return
        
        # Obtener datos del perfil
        profile_data = self.profile_manager.load_profile(self.current_profile)
        
        # Solicitar ubicación para guardar
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "📤 Exportar Perfil",
            f"{self.current_profile}.json",
            "Archivos JSON (*.json);;Todos los archivos (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(profile_data, f, indent=2, ensure_ascii=False)
                
                self.status_bar.setText(f"📤 Perfil exportado a: {file_path}")
                logger.info(f"📤 Perfil exportado: {self.current_profile} -> {file_path}")
                
            except Exception as e:
                logger.error(f"❌ Error exportando perfil: {e}")
                QMessageBox.critical(
                    self,
                    "Error de exportación",
                    f"No se pudo exportar el perfil:\n{str(e)}"
                )
    
    def _clear_editor(self):
        """Limpia el editor de perfiles."""
        self.current_profile = None
        self.has_unsaved_changes = False
        
        self.profile_editor.load_profile("", {})
        
        self.btn_activate.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.profile_info_label.setText("Selecciona un perfil para ver detalles")
        
        # Deshabilitar exportación
        for action in self.toolbar.actions():
            if action.text() == "📤 Exportar":
                action.setEnabled(False)
    
    def closeEvent(self, event):
        """Manejador cuando se cierra la ventana."""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Cambios sin guardar",
                "Hay cambios sin guardar en el perfil actual. ¿Quieres guardarlos antes de salir?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self._save_profile()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# Función para abrir el gestor de perfiles
def open_profile_manager(parent=None, profile_manager=None):
    """
    Abre la ventana de gestión de perfiles.
    
    Args:
        parent: Ventana padre
        profile_manager: Instancia de ProfileManager
        
    Returns:
        ProfileManagerWindow: Instancia de la ventana
    """
    if profile_manager is None:
        from core.profile_manager import ProfileManager
        profile_manager = ProfileManager()
    
    window = ProfileManagerWindow(profile_manager, parent)
    return window


if __name__ == "__main__":
    # Para pruebas independientes
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Aplicar tema
    from ui.styles import styles
    styles.apply_to_app(app)
    
    # Crear gestor de perfiles de prueba
    from core.profile_manager import ProfileManager
    profile_manager = ProfileManager()
    
    # Crear ventana
    window = ProfileManagerWindow(profile_manager)
    window.show()
    
    sys.exit(app.exec())