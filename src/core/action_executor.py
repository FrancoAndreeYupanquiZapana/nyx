"""
🎮 ACTION EXECUTOR - Ejecutor de Acciones para NYX
==================================================
Controlador central que ejecuta acciones basadas en gestos o comandos de voz.
Integra todos los controladores específicos (teclado, mouse, bash, ventanas).
"""

import threading
import queue
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

class ActionExecutor:
    """Ejecutor central de acciones para NYX."""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el ejecutor de acciones para NYX.
        
        Args:
            config: Configuración del sistema desde system.yaml
        """
        self.config = config or {}
        
        # Cola de procesamiento
        self.action_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
        # Sistema de perfiles (CRÍTICO para NYX)
        self.profile_runtime = None
        self.current_profile = None
        self.profile_name = None
        
        # Controladores específicos (CORRECCIÓN IMPORTANTE)
        self.controllers = {}
        self._init_controllers()
        
        # Historial para NYX UI
        self.history = []
        self.max_history = 50
        
        # Estadísticas para monitoreo
        self.stats = {
            'total_executed': 0,
            'successful': 0,
            'failed': 0,
            'gestures': 0,
            'voice_commands': 0,
            'last_execution': None,
            'queue_size': 0
        }
        
        # Callbacks para UI de NYX
        self.callbacks = {
            'on_action_start': [],
            'on_action_complete': [],
            'on_action_error': [],
            'on_profile_changed': []
        }
        
        logger.info("✅ ActionExecutor inicializado para NYX")

    def _init_controllers(self):
        """Inicializa todos los controladores específicos."""
        try:
            # 🎮 Teclado - Usa KeyboardController específico
            try:
                from .keyboard_controller import KeyboardController
                self.controllers['keyboard'] = KeyboardController(self.config)
                logger.debug("✅ KeyboardController cargado")
            except ImportError as e:
                logger.error(f"❌ No se pudo cargar KeyboardController: {e}")
                self.controllers['keyboard'] = None
            
            # 🖱️ Mouse - Usa MouseController específico
            try:
                from .mouse_controller import MouseController
                self.controllers['mouse'] = MouseController(self.config)
                logger.debug("✅ MouseController cargado")
            except ImportError as e:
                logger.error(f"❌ No se pudo cargar MouseController: {e}")
                self.controllers['mouse'] = None
            
            # 💻 Bash - Usa BashController específico
            try:
                from .bash_controller import BashController
                self.controllers['bash'] = BashController(self.config)
                logger.debug("✅ BashController cargado")
            except ImportError as e:
                logger.error(f"❌ No se pudo cargar BashController: {e}")
                self.controllers['bash'] = None
            
            # 🪟 Ventanas - Usa WindowController específico
            try:
                from .window_controller import WindowController
                self.controllers['window'] = WindowController(self.config)
                logger.debug("✅ WindowController cargado")
            except ImportError as e:
                logger.error(f"❌ No se pudo cargar WindowController: {e}")
                self.controllers['window'] = None
            
            # Combinaciones (especial)
            self.controllers['combination'] = None  # Se maneja internamente
            
            # Personalizado
            self.controllers['custom'] = None  # Para callbacks
            
            logger.info(f"🎮 Controladores inicializados: {list(self.controllers.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Error crítico inicializando controladores: {e}")
            # Fallback: crear controladores vacíos
            for name in ['keyboard', 'mouse', 'bash', 'window']:
                self.controllers[name] = None

    def set_profile_runtime(self, profile_runtime):
        """
        Configura el ProfileRuntime actual (CONEXIÓN CRÍTICA).
        
        Args:
            profile_runtime: Instancia de ProfileRuntime
        """
        self.profile_runtime = profile_runtime
        
        if profile_runtime:
            self.current_profile = profile_runtime
            self.profile_name = profile_runtime.name
            logger.info(f"🎭 ProfileRuntime configurado: {self.profile_name}")
            
            # Notificar a UI
            self._run_callbacks('on_profile_changed', {
                'profile_name': self.profile_name,
                'gesture_count': profile_runtime.get_gesture_count(),
                'voice_count': profile_runtime.get_voice_command_count()
            })
        else:
            logger.warning("⚠️ ProfileRuntime configurado como None")
            self.current_profile = None
            self.profile_name = None

    def get_action_for_gesture(self, gesture_name: str, source: str = 'hand', 
                               hand_type: str = 'right') -> Optional[Dict]:
        """
        Obtiene acción para un gesto detectado.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente (hand/arm)
            hand_type: Tipo de mano (right/left)
            
        Returns:
            Configuración de acción o None
        """
        if not self.profile_runtime:
            logger.debug("❌ No hay ProfileRuntime configurado")
            return None
        
        try:
            # Buscar en gestos del perfil
            gesture_data = self.profile_runtime.get_gesture(gesture_name)
            if not gesture_data:
                logger.debug(f"❌ Gesto no encontrado: {gesture_name}")
                return None
            
            # Verificar si está habilitado
            if not gesture_data.get('enabled', True):
                logger.debug(f"⚠️ Gesto deshabilitado: {gesture_name}")
                return None
            
            # Verificar confianza mínima
            confidence = gesture_data.get('confidence', 0.5)
            required_confidence = gesture_data.get('required_confidence', 0.5)
            
            if confidence < required_confidence:
                logger.debug(f"⚠️ Confianza insuficiente: {confidence} < {required_confidence}")
                return None
            
            # Verificar tipo de mano si está especificado
            required_hand = gesture_data.get('hand')
            if required_hand and required_hand != hand_type:
                logger.debug(f"⚠️ Mano incorrecta: {hand_type} != {required_hand}")
                return None
            
            # Crear acción para el controlador
            action = {
                'type': gesture_data.get('action', 'unknown'),
                'command': gesture_data.get('command', ''),
                'description': gesture_data.get('description', f"Gesto: {gesture_name}"),
                'gesture_name': gesture_name,
                'source': source,
                'hand': hand_type,
                'confidence': confidence,
                'profile': self.profile_name
            }
            
            return action
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo acción para gesto: {e}")
            return None

    def get_action_for_voice(self, command_text: str) -> Optional[Dict]:
        """
        Obtiene acción para un comando de voz.
        
        Args:
            command_text: Texto del comando
            
        Returns:
            Configuración de acción o None
        """
        if not self.profile_runtime:
            logger.debug("❌ No hay ProfileRuntime configurado")
            return None
        
        try:
            # Buscar en comandos de voz del perfil
            voice_data = self.profile_runtime.get_voice_command(command_text)
            if not voice_data:
                logger.debug(f"❌ Comando de voz no encontrado: {command_text}")
                return None
            
            # Verificar si está habilitado
            if not voice_data.get('enabled', True):
                logger.debug(f"⚠️ Comando de voz deshabilitado: {command_text}")
                return None
            
            # Crear acción para el controlador
            action = {
                'type': voice_data.get('action', 'unknown'),
                'command': voice_data.get('command', ''),
                'description': voice_data.get('description', f"Voz: {command_text}"),
                'voice_command': command_text,
                'profile': self.profile_name
            }
            
            return action
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo acción para voz: {e}")
            return None

    def execute_gesture(self, gesture_name: str, source: str = 'hand', 
                        hand_type: str = 'right', confidence: float = 0.8) -> Dict[str, Any]:
        """
        Ejecuta acción basada en gesto detectado.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente (hand/arm)
            hand_type: Tipo de mano (right/left)
            confidence: Confianza de detección
            
        Returns:
            Resultado de la ejecución
        """
        logger.info(f"👋 Gestos detectado: {gesture_name} ({source}, {hand_type}, conf: {confidence:.2f})")
        
        # Obtener acción del perfil
        action_cfg = self.get_action_for_gesture(gesture_name, source, hand_type)
        if not action_cfg:
            result = self._format_result(
                success=False,
                error=f"No hay acción configurada para gesto: {gesture_name}"
            )
            return result
        
        # Actualizar confianza
        action_cfg['confidence'] = confidence
        
        # Añadir metadata
        action_cfg.update({
            'timestamp': datetime.now().isoformat(),
            'action_type': 'gesture',
            'execution_mode': 'immediate'
        })
        
        # Ejecutar
        return self.execute(action_cfg)

    def execute_voice(self, command_text: str) -> Dict[str, Any]:
        """
        Ejecuta acción basada en comando de voz.
        
        Args:
            command_text: Texto del comando de voz
            
        Returns:
            Resultado de la ejecución
        """
        logger.info(f"🎤 Comando de voz: {command_text}")
        
        # Obtener acción del perfil
        action_cfg = self.get_action_for_voice(command_text)
        if not action_cfg:
            result = self._format_result(
                success=False,
                error=f"No hay acción configurada para comando: {command_text}"
            )
            return result
        
        # Añadir metadata
        action_cfg.update({
            'timestamp': datetime.now().isoformat(),
            'action_type': 'voice',
            'execution_mode': 'immediate'
        })
        
        # Ejecutar
        return self.execute(action_cfg)

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta una acción.
        
        Args:
            action: Diccionario con configuración de acción
            
        Returns:
            Resultado de la ejecución
        """
        if not action or 'type' not in action:
            return self._format_result(
                success=False,
                error="Acción inválida o sin tipo"
            )
        
        # Generar ID único
        action_id = f"act_{int(time.time() * 1000)}_{self.stats['total_executed']}"
        action['id'] = action_id
        
        # Notificar inicio
        self._run_callbacks('on_action_start', action)
        
        # Determinar modo de ejecución
        execution_mode = action.get('execution_mode', 'queue')
        
        if execution_mode == 'immediate':
            # Ejecutar inmediatamente (gestos, voz)
            result = self._execute_single_action(action)
        else:
            # Encolar para procesamiento asíncrono
            self.action_queue.put(action)
            result = self._format_result(
                success=True,
                output=f"Acción encolada: {action.get('description', 'Sin descripción')}",
                queue_position=self.action_queue.qsize()
            )
        
        return result

    def start(self):
        """Inicia el worker thread para procesar acciones en cola."""
        if self.is_running:
            logger.warning("⚠️ ActionExecutor ya está ejecutándose")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="NYX-ActionExecutor"
        )
        self.worker_thread.start()
        
        logger.info("▶️ ActionExecutor iniciado")

    def stop(self):
        """Detiene el worker thread."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        
        logger.info("⏹️ ActionExecutor detenido")

    def _processing_loop(self):
        """Bucle principal de procesamiento de acciones."""
        logger.info("🔄 Iniciando bucle de procesamiento...")
        
        while self.is_running:
            try:
                # Obtener acción de la cola
                action = self.action_queue.get(timeout=0.5)
                if not action:
                    continue
                
                # Ejecutar acción
                result = self._execute_single_action(action)
                
                # Actualizar estadísticas
                self.stats['queue_size'] = self.action_queue.qsize()
                
                self.action_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de procesamiento: {e}")
        
        logger.info("🔄 Bucle de procesamiento terminado")

    def _execute_single_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta una acción individual.
        
        Args:
            action: Configuración de la acción
            
        Returns:
            Resultado formateado
        """
        action_id = action.get('id', 'unknown')
        action_type = action.get('type', 'unknown')
        action_desc = action.get('description', f'Acción {action_type}')
        
        logger.info(f"🎯 Ejecutando acción [{action_id}]: {action_desc}")
        
        # Verificar controlador disponible
        if action_type not in self.controllers:
            error_msg = f"Controlador no disponible: {action_type}"
            logger.error(f"❌ {error_msg}")
            return self._format_result(success=False, error=error_msg, action=action)
        
        controller = self.controllers[action_type]
        if controller is None:
            error_msg = f"Controlador {action_type} no inicializado"
            logger.error(f"❌ {error_msg}")
            return self._format_result(success=False, error=error_msg, action=action)
        
        try:
            # DELEGAR AL CONTROLADOR ESPECÍFICO (CORRECCIÓN CLAVE)
            if action_type == 'keyboard':
                result = controller.execute(action)
            elif action_type == 'mouse':
                result = controller.execute(action)
            elif action_type == 'bash':
                result = controller.execute(action)
            elif action_type == 'window':
                result = controller.execute(action)
            elif action_type == 'combination':
                result = self._execute_combination(action)
            elif action_type == 'custom':
                result = self._execute_custom(action)
            else:
                error_msg = f"Tipo de acción no soportado: {action_type}"
                return self._format_result(success=False, error=error_msg, action=action)
            
            # Actualizar estadísticas
            self._update_stats(result.get('success', False), action_type)
            
            # Guardar en historial
            self._add_to_history(action, result)
            
            # Notificar resultado
            if result.get('success', False):
                self._run_callbacks('on_action_complete', action, result)
            else:
                self._run_callbacks('on_action_error', action, result)
            
            return result
            
        except Exception as e:
            error_msg = f"Error ejecutando acción {action_type}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            error_result = self._format_result(success=False, error=error_msg, action=action)
            self._run_callbacks('on_action_error', action, error_result)
            return error_result

    def _execute_combination(self, action: Dict) -> Dict[str, Any]:
        """Ejecuta combinación de acciones."""
        sequence = action.get('sequence', [])
        results = []
        
        for i, sub_action in enumerate(sequence):
            result = self._execute_single_action(sub_action)
            results.append(result)
            
            # Delay entre acciones si se especifica
            delay = action.get('delay', 0.1)
            if i < len(sequence) - 1 and delay > 0:
                time.sleep(delay)
        
        # Combinar resultados
        all_success = all(r.get('success', False) for r in results)
        return self._format_result(
            success=all_success,
            output=f"Combinación ejecutada: {len(results)} acciones",
            details=results
        )

    def _execute_custom(self, action: Dict) -> Dict[str, Any]:
        """Ejecuta acción personalizada (callback)."""
        callback = action.get('callback')
        if not callable(callback):
            return self._format_result(success=False, error="Callback no válido")
        
        try:
            args = action.get('args', [])
            kwargs = action.get('kwargs', {})
            
            result = callback(*args, **kwargs)
            
            return self._format_result(
                success=True,
                output="Callback ejecutado exitosamente",
                result=result
            )
        except Exception as e:
            return self._format_result(success=False, error=str(e))

    def _format_result(self, success: bool, output: str = '', error: str = '', 
                      action: Dict = None, **kwargs) -> Dict[str, Any]:
        """Formatea resultado para NYX."""
        result = {
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'output': output,
            'error': error
        }
        
        if action:
            result.update({
                'action_id': action.get('id'),
                'action_type': action.get('type'),
                'description': action.get('description', ''),
                'profile': action.get('profile', self.profile_name)
            })
        
        result.update(kwargs)
        return result

    def _update_stats(self, success: bool, action_type: str):
        """Actualiza estadísticas."""
        self.stats['total_executed'] += 1
        if success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
        
        if action_type == 'gesture':
            self.stats['gestures'] += 1
        elif action_type == 'voice':
            self.stats['voice_commands'] += 1
        
        self.stats['last_execution'] = datetime.now().isoformat()

    def _add_to_history(self, action: Dict, result: Dict):
        """Añade acción al historial."""
        entry = {
            'action': action.copy(),
            'result': result.copy(),
            'timestamp': datetime.now().isoformat()
        }
        
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def _run_callbacks(self, callback_type: str, *args):
        """Ejecuta callbacks."""
        for callback in self.callbacks[callback_type]:
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"❌ Error en callback {callback_type}: {e}")

    def add_callback(self, callback_type: str, callback: Callable):
        """Agrega callback."""
        if callback_type in self.callbacks:
            self.callbacks[callback_type].append(callback)

    def get_status(self) -> Dict[str, Any]:
        """Obtiene estado actual para NYX UI."""
        return {
            'running': self.is_running,
            'profile': self.profile_name,
            'stats': self.stats.copy(),
            'queue_size': self.action_queue.qsize(),
            'history_size': len(self.history),
            'controllers': {
                name: (ctrl is not None) 
                for name, ctrl in self.controllers.items()
            }
        }

    def get_recent_actions(self, limit: int = 10) -> List[Dict]:
        """Obtiene acciones recientes para UI."""
        return self.history[-limit:] if self.history else []

    def cleanup(self):
        """Limpia recursos."""
        self.stop()
        
        # Limpiar controladores
        for name, controller in self.controllers.items():
            if hasattr(controller, 'cleanup'):
                controller.cleanup()
        
        logger.info("✅ ActionExecutor limpiado")


