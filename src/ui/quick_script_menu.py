"""
⚡ QUICK SCRIPT MENU - Modal para ejecutar scripts rápidamente
==============================================================
Muestra un menú flotante con scripts disponibles según el OS del perfil activo.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

from core.script_manager import ScriptManager
from ui.styles import get_color, get_font

logger = logging.getLogger(__name__)


class ScriptListItem(QWidget):
    """Widget personalizado para cada item de script en la lista."""
    
    def __init__(self, script: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.script = script
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz del item."""
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)
        
        # Icono
        icon_label = QLabel(self.script.get('icon', '📄'))
        icon_label.setFont(QFont("Segoe UI Emoji", 20))
        icon_label.setFixedWidth(40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Contenido (nombre + descripción)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        # Nombre
        name_label = QLabel(self.script.get('name', 'Sin nombre'))
        name_label.setFont(get_font('heading'))
        name_label.setStyleSheet(f"color: {get_color('text_primary')}; font-weight: bold;")
        content_layout.addWidget(name_label)
        
        # Descripción
        desc_label = QLabel(self.script.get('description', ''))
        desc_label.setFont(get_font('body'))
        desc_label.setStyleSheet(f"color: {get_color('text_secondary')}; font-size: 11px;")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)
        
        layout.addLayout(content_layout, 1)
        
        self.setLayout(layout)


