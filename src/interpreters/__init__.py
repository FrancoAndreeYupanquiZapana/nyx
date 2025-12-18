"""
Interpretadores de gestos para NYX
"""
from .hand_interpreter import HandInterpreter
from .arm_interpreter import ArmInterpreter
from .voice_interpreter import VoiceInterpreter  

__all__ = ['HandInterpreter', 'ArmInterpreter', 'VoiceInterpreter']  # ✅ AÑADIR