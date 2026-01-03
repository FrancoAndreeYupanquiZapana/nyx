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
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from datetime import datetime
from collections import deque
import numpy as np
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger(__name__)


class RecordingMode(Enum):
    """Modos de grabación disponibles."""
    SINGLE = "single"
    SEQUENCE = "sequence"
    CONTINUOUS = "continuous"
    TRAINING = "training"


class QualityLevel(Enum):
    """Niveles de calidad."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCELLENT = "excellent"


@dataclass
class RecordingConfig:
    """Configuración de grabación."""
    min_frames_per_gesture: int = 15
    max_recording_time: float = 30.0
    buffer_size: int = 30
    min_confidence: float = 0.6
    auto_save: bool = True
    compression: bool = False
    default_sample_rate: int = 30
    min_quality_score: float = 0.7
    export_formats: List[str] = field(default_factory=lambda: ["json", "numpy"])
    metadata_fields: List[str] = field(default_factory=lambda: [
        "gesture_name", "action", "profile", "user_id", "environment"
    ])


@dataclass
class FrameData:
    """Datos de un frame individual."""
    timestamp: float
    frame_id: int
    frame_data: Dict[str, Any]
    image_thumbnail: Optional[List] = None
    quality_score: Optional[float] = None
    landmarks_present: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)


@dataclass 
class RecordingMetadata:
    """Metadatos de una grabación."""
    gesture_name: str
    recording_mode: str
    action: str = ""
    profile: str = ""
    user_id: str = "anonymous"
    environment: str = "default"
    notes: str = ""
    total_frames: int = 0
    duration: float = 0.0
    fps: float = 0.0
    timestamp: str = ""
    quality_score: float = 0.0
    quality_level: str = ""
    gestures_detected: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return asdict(self)


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
                 output_dir: Union[str, Path] = "workspace/recorded_gestures",
                 config: Optional[Dict[str, Any]] = None,
                 auto_cleanup: bool = False):
        """
        Inicializa la grabadora de gestos.
        
        Args:
            output_dir: Directorio para guardar grabaciones
            config: Configuración opcional
            auto_cleanup: Limpiar automáticamente grabaciones de baja calidad
        """
        self.output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuración
        self._config = RecordingConfig(**config) if config else RecordingConfig()
        
        # Detectores (se inyectan después)
        self.hand_detector = None
        self.arm_detector = None
        self.pose_detector = None
        
        # Estado de grabación
        self.is_recording = False
        self.recording_mode = None
        self.current_recording: List[FrameData] = []
        self.recording_start_time = 0
        self.recording_paused = False
        
        # Buffer para análisis
        self.frame_buffer = deque(maxlen=self._config.buffer_size)
        
        # Metadatos actuales
        self.current_metadata = RecordingMetadata(gesture_name="", recording_mode="")
        
        # Hilos
        self.recording_thread = None
        self.stop_flag = threading.Event()
        self.lock = threading.RLock()  # Lock para acceso concurrente
        
        # Estadísticas
        self.stats = {
            'total_recordings': 0,
            'total_frames': 0,
            'total_duration': 0.0,
            'last_recording': None,
            'quality_distribution': {level.value: 0 for level in QualityLevel}
        }
        
        # Calidad
        self.quality_thresholds = {
            QualityLevel.LOW: 0.0,
            QualityLevel.MEDIUM: 0.5,
            QualityLevel.HIGH: 0.7,
            QualityLevel.EXCELLENT: 0.9
        }
        
        # Callbacks
        self.on_recording_start: Optional[Callable] = None
        self.on_recording_stop: Optional[Callable] = None
        self.on_frame_added: Optional[Callable] = None
        self.on_quality_alert: Optional[Callable] = None
        
        # Cargar índice existente
        self.recording_index = []
        self._load_recording_index()
        
        # Auto-cleanup si está habilitado
        if auto_cleanup:
            self._cleanup_low_quality_recordings()
        
        logger.info(f"🎥 GestureRecorder inicializado. Salida: {self.output_dir}")
        logger.debug(f"Configuración: {self._config}")
    
    # ========== PROPIEDADES ==========
    
    @property
    def config(self) -> RecordingConfig:
        """Obtiene la configuración."""
        return self._config
    
    @property
    def current_duration(self) -> float:
        """Duración actual de la grabación."""
        if not self.is_recording or not self.current_recording:
            return 0.0
        return time.time() - self.recording_start_time
    
    @property
    def frame_count(self) -> int:
        """Número de frames en la grabación actual."""
        return len(self.current_recording)
    
    # ========== INYECCIÓN DE DEPENDENCIAS ==========
    
    def set_detector(self, detector_type: str, detector: Any):
        """
        Establece un detector.
        
        Args:
            detector_type: Tipo de detector ('hand', 'arm', 'pose')
            detector: Instancia del detector
        """
        with self.lock:
            if detector_type == 'hand':
                self.hand_detector = detector
                logger.debug("✅ Detector de manos configurado")
            elif detector_type == 'arm':
                self.arm_detector = detector
                logger.debug("✅ Detector de brazos configurado")
            elif detector_type == 'pose':
                self.pose_detector = detector
                logger.debug("✅ Detector de postura configurado")
            else:
                logger.warning(f"⚠️ Tipo de detector desconocido: {detector_type}")
    
    def set_callbacks(self, **callbacks):
        """Configura callbacks para eventos."""
        valid_callbacks = {
            'on_recording_start', 'on_recording_stop',
            'on_frame_added', 'on_quality_alert'
        }
        
        for name, callback in callbacks.items():
            if name in valid_callbacks:
                setattr(self, name, callback)
                logger.debug(f"✅ Callback configurado: {name}")
    
    # ========== CONTROL DE GRABACIÓN ==========
    
    def start_recording(self,
                       gesture_name: str,
                       mode: Union[str, RecordingMode] = RecordingMode.SINGLE,
                       **metadata) -> bool:
        """
        Inicia una nueva grabación.
        
        Args:
            gesture_name: Nombre del gesto (requerido)
            mode: Modo de grabación
            **metadata: Metadatos adicionales
            
        Returns:
            True si se inició correctamente
        """
        with self.lock:
            if self.is_recording:
                logger.warning("⚠️ Ya hay una grabación en curso")
                return False
            
            # Validar modo
            if isinstance(mode, str):
                try:
                    mode = RecordingMode(mode)
                except ValueError:
                    logger.error(f"❌ Modo de grabación inválido: {mode}")
                    return False
            
            if mode != RecordingMode.CONTINUOUS and not gesture_name:
                logger.error("❌ Se requiere nombre de gesto para este modo")
                return False
            
            # Configurar metadatos
            self.current_metadata = RecordingMetadata(
                gesture_name=gesture_name,
                recording_mode=mode.value,
                timestamp=datetime.now().isoformat(),
                **{k: v for k, v in metadata.items() 
                   if k in RecordingMetadata.__annotations__}
            )
            
            # Inicializar grabación
            self.is_recording = True
            self.recording_mode = mode
            self.current_recording = []
            self.recording_start_time = time.time()
            self.recording_paused = False
            
            # Limpiar buffer y flags
            self.frame_buffer.clear()
            self.stop_flag.clear()
            
            # Ejecutar callback si existe
            if self.on_recording_start:
                try:
                    self.on_recording_start(self.current_metadata)
                except Exception as e:
                    logger.error(f"❌ Error en callback on_recording_start: {e}")
            
            logger.info(f"⏺️  Grabación iniciada: {gesture_name} ({mode.value})")
            return True
    
    def pause_recording(self) -> bool:
        """Pausa la grabación actual."""
        with self.lock:
            if not self.is_recording:
                logger.warning("⚠️ No hay grabación en curso")
                return False
            
            self.recording_paused = True
            logger.info("⏸️  Grabación pausada")
            return True
    
    def resume_recording(self) -> bool:
        """Reanuda la grabación pausada."""
        with self.lock:
            if not self.is_recording:
                logger.warning("⚠️ No hay grabación en curso")
                return False
            
            if not self.recording_paused:
                logger.warning("⚠️ La grabación no está pausada")
                return False
            
            self.recording_paused = False
            logger.info("▶️  Grabación reanudada")
            return True
    
    def stop_recording(self, save: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Detiene la grabación actual.
        
        Args:
            save: Si guardar automáticamente (None = usar auto_save config)
            
        Returns:
            Datos de la grabación o None
        """
        with self.lock:
            if not self.is_recording:
                logger.warning("⚠️ No hay grabación en curso")
                return None
            
            self.is_recording = False
            self.stop_flag.set()
            
            # Procesar grabación
            recording_data = self._process_recording()
            
            # Determinar si guardar
            should_save = save if save is not None else self._config.auto_save
            
            if should_save and recording_data:
                saved_path = self._save_recording(recording_data)
                if saved_path:
                    logger.info(f"💾 Grabación guardada: {saved_path.name}")
            
            # Ejecutar callback si existe
            if self.on_recording_stop and recording_data:
                try:
                    self.on_recording_stop(recording_data)
                except Exception as e:
                    logger.error(f"❌ Error en callback on_recording_stop: {e}")
            
            logger.info(f"⏹️  Grabación finalizada: {self.frame_count} frames")
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
        if not self.is_recording or self.recording_paused:
            return False
        
        with self.lock:
            try:
                # Crear entrada del frame
                timestamp = time.time() - self.recording_start_time
                frame_id = len(self.current_recording)
                
                # Crear thumbnail si se proporciona image
                image_thumbnail = None
                if image is not None:
                    # Redimensionar a tamaño manejable
                    if image.size > 0:
                        # Convertir a miniatura (max 64x64)
                        h, w = image.shape[:2]
                        scale = min(64 / max(h, w), 1.0)
                        if scale < 1.0:
                            new_h, new_w = int(h * scale), int(w * scale)
                            # Usar OpenCV si está disponible, sino numpy básico
                            try:
                                import cv2
                                thumbnail = cv2.resize(image, (new_w, new_h))
                            except ImportError:
                                # Resample simple con numpy
                                thumbnail = image[::int(1/scale), ::int(1/scale)]
                        else:
                            thumbnail = image.copy()
                        
                        # Aplanar para JSON
                        image_thumbnail = thumbnail.flatten().tolist()
                
                # Verificar landmarks
                landmarks_present = self._check_landmarks_present(frame_data)
                
                # Calcular calidad del frame
                quality_score = self._calculate_frame_quality(frame_data, landmarks_present)
                
                # Crear objeto FrameData
                frame_entry = FrameData(
                    timestamp=timestamp,
                    frame_id=frame_id,
                    frame_data=frame_data,
                    image_thumbnail=image_thumbnail,
                    quality_score=quality_score,
                    landmarks_present=landmarks_present
                )
                
                # Agregar a la grabación
                self.current_recording.append(frame_entry)
                self.frame_buffer.append(frame_entry)
                
                # Ejecutar callback si existe
                if self.on_frame_added:
                    try:
                        self.on_frame_added(frame_entry)
                    except Exception as e:
                        logger.error(f"❌ Error en callback on_frame_added: {e}")
                
                # Verificar límites
                self._check_recording_limits(timestamp)
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error agregando frame: {e}", exc_info=True)
                return False
    
    # ========== PROCESAMIENTO Y ANÁLISIS ==========
    
    def _check_landmarks_present(self, frame_data: Dict[str, Any]) -> bool:
        """Verifica si hay landmarks en el frame."""
        # Buscar landmarks en diferentes formatos
        landmarks_sources = [
            frame_data.get('landmarks'),
            frame_data.get('hands', [{}])[0].get('landmarks') if frame_data.get('hands') else None,
            frame_data.get('pose', {}).get('landmarks'),
            frame_data.get('keypoints')
        ]
        
        for landmarks in landmarks_sources:
            if landmarks and len(landmarks) > 0:
                return True
        
        return False
    
    def _calculate_frame_quality(self, frame_data: Dict[str, Any], landmarks_present: bool) -> float:
        """Calcula la calidad de un frame individual."""
        score = 0.0
        
        # Puntos por landmarks
        if landmarks_present:
            score += 0.4
        
        # Puntos por confianza
        confidence = frame_data.get('confidence', 0.0)
        score += confidence * 0.3
        
        # Puntos por gestos detectados
        if frame_data.get('gestures') or frame_data.get('gesture'):
            score += 0.3
        
        return min(score, 1.0)
    
    def _check_recording_limits(self, timestamp: float):
        """Verifica límites de grabación."""
        # Límite de tiempo
        if timestamp > self._config.max_recording_time:
            logger.warning("⏰ Límite de tiempo de grabación alcanzado")
            self.stop_recording()
        
        # Límite mínimo de frames
        elif (self.recording_mode == RecordingMode.SINGLE and 
              len(self.current_recording) >= self._config.min_frames_per_gesture and
              timestamp > 1.0):  # Al menos 1 segundo
            # Verificar si el gesto está completo
            if self._is_gesture_complete():
                logger.info("✅ Gesto completo detectado")
                self.stop_recording()
    
    def _is_gesture_complete(self) -> bool:
        """Detecta si un gesto está completo."""
        if len(self.current_recording) < 3:
            return False
        
        # Análisis simple de velocidad
        try:
            speeds = []
            for i in range(len(self.current_recording) - 1):
                f1 = self.current_recording[i]
                f2 = self.current_recording[i + 1]
                
                # Calcular velocidad si hay posiciones
                pos1 = self._extract_position(f1.frame_data)
                pos2 = self._extract_position(f2.frame_data)
                
                if pos1 and pos2:
                    dt = f2.timestamp - f1.timestamp
                    if dt > 0:
                        dx = pos2[0] - pos1[0]
                        dy = pos2[1] - pos1[1]
                        speed = np.sqrt(dx*dx + dy*dy) / dt
                        speeds.append(speed)
            
            if speeds:
                # Si la velocidad cae cerca de cero, el gesto podría estar completo
                recent_speeds = speeds[-min(5, len(speeds)):]
                avg_recent_speed = np.mean(recent_speeds)
                
                if avg_recent_speed < 0.05:  # Umbral empírico
                    return True
                
        except Exception as e:
            logger.debug(f"Error analizando gesto: {e}")
        
        return False
    
    def _extract_position(self, frame_data: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """Extrae posición de los datos del frame."""
        # Buscar en diferentes formatos
        if 'hands' in frame_data and frame_data['hands']:
            hand = frame_data['hands'][0]
            if 'bbox' in hand and 'center' in hand['bbox']:
                return hand['bbox']['center'][:2]
        
        if 'landmarks' in frame_data and frame_data['landmarks']:
            # Usar promedio de landmarks
            landmarks = np.array(frame_data['landmarks'])
            if landmarks.shape[0] > 0:
                return tuple(np.mean(landmarks[:, :2], axis=0))
        
        return None
    
    def _process_recording(self) -> Optional[Dict[str, Any]]:
        """Procesa la grabación para extraer características."""
        if not self.current_recording:
            return None
        
        try:
            # Actualizar metadatos con información real
            self.current_metadata.total_frames = len(self.current_recording)
            self.current_metadata.duration = self.current_recording[-1].timestamp
            self.current_metadata.fps = (self.current_metadata.total_frames / 
                                       self.current_metadata.duration 
                                       if self.current_metadata.duration > 0 else 0)
            
            # Extraer gestos detectados
            gestures_detected = set()
            for frame in self.current_recording:
                frame_data = frame.frame_data
                if 'gestures' in frame_data:
                    for gesture in frame_data['gestures']:
                        if isinstance(gesture, dict):
                            gestures_detected.add(gesture.get('name', 'unknown'))
                        else:
                            gestures_detected.add(str(gesture))
                elif 'gesture' in frame_data:
                    gesture = frame_data['gesture']
                    if isinstance(gesture, dict):
                        gestures_detected.add(gesture.get('name', 'unknown'))
                    else:
                        gestures_detected.add(str(gesture))
            
            self.current_metadata.gestures_detected = list(gestures_detected)
            
            # Análisis de calidad
            quality_metrics = self._analyze_quality()
            self.current_metadata.quality_score = quality_metrics.get('overall_score', 0.0)
            
            # Determinar nivel de calidad
            for level, threshold in sorted(self.quality_thresholds.items(), 
                                         key=lambda x: x[1], reverse=True):
                if self.current_metadata.quality_score >= threshold:
                    self.current_metadata.quality_level = level.value
                    break
            
            # Extraer características
            features = self._extract_features()
            
            # Alerta de baja calidad si es necesario
            if (self.current_metadata.quality_score < self._config.min_quality_score and
                self.on_quality_alert):
                try:
                    self.on_quality_alert(self.current_metadata.quality_score, 
                                        quality_metrics.get('issues', []))
                except Exception as e:
                    logger.error(f"❌ Error en callback on_quality_alert: {e}")
            
            recording_data = {
                'metadata': self.current_metadata.to_dict(),
                'frames': [frame.to_dict() for frame in self.current_recording],
                'features': features,
                'quality_metrics': quality_metrics,
                'version': '2.0',
                'recorder_config': asdict(self._config)
            }
            
            logger.debug(f"📊 Grabación procesada: {self.current_metadata.total_frames} frames, "
                        f"{self.current_metadata.duration:.2f}s, "
                        f"Calidad: {self.current_metadata.quality_level}")
            
            return recording_data
            
        except Exception as e:
            logger.error(f"❌ Error procesando grabación: {e}", exc_info=True)
            return None
    
    def _analyze_quality(self) -> Dict[str, Any]:
        """Analiza la calidad de la grabación."""
        metrics = {
            'frame_count': len(self.current_recording),
            'issues': [],
            'warnings': [],
            'suggestions': []
        }
        
        try:
            if len(self.current_recording) < 2:
                metrics['issues'].append('muy_corto')
                metrics['overall_score'] = 0.0
                return metrics
            
            # Duración
            metrics['duration'] = self.current_recording[-1].timestamp
            
            # Calidad de frames individuales
            frame_scores = [frame.quality_score for frame in self.current_recording 
                          if frame.quality_score is not None]
            
            if frame_scores:
                metrics['avg_frame_quality'] = np.mean(frame_scores)
                metrics['min_frame_quality'] = np.min(frame_scores)
                metrics['frame_quality_std'] = np.std(frame_scores)
                
                # Contar frames de baja calidad
                low_quality_frames = sum(1 for score in frame_scores if score < 0.3)
                if low_quality_frames > len(frame_scores) * 0.3:  # Más del 30%
                    metrics['issues'].append('muchos_frames_baja_calidad')
                    metrics['low_quality_frames_count'] = low_quality_frames
            
            # Consistencia temporal
            timestamps = [frame.timestamp for frame in self.current_recording]
            time_diffs = np.diff(timestamps)
            
            if len(time_diffs) > 0:
                metrics['avg_frame_time'] = np.mean(time_diffs)
                metrics['fps_actual'] = 1.0 / metrics['avg_frame_time'] if metrics['avg_frame_time'] > 0 else 0
                metrics['frame_time_std'] = np.std(time_diffs)
                
                # Detectar problemas de timing
                if metrics['frame_time_std'] > 0.05:
                    metrics['warnings'].append('inconsistencia_temporal')
                
                large_gaps = [td for td in time_diffs if td > 0.1]
                if large_gaps:
                    metrics['issues'].append('caidas_frames')
                    metrics['large_gaps_count'] = len(large_gaps)
            
            # Cobertura de landmarks
            landmarks_frames = sum(1 for frame in self.current_recording 
                                 if frame.landmarks_present)
            metrics['landmarks_coverage'] = landmarks_frames / len(self.current_recording)
            
            if metrics['landmarks_coverage'] < 0.5:
                metrics['issues'].append('landmarks_insuficientes')
            elif metrics['landmarks_coverage'] < 0.8:
                metrics['warnings'].append('landmarks_intermitentes')
            
            # Cálculo de puntuación final
            scores = []
            
            # Duración (0-1, óptimo 2-5 segundos)
            duration_norm = min(metrics['duration'] / 5.0, 1.0)
            scores.append(duration_norm * 0.2)
            
            # Cobertura de landmarks
            scores.append(metrics['landmarks_coverage'] * 0.3)
            
            # Calidad promedio de frames
            if 'avg_frame_quality' in metrics:
                scores.append(metrics['avg_frame_quality'] * 0.3)
            
            # Consistencia de FPS
            if 'fps_actual' in metrics:
                fps_score = min(metrics['fps_actual'] / 30.0, 1.0)
                scores.append(fps_score * 0.2)
            
            # Penalizaciones por issues
            penalty = 1.0
            for issue in metrics['issues']:
                if issue in ['muy_corto', 'caidas_frames']:
                    penalty *= 0.7
                elif issue in ['landmarks_insuficientes', 'muchos_frames_baja_calidad']:
                    penalty *= 0.8
            
            metrics['overall_score'] = (sum(scores) / len(scores) * penalty if scores else 0.0)
            
            # Sugerencias
            if metrics['landmarks_coverage'] < 0.8:
                metrics['suggestions'].append('mejorar_iluminacion_o_posicion')
            
            if 'inconsistencia_temporal' in metrics['warnings']:
                metrics['suggestions'].append('reducir_carga_sistema')
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error analizando calidad: {e}", exc_info=True)
            metrics['issues'].append('error_analisis')
            metrics['overall_score'] = 0.0
            return metrics
    
    def _extract_features(self) -> Dict[str, Any]:
        """Extrae características de los gestos grabados."""
        features = {
            'trajectories': [],
            'speeds': [],
            'accelerations': [],
            'key_points': [],
            'statistics': {}
        }
        
        try:
            if len(self.current_recording) < 3:
                return features
            
            # Extraer trayectoria
            positions = []
            for frame in self.current_recording:
                pos = self._extract_position(frame.frame_data)
                if pos:
                    positions.append({
                        'x': float(pos[0]),
                        'y': float(pos[1]),
                        't': frame.timestamp
                    })
            
            if len(positions) > 1:
                features['trajectories'] = positions
                
                # Calcular velocidades
                speeds = []
                for i in range(len(positions) - 1):
                    p1 = positions[i]
                    p2 = positions[i + 1]
                    dt = p2['t'] - p1['t']
                    
                    if dt > 0:
                        dx = p2['x'] - p1['x']
                        dy = p2['y'] - p1['y']
                        speed = np.sqrt(dx*dx + dy*dy) / dt
                        speeds.append(float(speed))
                
                if speeds:
                    features['speeds'] = speeds
                    
                    # Estadísticas
                    features['statistics']['avg_speed'] = float(np.mean(speeds))
                    features['statistics']['max_speed'] = float(np.max(speeds))
                    features['statistics']['min_speed'] = float(np.min(speeds))
                    features['statistics']['speed_std'] = float(np.std(speeds))
                    
                    # Aceleraciones
                    if len(speeds) > 1:
                        accelerations = []
                        time_intervals = [positions[i+1]['t'] - positions[i]['t'] 
                                        for i in range(len(positions)-1)]
                        
                        for i in range(len(speeds) - 1):
                            if time_intervals[i] > 0:
                                acceleration = (speeds[i+1] - speeds[i]) / time_intervals[i]
                                accelerations.append(float(acceleration))
                        
                        if accelerations:
                            features['accelerations'] = accelerations
                            features['statistics']['avg_acceleration'] = float(np.mean(accelerations))
                            features['statistics']['max_acceleration'] = float(np.max(accelerations))
            
            # Puntos clave
            key_frame_indices = [0, len(self.current_recording) // 2, -1]
            features['key_points'] = [
                {
                    'frame_id': self.current_recording[i].frame_id,
                    'timestamp': self.current_recording[i].timestamp,
                    'position': self._extract_position(self.current_recording[i].frame_data)
                }
                for i in key_frame_indices
            ]
            
            return features
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo características: {e}")
            return features
    
    # ========== PERSISTENCIA ==========
    
    def _save_recording(self, recording_data: Dict[str, Any]) -> Optional[Path]:
        """Guarda la grabación en disco."""
        try:
            # Crear nombre de archivo seguro
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            safe_name = "".join(c if c.isalnum() else "_" for c in self.current_metadata.gesture_name)
            safe_name = safe_name or "gesture"
            
            # Incluir calidad en el nombre
            quality_level = self.current_metadata.quality_level or "unknown"
            filename = f"{safe_name}_{quality_level}_{timestamp}.json"
            filepath = self.output_dir / filename
            
            # Guardar como JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recording_data, f, indent=2, ensure_ascii=False, 
                         default=self._json_serializer)
            
            # Actualizar índice y estadísticas
            self._update_recording_index(filepath, recording_data['metadata'])
            
            # Actualizar distribución de calidad
            quality_level = self.current_metadata.quality_level
            if quality_level in self.stats['quality_distribution']:
                self.stats['quality_distribution'][quality_level] += 1
            
            logger.debug(f"💾 Grabación guardada: {filepath.name}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error guardando grabación: {e}")
            return None
    
    def _json_serializer(self, obj):
        """Serializador personalizado para JSON."""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Tipo {type(obj)} no serializable")
    
    def _load_recording_index(self):
        """Carga el índice de grabaciones existentes."""
        index_file = self.output_dir / "recordings_index.json"
        
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    self.recording_index = json.load(f)
                
                logger.debug(f"📋 Índice cargado: {len(self.recording_index)} grabaciones")
            except Exception as e:
                logger.error(f"❌ Error cargando índice: {e}")
                self.recording_index = []
        else:
            self.recording_index = []
    
    def _update_recording_index(self, filepath: Path, metadata: Dict[str, Any]):
        """Actualiza el índice de grabaciones."""
        entry = {
            'file': filepath.name,
            'path': str(filepath.absolute()),
            'size_kb': filepath.stat().st_size / 1024 if filepath.exists() else 0,
            **metadata
        }
        
        self.recording_index.append(entry)
        self.stats['total_recordings'] = len(self.recording_index)
        self.stats['last_recording'] = metadata.get('timestamp')
        
        # Guardar índice actualizado
        index_file = self.output_dir / "recordings_index.json"
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(self.recording_index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Error guardando índice: {e}")
    
    def _cleanup_low_quality_recordings(self, min_quality: float = 0.5):
        """Limpia grabaciones de baja calidad."""
        try:
            to_remove = []
            for entry in self.recording_index[:]:  # Copia para iterar
                if entry.get('quality_score', 0) < min_quality:
                    filepath = Path(entry.get('path', self.output_dir / entry['file']))
                    if filepath.exists():
                        filepath.unlink()
                        to_remove.append(entry)
                        logger.debug(f"🗑️  Eliminada grabación de baja calidad: {filepath.name}")
            
            # Actualizar índice
            self.recording_index = [e for e in self.recording_index if e not in to_remove]
            self.stats['total_recordings'] = len(self.recording_index)
            
            if to_remove:
                self._update_recording_index_file()
                logger.info(f"🧹 Eliminadas {len(to_remove)} grabaciones de baja calidad")
                
        except Exception as e:
            logger.error(f"❌ Error en cleanup: {e}")
    
    def _update_recording_index_file(self):
        """Guarda el índice en disco."""
        index_file = self.output_dir / "recordings_index.json"
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(self.recording_index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Error actualizando índice: {e}")
    
    # ========== API PÚBLICA ==========
    
    def load_recording(self, 
                      filename: str, 
                      load_frames: bool = True) -> Optional[Dict[str, Any]]:
        """Carga una grabación desde disco."""
        try:
            filepath = Path(filename)
            if not filepath.is_absolute():
                filepath = self.output_dir / filename
            
            if not filepath.exists():
                logger.error(f"❌ Archivo no encontrado: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not load_frames and 'frames' in data:
                # Remover frames para ahorrar memoria
                data['frames'] = f"{len(data['frames'])} frames (no cargados)"
            
            logger.debug(f"📂 Grabación cargada: {filepath.name}")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error cargando grabación: {e}")
            return None
    
    def list_recordings(self, 
                       filter_by: Optional[Dict[str, Any]] = None,
                       sort_by: str = "timestamp",
                       descending: bool = True) -> List[Dict[str, Any]]:
        """Lista grabaciones con filtros y ordenamiento."""
        recordings = self.recording_index.copy()
        
        # Aplicar filtros
        if filter_by:
            filtered = []
            for entry in recordings:
                match = True
                for key, value in filter_by.items():
                    if key in entry:
                        if isinstance(value, (list, tuple)):
                            if entry[key] not in value:
                                match = False
                                break
                        elif entry[key] != value:
                            match = False
                            break
                    else:
                        match = False
                        break
                
                if match:
                    filtered.append(entry)
            recordings = filtered
        
        # Ordenar
        if sort_by and recordings:
            try:
                recordings.sort(key=lambda x: x.get(sort_by, 0), reverse=descending)
            except Exception as e:
                logger.warning(f"⚠️ Error ordenando: {e}")
        
        return recordings
    
    def search_recordings(self, 
                         query: str,
                         fields: List[str] = None) -> List[Dict[str, Any]]:
        """Busca grabaciones por texto."""
        if fields is None:
            fields = ['gesture_name', 'action', 'profile', 'notes', 'tags']
        
        query = query.lower()
        results = []
        
        for entry in self.recording_index:
            for field in fields:
                if field in entry:
                    value = str(entry[field]).lower()
                    if query in value:
                        results.append(entry)
                        break
        
        return results
    
    def get_stats(self, detailed: bool = False) -> Dict[str, Any]:
        """Obtiene estadísticas de la grabadora."""
        base_stats = {
            'total_recordings': self.stats['total_recordings'],
            'is_recording': self.is_recording,
            'current_mode': self.recording_mode.value if self.recording_mode else None,
            'current_gesture': self.current_metadata.gesture_name if self.is_recording else None,
            'output_dir': str(self.output_dir.absolute()),
            'config': asdict(self._config)
        }
        
        if detailed:
            # Estadísticas detalladas
            if self.recording_index:
                durations = [r.get('duration', 0) for r in self.recording_index]
                quality_scores = [r.get('quality_score', 0) for r in self.recording_index]
                
                base_stats.update({
                    'avg_duration': np.mean(durations) if durations else 0,
                    'max_duration': np.max(durations) if durations else 0,
                    'min_duration': np.min(durations) if durations else 0,
                    'avg_quality': np.mean(quality_scores) if quality_scores else 0,
                    'quality_distribution': self.stats['quality_distribution'],
                    'recent_recordings': self.recording_index[-5:] if len(self.recording_index) >= 5 else self.recording_index
                })
        
        return base_stats
    
    def export_for_training(self, 
                          output_format: str = "json",
                          include_images: bool = False,
                          quality_filter: Optional[float] = None) -> Optional[Path]:
        """
        Exporta grabaciones para entrenamiento.
        
        Args:
            output_format: Formato de salida ('json', 'numpy', 'csv')
            include_images: Incluir imágenes
            quality_filter: Filtrar por calidad mínima
            
        Returns:
            Ruta del archivo exportado
        """
        try:
            # Filtrar grabaciones
            recordings_to_export = []
            for entry in self.recording_index:
                if quality_filter and entry.get('quality_score', 0) < quality_filter:
                    continue
                
                recording_data = self.load_recording(entry['file'], load_frames=False)
                if recording_data:
                    # Opcional: excluir imágenes si no se requieren
                    if not include_images and 'frames' in recording_data:
                        # Reemplazar frames con metadatos
                        recording_data['frames'] = f"{len(recording_data['frames'])} frames"
                    
                    recordings_to_export.append(recording_data)
            
            if not recordings_to_export:
                logger.warning("⚠️ No hay grabaciones para exportar")
                return None
            
            # Crear archivo de exportación
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_data = {
                'export_timestamp': timestamp,
                'total_recordings': len(recordings_to_export),
                'format_version': '2.0',
                'recordings': recordings_to_export
            }
            
            filename = f"training_export_{timestamp}.{output_format}"
            filepath = self.output_dir / filename
            
            # Guardar según formato
            if output_format == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif output_format == "numpy":
                # Exportar como numpy array (solo características)
                features = []
                for recording in recordings_to_export:
                    if 'features' in recording:
                        features.append(recording['features'])
                
                if features:
                    np.savez_compressed(filepath.with_suffix('.npz'), features=np.array(features))
            
            logger.info(f"📤 Exportadas {len(recordings_to_export)} grabaciones: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error exportando: {e}")
            return None
    
    def clear_recordings(self, 
                        confirm: bool = False,
                        keep_index: bool = False) -> bool:
        """Elimina todas las grabaciones."""
        if not confirm:
            logger.warning("⚠️ Se requiere confirmación para eliminar grabaciones")
            return False
        
        try:
            # Eliminar archivos de grabación
            for file in self.output_dir.glob("*.json"):
                if file.name != "recordings_index.json" or not keep_index:
                    file.unlink()
            
            # Reiniciar estado
            if not keep_index:
                self.recording_index = []
                self.stats = {
                    'total_recordings': 0,
                    'total_frames': 0,
                    'total_duration': 0.0,
                    'last_recording': None,
                    'quality_distribution': {level.value: 0 for level in QualityLevel}
                }
            else:
                # Mantener índice pero limpiar estadísticas
                self.stats.update({
                    'total_recordings': 0,
                    'total_frames': 0,
                    'total_duration': 0.0,
                    'last_recording': None
                })
            
            logger.info("🧹 Grabaciones eliminadas")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error eliminando grabaciones: {e}")
            return False
    
    def backup(self, backup_dir: Union[str, Path] = None) -> Optional[Path]:
        """Crea una copia de seguridad de las grabaciones."""
        try:
            if backup_dir is None:
                backup_dir = self.output_dir.parent / f"{self.output_dir.name}_backup"
            
            backup_dir = Path(backup_dir)
            backup_dir.mkdir(exist_ok=True, parents=True)
            
            import shutil
            for file in self.output_dir.glob("*.json"):
                shutil.copy2(file, backup_dir / file.name)
            
            logger.info(f"💾 Copia de seguridad creada: {backup_dir}")
            return backup_dir
            
        except Exception as e:
            logger.error(f"❌ Error en backup: {e}")
            return None
    
    def cleanup(self):
        """Limpia recursos y finaliza grabaciones pendientes."""
        if self.is_recording:
            logger.info("🛑 Deteniendo grabación pendiente...")
            self.stop_recording(save=False)
        
        # Cerrar conexiones si las hay
        for attr in ['hand_detector', 'arm_detector', 'pose_detector']:
            detector = getattr(self, attr)
            if detector and hasattr(detector, 'cleanup'):
                try:
                    detector.cleanup()
                except Exception as e:
                    logger.debug(f"Error limpiando detector {attr}: {e}")
        
        logger.info("🧹 GestureRecorder limpiado")