class QuickScriptMenu(QDialog):
    """Modal flotante para seleccionar y ejecutar scripts rápidamente."""
    
    script_executed = pyqtSignal(str)  # Emite el ID del script ejecutado
    
    def __init__(self, profile_os: str = "any", parent=None):
        super().__init__(parent)
        
        self.profile_os = profile_os
        self.script_manager = ScriptManager()
        self.selected_script = None
        
        self._init_ui()
        self._load_scripts()
        self._apply_styles()
    
    def _init_ui(self):
        """Inicializa la interfaz del modal."""
        self.setWindowTitle("Scripts Rápidos")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.setMaximumSize(600, 600)
        
        # Layout principal
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Lista de scripts
        self.script_list = QListWidget()
        self.script_list.setSpacing(4)
        self.script_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.script_list.itemClicked.connect(self._on_script_clicked)
        self.script_list.itemDoubleClicked.connect(self._on_script_double_clicked)
        layout.addWidget(self.script_list, 1)
        
        # Footer con botón cancelar
        footer = self._create_footer()
        layout.addWidget(footer)
        
        self.setLayout(layout)
    
    def _create_header(self) -> QWidget:
        """Crea el header del modal."""
        header = QFrame()
        header.setObjectName("header")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Título
        title = QLabel("⚡ Scripts Rápidos")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {get_color('accent')}; background: transparent;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Info del OS
        os_label = QLabel(f"OS: {self.profile_os.upper()}")
        os_label.setFont(get_font('caption'))
        os_label.setStyleSheet(f"color: {get_color('text_secondary')}; background: transparent; padding: 4px 8px; border-radius: 4px; background-color: {get_color('surface')};")
        layout.addWidget(os_label)
        
        header.setLayout(layout)
        return header
    
    def _create_footer(self) -> QWidget:
        """Crea el footer del modal."""
        footer = QFrame()
        footer.setObjectName("footer")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        
        layout.addStretch()
        
        # Botón cancelar
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFont(get_font('body'))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(100)
        layout.addWidget(cancel_btn)
        
        # Botón ejecutar (nuevo)
        self.execute_btn = QPushButton("Ejecutar")
        self.execute_btn.setFont(get_font('body'))
        self.execute_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('accent')};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {get_color('accent_hover')};
            }}
            QPushButton:disabled {{
                background-color: {get_color('border')};
                color: {get_color('text_disabled')};
            }}
        """)
        self.execute_btn.clicked.connect(self._on_execute_clicked)
        self.execute_btn.setEnabled(False)  # Deshabilitado al inicio
        self.execute_btn.setMinimumWidth(100)
        layout.addWidget(self.execute_btn)
        
        footer.setLayout(layout)
        return footer
    
    def _load_scripts(self):
        """Carga los scripts compatibles con el OS del perfil."""
        self.script_list.clear()
        
        # Obtener scripts compatibles
        scripts = self.script_manager.get_scripts_for_os(self.profile_os)
        
        if not scripts:
            # Mostrar mensaje si no hay scripts
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 60))
            self.script_list.addItem(item)
            
            no_scripts_widget = QLabel("No hay scripts disponibles para este sistema operativo")
            no_scripts_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_scripts_widget.setStyleSheet(f"color: {get_color('text_secondary')}; padding: 20px;")
            self.script_list.setItemWidget(item, no_scripts_widget)
            return
        
        # Agregar cada script como item
        for script in scripts:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, script)
            item.setSizeHint(QSize(0, 70))
            
            self.script_list.addItem(item)
            
            # Widget personalizado para el item
            script_widget = ScriptListItem(script)
            self.script_list.setItemWidget(item, script_widget)
        
        logger.info(f"📋 Cargados {len(scripts)} scripts para OS: {self.profile_os}")
    
    def _on_script_clicked(self, item: QListWidgetItem):
        """Manejador cuando se hace click en un script."""
        script = item.data(Qt.ItemDataRole.UserRole)
        if script:
            self.selected_script = script
            self.execute_btn.setEnabled(True)  # Habilitar botón
            logger.debug(f"Script seleccionado: {script.get('name')}")
    
    def _on_execute_clicked(self):
        """Manejador del botón ejecutar."""
        if self.selected_script:
            self._execute_script(self.selected_script)
    
    def _on_script_double_clicked(self, item: QListWidgetItem):
        """Manejador cuando se hace doble click en un script (ejecutar)."""
        script = item.data(Qt.ItemDataRole.UserRole)
        if script:
            self._execute_script(script)
    
    def _execute_script(self, script: Dict[str, Any]):
        """Ejecuta el script seleccionado."""
        script_id = script.get('id')
        script_name = script.get('name')
        
        logger.info(f"🚀 Ejecutando script: {script_name}")
        
        # Ejecutar usando ScriptManager
        success = self.script_manager.execute_script(script_id, self.profile_os)
        
        if success:
            # Emitir señal y cerrar modal
            self.script_executed.emit(script_id)
            self.accept()
        else:
            logger.error(f"❌ Error ejecutando script: {script_name}")
    
    def _apply_styles(self):
        """Aplica estilos al modal."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {get_color('background')};
                border-radius: 8px;
            }}
            
            QFrame#header {{
                background-color: {get_color('surface')};
                border-bottom: 1px solid {get_color('border')};
            }}
            
            QFrame#footer {{
                background-color: {get_color('surface')};
                border-top: 1px solid {get_color('border')};
            }}
            
            QListWidget {{
                background-color: {get_color('background')};
                border: none;
                outline: none;
                padding: 10px;
            }}
            
            QListWidget::item {{
                background-color: {get_color('surface')};
                border-radius: 6px;
                margin: 2px 0px;
            }}
            
            QListWidget::item:hover {{
                background-color: {get_color('hover')};
            }}
            
            QListWidget::item:selected {{
                background-color: {get_color('accent')};
            }}
            
            QPushButton {{
                background-color: {get_color('surface')};
                color: {get_color('text_primary')};
                border: 1px solid {get_color('border')};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            
            QPushButton:hover {{
                background-color: {get_color('hover')};
                border-color: {get_color('accent')};
            }}
            
            QPushButton:pressed {{
                background-color: {get_color('accent')};
            }}
        """)
    
    def keyPressEvent(self, event):
        """Maneja eventos de teclado."""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.selected_script:
                self._execute_script(self.selected_script)
        else:
            super().keyPressEvent(event)
