"""
🎨 STYLES - Estilos y temas para la interfaz
============================================
Define colores, estilos y temas para toda la UI.
"""

from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtCore import Qt
from typing import Dict, Any


class Theme:
    """Base para temas de la aplicación."""
    
    def __init__(self, name: str):
        self.name = name
        self.colors = {}
        self.fonts = {}
        self.styles = {}
    
    def apply_to_app(self, app):
        """Aplica el tema a la aplicación."""
        pass


class DarkTheme(Theme):
    """Tema oscuro para la aplicación."""
    
    def __init__(self):
        super().__init__("dark")
        
        # Colores principales
        self.colors = {
            'primary': '#2E7D32',       # Verde
            'secondary': '#1976D2',      # Azul
            'accent': '#FF9800',         # Naranja
            'background': '#121212',     # Fondo oscuro
            'surface': '#1E1E1E',        # Superficie
            'card': '#252525',           # Tarjetas
            'text_primary': '#FFFFFF',   # Texto principal
            'text_secondary': '#B0B0B0', # Texto secundario
            'text_disabled': '#666666',  # Texto deshabilitado
            'border': '#333333',         # Bordes
            'error': '#CF6679',          # Error
            'success': '#4CAF50',        # Éxito
            'warning': '#FFB74D',        # Advertencia
            'info': '#2196F3',           # Información
            
            # Específicos para gestos
            'hand_detected': '#00BCD4',  # Cyan para manos
            'arm_detected': '#9C27B0',   # Púrpura para brazos
            'voice_active': '#FF5722',   # Naranja para voz
            'gesture_active': '#4CAF50', # Verde para gesto activo
        }
        
        # Fuentes
        self.fonts = {
            'title': QFont('Segoe UI', 16, QFont.Weight.Bold),
            'heading': QFont('Segoe UI', 14, QFont.Weight.Bold),
            'subheading': QFont('Segoe UI', 12, QFont.Weight.Bold),
            'body': QFont('Segoe UI', 10),
            'monospace': QFont('Courier New', 10),
            'small': QFont('Segoe UI', 9),
        }
        
        # Estilos CSS para widgets
        self.styles = self._generate_styles()
    
    def _generate_styles(self) -> Dict[str, str]:
        """Genera estilos CSS para widgets."""
        primary_color = QColor(self.colors['primary'])
        surface_color = QColor(self.colors['surface'])
        
        return {
            'QMainWindow': f"""
                background-color: {self.colors['background']};
                color: {self.colors['text_primary']};
            """,
            
            'QWidget': f"""
                background-color: {self.colors['background']};
                color: {self.colors['text_primary']};
                font-family: 'Segoe UI';
                font-size: 10pt;
            """,
            
            'QPushButton': f"""
                QPushButton {{
                    background-color: {self.colors['primary']};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {primary_color.darker(120).name()};
                }}
                QPushButton:pressed {{
                    background-color: {primary_color.darker(150).name()};
                }}
                QPushButton:disabled {{
                    background-color: {self.colors['text_disabled']};
                    color: {self.colors['text_secondary']};
                }}
            """,
            
            'QPushButton.danger': f"""
                QPushButton {{
                    background-color: {self.colors['error']};
                }}
            """,
            
            'QPushButton.success': f"""
                QPushButton {{
                    background-color: {self.colors['success']};
                }}
            """,
            
            'QPushButton.warning': f"""
                QPushButton {{
                    background-color: {self.colors['warning']};
                }}
            """,
            
            'QLabel': f"""
                color: {self.colors['text_primary']};
            """,
            
            'QLabel.title': f"""
                font-size: 16pt;
                font-weight: bold;
                color: {self.colors['primary']};
            """,
            
            'QLabel.subtitle': f"""
                font-size: 12pt;
                font-weight: bold;
                color: {self.colors['secondary']};
            """,
            
            'QLineEdit': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 6px;
                color: {self.colors['text_primary']};
            """,
            
            'QTextEdit': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 6px;
                color: {self.colors['text_primary']};
            """,
            
            'QComboBox': f"""
                background-color: {self.colors['surface']};
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                padding: 6px;
                color: {self.colors['text_primary']};
            """,
            
            'QComboBox::drop-down': """
                border: none;
            """,
            
            'QComboBox::down-arrow': f"""
                image: none;
                border-left: 1px solid {self.colors['border']};
                padding: 0 8px;
            """,
            
            'QCheckBox': f"""
                color: {self.colors['text_primary']};
                spacing: 8px;
            """,
            
            'QCheckBox::indicator': f"""
                width: 18px;
                height: 18px;
                border: 2px solid {self.colors['border']};
                border-radius: 3px;
            """,
            
            'QCheckBox::indicator:checked': f"""
                background-color: {self.colors['primary']};
                border: 2px solid {self.colors['primary']};
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
            """,
            
            'QRadioButton::indicator:checked': f"""
                background-color: {self.colors['primary']};
                border: 2px solid {self.colors['primary']};
            """,
            
            'QGroupBox': f"""
                font-weight: bold;
                border: 2px solid {self.colors['border']};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                color: {self.colors['text_primary']};
            """,
            
            'QGroupBox::title': f"""
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            """,
            
            'QSlider::groove:horizontal': f"""
                height: 6px;
                background: {self.colors['surface']};
                border-radius: 3px;
            """,
            
            'QSlider::handle:horizontal': f"""
                background: {self.colors['primary']};
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            """,
            
            'QProgressBar': f"""
                border: 1px solid {self.colors['border']};
                border-radius: 4px;
                text-align: center;
                background: {self.colors['surface']};
            """,
            
            'QProgressBar::chunk': f"""
                background-color: {self.colors['primary']};
                border-radius: 4px;
            """,
            
            'QTabWidget::pane': f"""
                border: 1px solid {self.colors['border']};
                background-color: {self.colors['surface']};
            """,
            
            'QTabBar::tab': f"""
                background-color: {self.colors['surface']};
                color: {self.colors['text_secondary']};
                padding: 8px 16px;
                margin-right: 2px;
            """,
            
            'QTabBar::tab:selected': f"""
                background-color: {self.colors['primary']};
                color: white;
                font-weight: bold;
            """,
            
            'QTabBar::tab:hover': f"""
                background-color: {surface_color.lighter(120).name()};
            """,
            
            'QTableWidget': f"""
                background-color: {self.colors['surface']};
                alternate-background-color: {QColor(self.colors['surface']).darker(110).name()};
                gridline-color: {self.colors['border']};
                color: {self.colors['text_primary']};
                border: none;
            """,
            
            'QHeaderView::section': f"""
                background-color: {self.colors['card']};
                color: {self.colors['text_primary']};
                padding: 6px;
                border: none;
                font-weight: bold;
            """,
            
            'QScrollBar:vertical': f"""
                background-color: {self.colors['surface']};
                width: 12px;
                margin: 0px;
            """,
            
            'QScrollBar::handle:vertical': f"""
                background-color: {self.colors['border']};
                min-height: 20px;
                border-radius: 6px;
            """,
            
            'QScrollBar::handle:vertical:hover': f"""
                background-color: {self.colors['text_secondary']};
            """,
            
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical': """
                border: none;
                background: none;
            """,
            
            # Estilos especiales para nuestra app
            'GestureStatus': f"""
                background-color: {self.colors['card']};
                border: 2px solid {self.colors['border']};
                border-radius: 8px;
                padding: 10px;
            """,
            
            'CameraView': f"""
                background-color: black;
                border: 2px solid {self.colors['border']};
                border-radius: 4px;
            """,
            
            'ProfileCard': f"""
                background-color: {self.colors['card']};
                border: 1px solid {self.colors['border']};
                border-radius: 6px;
                padding: 12px;
            """,
            
            'ProfileCard.active': f"""
                border: 2px solid {self.colors['primary']};
                background-color: {QColor(self.colors['primary']).lighter(180).name()};
            """,
        }
    
    def apply_to_app(self, app):
        """Aplica el tema a la aplicación Qt."""
        # Configurar paleta de colores
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.colors['background']))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.colors['surface']))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(self.colors['card']))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(self.colors['surface']))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Text, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.colors['surface']))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.colors['text_primary']))
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(self.colors['secondary']))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self.colors['primary']))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        app.setPalette(palette)
        
        # Aplicar estilos CSS
        full_stylesheet = ""
        for selector, style in self.styles.items():
            full_stylesheet += f"{selector} {{{style}}}\n"
        
        app.setStyleSheet(full_stylesheet)


class LightTheme(Theme):
    """Tema claro para la aplicación."""
    
    def __init__(self):
        super().__init__("light")
        
        # Colores principales (invertidos del tema oscuro)
        self.colors = {
            'primary': '#2196F3',
            'secondary': '#FF9800',
            'accent': '#9C27B0',
            'background': '#F5F5F5',
            'surface': '#FFFFFF',
            'card': '#FAFAFA',
            'text_primary': '#212121',
            'text_secondary': '#757575',
            'text_disabled': '#BDBDBD',
            'border': '#E0E0E0',
            'error': '#F44336',
            'success': '#4CAF50',
            'warning': '#FFC107',
            'info': '#2196F3',
            'hand_detected': '#00BCD4',
            'arm_detected': '#9C27B0',
            'voice_active': '#FF5722',
            'gesture_active': '#4CAF50',
        }
        
        self.fonts = DarkTheme().fonts  # Mismas fuentes
        self.styles = self._generate_styles()
    
    def _generate_styles(self) -> Dict[str, str]:
        """Genera estilos CSS para tema claro."""
        # Reutiliza los estilos del tema oscuro pero con colores claros
        dark_theme = DarkTheme()
        styles = dark_theme.styles.copy()
        
        # Solo actualizamos los colores en los estilos
        import re
        for selector, style in styles.items():
            for dark_color, light_color in zip(dark_theme.colors.values(), self.colors.values()):
                style = style.replace(dark_color, light_color)
            styles[selector] = style
        
        return styles
    
    def apply_to_app(self, app):
        """Aplica el tema claro."""
        dark_theme = DarkTheme()
        dark_theme.colors = self.colors
        dark_theme.apply_to_app(app)


class StyleManager:
    """Gestor de estilos para la aplicación."""
    
    _instance = None
    _themes = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_themes()
        return cls._instance
    
    def _init_themes(self):
        """Inicializa los temas disponibles."""
        self._themes = {
            'dark': DarkTheme(),
            'light': LightTheme(),
        }
        
        # Tema por defecto
        self.current_theme = 'dark'
    
    def get_theme(self, name: str = None) -> Theme:
        """
        Obtiene un tema por nombre.
        
        Args:
            name: Nombre del tema (dark, light)
            
        Returns:
            Objeto Theme
        """
        if name is None:
            name = self.current_theme
        
        return self._themes.get(name, self._themes['dark'])
    
    def set_theme(self, name: str, app=None) -> bool:
        """
        Cambia el tema actual.
        
        Args:
            name: Nombre del tema
            app: Aplicación Qt para aplicar el tema
            
        Returns:
            True si se cambió correctamente
        """
        if name not in self._themes:
            return False
        
        self.current_theme = name
        
        if app:
            self._themes[name].apply_to_app(app)
        
        return True
    
    def list_themes(self) -> list:
        """Lista todos los temas disponibles."""
        return list(self._themes.keys())
    
    def get_color(self, color_name: str) -> str:
        """
        Obtiene un color del tema actual.
        
        Args:
            color_name: Nombre del color
            
        Returns:
            Código hexadecimal del color
        """
        theme = self.get_theme()
        return theme.colors.get(color_name, '#000000')
    
    def get_font(self, font_name: str) -> QFont:
        """
        Obtiene una fuente del tema actual.
        
        Args:
            font_name: Nombre de la fuente
            
        Returns:
            Objeto QFont
        """
        theme = self.get_theme()
        return theme.fonts.get(font_name, QFont('Segoe UI', 10))
    
    def apply_to_app(self, app):
        """Aplica el tema actual a la aplicación."""
        self.get_theme().apply_to_app(app)


# Instancia global
styles = StyleManager()

# Funciones de conveniencia
def apply_theme(app, theme_name: str = 'dark'):
    """Aplica un tema a la aplicación."""
    return styles.set_theme(theme_name, app)

def get_color(color_name: str) -> str:
    """Obtiene un color del tema actual."""
    return styles.get_color(color_name)

def get_font(font_name: str) -> QFont:
    """Obtiene una fuente del tema actual."""
    return styles.get_font(font_name)

def create_gradient(color1: str, color2: str, direction: str = 'horizontal') -> str:
    """
    Crea un gradiente CSS.
    
    Args:
        color1: Color inicial
        color2: Color final
        direction: Dirección ('horizontal' o 'vertical')
        
    Returns:
        Cadena CSS del gradiente
    """
    if direction == 'horizontal':
        return f"qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 {color1}, stop: 1 {color2})"
    else:
        return f"qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {color1}, stop: 1 {color2})"

def create_shadow(blur_radius: int = 10, offset: tuple = (0, 2), color: str = None) -> str:
    """
    Crea sombra CSS para widgets.
    
    Args:
        blur_radius: Radio de desenfoque
        offset: Desplazamiento (x, y)
        color: Color de la sombra
        
    Returns:
        Cadena CSS de sombra
    """
    if color is None:
        color = styles.get_color('background')
    
    x_offset, y_offset = offset
    return f"drop-shadow({x_offset}px {y_offset}px {blur_radius}px {color})"