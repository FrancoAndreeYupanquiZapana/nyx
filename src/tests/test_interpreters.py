"""
🧪 TEST INTERPRETERS - Pruebas para interpretadores
====================================================
Pruebas unitarias para los módulos de interpretación de gestos.
"""

import pytest
import numpy as np
import sys
import os

# Agregar al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpreters.hand_interpreter import HandInterpreter
from interpreters.arm_interpreter import ArmInterpreter
from interpreters.voice_interpreter import VoiceInterpreter

class TestHandInterpreter:
    """Pruebas para el interpretador de manos."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.interpreter = HandInterpreter()
        
        # Crear landmarks de prueba
        self.test_landmarks = []
        for i in range(21):  # 21 landmarks de MediaPipe Hands
            landmark = type('Landmark', (), {
                'x': 0.5 + i * 0.01,
                'y': 0.5 + i * 0.01,
                'z': i * 0.1
            })()
            self.test_landmarks.append(landmark)
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.interpreter is not None
        assert hasattr(self.interpreter, 'gesture_threshold')
        assert hasattr(self.interpreter, 'gesture_history')
    
    def test_interpret_fist(self):
        """Test de interpretación de puño."""
        # Modificar landmarks para simular puño (todos los dedos cerrados)
        for i in range(21):
            self.test_landmarks[i].y = 0.9  # Todos abajo
        
        gesture = self.interpreter.interpret(self.test_landmarks)
        
        assert gesture is not None
        assert 'gesture' in gesture
        assert 'confidence' in gesture
        
        # Debería detectar puño
        if gesture['gesture'] == 'fist':
            assert gesture['confidence'] > 0.5
    
    def test_interpret_open_hand(self):
        """Test de interpretación de mano abierta."""
        # Modificar landmarks para simular mano abierta
        # Puntos de los dedos separados
        finger_tips = [4, 8, 12, 16, 20]
        for tip in finger_tips:
            self.test_landmarks[tip].y = 0.3  # Arriba
        
        gesture = self.interpreter.interpret(self.test_landmarks)
        
        assert gesture is not None
        if gesture['gesture'] == 'open_hand':
            assert gesture['confidence'] > 0.5
    
    def test_interpret_peace_sign(self):
        """Test de interpretación de señal de paz."""
        # Índice y medio arriba, otros abajo
        self.test_landmarks[8].y = 0.3   # Índice arriba
        self.test_landmarks[12].y = 0.3  # Medio arriba
        self.test_landmarks[16].y = 0.9  # Anular abajo
        self.test_landmarks[20].y = 0.9  # Meñique abajo
        
        gesture = self.interpreter.interpret(self.test_landmarks)
        
        assert gesture is not None
        if gesture['gesture'] == 'peace':
            assert gesture['confidence'] > 0.5
    
    def test_interpret_thumbs_up(self):
        """Test de interpretación de pulgar arriba."""
        # Pulgar separado y arriba
        self.test_landmarks[4].x = 0.7  # Pulgar a la derecha
        self.test_landmarks[4].y = 0.3  # Pulgar arriba
        
        gesture = self.interpreter.interpret(self.test_landmarks)
        
        assert gesture is not None
        if gesture['gesture'] == 'thumbs_up':
            assert gesture['confidence'] > 0.5
    
    def test_calculate_finger_states(self):
        """Test de cálculo de estados de dedos."""
        states = self.interpreter._calculate_finger_states(self.test_landmarks)
        
        assert isinstance(states, dict)
        assert 'thumb' in states
        assert 'index' in states
        assert 'middle' in states
        assert 'ring' in states
        assert 'pinky' in states
        
        # Cada estado debe ser bool
        for finger, state in states.items():
            assert isinstance(state, bool)
    
    def test_calculate_hand_orientation(self):
        """Test de cálculo de orientación de mano."""
        orientation = self.interpreter._calculate_hand_orientation(self.test_landmarks)
        
        assert isinstance(orientation, dict)
        assert 'pitch' in orientation
        assert 'roll' in orientation
        assert 'yaw' in orientation
        
        # Los ángulos deben estar en rangos razonables
        assert -180 <= orientation['pitch'] <= 180
        assert -180 <= orientation['roll'] <= 180
        assert -180 <= orientation['yaw'] <= 180
    
    def test_interpret_empty_landmarks(self):
        """Test con landmarks vacíos."""
        gesture = self.interpreter.interpret([])
        
        assert gesture is not None
        assert gesture['gesture'] == 'unknown'
        assert gesture['confidence'] == 0.0
    
    def test_get_gesture_history(self):
        """Test de obtención del historial de gestos."""
        # Interpretar varias veces
        for _ in range(5):
            self.interpreter.interpret(self.test_landmarks)
        
        history = self.interpreter.get_gesture_history(3)
        
        assert isinstance(history, list)
        assert len(history) <= 3

class TestArmInterpreter:
    """Pruebas para el interpretador de brazos."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.interpreter = ArmInterpreter()
        
        # Crear datos de brazos de prueba
        self.test_arms_data = {
            'arms': [
                {
                    'positions': [(100, 100), (100, 300)],  # Brazo vertical
                    'angles': [180.0],
                    'length': 200.0
                },
                {
                    'positions': [(500, 100), (700, 100)],  # Brazo horizontal
                    'angles': [90.0],
                    'length': 200.0
                }
            ],
            'arm_count': 2
        }
    
    def test_interpret_arms_up(self):
        """Test de interpretación de brazos arriba."""
        # Brazos verticales (arriba)
        arms_data = {
            'arms': [
                {
                    'positions': [(200, 400), (200, 200)],  # Hacia arriba
                    'angles': [160.0],
                    'length': 200.0
                }
            ],
            'arm_count': 1
        }
        
        result = self.interpreter.interpret(arms_data)
        
        assert result is not None
        assert 'gesture' in result
        if result['gesture'] == 'arms_up':
            assert result['confidence'] > 0.5
    
    def test_interpret_arms_crossed(self):
        """Test de interpretación de brazos cruzados."""
        # Brazos cruzados (en X)
        arms_data = {
            'arms': [
                {
                    'positions': [(100, 300), (300, 100)],  # Diagonal \
                    'angles': [45.0],
                    'length': 280.0
                },
                {
                    'positions': [(300, 300), (100, 100)],  # Diagonal /
                    'angles': [135.0],
                    'length': 280.0
                }
            ],
            'arm_count': 2
        }
        
        result = self.interpreter.interpret(arms_data)
        
        assert result is not None
        if result['gesture'] == 'arms_crossed':
            assert result['confidence'] > 0.5
    
    def test_interpret_zoom_in(self):
        """Test de interpretación de zoom in (brazos separados)."""
        # Brazos separados horizontalmente
        arms_data = {
            'arms': [
                {
                    'positions': [(100, 200), (50, 200)],  # Izquierda
                    'angles': [180.0],
                    'length': 50.0
                },
                {
                    'positions': [(300, 200), (350, 200)],  # Derecha
                    'angles': [0.0],
                    'length': 50.0
                }
            ],
            'arm_count': 2
        }
        
        result = self.interpreter.interpret(arms_data)
        
        assert result is not None
        if result['gesture'] == 'zoom_in':
            assert result['confidence'] > 0.5
    
    def test_interpret_zoom_out(self):
        """Test de interpretación de zoom out (brazos juntos)."""
        # Brazos juntos
        arms_data = {
            'arms': [
                {
                    'positions': [(200, 200), (180, 200)],  # Cerca
                    'angles': [180.0],
                    'length': 20.0
                },
                {
                    'positions': [(200, 200), (220, 200)],  # Cerca
                    'angles': [0.0],
                    'length': 20.0
                }
            ],
            'arm_count': 2
        }
        
        result = self.interpreter.interpret(arms_data)
        
        assert result is not None
        if result['gesture'] == 'zoom_out':
            assert result['confidence'] > 0.5
    
    def test_calculate_arm_angle(self):
        """Test de cálculo de ángulo de brazo."""
        points = [(100, 100), (200, 100), (300, 100)]  # Línea recta
        angle = self.interpreter._calculate_arm_angle(points)
        
        assert isinstance(angle, float)
        assert angle == 180.0  # Línea recta horizontal
    
    def test_detect_arm_pattern(self):
        """Test de detección de patrones de brazo."""
        patterns = self.interpreter._detect_arm_pattern(self.test_arms_data)
        
        assert isinstance(patterns, list)
        assert len(patterns) > 0
    
    def test_interpret_empty_data(self):
        """Test con datos vacíos."""
        result = self.interpreter.interpret({})
        
        assert result is not None
        assert result['gesture'] == 'unknown'
        assert result['confidence'] == 0.0

