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
import json
import numpy as np
from collections import deque

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
        self.frame_times = deque(maxlen=30)
        self.processing_times = deque(maxlen=30)
        self.start_time = time.time()
        
        # Nuevas estructuras para funcionalidades faltantes
        self._initialize_missing_components()
        
        logger.info("✅ GestureIntegrator inicializado (versión completa)")
    
    def _initialize_missing_components(self):
        """Inicializa componentes faltantes identificados en el análisis."""
        # Buffer para gestos combinados (mano + brazo)
        self.combined_gesture_buffer = []
        self.max_combined_buffer = 5
        
        # Timeouts para diferentes tipos de gestos
        self.gesture_timeouts = {
            'hand': 0.3,
            'arm': 0.5,
            'pose': 0.8,
            'voice': 1.0,
            'combined': 0.4
        }
        
        # Configuración de fusión de gestos
        self.fusion_config = {
            'enable_hand_arm_fusion': True,
            'enable_multi_hand_fusion': True,
            'fusion_window_ms': 300,
            'min_fusion_confidence': 0.4
        }
        
        # Contexto de gestos recientes
        self.recent_gestures_context = {
            'last_hand_gesture': None,
            'last_arm_gesture': None,
            'last_voice_command': None,
            'continuous_gestures': {},
            'sequence_buffer': []
        }
        
        # Estado de gestos continuos (como swipe, zoom, etc.)
        self.continuous_gesture_states = {}
        
        # Temporizadores
        self.last_frame_time = 0
        self.last_gesture_emission = 0
        
        # Configuración de debounce
        self.debounce_config = {
            'same_gesture_ms': 300,
            'different_gesture_ms': 150,
            'enable_debounce': True
        }
    
    # ========== MÉTODOS FALTANTES IDENTIFICADOS ==========
    
    def _fuse_gestures(self, gestures: List[Dict]) -> List[Dict]:
        """
        Fusiona múltiples gestos detectados simultáneamente.
        
        Args:
            gestures: Lista de gestos a fusionar
            
        Returns:
            Lista de gestos fusionados
        """
        if not self.fusion_config['enable_hand_arm_fusion'] or len(gestures) < 2:
            return gestures
        
        fused_gestures = []
        processed_indices = set()
        
        current_time = time.time()
        
        # Buscar combinaciones mano-brazo
        for i, gesture1 in enumerate(gestures):
            if i in processed_indices:
                continue
                
            for j, gesture2 in enumerate(gestures[i+1:], start=i+1):
                if j in processed_indices:
                    continue
                
                # Verificar si son de tipos compatibles para fusión
                if self._are_gestures_fusible(gesture1, gesture2):
                    fused = self._create_fused_gesture(gesture1, gesture2)
                    if fused:
                        fused_gestures.append(fused)
                        processed_indices.add(i)
                        processed_indices.add(j)
                        break
        
        # Agregar gestos no fusionados
        for i, gesture in enumerate(gestures):
            if i not in processed_indices:
                fused_gestures.append(gesture)
        
        return fused_gestures
    
    def _are_gestures_fusible(self, gesture1: Dict, gesture2: Dict) -> bool:
        """Determina si dos gestos pueden fusionarse."""
        type1 = gesture1.get('type', '')
        type2 = gesture2.get('type', '')
        
        # Combinaciones válidas para fusión
        fusible_pairs = [
            ('hand', 'arm'),  # Mano + brazo
            ('left_hand', 'right_hand'),  # Dos manos
            ('hand', 'pose'),  # Mano + postura
        ]
        
        pair = (type1, type2)
        reverse_pair = (type2, type1)
        
        # Verificar si es una combinación fusible
        if pair in fusible_pairs or reverse_pair in fusible_pairs:
            # Verificar temporalidad (deben ser casi simultáneos)
            time_diff = abs(gesture1.get('timestamp', 0) - gesture2.get('timestamp', 0))
            return time_diff < (self.fusion_config['fusion_window_ms'] / 1000.0)
        
        return False
    
    def _create_fused_gesture(self, gesture1: Dict, gesture2: Dict) -> Optional[Dict]:
        """Crea un gesto fusionado a partir de dos gestos."""
        try:
            # Determinar tipos
            types = [gesture1.get('type', ''), gesture2.get('type', '')]
            
            # Crear gesto fusionado
            fused_gesture = {
                'type': 'combined',
                'timestamp': max(gesture1.get('timestamp', 0), gesture2.get('timestamp', 0)),
                'confidence': (gesture1.get('confidence', 0) + gesture2.get('confidence', 0)) / 2,
                'sources': [gesture1.get('type'), gesture2.get('type')],
                'original_gestures': [gesture1, gesture2],
                'detectors': [gesture1.get('detector', ''), gesture2.get('detector', '')]
            }
            
            # Combinar información específica según tipos
            if 'hand' in types and 'arm' in types:
                # Fusión mano-brazo
                hand_gesture = gesture1 if 'hand' in gesture1.get('type', '') else gesture2
                arm_gesture = gesture1 if 'arm' in gesture1.get('type', '') else gesture2
                
                fused_gesture.update({
                    'gesture': f"{hand_gesture.get('gesture', '')}_{arm_gesture.get('gesture', '')}",
                    'hand_data': hand_gesture,
                    'arm_data': arm_gesture,
                    'description': f"{hand_gesture.get('description', '')} con {arm_gesture.get('description', '')}"
                })
            
            elif 'left_hand' in types and 'right_hand' in types:
                # Fusión de dos manos
                fused_gesture.update({
                    'gesture': 'two_hand_' + gesture1.get('gesture', ''),
                    'left_hand': gesture1 if 'left' in gesture1.get('type', '') else gesture2,
                    'right_hand': gesture2 if 'right' in gesture2.get('type', '') else gesture1,
                    'description': f"Dos manos: {gesture1.get('description', '')}"
                })
            
            # Aplicar mapeo de perfil al gesto fusionado
            self._apply_profile_mapping(fused_gesture)
            
            return fused_gesture
            
        except Exception as e:
            logger.error(f"❌ Error creando gesto fusionado: {e}")
            return None
    
    def _update_continuous_gesture(self, gesture: Dict):
        """Actualiza el estado de un gesto continuo."""
        gesture_name = gesture.get('gesture', '')
        
        # Gestos que pueden ser continuos (swipe, zoom, rotate, etc.)
        continuous_gestures = ['swipe', 'pan', 'zoom', 'rotate', 'drag', 'scroll']
        
        is_continuous = any(cont_gesture in gesture_name for cont_gesture in continuous_gestures)
        
        if is_continuous:
            gesture_id = f"{gesture_name}_{gesture.get('type', '')}"
            
            if gesture_id not in self.continuous_gesture_states:
                # Iniciar nuevo gesto continuo
                self.continuous_gesture_states[gesture_id] = {
                    'start_time': time.time(),
                    'last_update': time.time(),
                    'gesture_data': gesture,
                    'update_count': 1
                }
            else:
                # Actualizar gesto continuo existente
                state = self.continuous_gesture_states[gesture_id]
                state['last_update'] = time.time()
                state['update_count'] += 1
                
                # Agregar datos acumulativos
                if 'delta_x' in gesture:
                    state.setdefault('total_delta_x', 0)
                    state['total_delta_x'] += gesture.get('delta_x', 0)
                
                if 'delta_y' in gesture:
                    state.setdefault('total_delta_y', 0)
                    state['total_delta_y'] += gesture.get('delta_y', 0)
                
                # Actualizar el gesto con información acumulada
                gesture['continuous'] = True
                gesture['continuous_duration'] = time.time() - state['start_time']
                gesture['continuous_updates'] = state['update_count']
                
                if 'total_delta_x' in state:
                    gesture['total_delta_x'] = state['total_delta_x']
                
                if 'total_delta_y' in state:
                    gesture['total_delta_y'] = state['total_delta_y']
    
    def _cleanup_continuous_gestures(self):
        """Limpia gestos continuos que han expirado."""
        current_time = time.time()
        expired_gestures = []
        
        for gesture_id, state in self.continuous_gesture_states.items():
            # Si no ha sido actualizado en más de 1 segundo, limpiar
            if current_time - state['last_update'] > 1.0:
                expired_gestures.append(gesture_id)
        
        for gesture_id in expired_gestures:
            del self.continuous_gesture_states[gesture_id]
    
    def _apply_debounce(self, gesture: Dict) -> bool:
        """Aplica debounce para evitar gestos duplicados demasiado rápido."""
        if not self.debounce_config['enable_debounce']:
            return True
        
        gesture_name = gesture.get('gesture', '')
        gesture_type = gesture.get('type', '')
        current_time = time.time()
        
        # Buscar gestos recientes del mismo tipo
        recent_same_gesture = None
        for g in reversed(self.gesture_history[-10:]):
            if g.get('gesture') == gesture_name and g.get('type') == gesture_type:
                recent_same_gesture = g
                break
        
        if recent_same_gesture:
            time_diff = current_time - recent_same_gesture.get('timestamp', 0)
            
            # Si es el mismo gesto muy reciente, aplicar debounce
            if time_diff < (self.debounce_config['same_gesture_ms'] / 1000.0):
                logger.debug(f"⏱️  Gestos duplicados muy rápido, ignorando: {gesture_name}")
                return False
        
        return True
    
    def _handle_gesture_sequence(self, gesture: Dict):
        """Maneja secuencias de gestos (como doble tap, combinaciones)."""
        current_time = time.time()
        gesture_name = gesture.get('gesture', '')
        
        # Agregar a buffer de secuencia
        self.recent_gestures_context['sequence_buffer'].append({
            'gesture': gesture_name,
            'timestamp': current_time,
            'type': gesture.get('type', ''),
            'data': gesture
        })
        
        # Mantener solo últimos 5 gestos en el buffer
        if len(self.recent_gestures_context['sequence_buffer']) > 5:
            self.recent_gestures_context['sequence_buffer'].pop(0)
        
        # Buscar patrones de secuencia
        sequence_patterns = self._detect_sequence_patterns()
        
        # Si se detecta un patrón, crear gesto combinado
        for pattern in sequence_patterns:
            combined_gesture = self._create_sequence_gesture(pattern)
            if combined_gesture:
                # Aplicar mapeo de perfil
                self._apply_profile_mapping(combined_gesture)
                
                # Encolar para procesamiento
                try:
                    self.interpretation_queue.put(combined_gesture, timeout=0.01)
                    logger.debug(f"🔄 Secuencia detectada: {pattern['name']}")
                except queue.Full:
                    pass
    
    def _detect_sequence_patterns(self) -> List[Dict]:
        """Detecta patrones en la secuencia de gestos recientes."""
        patterns = []
        buffer = self.recent_gestures_context['sequence_buffer']
        
        if len(buffer) < 2:
            return patterns
        
        # Patrón: doble tap
        if len(buffer) >= 2:
            last_two = buffer[-2:]
            if (last_two[0]['gesture'] == last_two[1]['gesture'] and 
                'tap' in last_two[0]['gesture'].lower() and
                last_two[1]['timestamp'] - last_two[0]['timestamp'] < 0.5):
                
                patterns.append({
                    'name': f"double_{last_two[0]['gesture']}",
                    'gestures': last_two,
                    'type': 'sequence'
                })
        
        # Patrón: gesto + gesto (combinación)
        if len(buffer) >= 2:
            gesture_combo = f"{buffer[-2]['gesture']}_{buffer[-1]['gesture']}"
            patterns.append({
                'name': gesture_combo,
                'gestures': buffer[-2:],
                'type': 'combination'
            })
        
        return patterns
    
    def _create_sequence_gesture(self, pattern: Dict) -> Optional[Dict]:
        """Crea un gesto a partir de un patrón de secuencia."""
        try:
            sequence_gesture = {
                'type': 'sequence',
                'gesture': pattern['name'],
                'timestamp': time.time(),
                'confidence': 0.8,  # Alta confianza para secuencias
                'sequence_data': pattern,
                'description': f"Secuencia: {pattern['name'].replace('_', ' → ')}"
            }
            
            return sequence_gesture
            
        except Exception as e:
            logger.error(f"❌ Error creando gesto de secuencia: {e}")
            return None
    
    def _prioritize_gestures(self, gestures: List[Dict]) -> List[Dict]:
        """Prioriza gestos según su importancia y contexto."""
        if not gestures:
            return []
        
        # Asignar prioridades
        prioritized = []
        for gesture in gestures:
            priority = self._calculate_gesture_priority(gesture)
            gesture['priority'] = priority
            prioritized.append(gesture)
        
        # Ordenar por prioridad (mayor primero)
        prioritized.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return prioritized
    
    def _calculate_gesture_priority(self, gesture: Dict) -> int:
        """Calcula la prioridad de un gesto."""
        base_priority = 0
        
        # Prioridad por tipo
        type_priority = {
            'voice': GesturePriority.HIGH.value,
            'combined': GesturePriority.HIGH.value,
            'emergency': GesturePriority.HIGH.value,
            'arm': GesturePriority.MEDIUM.value,
            'hand': GesturePriority.MEDIUM.value,
            'pose': GesturePriority.LOW.value,
            'sequence': GesturePriority.MEDIUM.value
        }
        
        gesture_type = gesture.get('type', '')
        base_priority = type_priority.get(gesture_type, GesturePriority.LOW.value)
        
        # Aumentar prioridad por confianza
        confidence = gesture.get('confidence', 0)
        if confidence > 0.8:
            base_priority += 1
        
        # Aumentar prioridad si es gesto crítico
        critical_gestures = ['emergency_stop', 'help', 'pause', 'activate']
        if any(crit_gesture in gesture.get('gesture', '').lower() 
               for crit_gesture in critical_gestures):
            base_priority += 2
        
        # Reducir prioridad si es gesto continuo repetido
        if gesture.get('continuous', False):
            base_priority -= 1
        
        return max(1, min(base_priority, 5))  # Limitar entre 1 y 5
    
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
                    # Aplicar fusión si hay múltiples gestos
                    if len(interpreted_gestures) > 1 and self.fusion_config['enable_multi_hand_fusion']:
                        interpreted_gestures = self._fuse_gestures(interpreted_gestures)
                    
                    # Aplicar debounce
                    interpreted_gestures = [g for g in interpreted_gestures 
                                           if self._apply_debounce(g)]
                    
                    # Actualizar gestos continuos
                    for gesture in interpreted_gestures:
                        self._update_continuous_gesture(gesture)
                        self._handle_gesture_sequence(gesture)
                    
                    # Priorizar gestos
                    interpreted_gestures = self._prioritize_gestures(interpreted_gestures)
                    
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
        
        # Limpiar gestos continuos expirados
        self._cleanup_continuous_gestures()
    
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
        max_age = 2.0  # 2 segundos máximo
        if time.time() - gesture.get('timestamp', 0) > max_age:
            return False
        
        # Validar que no sea gesto duplicado muy rápido
        if not self._apply_debounce(gesture):
            return False
        
        return True
    
    # ========== NUEVOS MÉTODOS PÚBLICOS PARA INTEGRACIÓN ==========
    
    def enable_fusion(self, enable: bool = True):
        """Habilita o deshabilita la fusión de gestos."""
        self.fusion_config['enable_hand_arm_fusion'] = enable
        self.fusion_config['enable_multi_hand_fusion'] = enable
        logger.info(f"🔄 Fusión de gestos {'habilitada' if enable else 'deshabilitada'}")
    
    def set_fusion_window(self, window_ms: int):
        """Establece la ventana temporal para fusión de gestos."""
        self.fusion_config['fusion_window_ms'] = max(100, min(window_ms, 1000))
        logger.info(f"🔄 Ventana de fusión establecida: {self.fusion_config['fusion_window_ms']}ms")
    
    def enable_debounce(self, enable: bool = True):
        """Habilita o deshabilita el debounce de gestos."""
        self.debounce_config['enable_debounce'] = enable
        logger.info(f"🔄 Debounce {'habilitado' if enable else 'deshabilitado'}")
    
    def get_continuous_gestures(self) -> Dict[str, Any]:
        """Obtiene el estado actual de gestos continuos."""
        with self.lock:
            return self.continuous_gesture_states.copy()
    
    def get_gesture_sequence(self) -> List[Dict]:
        """Obtiene la secuencia reciente de gestos."""
        with self.lock:
            return self.recent_gestures_context['sequence_buffer'].copy()
    
    def clear_gesture_sequence(self):
        """Limpia el buffer de secuencia de gestos."""
        with self.lock:
            self.recent_gestures_context['sequence_buffer'].clear()
            logger.info("🧹 Secuencia de gestos limpiada")
    
    def process_combined_gesture(self, gesture_data: Dict):
        """Procesa un gesto combinado manualmente."""
        try:
            # Validar gesto combinado
            if 'combined' not in gesture_data.get('type', ''):
                gesture_data['type'] = 'combined'
            
            # Asegurar campos requeridos
            if 'timestamp' not in gesture_data:
                gesture_data['timestamp'] = time.time()
            
            if 'confidence' not in gesture_data:
                gesture_data['confidence'] = 0.7
            
            # Aplicar mapeo de perfil
            self._apply_profile_mapping(gesture_data)
            
            # Encolar para procesamiento
            self.interpretation_queue.put(gesture_data, timeout=0.01)
            logger.debug(f"🔄 Gesto combinado procesado: {gesture_data.get('gesture', '')}")
            
        except Exception as e:
            logger.error(f"❌ Error procesando gesto combinado: {e}")
    
    # ========== MÉTODOS DE PROCESAMIENTO MEJORADOS ==========
    
    def _processing_loop(self):
        """Bucle de procesamiento mejorado con nuevas funcionalidades."""
        logger.debug("🔄 Iniciando bucle de procesamiento mejorado")
        
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
                
                # Actualizar contexto de gestos recientes
                self._update_recent_gesture_context(gesture)
                
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
    
    def _update_recent_gesture_context(self, gesture: Dict):
        """Actualiza el contexto de gestos recientes."""
        gesture_type = gesture.get('type', '')
        
        if gesture_type == 'hand':
            self.recent_gestures_context['last_hand_gesture'] = gesture
        elif gesture_type == 'arm':
            self.recent_gestures_context['last_arm_gesture'] = gesture
        elif gesture_type == 'voice':
            self.recent_gestures_context['last_voice_command'] = gesture
        
        # Limitar tamaño del contexto
        for key in ['last_hand_gesture', 'last_arm_gesture', 'last_voice_command']:
            context_item = self.recent_gestures_context.get(key)
            if context_item and time.time() - context_item.get('timestamp', 0) > 10.0:
                self.recent_gestures_context[key] = None
    
    def _resolve_conflicts(self, new_gesture: Dict) -> bool:
        """Resuelve conflictos entre gestos nuevos y previos mejorado."""
        if not self.gesture_history:
            return True
        
        # Obtener gestos recientes (último segundo)
        recent_gestures = [
            g for g in self.gesture_history[-10:]
            if time.time() - g.get('timestamp', 0) < 1.0
        ]
        
        if not recent_gestures:
            return True
        
        # Reglas de resolución de conflictos mejoradas
        new_gesture_name = new_gesture.get('gesture')
        new_gesture_type = new_gesture.get('type')
        new_priority = new_gesture.get('priority', 0)
        
        for recent_gesture in recent_gestures:
            recent_name = recent_gesture.get('gesture')
            recent_type = recent_gesture.get('type')
            recent_priority = recent_gesture.get('priority', 0)
            
            # Mismo gesto muy rápido = posible duplicado
            if (new_gesture_name == recent_name and 
                new_gesture_type == recent_type):
                time_diff = new_gesture['timestamp'] - recent_gesture['timestamp']
                if time_diff < 0.2:  # Menos de 200ms = duplicado seguro
                    logger.debug(f"⚠️ Gesto duplicado filtrado: {new_gesture_name}")
                    return False
            
            # Conflictos de prioridad
            if new_priority < recent_priority:
                # Gestos de menor prioridad ignorados si hay uno de mayor prioridad reciente
                time_diff = new_gesture['timestamp'] - recent_gesture['timestamp']
                if time_diff < 0.5:  # Medio segundo
                    logger.debug(f"⚠️ Gesto de baja prioridad ignorado: {new_gesture_name}")
                    return False
            
            # Conflictos mano/brazo con contexto
            if (new_gesture_type == 'hand' and recent_type == 'arm' or
                new_gesture_type == 'arm' and recent_type == 'hand'):
                
                # Si hay gesto continuo activo, priorizarlo
                if recent_gesture.get('continuous', False):
                    logger.debug(f"⚠️ Gesto de {new_gesture_type} ignorado por gesto continuo de {recent_type}")
                    return False
        
        return True
    
    def _create_action_data(self, gesture: Dict) -> Dict:
        """Crea datos de acción a partir de un gesto mejorado."""
        action_data = {
            'type': 'gesture',
            'gesture': gesture['gesture'],
            'action': gesture.get('action'),
            'command': gesture.get('command'),
            'confidence': gesture.get('confidence', 0.5),
            'timestamp': time.time(),
            'source': gesture.get('source', 'unknown'),
            'gesture_type': gesture.get('type', 'unknown'),
            'priority': gesture.get('priority', 1),
            'gesture_data': gesture
        }
        
        # Agregar información adicional para gestos continuos
        if gesture.get('continuous', False):
            action_data['continuous'] = True
            action_data['continuous_duration'] = gesture.get('continuous_duration', 0)
            action_data['continuous_updates'] = gesture.get('continuous_updates', 1)
            
            if 'total_delta_x' in gesture:
                action_data['total_delta_x'] = gesture['total_delta_x']
            
            if 'total_delta_y' in gesture:
                action_data['total_delta_y'] = gesture['total_delta_y']
        
        # Agregar información de secuencia si existe
        if 'sequence_data' in gesture:
            action_data['sequence'] = True
            action_data['sequence_name'] = gesture.get('gesture', '')
        
        return action_data
    
    # ========== MÉTODO PARA COMANDOS DE VOZ MEJORADO ==========
    
    def process_voice_command(self, voice_data: Dict):
        """
        Procesa un comando de voz directamente.
        
        Args:
            voice_data: Datos del comando de voz
        """
        if not self.running or 'voice' not in self.interpreters:
            return
        
        try:
            # Agregar metadatos
            voice_data['detector'] = 'voice'
            voice_data['timestamp'] = time.time()
            voice_data.setdefault('confidence', 0.9)
            
            # Enviar directamente al VoiceInterpreter
            interpreter = self.interpreters['voice']
            interpreted_action = interpreter.interpret([voice_data])
            
            if interpreted_action and isinstance(interpreted_action, list):
                for action in interpreted_action:
                    action['source'] = 'voice'
                    action['detection_count'] = 1
                    
                    # Aplicar mapeo de perfil
                    if self.profile_runtime:
                        self._apply_profile_mapping(action)
                    
                    # Priorizar gestos de voz (alta prioridad)
                    action['priority'] = GesturePriority.HIGH.value
                    
                    # Encolar para procesamiento
                    try:
                        self.interpretation_queue.put(action, timeout=0.01)
                        logger.debug(f"🎤 Comando de voz procesado: {voice_data.get('text', '')}")
                    except queue.Full:
                        logger.warning("⚠️ Cola de interpretaciones llena, descartando comando de voz")
                        
        except Exception as e:
            logger.error(f"❌ Error procesando comando de voz: {e}")
    
    # ========== REGISTRO DE COMPONENTES MEJORADO ==========
    
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
            
            # Inicializar estadísticas del detector
            self.stats['detector_stats'][name] = {
                'calls': 0,
                'successes': 0,
                'errors': 0,
                'last_call': 0,
                'avg_processing_time': 0
            }
            
            logger.info(f"✅ Detector '{name}' registrado con estadísticas")
    
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
            
            # Inicializar estadísticas del intérprete
            self.stats['interpreter_stats'][name] = {
                'calls': 0,
                'gestures_interpreted': 0,
                'errors': 0,
                'last_call': 0,
                'avg_processing_time': 0
            }
            
            logger.info(f"✅ Intérprete '{name}' registrado con estadísticas")
    
    # ========== MÉTODOS RESTANTES DEL CÓDIGO ORIGINAL ==========
    # (Mantener los métodos existentes que no fueron modificados)
    
    # [Aquí irían todos los métodos originales que no requieren cambios]
    # Por ejemplo: start(), stop(), load_profile(), get_stats(), etc.
    # Estos se mantienen igual que en tu código original

