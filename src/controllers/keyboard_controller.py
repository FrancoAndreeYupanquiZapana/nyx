"""
⌨️ KEYBOARD CONTROLLER - Controlador de teclado para NYX
=========================================================
Simula pulsaciones de teclado para ejecutar acciones del sistema.
Versión integrada con todos los métodos de la especificación original.
"""

import time
import logging
from typing import Dict, Any, Optional, List
import threading

logger = logging.getLogger(__name__)


class KeyboardController:
    """Controlador de teclado para NYX."""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el controlador de teclado.
        
        Args:
            config: Configuración del controlador
        """
        self.config = config or {}
        self.is_running = True
        
        # Configuración
        self.key_delay = self.config.get('key_delay', 0.1)
        self.default_press_time = self.config.get('default_press_time', 0.1)
        self.default_delay = self.config.get('default_delay', 0.05)
        
        # Historial de acciones
        self.action_history = []
        self.max_history = 50
        
        # Estado
        self.hold_keys = {}  # Teclas actualmente presionadas
        self.macros = {}     # Macros definidas
        self.is_macro_running = False
        self.keyboard_module = None
        
        # Estadísticas
        self.stats = {
            'key_presses': 0,
            'key_combinations': 0,
            'macros_executed': 0,
            'errors': 0
        }
        
        # Inicializar módulo de teclado
        self._init_keyboard_module()
        
        logger.info("✅ KeyboardController inicializado")
    
    def _init_keyboard_module(self):
        """Inicializa el módulo de teclado."""
        try:
            # Intentar diferentes módulos
            try:
                import keyboard as kb
                self.keyboard_module = kb
                logger.info("✅ Módulo 'keyboard' cargado correctamente")
                return
            except ImportError:
                pass
            
            try:
                import pyautogui
                self.keyboard_module = 'pyautogui'
                logger.info("✅ Módulo 'pyautogui' cargado correctamente")
                return
            except ImportError:
                pass
            
            # Verificar xdotool en Linux
            try:
                import subprocess
                subprocess.run(['which', 'xdotool'], capture_output=True, check=False)
                self.keyboard_module = 'xdotool'
                logger.info("✅ xdotool disponible en sistema")
                return
            except Exception:
                pass
            
            logger.warning("⚠️ No se encontraron módulos de teclado, usando simulación básica")
            self.keyboard_module = 'simulation'
            
        except Exception as e:
            logger.error(f"❌ Error inicializando teclado: {e}")
            self.keyboard_module = 'simulation'
    
    def press_key(self, key_combination: str, press_time: float = None) -> Dict[str, Any]:
        """
        Presiona una combinación de teclas.
        
        Args:
            key_combination: Combinación de teclas (ej: "ctrl+f", "alt+tab")
            press_time: Tiempo para mantener presionada (segundos)
            
        Returns:
            Resultado de la acción
        """
        try:
            # Limpiar y normalizar combinación
            keys = self._parse_key_combination(key_combination)
            
            logger.info(f"⌨️ Presionando teclas: {key_combination}")
            
            # Ejecutar según el método disponible
            if len(keys) == 1:
                # Tecla individual
                result = self._execute_single_key(keys[0], press_time)
            else:
                # Combinación de teclas
                result = self._execute_key_combination(keys)
            
            # Agregar al historial
            self.action_history.append({
                'type': 'keyboard',
                'command': 'press_key',
                'keys': key_combination,
                'result': result,
                'timestamp': time.time()
            })
            
            if len(self.action_history) > self.max_history:
                self.action_history.pop(0)
            
            # Actualizar estadísticas
            self.stats['key_presses'] += 1 if len(keys) == 1 else 0
            self.stats['key_combinations'] += 1 if len(keys) > 1 else 0
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': key_combination,
                'message': f'Teclas presionadas: {key_combination}',
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"❌ Error presionando teclas {key_combination}: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': key_combination,
                'error': str(e)
            }
    
    def _execute_single_key(self, key: str, press_time: float = None) -> bool:
        """Ejecuta una tecla individual."""
        if press_time is None:
            press_time = self.default_press_time
        
        try:
            if self.keyboard_module == 'keyboard':
                import keyboard
                keyboard.press(key)
                time.sleep(press_time)
                keyboard.release(key)
            elif self.keyboard_module == 'pyautogui':
                import pyautogui
                pyautogui.keyDown(key)
                time.sleep(press_time)
                pyautogui.keyUp(key)
            elif self.keyboard_module == 'xdotool':
                import subprocess
                subprocess.run(['xdotool', 'key', key], check=False)
                time.sleep(press_time)
            else:
                # Simulación
                logger.debug(f"  Simulando tecla: {key} por {press_time}s")
                time.sleep(press_time)
            
            time.sleep(self.key_delay)
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando tecla {key}: {e}")
            return False
    
    def _execute_key_combination(self, keys: List[str]) -> bool:
        """Ejecuta una combinación de teclas."""
        try:
            if self.keyboard_module == 'keyboard':
                import keyboard
                for key in keys[:-1]:
                    keyboard.press(key)
                    time.sleep(self.default_delay)
                
                keyboard.press_and_release(keys[-1])
                time.sleep(self.default_delay)
                
                for key in reversed(keys[:-1]):
                    keyboard.release(key)
                    time.sleep(self.default_delay)
                    
            elif self.keyboard_module == 'pyautogui':
                import pyautogui
                pyautogui.hotkey(*keys)
                
            elif self.keyboard_module == 'xdotool':
                import subprocess
                key_str = '+'.join(keys)
                subprocess.run(['xdotool', 'key', key_str], check=False)
            else:
                # Simulación
                key_str = '+'.join(keys)
                logger.debug(f"  Simulando combinación: {key_str}")
            
            time.sleep(self.key_delay)
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando combinación {keys}: {e}")
            return False
    
    def type_text(self, text: str, delay: float = None) -> Dict[str, Any]:
        """
        Escribe texto caracter por caracter.
        
        Args:
            text: Texto a escribir
            delay: Retardo entre caracteres
            
        Returns:
            Resultado de la acción
        """
        try:
            if delay is None:
                delay = 0.01
            
            logger.info(f"⌨️ Escribiendo texto: '{text[:50]}...'")
            
            # Ejecutar según método disponible
            if self.keyboard_module == 'keyboard':
                import keyboard
                keyboard.write(text)
                
            elif self.keyboard_module == 'pyautogui':
                import pyautogui
                pyautogui.write(text, interval=delay)
                
            elif self.keyboard_module == 'xdotool':
                import subprocess
                # Escapar texto para xdotool
                text_escaped = text.replace('"', '\\"')
                subprocess.run(['xdotool', 'type', text_escaped], check=False)
            else:
                # Simulación
                logger.debug(f"  Simulando escritura: {len(text)} caracteres")
                time.sleep(len(text) * delay)
            
            # Agregar al historial
            self.action_history.append({
                'type': 'keyboard',
                'command': 'type_text',
                'text_preview': text[:50],
                'length': len(text),
                'timestamp': time.time()
            })
            
            if len(self.action_history) > self.max_history:
                self.action_history.pop(0)
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': 'type_text',
                'message': f'Texto escrito ({len(text)} caracteres)'
            }
            
        except Exception as e:
            logger.error(f"❌ Error escribiendo texto: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'type_text',
                'error': str(e)
            }
    
    def hold_key(self, key: str, duration: float = None) -> Dict[str, Any]:
        """
        Mantiene una tecla presionada.
        
        Args:
            key: Tecla a mantener presionada
            duration: Duración en segundos (None = indefinido)
            
        Returns:
            Resultado de la acción
        """
        try:
            logger.info(f"⌨️ Manteniendo tecla: '{key}'")
            
            if key in self.hold_keys:
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': 'hold_key',
                    'message': f'Tecla {key} ya está siendo mantenida'
                }
            
            # Presionar tecla
            if self.keyboard_module == 'keyboard':
                import keyboard
                keyboard.press(key)
            elif self.keyboard_module == 'pyautogui':
                import pyautogui
                pyautogui.keyDown(key)
            elif self.keyboard_module == 'xdotool':
                import subprocess
                subprocess.run(['xdotool', 'keydown', key], check=False)
            else:
                logger.debug(f"  Simulando mantener tecla: {key}")
            
            # Registrar tecla mantenida
            self.hold_keys[key] = time.time()
            
            # Liberar después de duración si se especifica
            if duration is not None:
                threading.Timer(duration, self._release_held_key, args=[key]).start()
            
            # Agregar al historial
            self.action_history.append({
                'type': 'keyboard',
                'command': 'hold_key',
                'key': key,
                'duration': duration,
                'timestamp': time.time()
            })
            
            if len(self.action_history) > self.max_history:
                self.action_history.pop(0)
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': 'hold_key',
                'message': f'Tecla {key} mantenida' + 
                          (f' por {duration}s' if duration else ' indefinidamente')
            }
            
        except Exception as e:
            logger.error(f"❌ Error manteniendo tecla {key}: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'hold_key',
                'error': str(e)
            }
    
    def _release_held_key(self, key: str):
        """Libera una tecla mantenida (para uso interno)."""
        self.release_key(key)
    
    def release_key(self, key: str) -> Dict[str, Any]:
        """
        Libera una tecla mantenida.
        
        Args:
            key: Tecla a liberar (o 'all' para todas)
            
        Returns:
            Resultado de la acción
        """
        try:
            if key == 'all':
                return self.release_all_keys()
            
            if key not in self.hold_keys:
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': 'release_key',
                    'message': f'Tecla {key} no estaba siendo mantenida'
                }
            
            logger.info(f"⌨️ Liberando tecla: '{key}'")
            
            # Liberar tecla
            if self.keyboard_module == 'keyboard':
                import keyboard
                keyboard.release(key)
            elif self.keyboard_module == 'pyautogui':
                import pyautogui
                pyautogui.keyUp(key)
            elif self.keyboard_module == 'xdotool':
                import subprocess
                subprocess.run(['xdotool', 'keyup', key], check=False)
            else:
                logger.debug(f"  Simulando liberar tecla: {key}")
            
            # Remover del registro
            self.hold_keys.pop(key, None)
            
            # Agregar al historial
            self.action_history.append({
                'type': 'keyboard',
                'command': 'release_key',
                'key': key,
                'timestamp': time.time()
            })
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': 'release_key',
                'message': f'Tecla {key} liberada'
            }
            
        except Exception as e:
            logger.error(f"❌ Error liberando tecla {key}: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'release_key',
                'error': str(e)
            }
    
    def release_all_keys(self) -> Dict[str, Any]:
        """
        Libera todas las teclas mantenidas.
        
        Returns:
            Resultado de la acción
        """
        try:
            if not self.hold_keys:
                return {
                    'success': True,
                    'action': 'keyboard',
                    'command': 'release_all_keys',
                    'message': 'No hay teclas mantenidas'
                }
            
            logger.info(f"⌨️ Liberando {len(self.hold_keys)} teclas")
            keys_to_release = list(self.hold_keys.keys())
            success_count = 0
            
            for key in keys_to_release:
                result = self.release_key(key)
                if result.get('success', False):
                    success_count += 1
            
            return {
                'success': success_count == len(keys_to_release),
                'action': 'keyboard',
                'command': 'release_all_keys',
                'message': f'Liberadas {success_count}/{len(keys_to_release)} teclas'
            }
            
        except Exception as e:
            logger.error(f"❌ Error liberando todas las teclas: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'release_all_keys',
                'error': str(e)
            }
    
    def add_macro(self, name: str, sequence: List[Dict]) -> Dict[str, Any]:
        """
        Agrega una macro.
        
        Args:
            name: Nombre de la macro
            sequence: Secuencia de acciones
            
        Returns:
            Resultado de la acción
        """
        try:
            if not sequence:
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': 'add_macro',
                    'message': 'Secuencia vacía'
                }
            
            self.macros[name] = sequence
            logger.info(f"✅ Macro '{name}' agregada con {len(sequence)} acciones")
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': 'add_macro',
                'message': f'Macro {name} agregada',
                'actions_count': len(sequence)
            }
            
        except Exception as e:
            logger.error(f"❌ Error agregando macro {name}: {e}")
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'add_macro',
                'error': str(e)
            }
    
    def execute_macro(self, name: str, wait: bool = True) -> Dict[str, Any]:
        """
        Ejecuta una macro.
        
        Args:
            name: Nombre de la macro
            wait: Esperar a que termine
            
        Returns:
            Resultado de la acción
        """
        try:
            if name not in self.macros:
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': 'execute_macro',
                    'message': f'Macro {name} no encontrada'
                }
            
            if self.is_macro_running:
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': 'execute_macro',
                    'message': 'Ya hay una macro en ejecución'
                }
            
            def run_macro():
                self.is_macro_running = True
                sequence = self.macros[name]
                
                try:
                    logger.info(f"🎬 Ejecutando macro: '{name}'")
                    
                    for action in sequence:
                        action_type = action.get('type', 'press')
                        
                        if action_type == 'press':
                            key = action.get('key')
                            press_time = action.get('press_time', self.default_press_time)
                            if key:
                                self.press_key(key, press_time)
                        
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
            
            # Ejecutar macro
            if wait:
                run_macro()
            else:
                thread = threading.Thread(target=run_macro, daemon=True)
                thread.start()
            
            return {
                'success': True,
                'action': 'keyboard',
                'command': 'execute_macro',
                'message': f'Macro {name} ejecutada',
                'async': not wait
            }
            
        except Exception as e:
            logger.error(f"❌ Error ejecutando macro {name}: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': 'execute_macro',
                'error': str(e)
            }
    
    def _parse_key_combination(self, combination: str) -> list:
        """Parsea una combinación de teclas."""
        # Convertir a minúsculas y dividir
        combination = combination.lower().strip()
        
        # Mapear nombres comunes
        key_map = {
            'ctrl': 'ctrl',
            'control': 'ctrl',
            'alt': 'alt',
            'shift': 'shift',
            'win': 'win',
            'super': 'super',
            'meta': 'super',
            'cmd': 'cmd',
            'command': 'cmd',
            'esc': 'esc',
            'escape': 'esc',
            'enter': 'enter',
            'return': 'enter',
            'tab': 'tab',
            'space': 'space',
            ' ': 'space',
            'backspace': 'backspace',
            'delete': 'delete',
            'del': 'delete',
            'insert': 'insert',
            'ins': 'insert',
            'home': 'home',
            'end': 'end',
            'pageup': 'pageup',
            'pgup': 'pageup',
            'pagedown': 'pagedown',
            'pgdn': 'pagedown',
            'up': 'up',
            'down': 'down',
            'left': 'left',
            'right': 'right',
            'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
            'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
            'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12'
        }
        
        # Dividir por +
        keys = []
        for key in combination.split('+'):
            key = key.strip()
            if key in key_map:
                keys.append(key_map[key])
            else:
                # Para teclas simples como letras y números
                if len(key) == 1 and key.isalnum():
                    keys.append(key)
                else:
                    logger.warning(f"⚠️ Tecla desconocida: '{key}'")
                    keys.append(key)  # Intentar de todos modos
        
        return keys
    
    def execute_command(self, command_data: Dict) -> Dict[str, Any]:
        """
        Ejecuta un comando de teclado desde formato estandarizado.
        
        Args:
            command_data: Diccionario con comando
            
        Returns:
            Resultado de la acción
        """
        command_type = command_data.get('command', 'press')
        
        try:
            if command_type == 'press':
                key = command_data.get('key')
                press_time = command_data.get('press_time')
                return self.press_key(key, press_time)
            
            elif command_type == 'combination':
                keys = command_data.get('keys', [])
                key_str = '+'.join(keys)
                return self.press_key(key_str)
            
            elif command_type == 'type' or command_type == 'type_text':
                text = command_data.get('text', '')
                delay = command_data.get('delay', 0.01)
                if not text and 'args' in command_data:
                    text = command_data['args'].get('text', '')
                return self.type_text(text, delay)
            
            elif command_type == 'macro':
                macro_name = command_data.get('macro')
                wait = command_data.get('wait', True)
                return self.execute_macro(macro_name, wait)
            
            elif command_type == 'hold':
                key = command_data.get('key')
                duration = command_data.get('duration')
                return self.hold_key(key, duration)
            
            elif command_type == 'release':
                key = command_data.get('key')
                return self.release_key(key)
            
            else:
                logger.error(f"❌ Tipo de comando desconocido: {command_type}")
                return {
                    'success': False,
                    'action': 'keyboard',
                    'command': command_type,
                    'message': f'Tipo de comando desconocido: {command_type}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error ejecutando comando {command_type}: {e}")
            self.stats['errors'] += 1
            return {
                'success': False,
                'action': 'keyboard',
                'command': command_type,
                'error': str(e)
            }
    
    def execute(self, command: str, params: Dict = None) -> Dict[str, Any]:
        """
        Método principal de ejecución para NYX.
        
        Args:
            command: Comando a ejecutar
            params: Parámetros adicionales
            
        Returns:
            Resultado de la ejecución
        """
        params = params or {}
        
        # Determinar tipo de comando
        if ' ' in command or len(command) > 2:
            # Es texto para escribir
            if command.startswith('type:'):
                text = command[5:]
                return self.type_text(text, params.get('delay', 0.01))
            else:
                # Tratar como texto normal
                return self.type_text(command, params.get('delay', 0.01))
        else:
            # Es combinación de teclas o tecla simple
            return self.press_key(command, params.get('press_time'))
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del controlador."""
        return {
            'available': self.keyboard_module is not None,
            'stats': self.stats.copy(),
            'macros_count': len(self.macros),
            'keys_held': len(self.hold_keys),
            'is_macro_running': self.is_macro_running,
            'keyboard_module': self.keyboard_module
        }
    
    def get_available_keys(self) -> List[str]:
        """Obtiene lista de teclas disponibles."""
        keys = [
            # Letras
            *[chr(i) for i in range(ord('a'), ord('z') + 1)],
            # Números
            *[str(i) for i in range(10)],
            # Teclas especiales
            'alt', 'ctrl', 'shift', 'win', 'super', 'cmd',
            'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'esc', 'enter', 'tab', 'backspace', 'delete', 'insert', 'home', 'end',
            'pageup', 'pagedown', 'up', 'down', 'left', 'right',
            'capslock', 'numlock', 'scrolllock',
            'space', 'printscreen', 'pause'
        ]
        
        return keys
    
    def get_action_history(self, limit: int = 10) -> list:
        """Obtiene historial de acciones."""
        return self.action_history[-limit:] if self.action_history else []
    
    def stop(self):
        """Detiene el controlador."""
        self.is_running = False
        self.release_all_keys()
        logger.info("⏹️ KeyboardController detenido")
    
    def cleanup(self):
        """Limpia recursos."""
        self.stop()
        self.action_history.clear()
        self.hold_keys.clear()
        self.macros.clear()
        logger.info("✅ KeyboardController limpiado")