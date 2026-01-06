"""
🎨 STYLES - Estilos y temas para NYX
=====================================
Define colores, estilos y temas para toda la interfaz de NYX.
Sistema completo de temas con soporte para dark/light mode.
"""

from PyQt6.QtGui import QColor, QPalette, QFont, QFontDatabase,QPixmap
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QGroupBox, QFrame

from typing import Dict, Any, List, Optional
import json
import os
import sys
from pathlib import Path
from utils.logger import logger

# Helper to locate assets/config recursively or absolutely
def get_project_root() -> Path:
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # In onedir, sys._MEIPASS is the _internal folder
        return Path(sys._MEIPASS)
    else:
        # src/ui/styles.py -> src/ui -> src -> root
        return Path(__file__).resolve().parent.parent.parent

def get_assets_path() -> Path:
    root = get_project_root()
    # In frozen: _internal/src/assets
    # In dev: root/src/assets
    return root / "src" / "assets"

ASSETS_ROOT = get_assets_path().as_posix()

class Theme:
    """Base para temas de la aplicación NYX."""
    
    def __init__(self, name: str, display_name: str):
        self.name = name
        self.display_name = display_name
        self.colors = {}
        self.fonts = {}
        self.styles = {}
        self.icons = {}
    
    def apply_to_app(self, app: QApplication):
        """Aplica el tema a la aplicación Qt."""
        # Configurar paleta de colores
        palette = QPalette()
        
        # Colores básicos
        palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.colors['surface']))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(self.colors['surface_dark']))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(self.colors['card']))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Text, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.colors['surface']))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        
        # Colores de interacción
        palette.setColor(QPalette.ColorRole.Light, QColor(self.colors['surface_light']))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(self.colors['border']))
        palette.setColor(QPalette.ColorRole.Dark, QColor(self.colors['surface_dark']))
        palette.setColor(QPalette.ColorRole.Mid, QColor(self.colors['border_dark']))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(self.colors['shadow']))
        
        # Colores de selección
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self.colors['primary']))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(self.colors['text_inverse']))
        
        # Enlaces
        palette.setColor(QPalette.ColorRole.Link, QColor(self.colors['secondary']))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(self.colors['secondary_dark']))
        
        app.setPalette(palette)
        
        # Aplicar estilos CSS
        full_stylesheet = self._generate_full_stylesheet()
        app.setStyleSheet(full_stylesheet)
        
        # Configurar fuentes
        self._setup_fonts(app)
    
    def _generate_full_stylesheet(self) -> str:
        """Genera la hoja de estilos completa."""
        stylesheet = ""
        
        # Agregar estilos base
        for selector, style in self.styles.items():
            stylesheet += f"{selector} {{{style}}}\n"
        
        # Agregar estilos para estados específicos
        stylesheet += self._generate_state_styles()
        
        return stylesheet
    
    def _generate_state_styles(self) -> str:
        """Genera estilos para estados específicos (hover, pressed, etc.)."""
        return f"""
            /* Estados de botones */
            QPushButton:hover {{
                background-color: {self.colors['primary_light']};
                border-color: {self.colors['primary']};
            }}
            
            QPushButton:pressed {{
                background-color: {self.colors['primary_dark']};
            }}
            
            QPushButton:disabled {{
                background-color: {self.colors['surface_disabled']};
                color: {self.colors['text_disabled']};
                border-color: {self.colors['border_disabled']};
            }}
            
            /* Estados de checkboxes */
            QCheckBox:hover::indicator {{
                border-color: {self.colors['primary']};
            }}
            
            QCheckBox:disabled::indicator {{
                border-color: {self.colors['border_disabled']};
            }}
            
            /* Estados de sliders */
            QSlider::handle:hover {{
                background-color: {self.colors['primary_light']};
            }}
            
            QSlider::handle:pressed {{
                background-color: {self.colors['primary_dark']};
            }}
            
            /* Estados de tabs */
            QTabBar::tab:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            
            /* Estados de list items */
            QListWidget::item:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            
            QListWidget::item:selected {{
                background-color: {self.colors['primary']};
                color: {self.colors['text_inverse']};
            }}
            
            /* Estados de table items */
            QTableWidget::item:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            
            QTableWidget::item:selected {{
                background-color: {self.colors['primary']};
                color: {self.colors['text_inverse']};
            }}
            
            /* Scrollbars */
            QScrollBar:vertical:hover {{
                background-color: {self.colors['surface_hover']};
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {self.colors['primary_light']};
            }}
            
            QScrollBar::handle:vertical:pressed {{
                background-color: {self.colors['primary_dark']};
            }}
        """
    
    def _setup_fonts(self, app: QApplication):
        """Configura las fuentes de la aplicación."""
        # Establecer fuente por defecto
        default_font = self.fonts.get('body', QFont('Segoe UI', 10))
        app.setFont(default_font)
        
        # Cargar fuentes personalizadas si existen
        self._load_custom_fonts()
    
    def _load_custom_fonts(self):
        """Carga fuentes personalizadas desde archivos."""
        font_dir = get_assets_path() / 'fonts'
        
        if font_dir.exists():
            for font_file in os.listdir(font_dir):
                if font_file.endswith(('.ttf', '.otf')):
                    font_path = font_dir / font_file
                    font_id = QFontDatabase.addApplicationFont(str(font_path))
                    
                    if font_id != -1:
                        font_families = QFontDatabase.applicationFontFamilies(font_id)
                        if font_families:
                            logger.debug(f"Fuente cargada: {font_families[0]}")
    
    def get_color(self, color_name: str) -> str:
        """Obtiene un color por nombre."""
        return self.colors.get(color_name, '#000000')
    
    def get_font(self, font_name: str) -> QFont:
        """Obtiene una fuente por nombre."""
        return self.fonts.get(font_name, QFont('Segoe UI', 10))
    
    def save_to_file(self, file_path: str):
        """Guarda el tema en un archivo JSON."""
        theme_data = {
            'name': self.name,
            'display_name': self.display_name,
            'colors': self.colors,
            'fonts': {
                name: {
                    'family': font.family(),
                    'size': font.pointSize(),
                    'weight': font.weight(),
                    'italic': font.italic(),
                    'bold': font.bold()
                }
                for name, font in self.fonts.items()
            },
            'styles': self.styles
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(theme_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'Theme':
        """Carga un tema desde un archivo JSON."""
        with open(file_path, 'r', encoding='utf-8') as f:
            theme_data = json.load(f)
        
        theme = cls(theme_data['name'], theme_data['display_name'])
        theme.colors = theme_data['colors']
        
        # Cargar fuentes
        theme.fonts = {}
        for name, font_data in theme_data.get('fonts', {}).items():
            font = QFont(font_data['family'], font_data['size'])
            font.setWeight(font_data['weight'])
            font.setItalic(font_data['italic'])
            font.setBold(font_data['bold'])
            theme.fonts[name] = font
        
        theme.styles = theme_data.get('styles', {})
        
        return theme


class DarkTheme(Theme):
    """Tema oscuro para NYX - Moderno y profesional."""
    
    def __init__(self):
        super().__init__("dark", "Oscuro")
        
        # Sistema de colores completo
        self.colors = {
            # Colores primarios
            'primary': '#4CAF50',           # Verde NYX
            'primary_light': '#66BB6A',     # Verde claro
            'primary_dark': '#388E3C',      # Verde oscuro
            'secondary': '#2196F3',         # Azul
            'secondary_light': '#64B5F6',   # Azul claro
            'secondary_dark': '#1976D2',    # Azul oscuro
            'accent': '#FF9800',            # Naranja/accento
            
            # Colores de fondo
            'background': '#121212',        # Fondo principal
            'background_light': '#1A1A1A',  # Fondo claro
            'background_dark': '#0A0A0A',   # Fondo oscuro
            
            # Superficies
            'surface': '#1E1E1E',           # Superficie principal
            'surface_light': '#252525',     # Superficie clara
            'surface_dark': '#171717',      # Superficie oscura
            'surface_hover': '#2A2A2A',     # Superficie hover
            'surface_active': '#303030',    # Superficie activa
            'surface_disabled': '#2D2D2D',  # Superficie deshabilitada
            
            # Tarjetas/Contenedores
            'card': '#252525',              # Tarjetas
            'card_light': '#2D2D2D',        # Tarjetas claras
            'card_dark': '#1D1D1D',         # Tarjetas oscuras
            
            # Texto
            'text_primary': '#FFFFFF',      # Texto principal
            'text_secondary': '#B0B0B0',    # Texto secundario
            'text_disabled': '#666666',     # Texto deshabilitado
            'text_inverse': '#000000',      # Texto invertido (sobre fondo claro)
            'text_success': '#4CAF50',      # Texto éxito
            'text_error': '#F44336',        # Texto error
            'text_warning': '#FF9800',      # Texto advertencia
            'text_info': '#2196F3',         # Texto información
            
            # Bordes
            'border': '#333333',            # Borde normal
            'border_light': '#404040',      # Borde claro
            'border_dark': '#262626',       # Borde oscuro
            'border_disabled': '#4D4D4D',   # Borde deshabilitado
            
            # Estados y feedback
            'success': '#4CAF50',           # Éxito
            'success_light': '#66BB6A',     # Éxito claro
            'success_dark': '#388E3C',      # Éxito oscuro
            
            'error': '#F44336',             # Error
            'error_light': '#EF5350',       # Error claro
            'error_dark': '#D32F2F',        # Error oscuro
            
            'warning': '#FF9800',           # Advertencia
            'warning_light': '#FFB74D',     # Advertencia clara
            'warning_dark': '#F57C00',      # Advertencia oscura
            
            'info': '#2196F3',              # Información
            'info_light': '#64B5F6',        # Información clara
            'info_dark': '#1976D2',         # Información oscura
            
            # Específicos de NYX
            'hand_detected': '#00BCD4',     # Cyan para detección de manos
            'arm_detected': '#9C27B0',      # Púrpura para brazos
            'voice_active': '#FF5722',      # Naranja para voz
            'gesture_active': '#4CAF50',    # Verde para gesto activo
            'camera_active': '#2196F3',     # Azul para cámara activa
            'pipeline_active': '#4CAF50',   # Verde para pipeline activo
            
            # Sombras
            'shadow': '#000000',            # Sombra
            'shadow_light': '#1A1A1A',      # Sombra clara
            'shadow_dark': '#0A0A0A',       # Sombra oscura
            
            # Gradientes
            'gradient_start': '#1E1E1E',    # Inicio gradiente
            'gradient_end': '#121212',      # Fin gradiente
        }
        
        # Sistema de fuentes
        self.fonts = {
            'title': QFont('Segoe UI', 24, QFont.Weight.Bold),
            'heading': QFont('Segoe UI', 18, QFont.Weight.Bold),
            'subheading': QFont('Segoe UI', 14, QFont.Weight.Bold),
            'body': QFont('Segoe UI', 10),
            'body_bold': QFont('Segoe UI', 10, QFont.Weight.Bold),
            'caption': QFont('Segoe UI', 9),
            'caption_bold': QFont('Segoe UI', 9, QFont.Weight.Bold),
            'monospace': QFont('Courier New', 10),
            'monospace_bold': QFont('Courier New', 10, QFont.Weight.Bold),
            'small': QFont('Segoe UI', 8),
            'large': QFont('Segoe UI', 12),
        }
        
        # Estilos CSS
        self.styles = self._generate_styles()
    
    def _generate_styles(self) -> Dict[str, str]:
        """Genera estilos CSS para todos los widgets."""
        return {
            # ===== ESTILOS GLOBALES =====
            'QWidget': f"""
                background-color: {self.colors['background']};
                color: {self.colors['text_primary']};
                font-family: 'Segoe UI';
                font-size: 10pt;
                selection-background-color: {self.colors['primary']};
                selection-color: {self.colors['text_inverse']};
            """,
            
            'QMainWindow': f"""
                background-color: {self.colors['background']};
                border: none;
            """,
            
            # ===== BOTONES =====
            'QPushButton': f"""
                QPushButton {{
                    background-color: {self.colors['surface']};
                    color: {self.colors['text_primary']};
                    border: 1px solid {self.colors['border']};
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: 500;
                    min-height: 32px;
                }}
                QPushButton:focus {{
                    border: 2px solid {self.colors['primary']};
                    padding: 7px 15px;
                }}
            """,
            
            'QPushButton.primary': f"""
                QPushButton {{
                    background-color: {self.colors['primary']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['primary_dark']};
                    font-weight: bold;
                }}
            """,
            
            'QPushButton.secondary': f"""
                QPushButton {{
                    background-color: {self.colors['secondary']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['secondary_dark']};
                }}
            """,
            
            'QPushButton.success': f"""
                QPushButton {{
                    background-color: {self.colors['success']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['success_dark']};
                }}
            """,
            
            'QPushButton.error': f"""
                QPushButton {{
                    background-color: {self.colors['error']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['error_dark']};
                }}
            """,
            
            'QPushButton.warning': f"""
                QPushButton {{
                    background-color: {self.colors['warning']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['warning_dark']};
                }}
            """,
            
            'QPushButton.info': f"""
                QPushButton {{
                    background-color: {self.colors['info']};
                    color: {self.colors['text_inverse']};
                    border: 1px solid {self.colors['info_dark']};
                }}
            """,
            
            # ===== ETIQUETAS =====
            'QLabel': f"""
                color: {self.colors['text_primary']};
                background-color: transparent;
            """,
            
            'QLabel.title': f"""
                font-size: 24pt;
                font-weight: bold;
                color: {self.colors['primary']};
                padding: 10px 0;
            """,
            
            'QLabel.heading': f"""
                font-size: 18pt;
                font-weight: bold;
                color: {self.colors['text_primary']};
                padding: 8px 0;
            """,
            
            'QLabel.subheading': f"""
                font-size: 14pt;
                font-weight: bold;
                color: {self.colors['text_secondary']};
                padding: 6px 0;
            """,
            
            'QLabel.caption': f"""
                font-size: 9pt;
                color: {self.colors['text_secondary']};
            """,
            
            'QLabel.success': f"""
                color: {self.colors['success']};
                font-weight: bold;
            """,
            
            'QLabel.error': f"""
                color: {self.colors['error']};
                font-weight: bold;
            """,
            
            'QLabel.warning': f"""
                color: {self.colors['warning']};
                font-weight: bold;
            """,
            
            'QLabel.info': f"""
                color: {self.colors['info']};
                font-weight: bold;
            """,
            
            # ===== CAMPOS DE TEXTO =====
            'QLineEdit': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.colors['text_primary']};
                selection-background-color: {self.colors['primary']};
                selection-color: {self.colors['text_inverse']};
            """,
            
            'QLineEdit:focus': f"""
                border: 2px solid {self.colors['primary']};
                padding: 7px;
            """,
            
            'QLineEdit:disabled': f"""
                background-color: {self.colors['surface_disabled']};
                color: {self.colors['text_disabled']};
                border-color: {self.colors['border_disabled']};
            """,
            
            'QTextEdit': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.colors['text_primary']};
                selection-background-color: {self.colors['primary']};
                selection-color: {self.colors['text_inverse']};
            """,
            
            'QTextEdit:focus': f"""
                border: 2px solid {self.colors['primary']};
                padding: 7px;
            """,
            
            # ===== CHECKBOXES Y RADIO BUTTONS =====
            'QCheckBox': f"""
                color: {self.colors['text_primary']};
                spacing: 8px;
            """,
            
            'QCheckBox::indicator': f"""
                width: 18px;
                height: 18px;
                border: 2px solid {self.colors['border']};
                border-radius: 3px;
                background-color: {self.colors['surface']};
            """,
            
            'QCheckBox::indicator:checked': f"""
                background-color: {self.colors['primary']};
                border: 2px solid {self.colors['primary']};
                image: url({ASSETS_ROOT}/icons/check.svg);
            """,
            
            'QCheckBox::indicator:disabled': f"""
                border-color: {self.colors['border_disabled']};
                background-color: {self.colors['surface_disabled']};
            """,
            
            'QRadioButton': f"""
                color: {self.colors['text_primary']};
                spacing: 8px;
            """,
            
            'QRadioButton::indicator': f"""
                width: 18px;
                height: 18px;
                border: 2px solid {self.colors['border']};
                border-radius: 9px;
                background-color: {self.colors['surface']};
            """,
            
            'QRadioButton::indicator:checked': f"""
                background-color: {self.colors['primary']};
                border: 2px solid {self.colors['primary']};
            """,
            
            # ===== COMBO BOXES =====
            'QComboBox': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                padding-right: 30px;
                color: {self.colors['text_primary']};
                min-height: 32px;
            """,
            
            'QComboBox::drop-down': f"""
                border: none;
                width: 30px;
            """,
            
            'QComboBox::down-arrow': f"""
                image: url({ASSETS_ROOT}/icons/arrow-down.svg);
                width: 16px;
                height: 16px;
            """,
            
            'QComboBox QAbstractItemView': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 4px;
                color: {self.colors['text_primary']};
                selection-background-color: {self.colors['primary']};
                selection-color: {self.colors['text_inverse']};
            """,
            
            # ===== SLIDERS =====
            'QSlider::groove:horizontal': f"""
                height: 6px;
                background: {self.colors['surface_dark']};
                border-radius: 3px;
                margin: 0px;
            """,
            
            'QSlider::sub-page:horizontal': f"""
                background: {self.colors['primary']};
                border-radius: 3px;
            """,
            
            'QSlider::handle:horizontal': f"""
                background: {self.colors['primary']};
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
                border: 2px solid {self.colors['primary_dark']};
            """,
            
            # ===== SPIN BOXES =====
            'QSpinBox, QDoubleSpinBox': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.colors['text_primary']};
                min-height: 32px;
            """,
            
            'QSpinBox::up-button, QDoubleSpinBox::up-button': f"""
                background-color: {self.colors['surface_light']};
                border: 1px solid {self.colors['border']};
                border-radius: 2px;
                width: 20px;
                height: 15px;
            """,
            
            'QSpinBox::down-button, QDoubleSpinBox::down-button': f"""
                background-color: {self.colors['surface_light']};
                border: 1px solid {self.colors['border']};
                border-radius: 2px;
                width: 20px;
                height: 15px;
            """,
            
            # ===== GROUP BOXES =====
            'QGroupBox': f"""
                font-weight: bold;
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                color: {self.colors['text_primary']};
                background-color: {self.colors['surface']};
            """,
            
            'QGroupBox::title': f"""
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
                background-color: {self.colors['surface']};
            """,
            
            # ===== TAB WIDGETS =====
            'QTabWidget::pane': f"""
                border: 1px solid {self.colors['border']};
                background-color: {self.colors['surface']};
                border-radius: 4px;
                margin: 2px;
            """,
            
            'QTabBar::tab': f"""
                background-color: {self.colors['surface']};
                color: {self.colors['text_secondary']};
                border: 1px solid {self.colors['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
                min-width: 100px;
            """,
            
            'QTabBar::tab:selected': f"""
                background-color: {self.colors['primary']};
                color: {self.colors['text_inverse']};
                font-weight: bold;
                border-color: {self.colors['primary_dark']};
            """,
            
            # ===== TABLES =====
            'QTableWidget': f"""
                background-color: {self.colors['surface']};
                alternate-background-color: {self.colors['surface_dark']};
                gridline-color: {self.colors['border']};
                color: {self.colors['text_primary']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 2px;
            """,
            
            'QHeaderView::section': f"""
                background-color: {self.colors['surface_light']};
                color: {self.colors['text_primary']};
                padding: 8px;
                border: none;
                border-right: 1px solid {self.colors['border']};
                border-bottom: 1px solid {self.colors['border']};
                font-weight: bold;
                min-height: 30px;
            """,
            
            'QHeaderView::section:last': """
                border-right: none;
            """,
            
            # ===== LIST WIDGETS =====
            'QListWidget': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 4px;
                color: {self.colors['text_primary']};
                outline: none;
            """,
            
            'QListWidget::item': f"""
                padding: 8px;
                border-radius: 3px;
                margin: 2px;
            """,
            
            'QListWidget::item:alternate': f"""
                background-color: {self.colors['surface_dark']};
            """,
            
            # ===== SCROLLBARS =====
            'QScrollBar:vertical': f"""
                background-color: {self.colors['surface']};
                width: 12px;
                border: none;
                margin: 0px;
            """,
            
            'QScrollBar::handle:vertical': f"""
                background-color: {self.colors['border']};
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            """,
            
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical': """
                border: none;
                background: none;
                height: 0px;
            """,
            
            'QScrollBar:horizontal': f"""
                background-color: {self.colors['surface']};
                height: 12px;
                border: none;
                margin: 0px;
            """,
            
            'QScrollBar::handle:horizontal': f"""
                background-color: {self.colors['border']};
                min-width: 20px;
                border-radius: 6px;
                margin: 2px;
            """,
            
            # ===== PROGRESS BARS =====
            'QProgressBar': f"""
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                text-align: center;
                background: {self.colors['surface_dark']};
                color: {self.colors['text_primary']};
                height: 20px;
            """,
            
            'QProgressBar::chunk': f"""
                background-color: {self.colors['primary']};
                border-radius: 3px;
            """,
            
            # ===== TOOLBARS =====
            'QToolBar': f"""
                background-color: {self.colors['surface']};
                border: none;
                border-bottom: 1px solid {self.colors['border']};
                padding: 4px;
                spacing: 4px;
            """,
            
            'QToolButton': f"""
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 6px;
                min-width: 32px;
                min-height: 32px;
            """,
            
            # ===== MENUS =====
            'QMenu': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 4px;
                color: {self.colors['text_primary']};
            """,
            
            'QMenu::item': f"""
                padding: 6px 24px 6px 12px;
                border-radius: 3px;
                margin: 2px;
            """,
            
            'QMenu::item:selected': f"""
                background-color: {self.colors['primary']};
                color: {self.colors['text_inverse']};
            """,
            
            'QMenu::separator': f"""
                height: 1px;
                background-color: {self.colors['border']};
                margin: 4px 8px;
            """,
            
            # ===== STATUS BAR =====
            'QStatusBar': f"""
                background-color: {self.colors['surface']};
                border-top: 1px solid {self.colors['border']};
                color: {self.colors['text_secondary']};
                padding: 4px;
            """,
            
            # ===== FRAMES =====
            'QFrame': f"""
                background-color: transparent;
                border: none;
            """,
            
            'QFrame#CameraView': f"""
                background-color: black;
                border: 2px solid {self.colors['border']};
                border-radius: 4px;
            """,
            
            'QFrame#line': f"""
                background-color: {self.colors['border']};
            """,
            
            # ===== DIALOGS =====
            'QDialog': f"""
                background-color: {self.colors['background']};
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
            """,
            
            # ===== SPLITTERS =====
            'QSplitter::handle': f"""
                background-color: {self.colors['border']};
                width: 1px;
                height: 1px;
            """,
            
            'QSplitter::handle:hover': f"""
                background-color: {self.colors['primary']};
            """,
            
            # ===== ESTILOS ESPECIALES NYX =====
            'GestureStatus': f"""
                background-color: {self.colors['card']};
                border: 2px solid {self.colors['border']};
                border-radius: 8px;
                padding: 12px;
            """,
            
            'ProfileCard': f"""
                background-color: {self.colors['card']};
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
                padding: 12px;
                margin: 4px;
            """,
            
            'ProfileCard.active': f"""
                border: 2px solid {self.colors['primary']};
                background-color: {self.colors['success_light']};
            """,
            
            'LogConsole': f"""
                background-color: {self.colors['surface_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
            """,
            
            'ControlPanel': f"""
                background-color: {self.colors['card']};
                border: 2px solid {self.colors['border']};
                border-radius: 8px;
                padding: 15px;
            """,
        }


class LightTheme(Theme):
    """Tema claro para NYX - Moderno y limpio."""
    
    def __init__(self):
        super().__init__("light", "Claro")
        
        # Sistema de colores claro
        self.colors = {
            # Colores primarios (mismos que dark pero más claros)
            'primary': '#4CAF50',           # Verde NYX
            'primary_light': '#66BB6A',     # Verde claro
            'primary_dark': '#388E3C',      # Verde oscuro
            'secondary': '#2196F3',         # Azul
            'secondary_light': '#64B5F6',   # Azul claro
            'secondary_dark': '#1976D2',    # Azul oscuro
            'accent': '#FF9800',            # Naranja/accento
            
            # Colores de fondo (claros)
            'background': '#F5F5F5',        # Fondo principal
            'background_light': '#FFFFFF',  # Fondo claro
            'background_dark': '#E0E0E0',   # Fondo oscuro
            
            # Superficies (claros)
            'surface': '#FFFFFF',           # Superficie principal
            'surface_light': '#FAFAFA',     # Superficie clara
            'surface_dark': '#F0F0F0',      # Superficie oscura
            'surface_hover': '#EEEEEE',     # Superficie hover
            'surface_active': '#E0E0E0',    # Superficie activa
            'surface_disabled': '#F5F5F5',  # Superficie deshabilitada
            
            # Tarjetas/Contenedores
            'card': '#FFFFFF',              # Tarjetas
            'card_light': '#FAFAFA',        # Tarjetas claras
            'card_dark': '#F5F5F5',         # Tarjetas oscuras
            
            # Texto (oscuros sobre fondo claro)
            'text_primary': '#212121',      # Texto principal
            'text_secondary': '#757575',    # Texto secundario
            'text_disabled': '#BDBDBD',     # Texto deshabilitado
            'text_inverse': '#FFFFFF',      # Texto invertido (sobre fondo oscuro)
            'text_success': '#4CAF50',      # Texto éxito
            'text_error': '#F44336',        # Texto error
            'text_warning': '#FF9800',      # Texto advertencia
            'text_info': '#2196F3',         # Texto información
            
            # Bordes
            'border': '#E0E0E0',            # Borde normal
            'border_light': '#EEEEEE',      # Borde claro
            'border_dark': '#BDBDBD',       # Borde oscuro
            'border_disabled': '#E0E0E0',   # Borde deshabilitado
            
            # Estados y feedback
            'success': '#4CAF50',           # Éxito
            'success_light': '#66BB6A',     # Éxito claro
            'success_dark': '#388E3C',      # Éxito oscuro
            
            'error': '#F44336',             # Error
            'error_light': '#EF5350',       # Error claro
            'error_dark': '#D32F2F',        # Error oscuro
            
            'warning': '#FF9800',           # Advertencia
            'warning_light': '#FFB74D',     # Advertencia clara
            'warning_dark': '#F57C00',      # Advertencia oscura
            
            'info': '#2196F3',              # Información
            'info_light': '#64B5F6',        # Información clara
            'info_dark': '#1976D2',         # Información oscura
            
            # Específicos de NYX
            'hand_detected': '#00BCD4',     # Cyan para detección de manos
            'arm_detected': '#9C27B0',      # Púrpura para brazos
            'voice_active': '#FF5722',      # Naranja para voz
            'gesture_active': '#4CAF50',    # Verde para gesto activo
            'camera_active': '#2196F3',     # Azul para cámara activa
            'pipeline_active': '#4CAF50',   # Verde para pipeline activo
            
            # Sombras
            'shadow': '#00000020',          # Sombra (con transparencia)
            'shadow_light': '#00000010',    # Sombra clara
            'shadow_dark': '#00000030',     # Sombra oscura
            
            # Gradientes
            'gradient_start': '#FFFFFF',    # Inicio gradiente
            'gradient_end': '#F5F5F5',      # Fin gradiente
        }
        
        # Mismas fuentes que dark theme
        self.fonts = DarkTheme().fonts
        
        # Generar estilos (usará los mismos selectores pero con colores claros)
        self.styles = self._generate_styles()
    
    def _generate_styles(self) -> Dict[str, str]:
        """Genera estilos CSS para tema claro."""
        # Copiar estilos del tema oscuro
        dark_theme = DarkTheme()
        styles = dark_theme.styles.copy()
        
        # Reemplazar colores oscuros por claros
        import re
        
        for selector, style in styles.items():
            # Reemplazar cada color del tema oscuro por el correspondiente claro
            for dark_color, light_color in zip(dark_theme.colors.values(), self.colors.values()):
                # Usar regex para reemplazar solo valores de color, no nombres
                pattern = r'(?<![\w-])' + re.escape(dark_color) + r'(?![\w-])'
                style = re.sub(pattern, light_color, style)
            
            styles[selector] = style
        
        return styles


class BlueDarkTheme(DarkTheme):
    """Variante azul del tema oscuro."""
    
    def __init__(self):
        super().__init__()
        self.name = "blue_dark"
        self.display_name = "Azul Oscuro"
        
        # Modificar colores primarios a azules
        self.colors.update({
            'primary': '#2196F3',
            'primary_light': '#64B5F6',
            'primary_dark': '#1976D2',
            'secondary': '#4CAF50',
            'secondary_light': '#66BB6A',
            'secondary_dark': '#388E3C',
        })


class PurpleDarkTheme(DarkTheme):
    """Variante púrpura del tema oscuro."""
    
    def __init__(self):
        super().__init__()
        self.name = "purple_dark"
        self.display_name = "Púrpura Oscuro"
        
        # Modificar colores primarios a púrpuras
        self.colors.update({
            'primary': '#9C27B0',
            'primary_light': '#BA68C8',
            'primary_dark': '#7B1FA2',
            'secondary': '#4CAF50',
            'secondary_light': '#66BB6A',
            'secondary_dark': '#388E3C',
        })


class StyleManager:
    """
    🎨 Gestor de Estilos para NYX
    ==============================
    Gestiona todos los temas y estilos de la aplicación.
    Patrón Singleton para acceso global.
    """
    
    _instance = None
    _themes = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_themes()
        return cls._instance
    
    def _init_themes(self):
        """Inicializa todos los temas disponibles."""
        self._themes = {
            'dark': DarkTheme(),
            'light': LightTheme(),
            'blue_dark': BlueDarkTheme(),
            'purple_dark': PurpleDarkTheme(),
        }
        
        # Tema por defecto
        self.current_theme = 'dark'
        
        # Cargar tema guardado en configuración
        self._load_saved_theme()
    
    def _load_saved_theme(self):
        """Carga el tema guardado en la configuración."""
        try:
            from utils.config_loader import config
            saved_theme = config.get_setting('ui.theme', 'dark')
            
            if saved_theme in self._themes:
                self.current_theme = saved_theme
                logger.info(f"🎨 Tema cargado desde configuración: {saved_theme}")
        except:
            pass  # Si hay error, usa el tema por defecto
    
    def get_theme(self, name: str = None) -> Theme:
        """
        Obtiene un tema por nombre.
        
        Args:
            name: Nombre del tema. Si es None, usa el tema actual.
            
        Returns:
            Objeto Theme
        """
        if name is None:
            name = self.current_theme
        
        return self._themes.get(name, self._themes['dark'])
    
    def set_theme(self, name: str, app: QApplication = None) -> bool:
        """
        Cambia el tema actual.
        
        Args:
            name: Nombre del tema
            app: Aplicación Qt para aplicar el tema
            
        Returns:
            True si se cambió correctamente
        """
        if name not in self._themes:
            logger.warning(f"🎨 Tema '{name}' no encontrado")
            return False
        
        self.current_theme = name
        
        # Guardar en configuración
        try:
            from utils.config_loader import config
            config.update_setting('ui.theme', name)
            config.save_settings()
        except:
            pass
        
        # Aplicar a la aplicación si se proporciona
        if app:
            self._themes[name].apply_to_app(app)
        
        logger.info(f"🎨 Tema cambiado a: {name}")
        return True
    
    def apply_to_app(self, app: QApplication):
        """Aplica el tema actual a la aplicación."""
        self.get_theme().apply_to_app(app)
    
    def list_themes(self) -> List[Dict[str, str]]:
        """Lista todos los temas disponibles con información."""
        themes = []
        
        for name, theme in self._themes.items():
            themes.append({
                'name': name,
                'display_name': theme.display_name,
                'is_dark': 'dark' in name,
                'primary_color': theme.colors['primary']
            })
        
        return themes
    
    def get_color(self, color_name: str, theme_name: str = None) -> str:
        """
        Obtiene un color del tema.
        
        Args:
            color_name: Nombre del color
            theme_name: Nombre del tema (None para tema actual)
            
        Returns:
            Código hexadecimal del color
        """
        theme = self.get_theme(theme_name)
        return theme.get_color(color_name)
    
    def get_font(self, font_name: str, theme_name: str = None) -> QFont:
        """
        Obtiene una fuente del tema.
        
        Args:
            font_name: Nombre de la fuente
            theme_name: Nombre del tema (None para tema actual)
            
        Returns:
            Objeto QFont
        """
        theme = self.get_theme(theme_name)
        return theme.get_font(font_name)
    
    def create_gradient(self, color1: str, color2: str, direction: str = 'horizontal') -> str:
        """
        Crea un gradiente CSS.
        
        Args:
            color1: Color inicial
            color2: Color final
            direction: 'horizontal' o 'vertical'
            
        Returns:
            Cadena CSS del gradiente
        """
        if direction == 'horizontal':
            return f"qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 {color1}, stop: 1 {color2})"
        else:
            return f"qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {color1}, stop: 1 {color2})"
    
    def create_shadow(self, blur_radius: int = 10, offset: tuple = (0, 2), 
                     color: str = None, spread: int = 0) -> str:
        """
        Crea sombra CSS para widgets.
        
        Args:
            blur_radius: Radio de desenfoque
            offset: Desplazamiento (x, y)
            color: Color de la sombra
            spread: Extensión de la sombra
            
        Returns:
            Cadena CSS de sombra
        """
        if color is None:
            color = self.get_color('shadow')
        
        x_offset, y_offset = offset
        return f"drop-shadow({x_offset}px {y_offset}px {blur_radius}px {color})"
    
    def get_theme_preview(self, theme_name: str, size: QSize = QSize(100, 60)) -> QPixmap:
        """
        Genera una vista previa del tema.
        
        Args:
            theme_name: Nombre del tema
            size: Tamaño de la vista previa
            
        Returns:
            QPixmap con la vista previa
        """
        theme = self.get_theme(theme_name)
        
        # Crear imagen de preview
        pixmap = QPixmap(size)
        pixmap.fill(QColor(theme.colors['background']))
        
        # TODO: Agregar elementos de preview más detallados
        return pixmap
    
    def save_custom_theme(self, theme_data: Dict[str, Any], name: str):
        """
        Guarda un tema personalizado.
        
        Args:
            theme_data: Datos del tema
            name: Nombre del tema
        """
        # TODO: Implementar guardado de temas personalizados
        pass
    
    def load_custom_themes(self):
        """Carga temas personalizados desde archivos."""
        themes_dir = os.path.join(os.path.dirname(__file__), '..', 'themes')
        
        if os.path.exists(themes_dir):
            for file_name in os.listdir(themes_dir):
                if file_name.endswith('.json'):
                    try:
                        theme_path = os.path.join(themes_dir, file_name)
                        theme = Theme.load_from_file(theme_path)
                        self._themes[theme.name] = theme
                        logger.info(f"🎨 Tema personalizado cargado: {theme.name}")
                    except Exception as e:
                        logger.error(f"❌ Error cargando tema {file_name}: {e}")


# Instancia global del gestor de estilos
styles = StyleManager()


# ===== FUNCIONES DE CONVENIENCIA =====

def apply_theme(app: QApplication, theme_name: str = 'dark') -> bool:
    """
    Aplica un tema a la aplicación.
    
    Args:
        app: Aplicación Qt
        theme_name: Nombre del tema
        
    Returns:
        True si se aplicó correctamente
    """
    return styles.set_theme(theme_name, app)

def get_color(color_name: str, theme_name: str = None) -> str:
    """
    Obtiene un color del tema actual.
    
    Args:
        color_name: Nombre del color
        theme_name: Nombre del tema específico (opcional)
        
    Returns:
        Código hexadecimal del color
    """
    return styles.get_color(color_name, theme_name)

def get_font(font_name: str, theme_name: str = None) -> QFont:
    """
    Obtiene una fuente del tema actual.
    
    Args:
        font_name: Nombre de la fuente
        theme_name: Nombre del tema específico (opcional)
        
    Returns:
        Objeto QFont
    """
    return styles.get_font(font_name, theme_name)

def create_gradient(color1: str, color2: str, direction: str = 'horizontal') -> str:
    """
    Crea un gradiente CSS.
    
    Args:
        color1: Color inicial
        color2: Color final
        direction: 'horizontal' o 'vertical'
        
    Returns:
        Cadena CSS del gradiente
    """
    return styles.create_gradient(color1, color2, direction)

def create_shadow(blur_radius: int = 10, offset: tuple = (0, 2), 
                 color: str = None, spread: int = 0) -> str:
    """
    Crea sombra CSS para widgets.
    
    Args:
        blur_radius: Radio de desenfoque
        offset: Desplazamiento (x, y)
        color: Color de la sombra
        spread: Extensión de la sombra
        
    Returns:
        Cadena CSS de sombra
    """
    return styles.create_shadow(blur_radius, offset, color, spread)

def list_themes() -> List[Dict[str, str]]:
    """
    Lista todos los temas disponibles.
    
    Returns:
        Lista de diccionarios con información de temas
    """
    return styles.list_themes()

def get_theme_preview(theme_name: str, size: QSize = QSize(100, 60)) -> QPixmap:
    """
    Genera una vista previa del tema.
    
    Args:
        theme_name: Nombre del tema
        size: Tamaño de la vista previa
        
    Returns:
        QPixmap con la vista previa
    """
    return styles.get_theme_preview(theme_name, size)


# ===== CLASES DE WIDGETS ESTILIZADOS =====

class StyledButton(QPushButton):
    """Botón con estilos NYX."""
    
    def __init__(self, text: str = "", parent=None, style_type: str = "default"):
        super().__init__(text, parent)
        self.style_type = style_type
        self._apply_style()
    
    def _apply_style(self):
        """Aplica el estilo al botón."""
        if self.style_type == "primary":
            self.setProperty("class", "primary")
        elif self.style_type == "success":
            self.setProperty("class", "success")
        elif self.style_type == "error":
            self.setProperty("class", "error")
        elif self.style_type == "warning":
            self.setProperty("class", "warning")
        elif self.style_type == "info":
            self.setProperty("class", "info")


class StyledLabel(QLabel):
    """Etiqueta con estilos NYX."""
    
    def __init__(self, text: str = "", parent=None, style_type: str = "default"):
        super().__init__(text, parent)
        self.style_type = style_type
        self._apply_style()
    
    def _apply_style(self):
        """Aplica el estilo a la etiqueta."""
        if self.style_type == "title":
            self.setProperty("class", "title")
        elif self.style_type == "heading":
            self.setProperty("class", "heading")
        elif self.style_type == "subheading":
            self.setProperty("class", "subheading")
        elif self.style_type == "caption":
            self.setProperty("class", "caption")
        elif self.style_type == "success":
            self.setProperty("class", "success")
        elif self.style_type == "error":
            self.setProperty("class", "error")
        elif self.style_type == "warning":
            self.setProperty("class", "warning")
        elif self.style_type == "info":
            self.setProperty("class", "info")


class StyledGroupBox(QGroupBox):
    """GroupBox con estilos NYX."""
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
        self._apply_style()
    
    def _apply_style(self):
        """Aplica el estilo al GroupBox."""
        self.setProperty("class", "styled")


class StyledFrame(QFrame):
    """Frame con estilos NYX."""
    
    def __init__(self, parent=None, frame_id: str = None):
        super().__init__(parent)
        if frame_id:
            self.setObjectName(frame_id)
        self._apply_style()
    
    def _apply_style(self):
        """Aplica el estilo al Frame."""
        pass  # El estilo se aplica por CSS según objectName


# ===== FUNCIÓN DE INICIALIZACIÓN =====

def init_styles(app: QApplication):
    """
    Inicializa el sistema de estilos.
    
    Args:
        app: Aplicación Qt
    """
    # Aplicar tema
    styles.apply_to_app(app)
    
    # Registrar widgets personalizados
    from PyQt6.QtWidgets import QApplication
    app.setStyle("Fusion")  # Usar estilo Fusion para mejor compatibilidad
    
    logger.info("🎨 Sistema de estilos inicializado")


if __name__ == "__main__":
    # Prueba de estilos
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    # Aplicar tema oscuro
    init_styles(app)
    
    # Crear ventana de prueba
    window = QMainWindow()
    window.setWindowTitle("🎨 Prueba de Estilos NYX")
    window.setGeometry(100, 100, 400, 300)
    
    # Widget central
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    
    # Botones de prueba
    btn_normal = QPushButton("Botón Normal")
    layout.addWidget(btn_normal)
    
    btn_primary = StyledButton("Botón Primario", style_type="primary")
    layout.addWidget(btn_primary)
    
    btn_success = StyledButton("Botón Éxito", style_type="success")
    layout.addWidget(btn_success)
    
    btn_error = StyledButton("Botón Error", style_type="error")
    layout.addWidget(btn_error)
    
    # Etiquetas de prueba
    label_title = StyledLabel("Título Principal", style_type="title")
    layout.addWidget(label_title)
    
    label_heading = StyledLabel("Encabezado", style_type="heading")
    layout.addWidget(label_heading)
    
    label_success = StyledLabel("Texto de éxito", style_type="success")
    layout.addWidget(label_success)
    
    window.setCentralWidget(central_widget)
    window.show()
    
    sys.exit(app.exec())