"""
🎮 GESTURE PIPELINE - Cerebro del Sistema NYX
=============================================
Coordina todo el flujo: cámara → detección → perfil → ejecución → UI.
"""

import cv2
import time
import threading
import queue
import traceback
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

# Importar PyQt6 para señales
try:
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    # Clases dummy para compatibilidad
    class QObject:
        def __init__(self, *args, **kwargs):
            pass
    
    def pyqtSignal(*args, **kwargs):
        class DummySignal:
            def emit(self, *args, **kwargs):
                pass
            def connect(self, *args, **kwargs):
                pass
        return DummySignal()

logger = logging.getLogger(__name__)


class GesturePipeline(QObject):
    """Pipeline principal del sistema NYX."""
    
    # Señales PyQt6 para comunicación con la UI
    if QT_AVAILABLE:
        gesture_detected = pyqtSignal(dict)           # Gesto detectado
        action_executed = pyqtSignal(dict, dict)      # (acción, resultado)
        frame_available = pyqtSignal(dict)            # Nuevo frame para UI
        status_changed = pyqtSignal(str, dict)        # (estado, datos)
        error_occurred = pyqtSignal(str, str)         # (tipo_error, mensaje)
        profile_changed = pyqtSignal(str, dict)       # (nombre_perfil, info)
        stats_updated = pyqtSignal(dict)              # Estadísticas actualizadas
    else:
        # Placeholders cuando PyQt6 no está disponible
        gesture_detected = None
        action_executed = None
        frame_available = None
        status_changed = None
        error_occurred = None
        profile_changed = None
        stats_updated = None
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el pipeline de NYX.
        
        Args:
            config: Configuración del sistema
        """
        if QT_AVAILABLE:
            super().__init__()
        else:
            QObject.__init__(self)
        
        # Configuración
        self.config = config or {}
        
        # Estado del pipeline
        self.is_running = False
        self._camera_active = False
        self._processing_active = False
        
        # Sistema de perfiles (CRÍTICO)
        self.current_profile_name = None
        self.profile_runtime = None
        
        # Componentes del sistema
        self.hand_detector = None
        self.arm_detector = None
        self.voice_recognizer = None
        self.action_executor = None
        self.config_loader = None
        
        # Colas para comunicación entre hilos
        self.gesture_queue = queue.Queue(maxsize=10)      # Frames para UI
        self.action_queue = queue.Queue()                 # Acciones a ejecutar
        self.voice_queue = queue.Queue(maxsize=5)         # Comandos de voz
        
        # Para acceso thread-safe
        self._latest_frame = None
        self._latest_gestures = []
        self._latest_landmarks = []
        self._frame_lock = threading.RLock()
        self._stats_lock = threading.RLock()
        
        # Estadísticas en tiempo real
        self.stats = {
            'fps': 0,
            'frame_count': 0,
            'gestures_detected': 0,
            'actions_executed': 0,
            'actions_successful': 0,
            'actions_failed': 0,
            'voice_commands': 0,
            'processing_time': 0,
            'detection_time': 0,
            'last_update': time.time(),
            'start_time': time.time()
        }
        
        # Historial
        self.gesture_history = []
        self.action_history = []
        self.voice_history = []
        self.max_history = 100
        
        # Cooldown y debouncing
        self.gesture_cooldowns = {}  # {gesto_name: last_time}
        self.min_gesture_interval = 0.3  # segundos
        
        # Hilos
        self.camera_thread = None
        self.processing_thread = None
        self.voice_thread = None
        self.stats_thread = None
        
        # Temporizador para estadísticas
        self._stats_timer = None
        
        # Inicializar componentes
        self._init_components()
        
        # Emitir señal de inicialización
        self._emit_status("initialized", {"config": self.config})
        
        logger.info("✅ GesturePipeline inicializado para NYX")

    def _init_components(self):
        """Inicializa todos los componentes del sistema."""
        components_loaded = []
        
        try:
            # 1. Config Loader
            try:
                from utils.config_loader import ConfigLoader
                self.config_loader = ConfigLoader()
                components_loaded.append("ConfigLoader")
                logger.debug("✅ ConfigLoader cargado")
            except ImportError as e:
                logger.warning(f"⚠️ No se pudo cargar ConfigLoader: {e}")
                self.config_loader = None
            
            # 2. Hand Detector
            try:
                hand_config = self.config.get('hand_detection', {})
                if hand_config.get('enabled', True):
                    from detectors.hand_detector import HandDetector
                    self.hand_detector = HandDetector(
                        max_num_hands=hand_config.get('max_num_hands', 2),
                        min_detection_confidence=hand_config.get('min_detection_confidence', 0.7),
                        min_tracking_confidence=hand_config.get('min_tracking_confidence', 0.5),
                        model_complexity=hand_config.get('model_complexity', 1)
                    )
                    components_loaded.append("HandDetector")
                    logger.info("✅ HandDetector inicializado")
                else:
                    logger.info("❌ HandDetector deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar HandDetector: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando HandDetector: {e}")
            
            # 3. Arm Detector
            try:
                arm_config = self.config.get('arm_detection', {})
                if arm_config.get('enabled', False):
                    from detectors.arm_detector import ArmDetector
                    self.arm_detector = ArmDetector(
                        min_detection_confidence=arm_config.get('min_detection_confidence', 0.5),
                        min_tracking_confidence=arm_config.get('min_tracking_confidence', 0.5),
                        model_complexity=arm_config.get('model_complexity', 1)
                    )
                    components_loaded.append("ArmDetector")
                    logger.info("✅ ArmDetector inicializado")
                else:
                    logger.info("❌ ArmDetector deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar ArmDetector: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando ArmDetector: {e}")
            
            # 4. Voice Recognizer
            try:
                voice_config = self.config.get('voice_recognition', {})
                if voice_config.get('enabled', True):
                    from core.voice_recognizer import VoiceRecognizer
                    self.voice_recognizer = VoiceRecognizer(
                        activation_word=voice_config.get('activation_word', 'nyx'),
                        language=voice_config.get('language', 'es-ES'),
                        energy_threshold=voice_config.get('energy_threshold', 300),
                        pause_threshold=voice_config.get('pause_threshold', 0.8),
                        dynamic_energy_threshold=voice_config.get('dynamic_energy_threshold', True)
                    )
                    components_loaded.append("VoiceRecognizer")
                    logger.info("✅ VoiceRecognizer inicializado")
                else:
                    logger.info("❌ VoiceRecognizer deshabilitado en configuración")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar VoiceRecognizer: {e}")
            except Exception as e:
                logger.error(f"❌ Error inicializando VoiceRecognizer: {e}")
            
            # 5. Action Executor (CRÍTICO)
            try:
                from core.action_executor import ActionExecutor
                self.action_executor = ActionExecutor(self.config)
                components_loaded.append("ActionExecutor")
                logger.info("✅ ActionExecutor inicializado")
            except ImportError as e:
                logger.error(f"❌ No se pudo importar ActionExecutor: {e}")
                raise Exception("ActionExecutor es crítico para NYX")
            except Exception as e:
                logger.error(f"❌ Error inicializando ActionExecutor: {e}")
                raise
            
            logger.info(f"🎮 Componentes cargados: {', '.join(components_loaded)}")
            
        except Exception as e:
            logger.critical(f"🔥 Error crítico inicializando componentes: {e}")
            self._emit_error("init_error", f"Error inicializando: {str(e)}")
            raise

    def load_profile(self, profile_name: str) -> bool:
        """
        Carga un perfil de configuración.
        
        Args:
            profile_name: Nombre del perfil a cargar
            
        Returns:
            True si se cargó correctamente
        """
        logger.info(f"📥 Cargando perfil: {profile_name}")
        
        try:
            # 1. Obtener datos del perfil
            profile_data = None
            
            if self.config_loader:
                profile_data = self.config_loader.get_profile(profile_name)
            else:
                # Fallback: cargar directamente desde archivo
                import json
                import os
                profiles_dir = os.path.join('src', 'config', 'profiles')
                profile_path = os.path.join(profiles_dir, f"{profile_name}.json")
                
                if os.path.exists(profile_path):
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
            
            if not profile_data:
                error_msg = f"Perfil no encontrado: {profile_name}"
                logger.error(f"❌ {error_msg}")
                self._emit_error("profile_error", error_msg)
                return False
            
            logger.info(f"✅ Perfil encontrado: {profile_name}")
            
            # 2. Crear ProfileRuntime
            try:
                from core.profile_runtime import ProfileRuntime
                self.profile_runtime = ProfileRuntime(profile_data)
                logger.info("✅ ProfileRuntime creado")
            except Exception as e:
                error_msg = f"Error creando ProfileRuntime: {str(e)}"
                logger.error(f"❌ {error_msg}")
                self._emit_error("profile_error", error_msg)
                return False
            
            # 3. Actualizar estado interno
            self.current_profile_name = profile_name
            
            # 4. ✅ CONEXIÓN CRÍTICA: Conectar perfil con ActionExecutor
            if self.action_executor:
                logger.info("🔗 Conectando perfil con ActionExecutor...")
                
                if hasattr(self.action_executor, 'set_profile_runtime'):
                    self.action_executor.set_profile_runtime(self.profile_runtime)
                    logger.info("✅ ProfileRuntime conectado a ActionExecutor")
                else:
                    error_msg = "ActionExecutor no tiene set_profile_runtime"
                    logger.error(f"❌ {error_msg}")
                    self._emit_error("connection_error", error_msg)
                    return False
            
            # 5. Configurar detectores con gestos activos
            if self.hand_detector and hasattr(self.hand_detector, 'set_active_gestures'):
                try:
                    active_gestures = self.profile_runtime.get_all_gestures()
                    self.hand_detector.set_active_gestures(active_gestures)
                    logger.info(f"✅ {len(active_gestures)} gestos configurados en HandDetector")
                except Exception as e:
                    logger.warning(f"⚠️ Error configurando gestos en HandDetector: {e}")
            
            # 6. Configurar voz
            if self.voice_recognizer:
                activation_word = self.config.get('voice_recognition', {}).get('activation_word', 'nyx')
                if hasattr(self.voice_recognizer, 'set_activation_word'):
                    self.voice_recognizer.set_activation_word(activation_word)
                    logger.info(f"✅ Palabra de activación configurada: {activation_word}")
                
                # Configurar comandos de voz del perfil
                if hasattr(self.voice_recognizer, 'set_voice_commands'):
                    voice_commands = self.profile_runtime.get_voice_commands()
                    self.voice_recognizer.set_voice_commands(voice_commands)
                    logger.info(f"✅ {len(voice_commands)} comandos de voz configurados")
            
            # 7. Emitir señales
            profile_info = {
                'name': profile_name,
                'gesture_count': self.profile_runtime.get_gesture_count(),
                'voice_command_count': self.profile_runtime.get_voice_command_count(),
                'enabled_modules': profile_data.get('enabled_modules', []),
                'settings': profile_data.get('settings', {})
            }
            
            self._emit_status("profile_loaded", profile_info)
            
            if self.profile_changed:
                self.profile_changed.emit(profile_name, profile_info)
            
            logger.info(f"✅ Perfil '{profile_name}' cargado exitosamente")
            logger.info(f"📊 Resumen: {profile_info['gesture_count']} gestos, "
                      f"{profile_info['voice_command_count']} comandos voz")
            
            return True
            
        except Exception as e:
            error_msg = f"Error cargando perfil {profile_name}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(traceback.format_exc())
            self._emit_error("profile_error", error_msg)
            return False

    def set_active_profile(self, profile_name: str) -> bool:
        """
        Cambia el perfil activo dinámicamente.
        
        Args:
            profile_name: Nombre del nuevo perfil
            
        Returns:
            True si se cambió correctamente
        """
        logger.info(f"🔄 Cambiando perfil a: {profile_name}")
        
        # Guardar estado actual
        was_running = self.is_running
        
        # Detener si está corriendo
        if was_running:
            self.stop()
        
        # Cargar nuevo perfil
        success = self.load_profile(profile_name)
        
        # Reanudar si estaba corriendo
        if was_running and success:
            self.start()
        
        return success

    def start(self) -> bool:
        """
        Inicia el pipeline completo.
        
        Returns:
            True si se inició correctamente
        """
        if self.is_running:
            logger.warning("⚠️ Pipeline ya está en ejecución")
            return True
        
        logger.info("▶️ Iniciando GesturePipeline...")
        
        try:
            # 1. Verificar componentes críticos
            if not self.action_executor:
                error_msg = "ActionExecutor no inicializado"
                logger.error(f"❌ {error_msg}")
                self._emit_error("start_error", error_msg)
                return False
            
            if self.profile_runtime is None:
                # Cargar perfil por defecto
                default_profile = self.config.get('active_profile', 'gamer')
                logger.info(f"🔄 Cargando perfil por defecto: {default_profile}")
                if not self.load_profile(default_profile):
                    error_msg = f"No se pudo cargar perfil por defecto: {default_profile}"
                    logger.error(f"❌ {error_msg}")
                    self._emit_error("start_error", error_msg)
                    return False
            
            # 2. Iniciar ActionExecutor
            try:
                self.action_executor.start()
                logger.info("✅ ActionExecutor iniciado")
            except Exception as e:
                logger.error(f"❌ Error iniciando ActionExecutor: {e}")
            
            # 3. Iniciar VoiceRecognizer
            if self.voice_recognizer:
                try:
                    self.voice_recognizer.start()
                    logger.info("✅ VoiceRecognizer iniciado")
                except Exception as e:
                    logger.error(f"❌ Error iniciando VoiceRecognizer: {e}")
            
            # 4. Marcar como corriendo
            self.is_running = True
            self._processing_active = True
            
            # 5. Iniciar hilos
            # Hilo de cámara
            self.camera_thread = threading.Thread(
                target=self._camera_loop,
                daemon=True,
                name="NYX-CameraThread"
            )
            self.camera_thread.start()
            logger.info("✅ Hilo de cámara iniciado")
            
            # Hilo de procesamiento
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="NYX-ProcessingThread"
            )
            self.processing_thread.start()
            logger.info("✅ Hilo de procesamiento iniciado")
            
            # Hilo de voz (si está disponible)
            if self.voice_recognizer:
                self.voice_thread = threading.Thread(
                    target=self._voice_loop,
                    daemon=True,
                    name="NYX-VoiceThread"
                )
                self.voice_thread.start()
                logger.info("✅ Hilo de voz iniciado")
            
            # 6. Iniciar temporizador de estadísticas
            self._start_stats_timer()
            
            # 7. Emitir señal de inicio
            self._emit_status("started", {
                'profile': self.current_profile_name,
                'components': {
                    'camera': self.camera_thread.is_alive() if self.camera_thread else False,
                    'processing': self.processing_thread.is_alive() if self.processing_thread else False,
                    'voice': self.voice_thread.is_alive() if self.voice_thread else False
                }
            })
            
            logger.info("✅ GesturePipeline iniciado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error iniciando pipeline: {e}")
            logger.error(traceback.format_exc())
            self._emit_error("start_error", str(e))
            self.is_running = False
            return False

    def stop(self):
        """Detiene el pipeline de manera controlada."""
        if not self.is_running:
            return
        
        logger.info("⏹️ Deteniendo GesturePipeline...")
        
        # 1. Marcar como detenido
        self.is_running = False
        self._camera_active = False
        self._processing_active = False
        
        # 2. Detener temporizador de estadísticas
        self._stop_stats_timer()
        
        # 3. Detener VoiceRecognizer
        if self.voice_recognizer:
            try:
                self.voice_recognizer.stop()
                logger.info("✅ VoiceRecognizer detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo VoiceRecognizer: {e}")
        
        # 4. Detener ActionExecutor
        if self.action_executor:
            try:
                self.action_executor.stop()
                logger.info("✅ ActionExecutor detenido")
            except Exception as e:
                logger.error(f"❌ Error deteniendo ActionExecutor: {e}")
        
        # 5. Esperar a que terminen los hilos
        threads = [
            (self.camera_thread, "cámara"),
            (self.processing_thread, "procesamiento"),
            (self.voice_thread, "voz")
        ]
        
        for thread, name in threads:
            if thread and thread.is_alive():
                logger.info(f"⏳ Esperando hilo de {name}...")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    logger.warning(f"⚠️ Hilo de {name} no terminó correctamente")
                else:
                    logger.info(f"✅ Hilo de {name} detenido")
        
        # 6. Limpiar colas
        self._clear_queues()
        
        # 7. Emitir señal de detención
        self._emit_status("stopped", {
            'uptime': time.time() - self.stats['start_time']
        })
        
        logger.info("✅ GesturePipeline detenido correctamente")

    def _camera_loop(self):
        """Bucle principal de captura de cámara."""
        logger.info("🎥 Iniciando bucle de cámara...")
        
        camera_config = self.config.get('camera', {})
        device_id = camera_config.get('device_id', 0)
        width = camera_config.get('width', 1280)
        height = camera_config.get('height', 720)
        fps_target = camera_config.get('fps', 30)
        mirror = camera_config.get('mirror', True)
        
        # Intentar abrir la cámara
        cap = None
        retry_count = 0
        max_retries = 3
        
        while self.is_running and retry_count < max_retries:
            try:
                cap = cv2.VideoCapture(device_id)
                if cap.isOpened():
                    # Configurar propiedades
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    cap.set(cv2.CAP_PROP_FPS, fps_target)
                    
                    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    self._camera_active = True
                    
                    logger.info(f"📷 Cámara {device_id} abierta: "
                              f"{actual_width}x{actual_height} @ {actual_fps:.1f} FPS")
                    
                    self._emit_status("camera_active", {
                        'device_id': device_id,
                        'resolution': f"{actual_width}x{actual_height}",
                        'fps': actual_fps,
                        'mirror': mirror
                    })
                    break
                else:
                    logger.warning(f"⚠️ No se pudo abrir cámara {device_id}, intentando alternativa...")
                    device_id = (device_id + 1) % 3
                    retry_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error abriendo cámara: {e}")
                retry_count += 1
            
            if retry_count < max_retries:
                time.sleep(1)
        
        if not cap or not cap.isOpened():
            error_msg = f"No se pudo abrir ninguna cámara después de {max_retries} intentos"
            logger.error(f"❌ {error_msg}")
            self._emit_error("camera_error", error_msg)
            return
        
        # Control de FPS
        frame_interval = 1.0 / fps_target if fps_target > 0 else 0.033
        last_frame_time = time.time()
        frame_count = 0
        fps_timer = time.time()
        
        # Bucle principal de captura
        while self.is_running and self._camera_active and cap.isOpened():
            current_time = time.time()
            
            # Control de FPS
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue
            
            last_frame_time = current_time
            
            # Capturar frame
            ret, frame = cap.read()
            if not ret:
                logger.warning("⚠️ Error leyendo frame de cámara")
                time.sleep(0.05)
                continue
            
            # Espejar si está configurado
            if mirror:
                frame = cv2.flip(frame, 1)
            
            # Procesar frame
            try:
                start_process = time.time()
                
                # Detección
                processed_data = self._process_frame(frame)
                processing_time = time.time() - start_process
                
                with self._stats_lock:
                    self.stats['processing_time'] = processing_time * 0.1 + self.stats['processing_time'] * 0.9
                
                # Guardar frame más reciente
                with self._frame_lock:
                    self._latest_frame = processed_data['image']
                    self._latest_gestures = processed_data['gestures']
                    self._latest_landmarks = processed_data['landmarks']
                
                # Preparar datos para UI
                frame_data = {
                    'type': 'frame',
                    'image': processed_data['image'],
                    'gestures': processed_data['gestures'],
                    'landmarks': processed_data['landmarks'],
                    'timestamp': current_time,
                    'processing_time': processing_time,
                    'stats': self._get_current_stats()
                }
                
                # Enviar a la cola para UI
                try:
                    self.gesture_queue.put_nowait(frame_data)
                except queue.Full:
                    # Descartar frame más viejo
                    try:
                        self.gesture_queue.get_nowait()
                        self.gesture_queue.put_nowait(frame_data)
                    except queue.Empty:
                        pass
                
                # Emitir señal si hay suscriptores
                if self.frame_available:
                    self.frame_available.emit(frame_data)
                
                # Actualizar estadísticas de FPS
                frame_count += 1
                if current_time - fps_timer >= 1.0:
                    with self._stats_lock:
                        self.stats['fps'] = frame_count
                        self.stats['frame_count'] += frame_count
                    frame_count = 0
                    fps_timer = current_time
                
                # Procesar cola de voz
                self._process_voice_queue()
                
            except Exception as e:
                logger.error(f"❌ Error procesando frame: {e}")
                logger.error(traceback.format_exc())
        
        # Liberar recursos
        cap.release()
        self._camera_active = False
        cv2.destroyAllWindows()
        
        logger.info("🎥 Bucle de cámara terminado")

    def _process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Procesa un frame individual para detección.
        
        Args:
            frame: Frame de imagen BGR
            
        Returns:
            Diccionario con resultados
        """
        gestures = []
        landmarks = []
        processed_frame = frame.copy()
        
        # 1. Detección de manos
        if self.hand_detector and self.config.get('hand_detection', {}).get('enabled', True):
            try:
                start_detect = time.time()
                results = self.hand_detector.detect(frame)
                detect_time = time.time() - start_detect
                
                with self._stats_lock:
                    self.stats['detection_time'] = detect_time * 0.1 + self.stats['detection_time'] * 0.9
                
                if results.get('success', False):
                    # Obtener imagen procesada
                    if results.get('image') is not None:
                        processed_frame = results['image']
                    
                    # Procesar gestos detectados
                    if results.get('gestures'):
                        for gesture_data in results['gestures']:
                            # Validar confianza mínima
                            confidence = gesture_data.get('confidence', 0)
                            min_confidence = self.config.get('hand_detection', {}).get('min_detection_confidence', 0.5)
                            
                            if confidence >= min_confidence:
                                # Completar datos del gesto
                                gesture_data.update({
                                    'timestamp': time.time(),
                                    'source': 'hand',
                                    'detection_time': detect_time
                                })
                                
                                gestures.append(gesture_data)
                                
                                # Manejar gesto
                                self._handle_detected_gesture(gesture_data)
                    
                    # Obtener landmarks
                    if results.get('landmarks'):
                        landmarks.extend(results['landmarks'])
                        
            except Exception as e:
                logger.error(f"❌ Error en detección de manos: {e}")
        
        # 2. Detección de brazos (si está habilitado)
        if self.arm_detector and self.config.get('arm_detection', {}).get('enabled', False):
            try:
                results = self.arm_detector.detect(frame)
                
                if results.get('success', False):
                    # Procesar gestos de brazos
                    if results.get('gestures'):
                        for gesture_data in results['gestures']:
                            gesture_data.update({
                                'timestamp': time.time(),
                                'source': 'arm'
                            })
                            
                            gestures.append(gesture_data)
                            
                            # Manejar gesto
                            self._handle_detected_gesture(gesture_data)
                    
                    # Obtener landmarks de brazos
                    if results.get('landmarks'):
                        landmarks.extend(results['landmarks'])
                        
            except Exception as e:
                logger.error(f"❌ Error en detección de brazos: {e}")
        
        # 3. Dibujar información en el frame
        processed_frame = self._draw_frame_info(processed_frame, gestures, landmarks)
        
        return {
            'image': processed_frame,
            'gestures': gestures,
            'landmarks': landmarks,
            'success': len(gestures) > 0,
            'timestamp': time.time()
        }

    def _handle_detected_gesture(self, gesture_data: Dict):
        """
        Maneja un gesto recién detectado.
        
        Args:
            gesture_data: Datos del gesto detectado
        """
        gesture_name = gesture_data.get('gesture')
        hand_type = gesture_data.get('hand', 'unknown')
        source = gesture_data.get('source', 'unknown')
        confidence = gesture_data.get('confidence', 0)
        
        # 1. Verificar cooldown
        gesture_key = f"{gesture_name}_{hand_type}_{source}"
        current_time = time.time()
        last_time = self.gesture_cooldowns.get(gesture_key, 0)
        
        if current_time - last_time < self.min_gesture_interval:
            return
        
        # 2. Actualizar cooldown
        self.gesture_cooldowns[gesture_key] = current_time
        
        # 3. Actualizar estadísticas
        with self._stats_lock:
            self.stats['gestures_detected'] += 1
        
        # 4. Agregar al historial
        self.gesture_history.append(gesture_data.copy())
        if len(self.gesture_history) > self.max_history:
            self.gesture_history.pop(0)
        
        # 5. Emitir señal
        if self.gesture_detected:
            self.gesture_detected.emit(gesture_data)
        
        # 6. Ejecutar acción si hay ActionExecutor y ProfileRuntime
        if self.action_executor and self.profile_runtime:
            try:
                # Obtener acción del gesto
                action_result = self.action_executor.execute_gesture(
                    gesture_name=gesture_name,
                    source=source,
                    hand_type=hand_type,
                    confidence=confidence
                )
                
                # Registrar en historial de acciones
                if action_result:
                    self.action_history.append({
                        'gesture': gesture_data,
                        'action_result': action_result,
                        'timestamp': time.time()
                    })
                    
                    if len(self.action_history) > self.max_history:
                        self.action_history.pop(0)
                    
                    # Actualizar estadísticas
                    with self._stats_lock:
                        self.stats['actions_executed'] += 1
                        if action_result.get('success', False):
                            self.stats['actions_successful'] += 1
                        else:
                            self.stats['actions_failed'] += 1
                    
                    # Emitir señal de acción ejecutada
                    if self.action_executed:
                        self.action_executed.emit(gesture_data, action_result)
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando acción para gesto {gesture_name}: {e}")

    def _draw_frame_info(self, frame: np.ndarray, gestures: List[Dict], 
                        landmarks: List[Dict]) -> np.ndarray:
        """
        Dibuja información en el frame para visualización.
        
        Args:
            frame: Imagen original
            gestures: Lista de gestos detectados
            landmarks: Lista de landmarks
            
        Returns:
            Imagen con información dibujada
        """
        h, w = frame.shape[:2]
        
        # Crear overlay para información
        overlay = frame.copy()
        
        # 1. Barra superior
        cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # 2. Información del sistema
        # Nombre y FPS
        fps_text = f"NYX | FPS: {self.stats['fps']}"
        cv2.putText(frame, fps_text, (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Perfil actual
        profile_text = f"Perfil: {self.current_profile_name or 'Ninguno'}"
        cv2.putText(frame, profile_text, (w - 200, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 3. Información de gestos
        if gestures:
            y_offset = 60
            for i, gesture in enumerate(gestures[:3]):  # Mostrar máximo 3
                name = gesture.get('gesture', 'Desconocido')
                hand = gesture.get('hand', '').capitalize()
                conf = gesture.get('confidence', 0)
                
                gesture_text = f"{hand} {name}: {conf:.1%}"
                color = (0, 200, 255) if conf > 0.7 else (200, 200, 200)
                
                cv2.putText(frame, gesture_text, (10, y_offset + i * 25), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1)
        
        # 4. Estadísticas en esquina inferior
        stats_text = f"Gestos: {self.stats['gestures_detected']} | "
        stats_text += f"Acciones: {self.stats['actions_executed']}"
        cv2.putText(frame, stats_text, (10, h - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        return frame

    def _voice_loop(self):
        """Bucle para procesamiento de voz."""
        if not self.voice_recognizer:
            return
        
        logger.info("🎤 Iniciando bucle de voz...")
        
        while self.is_running and self._processing_active:
            try:
                # Escuchar comandos
                command = self.voice_recognizer.listen()
                
                if command:
                    # Procesar comando
                    self._process_voice_command(command)
                    
            except Exception as e:
                logger.error(f"❌ Error en bucle de voz: {e}")
                time.sleep(0.1)
        
        logger.info("🎤 Bucle de voz terminado")

    def _process_voice_command(self, command_data: Dict):
        """
        Procesa un comando de voz.
        
        Args:
            command_data: Datos del comando de voz
        """
        command_text = command_data.get('text', '').lower().strip()
        
        if not command_text:
            return
        
        logger.info(f"🎤 Comando de voz detectado: '{command_text}'")
        
        # 1. Agregar al historial
        self.voice_history.append(command_data.copy())
        if len(self.voice_history) > self.max_history:
            self.voice_history.pop(0)
        
        # 2. Actualizar estadísticas
        with self._stats_lock:
            self.stats['voice_commands'] += 1
        
        # 3. Ejecutar acción si hay ActionExecutor
        if self.action_executor:
            try:
                action_result = self.action_executor.execute_voice(command_text)
                
                # Registrar resultado
                if action_result:
                    self.action_history.append({
                        'voice_command': command_data,
                        'action_result': action_result,
                        'timestamp': time.time()
                    })
                    
                    # Emitir señal si se ejecutó
                    if action_result.get('success', False) and self.action_executed:
                        self.action_executed.emit(command_data, action_result)
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando comando de voz: {e}")

    def _process_voice_queue(self):
        """Procesa comandos de voz en la cola."""
        try:
            while not self.voice_queue.empty():
                command = self.voice_queue.get_nowait()
                self._process_voice_command(command)
                self.voice_queue.task_done()
        except queue.Empty:
            pass

    def _processing_loop(self):
        """Bucle de procesamiento de acciones en cola."""
        logger.info("🔄 Iniciando bucle de procesamiento...")
        
        while self.is_running and self._processing_active:
            try:
                # 1. Procesar acciones de la cola
                if not self.action_queue.empty():
                    action = self.action_queue.get(timeout=0.01)
                    
                    if action and self.action_executor:
                        # Ejecutar acción
                        result = self.action_executor.execute(action)
                        
                        # Emitir señal
                        if self.action_executed:
                            self.action_executed.emit(action, result)
                    
                    self.action_queue.task_done()
                
                # 2. Pequeña pausa para no consumir mucho CPU
                time.sleep(0.001)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en bucle de procesamiento: {e}")
        
        logger.info("🔄 Bucle de procesamiento terminado")

    def _start_stats_timer(self):
        """Inicia el temporizador para actualizar estadísticas."""
        if QT_AVAILABLE and self.stats_updated:
            self._stats_timer = QTimer()
            self._stats_timer.timeout.connect(self._update_stats_display)
            self._stats_timer.start(1000)  # Actualizar cada segundo

    def _stop_stats_timer(self):
        """Detiene el temporizador de estadísticas."""
        if self._stats_timer:
            self._stats_timer.stop()
            self._stats_timer = None

    def _update_stats_display(self):
        """Actualiza y emite estadísticas para la UI."""
        stats = self._get_current_stats()
        
        if self.stats_updated:
            self.stats_updated.emit(stats)

    def _get_current_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas actuales."""
        with self._stats_lock:
            stats_copy = self.stats.copy()
            stats_copy.update({
                'uptime': time.time() - stats_copy['start_time'],
                'gesture_history_size': len(self.gesture_history),
                'action_history_size': len(self.action_history),
                'voice_history_size': len(self.voice_history),
                'action_queue_size': self.action_queue.qsize(),
                'gesture_queue_size': self.gesture_queue.qsize(),
                'voice_queue_size': self.voice_queue.qsize(),
                'is_running': self.is_running,
                'camera_active': self._camera_active,
                'processing_active': self._processing_active,
                'current_profile': self.current_profile_name,
                'has_profile_runtime': self.profile_runtime is not None,
                'has_action_executor': self.action_executor is not None
            })
        
        return stats_copy

    def _clear_queues(self):
        """Limpia todas las colas."""
        for q in [self.gesture_queue, self.action_queue, self.voice_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except (queue.Empty, queue.Full):
                    break

    def _emit_status(self, status_type: str, data: Dict = None):
        """Emite señal de cambio de estado."""
        if self.status_changed:
            self.status_changed.emit(status_type, data or {})

    def _emit_error(self, error_type: str, message: str):
        """Emite señal de error."""
        if self.error_occurred:
            self.error_occurred.emit(error_type, message)
        logger.error(f"🚨 [{error_type}] {message}")

    # ========== MÉTODOS PÚBLICOS PARA UI ==========

    def get_latest_frame(self) -> Optional[Dict]:
        """
        Obtiene el último frame procesado.
        
        Returns:
            Diccionario con frame y datos o None
        """
        try:
            return self.gesture_queue.get_nowait()
        except queue.Empty:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return {
                        'type': 'frame',
                        'image': self._latest_frame,
                        'gestures': self._latest_gestures,
                        'landmarks': self._latest_landmarks,
                        'timestamp': time.time(),
                        'stats': self._get_current_stats()
                    }
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pipeline."""
        return self._get_current_stats()

    def get_gesture_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de gestos."""
        return self.gesture_history[-limit:] if self.gesture_history else []

    def get_action_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de acciones."""
        return self.action_history[-limit:] if self.action_history else []

    def get_voice_history(self, limit: int = 10) -> List[Dict]:
        """Obtiene historial de comandos de voz."""
        return self.voice_history[-limit:] if self.voice_history else []

    def update_config(self, new_config: Dict):
        """Actualiza configuración dinámicamente."""
        logger.info("⚙️ Actualizando configuración...")
        
        # Actualizar configuración
        for key, value in new_config.items():
            if key in self.config and isinstance(self.config[key], dict) and isinstance(value, dict):
                self.config[key].update(value)
            else:
                self.config[key] = value
        
        # Reiniciar componentes si es necesario
        needs_restart = False
        
        if 'hand_detection' in new_config or 'arm_detection' in new_config:
            logger.info("🔄 Reiniciando detectores...")
            self._init_detectors()
            needs_restart = True
        
        if 'voice_recognition' in new_config and self.voice_recognizer:
            logger.info("🔄 Actualizando VoiceRecognizer...")
            try:
                self.voice_recognizer.update_config(new_config['voice_recognition'])
            except:
                pass
        
        # Reiniciar si es necesario
        was_running = self.is_running
        if needs_restart and was_running:
            self.stop()
            self.start()
        
        self._emit_status("config_updated", new_config)
        logger.info("✅ Configuración actualizada")

    def _init_detectors(self):
        """Reinicializa detectores."""
        # Hand Detector
        try:
            hand_config = self.config.get('hand_detection', {})
            if hand_config.get('enabled', True):
                from detectors.hand_detector import HandDetector
                
                if self.hand_detector:
                    if hasattr(self.hand_detector, 'release'):
                        self.hand_detector.release()
                
                self.hand_detector = HandDetector(
                    max_num_hands=hand_config.get('max_num_hands', 2),
                    min_detection_confidence=hand_config.get('min_detection_confidence', 0.7),
                    min_tracking_confidence=hand_config.get('min_tracking_confidence', 0.5),
                    model_complexity=hand_config.get('model_complexity', 1)
                )
                
                # Reconfigurar gestos activos si hay perfil
                if self.profile_runtime and hasattr(self.hand_detector, 'set_active_gestures'):
                    active_gestures = self.profile_runtime.get_all_gestures()
                    self.hand_detector.set_active_gestures(active_gestures)
        except Exception as e:
            logger.error(f"❌ Error reinicializando HandDetector: {e}")

    def get_component_status(self) -> Dict[str, Any]:
        """Obtiene estado de todos los componentes."""
        return {
            'hand_detector': self.hand_detector is not None,
            'arm_detector': self.arm_detector is not None,
            'voice_recognizer': self.voice_recognizer is not None,
            'action_executor': self.action_executor is not None,
            'config_loader': self.config_loader is not None,
            'profile_runtime': self.profile_runtime is not None,
            'current_profile': self.current_profile_name,
            'is_running': self.is_running,
            'camera_active': self._camera_active,
            'processing_active': self._processing_active
        }

    def execute_test_action(self, action_type: str, command: str) -> Dict[str, Any]:
        """
        Ejecuta una acción de prueba (para debugging).
        
        Args:
            action_type: Tipo de acción (keyboard, mouse, bash, window)
            command: Comando a ejecutar
            
        Returns:
            Resultado de la ejecución
        """
        if not self.action_executor:
            return {'success': False, 'error': 'ActionExecutor no disponible'}
        
        test_action = {
            'type': action_type,
            'command': command,
            'description': f'Prueba: {action_type} - {command}',
            'timestamp': time.time(),
            'test': True
        }
        
        return self.action_executor.execute(test_action)

    def cleanup(self):
        """Limpia todos los recursos."""
        logger.info("🧹 Limpiando GesturePipeline...")
        
        # Detener pipeline
        self.stop()
        
        # Liberar detectores
        if self.hand_detector and hasattr(self.hand_detector, 'release'):
            try:
                self.hand_detector.release()
            except:
                pass
        
        if self.arm_detector and hasattr(self.arm_detector, 'release'):
            try:
                self.arm_detector.release()
            except:
                pass
        
        # Limpiar controladores
        if self.action_executor and hasattr(self.action_executor, 'cleanup'):
            try:
                self.action_executor.cleanup()
            except:
                pass
        
        # Limpiar datos
        self._clear_queues()
        
        with self._frame_lock:
            self._latest_frame = None
            self._latest_gestures = []
            self._latest_landmarks = []
        
        self.gesture_history.clear()
        self.action_history.clear()
        self.voice_history.clear()
        self.gesture_cooldowns.clear()
        
        logger.info("✅ GesturePipeline limpiado correctamente")


# Ejemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuración de prueba
    test_config = {
        'active_profile': 'gamer',
        'camera': {
            'device_id': 0,
            'width': 640,
            'height': 480,
            'fps': 30,
            'mirror': True
        },
        'hand_detection': {
            'enabled': True,
            'max_num_hands': 2,
            'min_detection_confidence': 0.7,
            'min_tracking_confidence': 0.5
        },
        'voice_recognition': {
            'enabled': False  # Desactivado para prueba
        }
    }
    
    # Crear pipeline
    print("🎮 Creando GesturePipeline...")
    pipeline = GesturePipeline(test_config)
    
    # Cargar perfil
    print("📥 Cargando perfil gamer...")
    if pipeline.load_profile('gamer'):
        print("✅ Perfil cargado")
        
        # Mostrar estado
        status = pipeline.get_component_status()
        print(f"📊 Estado componentes: {status}")
        
        # Iniciar pipeline
        print("▶️ Iniciando pipeline (5 segundos)...")
        pipeline.start()
        
        # Esperar un poco
        import time
        time.sleep(5)
        
        # Obtener estadísticas
        stats = pipeline.get_stats()
        print(f"\n📊 Estadísticas después de 5 segundos:")
        print(f"  FPS: {stats['fps']}")
        print(f"  Frames procesados: {stats['frame_count']}")
        print(f"  Gestos detectados: {stats['gestures_detected']}")
        
        # Detener
        print("\n⏹️ Deteniendo pipeline...")
        pipeline.stop()
        
        # Limpiar
        pipeline.cleanup()
        print("✅ Prueba completada")
    else:
        print("❌ Error cargando perfil")


# En gesture_pipeline.py, después de la clase GesturePipeline, agregar:

"""
# Importar el nuevo integrador
from .gesture_integrator import GestureIntegrator

# Modificar el método __init__ de GesturePipeline para incluir:
class GesturePipeline:
    def __init__(self, config):
        # ... código existente ...
        
        # Inicializar integrador de gestos
        self.gesture_integrator = GestureIntegrator(config)
        
        # Conectar integrador con pipeline
        self.gesture_integrator.set_pipeline(self)
        
        # ... resto del código ...
    
    def start(self):
        Inicia el pipeline y todos sus componentes
        # ... código existente ...
        
        # Iniciar integrador
        if hasattr(self, 'gesture_integrator'):
            self.gesture_integrator.start()
        
        # ... resto del código ...
    
    def stop(self):
        Detiene el pipeline y todos sus componentes
        # ... código existente ...
        
        # Detener integrador
        if hasattr(self, 'gesture_integrator') and self.gesture_integrator.running:
            self.gesture_integrator.stop()
        
        # ... resto del código ...
    
    def register_detector(self, name: str, detector):
        Registra un detector en el pipeline
        if hasattr(self, 'gesture_integrator'):
            self.gesture_integrator.register_detector(name, detector)
        else:
            logger.warning("❌ GestureIntegrator no inicializado")
    
    def register_interpreter(self, name: str, interpreter):
        Registra un intérprete en el pipeline.
        if hasattr(self, 'gesture_integrator'):
            self.gesture_integrator.register_interpreter(name, interpreter)
        else:
            logger.warning("❌ GestureIntegrator no inicializado")
    
    def process_frame(self, frame):
        
        Procesa un frame a través del pipeline.
        
        Args:
            frame: Frame de imagen a procesar
        # ... procesamiento existente ...
        
        # También enviar al integrador
        if hasattr(self, 'gesture_integrator') and self.gesture_integrator.running:
            frame_data = {
                'frame_id': self.frame_count,
                'timestamp': time.time()
            }
            self.gesture_integrator.process_frame(frame, frame_data)
        
        # ... resto del código ...
    
    def load_profile(self, profile_data: Dict):
        # ... código existente para profile_runtime ...
        
        # También cargar en el integrador
        if hasattr(self, 'gesture_integrator'):
            self.gesture_integrator.load_profile(profile_data)
        
        # ... resto del código ...
    
    def get_actions(self):
       Obtiene acciones pendientes del integrador.
        if hasattr(self, 'gesture_integrator'):
            return self.gesture_integrator.get_actions()
        return []        
"""

"""
Usar geture integrador???
# 1. Crear instancia
integrator = GestureIntegrator(config)

# 2. Registrar componentes
integrator.register_detector('arm', arm_detector)
integrator.register_detector('hand', hand_detector)
integrator.register_interpreter('arm', arm_interpreter)
integrator.register_interpreter('hand', hand_interpreter)

# 3. Conectar con otros componentes
integrator.set_profile_runtime(profile_runtime)
integrator.set_action_executor(action_executor)  # Opcional
integrator.set_pipeline(pipeline)  # Opcional

# 4. Cargar perfil
integrator.load_profile(profile_data)

# 5. Iniciar
integrator.start()

# 6. Usar
integrator.process_frame(frame)  # Para detectores de imagen
# O
integrator.process_detection('voice', voice_data)  # Para voz

# 7. Obtener acciones para ejecutar
actions = integrator.get_actions()

# 8. Monitorear
stats = integrator.get_stats()
history = integrator.get_gesture_history()

# 9. Detener
integrator.stop()
"""


"""
del main
# Al inicio del archivo:
from .gesture_integrator import GestureIntegrator

# En la clase GesturePipeline.__init__:
def __init__(self, config):
    # ... código existente ...
    
    # Inicializar GestureIntegrator
    self.gesture_integrator = None  # Se asignará desde main.py
    
    # Conectar con otros componentes
    if hasattr(self, 'action_executor'):
        self.action_executor.set_logger(self.logger)
    
    # ... resto del código ...

# Agregar método para recibir el integrador
def set_gesture_integrator(self, integrator):
    self.gesture_integrator = integrator
    integrator.set_pipeline(self)
    integrator.set_profile_runtime(self.profile_runtime)
    if hasattr(self, 'action_executor'):
        integrator.set_action_executor(self.action_executor)
"""