# Uso en NYX
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Crear ActionExecutor simulado
    executor = ActionExecutor()
    
    # Simular perfil gamer
    class MockProfileRuntime:
        name = "gamer"
        gestures = {
            "fist": {
                "action": "keyboard",
                "command": "ctrl+f",
                "description": "Buscar en juego",
                "enabled": True,
                "confidence": 0.7,
                "hand": "right"
            },
            "peace": {
                "action": "keyboard", 
                "command": "esc",
                "description": "Abrir menú",
                "enabled": True,
                "confidence": 0.7
            }
        }
        
        def get_gesture(self, name):
            return self.gestures.get(name)
        
        def get_gesture_count(self):
            return len(self.gestures)
        
        def get_voice_command_count(self):
            return 0
    
    # Configurar perfil
    profile = MockProfileRuntime()
    executor.set_profile_runtime(profile)
    
    # Iniciar ejecutor
    executor.start()
    
    # Probar gesto
    print("🎮 Probando ActionExecutor con NYX:")
    result = executor.execute_gesture("fist", hand_type="right", confidence=0.8)
    print(f"  Resultado: {'✅' if result['success'] else '❌'} {result.get('output', result.get('error', ''))}")
    
    # Mostrar estado
    status = executor.get_status()
    print(f"\n📊 Estado ActionExecutor:")
    print(f"  Perfil activo: {status['profile']}")
    print(f"  Ejecutando: {status['running']}")
    print(f"  Acciones ejecutadas: {status['stats']['total_executed']}")
    
    # Limpiar
    executor.cleanup()