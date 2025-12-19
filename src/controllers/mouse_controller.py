"""
🖱️ MOUSE CONTROLLER - Control del Mouse para NYX
================================================
Controla movimiento, clics y scroll del mouse integrado con NYX.
Usa configuración de perfiles para sensibilidad y comportamiento.
"""

import time
import threading
import math
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MouseConfig:
    """Configuración del mouse para NYX."""
    sensitivity: float = 1.0           # Sensibilidad general
    click_delay: float = 0.1           # Retardo entre clics
    scroll_amount: int = 3             # Cantidad de scroll
    smooth_movement: bool = True       # Movimiento suave
    movement_steps: int = 20           # Pasos para movimiento suave
    gesture_threshold: int = 50        # Umbral para detección de gestos
    drag_duration: float = 0.5         # Duración de arrastre


class MouseController:
    """Controlador del mouse integrado con NYX."""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el controlador del mouse para NYX.
        
        Args:
            config: Configuración del sistema desde system.yaml
        """
        self.config = config or {}
        self.pyautogui = None
        self.is_available = False
        
        # Configuración específica de NYX
        self.nyx_config = MouseConfig()
        
        # Aplicar configuración si existe
        if 'mouse_settings' in self.config:
            mouse_settings = self.config.get('mouse_settings', {})
            self.nyx_config.sensitivity = mouse_settings.get('sensitivity', 1.0)
            self.nyx_config.click_delay = mouse_settings.get('click_delay', 0.1)
            self.nyx_config.scroll_amount = mouse_settings.get('scroll_amount', 3)
            self.nyx_config.smooth_movement = mouse_settings.get('smooth_movement', True)
            self.nyx_config.gesture_threshold = mouse_settings.get('gesture_threshold', 50)
        
        # Estado actual
        self.current_position = (0, 0)
        self.is_dragging = False
        self.drag_start = None
        
        # Para seguimiento de gestos
        self.last_positions = []     # Últimas posiciones para seguimiento
        self.max_history = 10
        self.gesture_cooldown = 0.3  # Tiempo entre gestos
        self.last_gesture_time = 0
        
        # Historial para NYX UI
        self.action_history = []
        self.max_action_history = 50
        
        # Estadísticas para NYX UI
        self.stats = {
            'total_clicks': 0,
            'total_movements': 0,
            'total_scrolls': 0,
            'total_drags': 0,
            'gestures_detected': 0,
            'errors': 0,
            'last_action': None,
            'uptime': time.time()
        }
        
        # Inicializar módulo
        self._init_mouse_module()
        
        # Obtener posición inicial
        if self.is_available:
            self._update_position()
        
        logger.info(f"✅ MouseController inicializado para NYX (sensibilidad: {self.nyx_config.sensitivity})")
    
    def _init_mouse_module(self):
        """Inicializa el módulo de mouse."""
        try:
            import pyautogui
            self.pyautogui = pyautogui
            
            # Configurar failsafe (se activa al mover a esquina)
            self.pyautogui.FAILSAFE = True
            
            self.is_available = True
            logger.debug("✅ Módulo 'pyautogui' cargado para NYX")
        except ImportError as e:
            logger.error(f"❌ NYX: No se pudo cargar módulo 'pyautogui': {e}")
            self.is_available = False
        except Exception as e:
            logger.error(f"❌ NYX: Error inicializando mouse: {e}")
            self.is_available = False
    
    def execute(self, command_data: Dict) -> Dict[str, Any]:
        """
        Ejecuta un comando de mouse desde NYX.
        
        Args:
            command_data: {
                'type': 'mouse',
                'command': 'click' | 'move' | 'scroll' | 'drag' | 'gesture',
                'button': 'left' | 'right' | 'middle',
                'clicks': 1,
                'x': 100,
                'y': 100,
                'duration': 0.2,
                'relative': False,
                'amount': 3,
                'direction': 'up' | 'down',
                'description': 'Descripción para logs'
            }
            
        Returns:
            Resultado de la ejecución
        """
        if not self.is_available:
            error_msg = "Módulo de mouse no disponible"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg)
        
        command = command_data.get('command', 'click')
        description = command_data.get('description', 'Comando de mouse')
        
        logger.info(f"🎮 NYX ejecutando mouse: {description}")
        
        try:
            success = False
            
            if command == 'click':
                success = self._execute_click(command_data)
            elif command == 'move':
                success = self._execute_move(command_data)
            elif command == 'scroll':
                success = self._execute_scroll(command_data)
            elif command == 'drag':
                success = self._execute_drag(command_data)
            elif command == 'gesture':
                success = self._execute_gesture(command_data)
            else:
                error_msg = f"Comando de mouse desconocido: {command}"
                logger.error(f"❌ NYX: {error_msg}")
                return self._format_result(False, error=error_msg, command_data=command_data)
            
            # Actualizar estadísticas
            self._update_stats(success, command)
            
            # Guardar en historial
            self._add_to_history(command_data, success)
            
            return self._format_result(
                success=success,
                output=f"Comando '{command}' ejecutado",
                command_data=command_data
            )
            
        except Exception as e:
            error_msg = f"Error ejecutando mouse: {str(e)}"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg, command_data=command_data)
    
    def _execute_click(self, data: Dict) -> bool:
        """Ejecuta clic de mouse."""
        button = data.get('button', 'left')
        clicks = data.get('clicks', 1)
        x = data.get('x')
        y = data.get('y')
        
        # Aplicar sensibilidad de NYX
        if x is not None and y is not None:
            x = int(x * self.nyx_config.sensitivity)
            y = int(y * self.nyx_config.sensitivity)
        
        try:
            if x is not None and y is not None:
                self.pyautogui.click(x, y, clicks=clicks, button=button)
                logger.debug(f"🖱️ NYX: Clic en ({x}, {y}) botón {button}")
            else:
                self.pyautogui.click(button=button, clicks=clicks)
                logger.debug(f"🖱️ NYX: Clic en posición actual botón {button}")
            
            # Delay entre clics
            time.sleep(self.nyx_config.click_delay)
            
            self._update_position()
            self.stats['total_clicks'] += clicks
            
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error en clic: {e}")
            return False
    
    def _execute_move(self, data: Dict) -> bool:
        """Ejecuta movimiento de mouse."""
        relative = data.get('relative', False)
        duration = data.get('duration', 0.1)
        
        # Verificar si hay datos de cursor desde el gesto
        gesture_data = data.get('gesture_data', {})
        cursor_pos = gesture_data.get('cursor')
        
        if cursor_pos and self.pyautogui:
            # Mapeo directo de coordenadas normalizadas a pantalla
            screen_w, screen_h = self.pyautogui.size()
            x = int(cursor_pos.get('x', 0) * screen_w)
            y = int(cursor_pos.get('y', 0) * screen_h)
            
            # Forzar movimiento absoluto y sin suavizado excesivo para respuesta rápida
            relative = False
            duration = min(duration, 0.05) 
            logger.debug(f"🖱️ Cursor track: {x}, {y}")
        else:
            # Comportamiento normal (params explícitos)
            x = data.get('x', 0)
            y = data.get('y', 0)
            
            # Aplicar sensibilidad de NYX solo a deltas manuales (no tracking)
            x = int(x * self.nyx_config.sensitivity)
            y = int(y * self.nyx_config.sensitivity)
        
        try:
            if relative:
                # Convertir a absoluto
                current_x, current_y = self.current_position
                x = current_x + x
                y = current_y + y
            
            if self.nyx_config.smooth_movement and duration > 0:
                # Movimiento suave
                self._smooth_move(x, y, duration)
            else:
                # Movimiento directo
                self.pyautogui.moveTo(x, y, duration=duration)
            
            self._update_position()
            self.stats['total_movements'] += 1
            
            logger.debug(f"🖱️ NYX: Movido a ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error moviendo mouse: {e}")
            return False
    
    def _smooth_move(self, x: int, y: int, duration: float):
        """Movimiento suave con interpolación."""
        start_x, start_y = self.current_position
        
        for step in range(1, self.nyx_config.movement_steps + 1):
            t = step / self.nyx_config.movement_steps
            # Easing: ease-in-out
            eased_t = t * t * (3 - 2 * t)
            
            current_x = start_x + (x - start_x) * eased_t
            current_y = start_y + (y - start_y) * eased_t
            
            self.pyautogui.moveTo(current_x, current_y)
            time.sleep(duration / self.nyx_config.movement_steps)
    
    def _execute_scroll(self, data: Dict) -> bool:
        """Ejecuta scroll de mouse."""
        amount = data.get('amount', self.nyx_config.scroll_amount)
        direction = data.get('direction', 'up')
        
        if direction == 'down':
            amount = -amount
        
        try:
            self.pyautogui.scroll(amount)
            self.stats['total_scrolls'] += 1
            
            logger.debug(f"🖱️ NYX: Scroll {direction} {abs(amount)} unidades")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error en scroll: {e}")
            return False
    
    def _execute_drag(self, data: Dict) -> bool:
        """Ejecuta arrastre de mouse."""
        x1 = data.get('x1')
        y1 = data.get('y1')
        x2 = data.get('x2')
        y2 = data.get('y2')
        duration = data.get('duration', self.nyx_config.drag_duration)
        button = data.get('button', 'left')
        
        # Aplicar sensibilidad
        if x1 is not None:
            x1 = int(x1 * self.nyx_config.sensitivity)
        if y1 is not None:
            y1 = int(y1 * self.nyx_config.sensitivity)
        if x2 is not None:
            x2 = int(x2 * self.nyx_config.sensitivity)
        if y2 is not None:
            y2 = int(y2 * self.nyx_config.sensitivity)
        
        # Usar posición actual si no se especifica inicio
        if x1 is None or y1 is None:
            current_x, current_y = self.current_position
            x1 = current_x
            y1 = current_y
        
        # Usar desplazamiento si no se especifica fin
        if x2 is None:
            x2 = x1 + 100
        if y2 is None:
            y2 = y1 + 100
        
        try:
            # Mover al punto de inicio
            self.pyautogui.moveTo(x1, y1)
            
            # Arrastrar
            self.pyautogui.dragTo(x2, y2, duration=duration, button=button)
            
            self._update_position()
            self.stats['total_drags'] += 1
            
            logger.debug(f"🖱️ NYX: Arrastrado de ({x1}, {y1}) a ({x2}, {y2})")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error arrastrando: {e}")
            return False
    
    def _execute_gesture(self, data: Dict) -> bool:
        """Ejecuta gesto de mouse."""
        gesture_type = data.get('gesture_type', '')
        
        current_time = time.time()
        if current_time - self.last_gesture_time < self.gesture_cooldown:
            logger.debug(f"🖱️ NYX: Gestos en cooldown")
            return False
        
        try:
            if gesture_type == 'swipe_up':
                self.pyautogui.scroll(self.nyx_config.scroll_amount)
            elif gesture_type == 'swipe_down':
                self.pyautogui.scroll(-self.nyx_config.scroll_amount)
            elif gesture_type == 'swipe_left':
                # Simular Alt+Left (navegación anterior)
                import keyboard
                keyboard.press('alt')
                keyboard.press('left')
                time.sleep(0.1)
                keyboard.release('left')
                keyboard.release('alt')
            elif gesture_type == 'swipe_right':
                # Simular Alt+Right (navegación siguiente)
                import keyboard
                keyboard.press('alt')
                keyboard.press('right')
                time.sleep(0.1)
                keyboard.release('right')
                keyboard.release('alt')
            else:
                return False
            
            self.stats['gestures_detected'] += 1
            self.last_gesture_time = current_time
            
            logger.debug(f"🖱️ NYX: Gestos ejecutado: {gesture_type}")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error en gesto: {e}")
            return False
    
    def _update_position(self):
        """Actualiza posición actual del mouse."""
        if not self.is_available:
            return
        
        try:
            self.current_position = self.pyautogui.position()
            
            # Guardar en historial para seguimiento
            self.last_positions.append({
                'x': self.current_position.x,
                'y': self.current_position.y,
                'time': time.time()
            })
            
            if len(self.last_positions) > self.max_history:
                self.last_positions.pop(0)
        except:
            pass
    
    def _format_result(self, success: bool, output: str = '', 
                      error: str = '', command_data: Dict = None) -> Dict[str, Any]:
        """Formatea resultado para NYX."""
        result = {
            'success': success,
            'timestamp': time.time(),
            'output': output,
            'error': error,
            'type': 'mouse'
        }
        
        if command_data:
            result['command_data'] = command_data
        
        return result
    
    def _update_stats(self, success: bool, command_type: str):
        """Actualiza estadísticas."""
        if success:
            self.stats['last_action'] = {
                'type': command_type,
                'time': time.time()
            }
        else:
            self.stats['errors'] += 1
    
    def _add_to_history(self, command_data: Dict, success: bool):
        """Añade acción al historial."""
        entry = {
            'command': command_data,
            'success': success,
            'timestamp': time.time(),
            'position': self.current_position
        }
        
        self.action_history.append(entry)
        if len(self.action_history) > self.max_action_history:
            self.action_history.pop(0)
    
    def get_position(self) -> Dict[str, int]:
        """Obtiene posición actual del mouse."""
        self._update_position()
        return {
            'x': self.current_position[0],
            'y': self.current_position[1]
        }
    
    def get_screen_size(self) -> Dict[str, int]:
        """Obtiene tamaño de pantalla."""
        if not self.is_available:
            return {'width': 1920, 'height': 1080}
        
        try:
            size = self.pyautogui.size()
            return {'width': size.width, 'height': size.height}
        except:
            return {'width': 1920, 'height': 1080}
    
    def detect_gesture_from_movement(self) -> Optional[Dict]:
        """Detecta gesto basado en historial de movimiento."""
        if len(self.last_positions) < 3:
            return None
        
        # Obtener puntos recientes
        recent = self.last_positions[-3:]
        
        # Calcular dirección
        dx = recent[-1]['x'] - recent[0]['x']
        dy = recent[-1]['y'] - recent[0]['y']
        dt = recent[-1]['time'] - recent[0]['time']
        
        if dt == 0 or dt > 1.0:  # Movimiento muy lento o viejo
            return None
        
        speed = math.sqrt(dx*dx + dy*dy) / dt
        
        # Detectar gesto basado en dirección y velocidad
        gesture = None
        
        if speed > 100:  # Movimiento rápido
            if abs(dx) > abs(dy) * 2 and abs(dx) > self.nyx_config.gesture_threshold:
                gesture = 'swipe_right' if dx > 0 else 'swipe_left'
            elif abs(dy) > abs(dx) * 2 and abs(dy) > self.nyx_config.gesture_threshold:
                gesture = 'swipe_down' if dy > 0 else 'swipe_up'
        
        if gesture:
            return {
                'gesture': gesture,
                'speed': speed,
                'distance': math.sqrt(dx*dx + dy*dy),
                'direction': (dx, dy)
            }
        
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene estado del controlador para NYX UI."""
        return {
            'available': self.is_available,
            'config': {
                'sensitivity': self.nyx_config.sensitivity,
                'smooth_movement': self.nyx_config.smooth_movement,
                'gesture_threshold': self.nyx_config.gesture_threshold
            },
            'stats': self.stats,
            'position': self.get_position(),
            'screen_size': self.get_screen_size(),
            'is_dragging': self.is_dragging,
            'action_history_size': len(self.action_history)
        }
    
    def update_config(self, new_config: Dict):
        """Actualiza configuración desde perfil."""
        if 'mouse_settings' in new_config:
            mouse_settings = new_config['mouse_settings']
            
            if 'sensitivity' in mouse_settings:
                self.nyx_config.sensitivity = mouse_settings['sensitivity']
                logger.info(f"🔄 Sensibilidad del mouse cambiada: {self.nyx_config.sensitivity}")
            
            if 'smooth_movement' in mouse_settings:
                self.nyx_config.smooth_movement = mouse_settings['smooth_movement']
                logger.info(f"🔄 Movimiento suave: {'ON' if self.nyx_config.smooth_movement else 'OFF'}")
    
    def cleanup(self):
        """Limpia recursos para NYX."""
        if self.is_dragging:
            try:
                self.pyautogui.mouseUp()
                self.is_dragging = False
            except:
                pass
        
        logger.info("✅ MouseController limpiado para NYX")