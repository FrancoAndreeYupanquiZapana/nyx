"""
🧠 GESTURE INTEGRATOR - Coordina detectores e interpretadores NYX
===============================================================
Conecta todos los detectores con sus interpretadores y el pipeline principal.
Maneja sincronización, priorización, fusión de gestos y mapeo a acciones.
"""

import time
import threading
import queue
from typing import Dict, List, Optional, Any, Tuple
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class GesturePriority(Enum):
    """Prioridades de gestos para resolución de conflictos."""
    HIGH = 3      # Gestos críticos (emergencia, activación)
    MEDIUM = 2    # Gestos de control principal
    LOW = 1       # Gestos de navegación/ajuste
    BACKGROUND = 0 # Gestos de contexto


class GestureType(Enum):
    """Tipos de gestos reconocidos."""
    HAND = "hand"
    ARM = "arm"
    POSE = "pose"
    VOICE = "voice"
    COMBINED = "combined"


class GestureIntegrator:
    """
    Integra todos los detectores e interpretadores del sistema NYX.
    Versión completa y robusta combinando ambas implementaciones.
    """
    
    def __init__(self, config: Dict):
        """
        Inicializa el integrador de gestos.
        
        Args:
            config: Configuración del sistema
        """
        self.config = config
        
        # Componentes registrados
        self.detectors = {}      # Dict[str, detector]: {'arm': ArmDetector, 'hand': HandDetector}
        self.interpreters = {}   # Dict[str, interpreter]: {'arm': ArmInterpreter, 'hand': GestureInterpreter}
        
        # Referencias a otros componentes
        self.pipeline = None          # Referencia a GesturePipeline
        self.profile_runtime = None   # Referencia a ProfileRuntime
        self.action_executor = None   # Referencia a ActionExecutor (opcional)
        
        # Colas para comunicación
        self.detection_queue = queue.Queue(maxsize=100)    # Detecciones crudas
        self.interpretation_queue = queue.Queue(maxsize=50) # Gestos interpretados
        self.action_queue = queue.Queue(maxsize=20)        # Acciones listas para ejecutar
        
        # Hilos de procesamiento
        self.integration_thread = None
        self.processing_thread = None
        self.action_thread = None
        self.running = False
        
        # Estado del sistema
        self.active_detectors = set()    # Detectores activos
        self.active_interpreters = set() # Interpretadores activos
        self.current_profile = None      # Perfil actual
        self.gesture_mappings = {}       # Mapeos cargados
        
        # Historial para estabilización y depuración
        self.gesture_history = []
        self.detection_history = []
        self.action_history = []
        self.max_history = 100
        
        # Configuración
        self.enable_arm_detection = config.get('arm_detection', {}).get('enabled', False)
        self.enable_hand_detection = config.get('hand_detection', {}).get('enabled', True)
        self.gesture_timeout = 0.5       # Timeout para gestos (segundos)
        self.conflict_resolution_enabled = True
        self.min_gesture_confidence = config.get('general', {}).get('min_gesture_confidence', 0.6)
        
        # Bloqueos para acceso seguro a recursos compartidos
        self.lock = threading.RLock()
        self.stats_lock = threading.Lock()
        
        # Estadísticas
        self.stats = {
            'total_detections': 0,
            'total_interpretations': 0,
            'total_actions_queued': 0,
            'total_actions_executed': 0,
            'gestures_per_second': 0,
            'avg_processing_time': 0.0,
            'detector_stats': {},
            'interpreter_stats': {},
            'errors': 0,
            'queue_overflows': 0
        }
        
        # Para cálculo de FPS y métricas
        self.frame_times = []
        self.processing_times = []
        self.start_time = time.time()
        
        logger.info("✅ GestureIntegrator inicializado (versión completa)")
    
    # ========== REGISTRO DE COMPONENTES ==========
    
    def register_detector(self, name: str, detector: Any):
        """
        Registra un detector en el integrador.
        
        Args:
            name: Nombre del detector ('hand', 'arm', 'pose', 'voice')
            detector: Instancia del detector
        """
        with self.lock:
            self.detectors[name] = detector
            self.active_detectors.add(name)
            logger.info(f"✅ Detector '{name}' registrado")
    
    def register_interpreter(self, name: str, interpreter: Any):
        """
        Registra un intérprete en el integrador.
        
        Args:
            name: Nombre del intérprete ('hand', 'arm', 'voice')
            interpreter: Instancia del intérprete
        """
        with self.lock:
            self.interpreters[name] = interpreter
            self.active_interpreters.add(name)
            logger.info(f"✅ Intérprete '{name}' registrado")
    
    def set_pipeline(self, pipeline):
        """Establece referencia al GesturePipeline."""
        self.pipeline = pipeline
    
    def set_profile_runtime(self, profile_runtime):
        """Establece referencia al ProfileRuntime."""
        self.profile_runtime = profile_runtime
    
    def set_action_executor(self, action_executor):
        """Establece referencia al ActionExecutor (opcional)."""
        self.action_executor = action_executor
    
    # ========== CONTROL DEL SISTEMA ==========
    
    def start(self):
        """Inicia todos los hilos de procesamiento del integrador."""
        if self.running:
            logger.warning("⚠️ GestureIntegrator ya está en ejecución")
            return
        
        self.running = True
        
        # Iniciar hilo de integración (procesa detecciones)
        self.integration_thread = threading.Thread(
            target=self._integration_loop,
            name="GestureIntegrationThread",
            daemon=True
        )
        self.integration_thread.start()
        
        # Iniciar hilo de procesamiento (interpreta gestos)
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            name="GestureProcessingThread",
            daemon=True
        )
        self.processing_thread.start()
        
        # Iniciar hilo de acciones (ejecuta acciones)
        self.action_thread = threading.Thread(
            target=self._action_loop,
            name="GestureActionThread",
            daemon=True
        )
        self.action_thread.start()
        
        logger.info("▶️ GestureIntegrator iniciado con 3 hilos")
    
    def stop(self):
        """Detiene todos los hilos de procesamiento."""
        self.running = False
        
        # Esperar a que terminen los hilos
        threads = [self.integration_thread, self.processing_thread, self.action_thread]
        for thread in threads:
            if thread:
                thread.join(timeout=2.0)
        
        # Limpiar colas
        self._clear_queues()
        
        logger.info("⏹️ GestureIntegrator detenido")
    
    # ========== INTERFAZ PRINCIPAL ==========
    
    def process_frame(self, frame, frame_data: Dict = None):
        """
        Procesa un frame a través de todos los detectores activos.
        
        Args:
            frame: Frame de imagen
            frame_data: Datos adicionales del frame
        """
        if not self.running:
            return
        
        frame_data = frame_data or {}
        frame_data['timestamp'] = time.time()
        
        # Procesar en paralelo con cada detector activo
        for detector_name, detector in self.detectors.items():
            if detector_name not in self.active_detectors:
                continue
            
            try:
                # Ejecutar detección
                detection_result = detector.detect(frame.copy())
                
                if detection_result:
                    # Agregar metadatos
                    detection_result['detector'] = detector_name
                    detection_result['timestamp'] = frame_data['timestamp']
                    detection_result['frame_id'] = frame_data.get('frame_id', 0)
                    
                    # Encolar para procesamiento
                    try:
                        self.detection_queue.put(detection_result, timeout=0.01)
                        with self.stats_lock:
                            self.stats['total_detections'] += 1
                    except queue.Full:
                        with self.stats_lock:
                            self.stats['queue_overflows'] += 1
                        logger.warning(f"⚠️ Cola de detecciones llena, descartando")
                        
            except Exception as e:
                logger.error(f"❌ Error en detector {detector_name}: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
    
    def process_detection(self, detector_name: str, detection_data: Dict):
        """
        Método alternativo: procesa una detección directamente.
        Útil para detectores que no procesan frames (ej: voz).
        
        Args:
            detector_name: Nombre del detector
            detection_data: Datos de detección
        """
        if not self.running:
            return
        
        # Agregar metadatos
        detection_data['detector'] = detector_name
        detection_data['timestamp'] = time.time()
        
        # Encolar para procesamiento
        try:
            self.detection_queue.put(detection_data, timeout=0.01)
            with self.stats_lock:
                self.stats['total_detections'] += 1
        except queue.Full:
            with self.stats_lock:
                self.stats['queue_overflows'] += 1
            logger.warning(f"⚠️ Cola de detecciones llena, descartando detección de {detector_name}")
    
    # ========== BUCLES DE PROCESAMIENTO ==========
    
    def _integration_loop(self):
        """Bucle de integración: procesa detecciones crudas."""
        logger.debug("🔄 Iniciando bucle de integración")
        
        while self.running:
            try:
                start_time = time.time()
                
                # Obtener todas las detecciones disponibles (hasta 10)
                detections = []
                while not self.detection_queue.empty() and len(detections) < 10:
                    try:
                        detection = self.detection_queue.get(timeout=0.01)
                        detections.append(detection)
                        self.detection_queue.task_done()
                    except queue.Empty:
                        break
                
                if not detections:
                    time.sleep(0.001)  # Pequeña pausa para no saturar CPU
                    continue
                
                # Agregar al historial
                self._add_to_detection_history(detections)
                
                # Procesar detecciones por tipo
                grouped_detections = self._group_detections_by_type(detections)
                
                # Enviar a interpretadores correspondientes
                self._route_to_interpreters(grouped_detections)
                
                # Actualizar estadísticas
                processing_time = time.time() - start_time
                self.processing_times.append(processing_time)
                if len(self.processing_times) > 30:
                    self.processing_times.pop(0)
                
                with self.stats_lock:
                    self.stats['avg_processing_time'] = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
                
            except Exception as e:
                logger.error(f"❌ Error en bucle de integración: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
                time.sleep(0.1)
    
    def _processing_loop(self):
        """Bucle de procesamiento: interpreta gestos y crea acciones."""
        logger.debug("🔄 Iniciando bucle de procesamiento")
        
        while self.running:
            try:
                # Obtener gesto interpretado
                gesture = self.interpretation_queue.get(timeout=0.1)
                self.interpretation_queue.task_done()
                
                # Validar gesto
                if not self._validate_gesture(gesture):
                    continue
                
                # Resolver conflictos con gestos previos
                if self.conflict_resolution_enabled:
                    if not self._resolve_conflicts(gesture):
                        continue
                
                # Agregar al historial
                self._add_to_gesture_history(gesture)
                
                # Si tiene acción mapeada, enviar a cola de acciones
                if gesture.get('mapped', False):
                    action_data = self._create_action_data(gesture)
                    
                    try:
                        self.action_queue.put(action_data, timeout=0.01)
                        with self.stats_lock:
                            self.stats['total_actions_queued'] += 1
                    except queue.Full:
                        logger.warning(f"⚠️ Cola de acciones llena, descartando acción")
                
                # Notificar al pipeline si está disponible
                if self.pipeline and hasattr(self.pipeline, 'handle_interpreted_gesture'):
                    try:
                        self.pipeline.handle_interpreted_gesture(gesture)
                    except Exception as e:
                        logger.debug(f"⚠️ Pipeline no pudo manejar gesto: {e}")
                
                # Emitir señal de gesto detectado (para UI)
                self._emit_gesture_signal(gesture)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de procesamiento: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
    
    def _action_loop(self):
        """Bucle de acciones: procesa y ejecuta acciones."""
        logger.debug("🔄 Iniciando bucle de acciones")
        
        while self.running:
            try:
                # Obtener acción de la cola
                action = self.action_queue.get(timeout=0.1)
                self.action_queue.task_done()
                
                # Agregar al historial
                self._add_to_action_history(action)
                
                # Ejecutar acción si tenemos ActionExecutor
                if self.action_executor and hasattr(self.action_executor, 'execute_action'):
                    try:
                        self.action_executor.execute_action(action)
                        with self.stats_lock:
                            self.stats['total_actions_executed'] += 1
                    except Exception as e:
                        logger.error(f"❌ Error ejecutando acción: {e}")
                        with self.stats_lock:
                            self.stats['errors'] += 1
                
                # Notificar al pipeline
                if self.pipeline and hasattr(self.pipeline, 'handle_action_executed'):
                    try:
                        self.pipeline.handle_action_executed(action)
                    except Exception as e:
                        logger.debug(f"⚠️ Pipeline no pudo manejar acción ejecutada: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de acciones: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _group_detections_by_type(self, detections: List[Dict]) -> Dict[str, List]:
        """Agrupa detecciones por tipo."""
        grouped = {
            'hand': [],
            'arm': [],
            'pose': [],
            'voice': []
        }
        
        for detection in detections:
            detector_type = detection.get('detector', '')
            
            if 'hand' in detector_type:
                grouped['hand'].append(detection)
            elif 'arm' in detector_type:
                grouped['arm'].append(detection)
            elif 'pose' in detector_type:
                grouped['pose'].append(detection)
            elif 'voice' in detector_type:
                grouped['voice'].append(detection)
        
        return grouped
    
    def _route_to_interpreters(self, grouped_detections: Dict[str, List]):
        """Envía detecciones a los interpretadores correspondientes."""
        for detection_type, detections in grouped_detections.items():
            if not detections:
                continue
            
            interpreter_name = detection_type
            if interpreter_name not in self.interpreters:
                continue
            
            interpreter = self.interpreters[interpreter_name]
            
            try:
                # Interpretar detecciones
                interpreted_gestures = interpreter.interpret(detections)
                
                if interpreted_gestures:
                    # Agregar contexto adicional
                    for gesture in interpreted_gestures:
                        gesture['source'] = interpreter_name
                        gesture['detection_count'] = len(detections)
                        gesture['timestamp'] = time.time()
                        
                        # Aplicar mapeo de perfil si está disponible
                        self._apply_profile_mapping(gesture)
                    
                    # Encolar gestos interpretados
                    for gesture in interpreted_gestures:
                        try:
                            self.interpretation_queue.put(gesture, timeout=0.01)
                            with self.stats_lock:
                                self.stats['total_interpretations'] += 1
                        except queue.Full:
                            logger.warning(f"⚠️ Cola de interpretaciones llena, descartando gesto")
                        
            except Exception as e:
                logger.error(f"❌ Error en intérprete {interpreter_name}: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
    
    def _apply_profile_mapping(self, gesture: Dict):
        """Aplica mapeo de perfil a un gesto."""
        if not self.profile_runtime or not self.current_profile:
            gesture['mapped'] = False
            return
        
        gesture_name = gesture.get('gesture')
        gesture_type = gesture.get('type')
        
        # Buscar mapeo en el perfil activo
        mapping = None
        if hasattr(self.profile_runtime, 'get_gesture_mapping'):
            mapping = self.profile_runtime.get_gesture_mapping(gesture_name, gesture_type)
        
        if mapping:
            gesture['action'] = mapping.get('action')
            gesture['command'] = mapping.get('command')
            gesture['action_description'] = mapping.get('description', '')
            gesture['action_data'] = mapping
            gesture['mapped'] = True
        else:
            gesture['mapped'] = False
    
    def _validate_gesture(self, gesture: Dict) -> bool:
        """Valida un gesto interpretado."""
        # Validaciones básicas
        required_fields = ['gesture', 'type', 'confidence', 'timestamp']
        if not all(field in gesture for field in required_fields):
            return False
        
        # Validar confianza mínima
        if gesture.get('confidence', 0) < self.min_gesture_confidence:
            return False
        
        # Validar timestamp (no demasiado viejo)
        max_age = 1.0  # 1 segundo
        if time.time() - gesture.get('timestamp', 0) > max_age:
            return False
        
        return True
    
    def _resolve_conflicts(self, new_gesture: Dict) -> bool:
        """Resuelve conflictos entre gestos nuevos y previos."""
        if not self.gesture_history:
            return True
        
        # Obtener gestos recientes (último segundo)
        recent_gestures = [
            g for g in self.gesture_history[-5:]
            if time.time() - g.get('timestamp', 0) < 1.0
        ]
        
        if not recent_gestures:
            return True
        
        # Reglas de resolución de conflictos
        new_gesture_name = new_gesture.get('gesture')
        new_gesture_type = new_gesture.get('type')
        
        for recent_gesture in recent_gestures:
            recent_name = recent_gesture.get('gesture')
            recent_type = recent_gesture.get('type')
            
            # Mismo gesto muy rápido = posible duplicado
            if (new_gesture_name == recent_name and 
                new_gesture_type == recent_type):
                time_diff = new_gesture['timestamp'] - recent_gesture['timestamp']
                if time_diff < 0.3:  # Menos de 300ms
                    logger.debug(f"⚠️ Gesto duplicado filtrado: {new_gesture_name}")
                    return False
            
            # Conflictos mano/brazo
            if (new_gesture_type == 'hand' and recent_type == 'arm' or
                new_gesture_type == 'arm' and recent_type == 'hand'):
                # Si hay gesto de brazo activo, priorizar sobre mano
                if 'arms' in recent_name and 'continuous' in recent_gesture:
                    logger.debug(f"⚠️ Gesto de mano ignorado por brazo activo")
                    return False
        
        return True
    
    def _create_action_data(self, gesture: Dict) -> Dict:
        """Crea datos de acción a partir de un gesto."""
        return {
            'type': 'gesture',
            'gesture': gesture['gesture'],
            'action': gesture.get('action'),
            'command': gesture.get('command'),
            'confidence': gesture.get('confidence', 0.5),
            'timestamp': time.time(),
            'source': gesture.get('source', 'unknown'),
            'gesture_data': gesture
        }
    
    def _emit_gesture_signal(self, gesture: Dict):
        """Emite señal de gesto detectado (para UI)."""
        # Esto se conectará con señales PyQt6 más tarde
        if self.pipeline and hasattr(self.pipeline, 'emit_gesture_signal'):
            try:
                self.pipeline.emit_gesture_signal(gesture)
            except:
                pass
    
    # ========== MANEJO DE HISTORIAL ==========
    
    def _add_to_detection_history(self, detections: List[Dict]):
        """Agrega detecciones al historial."""
        with self.lock:
            for detection in detections[-5:]:  # Solo últimas 5
                self.detection_history.append({
                    'detector': detection.get('detector'),
                    'timestamp': detection.get('timestamp'),
                    'gestures': detection.get('gestures', []),
                    'frame_id': detection.get('frame_id', 0)
                })
            
            # Mantener tamaño máximo
            if len(self.detection_history) > self.max_history:
                self.detection_history = self.detection_history[-self.max_history:]
    
    def _add_to_gesture_history(self, gesture: Dict):
        """Agrega gesto al historial."""
        with self.lock:
            self.gesture_history.append(gesture.copy())
            if len(self.gesture_history) > self.max_history:
                self.gesture_history.pop(0)
    
    def _add_to_action_history(self, action: Dict):
        """Agrega acción al historial."""
        with self.lock:
            self.action_history.append(action.copy())
            if len(self.action_history) > self.max_history:
                self.action_history.pop(0)
    
    def _clear_queues(self):
        """Limpia todas las colas."""
        while not self.detection_queue.empty():
            try:
                self.detection_queue.get_nowait()
                self.detection_queue.task_done()
            except queue.Empty:
                break
        
        while not self.interpretation_queue.empty():
            try:
                self.interpretation_queue.get_nowait()
                self.interpretation_queue.task_done()
            except queue.Empty:
                break
        
        while not self.action_queue.empty():
            try:
                self.action_queue.get_nowait()
                self.action_queue.task_done()
            except queue.Empty:
                break
    
    # ========== INTERFAZ PÚBLICA ==========
    
    def get_actions(self, max_actions: int = 10) -> List[Dict]:
        """
        Obtiene acciones pendientes de procesar.
        
        Args:
            max_actions: Máximo número de acciones a obtener
            
        Returns:
            Lista de acciones
        """
        actions = []
        while not self.action_queue.empty() and len(actions) < max_actions:
            try:
                action = self.action_queue.get_nowait()
                actions.append(action)
                self.action_queue.task_done()
            except queue.Empty:
                break
        return actions
    
    def get_gestures(self, max_gestures: int = 10) -> List[Dict]:
        """
        Obtiene gestos interpretados pendientes.
        
        Args:
            max_gestures: Máximo número de gestos a obtener
            
        Returns:
            Lista de gestos
        """
        gestures = []
        while not self.interpretation_queue.empty() and len(gestures) < max_gestures:
            try:
                gesture = self.interpretation_queue.get_nowait()
                gestures.append(gesture)
                self.interpretation_queue.task_done()
            except queue.Empty:
                break
        return gestures
    
    def load_profile(self, profile_data: Dict):
        """
        Carga un perfil en el integrador y sus interpretadores.
        
        Args:
            profile_data: Datos del perfil
        """
        with self.lock:
            self.current_profile = profile_data.get('profile_name')
            
            # Guardar mapeos globales
            self.gesture_mappings = profile_data.get('gestures', {}).copy()
            
            # Separar gestos por tipo
            gestures = profile_data.get('gestures', {})
            hand_gestures = {}
            arm_gestures = {}
            pose_gestures = {}
            
            for gesture_name, gesture_data in gestures.items():
                gesture_type = gesture_data.get('type', 'hand')
                
                if gesture_type == 'hand':
                    hand_gestures[gesture_name] = gesture_data
                elif gesture_type == 'arm':
                    arm_gestures[gesture_name] = gesture_data
                elif gesture_type == 'pose':
                    pose_gestures[gesture_name] = gesture_data
            
            # Cargar en interpretadores correspondientes
            if 'hand' in self.interpreters and hand_gestures:
                self.interpreters['hand'].load_gesture_mappings(hand_gestures)
            
            if 'arm' in self.interpreters and arm_gestures:
                self.interpreters['arm'].load_gesture_mappings(arm_gestures)
            
            if 'pose' in self.interpreters and pose_gestures:
                self.interpreters['pose'].load_gesture_mappings(pose_gestures)
            
            logger.info(f"✅ Perfil '{self.current_profile}' cargado en integrador")
    
    def get_gesture_history(self, max_items: int = 10) -> List[Dict]:
        """
        Obtiene historial de gestos recientes.
        
        Args:
            max_items: Máximo número de items a retornar
            
        Returns:
            Lista de gestos recientes
        """
        with self.lock:
            return self.gesture_history[-max_items:]
    
    def get_detection_history(self, max_items: int = 5) -> List[Dict]:
        """
        Obtiene historial de detecciones recientes.
        
        Args:
            max_items: Máximo número de items a retornar
            
        Returns:
            Lista de detecciones recientes
        """
        with self.lock:
            return self.detection_history[-max_items:]
    
    def get_action_history(self, max_items: int = 5) -> List[Dict]:
        """
        Obtiene historial de acciones recientes.
        
        Args:
            max_items: Máximo número de items a retornar
            
        Returns:
            Lista de acciones recientes
        """
        with self.lock:
            return self.action_history[-max_items:]
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas actuales completas."""
        with self.stats_lock:
            current_time = time.time()
            
            # Calcular FPS
            self.frame_times.append(current_time)
            self.frame_times = [t for t in self.frame_times if current_time - t < 2.0]
            
            if len(self.frame_times) > 1:
                fps = len(self.frame_times) / (self.frame_times[-1] - self.frame_times[0])
                self.stats['gestures_per_second'] = round(fps, 1)
            
            stats = self.stats.copy()
            stats['active_detectors'] = list(self.active_detectors)
            stats['active_interpreters'] = list(self.active_interpreters)
            stats['current_profile'] = self.current_profile
            stats['queue_sizes'] = {
                'detection_queue': self.detection_queue.qsize(),
                'interpretation_queue': self.interpretation_queue.qsize(),
                'action_queue': self.action_queue.qsize()
            }
            stats['history_sizes'] = {
                'gesture_history': len(self.gesture_history),
                'detection_history': len(self.detection_history),
                'action_history': len(self.action_history)
            }
            stats['uptime'] = round(current_time - self.start_time, 1)
            
            return stats
    
    def enable_detector(self, detector_name: str, enabled: bool = True):
        """Habilita o deshabilita un detector."""
        with self.lock:
            if enabled:
                self.active_detectors.add(detector_name)
            else:
                self.active_detectors.discard(detector_name)
            logger.info(f"🔄 Detector '{detector_name}' {'habilitado' if enabled else 'deshabilitado'}")
    
    def enable_interpreter(self, interpreter_name: str, enabled: bool = True):
        """Habilita o deshabilita un intérprete."""
        with self.lock:
            if enabled:
                self.active_interpreters.add(interpreter_name)
            else:
                self.active_interpreters.discard(interpreter_name)
            logger.info(f"🔄 Intérprete '{interpreter_name}' {'habilitado' if enabled else 'deshabilitado'}")
    
    def clear_history(self):
        """Limpia todo el historial."""
        with self.lock:
            self.gesture_history.clear()
            self.detection_history.clear()
            self.action_history.clear()
            logger.info("🧹 Historial limpiado")
    
    def reset_stats(self):
        """Reinicia las estadísticas."""
        with self.stats_lock:
            self.stats = {
                'total_detections': 0,
                'total_interpretations': 0,
                'total_actions_queued': 0,
                'total_actions_executed': 0,
                'gestures_per_second': 0,
                'avg_processing_time': 0.0,
                'detector_stats': {},
                'interpreter_stats': {},
                'errors': 0,
                'queue_overflows': 0
            }
            self.start_time = time.time()
            logger.info("📊 Estadísticas reiniciadas")

    def process_voice_command(self, voice_data: Dict):
        """
        Procesa un comando de voz directamente (sin pasar por cola de detecciones).
        
        Args:
            voice_data: Datos del comando de voz
        """
        if not self.running or 'voice' not in self.interpreters:
            return
        
        try:
            # Agregar metadatos
            voice_data['detector'] = 'voice'
            voice_data['timestamp'] = time.time()
            
            # Enviar directamente al VoiceInterpreter
            interpreter = self.interpreters['voice']
            interpreted_action = interpreter.interpret(voice_data)
            
            if interpreted_action:
                interpreted_action['source'] = 'voice'
                interpreted_action['detection_count'] = 1
                
                # Aplicar mapeo de perfil
                if self.profile_runtime:
                    self._apply_profile_mapping(interpreted_action)
                
                # Encolar para procesamiento
                self.interpretation_queue.put(interpreted_action, timeout=0.01)
                
                logger.debug(f"🎤 Comando de voz procesado: {voice_data.get('text', '')}")
                
        except Exception as e:
            logger.error(f"❌ Error procesando comando de voz: {e}")