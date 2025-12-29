"""
🖐️ HAND DETECTOR - Detección de Manos con MediaPipe
===================================================
Detecta y rastrea manos en tiempo real usando MediaPipe Hands.
Reconoce gestos básicos como puño, paz, pulgar arriba, etc.
"""

import cv2
import mediapipe as mp
import numpy as np
import time
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class HandDetector:
    """Detector de manos utilizando MediaPipe."""
    
    def __init__(self, 
                 max_num_hands: int = 2,
                 min_detection_confidence: float = 0.7,
                 min_tracking_confidence: float = 0.5,
                 model_complexity: int = 1):
        """
        Inicializa el detector de manos.
        
        Args:
            max_num_hands: Número máximo de manos a detectar
            min_detection_confidence: Confianza mínima para detección
            min_tracking_confidence: Confianza mínima para tracking
            model_complexity: Complejidad del modelo (0, 1, 2)
        """
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Inicializar MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Configurar el modelo de manos
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=model_complexity
        )
        
        # Gestos reconocidos
        self.GESTURES = {
            'fist': self._is_fist,
            'victory': self._is_peace, # Renamed from peace as per user request
            'thumbs_up': self._is_thumbs_up,
            'thumbs_down': self._is_thumbs_down,
            'rock': self._is_rock,
            'ok': self._is_ok,
            'point': self._is_point,
            'palm': self._is_palm,
            # 'victory': self._is_victory, # Consolidated with peace
            'call_me': self._is_call_me,
            'stop': self._is_stop
        }
        
        # Landmarks importantes
        self.LANDMARK_NAMES = {
            0: 'wrist',
            1: 'thumb_cmc', 2: 'thumb_mcp', 3: 'thumb_ip', 4: 'thumb_tip',
            5: 'index_mcp', 6: 'index_pip', 7: 'index_dip', 8: 'index_tip',
            9: 'middle_mcp', 10: 'middle_pip', 11: 'middle_dip', 12: 'middle_tip',
            13: 'ring_mcp', 14: 'ring_pip', 15: 'ring_dip', 16: 'ring_tip',
            17: 'pinky_mcp', 18: 'pinky_pip', 19: 'pinky_dip', 20: 'pinky_tip'
        }
        
        # Colores para diferentes manos
        self.COLORS = {
            'left': (0, 165, 255),   # Naranja
            'right': (0, 255, 0),    # Verde
            'unknown': (255, 0, 0)   # Rojo
        }
        
        # Estadísticas
        self.stats = {
            'frames_processed': 0,
            'hands_detected': 0,
            'gestures_detected': 0,
            'fps': 0
        }
        
        # Historial para estabilizar gestos
        self.gesture_history = []
        self.history_size = 5
        
        # Para cálculo de FPS
        self.frame_count = 0
        self.start_time = time.time()
        
        logger.info(f"✅ HandDetector inicializado (max_hands={max_num_hands}, confidence={min_detection_confidence})")
    
    def detect(self, image: np.ndarray) -> Dict:
        """
        Detecta manos en la imagen.
        
        Args:
            image: Imagen BGR (OpenCV format)
            
        Returns:
            Diccionario con resultados:
            {
                'image': imagen procesada con landmarks dibujados,
                'hands': lista de información de manos detectadas,
                'gestures': lista de gestos detectados,
                'stats': estadísticas actualizadas
            }
        """
        # Calcular FPS
        self.frame_count += 1
        if time.time() - self.start_time >= 1.0:
            self.stats['fps'] = self.frame_count
            self.frame_count = 0
            self.start_time = time.time()
        
        self.stats['frames_processed'] += 1
        
        # Convertir BGR a RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        
        # Procesar imagen con MediaPipe
        results = self.hands.process(image_rgb)
        
        # Convertir de nuevo a BGR para dibujar
        image_rgb.flags.writeable = True
        processed_image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        hands_data = []
        all_gestures = []
        
        if results.multi_hand_landmarks:
            self.stats['hands_detected'] += len(results.multi_hand_landmarks)
            
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, 
                                                 results.multi_handedness):
                # Obtener información de la mano
                hand_info = self._get_hand_info(hand_landmarks, handedness, processed_image.shape)
                hands_data.append(hand_info)
                
                # Detectar gestos para esta mano
                gestures = self._detect_gestures(hand_landmarks, handedness)
                
                # ASEGURAR que siempre haya al menos un evento para el interpreter
                # aunque el detector base no reconozca nada (para mover el mouse)
                if not gestures:
                    gestures = [{
                        'type': 'hand',
                        'gesture': 'hand_tracking',
                        'hand': hand_info['handedness'],
                        'confidence': hand_info['confidence'],
                        'timestamp': time.time()
                    }]
                
                # Adjuntar hand_info (con landmarks) a cada gesto para el interpreter
                for g in gestures:
                    g['hand_info'] = hand_info
                    
                all_gestures.extend(gestures)
                self.stats['gestures_detected'] += len(gestures)
                
                # Dibujar landmarks y conexiones
                self._draw_landmarks(processed_image, hand_landmarks, handedness)
                
                # Dibujar caja delimitadora y etiqueta
                self._draw_hand_info(processed_image, hand_info, gestures)
        
        # Dibujar información del sistema
        processed_image = self._draw_system_info(processed_image)
        
        return {
            'image': processed_image,
            'hands': hands_data,
            'landmarks': [h['landmarks'] for h in hands_data],
            'gestures': all_gestures,
            'stats': self.stats.copy(),
            'raw_results': results,
            'success': True 
        }
    
    def _get_hand_info(self, landmarks, handedness, image_shape) -> Dict:
        """
        Extrae información estructurada de una mano.
        
        Args:
            landmarks: Landmarks de MediaPipe
            handedness: Información de mano izquierda/derecha
            image_shape: Forma de la imagen (height, width, channels)
            
        Returns:
            Diccionario con información de la mano
        """
        h, w, _ = image_shape
        
        # Obtener coordenadas de todos los landmarks
        landmarks_list = []
        for i, lm in enumerate(landmarks.landmark):
            x_px = int(lm.x * w)
            y_px = int(lm.y * h)
            landmarks_list.append({
                'id': i,
                'name': self.LANDMARK_NAMES.get(i, f'point_{i}'),
                'x': x_px,
                'y': y_px,
                'z': lm.z,
                'visibility': lm.visibility
            })
        
        # Calcular caja delimitadora
        xs = [lm['x'] for lm in landmarks_list]
        ys = [lm['y'] for lm in landmarks_list]
        
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        # Centro de la mano
        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2
        
        # Obtener mano izquierda/derecha
        hand_label = handedness.classification[0].label.lower()
        confidence = handedness.classification[0].score
        
        # Obtener estado de dedos
        finger_status = self._get_finger_status(landmarks)
        
        # Calcular ángulos importantes
        angles = self._calculate_hand_angles(landmarks)
        
        return {
            'landmarks': landmarks_list,
            'bbox': {
                'x_min': x_min,
                'y_min': y_min,
                'x_max': x_max,
                'y_max': y_max,
                'width': x_max - x_min,
                'height': y_max - y_min,
                'center': (center_x, center_y)
            },
            'handedness': hand_label,
            'confidence': confidence,
            'finger_status': finger_status,
            'angles': angles,
            'color': self.COLORS.get(hand_label, self.COLORS['unknown']),
            'frame_width': w,
            'frame_height': h
        }
    
    def _detect_gestures(self, landmarks, handedness) -> List[Dict]:
        """
        Detecta gestos específicos basados en landmarks.
        
        Args:
            landmarks: Landmarks de MediaPipe
            handedness: Información de mano izquierda/derecha
            
        Returns:
            Lista de gestos detectados
        """
        gestures = []
        
        for gesture_name, detector_func in self.GESTURES.items():
            try:
                if detector_func(landmarks):
                    # Calcular confianza básica
                    confidence = 0.8  # Podría calcularse basado en landmarks
                    
                    gesture = {
                        'type': 'hand',
                        'gesture': gesture_name,
                        'hand': handedness.classification[0].label.lower(),
                        'confidence': confidence,
                        'timestamp': time.time()
                    }
                    
                    # Verificar si es un gesto estable (no flickering)
                    if self._is_stable_gesture(gesture):
                        gestures.append(gesture)
                        
            except Exception as e:
                logger.debug(f"⚠️ Error detectando gesto {gesture_name}: {e}")
                continue
        
        return gestures
    
    def _is_fist(self, landmarks) -> bool:
        """Detecta si la mano está en puño (todos los dedos cerrados)."""
        # Puntos de referencia: puntas de dedos vs nudillos
        finger_tips = [8, 12, 16, 20]  # Índice, medio, anular, meñique
        finger_mcp = [5, 9, 13, 17]    # Nudillos base
        
        for tip, mcp in zip(finger_tips, finger_mcp):
            # Si la punta del dedo está más arriba que el nudillo, está extendido
            if landmarks.landmark[tip].y < landmarks.landmark[mcp].y:
                return False
        
        # Pulgar: Para un puño, el pulgar debe estar cerca de los dedos o doblado
        # No requerimos estrictamente que apunte abajo para permitir puños "laterales"
        # thumb_tip = landmarks.landmark[4]
        # thumb_ip = landmarks.landmark[3]
        # if thumb_tip.y < thumb_ip.y:
        #    return False
        
        # Check if thumb tip is close to index mcp (tucked in)
        # thumb_tip = landmarks.landmark[4]
        # index_mcp = landmarks.landmark[5]
        # distance = ((thumb_tip.x - index_mcp.x)**2 + (thumb_tip.y - index_mcp.y)**2)**0.5
        # if distance > 0.2: # If thumb is far away, it's not a fist?
        #    return False

        return True
    
    def _is_peace(self, landmarks) -> bool:
        """Detecta gesto de paz (dedos índice y medio levantados)."""
        # Índice y medio levantados
        if (landmarks.landmark[8].y < landmarks.landmark[6].y and  # Índice
            landmarks.landmark[12].y < landmarks.landmark[10].y):  # Medio
            # Anular y meñique doblados
            if (landmarks.landmark[16].y > landmarks.landmark[14].y and  # Anular
                landmarks.landmark[20].y > landmarks.landmark[18].y):    # Meñique
                # Pulgar puede estar en cualquier posición
                return True
        return False
    
    def _is_thumbs_up(self, landmarks) -> bool:
        """Detecta gesto de pulgar arriba."""
        # Pulgar extendido hacia arriba
        thumb_tip = landmarks.landmark[4]
        thumb_ip = landmarks.landmark[3]
        thumb_mcp = landmarks.landmark[2]
        
        # Pulgar debe estar más arriba que sus articulaciones y SIGNIFICATIVAMENTE arriba del índice
        if not (thumb_tip.y < thumb_ip.y < thumb_mcp.y):
            return False
            
        index_mcp = landmarks.landmark[5]
        # El pulgar debe estar más arriba que el nudillo del índice para ser un Thumbs Up claro
        if thumb_tip.y > index_mcp.y:
            return False
        
        # Los otros dedos deben estar doblados
        other_tips = [8, 12, 16, 20]  # Índice, medio, anular, meñique
        other_mcp = [5, 9, 13, 17]
        
        for tip, mcp in zip(other_tips, other_mcp):
            if landmarks.landmark[tip].y < landmarks.landmark[mcp].y:
                return False
        
        return True
    
    def _is_thumbs_down(self, landmarks) -> bool:
        """Detecta gesto de pulgar abajo."""
        # Pulgar extendido hacia abajo
        thumb_tip = landmarks.landmark[4]
        thumb_ip = landmarks.landmark[3]
        thumb_mcp = landmarks.landmark[2]
        
        # Pulgar debe estar más abajo que sus articulaciones
        if not (thumb_tip.y > thumb_ip.y > thumb_mcp.y):
            return False
        
        # Los otros dedos deben estar doblados
        other_tips = [8, 12, 16, 20]
        other_mcp = [5, 9, 13, 17]
        
        for tip, mcp in zip(other_tips, other_mcp):
            if landmarks.landmark[tip].y < landmarks.landmark[mcp].y:
                return False
        
        return True
    
    def _is_rock(self, landmarks) -> bool:
        """Detecta gesto de rock (meñique e índice levantados, otros doblados)."""
        # Índice y meñique levantados
        if (landmarks.landmark[8].y < landmarks.landmark[6].y and  # Índice
            landmarks.landmark[20].y < landmarks.landmark[18].y):  # Meñique
            # Medio y anular doblados
            if (landmarks.landmark[12].y > landmarks.landmark[10].y and  # Medio
                landmarks.landmark[16].y > landmarks.landmark[14].y):    # Anular
                return True
        return False
    
    def _is_ok(self, landmarks) -> bool:
        """Detecta gesto OK (pulgar e índice formando círculo)."""
        # Distancia entre punta del pulgar y punta del índice
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        
        distance = ((thumb_tip.x - index_tip.x) ** 2 + 
                   (thumb_tip.y - index_tip.y) ** 2) ** 0.5
        
        # Distancia pequeña indica círculo (ajustar threshold según necesidad)
        if distance < 0.05:
            # Los otros dedos pueden estar extendidos o ligeramente doblados
            return True
        return False
    
    def _is_point(self, landmarks) -> bool:
        """Detecta gesto de señalar (solo índice extendido)."""
        # Índice extendido
        if landmarks.landmark[8].y < landmarks.landmark[6].y:
            # Los otros dedos doblados
            other_tips = [12, 16, 20]  # Medio, anular, meñique
            other_mcp = [9, 13, 17]
            
            for tip, mcp in zip(other_tips, other_mcp):
                if landmarks.landmark[tip].y < landmarks.landmark[mcp].y:
                    return False
            return True
        return False
    
    def _is_palm(self, landmarks) -> bool:
        """Detecta mano abierta (todos los dedos extendidos)."""
        finger_tips = [4, 8, 12, 16, 20]  # Incluye pulgar
        finger_mcp = [2, 5, 9, 13, 17]
        
        for tip, mcp in zip(finger_tips, finger_mcp):
            # Para dedos extendidos, la punta está más arriba que el MCP
            if landmarks.landmark[tip].y > landmarks.landmark[mcp].y:
                return False
        
        # Verificar que los dedos estén razonablemente separados
        return True
    
    def _is_victory(self, landmarks) -> bool:
        """Detecta gesto de victoria (similar a peace pero con dedos separados)."""
        # Similar a peace pero con verificación adicional de separación
        if self._is_peace(landmarks):
            # Verificar que índice y medio estén separados
            index_tip = landmarks.landmark[8]
            middle_tip = landmarks.landmark[12]
            
            distance = ((index_tip.x - middle_tip.x) ** 2 + 
                       (index_tip.y - middle_tip.y) ** 2) ** 0.5
            
            if distance > 0.03:  # Dedos separados
                return True
        
        return False
    
    def _is_call_me(self, landmarks) -> bool:
        """Detecta gesto de 'llámame' (Shaka: Pulgar y Meñique extendidos)."""
        # 1. Meñique debe estar EXTENDIDO (Tip arriba de PIP en mano vertical)
        if not (landmarks.landmark[20].y < landmarks.landmark[18].y):
             return False

        # 2. Dedos centrales DOBLADOS (Índice, Medio, Anular)
        # Tip debe estar ABAJO del MCP (y mayor)
        folded_tips = [8, 12, 16]
        folded_mcp = [5, 9, 13]
        for tip, mcp in zip(folded_tips, folded_mcp):
             if landmarks.landmark[tip].y < landmarks.landmark[mcp].y: # Si alguno está extendido (arriba)
                 return False

        # 3. Pulgar EXTENDIDO (Relaxed)
        thumb_tip = landmarks.landmark[4]
        index_mcp = landmarks.landmark[5]
        
        # Distancia para asegurar que no está pegado
        distance = ((thumb_tip.x - index_mcp.x)**2 + (thumb_tip.y - index_mcp.y)**2)**0.5
        if distance < 0.1: 
             return False
             
        return True
    
    def _is_stop(self, landmarks) -> bool:
        """Detecta gesto de 'stop' (mano abierta con dedos juntos)."""
        if self._is_palm(landmarks):
            # Verificar que los dedos estén relativamente juntos
            tips = [8, 12, 16, 20]  # Puntas de dedos (sin pulgar)
            
            # Calcular distancia promedio entre puntas
            distances = []
            for i in range(len(tips)):
                for j in range(i + 1, len(tips)):
                    tip1 = landmarks.landmark[tips[i]]
                    tip2 = landmarks.landmark[tips[j]]
                    distance = ((tip1.x - tip2.x) ** 2 + (tip1.y - tip2.y) ** 2) ** 0.5
                    distances.append(distance)
            
            if distances:
                avg_distance = sum(distances) / len(distances)
                if avg_distance < 0.08:  # Dedos juntos
                    return True
        
        return False
    
    def _get_finger_status(self, landmarks) -> Dict[str, str]:
        """
        Obtiene el estado de cada dedo (extendido/doblado).
        
        Args:
            landmarks: Landmarks de MediaPipe
            
        Returns:
            Diccionario con estado de cada dedo
        """
        status = {}
        
        # Mapeo de dedos a puntos de referencia
        fingers = {
            'thumb': [(2, 3), (3, 4)],
            'index': [(5, 6), (6, 7), (7, 8)],
            'middle': [(9, 10), (10, 11), (11, 12)],
            'ring': [(13, 14), (14, 15), (15, 16)],
            'pinky': [(17, 18), (18, 19), (19, 20)]
        }
        
        for finger_name, joints in fingers.items():
            extended = True
            
            for joint_start, joint_end in joints:
                # Si la articulación distal está más abajo que la proximal, está doblado
                if landmarks.landmark[joint_end].y > landmarks.landmark[joint_start].y:
                    extended = False
                    break
            
            status[finger_name] = 'extended' if extended else 'bent'
        
        return status
    
    def _calculate_hand_angles(self, landmarks) -> Dict[str, float]:
        """
        Calcula ángulos importantes de la mano.
        
        Args:
            landmarks: Landmarks de MediaPipe
            
        Returns:
            Diccionario con ángulos en grados
        """
        import math
        
        def calculate_angle(a, b, c):
            """Calcula el ángulo entre tres puntos."""
            a = np.array([a.x, a.y])
            b = np.array([b.x, b.y])
            c = np.array([c.x, c.y])
            
            ba = a - b
            bc = c - b
            
            cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            cosine_angle = max(-1.0, min(1.0, cosine_angle))  # Clamp
            angle = math.degrees(math.acos(cosine_angle))
            
            return angle
        
        angles = {}
        
        # Ángulo del pulgar
        try:
            angles['thumb'] = calculate_angle(
                landmarks.landmark[2],  # CMC
                landmarks.landmark[3],  # IP
                landmarks.landmark[4]   # Tip
            )
        except:
            angles['thumb'] = 0.0
        
        # Ángulo del índice
        try:
            angles['index'] = calculate_angle(
                landmarks.landmark[5],  # MCP
                landmarks.landmark[6],  # PIP
                landmarks.landmark[8]   # Tip
            )
        except:
            angles['index'] = 0.0
        
        # Ángulo entre índice y pulgar
        try:
            angles['thumb_index'] = calculate_angle(
                landmarks.landmark[4],  # Thumb tip
                landmarks.landmark[0],  # Wrist
                landmarks.landmark[8]   # Index tip
            )
        except:
            angles['thumb_index'] = 0.0
        
        return angles
    
    def _is_stable_gesture(self, gesture: Dict) -> bool:
        """
        Verifica si un gesto es estable (evita flickering).
        
        Args:
            gesture: Diccionario con información del gesto
            
        Returns:
            True si el gesto es estable
        """
        # Agregar a historial
        self.gesture_history.append(gesture.copy())
        if len(self.gesture_history) > self.history_size:
            self.gesture_history.pop(0)
        
        # Si no hay suficiente historial, aceptar el gesto
        if len(self.gesture_history) < 3:
            return True
        
        # Contar cuántas veces aparece este gesto en el historial
        same_gesture_count = 0
        for g in self.gesture_history[-3:]:  # Últimos 3 frames
            if (g.get('gesture') == gesture['gesture'] and 
                g.get('hand') == gesture['hand']):
                same_gesture_count += 1
        
        # Requerir al menos 2 de 3 frames con el mismo gesto
        return same_gesture_count >= 2
    
    def _draw_landmarks(self, image, landmarks, handedness):
        """Dibuja landmarks y conexiones de la mano."""
        # Dibujar conexiones
        self.mp_drawing.draw_landmarks(
            image,
            landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing_styles.get_default_hand_landmarks_style(),
            self.mp_drawing_styles.get_default_hand_connections_style()
        )
    
    def _draw_hand_info(self, image, hand_info, gestures):
        """Dibuja información adicional de la mano."""
        bbox = hand_info['bbox']
        color = hand_info['color']
        hand_label = hand_info['handedness'].capitalize()
        confidence = hand_info['confidence']
        
        # Dibujar caja delimitadora
        cv2.rectangle(image, 
                     (bbox['x_min'], bbox['y_min']),
                     (bbox['x_max'], bbox['y_max']),
                     color, 2)
        
        # Dibujar etiqueta de mano
        label = f"{hand_label} ({confidence:.2f})"
        cv2.putText(image, label, 
                   (bbox['x_min'], bbox['y_min'] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Dibujar gestos detectados
        if gestures:
            pass # Eliminar texto de gestos para limpiar UI
            # gesture_text = ", ".join([g['gesture'] for g in gestures])
            # cv2.putText(image, gesture_text,
            #            (bbox['x_min'], bbox['y_max'] + 20),
            #            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Dibujar centro de la mano
        cv2.circle(image, bbox['center'], 5, color, -1)
    
    def _draw_system_info(self, image):
        """Dibuja información del sistema en la imagen."""
        # Deshabilitar overlay de sistema (barra negra con texto)
        return image
        
        # h, w = image.shape[:2]
        # 
        # # Fondo semitransparente para texto
        # overlay = image.copy()
        # cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
        # cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
        # 
        # # Información del detector
        # cv2.putText(image, f"🖐️ Hand Detector - FPS: {self.stats['fps']}", 
        #            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        # 
        # cv2.putText(image, f"Manos detectadas: {self.stats['hands_detected']} | Gestos: {self.stats['gestures_detected']}", 
        #            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        # 
        # cv2.putText(image, f"Confianza: {self.min_detection_confidence} | Máx manos: {self.max_num_hands}", 
        #            (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return image
    
    def get_detection_info(self) -> Dict:
        """Obtiene información de configuración del detector."""
        return {
            'max_num_hands': self.max_num_hands,
            'min_detection_confidence': self.min_detection_confidence,
            'min_tracking_confidence': self.min_tracking_confidence,
            'gestures_available': list(self.GESTURES.keys()),
            'stats': self.stats.copy()
        }
    
    def update_config(self, **kwargs):
        """Actualiza configuración del detector."""
        if 'max_num_hands' in kwargs:
            self.max_num_hands = kwargs['max_num_hands']
        
        if 'min_detection_confidence' in kwargs:
            self.min_detection_confidence = kwargs['min_detection_confidence']
        
        if 'min_tracking_confidence' in kwargs:
            self.min_tracking_confidence = kwargs['min_tracking_confidence']
        
        # Reiniciar el modelo con nueva configuración
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=self.max_num_hands,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
            model_complexity=1
        )
        
        logger.info(f"🔄 Configuración actualizada: {kwargs}")
    
    def release(self):
        """Libera recursos del detector."""
        if hasattr(self, 'hands'):
            self.hands.close()
            logger.info("✅ Recursos de HandDetector liberados")