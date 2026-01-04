"""
🎤 Voice Command Editor Dialog
Dialogo para editar comandos de voz.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox,
    QTextEdit, QCheckBox, QDialogButtonBox,
    QGroupBox
)
from PyQt6.QtCore import Qt

from ui.styles import get_color, get_font


class VoiceCommandEditorDialog(QDialog):
    """Diálogo para editar un comando de voz."""
    
    def __init__(self, parent=None, command_data=None):
        super().__init__(parent)
        
        self.command_data = command_data or {}
        self.setWindowTitle("🎤 Editor de Comandos de Voz")
        self.setGeometry(300, 300, 500, 300)
        
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        """Inicializa la interfaz."""
        layout = QVBoxLayout()
        
        # Información del comando
        info_group = QGroupBox("Información del Comando")
        info_layout = QFormLayout()
        
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Ej: nyx screenshot, nyx volume up")
        info_layout.addRow("Comando de voz:", self.command_input)
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(["keyboard", "mouse", "bash", "window", "custom"])
        info_layout.addRow("Tipo de acción:", self.action_combo)
        
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Ej: space, click, gnome-screenshot -a")
        info_layout.addRow("Acción objetivo:", self.target_input)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Configuración
        config_group = QGroupBox("Configuración")
        config_layout = QFormLayout()
        
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        self.description_input.setPlaceholderText("Descripción del comando...")
        config_layout.addRow("Descripción:", self.description_input)
        
        self.enabled_check = QCheckBox("Comando habilitado")
        self.enabled_check.setChecked(True)
        config_layout.addRow(self.enabled_check)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
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
        """Carga los datos del comando si existen."""
        if self.command_data:
            self.command_input.setText(self.command_data.get('command', ''))
            self.action_combo.setCurrentText(self.command_data.get('action', 'bash'))
            self.target_input.setText(self.command_data.get('target', ''))
            self.description_input.setText(self.command_data.get('description', ''))
            self.enabled_check.setChecked(self.command_data.get('enabled', True))
    
    def get_command_data(self) -> dict:
        """Obtiene los datos del comando."""
        return {
            'command': self.command_input.text().strip(),
            'action': self.action_combo.currentText(),
            'target': self.target_input.text().strip(),
            'description': self.description_input.toPlainText().strip(),
            'enabled': self.enabled_check.isChecked()
        }