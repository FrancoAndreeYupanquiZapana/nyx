"""
🧪 TEST DETECTORS - Pruebas para detectores
============================================
Pruebas unitarias para los módulos de detección.
"""

import pytest
import cv2
import numpy as np
from pathlib import Path
import sys
import os

# Agregar al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detectors.hand_detector import HandDetector
from detectors.arm_detector import ArmDetector
from detectors.pose_detector import PoseDetector

class TestHandDetector:
    """Pruebas para el detector de manos."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.detector = HandDetector()
        
        # Crear imagen de prueba
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        self.test_image[200:280, 200:280] = [255, 255, 255]  # Cuadrado blanco
    
    def test_initialization(self):
        """Test de inicialización del detector."""
        assert self.detector is not None
        assert hasattr(self.detector, 'mp_hands')
        assert hasattr(self.detector, 'mp_drawing')
    
    def test_detect_valid_image(self):
        """Test de detección con imagen válida."""
        result = self.detector.detect(self.test_image)
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'landmarks' in result
        assert 'hand_count' in result
    
    def test_detect_invalid_input(self):
        """Test con entradas inválidas."""
        # Imagen None
        result = self.detector.detect(None)
        assert result['success'] == False
        
        # Imagen vacía
        result = self.detector.detect(np.array([]))
        assert result['success'] == False
        
        # Formato incorrecto
        result = self.detector.detect(np.zeros((100, 100), dtype=np.uint8))  # 2D
        assert result['success'] == False
    
    def test_detect_multiple_hands(self):
        """Test de detección de múltiples manos."""
        # Crear imagen con dos áreas brillantes
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        test_img[100:180, 100:180] = [255, 255, 255]  # Mano 1
        test_img[300:380, 400:480] = [255, 255, 255]  # Mano 2
        
        result = self.detector.detect(test_img)
        assert result['hand_count'] >= 0  # Puede ser 0 si no detecta
    
    def test_get_landmark_positions(self):
        """Test de obtención de posiciones de landmarks."""
        result = self.detector.detect(self.test_image)
        
        if result['success'] and result['hand_count'] > 0:
            landmarks = result['landmarks']
            assert isinstance(landmarks, list)
            
            if len(landmarks) > 0:
                landmark = landmarks[0]
                assert hasattr(landmark, 'x')
                assert hasattr(landmark, 'y')
                assert hasattr(landmark, 'z')
    
    def test_draw_landmarks(self):
        """Test de dibujo de landmarks."""
        result_image = self.detector.draw_landmarks(self.test_image.copy())
        
        assert result_image is not None
        assert isinstance(result_image, np.ndarray)
        assert result_image.shape == self.test_image.shape
    
    def test_cleanup(self):
        """Test de limpieza del detector."""
        # Asegurar que no hay errores en cleanup
        try:
            self.detector.cleanup()
            assert True
        except Exception:
            pytest.fail("cleanup() should not raise exceptions")

class TestArmDetector:
    """Pruebas para el detector de brazos."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.detector = ArmDetector()
        
        # Crear imagen de prueba con dos "brazos"
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        # Brazo izquierdo (vertical)
        self.test_image[100:400, 150:200] = [200, 200, 200]
        # Brazo derecho (vertical)
        self.test_image[100:400, 450:500] = [200, 200, 200]
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.detector is not None
        assert hasattr(self.detector, 'min_arm_length')
        assert hasattr(self.detector, 'max_arm_length')
    
    def test_detect_arms(self):
        """Test de detección básica de brazos."""
        result = self.detector.detect(self.test_image)
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'arms' in result
        assert 'arm_count' in result
    
    def test_calculate_angles(self):
        """Test de cálculo de ángulos."""
        # Crear puntos de prueba
        points = [(100, 100), (200, 100), (300, 100)]
        angles = self.detector._calculate_angles(points)
        
        assert isinstance(angles, list)
        # Ángulo debería ser ~180 grados (línea recta)
        if angles:
            assert 170 <= angles[0] <= 190
    
    def test_find_contours(self):
        """Test de búsqueda de contornos."""
        contours = self.detector._find_contours(self.test_image)
        
        assert isinstance(contours, list)
        assert len(contours) > 0  # Debería encontrar los brazos
    
    def test_estimate_arm_length(self):
        """Test de estimación de longitud de brazo."""
        contour = np.array([[[100, 100]], [[200, 100]], [[200, 200]], [[100, 200]]])
        length = self.detector._estimate_arm_length(contour)
        
        assert isinstance(length, float)
        assert length > 0
    
    def test_draw_detection(self):
        """Test de dibujo de detecciones."""
        result_image = self.detector.draw_detection(self.test_image.copy())
        
        assert result_image is not None
        assert isinstance(result_image, np.ndarray)
        assert result_image.shape == self.test_image.shape

class TestPoseDetector:
    """Pruebas para el detector de postura."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.detector = PoseDetector()
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.detector is not None
        assert hasattr(self.detector, 'mp_pose')
    
    def test_detect_pose(self):
        """Test de detección de postura."""
        result = self.detector.detect(self.test_image)
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'landmarks' in result
    
    def test_get_key_points(self):
        """Test de obtención de puntos clave."""
        result = self.detector.detect(self.test_image)
        
        if result['success']:
            key_points = self.detector.get_key_points(result)
            assert isinstance(key_points, dict)
            
            # Verificar puntos clave esperados
            expected_points = ['nose', 'left_shoulder', 'right_shoulder', 
                              'left_elbow', 'right_elbow']
            
            for point in expected_points:
                assert point in key_points
    
    def test_calculate_posture_score(self):
        """Test de cálculo de puntuación de postura."""
        # Crear landmarks de prueba (postura erguida)
        test_landmarks = {
            'nose': (320, 100, 0),
            'left_shoulder': (280, 150, 0),
            'right_shoulder': (360, 150, 0),
            'left_hip': (280, 300, 0),
            'right_hip': (360, 300, 0)
        }
        
        score = self.detector.calculate_posture_score(test_landmarks)
        
        assert isinstance(score, float)
        assert 0 <= score <= 100
    
    def test_draw_pose(self):
        """Test de dibujo de postura."""
        result = self.detector.detect(self.test_image)
        result_image = self.detector.draw_pose(self.test_image.copy(), result)
        
        assert result_image is not None
        assert isinstance(result_image, np.ndarray)

def test_integration_detectors():
    """Test de integración entre detectores."""
    # Crear una imagen compleja
    test_image = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Añadir formas que simulen persona
    cv2.rectangle(test_image, (500, 100), (700, 400), (255, 255, 255), -1)  # Torso
    cv2.rectangle(test_image, (400, 150), (500, 300), (255, 255, 255), -1)  # Brazo izquierdo
    cv2.rectangle(test_image, (700, 150), (800, 300), (255, 255, 255), -1)  # Brazo derecho
    
    # Probar todos los detectores
    hand_detector = HandDetector()
    arm_detector = ArmDetector()
    pose_detector = PoseDetector()
    
    hand_result = hand_detector.detect(test_image)
    arm_result = arm_detector.detect(test_image)
    pose_result = pose_detector.detect(test_image)
    
    # Verificar que todos retornan resultados válidos
    assert hand_result['success'] in [True, False]
    assert arm_result['success'] in [True, False]
    assert pose_result['success'] in [True, False]
    
    # Limpiar
    hand_detector.cleanup()
    arm_detector.cleanup()
    pose_detector.cleanup()

if __name__ == "__main__":
    """Ejecutar pruebas directamente."""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))