# ========== CLASES AUXILIARES PARA INTEGRACIÓN ==========

class GestureBuffer:
    """Buffer para almacenar y procesar gestos temporalmente."""
    
    def __init__(self, max_size: int = 10, max_age: float = 2.0):
        self.max_size = max_size
        self.max_age = max_age
        self.buffer = deque(maxlen=max_size)
    
    def add(self, gesture: Dict):
        """Agrega un gesto al buffer."""
        self.buffer.append({
            'gesture': gesture,
            'timestamp': time.time()
        })
    
    def get_recent(self, min_confidence: float = 0.0) -> List[Dict]:
        """Obtiene gestos recientes que cumplan con la confianza mínima."""
        current_time = time.time()
        recent = []
        
        for item in reversed(self.buffer):
            if current_time - item['timestamp'] > self.max_age:
                break
            
            if item['gesture'].get('confidence', 0) >= min_confidence:
                recent.append(item['gesture'])
        
        return recent
    
    def clear(self):
        """Limpia el buffer."""
        self.buffer.clear()


class GestureSequenceDetector:
    """Detector de secuencias de gestos."""
    
    def __init__(self):
        self.sequences = {
            'double_tap': {'pattern': ['tap', 'tap'], 'max_interval': 0.5},
            'swipe_tap': {'pattern': ['swipe', 'tap'], 'max_interval': 1.0},
            'zoom_in_out': {'pattern': ['pinch_in', 'pinch_out'], 'max_interval': 1.5}
        }
    
    def detect(self, gesture_history: List[Dict]) -> List[Dict]:
        """Detecta secuencias en el historial de gestos."""
        detected_sequences = []
        
        for seq_name, seq_config in self.sequences.items():
            pattern = seq_config['pattern']
            max_interval = seq_config['max_interval']
            
            if len(gesture_history) >= len(pattern):
                # Buscar el patrón en el historial reciente
                recent_gestures = gesture_history[-len(pattern):]
                gesture_names = [g.get('gesture', '') for g in recent_gestures]
                
                # Verificar si coincide el patrón
                if all(g in p for g, p in zip(gesture_names, pattern)):
                    # Verificar intervalos temporales
                    timestamps = [g.get('timestamp', 0) for g in recent_gestures]
                    intervals = [timestamps[i+1] - timestamps[i] 
                               for i in range(len(timestamps)-1)]
                    
                    if all(interval <= max_interval for interval in intervals):
                        detected_sequences.append({
                            'name': seq_name,
                            'gestures': recent_gestures,
                            'confidence': min(g.get('confidence', 0.5) 
                                            for g in recent_gestures)
                        })
        
        return detected_sequences


logger.info("✅ Todos los métodos faltantes han sido integrados en GestureIntegrator")