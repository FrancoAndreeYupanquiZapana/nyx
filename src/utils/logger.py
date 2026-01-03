"""
📝 LOGGER - Sistema de registro centralizado NYX
================================================
Configura logging para el sistema NYX con diferentes niveles y handlers.
Sigue arquitectura modular y permite configuración flexible.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

class NYXLogger:
    """Logger centralizado para el sistema NYX."""
    
    # Formato predefinido para logs
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DEFAULT_DATE_FORMAT = '%H:%M:%S'
    
    # Colores para consola (opcional)
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Verde
        'WARNING': '\033[33m',   # Amarillo
        'ERROR': '\033[31m',     # Rojo
        'CRITICAL': '\033[41m',  # Rojo fondo
        'RESET': '\033[0m'       # Reset
    }
    
    def __init__(self, 
                 app_name: str = "NYX",
                 log_dir: str = "workspace/logs",
                 level: str = "INFO",
                 console: bool = True,
                 colors: bool = True):
        """
        Inicializa el sistema de logging para NYX.
        
        Args:
            app_name: Nombre de la aplicación
            log_dir: Directorio para archivos de log
            level: Nivel de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console: Habilitar salida por consola
            colors: Habilitar colores en consola
        """
        self.app_name = app_name
        self.log_dir = Path(log_dir)
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.colors_enabled = colors and console
        
        # Crear directorio de logs
        self.log_dir.mkdir(exist_ok=True)
        
        # Configurar logger principal
        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(self.level)
        
        # Evitar propagación al root logger
        self.logger.propagate = False
        
        # Remover handlers existentes
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Configurar handlers
        self._setup_handlers(console)
        
        # Log de inicio
        self.info(f"📝 Logger NYX configurado (nivel: {level})")
        self.info(f"📁 Logs en: {self.log_dir.absolute()}")
    
    def _setup_handlers(self, console: bool = True):
        """Configura todos los handlers de logging."""
        # Formato base
        formatter = logging.Formatter(
            self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )
        
        # Handler para consola (opcional con colores)
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)
            
            if self.colors_enabled:
                console_handler.setFormatter(self._create_colored_formatter())
            else:
                console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
        
        # Handler para archivo de debug (todos los niveles)
        debug_file = self.log_dir / f"{self.app_name.lower()}_debug.log"
        debug_handler = logging.FileHandler(debug_file, encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        self.logger.addHandler(debug_handler)
        
        # Handler para archivo de errores (solo WARNING+)
        error_file = self.log_dir / f"{self.app_name.lower()}_error.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
        
        # Handler rotativo para el log principal
        main_file = self.log_dir / f"{self.app_name.lower()}.log"
        rotating_handler = logging.handlers.RotatingFileHandler(
            main_file, 
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        rotating_handler.setLevel(self.level)
        rotating_handler.setFormatter(formatter)
        self.logger.addHandler(rotating_handler)
    
    def _create_colored_formatter(self) -> logging.Formatter:
        """Crea un formatter con colores para consola."""
        class ColoredFormatter(logging.Formatter):
            def format(self, record):
                # Agregar color al nivel
                levelname = record.levelname
                if levelname in NYXLogger.COLORS:
                    record.levelname = (
                        f"{NYXLogger.COLORS[levelname]}{levelname}"
                        f"{NYXLogger.COLORS['RESET']}"
                    )
                
                # Formatear el mensaje
                return super().format(record)
        
        return ColoredFormatter(
            self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )
    
    # ========== MÉTODOS PÚBLICOS BÁSICOS ==========
    
    def debug(self, message: str, **kwargs):
        """Registro a nivel DEBUG."""
        if kwargs:
            message = f"{message} {self._format_kwargs(kwargs)}"
        self.logger.debug(message)
    
    def info(self, message: str, **kwargs):
        """Registro a nivel INFO."""
        if kwargs:
            message = f"{message} {self._format_kwargs(kwargs)}"
        self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Registro a nivel WARNING."""
        if kwargs:
            message = f"{message} {self._format_kwargs(kwargs)}"
        self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """Registro a nivel ERROR."""
        if kwargs:
            message = f"{message} {self._format_kwargs(kwargs)}"
        self.logger.error(message, exc_info=kwargs.get('exc_info', False))
    
    def critical(self, message: str, **kwargs):
        """Registro a nivel CRITICAL."""
        if kwargs:
            message = f"{message} {self._format_kwargs(kwargs)}"
        self.logger.critical(message)
    
    # ========== MÉTODOS ESPECIALIZADOS PARA NYX ==========
    
    def log_system_start(self, version: str = "1.0.0"):
        """Registro especial para inicio del sistema."""
        self.info("=" * 50)
        self.info(f"🚀 INICIANDO NYX v{version}")
        self.info("=" * 50)
    
    def log_system_stop(self):
        """Registro especial para detención del sistema."""
        self.info("=" * 50)
        self.info("🛑 NYX DETENIDO")
        self.info("=" * 50)
    
    def log_gesture_detected(self, 
                           detector: str, 
                           gesture: str, 
                           confidence: float = 1.0,
                           hand: str = "unknown",
                           **kwargs):
        """Registro especializado para gestos detectados."""
        emoji = self._get_gesture_emoji(gesture)
        hand_emoji = "🖐️" if hand == "right" else "🤚" if hand == "left" else "✋"
        
        message = (
            f"{emoji} [{detector.upper()}] "
            f"Gesto: {gesture} "
            f"(conf: {confidence:.2f}, mano: {hand_emoji})"
        )
        
        if kwargs:
            message += f" {self._format_kwargs(kwargs)}"
        
        self.info(message)
    
    def log_action_executed(self,
                          controller: str,
                          action: str,
                          command: str = "",
                          status: str = "OK",
                          **kwargs):
        """Registro especializado para acciones ejecutadas."""
        icon = "✅" if status == "OK" else "⚠️" if status == "WARNING" else "❌"
        
        message = (
            f"{icon} [{controller.upper()}] "
            f"Acción: {action}"
        )
        
        if command:
            message += f" -> '{command}'"
        
        if kwargs:
            message += f" {self._format_kwargs(kwargs)}"
        
        if status == "OK":
            self.info(message)
        elif status == "WARNING":
            self.warning(message)
        else:
            self.error(message)
    
    def log_profile_event(self,
                         profile_name: str,
                         event: str,
                         details: str = "",
                         **kwargs):
        """Registro especializado para eventos de perfiles."""
        icons = {
            'loaded': '📂',
            'saved': '💾',
            'changed': '🔄',
            'created': '✨',
            'deleted': '🗑️'
        }
        
        icon = icons.get(event, '👤')
        
        message = f"{icon} [PERFIL:{profile_name}] {event.upper()}"
        
        if details:
            message += f" - {details}"
        
        if kwargs:
            message += f" {self._format_kwargs(kwargs)}"
        
        self.info(message)
    
    def log_config_event(self,
                        event: str,
                        key: str = "",
                        value: Any = None,
                        **kwargs):
        """Registro especializado para eventos de configuración."""
        icons = {
            'loaded': '⚙️',
            'saved': '💾',
            'updated': '📝',
            'reloaded': '🔄'
        }
        
        icon = icons.get(event, '⚙️')
        
        message = f"{icon} [CONFIG] {event.upper()}"
        
        if key:
            message += f" - {key}"
            if value is not None:
                message += f" = {value}"
        
        if kwargs:
            message += f" {self._format_kwargs(kwargs)}"
        
        self.info(message)
    
    # ========== MÉTODOS UTILITARIOS ==========
    
    def _get_gesture_emoji(self, gesture: str) -> str:
        """Obtiene emoji apropiado para un gesto."""
        emoji_map = {
            'fist': '✊',
            'peace': '✌️',
            'thumbs_up': '👍',
            'thumbs_down': '👎',
            'ok': '👌',
            'point': '👉',
            'rock': '🤘',
            'palm': '🖐️',
            'victory': '✌️',
            'call_me': '🤙',
            'stop': '🛑'
        }
        return emoji_map.get(gesture.lower(), '👋')
    
    def _format_kwargs(self, kwargs: Dict) -> str:
        """Formatea kwargs adicionales para logs."""
        if not kwargs:
            return ""
        
        items = []
        for key, value in kwargs.items():
            if key not in ['exc_info']:  # Excluir kwargs especiales
                items.append(f"{key}={value}")
        
        if items:
            return f"[{', '.join(items)}]"
        return ""
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """
        Obtiene un logger hijo con el nombre especificado.
        
        Args:
            name: Nombre del submódulo (ej: "core.pipeline")
            
        Returns:
            Logger configurado
        """
        if name:
            full_name = f"{self.app_name}.{name}"
        else:
            full_name = self.app_name
        
        return logging.getLogger(full_name)
    
    def set_level(self, level: str):
        """
        Cambia el nivel de logging.
        
        Args:
            level: Nuevo nivel (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        new_level = getattr(logging, level.upper(), None)
        if new_level:
            self.logger.setLevel(new_level)
            for handler in self.logger.handlers:
                handler.setLevel(new_level)
            self.info(f"📊 Nivel de log cambiado a: {level}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de los archivos de log.
        
        Returns:
            Diccionario con estadísticas
        """
        stats = {
            'log_dir': str(self.log_dir.absolute()),
            'log_files': [],
            'total_size': 0
        }
        
        try:
            for log_file in self.log_dir.glob("*.log"):
                file_info = {
                    'name': log_file.name,
                    'size': log_file.stat().st_size,
                    'modified': log_file.stat().st_mtime
                }
                stats['log_files'].append(file_info)
                stats['total_size'] += file_info['size']
        except Exception as e:
            self.error(f"Error obteniendo estadísticas de logs: {e}")
        
        return stats
    
    def clear_logs(self, keep_recent: bool = True):
        """
        Limpia los archivos de log.
        
        Args:
            keep_recent: Mantener el archivo de log actual
        """
        try:
            deleted = 0
            for log_file in self.log_dir.glob("*.log*"):  # Incluye backups
                if keep_recent and not log_file.name.endswith('.log'):
                    # Eliminar solo backups rotativos
                    log_file.unlink()
                    deleted += 1
                elif not keep_recent:
                    # Eliminar todo
                    log_file.unlink()
                    deleted += 1
            
            self.info(f"🧹 {deleted} archivos de log limpiados")
            return deleted
            
        except Exception as e:
            self.error(f"Error limpiando logs: {e}")
            return 0

# ¡NO hay instancia global aquí!
# El logger debe crearse con la configuración de la app
# ========= INSTANCIA GLOBAL DEL LOGGER =========

_nyx_logger = NYXLogger(
    app_name="NYX",
    log_dir="workspace/logs",
    level="INFO",
    console=True,
    colors=True
)

# Logger principal para imports directos
logger = _nyx_logger
