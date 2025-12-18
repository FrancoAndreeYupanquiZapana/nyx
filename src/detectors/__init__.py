"""
Detectores de gestos para NYX
"""
from .hand_detector import HandDetector
from .arm_detector import ArmDetector
from .pose_detector import PoseDetector 

__all__ = ['HandDetector', 'ArmDetector', 'PoseDetector'] 