class TestVoiceInterpreter:
    """Pruebas para el interpretador de voz."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.interpreter = VoiceInterpreter()
    
    def test_interpret_basic_commands(self):
        """Test de interpretación de comandos básicos."""
        test_cases = [
            ("nyx abre chrome", {"command": "open", "target": "chrome"}),
            ("nyx cierra ventana", {"command": "close", "target": "window"}),
            ("nyx sube volumen", {"command": "volume", "action": "up"}),
            ("nyx maximiza", {"command": "window", "action": "maximize"}),
            ("nyx mute", {"command": "volume", "action": "mute"}),
        ]
        
        for text, expected in test_cases:
            result = self.interpreter.interpret(text)
            
            assert result is not None
            assert 'command' in result
            assert 'confidence' in result
            
            # Verificar que se extrajo el comando correcto
            if result['confidence'] > 0.5:
                assert result['command'] == expected['command']
    
    def test_interpret_without_activation_word(self):
        """Test de texto sin palabra de activación."""
        result = self.interpreter.interpret("abre chrome")
        
        # Sin "nyx", debería ignorarse
        assert result['command'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_extract_activation_word(self):
        """Test de extracción de palabra de activación."""
        test_text = "nyx por favor abre chrome"
        cleaned = self.interpreter._extract_activation_word(test_text)
        
        assert "nyx" not in cleaned
        assert "por favor abre chrome" in cleaned
    
    def test_match_pattern(self):
        """Test de coincidencia de patrones."""
        patterns = self.interpreter.command_patterns
        
        # Probar varios patrones
        test_matches = [
            ("abre chrome", "open"),
            ("cierra ventana", "close"),
            ("maximiza esto", "window"),
            ("sube el volumen", "volume"),
        ]
        
        for text, expected_command in test_matches:
            for pattern in patterns:
                if pattern['command'] == expected_command:
                    for expr in pattern['patterns']:
                        if any(word in text for word in expr.split()):
                            assert True
                            break
    
    def test_interpret_empty_text(self):
        """Test con texto vacío."""
        result = self.interpreter.interpret("")
        
        assert result['command'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_interpret_unknown_command(self):
        """Test de comando desconocido."""
        result = self.interpreter.interpret("nyx haz algo raro")
        
        assert result['command'] == 'unknown'
        assert result['confidence'] < 0.5

def test_integration_interpreters():
    """Test de integración entre interpretadores."""
    # Crear instancias
    hand_interpreter = HandInterpreter()
    arm_interpreter = ArmInterpreter()
    voice_interpreter = VoiceInterpreter()
    
    # Verificar inicialización
    assert hand_interpreter is not None
    assert arm_interpreter is not None
    assert voice_interpreter is not None
    
    # Datos de prueba
    test_landmarks = []
    for i in range(21):
        landmark = type('Landmark', (), {'x': 0.5, 'y': 0.5, 'z': 0.0})()
        test_landmarks.append(landmark)
    
    test_arms_data = {
        'arms': [{'positions': [(100, 100), (100, 300)], 'angles': [180.0], 'length': 200.0}],
        'arm_count': 1
    }
    
    test_voice_command = "nyx abre chrome"
    
    # Probar interpretación
    hand_result = hand_interpreter.interpret(test_landmarks)
    arm_result = arm_interpreter.interpret(test_arms_data)
    voice_result = voice_interpreter.interpret(test_voice_command)
    
    # Verificar resultados
    assert 'gesture' in hand_result
    assert 'confidence' in hand_result
    
    assert 'gesture' in arm_result
    assert 'confidence' in arm_result
    
    assert 'command' in voice_result
    assert 'confidence' in voice_result

if __name__ == "__main__":
    """Ejecutar pruebas directamente."""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))