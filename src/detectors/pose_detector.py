"""
🧍 POSE DETECTOR - Detección de Postura Completa
===============================================
Detecta postura corporal completa usando MediaPipe Pose.
Útil para gestos que involucran todo el cuerpo.
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import math
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class PoseDetector:
    """Detector de postura corporal completa."""
    
    def __init__(self, 
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5,
                 model_complexity: int = 1,
                 enable_segmentation: bool = False,
                 smooth_landmarks: bool = True):
        """
        Inicializa el detector de postura.
        
        Args:
            min_detection_confidence: Confianza mínima para detección
            min_tracking_confidence: Confianza mínima para tracking
            model_complexity: Complejidad del modelo (0: Lite, 1: Full, 2: Heavy)
            enable_segmentation: Habilita segmentación de silueta
            smooth_landmarks: Suaviza landmarks entre frames
        """
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity
        self.enable_segmentation = enable_segmentation
        self.smooth_landmarks = smooth_landmarks
        
        # Inicializar MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Configurar el modelo de pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            smooth_landmarks=smooth_landmarks,
            enable_segmentation=enable_segmentation,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # Landmarks de MediaPipe Pose (33 puntos)
        self.LANDMARK_IDS = {
            'nose': self.mp_pose.PoseLandmark.NOSE,
            'left_eye_inner': self.mp_pose.PoseLandmark.LEFT_EYE_INNER,
            'left_eye': self.mp_pose.PoseLandmark.LEFT_EYE,
            'left_eye_outer': self.mp_pose.PoseLandmark.LEFT_EYE_OUTER,
            'right_eye_inner': self.mp_pose.PoseLandmark.RIGHT_EYE_INNER,
            'right_eye': self.mp_pose.PoseLandmark.RIGHT_EYE,
            'right_eye_outer': self.mp_pose.PoseLandmark.RIGHT_EYE_OUTER,
            'left_ear': self.mp_pose.PoseLandmark.LEFT_EAR,
            'right_ear': self.mp_pose.PoseLandmark.RIGHT_EAR,
            'mouth_left': self.mp_pose.PoseLandmark.MOUTH_LEFT,
            'mouth_right': self.mp_pose.PoseLandmark.MOUTH_RIGHT,
            'left_shoulder': self.mp_pose.PoseLandmark.LEFT_SHOULDER,
            'right_shoulder': self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            'left_elbow': self.mp_pose.PoseLandmark.LEFT_ELBOW,
            'right_elbow': self.mp_pose.PoseLandmark.RIGHT_ELBOW,
            'left_wrist': self.mp_pose.PoseLandmark.LEFT_WRIST,
            'right_wrist': self.mp_pose.PoseLandmark.RIGHT_WRIST,
            'left_pinky': self.mp_pose.PoseLandmark.LEFT_PINKY,
            'right_pinky': self.mp_pose.PoseLandmark.RIGHT_PINKY,
            'left_index': self.mp_pose.PoseLandmark.LEFT_INDEX,
            'right_index': self.mp_pose.PoseLandmark.RIGHT_INDEX,
            'left_thumb': self.mp_pose.PoseLandmark.LEFT_THUMB,
            'right_thumb': self.mp_pose.PoseLandmark.RIGHT_THUMB,
            'left_hip': self.mp_pose.PoseLandmark.LEFT_HIP,
            'right_hip': self.mp_pose.PoseLandmark.RIGHT_HIP,
            'left_knee': self.mp_pose.PoseLandmark.LEFT_KNEE,
            'right_knee': self.mp_pose.PoseLandmark.RIGHT_KNEE,
            'left_ankle': self.mp_pose.PoseLandmark.LEFT_ANKLE,
            'right_ankle': self.mp_pose.PoseLandmark.RIGHT_ANKLE,
            'left_heel': self.mp_pose.PoseLandmark.LEFT_HEEL,
            'right_heel': self.mp_pose.PoseLandmark.RIGHT_HEEL,
            'left_foot_index': self.mp_pose.PoseLandmark.LEFT_FOOT_INDEX,
            'right_foot_index': self.mp_pose.PoseLandmark.RIGHT_FOOT_INDEX
        }
        
        # Grupos de landmarks para diferentes partes del cuerpo
        self.BODY_PARTS = {
            'face': ['nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear', 'mouth_left', 'mouth_right'],
            'upper_body': ['left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 
                          'left_wrist', 'right_wrist', 'left_hip', 'right_hip'],
            'lower_body': ['left_knee', 'right_knee', 'left_ankle', 'right_ankle',
                          'left_heel', 'right_heel', 'left_foot_index', 'right_foot_index'],
            'left_arm': ['left_shoulder', 'left_elbow', 'left_wrist', 'left_pinky', 'left_index', 'left_thumb'],
            'right_arm': ['right_shoulder', 'right_elbow', 'right_wrist', 'right_pinky', 'right_index', 'right_thumb'],
            'left_leg': ['left_hip', 'left_knee', 'left_ankle', 'left_heel', 'left_foot_index'],
            'right_leg': ['right_hip', 'right_knee', 'right_ankle', 'right_heel', 'right_foot_index']
        }
        
        # Posturas reconocidas
        self.POSTURES = {
            'standing': self._is_standing,
            'sitting': self._is_sitting,
            'walking': self._is_walking,
            'jumping': self._is_jumping,
            't_pose': self._is_t_pose,
            'x_pose': self._is_x_pose,
            'raising_hands': self._is_raising_hands,
            'hands_on_hips': self._is_hands_on_hips,
            'leaning_left': self._is_leaning_left,
            'leaning_right': self._is_leaning_right,
            'bending': self._is_bending,
            'crouching': self._is_crouching
        }
        
        # Colores para diferentes partes del cuerpo
        self.COLORS = {
            'face': (255, 200, 0),      # Amarillo dorado
            'upper_body': (0, 255, 0),   # Verde
            'lower_body': (0, 0, 255),   # Rojo
            'left_side': (0, 165, 255),  # Naranja
            'right_side': (255, 0, 255), # Magenta
            'landmark': (255, 255, 255), # Blanco
            'connection': (200, 200, 200) # Gris
        }
        
        # Umbrales para detección de posturas
        self.THRESHOLDS = {
            'standing_knee_angle': 160,      # Ángulo mínimo de rodilla para estar de pie
            'sitting_knee_angle': 90,        # Ángulo máximo de rodilla para estar sentado
            'hip_knee_ratio': 0.8,           # Ratio cadera-rodilla para sentado
            'arm_raised_y': 0.2,             # Manos esta fracción arriba de hombros
            't_pose_arm_extension': 0.3,     # Extensión para T-pose
            'lean_threshold': 0.1,           # Inclinación significativa
            'jump_height': 0.15,             # Cambio en altura para salto
            'walking_leg_angle': 30          # Ángulo entre piernas para caminar
        }
        
        # Estadísticas
        self.stats = {
            'frames_processed': 0,
            'poses_detected': 0,
            'postures_detected': 0,
            'fps': 0,
            'tracking_quality': 0.0
        }
        
        # Historial para estabilizar posturas
        self.posture_history = []
        self.history_size = 10
        
        # Para cálculo de FPS y movimiento
        self.frame_count = 0
        self.start_time = time.time()
        self.previous_landmarks = None
        self.movement_history = []
        
        logger.info(f"✅ PoseDetector inicializado (model_complexity={model_complexity})")
    
    def detect(self, image: np.ndarray) -> Dict:
        """
        Detecta postura corporal en la imagen.
        
        Args:
            image: Imagen BGR (OpenCV format)
            
        Returns:
            Diccionario con resultados
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
        
        # Procesar imagen con MediaPipe Pose
        results = self.pose.process(image_rgb)
        
        # Convertir de nuevo a BGR para dibujar
        image_rgb.flags.writeable = True
        processed_image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        landmarks_data = {}
        postures = []
        angles = {}
        movement_info = {}
        
        if results.pose_landmarks:
            self.stats['poses_detected'] += 1
            
            # Extraer landmarks
            landmarks_data = self._extract_landmarks(results.pose_landmarks, processed_image.shape)
            
            # Calcular calidad de tracking
            self.stats['tracking_quality'] = self._calculate_tracking_quality(landmarks_data)
            
            # Calcular ángulos importantes
            angles = self._calculate_body_angles(landmarks_data)
            
            # Calcular información de movimiento
            movement_info = self._calculate_movement(landmarks_data)
            
            # Detectar posturas
            postures = self._detect_postures(landmarks_data, angles, movement_info)
            if postures:
                self.stats['postures_detected'] += len(postures)
            
            # Dibujar landmarks y conexiones
            self._draw_landmarks(processed_image, results.pose_landmarks, results.pose_world_landmarks)
            
            # Dibujar segmentación si está habilitada
            if self.enable_segmentation and results.segmentation_mask is not None:
                processed_image = self._draw_segmentation(processed_image, results.segmentation_mask)
            
            # Dibujar información adicional
            if landmarks_data:
                self._draw_body_info(processed_image, landmarks_data, angles, postures, movement_info)
        
        # Dibujar información del sistema
        processed_image = self._draw_system_info(processed_image)
        
        return {
            'image': processed_image,
            'landmarks': landmarks_data,
            'postures': postures,
            'angles': angles,
            'movement': movement_info,
            'stats': self.stats.copy(),
            'raw_results': results
        }
    
    def _extract_landmarks(self, landmarks, image_shape) -> Dict:
        """
        Extrae landmarks normalizados y en píxeles.
        
        Args:
            landmarks: Landmarks de MediaPipe Pose
            image_shape: Forma de la imagen (height, width, channels)
            
        Returns:
            Diccionario con landmarks
        """
        h, w, _ = image_shape
        landmarks_data = {}
        
        for name, landmark_id in self.LANDMARK_IDS.items():
            landmark = landmarks.landmark[landmark_id]
            
            landmarks_data[name] = {
                'x': landmark.x,           # Normalizado [0, 1]
                'y': landmark.y,           # Normalizado [0, 1]
                'z': landmark.z,           # Profundidad
                'visibility': landmark.visibility,
                'x_px': int(landmark.x * w),  # En píxeles
                'y_px': int(landmark.y * h),  # En píxeles
                'id': landmark_id.value,
                'name': name
            }
        
        return landmarks_data
    
    def _calculate_tracking_quality(self, landmarks: Dict) -> float:
        """
        Calcula calidad de tracking basada en visibilidad de landmarks.
        
        Args:
            landmarks: Diccionario con landmarks
            
        Returns:
            Calidad entre 0 y 1
        """
        if not landmarks:
            return 0.0
        
        # Landmarks importantes para calidad
        key_landmarks = ['nose', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip']
        visibilities = []
        
        for name in key_landmarks:
            if name in landmarks:
                visibilities.append(landmarks[name]['visibility'])
        
        if not visibilities:
            return 0.0
        
        return sum(visibilities) / len(visibilities)
    
    def _calculate_body_angles(self, landmarks: Dict) -> Dict:
        """
        Calcula ángulos importantes del cuerpo.
        
        Args:
            landmarks: Diccionario con landmarks
            
        Returns:
            Diccionario con ángulos en grados
        """
        angles = {}
        
        def calculate_angle(a, b, c):
            """Calcula el ángulo ABC en grados."""
            try:
                a_vec = np.array([a['x'], a['y']])
                b_vec = np.array([b['x'], b['y']])
                c_vec = np.array([c['x'], c['y']])
                
                ba = a_vec - b_vec
                bc = c_vec - b_vec
                
                dot_product = np.dot(ba, bc)
                norm_ba = np.linalg.norm(ba)
                norm_bc = np.linalg.norm(bc)
                
                if norm_ba == 0 or norm_bc == 0:
                    return 0.0
                
                cosine_angle = dot_product / (norm_ba * norm_bc)
                cosine_angle = max(-1.0, min(1.0, cosine_angle))
                angle_rad = math.acos(cosine_angle)
                
                return math.degrees(angle_rad)
            except:
                return 0.0
        
        # Ángulos de las rodillas (para sentado/de pie)
        if all(k in landmarks for k in ['left_hip', 'left_knee', 'left_ankle']):
            angles['left_knee'] = calculate_angle(
                landmarks['left_hip'],
                landmarks['left_knee'],
                landmarks['left_ankle']
            )
        
        if all(k in landmarks for k in ['right_hip', 'right_knee', 'right_ankle']):
            angles['right_knee'] = calculate_angle(
                landmarks['right_hip'],
                landmarks['right_knee'],
                landmarks['right_ankle']
            )
        
        # Ángulos de los codos
        if all(k in landmarks for k in ['left_shoulder', 'left_elbow', 'left_wrist']):
            angles['left_elbow'] = calculate_angle(
                landmarks['left_shoulder'],
                landmarks['left_elbow'],
                landmarks['left_wrist']
            )
        
        if all(k in landmarks for k in ['right_shoulder', 'right_elbow', 'right_wrist']):
            angles['right_elbow'] = calculate_angle(
                landmarks['right_shoulder'],
                landmarks['right_elbow'],
                landmarks['right_wrist']
            )
        
        # Ángulo de inclinación del torso
        if all(k in landmarks for k in ['left_shoulder', 'left_hip', 'right_hip']):
            # Ángulo entre hombros y cadera (para inclinación lateral)
            mid_shoulder = {
                'x': (landmarks['left_shoulder']['x'] + landmarks['right_shoulder']['x']) / 2,
                'y': (landmarks['left_shoulder']['y'] + landmarks['right_shoulder']['y']) / 2
            }
            mid_hip = {
                'x': (landmarks['left_hip']['x'] + landmarks['right_hip']['x']) / 2,
                'y': (landmarks['left_hip']['y'] + landmarks['right_hip']['y']) / 2
            }
            
            # Punto de referencia vertical
            vertical_point = {'x': mid_shoulder['x'], 'y': mid_shoulder['y'] - 0.1}
            
            angles['torso_lean'] = calculate_angle(
                vertical_point,
                mid_shoulder,
                mid_hip
            )
        
        # Ángulo entre piernas (para caminar)
        if all(k in landmarks for k in ['left_hip', 'left_knee', 'right_knee']):
            angles['leg_spread'] = calculate_angle(
                landmarks['left_knee'],
                landmarks['left_hip'],
                landmarks['right_knee']
            )
        
        return angles
    
    def _calculate_movement(self, current_landmarks: Dict) -> Dict:
        """
        Calcula información de movimiento comparando con frame anterior.
        
        Args:
            current_landmarks: Landmarks del frame actual
            
        Returns:
            Diccionario con información de movimiento
        """
        movement = {
            'speed': 0.0,
            'direction': 'stationary',
            'height_change': 0.0,
            'is_moving': False
        }
        
        if self.previous_landmarks is None:
            self.previous_landmarks = current_landmarks
            return movement
        
        # Calcular movimiento promedio de landmarks clave
        key_points = ['nose', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip']
        total_movement = 0.0
        count = 0
        
        for point in key_points:
            if point in current_landmarks and point in self.previous_landmarks:
                dx = current_landmarks[point]['x'] - self.previous_landmarks[point]['x']
                dy = current_landmarks[point]['y'] - self.previous_landmarks[point]['y']
                distance = math.sqrt(dx*dx + dy*dy)
                total_movement += distance
                count += 1
        
        if count > 0:
            movement['speed'] = total_movement / count
            
            # Determinar si se está moviendo
            movement['is_moving'] = movement['speed'] > 0.01
            
            # Dirección general
            if movement['speed'] > 0.02:
                # Para simplificar, usar movimiento vertical como indicador
                if 'nose' in current_landmarks and 'nose' in self.previous_landmarks:
                    height_diff = current_landmarks['nose']['y'] - self.previous_landmarks['nose']['y']
                    movement['height_change'] = height_diff
                    
                    if abs(height_diff) > 0.02:
                        movement['direction'] = 'up' if height_diff < 0 else 'down'
                    else:
                        movement['direction'] = 'horizontal'
        
        # Guardar para siguiente frame
        self.previous_landmarks = current_landmarks.copy()
        
        return movement
    
    def _detect_postures(self, landmarks: Dict, angles: Dict, movement: Dict) -> List[Dict]:
        """
        Detecta posturas corporales basadas en landmarks, ángulos y movimiento.
        
        Args:
            landmarks: Diccionario con landmarks
            angles: Diccionario con ángulos
            movement: Diccionario con información de movimiento
            
        Returns:
            Lista de posturas detectadas
        """
        postures = []
        current_time = time.time()
        
        for posture_name, detector_func in self.POSTURES.items():
            try:
                if detector_func(landmarks, angles, movement):
                    # Calcular confianza
                    confidence = self._calculate_posture_confidence(landmarks, posture_name)
                    
                    posture = {
                        'type': 'pose',
                        'posture': posture_name,
                        'confidence': confidence,
                        'timestamp': current_time
                    }
                    
                    # Verificar si es una postura estable
                    if self._is_stable_posture(posture):
                        postures.append(posture)
                        
            except Exception as e:
                logger.debug(f"⚠️ Error detectando postura {posture_name}: {e}")
                continue
        
        return postures
    
    def _is_standing(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta postura de pie."""
        # Verificar ángulos de rodilla
        left_knee = angles.get('left_knee', 180)
        right_knee = angles.get('right_knee', 180)
        
        # Rodillas casi rectas
        return (left_knee > self.THRESHOLDS['standing_knee_angle'] and 
                right_knee > self.THRESHOLDS['standing_knee_angle'])
    
    def _is_sitting(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta postura sentada."""
        # Ángulos de rodilla doblados
        left_knee = angles.get('left_knee', 180)
        right_knee = angles.get('right_knee', 180)
        
        # Rodillas dobladas y caderas más bajas que rodillas
        if (left_knee < self.THRESHOLDS['sitting_knee_angle'] and 
            right_knee < self.THRESHOLDS['sitting_knee_angle']):
            
            if 'left_hip' in landmarks and 'left_knee' in landmarks:
                # Cadera más baja que rodilla
                hip_knee_ratio = landmarks['left_hip']['y'] / landmarks['left_knee']['y']
                return hip_knee_ratio > self.THRESHOLDS['hip_knee_ratio']
        
        return False
    
    def _is_walking(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta caminando."""
        # Movimiento significativo y piernas separadas
        if movement.get('is_moving', False) and movement.get('speed', 0) > 0.02:
            leg_spread = angles.get('leg_spread', 0)
            return leg_spread > self.THRESHOLDS['walking_leg_angle']
        
        return False
    
    def _is_jumping(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta salto."""
        # Movimiento vertical rápido hacia arriba
        return (movement.get('direction') == 'up' and 
                abs(movement.get('height_change', 0)) > self.THRESHOLDS['jump_height'])
    
    def _is_t_pose(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta T-pose (brazos extendidos a los lados)."""
        if 'left_wrist' not in landmarks or 'right_wrist' not in landmarks:
            return False
        
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks.get('left_shoulder', {'x': 0, 'y': 0})
        rs = landmarks.get('right_shoulder', {'x': 0, 'y': 0})
        
        # Brazos extendidos horizontalmente
        return (abs(lw['y'] - ls['y']) < 0.1 and
                abs(rw['y'] - rs['y']) < 0.1 and
                lw['x'] < ls['x'] - self.THRESHOLDS['t_pose_arm_extension'] and
                rw['x'] > rs['x'] + self.THRESHOLDS['t_pose_arm_extension'])
    
    def _is_x_pose(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta X-pose (brazos y piernas extendidos en diagonal)."""
        # Similar a T-pose pero con piernas también separadas
        if not self._is_t_pose(landmarks, angles, movement):
            return False
        
        # Verificar separación de piernas
        if 'left_ankle' in landmarks and 'right_ankle' in landmarks:
            la = landmarks['left_ankle']
            ra = landmarks['right_ankle']
            lh = landmarks.get('left_hip', {'x': 0})
            rh = landmarks.get('right_hip', {'x': 0})
            
            return (la['x'] < lh['x'] and ra['x'] > rh['x'])
        
        return False
    
    def _is_raising_hands(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta manos levantadas."""
        if 'left_wrist' not in landmarks or 'right_wrist' not in landmarks:
            return False
        
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks.get('left_shoulder', {'y': 0})
        rs = landmarks.get('right_shoulder', {'y': 0})
        
        # Ambas manos arriba de los hombros
        return (lw['y'] < ls['y'] - self.THRESHOLDS['arm_raised_y'] and
                rw['y'] < rs['y'] - self.THRESHOLDS['arm_raised_y'])
    
    def _is_hands_on_hips(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta manos en las caderas."""
        if 'left_wrist' not in landmarks or 'right_wrist' not in landmarks:
            return False
        
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        lh = landmarks.get('left_hip', {'x': 0, 'y': 0})
        rh = landmarks.get('right_hip', {'x': 0, 'y': 0})
        
        # Manos cerca de las caderas
        return (abs(lw['x'] - lh['x']) < 0.1 and abs(lw['y'] - lh['y']) < 0.1 and
                abs(rw['x'] - rh['x']) < 0.1 and abs(rw['y'] - rh['y']) < 0.1)
    
    def _is_leaning_left(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta inclinación hacia la izquierda."""
        lean_angle = angles.get('torso_lean', 90)
        
        # Ángulo significativo y dirección
        if abs(lean_angle - 90) > self.THRESHOLDS['lean_threshold']:
            # Determinar dirección basada en posición de hombros
            if 'left_shoulder' in landmarks and 'right_shoulder' in landmarks:
                return landmarks['left_shoulder']['y'] > landmarks['right_shoulder']['y']
        
        return False
    
    def _is_leaning_right(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta inclinación hacia la derecha."""
        lean_angle = angles.get('torso_lean', 90)
        
        if abs(lean_angle - 90) > self.THRESHOLDS['lean_threshold']:
            if 'left_shoulder' in landmarks and 'right_shoulder' in landmarks:
                return landmarks['right_shoulder']['y'] > landmarks['left_shoulder']['y']
        
        return False
    
    def _is_bending(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta inclinación hacia adelante."""
        if 'nose' in landmarks and 'left_hip' in landmarks:
            # Nariz significativamente más baja que cadera
            return landmarks['nose']['y'] > landmarks['left_hip']['y'] + 0.2
        
        return False
    
    def _is_crouching(self, landmarks: Dict, angles: Dict, movement: Dict) -> bool:
        """Detecta agachado."""
        # Combinación de sentado y bajo
        if self._is_sitting(landmarks, angles, movement):
            if 'nose' in landmarks and 'left_knee' in landmarks:
                # Muy bajo (nariz cerca de rodillas)
                return abs(landmarks['nose']['y'] - landmarks['left_knee']['y']) < 0.3
        
        return False
    
    def _calculate_posture_confidence(self, landmarks: Dict, posture_name: str) -> float:
        """
        Calcula confianza para una postura.
        
        Args:
            landmarks: Diccionario con landmarks
            posture_name: Nombre de la postura
            
        Returns:
            Confianza entre 0 y 1
        """
        # Base en visibilidad de landmarks relevantes
        if posture_name in ['standing', 'sitting']:
            key_landmarks = ['left_knee', 'right_knee', 'left_hip', 'right_hip']
        elif posture_name in ['t_pose', 'x_pose', 'raising_hands']:
            key_landmarks = ['left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder']
        elif posture_name in ['walking', 'jumping']:
            key_landmarks = ['left_ankle', 'right_ankle', 'left_hip', 'right_hip']
        else:
            key_landmarks = ['nose', 'left_shoulder', 'right_shoulder']
        
        # Calcular visibilidad promedio
        visibilities = []
        for landmark_name in key_landmarks:
            if landmark_name in landmarks:
                visibilities.append(landmarks[landmark_name]['visibility'])
        
        if not visibilities:
            return 0.5
        
        avg_visibility = sum(visibilities) / len(visibilities)
        return min(avg_visibility * 1.2, 1.0)  # Aumentar ligeramente
    
    def _is_stable_posture(self, posture: Dict) -> bool:
        """
        Verifica si una postura es estable.
        
        Args:
            posture: Diccionario con información de postura
            
        Returns:
            True si la postura es estable
        """
        # Agregar a historial
        self.posture_history.append(posture.copy())
        if len(self.posture_history) > self.history_size:
            self.posture_history.pop(0)
        
        # Si no hay suficiente historial, aceptar
        if len(self.posture_history) < 5:
            return True
        
        # Contar ocurrencias recientes
        same_count = 0
        for p in self.posture_history[-5:]:
            if p.get('posture') == posture['posture']:
                same_count += 1
        
        # Requerir mayoría
        return same_count >= 3
    
    def _draw_landmarks(self, image, landmarks, world_landmarks=None):
        """Dibuja landmarks y conexiones."""
        # Dibujar en imagen 2D
        self.mp_drawing.draw_landmarks(
            image,
            landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(
                color=self.COLORS['landmark'], thickness=2, circle_radius=3
            ),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(
                color=self.COLORS['connection'], thickness=2
            )
        )
    
    def _draw_segmentation(self, image, segmentation_mask):
        """Dibuja máscara de segmentación."""
        # Convertir máscara a 3 canales
        condition = np.stack((segmentation_mask,) * 3, axis=-1) > 0.1
        bg_image = np.zeros(image.shape, dtype=np.uint8)
        bg_image[:] = (0, 0, 0)  # Fondo negro
        
        # Aplicar máscara
        output_image = np.where(condition, image, bg_image)
        return output_image
    
    def _draw_body_info(self, image, landmarks, angles, postures, movement):
        """Dibuja información adicional del cuerpo."""
        h, w = image.shape[:2]
        
        # Dibujar posturas detectadas
        if postures:
            posture_text = ", ".join([p['posture'].replace('_', ' ') for p in postures[:3]])
            cv2.putText(image, f"Postures: {posture_text}",
                       (20, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Dibujar información de movimiento
        if movement.get('is_moving', False):
            speed_text = f"Speed: {movement['speed']:.3f}"
            cv2.putText(image, speed_text,
                       (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
        
        # Dibujar ángulos importantes
        angle_text = ""
        if 'left_knee' in angles:
            angle_text += f"Knee: {angles['left_knee']:.0f}° "
        if 'torso_lean' in angles:
            angle_text += f"Lean: {angles['torso_lean']:.0f}°"
        
        if angle_text:
            cv2.putText(image, angle_text,
                       (w - 300, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Dibujar centro de gravedad estimado
        if 'left_hip' in landmarks and 'right_hip' in landmarks:
            lh = landmarks['left_hip']
            rh = landmarks['right_hip']
            cog_x = (lh['x_px'] + rh['x_px']) // 2
            cog_y = (lh['y_px'] + rh['y_px']) // 2
            
            cv2.circle(image, (cog_x, cog_y), 8, (0, 255, 255), -1)
            cv2.circle(image, (cog_x, cog_y), 10, (0, 255, 255), 2)
    
    def _draw_system_info(self, image):
        """Dibuja información del sistema."""
        h, w = image.shape[:2]
        
        # Fondo semitransparente
        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
        
        # Información del detector
        cv2.putText(image, f"🧍 Pose Detector - FPS: {self.stats['fps']}", 
                   (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        quality_text = f"Quality: {self.stats['tracking_quality']:.2f}"
        cv2.putText(image, quality_text,
                   (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return image
    
    def get_detection_info(self) -> Dict:
        """Obtiene información de configuración."""
        return {
            'min_detection_confidence': self.min_detection_confidence,
            'min_tracking_confidence': self.min_tracking_confidence,
            'model_complexity': self.model_complexity,
            'enable_segmentation': self.enable_segmentation,
            'postures_available': list(self.POSTURES.keys()),
            'stats': self.stats.copy()
        }
    
    def update_config(self, **kwargs):
        """Actualiza configuración."""
        if 'min_detection_confidence' in kwargs:
            self.min_detection_confidence = kwargs['min_detection_confidence']
        
        if 'min_tracking_confidence' in kwargs:
            self.min_tracking_confidence = kwargs['min_tracking_confidence']
        
        if 'model_complexity' in kwargs:
            self.model_complexity = kwargs['model_complexity']
        
        if 'enable_segmentation' in kwargs:
            self.enable_segmentation = kwargs['enable_segmentation']
        
        # Actualizar umbrales
        for threshold_name, value in kwargs.items():
            if threshold_name in self.THRESHOLDS:
                self.THRESHOLDS[threshold_name] = value
        
        # Reiniciar modelo
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=self.model_complexity,
            smooth_landmarks=self.smooth_landmarks,
            enable_segmentation=self.enable_segmentation,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )
        
        logger.info(f"🔄 PoseDetector config updated: {kwargs}")
    
    def release(self):
        """Libera recursos."""
        if hasattr(self, 'pose'):
            self.pose.close()
            logger.info("✅ PoseDetector resources released")
    
    def get_body_metrics(self, landmarks: Dict) -> Dict:
        """
        Calcula métricas corporales.
        
        Args:
            landmarks: Diccionario con landmarks
            
        Returns:
            Diccionario con métricas
        """
        metrics = {}
        
        # Altura estimada (nariz a tobillos)
        if 'nose' in landmarks and 'left_ankle' in landmarks:
            height = abs(landmarks['nose']['y'] - landmarks['left_ankle']['y'])
            metrics['estimated_height'] = height
        
        # Ancho de hombros
        if 'left_shoulder' in landmarks and 'right_shoulder' in landmarks:
            shoulder_width = abs(landmarks['left_shoulder']['x'] - landmarks['right_shoulder']['x'])
            metrics['shoulder_width'] = shoulder_width
        
        # Proporciones
        if 'estimated_height' in metrics and 'shoulder_width' in metrics:
            metrics['height_to_shoulder_ratio'] = metrics['estimated_height'] / metrics['shoulder_width']
        
        return metrics