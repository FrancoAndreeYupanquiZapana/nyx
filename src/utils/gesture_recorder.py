"""
🎥 GESTURE RECORDER - Grabadora de gestos NYX
=============================================
Sistema modular para grabar gestos que se integra con la arquitectura NYX.
No tiene dependencias directas, usa inyección de dependencias.
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from collections import deque
import numpy as np
import logging

logger = logging.getLogger(__name__)

class GestureRecorder:
    """
    Grabadora de gestos modular para NYX.
    
    Características:
    - Grabación de gestos individuales y secuencias
    - Exportación en formato JSON para entrenamiento
    - Reproducción de grabaciones
    - Análisis de estabilidad y calidad
    - Integración con detectores mediante inyección
    """
    
    def __init__(self, 
                 output_dir: str = "recorded_gestures",
                 config: Optional[Dict[str, Any]] = None):
        """
        Inicializa la grabadora de gestos.
        
        Args:
            output_dir: Directorio para guardar grabaciones
            config: Configuración opcional
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuración
        self.config = config or self._default_config()
        
        # Detectores (se inyectan después)
        self.hand_detector = None
        self.arm_detector = None
        self.pose_detector = None
        
        # Estado de grabación
        self.is_recording = False
        self.recording_mode = None  # 'single', 'sequence', 'continuous', 'training'
        self.current_recording = []
        self.recording_start_time = 0
        
        # Buffer para análisis
        self.frame_buffer = deque(maxlen=self.config['buffer_size'])
        
        # Metadatos
        self.current_gesture_name = ""
        self.current_action = ""
        self.current_profile = ""
        self.notes = ""
        
        # Hilos
        self.recording_thread = None
        self.stop_flag = threading.Event()
        
        # Estadísticas
        self.stats = {
            'total_recordings': 0,
            'total_frames': 0,
            'total_duration': 0.0,
            'last_recording': None
        }
        
        # Cargar índice existente
        self._load_recording_index()
        
        logger.info(f"🎥 GestureRecorder inicializado. Salida: {self.output_dir}")
    
    def _default_config(self) -> Dict[str, Any]:
        """Configuración por defecto."""
        return {
            'min_frames_per_gesture': 15,
            'max_recording_time': 30.0,
            'buffer_size': 30,
            'min_confidence': 0.6,
            'auto_save': True,
            'compression': False,
            'default_sample_rate': 30  # FPS
        }
    
    # ========== INYECCIÓN DE DEPENDENCIAS ==========
    
    def set_hand_detector(self, detector):
        """Establece el detector de manos."""
        self.hand_detector = detector
        logger.debug("✅ Detector de manos configurado")
    
    def set_arm_detector(self, detector):
        """Establece el detector de brazos."""
        self.arm_detector = detector
        logger.debug("✅ Detector de brazos configurado")
    
    def set_pose_detector(self, detector):
        """Establece el detector de postura."""
        self.pose_detector = detector
        logger.debug("✅ Detector de postura configurado")
    
    # ========== CONTROL DE GRABACIÓN ==========
    
    def start_recording(self,
                       gesture_name: str = "",
                       mode: str = "single",
                       action: str = "",
                       profile: str = "",
                       notes: str = "") -> bool:
        """
        Inicia una nueva grabación.
        
        Args:
            gesture_name: Nombre del gesto
            mode: Modo de grabación ('single', 'sequence', 'continuous', 'training')
            action: Acción asociada
            profile: Perfil asociado
            notes: Notas adicionales
            
        Returns:
            True si se inició correctamente
        """
        if self.is_recording:
            logger.warning("⚠️ Ya hay una grabación en curso")
            return False
        
        if mode != "continuous" and not gesture_name:
            logger.error("❌ Se requiere nombre de gesto para este modo")
            return False
        
        # Configurar nueva grabación
        self.is_recording = True
        self.recording_mode = mode
        self.current_recording = []
        self.recording_start_time = time.time()
        
        self.current_gesture_name = gesture_name
        self.current_action = action
        self.current_profile = profile
        self.notes = notes
        
        # Limpiar buffer
        self.frame_buffer.clear()
        self.stop_flag.clear()
        
        logger.info(f"⏺️  Grabación iniciada: {gesture_name} ({mode})")
        return True
    
    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """
        Detiene la grabación actual.
        
        Returns:
            Datos de la grabación o None
        """
        if not self.is_recording:
            logger.warning("⚠️ No hay grabación en curso")
            return None
        
        self.is_recording = False
        self.stop_flag.set()
        
        # Esperar a que termine el hilo si existe
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        # Procesar grabación
        if not self.current_recording:
            logger.warning("📭 Grabación vacía")
            return None
        
        recording_data = self._process_recording()
        
        # Guardar automáticamente si está configurado
        if self.config.get('auto_save', True) and recording_data:
            saved_path = self._save_recording(recording_data)
            if saved_path:
                logger.info(f"💾 Grabación guardada: {saved_path.name}")
        
        logger.info(f"⏹️  Grabación finalizada: {len(self.current_recording)} frames")
        return recording_data
    
    def add_frame(self,
                  frame_data: Dict[str, Any],
                  image: Optional[np.ndarray] = None) -> bool:
        """
        Agrega un frame a la grabación actual.
        
        Args:
            frame_data: Datos del frame (landmarks, gestos, etc.)
            image: Imagen del frame (opcional, para visualización)
            
        Returns:
            True si se agregó correctamente
        """
        if not self.is_recording:
            return False
        
        try:
            # Crear entrada del frame
            timestamp = time.time() - self.recording_start_time
            
            frame_entry = {
                'timestamp': timestamp,
                'frame_data': frame_data,
                'frame_id': len(self.current_recording)
            }
            
            # Agregar miniatura de imagen si se proporciona y es pequeño
            if image is not None and image.size < 10000:  # Imagen pequeña
                # Convertir a lista para serialización JSON
                frame_entry['image_thumbnail'] = image.tolist() if image is not None else None
            
            # Agregar a la grabación
            self.current_recording.append(frame_entry)
            self.frame_buffer.append(frame_entry)
            
            # Verificar límite de tiempo
            if timestamp > self.config['max_recording_time']:
                logger.warning("⏰ Límite de tiempo de grabación alcanzado")
                self.stop_recording()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error agregando frame: {e}")
            return False
    
    # ========== PROCESAMIENTO ==========
    
    def _process_recording(self) -> Optional[Dict[str, Any]]:
        """Procesa la grabación para extraer características."""
        if not self.current_recording:
            return None
        
        try:
            total_frames = len(self.current_recording)
            duration = self.current_recording[-1]['timestamp'] if total_frames > 0 else 0
            
            # Extraer gestos detectados
            gestures_detected = []
            for frame in self.current_recording:
                frame_data = frame.get('frame_data', {})
                if 'gestures' in frame_data:
                    gestures_detected.extend(frame_data['gestures'])
                elif 'gesture' in frame_data:
                    gestures_detected.append(frame_data['gesture'])
            
            # Análisis de calidad
            quality_metrics = self._analyze_quality()
            
            # Crear metadatos
            metadata = {
                'gesture_name': self.current_gesture_name,
                'recording_mode': self.recording_mode,
                'action': self.current_action,
                'profile': self.current_profile,
                'notes': self.notes,
                'total_frames': total_frames,
                'duration': duration,
                'fps': total_frames / duration if duration > 0 else 0,
                'timestamp': datetime.now().isoformat(),
                'quality_score': quality_metrics.get('overall_score', 0.0),
                'gestures_detected': list(set(gestures_detected))[:10]  # Únicos, máximo 10
            }
            
            # Extraer características
            features = self._extract_features()
            
            recording_data = {
                'metadata': metadata,
                'frames': self.current_recording,
                'features': features,
                'quality_metrics': quality_metrics,
                'version': '1.0',
                'recorder_config': self.config
            }
            
            logger.debug(f"📊 Grabación procesada: {total_frames} frames, {duration:.2f}s")
            return recording_data
            
        except Exception as e:
            logger.error(f"❌ Error procesando grabación: {e}", exc_info=True)
            return None
    
    def _analyze_quality(self) -> Dict[str, Any]:
        """Analiza la calidad de la grabación."""
        if len(self.current_recording) < 2:
            return {'overall_score': 0.0, 'issues': ['muy_corto']}
        
        try:
            metrics = {
                'frame_count': len(self.current_recording),
                'duration': self.current_recording[-1]['timestamp'],
                'issues': []
            }
            
            # Verificar consistencia de timestamps
            timestamps = [f['timestamp'] for f in self.current_recording]
            time_diffs = np.diff(timestamps)
            
            if len(time_diffs) > 0:
                metrics['avg_frame_time'] = np.mean(time_diffs)
                metrics['fps_actual'] = 1.0 / metrics['avg_frame_time'] if metrics['avg_frame_time'] > 0 else 0
                
                # Detectar caídas de frames
                large_gaps = [td for td in time_diffs if td > 0.1]  # >100ms
                if large_gaps:
                    metrics['issues'].append('caidas_frames')
                    metrics['large_gaps_count'] = len(large_gaps)
            
            # Verificar datos de landmarks
            landmarks_present = 0
            for frame in self.current_recording:
                frame_data = frame.get('frame_data', {})
                if 'landmarks' in frame_data or 'hands' in frame_data:
                    landmarks_present += 1
            
            metrics['landmarks_coverage'] = landmarks_present / len(self.current_recording)
            
            if metrics['landmarks_coverage'] < 0.5:
                metrics['issues'].append('landmarks_insuficientes')
            
            # Calcular puntuación general
            scores = []
            
            # Puntuación por duración (0-1)
            duration_score = min(metrics['duration'] / 2.0, 1.0)  # 2 segundos óptimo
            scores.append(duration_score * 0.3)
            
            # Puntuación por cobertura de landmarks
            scores.append(metrics['landmarks_coverage'] * 0.4)
            
            # Puntuación por consistencia de FPS
            if 'fps_actual' in metrics:
                fps_score = min(metrics['fps_actual'] / 30.0, 1.0)  # 30 FPS óptimo
                scores.append(fps_score * 0.3)
            
            metrics['overall_score'] = sum(scores) / len(scores) if scores else 0.0
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error analizando calidad: {e}")
            return {'overall_score': 0.0, 'issues': ['error_analisis']}
    
    def _extract_features(self) -> Dict[str, Any]:
        """Extrae características de los gestos grabados."""
        features = {
            'trajectories': [],
            'speeds': [],
            'accelerations': [],
            'key_points': []
        }
        
        try:
            if len(self.current_recording) < 3:
                return features
            
            # Extraer posiciones de manos si están disponibles
            positions = []
            for frame in self.current_recording:
                frame_data = frame.get('frame_data', {})
                
                # Intentar obtener posición de mano
                position = None
                
                if 'hands' in frame_data and frame_data['hands']:
                    # Usar primera mano
                    hand = frame_data['hands'][0]
                    if 'bbox' in hand and 'center' in hand['bbox']:
                        position = hand['bbox']['center']
                
                if position:
                    positions.append((position[0], position[1], frame['timestamp']))
            
            if len(positions) > 1:
                # Calcular velocidades
                speeds = []
                for i in range(len(positions) - 1):
                    x1, y1, t1 = positions[i]
                    x2, y2, t2 = positions[i + 1]
                    
                    dt = t2 - t1
                    if dt > 0:
                        dx = x2 - x1
                        dy = y2 - y1
                        speed = np.sqrt(dx*dx + dy*dy) / dt
                        speeds.append(speed)
                
                features['speeds'] = speeds
                
                if speeds:
                    features['avg_speed'] = np.mean(speeds)
                    features['max_speed'] = np.max(speeds)
                    features['speed_variance'] = np.var(speeds)
            
            # Puntos clave: inicio, pico, fin
            if len(self.current_recording) >= 3:
                features['key_points'] = [
                    self.current_recording[0],
                    self.current_recording[len(self.current_recording)//2],
                    self.current_recording[-1]
                ]
            
            return features
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo características: {e}")
            return features
    
    # ========== PERSISTENCIA ==========
    
    def _save_recording(self, recording_data: Dict[str, Any]) -> Optional[Path]:
        """Guarda la grabación en disco."""
        try:
            # Crear nombre de archivo único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() else "_" for c in self.current_gesture_name)
            
            if not safe_name:
                safe_name = "unknown"
            
            filename = f"{safe_name}_{timestamp}.json"
            filepath = self.output_dir / filename
            
            # Guardar como JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recording_data, f, indent=2, ensure_ascii=False)
            
            # Actualizar índice y estadísticas
            self._update_recording_index(filepath, recording_data['metadata'])
            self.stats['total_recordings'] += 1
            self.stats['total_frames'] += recording_data['metadata']['total_frames']
            self.stats['total_duration'] += recording_data['metadata']['duration']
            self.stats['last_recording'] = timestamp
            
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error guardando grabación: {e}")
            return None
    
    def _load_recording_index(self):
        """Carga el índice de grabaciones existentes."""
        index_file = self.output_dir / "recordings_index.json"
        
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.recording_index = json.load(f)
                
                # Actualizar estadísticas
                for entry in self.recording_index:
                    self.stats['total_recordings'] += 1
                    self.stats['total_frames'] += entry.get('total_frames', 0)
                    self.stats['total_duration'] += entry.get('duration', 0)
                
                logger.debug(f"📋 Índice cargado: {len(self.recording_index)} grabaciones")
            except:
                self.recording_index = []
        else:
            self.recording_index = []
    
    def _update_recording_index(self, filepath: Path, metadata: Dict[str, Any]):
        """Actualiza el índice de grabaciones."""
        entry = {
            'file': filepath.name,
            'gesture_name': metadata['gesture_name'],
            'mode': metadata['recording_mode'],
            'action': metadata['action'],
            'timestamp': metadata['timestamp'],
            'duration': metadata['duration'],
            'total_frames': metadata['total_frames'],
            'quality_score': metadata['quality_score'],
            'fps': metadata['fps']
        }
        
        self.recording_index.append(entry)
        
        # Guardar índice
        index_file = self.output_dir / "recordings_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(self.recording_index, f, indent=2, ensure_ascii=False)
    
    # ========== API PÚBLICA ==========
    
    def load_recording(self, filename: str) -> Optional[Dict[str, Any]]:
        """Carga una grabación desde disco."""
        try:
            filepath = Path(filename)
            if not filepath.is_absolute():
                filepath = self.output_dir / filename
            
            if not filepath.exists():
                logger.error(f"❌ Archivo no encontrado: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"❌ Error cargando grabación: {e}")
            return None
    
    def list_recordings(self, 
                       filter_by: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lista grabaciones con filtros opcionales."""
        if filter_by is None:
            return self.recording_index.copy()
        
        filtered = []
        for entry in self.recording_index:
            match = True
            for key, value in filter_by.items():
                if key in entry and entry[key] != value:
                    match = False
                    break
            
            if match:
                filtered.append(entry)
        
        return filtered
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la grabadora."""
        return {
            **self.stats,
            'is_recording': self.is_recording,
            'current_gesture': self.current_gesture_name,
            'output_dir': str(self.output_dir.absolute()),
            'index_size': len(self.recording_index),
            'config': self.config
        }
    
    def clear_recordings(self, confirm: bool = False) -> bool:
        """Elimina todas las grabaciones."""
        if not confirm:
            logger.warning("⚠️ Se requiere confirmación para eliminar grabaciones")
            return False
        
        try:
            import shutil
            
            # Eliminar archivos
            for file in self.output_dir.glob("*.json"):
                file.unlink()
            
            # Reiniciar estado
            self.recording_index = []
            self.stats = {
                'total_recordings': 0,
                'total_frames': 0,
                'total_duration': 0.0,
                'last_recording': None
            }
            
            logger.info("🧹 Todas las grabaciones eliminadas")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error eliminando grabaciones: {e}")
            return False
    
    def export_for_training(self, 
                          output_format: str = "json",
                          include_images: bool = False) -> Optional[Path]:
        """
        Exporta grabaciones para entrenamiento.
        
        Args:
            output_format: Formato de salida ('json', 'csv', 'numpy')
            include_images: Incluir imágenes (solo si son pequeñas)
            
        Returns:
            Ruta del archivo exportado
        """
        # TODO: Implementar exportación para entrenamiento
        logger.warning("⚠️ Exportación para entrenamiento no implementada")
        return None
    
    def cleanup(self):
        """Limpia recursos."""
        if self.is_recording:
            self.stop_recording()
        
        logger.info("🧹 GestureRecorder limpiado")

# ¡NO hay instancia global aquí!
# Debe crearse e inyectarse donde se necesite

"""
MAIN
# 1. Inicializar logger PRIMERO
from utils.logger import NYXLogger

logger = NYXLogger(
    app_name="NYX",
    log_dir="logs",
    level="INFO",
    console=True,
    colors=True
)

logger.log_system_start("1.0.0")

# 2. Inicializar ConfigLoader
from utils.config_loader import ConfigLoader

config_loader = ConfigLoader()  # Auto-detecta src/config/
system_config = config_loader.get_system_config()

# 3. Inicializar GestureRecorder cuando se necesite
from utils.gesture_recorder import GestureRecorder

# Opcional: Configurar detectores después
recorder = GestureRecorder(output_dir="recorded_gestures")
# recorder.set_hand_detector(hand_detector)  # Inyectar después
"""

"""
GESTURE PIPELINE
class GesturePipeline:
    def __init__(self, config: Dict):
        # Obtener logger específico
        self.logger = logging.getLogger("NYX.GesturePipeline")
        
        # Usar ConfigLoader
        from utils.config_loader import ConfigLoader
        self.config_loader = ConfigLoader()
        
        # Cargar perfil activo
        active_profile = config.get('active_profile', 'gamer')
        profile_data = self.config_loader.get_profile(active_profile)
        
        # Inicializar recorder opcional
        self.recorder = None
        if config.get('enable_recording', False):
            from utils.gesture_recorder import GestureRecorder
            self.recorder = GestureRecorder(config=config.get('recorder', {}))
"""

"""
OTROS
# Para obtener un logger específico del módulo
import logging
logger = logging.getLogger("NYX.Core.ActionExecutor")

# O usar el logger principal
from utils import NYXLogger
main_logger = NYXLogger()
main_logger.log_action_executed("keyboard", "press", "ctrl+s")
"""