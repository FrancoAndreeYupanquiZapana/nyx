"""
Script de prueba para verificar que el DirectMouseControl funciona en NYX
"""
import sys
import time
from src.core.gesture_pipeline import GesturePipeline

print("🎮 Iniciando prueba de DirectMouseControl en NYX...")
print("=" * 60)

# Crear pipeline
config = {
    'camera': {
        'device_id': 0,
        'width': 640,
        'height': 480,
        'fps': 30,
        'mirror': True
    },
    'hand_detection': {
        'enabled': True
    }
}

pipeline = GesturePipeline(config)

# Verificar que DirectMouseControl está habilitado
if pipeline.direct_mouse_control and pipeline.direct_mouse_control.enabled:
    print("✅ DirectMouseControl está habilitado")
    print(f"   Screen size: {pipeline.direct_mouse_control.screen_w}x{pipeline.direct_mouse_control.screen_h}")
else:
    print("❌ DirectMouseControl NO está habilitado")
    sys.exit(1)

# Inicializar detectores
from src.detectors.hand_detector import HandDetector
pipeline.hand_detector = HandDetector()

print("\n🚀 Iniciando pipeline...")
pipeline.start()

print("\n📹 Pipeline corriendo - Mueve tu mano para controlar el mouse")
print("   Gesto 'point' (índice arriba, otros abajo) = MOVER")
print("   Presiona Ctrl+C para detener\n")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\n🛑 Deteniendo...")
    pipeline.stop()
    print("✅ Pipeline detenido")
