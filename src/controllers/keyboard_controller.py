"""
⌨️ KEYBOARD CONTROLLER - Control de Teclado
==========================================
Simula pulsaciones de teclado y combinaciones de teclas.
Usa el módulo 'keyboard' para control del teclado a nivel de sistema.
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class KeyboardController:
    """Controlador de teclado."""
    
    def __init__(self):
        """Inicializa el controlador de teclado."""
        self.keyboard_module = None
        self.is_available = False
        
        # Configuración
        self.default_press_time = 0.1  # segundos
        self.default_delay = 0.05      # segundos entre teclas
        self.hold_keys = {}           # Teclas actualmente presionadas
        
        # Para macros y combinaciones complejas
        self.macros = {}
        self.macro_thread = None
        self.is_macro_running = False
        
        # Estadísticas
        self.stats = {
            'key_presses': 0,
            'key_combinations': 0,
            'macros_executed': 0,
            'errors': 0
        }
        
        # Inicializar módulo
        self._init_keyboard_module()
        
        logger.info(f"✅ KeyboardController inicializado (disponible: {self.is_available})")
    
    def _init_keyboard_module(self):
        """Inicializa el módulo de teclado."""
        try:
            import keyboard as kb
            self.keyboard_module = kb
            self.is_available = True
            logger.info("✅ Módulo 'keyboard' cargado correctamente")
        except ImportError as e:
            logger.error(f"❌ No se pudo importar módulo 'keyboard': {e}")
            self.is_available = False
        except Exception as e:
            logger.error(f"❌ Error inicializando teclado: {e}")
            self.is_available = False
    
    def press_key(self, key: str, press_time: float = None) -> bool:
        """
        Presiona y suelta una tecla individual.
        
        Args:
            key: Tecla a presionar (ej: 'a', 'enter', 'f1')
            press_time: Tiempo para mantener presionada (segundos)
            
        Returns:
            True si se ejecutó correctamente
        """
        if not self.is_available or not self.keyboard_module:
            logger.error("❌ Módulo de teclado no disponible")
            return False
        
        try:
            if press_time is None:
                press_time = self.default_press_time
            
            logger.debug(f"⌨️  Presionando tecla: '{key}' por {press_time:.2f}s")
            
            # Presionar y soltar con tiempo
            self.keyboard_module.press(key)
            time.sleep(press_time)
            self.keyboard_module.release(key)
            
            self.stats['key_presses'] += 1
            return True
            
        except ValueError as e:
            logger.error(f"❌ Tecla inválida '{key}': {e}")
            self.stats['errors'] += 1
            return False
        except Exception as e:
            logger.error(f"❌ Error presionando tecla '{key}': {e}")
            self.stats['errors'] += 1
            return False
    
    def press_combination(self, keys: List[str], delay: float = None) -> bool:
        """
        Presiona una combinación de teclas (ej: Ctrl+Alt+Delete).
        
        Args:
            keys: Lista de teclas en orden (modificadoras primero)
            delay: Retardo entre teclas (segundos)
            
        Returns:
            True si se ejecutó correctamente
        """
        if not self.is_available or not self.keyboard_module:
            logger.error("❌ Módulo de teclado no disponible")
            return False
        
        if not keys:
            logger.warning("⚠️ Lista de teclas vacía")
            return False
        
        try:
            if delay is None:
                delay = self.default_delay
            
            keys_str = '+'.join(keys)
            logger.debug(f"⌨️  Presionando combinación: {keys_str}")
            
            # Presionar teclas modificadoras
            for key in keys[:-1]:
                self.keyboard_module.press(key)
                time.sleep(delay)
            
            # Presionar y soltar tecla principal
            self.keyboard_module.press_and_release(keys[-1])
            time.sleep(delay)
            
            # Soltar teclas modificadoras en orden inverso
            for key in reversed(keys[:-1]):
                self.keyboard_module.release(key)
                time.sleep(delay)
            
            self.stats['key_combinations'] += 1
            return True
            
        except ValueError as e:
            logger.error(f"❌ Tecla inválida en combinación: {e}")
            self.stats['errors'] += 1
            return False
        except Exception as e:
            logger.error(f"❌ Error en combinación {keys}: {e}")
            self.stats['errors'] += 1
            return False
    
    def type_text(self, text: str, delay: float = 0.01) -> bool:
        """
        Escribe texto caracter por caracter.
        
        Args:
            text: Texto a escribir
            delay: Retardo entre caracteres (segundos)
            
        Returns:
            True si se ejecutó correctamente
        """
        if not self.is_available or not self.keyboard_module:
            logger.error("❌ Módulo de teclado no disponible")
            return False
        
        try:
            logger.debug(f"⌨️  Escribiendo texto: '{text[:50]}...'")
            
            for char in text:
                if char == '\n':
                    self.press_key('enter')
                elif char == '\t':
                    self.press_key('tab')
                else:
                    self.keyboard_module.write(char)
                    time.sleep(delay)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error escribiendo texto: {e}")
            self.stats['errors'] += 1
            return False
    
    def hold_key(self, key: str, duration: float = None) -> bool:
        """
        Mantiene una tecla presionada por un tiempo.
        
        Args:
            key: Tecla a mantener presionada
            duration: Duración en segundos (None = indefinido)
            
        Returns:
            True si se ejecutó correctamente
        """
        if not self.is_available or not self.keyboard_module:
            logger.error("❌ Módulo de teclado no disponible")
            return False
        
        try:
            if key in self.hold_keys:
                logger.warning(f"⚠️ Tecla '{key}' ya está siendo mantenida")
                return False
            
            logger.debug(f"⌨️  Manteniendo tecla: '{key}'")
            self.keyboard_module.press(key)
            self.hold_keys[key] = time.time()
            
            if duration is not None:
                # Liberar después de la duración
                threading.Timer(duration, self.release_key, args=[key]).start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error manteniendo tecla '{key}': {e}")
            self.stats['errors'] += 1
            return False
    
    def release_key(self, key: str) -> bool:
        """
        Libera una tecla que estaba siendo mantenida.
        
        Args:
            key: Tecla a liberar
            
        Returns:
            True si se liberó correctamente
        """
        if not self.is_available or not self.keyboard_module:
            logger.error("❌ Módulo de teclado no disponible")
            return False
        
        try:
            if key not in self.hold_keys:
                logger.warning(f"⚠️ Tecla '{key}' no estaba siendo mantenida")
                return False
            
            logger.debug(f"⌨️  Liberando tecla: '{key}'")
            self.keyboard_module.release(key)
            self.hold_keys.pop(key, None)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error liberando tecla '{key}': {e}")
            self.stats['errors'] += 1
            return False
    
    def release_all_keys(self) -> bool:
        """
        Libera todas las teclas que están siendo mantenidas.
        
        Returns:
            True si se liberaron todas correctamente
        """
        if not self.hold_keys:
            return True
        
        success = True
        keys_to_release = list(self.hold_keys.keys())
        
        for key in keys_to_release:
            if not self.release_key(key):
                success = False
        
        return success
    
    def add_macro(self, name: str, sequence: List[Dict]) -> bool:
        """
        Agrega una macro (secuencia de acciones de teclado).
        
        Args:
            name: Nombre de la macro
            sequence: Lista de acciones
                Ej: [{'type': 'press', 'key': 'ctrl', 'delay': 0.1},
                     {'type': 'press', 'key': 'c', 'delay': 0.1},
                     {'type': 'release', 'key': 'ctrl'}]
            
        Returns:
            True si se agregó correctamente
        """
        if not sequence:
            logger.warning("⚠️ Secuencia de macro vacía")
            return False
        
        self.macros[name] = sequence
        logger.debug(f"✅ Macro agregada: '{name}' con {len(sequence)} acciones")
        return True
    
    def execute_macro(self, name: str, wait: bool = True) -> bool:
        """
        Ejecuta una macro predefinida.
        
        Args:
            name: Nombre de la macro
            wait: Esperar a que termine la ejecución
            
        Returns:
            True si se ejecutó correctamente
        """
        if name not in self.macros:
            logger.error(f"❌ Macro '{name}' no encontrada")
            return False
        
        if self.is_macro_running:
            logger.warning("⚠️ Ya hay una macro en ejecución")
            return False
        
        def run_macro():
            self.is_macro_running = True
            sequence = self.macros[name]
            
            try:
                logger.info(f"🎬 Ejecutando macro: '{name}'")
                
                for action in sequence:
                    action_type = action.get('type', 'press')
                    
                    if action_type == 'press':
                        key = action.get('key')
                        delay = action.get('delay', self.default_delay)
                        press_time = action.get('press_time', self.default_press_time)
                        
                        if key:
                            if action.get('hold', False):
                                self.hold_key(key)
                            else:
                                self.press_key(key, press_time)
                        
                    elif action_type == 'release':
                        key = action.get('key')
                        if key:
                            self.release_key(key)
                    
                    elif action_type == 'type':
                        text = action.get('text', '')
                        delay = action.get('delay', 0.01)
                        if text:
                            self.type_text(text, delay)
                    
                    # Esperar delay si se especificó
                    action_delay = action.get('delay', 0)
                    if action_delay > 0:
                        time.sleep(action_delay)
                
                self.stats['macros_executed'] += 1
                logger.info(f"✅ Macro '{name}' ejecutada exitosamente")
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando macro '{name}': {e}")
                self.stats['errors'] += 1
            finally:
                self.is_macro_running = False
        
        # Ejecutar en hilo separado si no hay que esperar
        if wait:
            run_macro()
        else:
            self.macro_thread = threading.Thread(target=run_macro, daemon=True)
            self.macro_thread.start()
        
        return True
    
    def parse_key_command(self, command_str: str) -> Optional[List[str]]:
        """
        Parsea un string de comando en lista de teclas.
        
        Args:
            command_str: String como "ctrl+alt+delete" o "f11"
            
        Returns:
            Lista de teclas o None si hay error
        """
        if not command_str:
            return None
        
        # Separar por '+' y limpiar
        keys = [k.strip().lower() for k in command_str.split('+')]
        
        # Validar teclas básicas
        valid_keys = {
            # Teclas especiales
            'alt', 'ctrl', 'shift', 'win', 'cmd', 'command',
            # Funciones
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            # Navegación
            'esc', 'enter', 'tab', 'backspace', 'delete', 'insert', 'home', 'end',
            'pageup', 'pagedown', 'up', 'down', 'left', 'right',
            # Bloques
            'capslock', 'numlock', 'scrolllock',
            # Multimedia
            'volumemute', 'volumedown', 'volumeup', 'nexttrack', 'prevtrack',
            'playpause', 'stop', 'mediastop'
        }
        
        # Verificar teclas válidas
        for key in keys:
            # Permitir letras, números y teclas especiales conocidas
            if (len(key) == 1 and key.isalnum()) or key in valid_keys:
                continue
            
            # Teclas con nombres alternativos
            aliases = {
                'escape': 'esc',
                'return': 'enter',
                'del': 'delete',
                'ins': 'insert',
                'pgup': 'pageup',
                'pgdn': 'pagedown',
                'space': 'space',
                ' ': 'space'
            }
            
            if key in aliases:
                keys[keys.index(key)] = aliases[key]
            else:
                logger.warning(f"⚠️ Tecla desconocida: '{key}'")
                return None
        
        return keys
    
    def execute_command(self, command: Dict) -> bool:
        """
        Ejecuta un comando de teclado desde el formato estandarizado.
        
        Args:
            command: Diccionario con comando
                Formato: {
                    'type': 'keyboard',
                    'command': 'press' | 'combination' | 'type' | 'macro' | 'hold' | 'release',
                    'key': 'tecla' (para press/hold/release),
                    'keys': ['ctrl', 'c'] (para combination),
                    'text': 'texto' (para type),
                    'macro': 'nombre' (para macro),
                    'press_time': 0.1,
                    'delay': 0.05,
                    'duration': 1.0 (para hold)
                }
            
        Returns:
            True si se ejecutó correctamente
        """
        cmd_type = command.get('command', 'press')
        
        try:
            if cmd_type == 'press':
                key = command.get('key')
                press_time = command.get('press_time')
                return self.press_key(key, press_time)
            
            elif cmd_type == 'combination':
                keys = command.get('keys', [])
                delay = command.get('delay')
                return self.press_combination(keys, delay)
            
            elif cmd_type == 'type':
                text = command.get('text', '')
                delay = command.get('delay', 0.01)
                return self.type_text(text, delay)
            
            elif cmd_type == 'macro':
                macro_name = command.get('macro')
                wait = command.get('wait', True)
                return self.execute_macro(macro_name, wait)
            
            elif cmd_type == 'hold':
                key = command.get('key')
                duration = command.get('duration')
                return self.hold_key(key, duration)
            
            elif cmd_type == 'release':
                key = command.get('key')
                if key == 'all':
                    return self.release_all_keys()
                else:
                    return self.release_key(key)
            
            else:
                logger.error(f"❌ Tipo de comando desconocido: {cmd_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error ejecutando comando {cmd_type}: {e}")
            self.stats['errors'] += 1
            return False
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del controlador."""
        return {
            'available': self.is_available,
            'stats': self.stats.copy(),
            'macros_count': len(self.macros),
            'keys_held': len(self.hold_keys),
            'is_macro_running': self.is_macro_running
        }
    
    def get_available_keys(self) -> List[str]:
        """
        Obtiene lista de teclas disponibles.
        
        Returns:
            Lista de nombres de teclas
        """
        # Lista básica de teclas soportadas
        keys = [
            # Letras
            *[chr(i) for i in range(ord('a'), ord('z') + 1)],
            # Números
            *[str(i) for i in range(10)],
            # Teclas especiales
            'alt', 'ctrl', 'shift', 'win', 'cmd',
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'esc', 'enter', 'tab', 'backspace', 'delete', 'insert', 'home', 'end',
            'pageup', 'pagedown', 'up', 'down', 'left', 'right',
            'capslock', 'numlock', 'scrolllock',
            'space', 'printscreen', 'pause'
        ]
        
        return keys
    
    def cleanup(self):
        """Limpia recursos y libera teclas."""
        self.release_all_keys()
        
        if self.macro_thread and self.macro_thread.is_alive():
            self.macro_thread.join(timeout=1)
        
        logger.info("✅ KeyboardController limpiado")