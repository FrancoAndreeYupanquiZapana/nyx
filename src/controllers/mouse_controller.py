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
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MouseConfig:
    """Configuración del mouse para NYX."""
    sensitivity: float = 1.0           # Sensibilidad general
    click_delay: float = 0.1           # Retardo entre clics
    scroll_amount: int = 300           # Cantidad de scroll (Windows needs ~100 per notch)
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
        self.is_dragging = False
        self.drag_start_pos = None
        self.pinch_start_time = None # Para diferenciar clic vs drag
        
        # Para suavizado suave (snippet usuario)
        self.prev_x = 0
        self.prev_y = 0
        self.smooth_factor = 5.0
        
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
            
            # Configurar failsafe (snippet usuario: False para evitar interrupciones)
            self.pyautogui.FAILSAFE = False
            
            self.is_available = True
            logger.debug("✅ Módulo 'pyautogui' cargado para NYX")
        except ImportError as e:
            logger.error(f"❌ NYX: No se pudo cargar módulo 'pyautogui': {e}")
            self.is_available = False
        except Exception as e:
            logger.error(f"❌ NYX: Error inicializando mouse: {e}")
            self.is_available = False
    
    def execute(self, command_or_data: Union[str, Dict], action_data: Dict = None) -> Dict[str, Any]:
        """
        Ejecuta un comando de mouse desde NYX.
        
        Args:
            command_or_data: Comando string O dict completo (para compatibilidad)
            action_data: Datos adicionales de la acción (incluyendo gesture_data)
        
        Returns:
            Resultado de la ejecución
        """
        if not self.is_available:
            error_msg = "Módulo de mouse no disponible"
            logger.error(f"❌ NYX: {error_msg}")
            return self._format_result(False, error=error_msg)
        
        # Compatibilidad: si se pasa un dict como primer arg, usarlo directamente
        if isinstance(command_or_data, dict):
            command_data = command_or_data
        else:
            # Modo nuevo: command string + action_data dict
            command_data = action_data.copy() if action_data else {}
            command_data['command'] = command_or_data
        
        command = command_data.get('command', 'click')
        description = command_data.get('description', 'Comando de mouse')
        
        logger.info(f"🎮 NYX ejecutando mouse: {description} (gesture_data present: {bool(command_data.get('gesture_data'))})")
        
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
            elif command == 'drag_start':
                success = self._execute_drag_start(command_data)
            elif command == 'drag_end':
                success = self._execute_drag_end(command_data)
            elif command == 'gesture':
                success = self._execute_gesture(command_data) # Fixed dup
            elif command == 'scroll_mode':
                success = self._execute_scroll_mode(command_data)
            # --- New commands for gamer profile ---
            elif command == 'scroll_up':
                command_data['amount'] = self.nyx_config.scroll_amount
                success = self._execute_scroll(command_data)
            elif command == 'scroll_down':
                command_data['amount'] = -self.nyx_config.scroll_amount
                success = self._execute_scroll(command_data)
            elif command == 'right_click':
                command_data['button'] = 'right'
                success = self._execute_click(command_data)
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
        
        # Verificar si hay datos de cursor desde el gesto
        gesture_data = data.get('gesture_data', {})
        cursor_pos = gesture_data.get('cursor')
        
        if cursor_pos and self.pyautogui:
            # Mapeo directo de coordenadas normalizadas a pantalla
            screen_w, screen_h = self.pyautogui.size()
            x = int(cursor_pos.get('x', 0) * screen_w)
            y = int(cursor_pos.get('y', 0) * screen_h)
            logger.debug(f"🖱️ Click track: {x}, {y}")
        elif x is not None and y is not None:
            # Aplicar sensibilidad de NYX solo a deltas manuales
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
        
        logger.info(f"🔍 _execute_move called: gesture_data={bool(gesture_data)}, cursor_pos={cursor_pos}")
        
        if cursor_pos and self.pyautogui:
            # Mapeo directo de coordenadas normalizadas a pantalla
            screen_w, screen_h = self.pyautogui.size()
            x = int(cursor_pos.get('x', 0) * screen_w)
            y = int(cursor_pos.get('y', 0) * screen_h)
            
            logger.info(f"🎯 Cursor mapping: norm({cursor_pos.get('x', 0):.3f}, {cursor_pos.get('y', 0):.3f}) -> screen({x}, {y})")
            
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
            
            if self.nyx_config.smooth_movement:
                # Smoothing exponencial (Snippet Usuario)
                final_x = self.prev_x + (x - self.prev_x) / self.smooth_factor
                final_y = self.prev_y + (y - self.prev_y) / self.smooth_factor
                
                self.pyautogui.moveTo(final_x, final_y)
                self.prev_x, self.prev_y = final_x, final_y
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
        # Preferir scroll_amount del gesto si existe (proviene del HandInterpreter refined logic)
        amount = data.get('scroll_amount')
        
        if amount is None:
            amount = data.get('amount', self.nyx_config.scroll_amount)
            direction = data.get('direction', 'up')
            if direction == 'down':
                amount = -amount
        
        try:
            self.pyautogui.scroll(amount)
            self.stats['total_scrolls'] += 1
            
            logger.info(f"🖱️ NYX: Scroll {amount} unidades")
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
            
    def _execute_drag_start(self, data: Dict) -> bool:
        """Inicia un arrastre (mantiene presionado)."""
        button = data.get('button', 'left')
        try:
            self.pyautogui.mouseDown(button=button)
            self.is_dragging = True
            logger.debug(f"🖱️ NYX: Arrastre iniciado ({button})")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error iniciando arrastre: {e}")
            return False

    def _execute_drag_end(self, data: Dict) -> bool:
        """Finaliza un arrastre (suelta el botón)."""
        button = data.get('button', 'left')
        try:
            self.pyautogui.mouseUp(button=button)
            self.is_dragging = False
            logger.debug(f"🖱️ NYX: Arrastre finalizado ({button})")
            return True
        except Exception as e:
            logger.error(f"❌ NYX: Error finalizando arrastre: {e}")
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
    
    def process_direct_hand(self, landmarks: List[Dict], frame_w: int, frame_h: int):
        """
        Procesa landmarks directamente usando la lógica simple pero EFECTIVA.
        Bypassea el sistema de acciones tradicional para máximos FPS y fluidez.
        """
        if not self.is_available or not landmarks or len(landmarks) < 21:
            return

        try:
            # Obtener landmarks clave (formato dict de HandDetector)
            index_f  = landmarks[8]
            middle_f = landmarks[12]
            thumb_f  = landmarks[4]
            ring_f   = landmarks[16]
            pinky_f  = landmarks[20]
            
            # Coordenadas en píxeles (ya calculadas por HandDetector)
            ix, iy = index_f['x'], index_f['y']
            mx, my = middle_f['x'], middle_f['y']
            tx, ty = thumb_f['x'], thumb_f['y']
            rx, ry = ring_f['x'], ring_f['y']
            px, py = pinky_f['x'], pinky_f['y']
            
            # Calcular distancias
            d_it = np.hypot(ix - tx, iy - ty)
            d_mt = np.hypot(mx - tx, my - ty)
            
            # Configuración de NYX
            sensitivity = self.nyx_config.sensitivity
            smooth = self.smooth_factor if self.nyx_config.smooth_movement else 1.0
            
            # --- LÓGICA DE ALCANCE (REACH) MEJORADA ---
            # Queremos que con poco movimiento de la mano el mouse llegue lejos.
            # reach_multiplier base de 1.0 (mapeo directo) hasta 4.0 (amplificación fuerte)
            # Esto soluciona la necesidad de "estirarse" físicamente.
            reach_multiplier = 1.0 + (sensitivity * 3.0) 
            
            # Normalización cruda (0 a 1)
            raw_x = ix / frame_w
            raw_y = iy / frame_h
            
            # Escalamiento centrado: (valor - centro) * multiplicador + centro
            # Esto expande el centro de la cámara hacia los bordes de la pantalla.
            norm_x = (raw_x - 0.5) * reach_multiplier + 0.5
            norm_y = (raw_y - 0.5) * reach_multiplier + 0.5
            
            # Limitar a [0, 1] y mapear a pantalla
            norm_x = max(0.0, min(1.0, norm_x))
            norm_y = max(0.0, min(1.0, norm_y))
            
            screen_w, screen_h = self.pyautogui.size()
            target_x = int(norm_x * screen_w)
            target_y = int(norm_y * screen_h)
            
            # Estados de dedos
            ring_down  = ry > iy
            pinky_down = py > iy
            middle_down = my > iy
            
            # --------- HYSTERESIS STATE FOR PINCH ---------
            # Define thresholds
            PINCH_START_THRESH = 65    # Más fácil (era 35)
            PINCH_RELEASE_THRESH = 95  # Más seguro (era 60)
            
            # Determine current pinch state based on hysteresis
            current_distance = d_it
            is_pinching = False
            
            if self.is_dragging: # If already dragging/pinching, use relaxed threshold
                is_pinching = current_distance < PINCH_RELEASE_THRESH
            else: # If starting, use strict threshold
                is_pinching = current_distance < PINCH_START_THRESH
            
            
            # --------- MOVER (ÍNDICE + PULGAR EN L) O DRAG ---------
            # Move if Pointing (d_it > 60) OR Dragging (is_pinch and is_dragging)
            should_move = False
            
            if d_it > 60 and ring_down and pinky_down and middle_down:
                 should_move = True
            elif self.is_dragging: # Allow movement while dragging!
                 should_move = True
            
            if should_move:
                # Suavizado suave
                final_x = self.prev_x + (target_x - self.prev_x) / smooth
                final_y = self.prev_y + (target_y - self.prev_y) / smooth
                
                self.pyautogui.moveTo(int(final_x), int(final_y))
                self.prev_x, self.prev_y = final_x, final_y
                
                # Actualizar posición actual
                self.current_position = (int(final_x), int(final_y))
                self.stats['total_movements'] += 1
                
                self.stats['total_movements'] += 1
                
            # --------- LOGICA UNIFICADA CLICK / DRAG (Pellizco) ---------
            # Usar is_pinching calculado con hysteresis
            
            if is_pinching and ring_down and pinky_down:
                if self.pinch_start_time is None:
                    # Iniciar cronómetro de pellizco
                    self.pinch_start_time = time.time()
                
                # Calcular duración
                pinch_duration = time.time() - self.pinch_start_time
                
                # Si dura más de 0.4s, es DRAG
                if pinch_duration > 0.4:
                    if not self.is_dragging:
                        self.is_dragging = True
                        self.pyautogui.mouseDown()
                        self.stats['total_drags'] += 1
                        logger.info("🖱️ NYX DIRECT: DRAG START (Hold)")
            
            else:
                # Si soltamos el pellizco
                if self.pinch_start_time is not None:
                    pinch_duration = time.time() - self.pinch_start_time
                    
                    if self.is_dragging:
                        # Si estaba arrastrando, soltar
                        self.is_dragging = False
                        self.pyautogui.mouseUp()
                        logger.info("🖱️ NYX DIRECT: DRAG END")
                    elif pinch_duration > 0.02: # Filtro de ruido muy corto (reduced from 0.05)
                        # Si fue corto (< 0.4s) y no arrastramos -> CLIC
                        # Verificar cooldown de clic
                        now = time.time()
                        if now - self.last_gesture_time > 0.2: # Reduced cooldown from 0.3
                            self.pyautogui.click()
                            self.last_gesture_time = now
                            self.stats['total_clicks'] += 1
                            logger.info("🖱️ NYX DIRECT: CLICK LEFT (Tap)")
                    
                    self.pinch_start_time = None
            
        except Exception as e:
            logger.debug(f"Error en process_direct_hand: {e}")

    def cleanup(self):
        """Limpia recursos para NYX."""
        if self.is_dragging:
            try:
                self.pyautogui.mouseUp()
                self.is_dragging = False
            except:
                pass
        
        logger.info("✅ MouseController limpiado para NYX")

    def _execute_scroll_mode(self, data: Dict) -> bool:
        """
        Ejecuta modo scroll basado en movimiento vertical del puño (Agarre).
        """
        gesture_data = data.get('gesture_data', {})
        cursor_pos = gesture_data.get('cursor') # {x: 0..1, y: 0..1}
        
        if not cursor_pos:
            return False
            
        y = cursor_pos.get('y', 0.5)
        
        # Si es el primer frame del gesto, guardar posición inicial
        if not hasattr(self, 'scroll_last_y') or self.scroll_last_y is None:
            self.scroll_last_y = y
            self.scroll_accum = 0
            logger.debug("🖱️ Scroll Mode Started")
            return True
            
        # Calcular delta
        dy = y - self.scroll_last_y
        self.scroll_last_y = y
        
        # Umbral de movimiento para scroll
        threshold = 0.005 # 0.5% movimiento muy sensible
        multiplier = 200 # Velocidad ajustada
        
        if abs(dy) > threshold:
            # Scroll natural: Mover mano arriba (dy < 0) -> Sube contenido (Scroll Up -> +amount)
            # Mover mano abajo (dy > 0) -> Baja contenido (Scroll Down -> -amount)
            # dy es y_new - y_old. 
            # Si subo la mano, y disminuye -> dy negativo.
            # Scroll Up es positivo.
            amount = int(dy * multiplier * -1)
            
            # Simple check
            if abs(amount) > 0:
                self.pyautogui.scroll(amount)
                return True
                
        return True