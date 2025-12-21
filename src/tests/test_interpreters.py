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
        
        # Crear landmarks de prueba (en formato HandDetector: lista de dicts)
        self.test_landmarks = []
        for i in range(21):
            self.test_landmarks.append({
                'id': i,
                'x': 0.5,
                'y': 0.5,
                'z': 0.0,
                'visibility': 1.0
            })
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.interpreter is not None
        assert hasattr(self.interpreter, 'gesture_threshold')
        assert hasattr(self.interpreter, 'gesture_history')
    
    def test_interpret_fist(self):
        """Test de interpretación de puño."""
        # Preparar datos estructurados
        hand_data = [{
            'hand_info': {
                'landmarks': self.test_landmarks,
                'handedness': 'right',
                'confidence': 0.9,
                'frame_width': 640,
                'frame_height': 480
            },
            'gestures': [
                {'gesture': 'fist', 'confidence': 0.9, 'hand': 'right'}
            ]
        }]
        
        # Estabilizar (necesita al menos 2 frames)
        self.interpreter.interpret(hand_data)
        gestures = self.interpreter.interpret(hand_data)
        
        assert len(gestures) > 0
        assert gestures[0]['gesture'] == 'fist'
        assert gestures[0]['hand'] == 'right'
    
    def test_interpret_point(self):
        """Test de interpretación de señalar con cursor."""
        # Landmark 8 es la punta del índice
        self.test_landmarks[8]['x'] = 100
        self.test_landmarks[8]['y'] = 200
        
        hand_data = [{
            'hand_info': {
                'landmarks': self.test_landmarks,
                'handedness': 'right',
                'confidence': 0.8,
                'frame_width': 640,
                'frame_height': 480
            },
            'gestures': [
                {'gesture': 'point', 'confidence': 0.8, 'hand': 'right'}
            ]
        }]
        
        # Estabilizar
        self.interpreter.interpret(hand_data)
        gestures = self.interpreter.interpret(hand_data)
        
        assert len(gestures) > 0
        assert gestures[0]['gesture'] == 'point'
        assert gestures[0]['cursor'] is not None
        # Verificar normalización (100/640, 200/480)
        assert abs(gestures[0]['cursor']['x'] - 100/640) < 0.01
        assert abs(gestures[0]['cursor']['y'] - 200/480) < 0.01

    def test_interpret_empty_landmarks(self):
        """Test con datos vacíos."""
        gestures = self.interpreter.interpret([])
        assert isinstance(gestures, list)
        assert len(gestures) == 0

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
            ("nyx abre chrome", {"command": "open_app", "action": "bash"}),
            ("nyx cierra ventana", {"command": "close", "action": "window"}),
            ("nyx sube volumen", {"command": "adjust_volume", "action": "bash"}),
            ("nyx maximiza", {"command": "window", "action": "maximize"}),
            ("nyx mute", {"command": "adjust_volume", "action": "bash"}),
        ]
        
        for text, expected in test_cases:
            result = self.interpreter.interpret({'text': text})
            
            assert result is not None
            assert 'command' in result
            assert 'confidence' in result
            
            # Verificar que se extrajo el comando correcto
            if result['confidence'] > 0.5:
                assert result['command'] == expected['command']
    
    def test_interpret_without_activation_word(self):
        """Test de texto sin palabra de activación."""
        result = self.interpreter.interpret({'text': "abre chrome"})
        
        # Sin "nyx", debería ignorarse
        assert result['command'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_interpret_empty_text(self):
        """Test con texto vacío."""
        result = self.interpreter.interpret({'text': ""})
        
        assert result['command'] == 'unknown'
        assert result['confidence'] == 0.0
    
    def test_interpret_unknown_command(self):
        """Test de comando desconocido."""
        result = self.interpreter.interpret({'text': "nyx haz algo raro"})
        
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
    
    # Datos de prueba para manos (Formato NYX)
    test_landmarks = [{'id': i, 'x': 0.5, 'y': 0.5, 'z': 0.0} for i in range(21)]
    hands_data = [{
        'hand_info': {
            'landmarks': test_landmarks,
            'handedness': 'right',
            'confidence': 0.9,
            'frame_width': 640,
            'frame_height': 480
        },
        'gestures': [
            {'gesture': 'fist', 'confidence': 0.9, 'hand': 'right'}
        ]
    }]
    
    test_arms_data = {
        'arms': [{'positions': [(100, 100), (100, 300)], 'angles': [180.0], 'length': 200.0}],
        'arm_count': 1
    }
    
    test_voice_command = "nyx abre chrome"
    
    # Probar interpretación
    # Llamar dos veces para estabilización
    hand_interpreter.interpret(hands_data)
    hand_results = hand_interpreter.interpret(hands_data)
    
    arm_result = arm_interpreter.interpret(test_arms_data)
    voice_result = voice_interpreter.interpret({'text': test_voice_command})
    
    # Verificar resultados
    assert len(hand_results) > 0
    assert 'gesture' in hand_results[0]
    
    assert 'gesture' in arm_result
    assert 'confidence' in arm_result
    
    assert 'command' in voice_result
    assert 'confidence' in voice_result

if __name__ == "__main__":
    """Ejecutar pruebas directamente."""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))