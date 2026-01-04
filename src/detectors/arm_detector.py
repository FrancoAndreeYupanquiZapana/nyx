"""
💪 ARM DETECTOR - Detección de Brazos con MediaPipe Pose
=======================================================
Detecta y rastrea brazos para gestos a distancia.
Ideal para gestos amplios como "brazos en X", "manos arriba", etc.
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import math
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class ArmDetector:
    """Detector de gestos de brazos usando MediaPipe Pose."""
    
    def __init__(self, 
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5,
                 model_complexity: int = 1):
        """
        Inicializa el detector de brazos.
        
        Args:
            min_detection_confidence: Confianza mínima para detección
            min_tracking_confidence: Confianza mínima para tracking
            model_complexity: Complejidad del modelo (0: Lite, 1: Full, 2: Heavy)
        """
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Inicializar MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Configurar el modelo de pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            smooth_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # Landmarks de interés para brazos
        self.LANDMARK_IDS = {
            'left_shoulder': self.mp_pose.PoseLandmark.LEFT_SHOULDER,
            'right_shoulder': self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
            'left_elbow': self.mp_pose.PoseLandmark.LEFT_ELBOW,
            'right_elbow': self.mp_pose.PoseLandmark.RIGHT_ELBOW,
            'left_wrist': self.mp_pose.PoseLandmark.LEFT_WRIST,
            'right_wrist': self.mp_pose.PoseLandmark.RIGHT_WRIST,
            'left_hip': self.mp_pose.PoseLandmark.LEFT_HIP,
            'right_hip': self.mp_pose.PoseLandmark.RIGHT_HIP,
            'left_ear': self.mp_pose.PoseLandmark.LEFT_EAR,
            'right_ear': self.mp_pose.PoseLandmark.RIGHT_EAR
        }
        
        # Gestos reconocidos de brazos
        self.GESTURES = {
            'arms_crossed': self._is_arms_crossed,
            'arms_up': self._is_arms_up,
            'arms_down': self._is_arms_down,
            'arms_out': self._is_arms_out,
            'arms_together': self._is_arms_together,
            'left_arm_up': self._is_left_arm_up,
            'right_arm_up': self._is_right_arm_up,
            'left_arm_out': self._is_left_arm_out,
            'right_arm_out': self._is_right_arm_out,
            'wave_left': self._is_wave_left,
            'wave_right': self._is_wave_right,
            'zoom_in': self._is_zoom_in,
            'zoom_out': self._is_zoom_out,
            't_pose': self._is_t_pose,
            'x_pose': self._is_x_pose
        }
        
        # Colores para diferentes partes del cuerpo
        self.COLORS = {
            'left_arm': (0, 165, 255),   # Naranja
            'right_arm': (0, 255, 0),    # Verde
            'shoulders': (255, 0, 0),    # Rojo
            'gesture': (255, 255, 0)     # Amarillo
        }
        
        # Umbrales para detección de gestos (ajustables)
        self.THRESHOLDS = {
            'arm_up_y': 0.2,      # Mano debe estar esta fracción arriba del hombro
            'arm_cross_x': 0.1,   # Traslape para brazos cruzados
            'arm_out_x': 0.5,     # Separación para brazos abiertos
            'arm_together_x': 0.2,# Proximidad para brazos juntos
            'wave_angle': 30,     # Ángulo mínimo para saludar (grados)
            'zoom_threshold': 0.3 # Umbral para zoom in/out
        }
        
        # Estadísticas
        self.stats = {
            'frames_processed': 0,
            'poses_detected': 0,
            'gestures_detected': 0,
            'fps': 0
        }
        
        # Historial para estabilizar gestos
        self.gesture_history = []
        self.history_size = 5
        
        # Para cálculo de FPS
        self.frame_count = 0
        self.start_time = time.time()
        
        # Estado de gestos previos
        self.last_gestures = {}
        self.gesture_cooldown = {}  # Para evitar detecciones repetitivas
        
        logger.info(f"✅ ArmDetector inicializado (confidence={min_detection_confidence})")
    
    def detect(self, image: np.ndarray) -> Dict:
        """
        Detecta pose y gestos de brazos en la imagen.
        
        Args:
            image: Imagen BGR (OpenCV format)
            
        Returns:
            Diccionario con resultados:
            {
                'image': imagen procesada con landmarks dibujados,
                'landmarks': diccionario con landmarks normalizados,
                'gestures': lista de gestos detectados,
                'angles': ángulos de articulaciones,
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
        
        # Procesar imagen con MediaPipe Pose
        results = self.pose.process(image_rgb)
        
        # Convertir de nuevo a BGR para dibujar
        image_rgb.flags.writeable = True
        processed_image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        landmarks_data = {}
        gestures = []
        angles = {}
        
        if results.pose_landmarks:
            self.stats['poses_detected'] += 1
            
            # Extraer landmarks de interés
            landmarks_data = self._extract_landmarks(results.pose_landmarks, processed_image.shape)
            
            # Calcular ángulos de articulaciones
            angles = self._calculate_arm_angles(landmarks_data)
            
            # Detectar gestos
            gestures = self._detect_arm_gestures(landmarks_data, angles)
            if gestures:
                self.stats['gestures_detected'] += len(gestures)
            
            # Dibujar landmarks y conexiones
            self._draw_landmarks(processed_image, results.pose_landmarks)
            
            # Dibujar información adicional
            if landmarks_data:
                self._draw_arm_info(processed_image, landmarks_data, angles, gestures)
        
        # Dibujar información del sistema
        processed_image = self._draw_system_info(processed_image)
        
        return {
            'image': processed_image,
            'landmarks': landmarks_data,
            'gestures': gestures,
            'angles': angles,
            'stats': self.stats.copy(),
            'raw_results': results,
            'success': True
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
                'id': landmark_id.value
            }
        
        return landmarks_data
    
    def _calculate_arm_angles(self, landmarks: Dict) -> Dict:
        """
        Calcula ángulos importantes de los brazos.
        
        Args:
            landmarks: Diccionario con landmarks
            
        Returns:
            Diccionario con ángulos en grados
        """
        angles = {}
        
        # Función para calcular ángulo entre 3 puntos
        def calculate_angle(a, b, c):
            """Calcula el ángulo ABC en grados."""
            try:
                # Convertir a arrays numpy
                a = np.array([a['x'], a['y']])
                b = np.array([b['x'], b['y']])
                c = np.array([c['x'], c['y']])
                
                # Vectores BA y BC
                ba = a - b
                bc = c - b
                
                # Producto punto
                dot_product = np.dot(ba, bc)
                
                # Magnitudes
                norm_ba = np.linalg.norm(ba)
                norm_bc = np.linalg.norm(bc)
                
                # Ángulo en radianes
                cosine_angle = dot_product / (norm_ba * norm_bc)
                cosine_angle = max(-1.0, min(1.0, cosine_angle))  # Clamp
                angle_rad = math.acos(cosine_angle)
                
                # Convertir a grados
                angle_deg = math.degrees(angle_rad)
                
                return angle_deg
            except:
                return 0.0
        
        # Verificar que tengamos los landmarks necesarios
        required = ['left_shoulder', 'left_elbow', 'left_wrist', 
                   'right_shoulder', 'right_elbow', 'right_wrist']
        
        if not all(req in landmarks for req in required):
            return angles
        
        # Ángulo del codo izquierdo (hombro-codo-muñeca)
        angles['left_elbow'] = calculate_angle(
            landmarks['left_shoulder'],
            landmarks['left_elbow'],
            landmarks['left_wrist']
        )
        
        # Ángulo del codo derecho
        angles['right_elbow'] = calculate_angle(
            landmarks['right_shoulder'],
            landmarks['right_elbow'],
            landmarks['right_wrist']
        )
        
        # Ángulo del hombro izquierdo (cadera-hombro-codo)
        if 'left_hip' in landmarks:
            angles['left_shoulder'] = calculate_angle(
                landmarks['left_hip'],
                landmarks['left_shoulder'],
                landmarks['left_elbow']
            )
        
        # Ángulo del hombro derecho
        if 'right_hip' in landmarks:
            angles['right_shoulder'] = calculate_angle(
                landmarks['right_hip'],
                landmarks['right_shoulder'],
                landmarks['right_elbow']
            )
        
        # Ángulo entre los dos hombros (para postura)
        angles['shoulders_angle'] = calculate_angle(
            {'x': landmarks['left_shoulder']['x'], 'y': 0},  # Punto horizontal
            {'x': landmarks['left_shoulder']['x'], 'y': landmarks['left_shoulder']['y']},
            {'x': landmarks['right_shoulder']['x'], 'y': landmarks['right_shoulder']['y']}
        )
        
        return angles
    
    def _detect_arm_gestures(self, landmarks: Dict, angles: Dict) -> List[Dict]:
        """
        Detecta gestos de brazos basados en landmarks y ángulos.
        
        Args:
            landmarks: Diccionario con landmarks
            angles: Diccionario con ángulos
            
        Returns:
            Lista de gestos detectados
        """
        gestures = []
        
        # Verificar que tengamos landmarks mínimos
        required_landmarks = ['left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder']
        if not all(req in landmarks for req in required_landmarks):
            return gestures
        
        current_time = time.time()
        
        for gesture_name, detector_func in self.GESTURES.items():
            try:
                if detector_func(landmarks, angles):
                    # Verificar cooldown para evitar detecciones repetitivas
                    last_time = self.gesture_cooldown.get(gesture_name, 0)
                    if current_time - last_time < 0.5:  # 500ms de cooldown
                        continue
                    
                    # Calcular confianza basada en visibilidad de landmarks
                    confidence = self._calculate_gesture_confidence(landmarks, gesture_name)
                    
                    gesture = {
                        'type': 'arm',
                        'gesture': gesture_name,
                        'confidence': confidence,
                        'timestamp': current_time
                    }
                    
                    # Verificar si es un gesto estable
                    if self._is_stable_gesture(gesture):
                        gestures.append(gesture)
                        self.gesture_cooldown[gesture_name] = current_time
                        
            except Exception as e:
                logger.debug(f"⚠️ Error detectando gesto {gesture_name}: {e}")
                continue
        
        return gestures
    
    def _is_arms_crossed(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazos cruzados (X)."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        
        # Muñeca izquierda está a la derecha del hombro derecho
        # Muñeca derecha está a la izquierda del hombro izquierdo
        # Y aproximadamente a la misma altura
        return (lw['x'] > rs['x'] + self.THRESHOLDS['arm_cross_x'] and
                rw['x'] < ls['x'] - self.THRESHOLDS['arm_cross_x'] and
                abs(lw['y'] - rw['y']) < 0.15)
    
    def _is_arms_up(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta ambos brazos arriba."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        
        # Ambas muñecas están significativamente arriba de los hombros
        return (lw['y'] < ls['y'] - self.THRESHOLDS['arm_up_y'] and
                rw['y'] < rs['y'] - self.THRESHOLDS['arm_up_y'])
    
    def _is_arms_down(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta ambos brazos abajo (a los lados)."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        lh = landmarks.get('left_hip', {'y': 0.8})  # Valor por defecto
        rh = landmarks.get('right_hip', {'y': 0.8})
        
        # Ambas muñecas están cerca de las caderas
        return (abs(lw['y'] - lh['y']) < 0.1 and
                abs(rw['y'] - rh['y']) < 0.1 and
                lw['x'] < ls['x'] and  # Izquierda a la izquierda
                rw['x'] > rs['x'])     # Derecha a la derecha
    
    def _is_arms_out(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazos extendidos a los lados (T-pose parcial)."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        
        # Brazos extendidos horizontalmente
        return (lw['x'] < ls['x'] - self.THRESHOLDS['arm_out_x'] and
                rw['x'] > rs['x'] + self.THRESHOLDS['arm_out_x'] and
                abs(lw['y'] - ls['y']) < 0.15 and
                abs(rw['y'] - rs['y']) < 0.15)
    
    def _is_arms_together(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazos juntos frente al cuerpo."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        
        # Muñecas cercanas horizontal y verticalmente
        return (abs(lw['x'] - rw['x']) < self.THRESHOLDS['arm_together_x'] and
                abs(lw['y'] - rw['y']) < 0.15)
    
    def _is_left_arm_up(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazo izquierdo arriba."""
        lw = landmarks['left_wrist']
        ls = landmarks['left_shoulder']
        rw = landmarks['right_wrist']
        rs = landmarks['right_shoulder']
        
        # Brazo izquierdo arriba, derecho no
        return (lw['y'] < ls['y'] - self.THRESHOLDS['arm_up_y'] and
                rw['y'] > rs['y'])
    
    def _is_right_arm_up(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazo derecho arriba."""
        lw = landmarks['left_wrist']
        ls = landmarks['left_shoulder']
        rw = landmarks['right_wrist']
        rs = landmarks['right_shoulder']
        
        # Brazo derecho arriba, izquierdo no
        return (rw['y'] < rs['y'] - self.THRESHOLDS['arm_up_y'] and
                lw['y'] > ls['y'])
    
    def _is_left_arm_out(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazo izquierdo extendido a un lado."""
        lw = landmarks['left_wrist']
        ls = landmarks['left_shoulder']
        
        return (lw['x'] < ls['x'] - self.THRESHOLDS['arm_out_x']/2 and
                abs(lw['y'] - ls['y']) < 0.15)
    
    def _is_right_arm_out(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta brazo derecho extendido a un lado."""
        rw = landmarks['right_wrist']
        rs = landmarks['right_shoulder']
        
        return (rw['x'] > rs['x'] + self.THRESHOLDS['arm_out_x']/2 and
                abs(rw['y'] - rs['y']) < 0.15)
    
    def _is_wave_left(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta saludo con mano izquierda."""
        if 'left_elbow' not in angles:
            return False
        
        # Ángulo del codo indica movimiento de saludo
        return (90 < angles['left_elbow'] < 150 and
                landmarks['left_wrist']['y'] < landmarks['left_shoulder']['y'])
    
    def _is_wave_right(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta saludo con mano derecha."""
        if 'right_elbow' not in angles:
            return False
        
        return (90 < angles['right_elbow'] < 150 and
                landmarks['right_wrist']['y'] < landmarks['right_shoulder']['y'])
    
    def _is_zoom_in(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta gesto de zoom in (manos juntas moviéndose hacia el cuerpo)."""
        # Para zoom in necesitamos comparar con frame anterior
        # Por ahora, detectamos solo manos juntas
        return self._is_arms_together(landmarks, angles)
    
    def _is_zoom_out(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta gesto de zoom out (manos separándose)."""
        return self._is_arms_out(landmarks, angles)
    
    def _is_t_pose(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta postura en T (brazos completamente extendidos a los lados)."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        
        # Brazos completamente horizontales
        return (abs(lw['y'] - ls['y']) < 0.1 and
                abs(rw['y'] - rs['y']) < 0.1 and
                lw['x'] < ls['x'] - 0.3 and  # Más extendido que arms_out
                rw['x'] > rs['x'] + 0.3)
    
    def _is_x_pose(self, landmarks: Dict, angles: Dict) -> bool:
        """Detecta postura en X (brazos en diagonal)."""
        lw = landmarks['left_wrist']
        rw = landmarks['right_wrist']
        ls = landmarks['left_shoulder']
        rs = landmarks['right_shoulder']
        
        # Brazos en diagonal opuesta
        return (lw['x'] > rs['x'] and lw['y'] < ls['y'] and
                rw['x'] < ls['x'] and rw['y'] < rs['y'])
    
    def _calculate_gesture_confidence(self, landmarks: Dict, gesture_name: str) -> float:
        """
        Calcula confianza para un gesto basado en visibilidad de landmarks.
        
        Args:
            landmarks: Diccionario con landmarks
            gesture_name: Nombre del gesto
            
        Returns:
            Confianza entre 0 y 1
        """
        # Ponderar según importancia de landmarks para este gesto
        if gesture_name in ['arms_crossed', 'x_pose']:
            key_landmarks = ['left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder']
        elif 'left' in gesture_name:
            key_landmarks = ['left_wrist', 'left_elbow', 'left_shoulder']
        elif 'right' in gesture_name:
            key_landmarks = ['right_wrist', 'right_elbow', 'right_shoulder']
        else:
            key_landmarks = ['left_wrist', 'right_wrist', 'left_shoulder', 'right_shoulder']
        
        # Calcular visibilidad promedio
        visibilities = []
        for landmark_name in key_landmarks:
            if landmark_name in landmarks:
                visibilities.append(landmarks[landmark_name]['visibility'])
        
        if not visibilities:
            return 0.5  # Confianza por defecto
        
        avg_visibility = sum(visibilities) / len(visibilities)
        
        # Ajustar confianza basada en visibilidad
        if avg_visibility > 0.8:
            return 0.9
        elif avg_visibility > 0.6:
            return 0.7
        elif avg_visibility > 0.4:
            return 0.5
        else:
            return 0.3
    
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
            if g.get('gesture') == gesture['gesture']:
                same_gesture_count += 1
        
        # Requerir al menos 2 de 3 frames con el mismo gesto
        return same_gesture_count >= 2
    
    def _draw_landmarks(self, image, landmarks):
        """Dibuja landmarks y conexiones de pose."""
        # Dibujar conexiones
        self.mp_drawing.draw_landmarks(
            image,
            landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(
                color=self.COLORS['shoulders'], thickness=2, circle_radius=2
            ),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(
                color=self.COLORS['left_arm'], thickness=2
            )
        )
    
    def _draw_arm_info(self, image, landmarks, angles, gestures):
        """Dibuja información adicional de los brazos."""
        # Dibujar círculos en puntos importantes
        for name, landmark in landmarks.items():
            if 'wrist' in name or 'elbow' in name or 'shoulder' in name:
                color = self.COLORS['left_arm'] if 'left' in name else self.COLORS['right_arm']
                cv2.circle(image, 
                          (landmark['x_px'], landmark['y_px']), 
                          6, color, -1)
                
                # Etiqueta
                cv2.putText(image, name.replace('_', ' '),
                           (landmark['x_px'] + 10, landmark['y_px']),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Dibujar líneas entre articulaciones
        connections = [
            ('left_shoulder', 'left_elbow'),
            ('left_elbow', 'left_wrist'),
            ('right_shoulder', 'right_elbow'),
            ('right_elbow', 'right_wrist')
        ]
        
        for start, end in connections:
            if start in landmarks and end in landmarks:
                color = self.COLORS['left_arm'] if 'left' in start else self.COLORS['right_arm']
                cv2.line(image,
                        (landmarks[start]['x_px'], landmarks[start]['y_px']),
                        (landmarks[end]['x_px'], landmarks[end]['y_px']),
                        color, 2)
        
        # Mostrar ángulos
        for angle_name, angle_value in angles.items():
            if 'elbow' in angle_name or 'shoulder' in angle_name:
                # Encontrar posición para mostrar el ángulo
                if 'left' in angle_name and 'left_elbow' in landmarks:
                    pos = (landmarks['left_elbow']['x_px'], landmarks['left_elbow']['y_px'] - 20)
                elif 'right' in angle_name and 'right_elbow' in landmarks:
                    pos = (landmarks['right_elbow']['x_px'], landmarks['right_elbow']['y_px'] - 20)
                else:
                    continue
                
                cv2.putText(image, f"{angle_value:.0f}°",
                           pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Mostrar gestos detectados
        if gestures:
            gesture_text = ", ".join([g['gesture'].replace('_', ' ') for g in gestures[:2]])
            if len(gestures) > 2:
                gesture_text += f" (+{len(gestures)-2})"
            
            cv2.putText(image, gesture_text,
                       (20, image.shape[0] - 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLORS['gesture'], 2)
    
    def _draw_system_info(self, image):
        """Dibuja información del sistema en la imagen."""
        h, w = image.shape[:2]
        
        # Fondo semitransparente para texto
        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
        
        # Información del detector
        cv2.putText(image, f"💪 Arm Detector - FPS: {self.stats['fps']}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.putText(image, f"Poses: {self.stats['poses_detected']} | Gestos: {self.stats['gestures_detected']}", 
                   (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Mostrar gestos disponibles
        gesture_count = len(self.GESTURES)
        cv2.putText(image, f"Gestos disponibles: {gesture_count}", 
                   (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return image
    
    def get_detection_info(self) -> Dict:
        """Obtiene información de configuración del detector."""
        return {
            'min_detection_confidence': self.min_detection_confidence,
            'min_tracking_confidence': self.min_tracking_confidence,
            'gestures_available': list(self.GESTURES.keys()),
            'thresholds': self.THRESHOLDS.copy(),
            'stats': self.stats.copy()
        }
    
    def update_config(self, **kwargs):
        """Actualiza configuración del detector."""
        if 'min_detection_confidence' in kwargs:
            self.min_detection_confidence = kwargs['min_detection_confidence']
        
        if 'min_tracking_confidence' in kwargs:
            self.min_tracking_confidence = kwargs['min_tracking_confidence']
        
        # Actualizar umbrales si se proporcionan
        for threshold_name, value in kwargs.items():
            if threshold_name in self.THRESHOLDS:
                self.THRESHOLDS[threshold_name] = value
        
        # Reiniciar el modelo con nueva configuración
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        )
        
        logger.info(f"🔄 Configuración de ArmDetector actualizada: {kwargs}")
    
    def release(self):
        """Libera recursos del detector."""
        if hasattr(self, 'pose'):
            self.pose.close()
            logger.info("✅ Recursos de ArmDetector liberados")
    
    def get_arm_position(self, landmarks: Dict, side: str = 'left') -> Dict:
        """
        Obtiene información de posición de un brazo.
        
        Args:
            landmarks: Diccionario con landmarks
            side: 'left' o 'right'
            
        Returns:
            Diccionario con información de posición
        """
        if side not in ['left', 'right']:
            raise ValueError("side debe ser 'left' o 'right'")
        
        prefix = f"{side}_"
        wrist_key = f"{prefix}wrist"
        elbow_key = f"{prefix}elbow"
        shoulder_key = f"{prefix}shoulder"
        
        if not all(k in landmarks for k in [wrist_key, elbow_key, shoulder_key]):
            return {}
        
        # Calcular posición relativa
        wrist = landmarks[wrist_key]
        shoulder = landmarks[shoulder_key]
        
        position = {
            'horizontal': 'center',
            'vertical': 'center',
            'distance_from_shoulder': 0.0
        }
        
        # Horizontal
        if wrist['x'] < shoulder['x'] - 0.2:
            position['horizontal'] = 'out'
        elif wrist['x'] > shoulder['x'] + 0.2:
            position['horizontal'] = 'crossed'
        else:
            position['horizontal'] = 'front'
        
        # Vertical
        if wrist['y'] < shoulder['y'] - 0.2:
            position['vertical'] = 'up'
        elif wrist['y'] > shoulder['y'] + 0.2:
            position['vertical'] = 'down'
        else:
            position['vertical'] = 'middle'
        
        # Distancia
        dx = wrist['x'] - shoulder['x']
        dy = wrist['y'] - shoulder['y']
        position['distance_from_shoulder'] = math.sqrt(dx*dx + dy*dy)
        
        return position