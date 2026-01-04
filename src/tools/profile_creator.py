"""
🛠️ SIMPLE PROFILE CREATOR - Herramienta visual simple para crear perfiles JSON
=============================================================================
Una interfaz gráfica mejorada para que el usuario cree y edite perfiles
sin complicaciones. Soporta modo Dialog para integración.
Versión Final: Compacta, sin scroll global, botones siempre visibles.
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Asegurar que podemos importar módulos del proyecto
current_dir = Path(__file__).parent.absolute()
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QComboBox, QPushButton, 
    QCheckBox, QGroupBox, QFormLayout, QMessageBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

# Importar lógica de Nyx
from core.profile_manager import ProfileManager, ProfileData
from ui.styles import styles, get_color, get_font

class SimpleProfileCreator(QDialog): 
    profile_saved = pyqtSignal(str) 

    def __init__(self, parent=None, edit_mode=False):
        super().__init__(parent)
        
        self.profile_manager = ProfileManager()
        self.edit_mode = edit_mode
        self.original_name = None
        
        self.setWindowTitle("✨ Nyx - Editor de Perfiles" if edit_mode else "✨ Nyx - Nuevo Perfil")
        # Altura reducida para pantallas pequeñas
        self.setMinimumSize(600, 650) 
        self.setMaximumWidth(750)
        self.setModal(True)
        
        # Aplicar tema oscuro
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
                font-size: 13px;
            }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox, QDoubleSpinBox, QTableWidget {
                background-color: #2d2d2d;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
                min-height: 24px;
            }
            QComboBox::drop-down {
                border: 0px;
                width: 20px;
            }
            QTableWidget::item { 
                padding: 4px; 
            }
            QHeaderView::section {
                background-color: #3e3e3e;
                color: white;
                padding: 5px;
                border: 1px solid #1e1e1e;
                font-weight: bold;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0098ff;
            }
            QGroupBox {
                border: 1px solid #3e3e3e;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #00a5ff;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        # Mapa de gestos
        self.gesture_map = {
            'fist': '✊ Puño Cerrado',
            'peace': '✌️ Amor y Paz',
            'victory': '✌️ Victoria',
            'thumbs_up': '👍 Pulgar Arriba',
            'thumbs_down': '👎 Pulgar Abajo',
            'rock': '🤘 Rock / Cuernos',
            'call_me': '🤙 Llámame',
            'point': '☝️ Dedo Índice',
            'ok': '👌 OK / Círculo',
            'palm': '✋ Palma Abierta'
        }
        
        self.mouse_actions = {
            'click': 'Click Izquierdo',
            'right_click': 'Click Derecho',
            'double_click': 'Doble Click',
            'scroll_up': 'Scroll Arriba',
            'scroll_down': 'Scroll Abajo',
            'move': 'Mover Cursor',
            'drag_start': 'Iniciar Arrastre',
            'drag_end': 'Soltar Arrastre'
        }
        
        self.common_keys = [
            'space', 'enter', 'esc', 'tab', 'backspace', 
            'ctrl', 'alt', 'shift', 
            'up', 'down', 'left', 'right',
            'a', 'w', 's', 'd', 'e', 'r', 'f', 'q', 
            'ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+z', 'alt+tab'
        ]
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10) # Espaciado compacto
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Título
        title_text = "Editar Perfil" if self.edit_mode else "Crear Nuevo Perfil"
        title = QLabel(title_text)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #00a5ff; margin-bottom: 2px;")
        layout.addWidget(title)
        
        # 1. Datos Básicos
        basic_group = QGroupBox("📝 Info Básica")
        basic_layout = QFormLayout()
        basic_layout.setContentsMargins(10, 5, 10, 5)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Minecraft, Trabajo...")
        if self.edit_mode:
            self.name_input.setReadOnly(True) 
            self.name_input.setToolTip("El nombre no se puede cambiar en modo edición")
            
        basic_layout.addRow("Nombre:", self.name_input)
        
        self.author_input = QLineEdit()
        self.author_input.setText("Usuario")
        basic_layout.addRow("Autor:", self.author_input)
        
        self.os_combo = QComboBox()
        self.os_combo.addItems(["Cualquiera", "Windows", "Linux"])
        self.os_combo.setItemIcon(1, QIcon()) # Metadata or custom styles could be added later
        basic_layout.addRow("Sistema (SO):", self.os_combo)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 2. Plantilla (Compacta)
        if not self.edit_mode:
            template_group = QGroupBox("⚡ Inicio Rápido")
            template_layout = QHBoxLayout()
            template_layout.setContentsMargins(10, 5, 10, 5)
            
            label_temp = QLabel("Plantilla:")
            template_layout.addWidget(label_temp)
            
            self.template_combo = QComboBox()
            self.template_combo.addItems([
                "Personalizado (Vacío)",
                "Gaming (WASD style)",
                "Navegación (Mouse)",
                "Productividad (Ctrl+C/V)"
            ])
            self.template_combo.setMinimumWidth(200)
            template_layout.addWidget(self.template_combo)
            
            btn_apply = QPushButton("Aplicar")
            btn_apply.setStyleSheet("background-color: #444; max-width: 60px; padding: 5px;")
            btn_apply.clicked.connect(self.apply_template)
            template_layout.addWidget(btn_apply)
            
            template_group.setLayout(template_layout)
            layout.addWidget(template_group)
        
        # 3. VISUAL MAPPER
        mapper_group = QGroupBox("🛠️ Mapa de Gestos")
        mapper_layout = QVBoxLayout()
        mapper_layout.setContentsMargins(5, 10, 5, 5)
        
        self.gesture_table = QTableWidget()
        self.gesture_table.setColumnCount(3)
        self.gesture_table.setHorizontalHeaderLabels(["Gesto", "Acción", "Comando / Tecla"])
        
        header = self.gesture_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.gesture_table.verticalHeader().setVisible(False)
        # Altura fija suficiente para ver ~5-6 filas, scroll interno
        self.gesture_table.setMinimumHeight(280) 
        self.gesture_table.setAlternatingRowColors(True)
        self.gesture_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.gesture_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #353535;
                gridline-color: #444444;
                border: 1px solid #3e3e3e;
            }
            QTableWidget::item {
                padding-left: 8px;
            }
        """)
        
        self.gesture_table.setRowCount(len(self.gesture_map))
        self.gesture_table.verticalHeader().setDefaultSectionSize(45)

        for i, (gesture_key, gesture_friendly) in enumerate(self.gesture_map.items()):
            item_name = QTableWidgetItem(gesture_friendly)
            item_name.setData(Qt.ItemDataRole.UserRole, gesture_key)
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item_name.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.gesture_table.setItem(i, 0, item_name)
            
            combo_action = QComboBox()
            combo_action.addItems(["NONE", "mouse", "keyboard", "bash", "window"])
            combo_action.setItemText(0, "➖ Nada")
            combo_action.setItemText(1, "🖱️ Mouse")
            combo_action.setItemText(2, "⌨️ Teclado")
            combo_action.setItemText(3, "💻 CMD")
            combo_action.setItemText(4, "🪟 Win")
            
            combo_action.setProperty("row", i)
            combo_action.currentIndexChanged.connect(self.on_action_change)
            self.gesture_table.setCellWidget(i, 1, combo_action)
            self._set_cell_widget_by_type(i, "NONE")
            
        mapper_layout.addWidget(self.gesture_table)
        mapper_group.setLayout(mapper_layout)
        layout.addWidget(mapper_group)
        
        # 4. Ajustes y Módulos (En horizontal para ahorrar espacio vertical)
        row_config = QHBoxLayout()
        row_config.setSpacing(10)
        
        modules_group = QGroupBox("Módulos")
        modules_layout = QVBoxLayout()
        modules_layout.setContentsMargins(10, 5, 10, 5)
        modules_layout.setSpacing(2)
        self.check_voice = QCheckBox("Voz"); self.check_voice.setChecked(True)
        self.check_mouse = QCheckBox("Mouse"); self.check_mouse.setChecked(True)
        self.check_keyboard = QCheckBox("Teclado"); self.check_keyboard.setChecked(True)
        modules_layout.addWidget(self.check_voice)
        modules_layout.addWidget(self.check_mouse)
        modules_layout.addWidget(self.check_keyboard)
        modules_group.setLayout(modules_layout)
        row_config.addWidget(modules_group)
        
        settings_group = QGroupBox("Ajustes")
        settings_layout = QFormLayout()
        settings_layout.setContentsMargins(10, 5, 10, 5)
        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(0.1, 10.0); self.sensitivity.setValue(1.5)
        self.sensitivity.setSingleStep(0.1)
        settings_layout.addRow("Sensibilidad:", self.sensitivity)
        settings_group.setLayout(settings_layout)
        row_config.addWidget(settings_group)
        
        layout.addLayout(row_config)
        
        # Botones Finales
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("background-color: #444; min-width: 80px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save_text = "Guardar Cambios" if self.edit_mode else "✨ CREAR PERFIL"
        self.btn_create = QPushButton(btn_save_text)
        self.btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create.setMinimumWidth(150)
        self.btn_create.setStyleSheet("""
            QPushButton { background-color: #00cc66; font-size: 14px; padding: 10px; }
            QPushButton:hover { background-color: #00ee77; }
        """)
        self.btn_create.clicked.connect(self.create_profile)
        btn_layout.addWidget(self.btn_create)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _set_cell_widget_by_type(self, row, type_name, current_value=None):
        if type_name == "mouse":
            combo = QComboBox()
            for key, val in self.mouse_actions.items():
                combo.addItem(val, key)
            if current_value:
                idx = combo.findData(current_value)
                if idx >= 0: combo.setCurrentIndex(idx)
            self.gesture_table.setCellWidget(row, 2, combo)
        elif type_name == "keyboard":
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.addItems(self.common_keys)
            if current_value:
                combo.setCurrentText(str(current_value))
            else:
                combo.setCurrentText("")
                combo.setPlaceholderText("Tecla...")
            self.gesture_table.setCellWidget(row, 2, combo)
        elif type_name in ["bash", "window"]:
            line = QLineEdit()
            line.setPlaceholderText("Comando..." if type_name=="bash" else "Ventana...")
            if current_value: line.setText(str(current_value))
            self.gesture_table.setCellWidget(row, 2, line)
        else:
            line = QLineEdit()
            line.setPlaceholderText("-")
            line.setEnabled(False)
            self.gesture_table.setCellWidget(row, 2, line)

    def on_action_change(self, index):
        sender = self.sender()
        if not sender: return
        row = sender.property("row")
        types = ["NONE", "mouse", "keyboard", "bash", "window"]
        selected_type = types[index]
        self._set_cell_widget_by_type(row, selected_type)

    def _get_command_from_row(self, row):
        widget = self.gesture_table.cellWidget(row, 2)
        if isinstance(widget, QComboBox):
            if widget.isEditable():
                return widget.currentText()
            else:
                return widget.currentData()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    def load_profile_data(self, profile_data: Dict):
        if not profile_data: return
        self.original_name = profile_data.get('profile_name', '')
        self.name_input.setText(self.original_name)
        self.author_input.setText(profile_data.get('author', 'Usuario'))
        mods = profile_data.get('enabled_modules', [])
        self.check_voice.setChecked('voice' in mods)
        self.check_mouse.setChecked('mouse' in mods)
        self.check_keyboard.setChecked('keyboard' in mods)
        settings = profile_data.get('settings', {})
        if 'mouse_sensitivity' in settings:
            self.sensitivity.setValue(float(settings['mouse_sensitivity']))
        gestures = profile_data.get('gestures', {})
        for i in range(self.gesture_table.rowCount()):
            gesture_key = self.gesture_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            if gesture_key in gestures:
                g_data = gestures[gesture_key]
                if g_data.get('enabled', False):
                    action = g_data.get('action', 'NONE')
                    command = g_data.get('command', '')
                    combo_type = self.gesture_table.cellWidget(i, 1)
                    types_map = {"NONE":0, "mouse":1, "keyboard":2, "bash":3, "window":4}
                    idx = types_map.get(action, 0)
                    combo_type.blockSignals(True)
                    combo_type.setCurrentIndex(idx)
                    combo_type.blockSignals(False)
                    self._set_cell_widget_by_type(i, action, command)
                    
        # OS (new)
        os_val = profile_data.get('os_type', 'any')
        os_map = {"any": 0, "windows": 1, "linux": 2}
        self.os_combo.setCurrentIndex(os_map.get(os_val, 0))

    def apply_template(self):
        txt = self.template_combo.currentText()
        presets = {}
        if "Gaming" in txt:
            presets = {'fist': ('keyboard', 'space'), 'peace': ('keyboard', 'r'), 'thumbs_up': ('keyboard', 'e'), 'point': ('mouse', 'move')}
        elif "Navegación" in txt:
            presets = {'point': ('mouse', 'move'), 'fist': ('mouse', 'click'), 'peace': ('mouse', 'right_click'), 'victory': ('mouse', 'scroll_up'), 'rock': ('mouse', 'scroll_down')}
        elif "Productividad" in txt:
            presets = {'point': ('mouse', 'move'), 'fist': ('keyboard', 'ctrl+s'), 'peace': ('keyboard', 'ctrl+c'), 'thumbs_up': ('keyboard', 'ctrl+v')}
            
        for i in range(self.gesture_table.rowCount()):
            gesture_key = self.gesture_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            combo_type = self.gesture_table.cellWidget(i, 1)
            combo_type.setCurrentIndex(0)
            self._set_cell_widget_by_type(i, "NONE")
            if gesture_key in presets:
                action, cmd = presets[gesture_key]
                types_map = {"NONE":0, "mouse":1, "keyboard":2, "bash":3, "window":4}
                idx = types_map.get(action, 0)
                combo_type.setCurrentIndex(idx)
                self._set_cell_widget_by_type(i, action, cmd)

    def create_profile(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "¡Falta el nombre del perfil!")
            return
        gestures_config = {}
        for i in range(self.gesture_table.rowCount()):
            gesture_key = self.gesture_table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            combo_type = self.gesture_table.cellWidget(i, 1)
            # types in order: "NONE", "mouse", "keyboard", "bash", "window"
            types = ["NONE", "mouse", "keyboard", "bash", "window"]
            action_type = types[combo_type.currentIndex()]
            command = self._get_command_from_row(i)
            if action_type != "NONE" and command:
                gestures_config[gesture_key] = {
                    'action': action_type, 'command': command, 'description': f"Acción {command}",
                    'enabled': True, 'type': 'hand', 'hand': 'right', 'confidence': 0.7
                }
        modules = ['hand']
        if self.check_voice.isChecked(): modules.append('voice')
        if self.check_keyboard.isChecked(): modules.append('keyboard')
        if self.check_mouse.isChecked(): modules.append('mouse')
        
        try:
            desc = f"Perfil {name}"
            os_map = {0: "any", 1: "windows", 2: "linux"}
            os_type = os_map.get(self.os_combo.currentIndex(), "any")
            
            new_profile = ProfileData(
                profile_name=name, author=self.author_input.text(), description=desc,
                os_type=os_type,
                gestures=gestures_config, voice_commands={},
                settings={'mouse_sensitivity': self.sensitivity.value(), 'keyboard_delay': 0.1, 'gesture_cooldown': 0.3},
                enabled_modules=modules
            )
            self.profile_manager.save_profile(new_profile)
            msg = f"Perfil '{name}' {'actualizado' if self.edit_mode else 'creado'} correctamente."
            QMessageBox.information(self, "¡Éxito!", msg)
            self.profile_saved.emit(name)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Fatal", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleProfileCreator()
    if window.exec(): print("Perfil creado")
    sys.exit()
