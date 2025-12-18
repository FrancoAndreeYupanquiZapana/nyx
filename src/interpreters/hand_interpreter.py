"""
🤏 HAND INTERPRETER - Interpretador de Gestos de Manos
=====================================================
Convierte los datos crudos de detección de manos en gestos significativos
con contexto, confianza y mapeo a acciones.
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class HandInterpreter:
    """Interpreta gestos de manos detectados."""
    
    def __init__(self, gesture_threshold: float = 0.7):
        """
        Inicializa el interpretador de manos.
        
        Args:
            gesture_threshold: Umbral mínimo de confianza para considerar un gesto válido
        """
        self.gesture_threshold = gesture_threshold
        
        # Mapeo de gestos a acciones (se carga desde perfiles)
        self.gesture_mappings = {}
        
        # Historial para estabilización
        self.gesture_history = []
        self.max_history = 10
        
        # Estados de gestos previos
        self.last_gestures = {}
        self.gesture_durations = {}
        
        # Configuración de estabilización
        self.stabilization_frames = 3  # Número de frames para estabilizar un gesto
        self.cooldown_frames = 5       # Frames de cooldown entre gestos repetidos
        
        # Estadísticas
        self.stats = {
            'gestures_interpreted': 0,
            'gestures_filtered': 0,
            'actions_triggered': 0,
            'avg_confidence': 0.0
        }
        
        logger.info(f"✅ HandInterpreter inicializado (threshold={gesture_threshold})")
    
    def interpret(self, hands_data: List[Dict]) -> List[Dict]:
        """
        Interpreta los datos de manos detectadas en gestos significativos.
        
        Args:
            hands_data: Lista de datos de manos detectadas por HandDetector
            
        Returns:
            Lista de gestos interpretados con contexto adicional
        """
        interpreted_gestures = []
        
        for hand in hands_data:
            if not hand:
                continue
            
            # Obtener gestos crudos de esta mano
            raw_gestures = hand.get('gestures', [])
            hand_info = hand.get('hand_info', {})
            
            # Procesar cada gesto crudo
            for raw_gesture in raw_gestures:
                try:
                    # Interpretar el gesto crudo
                    interpreted = self._interpret_single_gesture(raw_gesture, hand_info)
                    
                    if interpreted:
                        # Verificar estabilidad del gesto
                        if self._is_gesture_stable(interpreted, hand_info.get('handedness')):
                            # Aplicar mapeo a acción si existe
                            interpreted = self._apply_gesture_mapping(interpreted)
                            interpreted_gestures.append(interpreted)
                            
                            # Actualizar estadísticas
                            self.stats['gestures_interpreted'] += 1
                            self.stats['avg_confidence'] = (
                                (self.stats['avg_confidence'] * (self.stats['gestures_interpreted'] - 1) + 
                                 interpreted['confidence']) / self.stats['gestures_interpreted']
                            )
                except Exception as e:
                    logger.debug(f"⚠️ Error interpretando gesto: {e}")
                    continue
        
        return interpreted_gestures
    
    def _interpret_single_gesture(self, raw_gesture: Dict, hand_info: Dict) -> Optional[Dict]:
        """
        Interpreta un gesto crudo individual.
        
        Args:
            raw_gesture: Gesto crudo del detector
            hand_info: Información de la mano
            
        Returns:
            Gesto interpretado con contexto o None si no es válido
        """
        # Verificar confianza mínima
        confidence = raw_gesture.get('confidence', 0.0)
        if confidence < self.gesture_threshold:
            self.stats['gestures_filtered'] += 1
            return None
        
        gesture_name = raw_gesture.get('gesture', 'unknown')
        hand_type = raw_gesture.get('hand', 'unknown')
        
        # Calcular confianza contextual
        contextual_confidence = self._calculate_contextual_confidence(
            raw_gesture, hand_info
        )
        
        # Ajustar confianza final
        final_confidence = min(confidence * contextual_confidence, 1.0)
        
        # Determinar tipo de gesto basado en nombre
        gesture_type = self._categorize_gesture(gesture_name)
        
        # Crear gesto interpretado
        interpreted_gesture = {
            'type': 'hand',
            'gesture': gesture_name,
            'category': gesture_type,
            'hand': hand_type,
            'confidence': final_confidence,
            'raw_confidence': confidence,
            'contextual_confidence': contextual_confidence,
            'timestamp': time.time(),
            'hand_info': {
                'landmarks_count': len(hand_info.get('landmarks', [])),
                'bbox_area': hand_info.get('bbox', {}).get('area', 0),
                'hand_confidence': hand_info.get('confidence', 0.0)
            },
            'raw_data': raw_gesture  # Mantener datos originales para referencia
        }
        
        # Agregar información de dedos si está disponible
        if 'finger_status' in hand_info:
            interpreted_gesture['finger_status'] = hand_info['finger_status']
        
        # Agregar ángulos si están disponibles
        if 'angles' in hand_info:
            interpreted_gesture['angles'] = hand_info['angles']
        
        return interpreted_gesture
    
    def _calculate_contextual_confidence(self, raw_gesture: Dict, hand_info: Dict) -> float:
        """
        Calcula confianza contextual basada en información adicional de la mano.
        
        Args:
            raw_gesture: Gesto crudo
            hand_info: Información de la mano
            
        Returns:
            Confianza contextual entre 0 y 1
        """
        contextual_factors = []
        
        # Factor 1: Visibilidad de landmarks
        landmarks = hand_info.get('landmarks', [])
        if landmarks:
            avg_visibility = sum(lm.get('visibility', 0.0) for lm in landmarks) / len(landmarks)
            contextual_factors.append(avg_visibility)
        
        # Factor 2: Tamaño de la mano en imagen
        bbox = hand_info.get('bbox', {})
        bbox_area = bbox.get('width', 0) * bbox.get('height', 0)
        if bbox_area > 0:
            # Manos muy pequeñas o muy grandes pueden ser menos confiables
            size_factor = min(bbox_area / 10000, 1.0)  # Normalizar
            contextual_factors.append(size_factor)
        
        # Factor 3: Confianza de la detección de mano
        hand_confidence = hand_info.get('confidence', 0.0)
        contextual_factors.append(hand_confidence)
        
        # Factor 4: Consistencia con estado de dedos
        finger_status = hand_info.get('finger_status', {})
        if finger_status:
            consistency = self._check_finger_consistency(raw_gesture.get('gesture', ''), finger_status)
            contextual_factors.append(consistency)
        
        if not contextual_factors:
            return 0.5  # Valor por defecto
        
        # Promedio ponderado
        return sum(contextual_factors) / len(contextual_factors)
    
    def _check_finger_consistency(self, gesture_name: str, finger_status: Dict) -> float:
        """
        Verifica consistencia del gesto con estado de dedos.
        
        Args:
            gesture_name: Nombre del gesto
            finger_status: Estado de cada dedo
            
        Returns:
            Consistencia entre 0 y 1
        """
        # Mapeo de gestos a estados esperados de dedos
        expected_states = {
            'fist': {
                'thumb': 'bent', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'
            },
            'peace': {
                'thumb': 'bent', 'index': 'extended', 'middle': 'extended', 'ring': 'bent', 'pinky': 'bent'
            },
            'thumbs_up': {
                'thumb': 'extended', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'
            },
            'thumbs_down': {
                'thumb': 'extended', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'
            },
            'rock': {
                'thumb': 'bent', 'index': 'extended', 'middle': 'bent', 'ring': 'bent', 'pinky': 'extended'
            },
            'ok': {
                'thumb': 'bent', 'index': 'bent', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'
            },
            'point': {
                'thumb': 'bent', 'index': 'extended', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'
            },
            'palm': {
                'thumb': 'extended', 'index': 'extended', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'
            },
            'victory': {
                'thumb': 'bent', 'index': 'extended', 'middle': 'extended', 'ring': 'bent', 'pinky': 'bent'
            },
            'call_me': {
                'thumb': 'extended', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'extended'
            },
            'stop': {
                'thumb': 'extended', 'index': 'extended', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'
            }
        }
        
        if gesture_name not in expected_states:
            return 0.7  # Consistencia media para gestos no definidos
        
        expected = expected_states[gesture_name]
        matches = 0
        total = 0
        
        for finger, expected_state in expected.items():
            if finger in finger_status:
                total += 1
                if finger_status[finger] == expected_state:
                    matches += 1
        
        if total == 0:
            return 0.5
        
        return matches / total
    
    def _categorize_gesture(self, gesture_name: str) -> str:
        """
        Categoriza un gesto por su tipo.
        
        Args:
            gesture_name: Nombre del gesto
            
        Returns:
            Categoría del gesto
        """
        categories = {
            'fist': 'command',
            'peace': 'command',
            'thumbs_up': 'feedback',
            'thumbs_down': 'feedback',
            'rock': 'command',
            'ok': 'confirmation',
            'point': 'navigation',
            'palm': 'control',
            'victory': 'celebration',
            'call_me': 'communication',
            'stop': 'command'
        }
        
        return categories.get(gesture_name, 'unknown')
    
    def _is_gesture_stable(self, interpreted_gesture: Dict, hand_type: str) -> bool:
        """
        Verifica si un gesto es estable (no flickering).
        
        Args:
            interpreted_gesture: Gesto interpretado
            hand_type: Tipo de mano (left/right)
            
        Returns:
            True si el gesto es estable
        """
        gesture_key = f"{hand_type}_{interpreted_gesture['gesture']}"
        current_time = time.time()
        
        # Agregar al historial
        history_entry = {
            'key': gesture_key,
            'gesture': interpreted_gesture['gesture'],
            'hand': hand_type,
            'confidence': interpreted_gesture['confidence'],
            'timestamp': current_time
        }
        
        self.gesture_history.append(history_entry)
        if len(self.gesture_history) > self.max_history:
            self.gesture_history.pop(0)
        
        # Limpiar historial viejo (más de 1 segundo)
        self.gesture_history = [
            h for h in self.gesture_history 
            if current_time - h['timestamp'] < 1.0
        ]
        
        # Verificar cooldown para gestos repetidos
        last_time = self.last_gestures.get(gesture_key, 0)
        if current_time - last_time < 0.3:  # 300ms de cooldown mínimo
            return False
        
        # Contar ocurrencias recientes del mismo gesto
        recent_same = 0
        for h in self.gesture_history[-self.stabilization_frames:]:
            if h['key'] == gesture_key:
                recent_same += 1
        
        # Requerir mayoría para estabilidad
        is_stable = recent_same >= 2
        
        if is_stable:
            # Actualizar último tiempo visto
            self.last_gestures[gesture_key] = current_time
            
            # Actualizar duración
            if gesture_key in self.gesture_durations:
                self.gesture_durations[gesture_key] += 0.1  # Aproximadamente 100ms por frame
            else:
                self.gesture_durations[gesture_key] = 0.1
            
            # Si el gesto se mantiene demasiado tiempo, podría ser estático
            if self.gesture_durations[gesture_key] > 2.0:  # 2 segundos
                logger.debug(f"⚠️ Gesto {gesture_key} mantenido por {self.gesture_durations[gesture_key]:.1f}s")
        
        return is_stable
    
    def _apply_gesture_mapping(self, interpreted_gesture: Dict) -> Dict:
        """
        Aplica mapeo de gesto a acción si existe.
        
        Args:
            interpreted_gesture: Gesto interpretado
            
        Returns:
            Gesto con información de acción si corresponde
        """
        gesture_name = interpreted_gesture['gesture']
        hand_type = interpreted_gesture['hand']
        
        # Buscar mapeo específico para esta combinación gesto-mano
        mapping_key = f"{hand_type}_{gesture_name}"
        
        if mapping_key in self.gesture_mappings:
            mapping = self.gesture_mappings[mapping_key]
            interpreted_gesture['action'] = mapping.get('action')
            interpreted_gesture['command'] = mapping.get('command')
            interpreted_gesture['action_description'] = mapping.get('description', '')
            interpreted_gesture['mapped'] = True
            self.stats['actions_triggered'] += 1
        else:
            # También buscar mapeo genérico (sin mano específica)
            if gesture_name in self.gesture_mappings:
                mapping = self.gesture_mappings[gesture_name]
                interpreted_gesture['action'] = mapping.get('action')
                interpreted_gesture['command'] = mapping.get('command')
                interpreted_gesture['action_description'] = mapping.get('description', '')
                interpreted_gesture['mapped'] = True
                self.stats['actions_triggered'] += 1
            else:
                interpreted_gesture['mapped'] = False
        
        return interpreted_gesture
    
    def load_gesture_mappings(self, mappings: Dict):
        """
        Carga mapeos de gestos a acciones.
        
        Args:
            mappings: Diccionario con mapeos
                Formato: {
                    'gesture_name': {
                        'action': 'keyboard',
                        'command': 'ctrl+s',
                        'description': 'Guardar'
                    },
                    'left_fist': {...},
                    'right_peace': {...}
                }
        """
        self.gesture_mappings = mappings
        logger.info(f"✅ Cargados {len(mappings)} mapeos de gestos")
    
    def add_gesture_mapping(self, gesture_name: str, action_config: Dict, hand_specific: str = None):
        """
        Agrega un mapeo de gesto a acción.
        
        Args:
            gesture_name: Nombre del gesto
            action_config: Configuración de la acción
            hand_specific: 'left', 'right', o None para ambas manos
        """
        if hand_specific:
            key = f"{hand_specific}_{gesture_name}"
        else:
            key = gesture_name
        
        self.gesture_mappings[key] = action_config
        logger.debug(f"✅ Mapeo agregado: {key} -> {action_config.get('action', 'unknown')}")
    
    def remove_gesture_mapping(self, gesture_name: str, hand_specific: str = None):
        """
        Remueve un mapeo de gesto.
        
        Args:
            gesture_name: Nombre del gesto
            hand_specific: 'left', 'right', o None
        """
        if hand_specific:
            key = f"{hand_specific}_{gesture_name}"
        else:
            key = gesture_name
        
        if key in self.gesture_mappings:
            del self.gesture_mappings[key]
            logger.debug(f"✅ Mapeo removido: {key}")
    
    def get_available_gestures(self) -> List[str]:
        """
        Obtiene lista de gestos disponibles.
        
        Returns:
            Lista de nombres de gestos
        """
        # Extraer gestos únicos de los mapeos
        gestures = set()
        for key in self.gesture_mappings.keys():
            if '_' in key:
                # Clave con mano específica: 'left_fist' -> 'fist'
                gesture = key.split('_', 1)[1]
            else:
                gesture = key
            gestures.add(gesture)
        
        return sorted(list(gestures))
    
    def get_gesture_stats(self, gesture_name: str = None, hand_type: str = None) -> Dict:
        """
        Obtiene estadísticas de gestos.
        
        Args:
            gesture_name: Nombre específico del gesto (opcional)
            hand_type: 'left', 'right', o None para ambas
            
        Returns:
            Diccionario con estadísticas
        """
        stats = {
            'total_interpreted': self.stats['gestures_interpreted'],
            'total_filtered': self.stats['gestures_filtered'],
            'actions_triggered': self.stats['actions_triggered'],
            'avg_confidence': self.stats['avg_confidence'],
            'mappings_count': len(self.gesture_mappings),
            'active_gestures': len(self.last_gestures)
        }
        
        if gesture_name:
            if hand_type:
                key = f"{hand_type}_{gesture_name}"
            else:
                # Buscar para cualquier mano
                keys = [k for k in self.last_gestures.keys() if gesture_name in k]
                key = keys[0] if keys else None
            
            if key and key in self.gesture_durations:
                stats['specific_gesture'] = {
                    'name': gesture_name,
                    'hand': hand_type or 'any',
                    'last_seen': self.last_gestures.get(key, 0),
                    'total_duration': self.gesture_durations.get(key, 0.0),
                    'mapped': key in self.gesture_mappings or 
                             gesture_name in self.gesture_mappings
                }
        
        return stats
    
    def clear_history(self):
        """Limpia el historial de gestos."""
        self.gesture_history.clear()
        self.last_gestures.clear()
        self.gesture_durations.clear()
        logger.debug("✅ Historial de gestos limpiado")
    
    def set_threshold(self, threshold: float):
        """
        Establece nuevo umbral de confianza.
        
        Args:
            threshold: Nuevo umbral (0.0 a 1.0)
        """
        old_threshold = self.gesture_threshold
        self.gesture_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"🔄 Umbral cambiado: {old_threshold:.2f} -> {self.gesture_threshold:.2f}")
    
    def set_stabilization(self, frames: int):
        """
        Establece número de frames para estabilización.
        
        Args:
            frames: Número de frames (mínimo 2)
        """
        self.stabilization_frames = max(2, frames)
        logger.info(f"🔄 Estabilización ajustada a {frames} frames")