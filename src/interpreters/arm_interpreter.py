"""
💪 ARM INTERPRETER - Interpretador de Gestos de Brazos
=====================================================
Convierte los datos crudos de detección de brazos en gestos significativos
para control a distancia (gestos amplios).
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class ArmInterpreter:
    """Interpreta gestos de brazos detectados."""
    
    def __init__(self, gesture_threshold: float = 0.6):
        """
        Inicializa el interpretador de brazos.
        
        Args:
            gesture_threshold: Umbral mínimo de confianza para considerar un gesto válido
        """
        self.gesture_threshold = gesture_threshold
        
        # Mapeo de gestos a acciones (se carga desde perfiles)
        self.gesture_mappings = {}
        
        # Historial para estabilización
        self.gesture_history = []
        self.max_history = 8
        
        # Estados de gestos previos
        self.last_gestures = {}
        self.gesture_start_times = {}
        self.gesture_durations = {}
        
        # Configuración de estabilización
        self.stabilization_frames = 2  # Menos frames que manos (gestos más lentos)
        self.cooldown_time = 0.8       # Más cooldown que manos (gestos más deliberados)
        
        # Para gestos continuos (zoom, volumen, etc.)
        self.continuous_gestures = ['zoom_in', 'zoom_out', 'arms_up', 'arms_down']
        self.continuous_threshold = 1.0  # Segundos para activar modo continuo
        
        # Estadísticas
        self.stats = {
            'gestures_interpreted': 0,
            'gestures_filtered': 0,
            'actions_triggered': 0,
            'continuous_actions': 0,
            'avg_confidence': 0.0
        }
        
        logger.info(f"✅ ArmInterpreter inicializado (threshold={gesture_threshold})")
    
    def interpret(self, arm_data: List[Dict]) -> List[Dict]:
        """
        Interpreta los datos de brazos detectados en gestos significativos.
        
        Args:
            arm_data: Lista de datos de brazos detectados por ArmDetector
            
        Returns:
            Lista de gestos interpretados con contexto adicional
        """
        interpreted_gestures = []
        
        # Procesar cada detección de brazo
        for detection in arm_data:
            if not detection:
                continue
            
            # Obtener gestos crudos y landmarks
            raw_gestures = detection.get('gestures', [])
            landmarks = detection.get('landmarks', {})
            angles = detection.get('angles', {})
            
            # Procesar cada gesto crudo
            for raw_gesture in raw_gestures:
                try:
                    # Interpretar el gesto crudo
                    interpreted = self._interpret_single_gesture(raw_gesture, landmarks, angles)
                    
                    if interpreted:
                        # Verificar estabilidad del gesto
                        if self._is_gesture_stable(interpreted):
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
                    logger.debug(f"⚠️ Error interpretando gesto de brazo: {e}")
                    continue
        
        # Procesar gestos continuos
        continuous_gestures = self._detect_continuous_gestures(interpreted_gestures)
        interpreted_gestures.extend(continuous_gestures)
        
        return interpreted_gestures
    
    def process_gesture(self, gesture_data: Dict) -> Optional[Dict]:
        """
        Procesa un único gesto (método de compatibilidad para GesturePipeline).
        
        Args:
            gesture_data: Datos del gesto individual
            
        Returns:
            Gesto interpretado o None
        """
        try:
            # Usar datos vacíos para landmarks y ángulos (modo compatibilidad)
            landmarks = {}
            angles = {}
            
            # Interpretar
            interpreted = self._interpret_single_gesture(gesture_data, landmarks, angles)
            
            if interpreted:
                if self._is_gesture_stable(interpreted):
                    return self._apply_gesture_mapping(interpreted)
            
            return None
        except Exception as e:
            logger.error(f"❌ Error procesando gesto de brazo individual: {e}")
            return None
    
    def _interpret_single_gesture(self, raw_gesture: Dict, landmarks: Dict, angles: Dict) -> Optional[Dict]:
        """
        Interpreta un gesto crudo individual de brazo.
        
        Args:
            raw_gesture: Gesto crudo del detector
            landmarks: Landmarks de los brazos
            angles: Ángulos de articulaciones
            
        Returns:
            Gesto interpretado con contexto o None si no es válido
        """
        # Verificar confianza mínima
        confidence = raw_gesture.get('confidence', 0.0)
        if confidence < self.gesture_threshold:
            self.stats['gestures_filtered'] += 1
            return None
        
        gesture_name = raw_gesture.get('gesture', 'unknown')
        
        # Calcular confianza contextual
        contextual_confidence = self._calculate_contextual_confidence(
            raw_gesture, landmarks, angles
        )
        
        # Ajustar confianza final
        final_confidence = min(confidence * contextual_confidence, 1.0)
        
        # Determinar tipo de gesto basado en nombre
        gesture_type = self._categorize_gesture(gesture_name)
        
        # Determinar magnitud del gesto
        magnitude = self._calculate_gesture_magnitude(gesture_name, landmarks, angles)
        
        # Determinar si es un gesto simétrico (ambos brazos)
        is_symmetric = self._is_symmetric_gesture(gesture_name)
        
        # Crear gesto interpretado
        interpreted_gesture = {
            'type': 'arm',
            'gesture': gesture_name,
            'category': gesture_type,
            'magnitude': magnitude,
            'symmetric': is_symmetric,
            'confidence': final_confidence,
            'raw_confidence': confidence,
            'contextual_confidence': contextual_confidence,
            'timestamp': time.time(),
            'landmarks_quality': self._calculate_landmarks_quality(landmarks),
            'angles': angles,
            'raw_data': raw_gesture
        }
        
        # Agregar información específica del gesto
        self._add_gesture_specific_info(interpreted_gesture, landmarks, angles)
        
        return interpreted_gesture
    
    def _calculate_contextual_confidence(self, raw_gesture: Dict, landmarks: Dict, angles: Dict) -> float:
        """
        Calcula confianza contextual basada en landmarks y ángulos.
        
        Args:
            raw_gesture: Gesto crudo
            landmarks: Landmarks de brazos
            angles: Ángulos de articulaciones
            
        Returns:
            Confianza contextual entre 0 y 1
        """
        contextual_factors = []
        
        # Factor 1: Calidad de landmarks
        required_landmarks = ['left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder']
        landmarks_present = sum(1 for lm in required_landmarks if lm in landmarks)
        landmarks_factor = landmarks_present / len(required_landmarks)
        contextual_factors.append(landmarks_factor)
        
        # Factor 2: Visibilidad promedio
        if landmarks:
            visibilities = [lm.get('visibility', 0.0) for lm in landmarks.values()]
            avg_visibility = sum(visibilities) / len(visibilities)
            contextual_factors.append(avg_visibility)
        
        # Factor 3: Consistencia con ángulos
        if angles:
            angle_consistency = self._check_angle_consistency(raw_gesture.get('gesture', ''), angles)
            contextual_factors.append(angle_consistency)
        
        # Factor 4: Simetría para gestos que deberían ser simétricos
        gesture_name = raw_gesture.get('gesture', '')
        if self._should_be_symmetric(gesture_name):
            symmetry = self._calculate_symmetry(landmarks)
            contextual_factors.append(symmetry)
        
        if not contextual_factors:
            return 0.5
        
        # Promedio ponderado (dar más peso a landmarks)
        weights = [0.4, 0.3, 0.2, 0.1]
        total = 0
        weighted_sum = 0
        
        for i, factor in enumerate(contextual_factors):
            if i < len(weights):
                weighted_sum += factor * weights[i]
                total += weights[i]
        
        return weighted_sum / total if total > 0 else sum(contextual_factors) / len(contextual_factors)
    
    def _check_angle_consistency(self, gesture_name: str, angles: Dict) -> float:
        """
        Verifica consistencia del gesto con ángulos de articulaciones.
        
        Args:
            gesture_name: Nombre del gesto
            angles: Ángulos de articulaciones
            
        Returns:
            Consistencia entre 0 y 1
        """
        # Ángulos esperados para diferentes gestos
        expected_angles = {
            'arms_up': {
                'left_elbow': (150, 180),  # Casi recto
                'right_elbow': (150, 180)
            },
            'arms_down': {
                'left_elbow': (150, 180),
                'right_elbow': (150, 180)
            },
            'arms_crossed': {
                'left_elbow': (70, 110),   # Doblado
                'right_elbow': (70, 110)
            },
            't_pose': {
                'left_elbow': (170, 180),  # Completamente extendido
                'right_elbow': (170, 180)
            },
            'wave_left': {
                'left_elbow': (90, 150),   # Ángulo de saludo
                'right_elbow': (150, 180)  # Derecho probablemente recto
            },
            'wave_right': {
                'left_elbow': (150, 180),
                'right_elbow': (90, 150)
            }
        }
        
        if gesture_name not in expected_angles:
            return 0.7  # Consistencia media para gestos no definidos
        
        expected = expected_angles[gesture_name]
        matches = 0
        total = 0
        
        for angle_name, (min_angle, max_angle) in expected.items():
            if angle_name in angles:
                total += 1
                if min_angle <= angles[angle_name] <= max_angle:
                    matches += 1
        
        if total == 0:
            return 0.5
        
        return matches / total
    
    def _should_be_symmetric(self, gesture_name: str) -> bool:
        """Determina si un gesto debería ser simétrico."""
        symmetric_gestures = [
            'arms_up', 'arms_down', 'arms_out', 'arms_together',
            't_pose', 'x_pose', 'zoom_in', 'zoom_out'
        ]
        return gesture_name in symmetric_gestures
    
    def _calculate_symmetry(self, landmarks: Dict) -> float:
        """
        Calcula simetría entre brazos izquierdo y derecho.
        
        Args:
            landmarks: Landmarks de brazos
            
        Returns:
            Simetría entre 0 y 1
        """
        left_points = ['left_wrist', 'left_elbow', 'left_shoulder']
        right_points = ['right_wrist', 'right_elbow', 'right_shoulder']
        
        if not all(p in landmarks for p in left_points + right_points):
            return 0.5
        
        # Calcular diferencias en posición Y (altura)
        y_differences = []
        for left, right in zip(left_points, right_points):
            left_y = landmarks[left]['y']
            right_y = landmarks[right]['y']
            y_differences.append(abs(left_y - right_y))
        
        avg_y_diff = sum(y_differences) / len(y_differences)
        
        # Convertir a simetría (menor diferencia = mayor simetría)
        symmetry = max(0, 1 - avg_y_diff * 5)  # Ajustar factor de escala
        return symmetry
    
    def _categorize_gesture(self, gesture_name: str) -> str:
        """
        Categoriza un gesto de brazo por su tipo.
        
        Args:
            gesture_name: Nombre del gesto
            
        Returns:
            Categoría del gesto
        """
        categories = {
            'arms_crossed': 'command',
            'arms_up': 'control',
            'arms_down': 'control',
            'arms_out': 'control',
            'arms_together': 'control',
            'left_arm_up': 'navigation',
            'right_arm_up': 'navigation',
            'left_arm_out': 'navigation',
            'right_arm_out': 'navigation',
            'wave_left': 'communication',
            'wave_right': 'communication',
            'zoom_in': 'adjustment',
            'zoom_out': 'adjustment',
            't_pose': 'activation',
            'x_pose': 'activation'
        }
        
        return categories.get(gesture_name, 'unknown')
    
    def _calculate_gesture_magnitude(self, gesture_name: str, landmarks: Dict, angles: Dict) -> float:
        """
        Calcula la magnitud/intensidad de un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            landmarks: Landmarks de brazos
            angles: Ángulos de articulaciones
            
        Returns:
            Magnitud entre 0 y 1
        """
        if gesture_name == 'arms_up':
            # Magnitud basada en qué tan arriba están las manos
            if 'left_wrist' in landmarks and 'left_shoulder' in landmarks:
                left_height = landmarks['left_shoulder']['y'] - landmarks['left_wrist']['y']
                return min(max(left_height * 3, 0), 1)
        
        elif gesture_name == 'arms_out':
            # Magnitud basada en qué tan extendidos están los brazos
            if 'left_wrist' in landmarks and 'left_shoulder' in landmarks:
                left_extension = landmarks['left_shoulder']['x'] - landmarks['left_wrist']['x']
                return min(abs(left_extension) * 2, 1)
        
        elif gesture_name in ['zoom_in', 'zoom_out']:
            # Magnitud basada en proximidad de manos
            if 'left_wrist' in landmarks and 'right_wrist' in landmarks:
                distance = abs(landmarks['left_wrist']['x'] - landmarks['right_wrist']['x'])
                if gesture_name == 'zoom_in':
                    return max(0, 1 - distance * 2)  # Más cerca = mayor magnitud
                else:
                    return min(distance * 2, 1)  # Más lejos = mayor magnitud
        
        elif 'wave' in gesture_name:
            # Magnitud basada en ángulo del codo
            angle_key = 'left_elbow' if 'left' in gesture_name else 'right_elbow'
            if angle_key in angles:
                # Ángulo óptimo para saludo: ~120 grados
                optimal_angle = 120
                angle_diff = abs(angles[angle_key] - optimal_angle)
                return max(0, 1 - angle_diff / 90)
        
        return 0.5  # Magnitud por defecto
    
    def _is_symmetric_gesture(self, gesture_name: str) -> bool:
        """Determina si un gesto es simétrico por definición."""
        symmetric_by_name = self._should_be_symmetric(gesture_name)
        
        # También los gestos que no especifican lado son simétricos
        no_side_specified = ('left' not in gesture_name and 'right' not in gesture_name)
        
        return symmetric_by_name or no_side_specified
    
    def _calculate_landmarks_quality(self, landmarks: Dict) -> float:
        """
        Calcula calidad general de los landmarks.
        
        Args:
            landmarks: Landmarks de brazos
            
        Returns:
            Calidad entre 0 y 1
        """
        if not landmarks:
            return 0.0
        
        # Puntos críticos
        critical_points = ['left_shoulder', 'right_shoulder', 'left_wrist', 'right_wrist']
        critical_present = sum(1 for p in critical_points if p in landmarks)
        
        # Visibilidad promedio
        visibilities = [lm.get('visibility', 0.0) for lm in landmarks.values()]
        avg_visibility = sum(visibilities) / len(visibilities) if visibilities else 0.0
        
        # Calcular calidad compuesta
        presence_score = critical_present / len(critical_points)
        quality = (presence_score * 0.6) + (avg_visibility * 0.4)
        
        return quality
    
    def _add_gesture_specific_info(self, gesture: Dict, landmarks: Dict, angles: Dict):
        """Agrega información específica basada en el tipo de gesto."""
        gesture_name = gesture['gesture']
        
        if gesture_name == 'arms_crossed':
            # Qué tan cruzados están los brazos
            if 'left_wrist' in landmarks and 'right_shoulder' in landmarks:
                cross_amount = landmarks['left_wrist']['x'] - landmarks['right_shoulder']['x']
                gesture['cross_amount'] = cross_amount
        
        elif gesture_name in ['zoom_in', 'zoom_out']:
            # Distancia entre manos
            if 'left_wrist' in landmarks and 'right_wrist' in landmarks:
                dx = landmarks['left_wrist']['x'] - landmarks['right_wrist']['x']
                dy = landmarks['left_wrist']['y'] - landmarks['right_wrist']['y']
                distance = (dx**2 + dy**2) ** 0.5
                gesture['hand_distance'] = distance
        
        elif 'arm_up' in gesture_name:
            # Altura relativa
            side = 'left' if 'left' in gesture_name else 'right'
            wrist_key = f'{side}_wrist'
            shoulder_key = f'{side}_shoulder'
            
            if wrist_key in landmarks and shoulder_key in landmarks:
                height_ratio = landmarks[shoulder_key]['y'] / landmarks[wrist_key]['y']
                gesture['height_ratio'] = height_ratio
    
    def _is_gesture_stable(self, interpreted_gesture: Dict) -> bool:
        """
        Verifica si un gesto de brazo es estable.
        
        Args:
            interpreted_gesture: Gesto interpretado
            
        Returns:
            True si el gesto es estable
        """
        gesture_name = interpreted_gesture['gesture']
        current_time = time.time()
        
        # Agregar al historial
        history_entry = {
            'gesture': gesture_name,
            'confidence': interpreted_gesture['confidence'],
            'magnitude': interpreted_gesture.get('magnitude', 0.5),
            'timestamp': current_time
        }
        
        self.gesture_history.append(history_entry)
        if len(self.gesture_history) > self.max_history:
            self.gesture_history.pop(0)
        
        # Limpiar historial viejo (más de 2 segundos para gestos lentos)
        self.gesture_history = [
            h for h in self.gesture_history 
            if current_time - h['timestamp'] < 2.0
        ]
        
        # Verificar cooldown para gestos repetidos
        last_time = self.last_gestures.get(gesture_name, 0)
        if current_time - last_time < self.cooldown_time:
            return False
        
        # Para gestos continuos, manejar diferente
        if gesture_name in self.continuous_gestures:
            return self._handle_continuous_gesture(gesture_name, interpreted_gesture, current_time)
        
        # Para gestos discretos, verificar estabilidad
        recent_same = 0
        for h in self.gesture_history[-self.stabilization_frames:]:
            if h['gesture'] == gesture_name:
                recent_same += 1
        
        # Requerir mayoría para estabilidad
        is_stable = recent_same >= 2
        
        if is_stable:
            self.last_gestures[gesture_name] = current_time
            
            # Trackear duración
            if gesture_name in self.gesture_durations:
                self.gesture_durations[gesture_name] += 0.1
            else:
                self.gesture_durations[gesture_name] = 0.1
                self.gesture_start_times[gesture_name] = current_time
        
        return is_stable
    
    def _handle_continuous_gesture(self, gesture_name: str, gesture: Dict, current_time: float) -> bool:
        """
        Maneja gestos continuos (mantenidos).
        
        Args:
            gesture_name: Nombre del gesto
            gesture: Gesto interpretado
            current_time: Tiempo actual
            
        Returns:
            True si el gesto continuo es activo
        """
        if gesture_name not in self.gesture_start_times:
            self.gesture_start_times[gesture_name] = current_time
            self.gesture_durations[gesture_name] = 0.0
            return True
        
        # Calcular duración
        duration = current_time - self.gesture_start_times[gesture_name]
        self.gesture_durations[gesture_name] = duration
        
        # Solo considerar activo después del threshold
        if duration >= self.continuous_threshold:
            # Para gestos continuos, seguir activos mientras se mantengan
            gesture['continuous'] = True
            gesture['duration'] = duration
            gesture['intensity'] = min(duration / 3.0, 1.0)  # Intensidad aumenta con el tiempo
            
            # Disparar acción periódica
            if int(duration * 2) > int((duration - 0.1) * 2):  # Cada ~0.5 segundos
                self.stats['continuous_actions'] += 1
            
            return True
        
        return False
    
    def _detect_continuous_gestures(self, current_gestures: List[Dict]) -> List[Dict]:
        """
        Detecta y genera eventos para gestos continuos.
        
        Args:
            current_gestures: Gestos actualmente activos
            
        Returns:
            Lista adicional de gestos continuos procesados
        """
        continuous_events = []
        current_time = time.time()
        
        # Revisar gestos que estaban activos pero ya no están
        active_gestures = {g['gesture'] for g in current_gestures if 'continuous' not in g}
        
        for gesture_name in list(self.gesture_start_times.keys()):
            if gesture_name not in active_gestures:
                # Gestos que terminaron
                duration = self.gesture_durations.get(gesture_name, 0)
                if duration > self.continuous_threshold:
                    # Crear evento de finalización
                    end_event = {
                        'type': 'arm',
                        'gesture': f'{gesture_name}_end',
                        'category': 'control',
                        'continuous': True,
                        'duration': duration,
                        'confidence': 0.8,
                        'timestamp': current_time
                    }
                    continuous_events.append(end_event)
                
                # Limpiar
                self.gesture_start_times.pop(gesture_name, None)
                self.gesture_durations.pop(gesture_name, None)
        
        return continuous_events
    
    def _apply_gesture_mapping(self, interpreted_gesture: Dict) -> Dict:
        """
        Aplica mapeo de gesto a acción si existe.
        
        Args:
            interpreted_gesture: Gesto interpretado
            
        Returns:
            Gesto con información de acción si corresponde
        """
        gesture_name = interpreted_gesture['gesture']
        
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
        """
        self.gesture_mappings = mappings
        logger.info(f"✅ Cargados {len(mappings)} mapeos de gestos de brazos")
    
    def add_gesture_mapping(self, gesture_name: str, action_config: Dict):
        """
        Agrega un mapeo de gesto a acción.
        
        Args:
            gesture_name: Nombre del gesto
            action_config: Configuración de la acción
        """
        self.gesture_mappings[gesture_name] = action_config
        logger.debug(f"✅ Mapeo de brazo agregado: {gesture_name}")
    
    def get_available_gestures(self) -> List[str]:
        """
        Obtiene lista de gestos disponibles.
        
        Returns:
            Lista de nombres de gestos
        """
        return sorted(list(self.gesture_mappings.keys()))
    
    def get_gesture_stats(self, gesture_name: str = None) -> Dict:
        """
        Obtiene estadísticas de gestos.
        
        Args:
            gesture_name: Nombre específico del gesto (opcional)
            
        Returns:
            Diccionario con estadísticas
        """
        stats = {
            'total_interpreted': self.stats['gestures_interpreted'],
            'total_filtered': self.stats['gestures_filtered'],
            'actions_triggered': self.stats['actions_triggered'],
            'continuous_actions': self.stats['continuous_actions'],
            'avg_confidence': self.stats['avg_confidence'],
            'mappings_count': len(self.gesture_mappings),
            'active_continuous': len(self.gesture_start_times)
        }
        
        if gesture_name:
            stats['specific_gesture'] = {
                'name': gesture_name,
                'last_seen': self.last_gestures.get(gesture_name, 0),
                'total_duration': self.gesture_durations.get(gesture_name, 0.0),
                'is_continuous': gesture_name in self.continuous_gestures,
                'currently_active': gesture_name in self.gesture_start_times,
                'mapped': gesture_name in self.gesture_mappings
            }
        
        return stats
    
    def clear_history(self):
        """Limpia el historial de gestos."""
        self.gesture_history.clear()
        self.last_gestures.clear()
        self.gesture_start_times.clear()
        self.gesture_durations.clear()
        logger.debug("✅ Historial de gestos de brazos limpiado")
    
    def set_threshold(self, threshold: float):
        """
        Establece nuevo umbral de confianza.
        
        Args:
            threshold: Nuevo umbral (0.0 a 1.0)
        """
        old_threshold = self.gesture_threshold
        self.gesture_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"🔄 Umbral cambiado: {old_threshold:.2f} -> {self.gesture_threshold:.2f}")
    
    def set_continuous_threshold(self, threshold: float):
        """
        Establece umbral para gestos continuos.
        
        Args:
            threshold: Nuevo umbral en segundos
        """
        self.continuous_threshold = max(0.5, threshold)
        logger.info(f"🔄 Umbral continuo cambiado: {threshold:.1f}s")