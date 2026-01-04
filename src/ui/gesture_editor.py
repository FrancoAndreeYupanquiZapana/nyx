"""
👋 Gesture Editor Dialog
Dialogo para editar gestos individuales.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox,
    QCheckBox, QTextEdit, QPushButton, QDialogButtonBox,
    QGroupBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.styles import get_color, get_font


class GestureEditorDialog(QDialog):
    """Diálogo para editar un gesto."""
    
    def __init__(self, parent=None, gesture_data=None):
        super().__init__(parent)
        
        self.gesture_data = gesture_data or {}
        self.setWindowTitle("✏️ Editor de Gestos")
        self.setGeometry(300, 300, 500, 400)
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Información básica
        basic_group = QGroupBox("Información del Gesto")
        basic_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: puño, paz, pulgar arriba")
        basic_layout.addRow("Nombre:", self.name_input)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["hand", "arm", "pose"])
        basic_layout.addRow("Tipo:", self.type_combo)
        
        self.hand_combo = QComboBox()
        self.hand_combo.addItems(["right", "left", "both"])
        basic_layout.addRow("Mano:", self.hand_combo)
        
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # Configuración
        config_group = QGroupBox("Configuración")
        config_layout = QFormLayout()
        
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(0.7)
        config_layout.addRow("Confianza mínima:", self.confidence_spin)
        
        self.enabled_check = QCheckBox("Gesto habilitado")
        self.enabled_check.setChecked(True)
        config_layout.addRow(self.enabled_check)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Acción
        action_group = QGroupBox("Acción")
        action_layout = QFormLayout()
        
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            "keyboard", "mouse", "window", "bash",
            "combination", "custom"
        ])
        action_layout.addRow("Tipo de acción:", self.action_combo)
        
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Ej: space, click, gnome-screenshot")
        action_layout.addRow("Comando:", self.command_input)
        
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        self.description_input.setPlaceholderText("Descripción de la acción...")
        action_layout.addRow("Descripción:", self.description_input)
        
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        self.setLayout(layout)
    
    def _load_data(self):
        """Carga los datos del gesto si existen."""
        if self.gesture_data:
            self.name_input.setText(self.gesture_data.get('name', ''))
            self.type_combo.setCurrentText(self.gesture_data.get('type', 'hand'))
            self.hand_combo.setCurrentText(self.gesture_data.get('hand', 'right'))
            self.confidence_spin.setValue(self.gesture_data.get('confidence', 0.7))
            self.enabled_check.setChecked(self.gesture_data.get('enabled', True))
            self.action_combo.setCurrentText(self.gesture_data.get('action', 'keyboard'))
            self.command_input.setText(self.gesture_data.get('command', ''))
            self.description_input.setText(self.gesture_data.get('description', ''))
    
    def get_gesture_data(self) -> dict:
        """Obtiene los datos del gesto."""
        return {
            'name': self.name_input.text().strip(),
            'type': self.type_combo.currentText(),
            'hand': self.hand_combo.currentText(),
            'confidence': self.confidence_spin.value(),
            'enabled': self.enabled_check.isChecked(),
            'action': self.action_combo.currentText(),
            'command': self.command_input.text().strip(),
            'description': self.description_input.toPlainText().strip()
        }