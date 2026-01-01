"""
🎮 GESTURE PIPELINE - Cerebro del Sistema NYX
=============================================
Coordina todo el flujo: cámara → detección → perfil → ejecución → UI.
Versión completa con integración GesturePipelineIntegration y VoiceRecognizer.
"""

import cv2
import time
import threading
import queue
import traceback
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

# Importar PyQt6 para señales
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    # Clases dummy para compatibilidad
    class QObject:
        def __init__(self, *args, **kwargs):
            pass
    
    def pyqtSignal(*args, **kwargs):
        class DummySignal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, *args, **kwargs):
                pass
        return DummySignal()

logger = logging.getLogger(__name__)



# ========== CONTROL DIRECTO DE MOUSE (BYPASS COMPLEXITY) ==========
# Ahora integrado directamente con el MouseController de NYX para usar configuraciones de la UI.


class GesturePipelineIntegration:
    """Clase base para integración de componentes del pipeline."""
    
    def __init__(self):
        """Inicializa la integración del pipeline."""
        self._gesture_buffer = []  # Buffer para gestos recientes
        self._voice_buffer = []    # Buffer para comandos de voz
        self._action_buffer = []   # Buffer para acciones
        self._integration_lock = threading.RLock()
    
    def process_gesture(self, gesture_data: Dict) -> Optional[Dict]:
        """
        Procesa un gesto detectado y lo convierte en acción.
        """
        # Prioridad 1: Usar el integrador especializado si está disponible
        if hasattr(self, 'gesture_integrator') and self.gesture_integrator:
            return self.gesture_integrator.process_gesture(gesture_data)
            
        with self._integration_lock:
            # Fallback a lógica interna (copia de seguridad)
            self._gesture_buffer.append(gesture_data)
            if len(self._gesture_buffer) > 10:
                self._gesture_buffer.pop(0)
            
            # Extraer información del gesto
            gesture_name = gesture_data.get('gesture')
            hand_type = gesture_data.get('hand', 'unknown')
            source = gesture_data.get('source', 'hand')
            confidence = gesture_data.get('confidence', 0)
            
            # Buscar acción correspondiente en el perfil
            action = self._find_action_for_gesture(gesture_name, source, hand_type)
            
            if action:
                # Añadir metadata
                full_action = action.copy()
                full_action.update({
                    'trigger': 'gesture',
                    'gesture_data': gesture_data,
                    'timestamp': time.time(),
                    'confidence': confidence
                })
                
                # Agregar al buffer de acciones
                self._action_buffer.append(full_action)
                if len(self._action_buffer) > 10:
                    self._action_buffer.pop(0)
                
                return full_action
        
        return None
    
    def process_voice_command(self, voice_data: Dict) -> Optional[Dict]:
        """
        Procesa un comando de voz y lo convierte en acción.
        
        Args:
            voice_data: Datos del comando de voz
            
        Returns:
            Acción a ejecutar o None
        """
        with self._integration_lock:
            # Agregar al buffer
            self._voice_buffer.append(voice_data)
            if len(self._voice_buffer) > 10:
                self._voice_buffer.pop(0)
            
            # Extraer texto
            command_text = voice_data.get('text', '').lower().strip()
            
            if not command_text:
                return None
            
            # Buscar acción correspondiente en el perfil
            action = self._find_action_for_voice(command_text)
            
            if action:
                # Añadir metadata
                action.update({
                    'trigger': 'voice',
                    'voice_data': voice_data,
                    'timestamp': time.time()
                })
                
                # Agregar al buffer de acciones
                self._action_buffer.append(action)
                if len(self._action_buffer) > 10:
                    self._action_buffer.pop(0)
                
                return action
        
        return None
    
    def _find_action_for_gesture(self, gesture_name: str, source: str, 
                                 hand_type: str) -> Optional[Dict]:
        """
        Busca una acción correspondiente a un gesto en el perfil.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente del gesto (hand, arm)
            hand_type: Tipo de mano (left, right)
            
        Returns:
            Acción correspondiente o None
        """
        if not hasattr(self, 'profile_runtime') or not self.profile_runtime:
            return None
        
        try:
            # Intentar obtener acción del perfil
            if hasattr(self.profile_runtime, 'get_action_for_gesture'):
                return self.profile_runtime.get_action_for_gesture(
                    gesture_name=gesture_name,
                    source=source,
                    hand_type=hand_type
                )
            
            # Método alternativo: buscar en mapeo de gestos
            if hasattr(self.profile_runtime, 'gesture_mappings'):
                gesture_mappings = self.profile_runtime.gesture_mappings
                
                # Buscar coincidencia exacta
                key = f"{gesture_name}_{source}_{hand_type}"
                if key in gesture_mappings:
                    return gesture_mappings[key]
                
                # Buscar coincidencia parcial
                for mapping_key, action in gesture_mappings.items():
                    if gesture_name in mapping_key and source in mapping_key:
                        return action
            
        except Exception as e:
            logger.error(f"❌ Error buscando acción para gesto: {e}")
        
        return None
    
    def _find_action_for_voice(self, command_text: str) -> Optional[Dict]:
        """
        Busca una acción correspondiente a un comando de voz.
        
        Args:
            command_text: Texto del comando de voz
            
        Returns:
            Acción correspondiente o None
        """
        if not hasattr(self, 'profile_runtime') or not self.profile_runtime:
            return None
        
        try:
            # Intentar obtener acción del perfil
            if hasattr(self.profile_runtime, 'get_action_for_voice'):
                return self.profile_runtime.get_action_for_voice(command_text)
            
            # Método alternativo: buscar en mapeo de voz
            if hasattr(self.profile_runtime, 'voice_mappings'):
                voice_mappings = self.profile_runtime.voice_mappings
                
                # Buscar coincidencia exacta
                if command_text in voice_mappings:
                    return voice_mappings[command_text]
                
                # Buscar coincidencia parcial
                for voice_key, action in voice_mappings.items():
                    if voice_key.lower() in command_text or command_text in voice_key.lower():
                        return action
            
        except Exception as e:
            logger.error(f"❌ Error buscando acción para voz: {e}")
        
        return None
    
    def get_gesture_buffer(self) -> List[Dict]:
        """Obtiene el buffer de gestos recientes."""
        with self._integration_lock:
            return self._gesture_buffer.copy()
    
    def get_voice_buffer(self) -> List[Dict]:
        """Obtiene el buffer de comandos de voz recientes."""
        with self._integration_lock:
            return self._voice_buffer.copy()
    
    def get_action_buffer(self) -> List[Dict]:
        """Obtiene el buffer de acciones recientes."""
        with self._integration_lock:
            return self._action_buffer.copy()
    
    def clear_buffers(self):
        """Limpia todos los buffers."""
        with self._integration_lock:
            self._gesture_buffer.clear()
            self._voice_buffer.clear()
            self._action_buffer.clear()


