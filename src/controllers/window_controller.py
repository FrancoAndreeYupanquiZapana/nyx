"""
🪟 WINDOW CONTROLLER - Control de Ventanas para NYX
===================================================
Controla ventanas del sistema integrado con perfiles de NYX.
Maneja activación, movimiento, redimensionado y organización.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WindowConfig:
    """Configuración de ventanas para NYX."""
    activation_delay: float = 0.1      # Retardo para activación
    resize_smoothness: float = 0.3     # Suavizado para redimensionar
    arrangement_gap: int = 10          # Espacio entre ventanas organizadas
    cache_timeout: float = 2.0         # Tiempo de cache de ventanas


class WindowController:
    """Controlador de ventanas integrado con NYX."""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el controlador de ventanas para NYX.
        
        Args:
            config: Configuración del sistema desde system.yaml
        """
        self.config = config or {}
        self.pygetwindow = None
        self.is_available = False
        
        # Configuración específica de NYX
        self.nyx_config = WindowConfig()
        
        # Cache de ventanas para mejor rendimiento
        self.window_cache = {}
        self.last_cache_update = 0
        
        # Reglas de búsqueda para aplicaciones comunes
        self.window_rules = {
            'chrome': ['chrome', 'google chrome', 'navegador'],
            'firefox': ['firefox', 'mozilla'],
            'terminal': ['terminal', 'bash', 'cmd', 'powershell', 'konsole'],
            'vscode': ['visual studio code', 'vscode', 'code'],
            'explorer': ['explorador', 'file manager', 'nautilus', 'dolphin'],
            'discord': ['discord'],
            'spotify': ['spotify']
        }
        
        # Historial para NYX UI
        self.action_history = []
        self.max_action_history = 50
        
        # Estadísticas para NYX UI
        self.stats = {
            'windows_managed': 0,
            'activations': 0,
            'resizes': 0,
            'moves': 0,
            'arrangements': 0,
            'errors': 0,
            'last_action': None,
            'uptime': time.time()
        }
        
        # Inicializar módulo
        self._init_window_module()
        
        logger.info(f"✅ WindowController inicializado para NYX")
    
    def _init_window_module(self):
        """Inicializa el módulo de ventanas."""
        try:
            import pygetwindow as gw
            self.pygetwindow = gw
            self.is_available = True
            logger.debug("✅ Módulo 'pygetwindow' cargado para NYX")
        except ImportError as e:
            logger.error(f"❌ NYX: No se pudo cargar módulo 'pygetwindow': {e}")
            self.is_available = False
        except Exception as e:
            logger.error(f"❌ NYX: Error inicializando ventanas: {e}")
            self.is_available = False
    
    def execute(self, command_data: Dict) -> Dict[str, Any]:
        """
        Ejecuta un comando de ventana desde NYX.
        
        Args:
            command_data: {
                'type': 'window',
                'command': 'activate' | 'close' | 'minimize' | 'maximize' | 'restore' |
                          'move' | 'resize' | 'arrange' | 'info',
                'window': 'título o "active"',
                'x': 100,
                'y': 100,
                'width': 800,
                'height': 600,
                'arrangement': 'grid' | 'horizontal' | 'vertical',
                'description': 'Descripción para logs'
            }
            
        Returns:
            Resultado de la ejecución
        """
        if not self.is_available:
            error_msg = "Módulo de ventanas no disponible"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg)
        
        command = command_data.get('command', 'activate')
        description = command_data.get('description', 'Comando de ventana')
        
        logger.info(f"🎮 NYX ejecutando ventana: {description}")
        
        try:
            # Obtener ventana objetivo
            window_identifier = command_data.get('window', 'active')
            window = self._find_window(window_identifier)
            
            if not window and window_identifier != 'active':
                error_msg = f"Ventana no encontrada: {window_identifier}"
                logger.warning(f"⚠️ NYX: {error_msg}")
                return self._format_result(False, error=error_msg, command_data=command_data)
            
            success = False
            
            if command == 'activate':
                success = self._execute_activate(window)
            elif command == 'close':
                success = self._execute_close(window)
            elif command == 'minimize':
                success = self._execute_minimize(window)
            elif command == 'maximize':
                success = self._execute_maximize(window)
            elif command == 'restore':
                success = self._execute_restore(window)
            elif command == 'move':
                success = self._execute_move(window, command_data)
            elif command == 'resize':
                success = self._execute_resize(window, command_data)
            elif command == 'arrange':
                success = self._execute_arrange(command_data)
            elif command == 'info':
                result = self._execute_info(window_identifier)
                return result  # Este retorna directamente
            else:
                error_msg = f"Comando de ventana desconocido: {command}"
                logger.error(f"❌ NYX: {error_msg}")
                return self._format_result(False, error=error_msg, command_data=command_data)
            
            # Actualizar estadísticas
            self._update_stats(success, command)
            
            # Guardar en historial
            self._add_to_history(command_data, success, window)
            
            return self._format_result(
                success=success,
                output=f"Comando '{command}' ejecutado",
                command_data=command_data
            )
            
        except Exception as e:
            error_msg = f"Error ejecutando ventana: {str(e)}"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg, command_data=command_data)
    
    def _find_window(self, identifier: Any) -> Optional[Any]:
        """Encuentra ventana por varios métodos."""
        if not self.is_available:
            return None
        
        # Actualizar cache si es necesario
        self._update_cache()
        
        # Ventana activa
        if identifier in ['active', 'focused', 'front', 'current']:
            try:
                return self.pygetwindow.getActiveWindow()
            except:
                return None
        
        # Buscar en cache por ID
        if isinstance(identifier, (str, int)):
            str_id = str(identifier)
            if str_id in self.window_cache:
                return self.window_cache[str_id]
        
        # Buscar por título
        return self._find_window_by_title(str(identifier))
    
    def _find_window_by_title(self, title: str) -> Optional[Any]:
        """Busca ventana por título con coincidencia flexible."""
        if not title:
            return None
        
        title_lower = title.lower()
        
        try:
            # Coincidencia exacta
            windows = self.pygetwindow.getWindowsWithTitle(title)
            if windows:
                return windows[0]
            
            # Coincidencia parcial
            all_windows = self.pygetwindow.getAllWindows()
            for window in all_windows:
                if window.title and title_lower in window.title.lower():
                    return window
            
            # Usar reglas de búsqueda
            for rule_name, keywords in self.window_rules.items():
                if any(keyword in title_lower for keyword in keywords):
                    for window in all_windows:
                        if window.title and any(keyword in window.title.lower() for keyword in keywords):
                            return window
        
        except Exception as e:
            logger.debug(f"⚠️ NYX: Error buscando ventana '{title}': {e}")
        
        return None
    
    def _update_cache(self):
        """Actualiza cache de ventanas."""
        current_time = time.time()
        
        if current_time - self.last_cache_update < self.nyx_config.cache_timeout:
            return
        
        try:
            windows = self.pygetwindow.getAllWindows()
            self.window_cache = {str(w._hWnd): w for w in windows}
            self.last_cache_update = current_time
        except:
            pass
    
    def _execute_activate(self, window: Any) -> bool:
        """Activa una ventana."""
        if not window:
            # Activar ventana activa actual (refresh)
            try:
                active = self.pygetwindow.getActiveWindow()
                if active:
                    active.activate()
                return True
            except:
                return False
        
        try:
            window.activate()
            time.sleep(self.nyx_config.activation_delay)
            
            self.stats['activations'] += 1
            logger.debug(f"🪟 NYX: Ventana activada: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error activando ventana: {e}")
            return False
    
    def _execute_close(self, window: Any) -> bool:
        """Cierra una ventana."""
        if not window:
            return False
        
        try:
            window.close()
            logger.info(f"🪟 NYX: Ventana cerrada: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error cerrando ventana: {e}")
            return False
    
    def _execute_minimize(self, window: Any) -> bool:
        """Minimiza una ventana."""
        if not window:
            return False
        
        try:
            window.minimize()
            logger.debug(f"🪟 NYX: Ventana minimizada: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error minimizando ventana: {e}")
            return False
    
    def _execute_maximize(self, window: Any) -> bool:
        """Maximiza una ventana."""
        if not window:
            return False
        
        try:
            window.maximize()
            logger.debug(f"🪟 NYX: Ventana maximizada: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error maximizando ventana: {e}")
            return False
    
    def _execute_restore(self, window: Any) -> bool:
        """Restaura una ventana."""
        if not window:
            return False
        
        try:
            window.restore()
            logger.debug(f"🪟 NYX: Ventana restaurada: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error restaurando ventana: {e}")
            return False
    
    def _execute_move(self, window: Any, data: Dict) -> bool:
        """Mueve una ventana."""
        if not window:
            return False
        
        x = data.get('x', window.left)
        y = data.get('y', window.top)
        
        try:
            window.moveTo(x, y)
            
            self.stats['moves'] += 1
            logger.debug(f"🪟 NYX: Ventana movida a ({x}, {y}): {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error moviendo ventana: {e}")
            return False
    
    def _execute_resize(self, window: Any, data: Dict) -> bool:
        """Redimensiona una ventana."""
        if not window:
            return False
        
        width = data.get('width', window.width)
        height = data.get('height', window.height)
        
        try:
            if self.nyx_config.resize_smoothness > 0:
                # Redimensionado suavizado
                current_width, current_height = window.width, window.height
                steps = 5
                
                for i in range(1, steps + 1):
                    t = i / steps
                    eased_t = t * t * (3 - 2 * t)  # ease-in-out
                    
                    interim_width = int(current_width + (width - current_width) * eased_t)
                    interim_height = int(current_height + (height - current_height) * eased_t)
                    
                    window.resizeTo(interim_width, interim_height)
                    time.sleep(0.05)
            else:
                # Redimensionado directo
                window.resizeTo(width, height)
            
            self.stats['resizes'] += 1
            logger.debug(f"🪟 NYX: Ventana redimensionada a {width}x{height}: {window.title}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error redimensionando ventana: {e}")
            return False
    
    def _execute_arrange(self, data: Dict) -> bool:
        """Organiza ventanas en un patrón."""
        arrangement = data.get('arrangement', 'grid')
        gap = data.get('gap', self.nyx_config.arrangement_gap)
        max_windows = data.get('max_windows', 4)
        
        try:
            # Obtener ventanas visibles
            windows = self.pygetwindow.getAllWindows()
            visible_windows = [w for w in windows if w.title and hasattr(w, 'visible') and w.visible][:max_windows]
            
            if not visible_windows:
                logger.warning("⚠️ NYX: No hay ventanas visibles para organizar")
                return False
            
            # Tamaño de pantalla aproximado
            screen_width, screen_height = 1920, 1080  # Valores por defecto
            
            if arrangement == 'grid':
                rows = int(len(visible_windows) ** 0.5)
                cols = (len(visible_windows) + rows - 1) // rows
                
                cell_width = (screen_width - gap * (cols + 1)) // cols
                cell_height = (screen_height - gap * (rows + 1)) // rows
                
                for i, window in enumerate(visible_windows):
                    row = i // cols
                    col = i % cols
                    
                    x = gap + col * (cell_width + gap)
                    y = gap + row * (cell_height + gap)
                    
                    window.moveTo(x, y)
                    window.resizeTo(cell_width, cell_height)
            
            elif arrangement == 'horizontal':
                cell_width = (screen_width - gap * (len(visible_windows) + 1)) // len(visible_windows)
                
                for i, window in enumerate(visible_windows):
                    x = gap + i * (cell_width + gap)
                    y = gap
                    height = screen_height - 2 * gap
                    
                    window.moveTo(x, y)
                    window.resizeTo(cell_width, height)
            
            elif arrangement == 'vertical':
                cell_height = (screen_height - gap * (len(visible_windows) + 1)) // len(visible_windows)
                
                for i, window in enumerate(visible_windows):
                    x = gap
                    y = gap + i * (cell_height + gap)
                    width = screen_width - 2 * gap
                    
                    window.moveTo(x, y)
                    window.resizeTo(width, cell_height)
            
            self.stats['arrangements'] += 1
            logger.info(f"🪟 NYX: {len(visible_windows)} ventanas organizadas en patrón {arrangement}")
            return True
            
        except Exception as e:
            logger.error(f"❌ NYX: Error organizando ventanas: {e}")
            return False
    
    def _execute_info(self, window_identifier: str) -> Dict[str, Any]:
        """Obtiene información de una ventana."""
        window = self._find_window(window_identifier)
        
        if not window:
            return self._format_result(False, error="Ventana no encontrada")
        
        try:
            info = {
                'title': window.title or '(sin título)',
                'handle': str(window._hWnd) if hasattr(window, '_hWnd') else 'unknown',
                'position': {
                    'x': window.left,
                    'y': window.top,
                    'width': window.width,
                    'height': window.height
                },
                'state': {
                    'active': window.isActive if hasattr(window, 'isActive') else False,
                    'maximized': window.isMaximized if hasattr(window, 'isMaximized') else False,
                    'minimized': window.isMinimized if hasattr(window, 'isMinimized') else False
                }
            }
            
            return self._format_result(
                success=True,
                output="Información de ventana obtenida",
                info=info
            )
            
        except Exception as e:
            error_msg = f"Error obteniendo info de ventana: {str(e)}"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg)
    
    def _format_result(self, success: bool, output: str = '', 
                      error: str = '', command_data: Dict = None, **kwargs) -> Dict[str, Any]:
        """Formatea resultado para NYX."""
        result = {
            'success': success,
            'timestamp': time.time(),
            'output': output,
            'error': error,
            'type': 'window'
        }
        
        if command_data:
            result['command_data'] = command_data
        
        result.update(kwargs)
        return result
    
    def _update_stats(self, success: bool, command_type: str):
        """Actualiza estadísticas."""
        if success:
            self.stats['windows_managed'] += 1
            self.stats['last_action'] = {
                'type': command_type,
                'time': time.time()
            }
        else:
            self.stats['errors'] += 1
    
    def _add_to_history(self, command_data: Dict, success: bool, window: Any = None):
        """Añade acción al historial."""
        entry = {
            'command': command_data,
            'success': success,
            'timestamp': time.time(),
            'window_title': window.title if window else 'unknown'
        }
        
        self.action_history.append(entry)
        if len(self.action_history) > self.max_action_history:
            self.action_history.pop(0)
    
    def get_active_window_info(self) -> Dict[str, Any]:
        """Obtiene información de la ventana activa."""
        if not self.is_available:
            return {}
        
        try:
            window = self.pygetwindow.getActiveWindow()
            if window:
                return {
                    'title': window.title,
                    'position': {
                        'x': window.left,
                        'y': window.top,
                        'width': window.width,
                        'height': window.height
                    }
                }
        except:
            pass
        
        return {}
    
    def list_windows(self) -> List[Dict[str, Any]]:
        """Lista todas las ventanas disponibles."""
        if not self.is_available:
            return []
        
        try:
            windows = self.pygetwindow.getAllWindows()
            window_list = []
            
            for window in windows:
                if not window.title:  # Omitir ventanas sin título
                    continue
                
                window_list.append({
                    'title': window.title,
                    'handle': str(window._hWnd) if hasattr(window, '_hWnd') else 'unknown',
                    'position': {
                        'x': window.left,
                        'y': window.top,
                        'width': window.width,
                        'height': window.height
                    },
                    'active': window.isActive if hasattr(window, 'isActive') else False
                })
            
            return window_list
            
        except Exception as e:
            logger.error(f"❌ NYX: Error listando ventanas: {e}")
            return []
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene estado del controlador para NYX UI."""
        return {
            'available': self.is_available,
            'config': {
                'activation_delay': self.nyx_config.activation_delay,
                'resize_smoothness': self.nyx_config.resize_smoothness,
                'arrangement_gap': self.nyx_config.arrangement_gap
            },
            'stats': self.stats,
            'cache_size': len(self.window_cache),
            'window_rules_count': len(self.window_rules),
            'action_history_size': len(self.action_history)
        }
    
    def add_window_rule(self, app_name: str, keywords: List[str]):
        """Agrega regla de búsqueda para una aplicación."""
        self.window_rules[app_name] = keywords
        logger.info(f"✅ NYX: Regla agregada para '{app_name}': {keywords}")
    
    def update_config(self, new_config: Dict):
        """Actualiza configuración desde perfil."""
        if 'window_settings' in new_config:
            window_settings = new_config['window_settings']
            
            if 'activation_delay' in window_settings:
                self.nyx_config.activation_delay = window_settings['activation_delay']
                logger.info(f"🔄 Retardo de activación cambiado: {self.nyx_config.activation_delay}s")
            
            if 'arrangement_gap' in window_settings:
                self.nyx_config.arrangement_gap = window_settings['arrangement_gap']
                logger.info(f"🔄 Espacio entre ventanas cambiado: {self.nyx_config.arrangement_gap}px")
    
    def cleanup(self):
        """Limpia recursos para NYX."""
        self.window_cache.clear()
        self.action_history.clear()
        logger.info("✅ WindowController limpiado para NYX")