class GesturePipeline(QObject, GesturePipelineIntegration):
    """Pipeline principal del sistema NYX con integración completa."""
    
    # Señales PyQt6 para comunicación con la UI
    if QT_AVAILABLE:
        gesture_detected = pyqtSignal(dict)           # Gesto detectado
        action_executed = pyqtSignal(dict, dict)      # (acción, resultado)
        frame_available = pyqtSignal(dict)            # Nuevo frame para UI
        status_changed = pyqtSignal(str, dict)        # (estado, datos)
        error_occurred = pyqtSignal(str, str)         # (tipo_error, mensaje)
        profile_changed = pyqtSignal(str, dict)       # (nombre_perfil, info)
        stats_updated = pyqtSignal(dict)              # Estadísticas actualizadas
        pipeline_started = pyqtSignal()               # Pipeline iniciado
        pipeline_stopped = pyqtSignal()               # Pipeline detenido
        voice_event = pyqtSignal(str, dict)           # Eventos de voz
    else:
        # Placeholders cuando PyQt6 no está disponible
        gesture_detected = None
        action_executed = None
        frame_available = None
        status_changed = None
        error_occurred = None
        profile_changed = None
        stats_updated = None
        pipeline_started = None
        pipeline_stopped = None
        voice_event = None
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el pipeline de NYX.
        
        Args:
            config: Configuración del sistema
        """
        # Inicializar integración primero
        GesturePipelineIntegration.__init__(self)
        
        if QT_AVAILABLE:
            QObject.__init__(self)
        else:
            QObject.__init__(self)
        
        # Configuración
        self.config = config or {}
        
        # Estado del pipeline
        self.is_running = False
        self._camera_active = False
        self._processing_active = False
        
        # Sistema de perfiles (CRÍTICO)
        self.current_profile_name = None
        self.profile_runtime = None
        
        # Componentes del sistema
        self.hand_detector = None
        self.arm_detector = None
        self.voice_recognizer = None
        self.action_executor = None
        self.config_loader = None
        
        # GestureIntegrator (opcional)
        self.gesture_integrator = None
        
        # Colas para comunicación entre hilos
        self.gesture_queue = queue.Queue(maxsize=10)      # Frames para UI
        self.action_queue = queue.Queue()                 # Acciones a ejecutar
        self.voice_queue = queue.Queue(maxsize=5)         # Comandos de voz
        self.voice_command_queue = queue.Queue(maxsize=10) # Comandos de voz procesados
        
        # Para acceso thread-safe
        self._latest_frame = None
        self._latest_gestures = []
        self._latest_landmarks = []
        self._frame_lock = threading.RLock()
        self._stats_lock = threading.RLock()
        
        # Estadísticas en tiempo real
        self.stats = {
            'fps': 0,
            'frame_count': 0,
            'gestures_detected': 0,
            'actions_executed': 0,
            'actions_successful': 0,
            'actions_failed': 0,
            'voice_commands': 0,
            'voice_activations': 0,
            'processing_time': 0,
            'detection_time': 0,
            'last_update': time.time(),
            'start_time': time.time()
        }
        
        # Historial
        self.gesture_history = []
        self.action_history = []
        self.voice_history = []
        self.max_history = 100
        
        # Cooldown y debouncing
        self.gesture_cooldowns = {}  # {gesto_name: last_time}
        self.min_gesture_interval = 0.3  # segundos
        
        # Hilos
        self.camera_thread = None
        self.processing_thread = None
        self.voice_thread = None
        self.voice_processing_thread = None
        self.stats_thread = None
        
        # Temporizador para estadísticas
        self._stats_timer = None
        
        # Cargar perfil por defecto desde configuración
        default_profile = self.config.get('active_profile', 'gamer')
        self.load_profile(default_profile)
        
        # Inicializar componentes
        self._init_components()
        
        # Emitir señal de inicialización
        self._emit_status("initialized", {"config": self.config})
        
        logger.info("✅ GesturePipeline inicializado para NYX")
    
    # ========== MÉTODOS DE INICIALIZACIÓN ==========
    
    def _init_components(self):
        """Inicializa todos los componentes del sistema."""
        components_loaded = []
        
        try:
            # 1. Config Loader
            try:
                from utils.config_loader import ConfigLoader
                self.config_loader = ConfigLoader()
                components_loaded.append("ConfigLoader")
                logger.debug("✅ ConfigLoader cargado")
            except ImportError as e:
                logger.warning(f"⚠️ No se pudo cargar ConfigLoader: {e}")
                self.config_loader = None
            
            # 2. Hand Detector
            try:
                hand_config = self.config.get('hand_detection', {})
                if hand_config.get('enabled', True):
                    from detectors.hand_detector import HandDetector
                    self.hand_detector = HandDetector(
                        max_num_hands=hand_config.get('max_num_hands', 2),
                        min_detection_confidence=hand_config.get('min_detection_confidence', 0.7),
                        min_tracking_confidence=hand_config.get('min_tracking_confidence', 0.5),
                        model_complexity=hand_config.get('model_complexity', 1)
                    )
                    components_loaded.append("HandDetector")
                    logger.info("✅ HandDetector inicializado")
                else:
                    logger.info("❌ HandDetector deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar HandDetector: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando HandDetector: {e}")
            
            # 3. Arm Detector
            try:
                arm_config = self.config.get('arm_detection', {})
                if arm_config.get('enabled', False):
                    from detectors.arm_detector import ArmDetector
                    self.arm_detector = ArmDetector(
                        min_detection_confidence=arm_config.get('min_detection_confidence', 0.5),
                        min_tracking_confidence=arm_config.get('min_tracking_confidence', 0.5),
                        model_complexity=arm_config.get('model_complexity', 1)
                    )
                    components_loaded.append("ArmDetector")
                    logger.info("✅ ArmDetector inicializado")
                else:
                    logger.info("❌ ArmDetector deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar ArmDetector: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando ArmDetector: {e}")
            
            # 4. Voice Recognizer (CRÍTICO - Método actualizado)
            try:
                voice_config = self.config.get('voice_recognition', {})
                if voice_config.get('enabled', True):
                    from core.voice_recognizer import VoiceRecognizer
                    
                    # Inicializar VoiceRecognizer
                    self.voice_recognizer = VoiceRecognizer(voice_config)
                    
                    # Configurar callbacks CRÍTICOS
                    self._setup_voice_callbacks()
                    
                    components_loaded.append("VoiceRecognizer")
                    logger.info("✅ VoiceRecognizer inicializado y callbacks configurados")
                else:
                    logger.info("❌ VoiceRecognizer deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar VoiceRecognizer: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando VoiceRecognizer: {e}")
            
            # 5. Action Executor (CRÍTICO)
            try:
                from core.action_executor import ActionExecutor
                self.action_executor = ActionExecutor(self.config)
                components_loaded.append("ActionExecutor")
                logger.info("✅ ActionExecutor inicializado")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar ActionExecutor: {e}")
                raise Exception("ActionExecutor es crítico para NYX")
            except Exception as e:
                logger.error(f"❌ Error inicializando ActionExecutor: {e}")
                raise
            
            # 6. Gesture Integrator (CRÍTICO para coordinación y fusión de gestos)
            try:
                from core.gesture_integrator import GestureIntegrator
                from interpreters.hand_interpreter import HandInterpreter
                from interpreters.arm_interpreter import ArmInterpreter
                
                self.gesture_integrator = GestureIntegrator(self.config)
                self.gesture_integrator.set_pipeline(self)
                
                # Registrar intérpretes especializados
                self.gesture_integrator.register_interpreter('hand', HandInterpreter())
                self.gesture_integrator.register_interpreter('arm', ArmInterpreter())
                
                # Sincronizar ActionExecutor si existe
                if self.action_executor:
                    self.gesture_integrator.action_executor = self.action_executor
                    
                # Sincronizar perfil si ya está cargado
                if self.profile_runtime:
                    self.gesture_integrator.set_profile_runtime(self.profile_runtime)
                
                components_loaded.append("GestureIntegrator")
                logger.info("✅ GestureIntegrator inicializado y registrado intérpretes")
            except ImportError as e:
                logger.warning(f"⚠️ No se pudieron cargar intérpretes para integrador: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando GestureIntegrator: {e}")
            
            logger.info(f"🎮 Componentes cargados: {', '.join(components_loaded)}")
            
        except Exception as e:
            logger.critical(f"🔥 Error crítico inicializando componentes: {e}")
            self._emit_error("init_error", f"Error inicializando: {str(e)}")
            raise
    
    def _setup_voice_callbacks(self):
        """Configura todos los callbacks para VoiceRecognizer."""
        if not self.voice_recognizer:
            return
        
        try:
            # Callback para comandos de voz detectados
            self.voice_recognizer.add_callback('on_command', self._on_voice_command)
            
            # Callback para activación por palabra clave
            self.voice_recognizer.add_callback('on_activation', self._on_voice_activation)
            
            # Callback para errores de voz
            self.voice_recognizer.add_callback('on_error', self._on_voice_error)
            
            # Callback para cambios de estado
            self.voice_recognizer.add_callback('on_state_change', self._on_voice_state_change)
            
            # Callback para audio capturado (opcional)
            self.voice_recognizer.add_callback('on_audio_captured', self._on_voice_audio_captured)
            
            logger.debug("✅ Callbacks de voz configurados")
            
        except Exception as e:
            logger.error(f"❌ Error configurando callbacks de voz: {e}")
    
    # ========== CALLBACKS DE VOZ ==========
    
    def _on_voice_command(self, command: Dict):
        """Procesa comando de voz detectado."""
        try:
            command_text = command.get('text', '').strip()
            logger.info(f"🎤 Comando de voz detectado: '{command_text}'")
            
            # Agregar metadata del perfil si está disponible
            if self.profile_runtime:
                command['profile'] = self.profile_runtime.get_profile_name()
                command['profile_id'] = self.profile_runtime.get_profile_id() if hasattr(self.profile_runtime, 'get_profile_id') else self.current_profile_name
            
            # Actualizar estadísticas
            with self._stats_lock:
                self.stats['voice_commands'] += 1
            
            # Agregar al historial
            self.voice_history.append(command.copy())
            if len(self.voice_history) > self.max_history:
                self.voice_history.pop(0)
            
            # Emitir evento
            if self.voice_event:
                self.voice_event.emit('command', command)
            
            # Encolar para procesamiento
            self._enqueue_voice_command(command)
            
        except Exception as e:
            logger.error(f"❌ Error en callback de comando de voz: {e}")
    
    def _on_voice_activation(self, text: str):
        """Maneja detección de palabra de activación."""
        try:
            logger.info(f"🎤 Activación detectada: '{text}'")
            
            # Actualizar estadísticas
            with self._stats_lock:
                self.stats['voice_activations'] += 1
            
            # Emitir evento
            if self.voice_event:
                self.voice_event.emit('activation', {'text': text, 'timestamp': time.time()})
            
            self._emit_status("voice_activated", {'text': text})
            
        except Exception as e:
            logger.error(f"❌ Error en callback de activación de voz: {e}")
    
    def _on_voice_error(self, error_type: str, message: str):
        """Maneja errores de voz."""
        try:
            logger.error(f"🎤 Error de voz [{error_type}]: {message}")
            
            # Emitir evento
            if self.voice_event:
                self.voice_event.emit('error', {'type': error_type, 'message': message})
            
            self._emit_error('voice_error', f"{error_type}: {message}")
            
        except Exception as e:
            logger.error(f"❌ Error en callback de error de voz: {e}")
    
    def _on_voice_state_change(self, old_state: str, new_state: str):
        """Maneja cambios de estado."""
        try:
            logger.info(f"🎤 Estado de voz: {old_state} → {new_state}")
            
            # Emitir evento
            if self.voice_event:
                self.voice_event.emit('state_change', {
                    'old': old_state,
                    'new': new_state,
                    'timestamp': time.time()
                })
            
            self._emit_status('voice_state', {'old': old_state, 'new': new_state})
            
        except Exception as e:
            logger.error(f"❌ Error en callback de cambio de estado de voz: {e}")
    
    def _on_voice_audio_captured(self, command: Dict):
        """Maneja audio procesado (opcional)."""
        # Opcional: análisis de audio o logging
        try:
            # Puedes agregar procesamiento adicional aquí
            audio_info = command.get('audio_info', {})
            duration = audio_info.get('duration', 0)
            sample_rate = audio_info.get('sample_rate', 0)
            
            if duration > 0:
                logger.debug(f"🎤 Audio capturado: {duration:.2f}s @ {sample_rate}Hz")
                
        except Exception as e:
            logger.debug(f"⚠️ Error en callback de audio: {e}")
    
    def _enqueue_voice_command(self, command: Dict):
        """Encuela comando de voz para procesamiento."""
        try:
            self.voice_command_queue.put_nowait(command)
            logger.debug(f"✅ Comando de voz encolado: {command.get('text', '')[:50]}...")
            
        except queue.Full:
            logger.warning("⚠️ Cola de comandos de voz llena")
            
            # Alternativa: procesar inmediatamente
            self._process_voice_command_immediately(command)
    
    def _process_voice_command_immediately(self, command: Dict):
        """Procesa un comando de voz inmediatamente."""
        try:
            # Verificar acción directa o mapeada
            action_type = command.get('action')
            
            if action_type == 'keyboard' and command.get('command') == 'type_text':
                # --- DICTATION HANDLER ---
                text_to_type = command.get('matched_text') or command.get('processed_text')
                if text_to_type and self.action_executor:
                     logger.info(f"⌨️ Escribiendo texto dictado: {text_to_type}")
                     # Crear acción de sistema para el teclado
                     type_action = {
                         'type': 'system',
                         'action': 'keyboard',
                         'command': 'type_text',
                         'args': {'text': text_to_type}
                     }
                     self.action_executor.execute(type_action)
                return

            # Ejecutar a través del ActionExecutor
            if self.action_executor:
                # Convertir voice command a formato de acción estándar
                action_data = {
                    'type': 'voice',
                    'command': command.get('command'),
                    'action': command.get('action'),
                    'args': command.get('args', {}),
                    'confidence': command.get('confidence', 1.0)
                }
                
                result = self.action_executor.execute(action_data)
                
                logger.info(f"🎤 Ejecutando comando de voz: {command.get('text', 'Unknown')}")
                
                # Registrar en historial
                if result:
                     self.action_history.append({
                        'voice_command': command,
                        'action': action_data,
                        'result': result,
                        'timestamp': time.time()
                     })

            else:
                logger.warning("⚠️ ActionExecutor no disponible para comando de voz")
                
        except Exception as e:
            logger.error(f"❌ Error procesando comando de voz en pipeline: {e}")
    
    # ========== MÉTODOS DE INTEGRACIÓN SOBREESCRITOS ==========
    
    def _handle_detected_gesture(self, gesture_data: Dict):
        """Maneja un gesto detectado usando el sistema integrado."""
        gesture_name = gesture_data.get('gesture')
        hand_type = gesture_data.get('hand', 'unknown')
        source = gesture_data.get('source', 'hand')
        confidence = gesture_data.get('confidence', 0)
        
        is_high_freq = False
        if hasattr(self, 'profile_runtime') and self.profile_runtime:
            action_cfg = self._find_action_for_gesture(gesture_name, source, hand_type)
            if action_cfg and action_cfg.get('action') == 'mouse':
                # Bypass cooldown for movement and precision gestures (pinch, scroll)
                if action_cfg.get('command') in ['move', 'scroll', 'click', 'drag_start', 'drag_end']:
                     is_high_freq = True
                     
        # TAMBIÉN bypass para el evento base de tracking que habilitamos
        if gesture_name == 'hand_tracking':
            is_high_freq = True

        gesture_key = f"{gesture_name}_{hand_type}_{source}"
        current_time = time.time()
        last_time = self.gesture_cooldowns.get(gesture_key, 0)
        
        if not is_high_freq and (current_time - last_time < self.min_gesture_interval):
            return
        
        # 2. Actualizar cooldown
        self.gesture_cooldowns[gesture_key] = current_time
        
        # 3. Actualizar estadísticas
        with self._stats_lock:
            self.stats['gestures_detected'] += 1
        
        # 4. Agregar al historial
        self.gesture_history.append(gesture_data.copy())
        if len(self.gesture_history) > self.max_history:
            self.gesture_history.pop(0)
        
        # 5. Mapear gesto a acción usando el sistema integrado
        action = self.process_gesture(gesture_data)
        
        # 6. Emitir señal (Asegurar que UI tenga el nombre correcto)
        if self.gesture_detected:
            ui_data = gesture_data.copy()
            ui_data['gesture_name'] = gesture_name
            if action:
                ui_data['action_name'] = f"{action.get('type', action.get('action'))}:{action.get('command')}"
            self.gesture_detected.emit(ui_data)
        
        if action and self.action_executor:
            try:
                # Ejecutar acción
                action_result = self.action_executor.execute(action)
                
                # Registrar en historial de acciones
                if action_result:
                    self.action_history.append({
                        'gesture': gesture_data,
                        'action': action,
                        'action_result': action_result,
                        'timestamp': time.time()
                    })
                    
                    if len(self.action_history) > self.max_history:
                        self.action_history.pop(0)
                    
                    # Actualizar estadísticas
                    with self._stats_lock:
                        self.stats['actions_executed'] += 1
                        if action_result.get('success', False):
                            self.stats['actions_successful'] += 1
                        else:
                            self.stats['actions_failed'] += 1
                    
                    # Emitir señal de acción ejecutada
                    if self.action_executed:
                        self.action_executed.emit(action, action_result)
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando acción para gesto {gesture_name}: {e}")
    
    def _process_voice_command(self, command_data: Dict):
        """Procesa un comando de voz usando el sistema integrado."""
        command_text = command_data.get('text', '').lower().strip()
        
        if not command_text:
            return
        
        logger.info(f"🎤 Procesando comando de voz: '{command_text}'")
        
        # 1. Agregar al historial
        self.voice_history.append(command_data.copy())
        if len(self.voice_history) > self.max_history:
            self.voice_history.pop(0)
        
        # 2. Actualizar estadísticas
        with self._stats_lock:
            self.stats['voice_commands'] += 1
        
        # 3. Usar el método integrado para procesar el comando de voz
        action = self.process_voice_command(command_data)
        
        if action and self.action_executor:
            try:
                # Ejecutar acción
                action_result = self.action_executor.execute(action)
                
                # Registrar resultado
                if action_result:
                    self.action_history.append({
                        'voice_command': command_data,
                        'action': action,
                        'action_result': action_result,
                        'timestamp': time.time()
                    })
                    
                    # Emitir señal si se ejecutó
                    if action_result.get('success', False) and self.action_executed:
                        self.action_executed.emit(action, action_result)
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando comando de voz: {e}")
    
    # ========== MÉTODOS DE GESTIÓN DE PERFILES ==========
    
    def load_profile(self, profile_name: str) -> bool:
        """
        Carga un perfil de configuración.
        
        Args:
            profile_name: Nombre del perfil a cargar
            
        Returns:
            True si se cargó correctamente
        """
        logger.info(f"📥 Cargando perfil: {profile_name}")
        
        try:
            # 1. Obtener datos del perfil
            profile_data = None
            
            if self.config_loader:
                profile_data = self.config_loader.get_profile(profile_name)
            else:
                # Fallback: cargar directamente desde archivo
                import json
                import os
                profiles_dir = os.path.join('src', 'config', 'profiles')
                profile_path = os.path.join(profiles_dir, f"{profile_name}.json")
                
                if os.path.exists(profile_path):
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
            
            if not profile_data:
                error_msg = f"Perfil no encontrado: {profile_name}"
                logger.error(f"❌ {error_msg}")
                self._emit_error("profile_error", error_msg)
                return False
            
            logger.info(f"✅ Perfil encontrado: {profile_name}")
            
            # 2. Crear ProfileRuntime
            try:
                from core.profile_runtime import ProfileRuntime
                self.profile_runtime = ProfileRuntime(profile_data)
                logger.info("✅ ProfileRuntime creado")
            except Exception as e:
                error_msg = f"Error creando ProfileRuntime: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self._emit_error("profile_error", error_msg)
                return False
            
            # 3. Actualizar estado interno
            self.current_profile_name = profile_name
            
            # 4. ✅ CONEXIÓN CRÍTICA: Conectar perfil con ActionExecutor
            if self.action_executor:
                logger.info("🔗 Conectando perfil con ActionExecutor...")
                
                if hasattr(self.action_executor, 'set_profile_runtime'):
                    self.action_executor.set_profile_runtime(self.profile_runtime)
                    logger.info("✅ ProfileRuntime conectado a ActionExecutor")
                else:
                    error_msg = "ActionExecutor no tiene set_profile_runtime"
                    logger.error(f"❌ {error_msg}")
                    self._emit_error("connection_error", error_msg)
                    return False
            
            # 5. Cargar perfil en GestureIntegrator si existe
            if self.gesture_integrator and hasattr(self.gesture_integrator, 'load_profile'):
                try:
                    self.gesture_integrator.load_profile(profile_data)
                    logger.info("✅ Perfil cargado en GestureIntegrator")
                except Exception as e:
                    logger.warning(f"⚠️ Error cargando perfil en GestureIntegrator: {e}")
            
            # 6. Configurar detectores con gestos activos
            if self.hand_detector and hasattr(self.hand_detector, 'set_active_gestures'):
                try:
                    active_gestures = self.profile_runtime.get_all_gestures()
                    self.hand_detector.set_active_gestures(active_gestures)
                    logger.info(f"✅ {len(active_gestures)} gestos configurados en HandDetector")
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando gestos en HandDetector: {e}")
            
            # 7. Configurar voz con comandos del perfil
            if self.voice_recognizer:
                # Configurar palabra de activación
                activation_word = self.config.get('voice_recognition', {}).get('activation_word', 'nyx')
                if hasattr(self.voice_recognizer, 'set_activation_word'):
                    self.voice_recognizer.set_activation_word(activation_word)
                    logger.info(f"✅ Palabra de activación configurada: {activation_word}")
                
                # Configurar comandos de voz del perfil
                if hasattr(self.voice_recognizer, 'set_voice_commands'):
                    voice_commands = self.profile_runtime.get_voice_commands()
                    self.voice_recognizer.set_voice_commands(voice_commands)
                    logger.info(f"✅ {len(voice_commands)} comandos de voz configurados")
            
            # 8. Emitir señales
            profile_info = {
                'name': profile_name,
                'gesture_count': self.profile_runtime.get_gesture_count(),
                'voice_command_count': self.profile_runtime.get_voice_command_count(),
                'enabled_modules': profile_data.get('enabled_modules', []),
                'settings': profile_data.get('settings', {})
            }
            
            self._emit_status("profile_loaded", profile_info)
            
            if self.profile_changed:
                safe_name = profile_name if isinstance(profile_name, str) else str(profile_name.get('profile_name', 'unknown') if isinstance(profile_name, dict) else profile_name)
                logger.info("DEBUG: Emitting profile_changed signal...")
                self.profile_changed.emit(safe_name, profile_info)
                logger.info("DEBUG: Signal emitted.")
            
            logger.info(f"✅ Perfil '{profile_name}' cargado exitosamente")
            logger.info(f"📊 Resumen: {profile_info['gesture_count']} gestos, "
                      f"{profile_info['voice_command_count']} comandos voz")
            
            return True
            
        except Exception as e:
            error_msg = f"Error cargando perfil {profile_name}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(traceback.format_exc())
            self._emit_error("profile_error", error_msg)
            return False
    
    # ========== MÉTODOS DE CONTROL DEL PIPELINE ==========
    
    def start(self) -> bool:
        """
        Inicia el pipeline completo.
        
        Returns:
            True si se inició correctamente
        """
        if self.is_running:
            logger.warning("⚠️ Pipeline ya está en ejecución")
            return True
        
        logger.info("▶️ Iniciando GesturePipeline...")
        
        try:
            # 1. Verificar componentes críticos
            if not self.action_executor:
                error_msg = "ActionExecutor no inicializado"
                logger.error(f"❌ {error_msg}")
                self._emit_error("start_error", error_msg)
                return False
            
            if self.profile_runtime is None:
                # Cargar perfil por defecto
                default_profile = self.config.get('active_profile', 'gamer')
                logger.info(f"🔄 Cargando perfil por defecto: {default_profile}")
                if not self.load_profile(default_profile):
                    error_msg = f"No se pudo cargar perfil por defecto: {default_profile}"
                    logger.error(f"❌ {error_msg}")
                    self._emit_error("start_error", error_msg)
                    return False
            
            # 2. Iniciar ActionExecutor
            try:
                self.action_executor.start()
                logger.info("✅ ActionExecutor iniciado")
            except Exception as e:
                logger.error(f"❌ Error iniciando ActionExecutor: {e}")
            
            # 3. Iniciar VoiceRecognizer
            if self.voice_recognizer:
                try:
                    self.voice_recognizer.start()
                    logger.info("✅ VoiceRecognizer iniciado")
                    
                    # Iniciar hilo de procesamiento de comandos de voz
                    self.voice_processing_thread = threading.Thread(
                        target=self._voice_processing_loop,
                        daemon=True,
                        name="NYX-VoiceProcessingThread"
                    )
                    self.voice_processing_thread.start()
                    logger.info("✅ Hilo de procesamiento de voz iniciado")
                    
                except Exception as e:
                    logger.error(f"❌ Error iniciando VoiceRecognizer: {e}")
            
            # 4. Iniciar GestureIntegrator
            if self.gesture_integrator and hasattr(self.gesture_integrator, 'start'):
                try:
                    self.gesture_integrator.start()
                    logger.info("✅ GestureIntegrator iniciado")
                except Exception as e:
                    logger.error(f"❌ Error iniciando GestureIntegrator: {e}")
            
            # 5. Marcar como corriendo
            self.is_running = True
            self._processing_active = True
            
            # 6. Iniciar hilos
            # Hilo de cámara
            self.camera_thread = threading.Thread(
                target=self._camera_loop,
                daemon=True,
                name="NYX-CameraThread"
            )
            self.camera_thread.start()
            logger.info("✅ Hilo de cámara iniciado")
            
            # Hilo de procesamiento
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="NYX-ProcessingThread"
            )
            self.processing_thread.start()
            logger.info("✅ Hilo de procesamiento iniciado")
            
            # Hilo de escucha de voz (si está disponible)
            if self.voice_recognizer and hasattr(self.voice_recognizer, 'listen_in_background'):
                self.voice_thread = threading.Thread(
                    target=self._voice_listening_loop,
                    daemon=True,
                    name="NYX-VoiceListeningThread"
                )
                self.voice_thread.start()
                logger.info("✅ Hilo de escucha de voz iniciado")
            
            # 7. Iniciar temporizador de estadísticas
            self._start_stats_timer()
            
            # 8. Emitir señal de inicio
            self._emit_status("started", {
                'profile': self.current_profile_name,
                'components': {
                    'camera': self.camera_thread.is_alive() if self.camera_thread else False,
                    'processing': self.processing_thread.is_alive() if self.processing_thread else False,
                    'voice_listening': self.voice_thread.is_alive() if self.voice_thread else False,
                    'voice_processing': self.voice_processing_thread.is_alive() if self.voice_processing_thread else False,
                    'integrator': self.gesture_integrator is not None
                }
            })
            
            if self.pipeline_started:
                self.pipeline_started.emit()
            
            logger.info("✅ GesturePipeline iniciado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error iniciando pipeline: {e}")
            logger.error(traceback.format_exc())
            self._emit_error("start_error", str(e))
            self.is_running = False
            return False
    
    def stop(self):
        """Detiene el pipeline de manera controlada."""
        if not self.is_running:
            return
        
        logger.info("⏹️ Deteniendo GesturePipeline...")
        
        # 1. Marcar como detenido
        self.is_running = False
        self._camera_active = False
        self._processing_active = False
        
        # 2. Detener temporizador de estadísticas
        self._stop_stats_timer()
        
        # 3. Detener VoiceRecognizer
        if self.voice_recognizer:
            try:
                self.voice_recognizer.stop()
                logger.info("✅ VoiceRecognizer detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo VoiceRecognizer: {e}")
        
        # 4. Detener ActionExecutor
        if self.action_executor:
            try:
                self.action_executor.stop()
                logger.info("✅ ActionExecutor detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo ActionExecutor: {e}")
        
        # 5. Detener GestureIntegrator
        if self.gesture_integrator and hasattr(self.gesture_integrator, 'stop'):
            try:
                self.gesture_integrator.stop()
                logger.info("✅ GestureIntegrator detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo GestureIntegrator: {e}")
        
        # 6. Esperar a que terminen los hilos
        threads = [
            (self.camera_thread, "cámara"),
            (self.processing_thread, "procesamiento"),
            (self.voice_thread, "escucha de voz"),
            (self.voice_processing_thread, "procesamiento de voz")
        ]
        
        for thread, name in threads:
            if thread and thread.is_alive():
                logger.info(f"⏳ Esperando hilo de {name}...")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    logger.warning(f"⚠️ Hilo de {name} no terminó correctamente")
                else:
                    logger.info(f"✅ Hilo de {name} detenido")
        
        # 7. Limpiar colas
        self._clear_queues()
        
        # 8. Limpiar buffers
        self.clear_buffers()
        
        # 9. Emitir señal de detención
        self._emit_status("stopped", {
            'uptime': time.time() - self.stats['start_time']
        })
        
        if self.pipeline_stopped:
            self.pipeline_stopped.emit()
        
        logger.info("✅ GesturePipeline detenido correctamente")
    
    # ========== BUCLES DE PROCESAMIENTO ==========
    
    def _camera_loop(self):
        """Bucle principal de captura de cámara."""
        logger.info("🎥 Iniciando bucle de cámara...")
        
        camera_config = self.config.get('camera', {})
        device_id = camera_config.get('device_id', 0)
        width = camera_config.get('width', 1280)
        height = camera_config.get('height', 720)
        fps_target = camera_config.get('fps', 30)
        mirror = camera_config.get('mirror', True)
        
        # Intentar abrir la cámara
        cap = None
        retry_count = 0
        max_retries = 3
        
        while self.is_running and retry_count < max_retries:
            try:
                print(f"DEBUG_PRINT: Opening camera {device_id} with CAP_DSHOW...")
                # Fix para Windows: usar DirectShow
                cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
                
                if cap.isOpened():
                    print("DEBUG_PRINT: Camera opened successfully")
                    # Configurar propiedades
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    cap.set(cv2.CAP_PROP_FPS, fps_target)
                    
                    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    self._camera_active = True
                    
                    logger.info(f"📷 Cámara {device_id} abierta: "
                              f"{actual_width}x{actual_height} @ {actual_fps:.1f} FPS")
                    
                    self._emit_status("camera_active", {
                        'device_id': device_id,
                        'resolution': f"{actual_width}x{actual_height}",
                        'fps': actual_fps,
                        'mirror': mirror
                    })
                    break
                else:
                    logger.warning(f"⚠️ No se pudo abrir cámara {device_id}, intentando alternativa...")
                    device_id = (device_id + 1) % 3
                    retry_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error abriendo cámara: {e}")
                retry_count += 1
            
            if retry_count < max_retries:
                time.sleep(1)
        
        if not cap or not cap.isOpened():
            error_msg = f"No se pudo abrir ninguna cámara después de {max_retries} intentos"
            logger.error(f"❌ {error_msg}")
            self._emit_error("camera_error", error_msg)
            return
        
        # Control de FPS
        frame_interval = 1.0 / fps_target if fps_target > 0 else 0.033
        last_frame_time = time.time()
        frame_count = 0
        fps_timer = time.time()
        
        # Bucle principal de captura
        while self.is_running and self._camera_active and cap.isOpened():
            current_time = time.time()
            
            # Control de FPS
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue
            
            last_frame_time = current_time
            
            # Capturar frame
            ret, frame = cap.read()
            if not ret:
                logger.warning("⚠️ Error leyendo frame de cámara")
                time.sleep(0.05)
                continue
            
            # Espejar si está configurado
            if mirror:
                frame = cv2.flip(frame, 1)
            
            # Procesar frame
            try:
                start_process = time.time()
                
                # Opción 1: Usar GestureIntegrator si está disponible
                if self.gesture_integrator and hasattr(self.gesture_integrator, 'process_frame'):
                    processed_data = self.gesture_integrator.process_frame(frame)
                    
                    # Obtener acciones del integrador
                    actions = self.gesture_integrator.get_actions()
                    for action in actions:
                        if self.action_executor:
                            self.action_executor.execute(action)
                
                # Opción 2: Procesamiento tradicional
                else:
                    processed_data = self._process_frame(frame)
                
                # ========== CONTROL DIRECTO DE MOUSE (BYPASS COMPLEXITY) ==========
                # Inyección directa desde el loop de cámara al MouseController
                if self.action_executor and hasattr(self.action_executor, 'controllers'):
                    mouse = self.action_executor.controllers.get('mouse')
                    if mouse and processed_data.get('landmarks'):
                        # ========== OPCIÓN NUCLEAR: SIEMPRE PROCESAR SI HAY MANO ==========
                        # Bypass completo de filtros de gestos
                        logger.info("🟢 MANO DETECTADA - PROCESANDO MOUSE")
                        for hand_landmarks in processed_data['landmarks']:
                            if hand_landmarks:
                                h, w = frame.shape[:2]
                                mouse.process_direct_hand(hand_landmarks, w, h)
                                break  # Solo procesar la primera mano
                
                frame_count += 1
                
                processing_time = time.time() - start_process
                
                with self._stats_lock:
                    self.stats['processing_time'] = processing_time * 0.1 + self.stats['processing_time'] * 0.9
                
                # Guardar frame más reciente
                with self._frame_lock:
                    self._latest_frame = processed_data['image']
                    self._latest_gestures = processed_data['gestures']
                    self._latest_landmarks = processed_data['landmarks']
                
                # Preparar datos para UI
                safe_frame = processed_data['image'].copy()
                
                frame_data = {
                    'type': 'frame',
                    'image': processed_data['image'].copy(),
                    'gestures': processed_data['gestures'],
                    'landmarks': processed_data['landmarks'],
                    'timestamp': current_time,
                    'processing_time': processing_time,
                    'stats': self._get_current_stats()
                }
                # Enviar a la cola para UI
                try:
                    self.gesture_queue.put_nowait(frame_data)
                except queue.Full:
                    try:
                        self.gesture_queue.get_nowait()
                        self.gesture_queue.put_nowait(frame_data)
                    except queue.Empty:
                        pass
                
                # Emitir señal si hay suscriptores
                if self.frame_available:
                    self.frame_available.emit(frame_data)
                
                # Actualizar estadísticas de FPS
                frame_count += 1
                if current_time - fps_timer >= 1.0:
                    with self._stats_lock:
                        self.stats['fps'] = frame_count
                        self.stats['frame_count'] += frame_count
                    frame_count = 0
                    fps_timer = current_time
                
                # Procesar cola de voz
                self._process_voice_queue()
                
            except Exception as e:
                print(f"DEBUG_PRINT: Camera loop exception: {e}")
                logger.error(f"❌ Error procesando frame: {e}")
                logger.error(traceback.format_exc())
                # NO reiniciar el loop, solo sleep
                time.sleep(0.1)
        
        # Liberar recursos
        cap.release()
        self._camera_active = False
        cv2.destroyAllWindows()
        
        logger.info("🎥 Bucle de cámara terminado")
    
    def _voice_listening_loop(self):
        """Bucle de escucha de voz en segundo plano."""
        if not self.voice_recognizer or not hasattr(self.voice_recognizer, 'listen_in_background'):
            return
        
        logger.info("🎤 Iniciando bucle de escucha de voz...")
        
        while self.is_running and self._processing_active:
            try:
                # Usar método de escucha en segundo plano si está disponible
                if hasattr(self.voice_recognizer, 'listen_in_background'):
                    self.voice_recognizer.listen_in_background()
                    break  # El método se ejecuta en su propio hilo
                else:
                    # Método tradicional de polling
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"❌ Error en bucle de escucha de voz: {e}")
                time.sleep(1)
        
        logger.info("🎤 Bucle de escucha de voz terminado")
    
    def _voice_processing_loop(self):
        """Bucle de procesamiento de comandos de voz en cola."""
        logger.info("🎤 Iniciando bucle de procesamiento de voz...")
        
        while self.is_running and self._processing_active:
            try:
                # Procesar comandos de voz de la cola
                if not self.voice_command_queue.empty():
                    command = self.voice_command_queue.get(timeout=0.01)
                    
                    if command:
                        # Procesar comando usando el sistema integrado
                        self._process_voice_command(command)
                    
                    self.voice_command_queue.task_done()
                
                # Pequeña pausa para no consumir mucho CPU
                time.sleep(0.001)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de procesamiento de voz: {e}")
                time.sleep(0.1)
        
        logger.info("🎤 Bucle de procesamiento de voz terminado")
    
    def start_voice_listening(self):
        """Activa la escucha de voz (Push-to-Talk)."""
        if self.voice_recognizer and hasattr(self.voice_recognizer, 'activate_listening'):
            self.voice_recognizer.activate_listening()
            logger.info("🎙️ Pipeline: Activando escucha de voz")

    def stop_voice_listening(self):
        """Desactiva la escucha de voz (Push-to-Talk)."""
        if self.voice_recognizer and hasattr(self.voice_recognizer, 'deactivate_listening'):
            self.voice_recognizer.deactivate_listening()
            logger.info("🔇 Pipeline: Desactivando escucha de voz")
    
    def _processing_loop(self):
        """Bucle de procesamiento de acciones en cola."""
        logger.info("🔄 Iniciando bucle de procesamiento...")
        
        while self.is_running and self._processing_active:
            try:
                # 1. Procesar acciones de la cola
                if not self.action_queue.empty():
                    action = self.action_queue.get(timeout=0.01)
                    
                    if action and self.action_executor:
                        # Ejecutar acción
                        result = self.action_executor.execute(action)
                        
                        # Emitir señal
                        if self.action_executed:
                            self.action_executed.emit(action, result)
                    
                    self.action_queue.task_done()
                
                # 2. Pequeña pausa para no consumir mucho CPU
                time.sleep(0.001)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de procesamiento: {e}")
        
        logger.info("🔄 Bucle de procesamiento terminado")
    
    # ========== MÉTODOS UTILITARIOS ==========
    
    def _process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Procesa un frame individual para detección.
        
        Args:
            frame: Frame de imagen BGR
            
        Returns:
            Diccionario con resultados
        """
        gestures = []
        landmarks = []
        processed_frame = frame.copy()
        
        # 1. Detección de manos
        if self.hand_detector and self.config.get('hand_detection', {}).get('enabled', True):
            try:
                start_detect = time.time()
                results = self.hand_detector.detect(frame)
                detect_time = time.time() - start_detect
                
                with self._stats_lock:
                    self.stats['detection_time'] = detect_time * 0.1 + self.stats['detection_time'] * 0.9
                
                if results.get('success', False):
                    # Obtener imagen procesada
                    if results.get('image') is not None:
                        processed_frame = results['image']
                    
                    # Procesar gestos detectados
                    if results.get('gestures'):
                        for gesture_data in results['gestures']:
                            # Validar confianza mínima
                            confidence = gesture_data.get('confidence', 0)
                            min_confidence = self.config.get('hand_detection', {}).get('min_detection_confidence', 0.5)
                            
                            if confidence >= min_confidence:
                                # Completar datos del gesto
                                gesture_data.update({
                                    'timestamp': time.time(),
                                    'source': 'hand',
                                    'detection_time': detect_time
                                })
                                
                                gestures.append(gesture_data)
                                
                                # Manejar gesto (usará el método integrado)
                                self._handle_detected_gesture(gesture_data)
                    
                    # Obtener landmarks
                    if results.get('landmarks'):
                        landmarks.extend(results['landmarks'])
                        
            except Exception as e:
                logger.error(f"❌ Error en detección de manos: {e}")
        
        # 2. Detección de brazos (si está habilitado)
        if self.arm_detector and self.config.get('arm_detection', {}).get('enabled', False):
            try:
                results = self.arm_detector.detect(frame)
                
                if results.get('success', False):
                    # Procesar gestos de brazos
                    if results.get('gestures'):
                        for gesture_data in results['gestures']:
                            gesture_data.update({
                                'timestamp': time.time(),
                                'source': 'arm'
                            })
                            
                            gestures.append(gesture_data)
                            
                            # Manejar gesto (usará el método integrado)
                            self._handle_detected_gesture(gesture_data)
                    
                    # Obtener landmarks de brazos
                    if results.get('landmarks'):
                        landmarks.extend(results['landmarks'])
                        
            except Exception as e:
                logger.error(f"❌ Error en detección de brazos: {e}")
        
        # 3. Dibujar información en el frame
        processed_frame = self._draw_frame_info(processed_frame, gestures, landmarks)
        
        return {
            'image': processed_frame,
            'gestures': gestures,
            'landmarks': landmarks,
            'success': len(gestures) > 0,
            'timestamp': time.time()
        }
    
    def _process_voice_queue(self):
        """Procesa comandos de voz en la cola."""
        try:
            while not self.voice_queue.empty():
                command = self.voice_queue.get_nowait()
                self._process_voice_command(command)
                self.voice_queue.task_done()
        except queue.Empty:
            pass
    
    # ========== MÉTODOS DE ESTADÍSTICAS ==========
    
    def _start_stats_timer(self):
        """Inicia el temporizador para actualizar estadísticas."""
        if QT_AVAILABLE and self.stats_updated:
            self._stats_timer = QTimer()
            self._stats_timer.timeout.connect(self._update_stats_display)
            self._stats_timer.start(1000)  # Actualizar cada segundo
    
    def _stop_stats_timer(self):
        """Detiene el temporizador de estadísticas."""
        if self._stats_timer:
            self._stats_timer.stop()
            self._stats_timer = None
    
    def _update_stats_display(self):
        """Actualiza y emite estadísticas para la UI."""
        stats = self._get_current_stats()
        
        if self.stats_updated:
            self.stats_updated.emit(stats)
    
    def _get_current_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas actuales."""
        with self._stats_lock:
            stats_copy = self.stats.copy()
            stats_copy.update({
                'uptime': time.time() - stats_copy['start_time'],
                'gesture_history_size': len(self.gesture_history),
                'action_history_size': len(self.action_history),
                'voice_history_size': len(self.voice_history),
                'action_queue_size': self.action_queue.qsize(),
                'gesture_queue_size': self.gesture_queue.qsize(),
                'voice_queue_size': self.voice_queue.qsize(),
                'voice_command_queue_size': self.voice_command_queue.qsize(),
                'gesture_buffer_size': len(self.get_gesture_buffer()),
                'voice_buffer_size': len(self.get_voice_buffer()),
                'action_buffer_size': len(self.get_action_buffer()),
                'is_running': self.is_running,
                'camera_active': self._camera_active,
                'processing_active': self._processing_active,
                'current_profile': self.current_profile_name,
                'has_profile_runtime': self.profile_runtime is not None,
                'has_action_executor': self.action_executor is not None,
                'has_gesture_integrator': self.gesture_integrator is not None,
                'has_voice_recognizer': self.voice_recognizer is not None
            })
        
        return stats_copy
    
    # ========== MÉTODOS DE VISUALIZACIÓN ==========
    
    def _draw_frame_info(self, frame: np.ndarray, gestures: List[Dict], 
                        landmarks: List[Dict]) -> np.ndarray:
        """
        Dibuja información en el frame para visualización.
        
        Args:
            frame: Imagen original
            gestures: Lista de gestos detectados
            landmarks: Lista de landmarks
            
        Returns:
            Imagen con información dibujada
        """
        h, w = frame.shape[:2]
        
        # Crear overlay para información
        overlay = frame.copy()
        
        # 1. Barra superior
        cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # 2. Información del sistema
        # Nombre y FPS
        fps_text = f"NYX | FPS: {self.stats['fps']}"
        cv2.putText(frame, fps_text, (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Perfil actual
        profile_text = f"Perfil: {self.current_profile_name or 'Ninguno'}"
        cv2.putText(frame, profile_text, (w - 200, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 3. Información de gestos
        if gestures:
            y_offset = 60
            for i, gesture in enumerate(gestures[:3]):  # Mostrar máximo 3
                name = gesture.get('gesture', 'Desconocido')
                hand = gesture.get('hand', '').capitalize()
                conf = gesture.get('confidence', 0)
                
                gesture_text = f"{hand} {name}: {conf:.1%}"
                color = (0, 200, 255) if conf > 0.7 else (200, 200, 200)
                
                cv2.putText(frame, gesture_text, (10, y_offset + i * 25), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        
        # 4. Estado de voz
        if self.voice_recognizer and hasattr(self.voice_recognizer, 'get_state'):
            voice_state = self.voice_recognizer.get_state()
            state_text = f"Voz: {voice_state}"
            state_color = (0, 200, 0) if voice_state == 'listening' else (200, 200, 200)
            cv2.putText(frame, state_text, (w - 200, h - 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, state_color, 1)
        
        # 5. Estadísticas en esquina inferior
        stats_text = f"Gestos: {self.stats['gestures_detected']} | "
        stats_text += f"Acciones: {self.stats['actions_executed']} | "
        stats_text += f"Voz: {self.stats['voice_commands']}"
        cv2.putText(frame, stats_text, (10, h - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        return frame
    
    # ========== MÉTODOS PÚBLICOS ==========
    
    def get_latest_frame(self) -> Optional[Dict]:
        """
        Obtiene el último frame procesado.
        
        Returns:
            Diccionario con frame y datos o None
        """
        try:
            return self.gesture_queue.get_nowait()
        except queue.Empty:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return {
                        'type': 'frame',
                        'image': self._latest_frame.copy(),
                        'gestures': list(self._latest_gestures),
                        'landmarks': self._latest_landmarks,
                        'timestamp': time.time(),
                        'stats': self._get_current_stats()
                    }
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pipeline."""
        return self._get_current_stats()
    
    def get_gesture_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de gestos."""
        return self.gesture_history[-limit:] if self.gesture_history else []
    
    def get_action_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de acciones."""
        return self.action_history[-limit:] if self.action_history else []
    
    def get_voice_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de comandos de voz."""
        return self.voice_history[-limit:] if self.voice_history else []
    
    def update_config(self, new_config: Dict):
        """Actualiza configuración dinámicamente."""
        logger.info("⚙️ Actualizando configuración...")
        
        # Actualizar configuración
        for key, value in new_config.items():
            if key in self.config and isinstance(self.config[key], dict) and isinstance(value, dict):
                self.config[key].update(value)
            else:
                self.config[key] = value
        
        # Reiniciar componentes si es necesario
        needs_restart = False
        
        if 'hand_detection' in new_config or 'arm_detection' in new_config:
            logger.info("🔄 Reiniciando detectores...")
            self._init_detectors()
            needs_restart = True
        
        if 'voice_recognition' in new_config and self.voice_recognizer:
            logger.info("🔄 Actualizando VoiceRecognizer...")
            try:
                self.voice_recognizer.update_config(new_config['voice_recognition'])
            except:
                pass
        
        # Actualizar GestureIntegrator si existe
        if self.gesture_integrator and hasattr(self.gesture_integrator, 'update_config'):
            try:
                self.gesture_integrator.update_config(new_config)
                logger.info("✅ Configuración actualizada en GestureIntegrator")
            except Exception as e:
                logger.error(f"❌ Error actualizando configuración en integrador: {e}")
        
        # Reiniciar si es necesario
        was_running = self.is_running
        if needs_restart and was_running:
            self.stop()
            self.start()
        
        self._emit_status("config_updated", new_config)
        logger.info("✅ Configuración actualizada")
    
    def _clear_queues(self):
        """Limpia todas las colas."""
        for q in [self.gesture_queue, self.action_queue, self.voice_queue, self.voice_command_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except (queue.Empty, queue.Full):
                    break
    
    def _emit_status(self, status_type: str, data: Dict = None):
        """Emite señal de cambio de estado."""
        if self.status_changed:
            self.status_changed.emit(status_type, data or {})
    
    def _emit_error(self, error_type: str, message: str):
        """Emite señal de error."""
        if self.error_occurred:
            self.error_occurred.emit(error_type, message)
        logger.error(f"🚨 [{error_type}] {message}")
    
    def set_gesture_integrator(self, integrator):
        """
        Establece el GestureIntegrator para el pipeline.
        
        Args:
            integrator: Instancia de GestureIntegrator
        """
        try:
            self.gesture_integrator = integrator
            
            # Conectar integrador con pipeline
            if hasattr(integrator, 'set_pipeline'):
                integrator.set_pipeline(self)
            
            # Conectar con ProfileRuntime si ya está cargado
            if self.profile_runtime and hasattr(integrator, 'set_profile_runtime'):
                integrator.set_profile_runtime(self.profile_runtime)
            
            # Conectar con ActionExecutor si está disponible
            if self.action_executor and hasattr(integrator, 'set_action_executor'):
                integrator.set_action_executor(self.action_executor)
            
            # Registrar detectores e interpretadores en el integrador
            self._register_components_with_integrator()
            
            logger.info("✅ GestureIntegrator configurado en pipeline")
            
        except Exception as e:
            logger.error(f"❌ Error configurando GestureIntegrator: {e}")
    
    def _register_components_with_integrator(self):
        """Registra componentes en el GestureIntegrator."""
        if not self.gesture_integrator:
            return
        
        try:
            # Registrar detectores
            if self.hand_detector and hasattr(self.gesture_integrator, 'register_detector'):
                self.gesture_integrator.register_detector('hand', self.hand_detector)
                logger.info("✅ HandDetector registrado en GestureIntegrator")
            
            if self.arm_detector and hasattr(self.gesture_integrator, 'register_detector'):
                self.gesture_integrator.register_detector('arm', self.arm_detector)
                logger.info("✅ ArmDetector registrado en GestureIntegrator")
            
            # Registrar interpretadores
            try:
                from interpreters.hand_interpreter import HandInterpreter
                hand_interpreter = HandInterpreter(gesture_threshold=0.7)
                if hasattr(self.gesture_integrator, 'register_interpreter'):
                    self.gesture_integrator.register_interpreter('hand', hand_interpreter)
                    logger.info("✅ HandInterpreter registrado en GestureIntegrator")
            except ImportError:
                logger.warning("⚠️ No se pudo importar HandInterpreter")
            
            try:
                from interpreters.arm_interpreter import ArmInterpreter
                arm_interpreter = ArmInterpreter(gesture_threshold=0.6)
                if hasattr(self.gesture_integrator, 'register_interpreter'):
                    self.gesture_integrator.register_interpreter('arm', arm_interpreter)
                    logger.info("✅ ArmInterpreter registrado en GestureIntegrator")
            except ImportError:
                logger.warning("⚠️ No se pudo importar ArmInterpreter")
            
            try:
                from interpreters.voice_interpreter import VoiceInterpreter
                voice_interpreter = VoiceInterpreter(
                    language=self.config.get('voice_recognition', {}).get('language', 'es-ES')
                )
                if hasattr(self.gesture_integrator, 'register_interpreter'):
                    self.gesture_integrator.register_interpreter('voice', voice_interpreter)
                    logger.info("✅ VoiceInterpreter registrado en GestureIntegrator")
            except ImportError:
                logger.warning("⚠️ No se pudo importar VoiceInterpreter")
            
        except Exception as e:
            logger.error(f"❌ Error registrando componentes en integrador: {e}")
    
    def set_active_profile(self, profile_name: str) -> bool:
        """
        Cambia el perfil activo dinámicamente.
        
        Args:
            profile_name: Nombre del nuevo perfil
            
        Returns:
            True si se cambió correctamente
        """
        logger.info(f"🔄 Cambiando perfil a: {profile_name}")
        
        # Guardar estado actual
        was_running = self.is_running
        
        # Detener si está corriendo
        if was_running:
            self.stop()
        
        # Cargar nuevo perfil
        success = self.load_profile(profile_name)
        
        # Reanudar si estaba corriendo
        if was_running and success:
            self.start()
        
        return success
    
    def _init_detectors(self):
        """Reinicializa detectores."""
        # Hand Detector
        try:
            hand_config = self.config.get('hand_detection', {})
            if hand_config.get('enabled', True):
                from detectors.hand_detector import HandDetector
                
                if self.hand_detector:
                    if hasattr(self.hand_detector, 'release'):
                        self.hand_detector.release()
                
                self.hand_detector = HandDetector(
                    max_num_hands=hand_config.get('max_num_hands', 2),
                    min_detection_confidence=hand_config.get('min_detection_confidence', 0.7),
                    min_tracking_confidence=hand_config.get('min_tracking_confidence', 0.5),
                    model_complexity=hand_config.get('model_complexity', 1)
                )
                
                # Reconfigurar gestos activos si hay perfil
                if self.profile_runtime and hasattr(self.hand_detector, 'set_active_gestures'):
                    active_gestures = self.profile_runtime.get_all_gestures()
                    self.hand_detector.set_active_gestures(active_gestures)
        except Exception as e:
            logger.error(f"❌ Error reinicializando HandDetector: {e}")
    
    def get_component_status(self) -> Dict[str, Any]:
        """Obtiene estado de todos los componentes."""
        return {
            'hand_detector': self.hand_detector is not None,
            'arm_detector': self.arm_detector is not None,
            'voice_recognizer': self.voice_recognizer is not None,
            'action_executor': self.action_executor is not None,
            'config_loader': self.config_loader is not None,
            'profile_runtime': self.profile_runtime is not None,
            'gesture_integrator': self.gesture_integrator is not None,
            'current_profile': self.current_profile_name,
            'is_running': self.is_running,
            'camera_active': self._camera_active,
            'processing_active': self._processing_active
        }
    
    def execute_test_action(self, action_type: str, command: str) -> Dict[str, Any]:
        """
        Ejecuta una acción de prueba (para debugging).
        
        Args:
            action_type: Tipo de acción (keyboard, mouse, bash, window)
            command: Comando a ejecutar
            
        Returns:
            Resultado de la ejecución
        """
        if not self.action_executor:
            return {'success': False, 'error': 'ActionExecutor no disponible'}
        
        test_action = {
            'type': action_type,
            'command': command,
            'description': f'Prueba: {action_type} - {command}',
            'timestamp': time.time(),
            'test': True
        }
        
        return self.action_executor.execute(test_action)
    
    def reconfigure(self, changes: Dict[str, Any]):
        """
        Reconfigura el pipeline con nuevos ajustes.
        Alias para update_config para compatibilidad con MainWindow.
        """
        logger.info(f"⚙️ Reconfigurando pipeline: {list(changes.keys())}")
        self.update_config(changes)
    
    def reconfigure_detectors(self, detector_changes: Dict[str, Any]):
        """Reconfigura detectores específicos."""
        self.update_config({'hand_detection': detector_changes.get('hand', {}),
                           'arm_detection': detector_changes.get('arm', {})})
    
    def reconfigure_controllers(self, controller_changes: Dict[str, Any]):
        """Reconfigura controladores específicos."""
        if 'controllers' not in self.config:
            self.config['controllers'] = {}
        
        for controller_type, changes in controller_changes.items():
            if controller_type not in self.config['controllers']:
                self.config['controllers'][controller_type] = {}
            self.config['controllers'][controller_type].update(changes)
    
    def is_camera_active(self) -> bool:
        """Verifica si la cámara está activa."""
        return self._camera_active
    
    def cleanup(self):
        """Limpia todos los recursos."""
        logger.info("🧹 Limpiando GesturePipeline...")
        
        # Detener pipeline
        self.stop()
        
        # Liberar detectores
        if self.hand_detector and hasattr(self.hand_detector, 'release'):
            try:
                self.hand_detector.release()
            except:
                pass
        
        if self.arm_detector and hasattr(self.arm_detector, 'release'):
            try:
                self.arm_detector.release()
            except:
                pass
        
        # Limpiar GestureIntegrator
        if self.gesture_integrator and hasattr(self.gesture_integrator, 'cleanup'):
            try:
                self.gesture_integrator.cleanup()
            except:
                pass
        
        # Limpiar controladores
        if self.action_executor and hasattr(self.action_executor, 'cleanup'):
            try:
                self.action_executor.cleanup()
            except:
                pass
        
        # Limpiar VoiceRecognizer
        if self.voice_recognizer and hasattr(self.voice_recognizer, 'cleanup'):
            try:
                self.voice_recognizer.cleanup()
            except:
                pass
        
        # Limpiar datos
        self._clear_queues()
        self.clear_buffers()
        
        with self._frame_lock:
            self._latest_frame = None
            self._latest_gestures = []
            self._latest_landmarks = []
        
        self.gesture_history.clear()
        self.action_history.clear()
        self.voice_history.clear()
        self.gesture_cooldowns.clear()
        
        logger.info("✅ GesturePipeline limpiado correctamente")


# Ejemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuración de prueba
    test_config = {
        'active_profile': 'gamer',
        'camera': {
            'device_id': 0,
            'width': 640,
            'height': 480,
            'fps': 30,
            'mirror': True
        },
        'hand_detection': {
            'enabled': True,
            'max_num_hands': 2,
            'min_detection_confidence': 0.7,
            'min_tracking_confidence': 0.5
        },
        'voice_recognition': {
            'enabled': True,
            'activation_word': 'nyx',
            'language': 'es-ES',
            'energy_threshold': 300,
            'pause_threshold': 0.8,
            'dynamic_energy_threshold': True
        }
    }
    
    # Crear pipeline
    print("🎮 Creando GesturePipeline...")
    pipeline = GesturePipeline(test_config)
    
    # Cargar perfil
    print("📥 Cargando perfil gamer...")
    if pipeline.load_profile('gamer'):
        print("✅ Perfil cargado")
        
        # Mostrar estado
        status = pipeline.get_component_status()
        print(f"📊 Estado componentes: {status}")
        
        # Iniciar pipeline
        print("▶️ Iniciando pipeline (10 segundos)...")
        pipeline.start()
        
        # Esperar un poco
        import time
        time.sleep(10)
        
        # Obtener estadísticas
        stats = pipeline.get_stats()
        print(f"\n📊 Estadísticas después de 10 segundos:")
        print(f"  FPS: {stats['fps']}")
        print(f"  Frames procesados: {stats['frame_count']}")
        print(f"  Gestos detectados: {stats['gestures_detected']}")
        print(f"  Comandos de voz: {stats['voice_commands']}")
        print(f"  Activaciones de voz: {stats['voice_activations']}")
        
        # Obtener buffers de integración
        gesture_buffer = pipeline.get_gesture_buffer()
        voice_buffer = pipeline.get_voice_buffer()
        action_buffer = pipeline.get_action_buffer()
        print(f"  Buffer de gestos: {len(gesture_buffer)}")
        print(f"  Buffer de voz: {len(voice_buffer)}")
        print(f"  Buffer de acciones: {len(action_buffer)}")
        
        # Obtener historial de voz
        voice_history = pipeline.get_voice_history(5)
        if voice_history:
            print(f"\n🎤 Últimos {len(voice_history)} comandos de voz:")
            for i, cmd in enumerate(voice_history):
                print(f"  {i+1}. {cmd.get('text', 'Sin texto')}")
        
        # Detener
        print("\n⏹️ Deteniendo pipeline...")
        pipeline.stop()
        
        # Limpiar
        pipeline.cleanup()
        print("✅ Prueba completada")
    else:
        print("❌ Error cargando perfil")