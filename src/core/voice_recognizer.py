"""
🎤 VOICE RECOGNIZER - Reconocimiento de Voz para NYX
====================================================
Módulo para reconocimiento de comandos de voz integrado con perfiles de NYX.
Escucha comandos predefinidos y los envía al ActionExecutor.
"""

import threading
import queue
import time
import logging
import re
import json
import os
import wave
import tempfile
from typing import Dict, Optional, Callable, List, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Estados del reconocedor de voz para NYX."""
    INITIALIZING = "initializing"  # Inicializando
    READY = "ready"               # Listo para escuchar
    LISTENING = "listening"       # Escuchando activamente
    PROCESSING = "processing"     # Procesando comando
    ERROR = "error"              # Error en el sistema
    DISABLED = "disabled"        # Deshabilitado por configuración
    CALIBRATING = "calibrating"  # Calibrando micrófono
    SLEEPING = "sleeping"        # En modo de bajo consumo


@dataclass
class VoiceCommand:
    """Estructura para comandos de voz."""
    id: str
    text: str
    action: str
    command: str
    description: str
    enabled: bool = True
    requires_activation: bool = True
    confidence_threshold: float = 0.6
    cooldown: float = 0.0  # Tiempo entre ejecuciones
    last_executed: float = 0.0


class VoiceStats:
    """Maneja estadísticas del reconocedor de voz."""
    
    def __init__(self):
        self.total_commands = 0
        self.valid_commands = 0
        self.activation_detected = 0
        self.processing_errors = 0
        self.audio_errors = 0
        self.false_positives = 0
        self.response_times = []
        self.start_time = time.time()
        self.last_command_time = 0
        self.commands_by_type = {}
        
    def add_response_time(self, response_time: float):
        """Agrega tiempo de respuesta."""
        self.response_times.append(response_time)
        if len(self.response_times) > 100:  # Mantener últimos 100
            self.response_times.pop(0)
    
    def get_average_response_time(self) -> float:
        """Obtiene tiempo promedio de respuesta."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            'total_commands': self.total_commands,
            'valid_commands': self.valid_commands,
            'activation_detected': self.activation_detected,
            'processing_errors': self.processing_errors,
            'audio_errors': self.audio_errors,
            'false_positives': self.false_positives,
            'average_response_time': self.get_average_response_time(),
            'last_command_time': self.last_command_time,
            'uptime_seconds': time.time() - self.start_time,
            'commands_by_type': self.commands_by_type.copy()
        }


class VoiceRecognizer:
    """Reconocedor de comandos de voz integrado con NYX."""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa el reconocedor de voz para NYX.
        
        Args:
            config: Configuración del sistema desde system.yaml
        """
        self.config = config or {}
        
        # Configuración de voz desde NYX
        voice_config = self.config.get('voice_recognition', {})
        self.activation_word = voice_config.get('activation_word', 'nyx').lower()
        self.language = voice_config.get('language', 'es-ES')
        self.energy_threshold = voice_config.get('energy_threshold', 300)
        self.pause_threshold = voice_config.get('pause_threshold', 0.8)
        self.dynamic_energy_threshold = voice_config.get('dynamic_energy_threshold', True)
        self.enabled = voice_config.get('enabled', True)
        self.auto_start = voice_config.get('auto_start', False)
        self.continuous_listening = voice_config.get('continuous_listening', True)
        self.silence_timeout = voice_config.get('silence_timeout', 10.0)  # Segundos sin actividad
        self.min_confidence = voice_config.get('min_confidence', 0.6)
        self.save_audio_samples = voice_config.get('save_audio_samples', False)
        self.audio_samples_dir = voice_config.get('audio_samples_dir', './voice_samples')
        
        # Comandos de voz del perfil activo
        self.voice_commands: Dict[str, VoiceCommand] = {}  # Comandos registrados
        self.command_patterns: List[tuple] = []    # Patrones para matching
        self.activation_patterns: set = set()      # Patrones de activación
        
        # Estado del sistema
        self.state = VoiceState.INITIALIZING
        self.is_running = False
        self.microphone_available = False
        self.listening_enabled = False  # EMERGENCY: ALWAYS ON
        self.last_activity_time = time.time()
        
        # Colas para comunicación con NYX
        self.command_queue = queue.Queue(maxsize=20)      # Comandos detectados
        self.action_queue = queue.Queue(maxsize=20)       # Acciones para ejecutar
        self.callbacks = {
            'on_command': [],
            'on_activation': [],
            'on_error': [],
            'on_state_change': [],
            'on_audio_captured': []
        }
        
        # Hilos
        self.listening_thread = None
        self.processing_thread = None
        self.monitoring_thread = None
        
        # Módulos de speech recognition (lazy loading)
        self.recognizer = None
        self.microphone = None
        self.speech_recognition_available = False
        
        # Estadísticas
        self.stats = VoiceStats()
        
        # Calibración
        self.calibrated = False
        self.calibration_samples = 0
        self.background_noise_level = 0
        
        # Cooldown de comandos
        self.command_cooldowns: Dict[str, float] = {}
        
        # Cache para reconocimiento
        self.recognition_cache: Dict[str, Dict] = {}
        self.cache_max_size = 100
        
        # Inicializar módulos
        self._init_speech_modules()
        
        # Crear directorio para muestras de audio si es necesario
        if self.save_audio_samples:
            os.makedirs(self.audio_samples_dir, exist_ok=True)
        
        logger.info(f"✅ VoiceRecognizer inicializado para NYX (activación: '{self.activation_word}')")
    
    def _init_speech_modules(self) -> bool:
        """Inicializa módulos de reconocimiento de voz."""
        try:
            import speech_recognition as sr
            import pyaudio
            
            self.speech_recognition_available = True
            logger.debug("✅ Módulos de speech recognition disponibles")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Módulos de speech recognition no disponibles: {e}")
            self.speech_recognition_available = False
            self.state = VoiceState.DISABLED
            return False
        except Exception as e:
            logger.error(f"❌ Error verificando módulos de voz: {e}")
            self.speech_recognition_available = False
            return False
    
    def set_activation_word(self, word: str):
        """Establece palabra de activación."""
        self.activation_word = word.lower()
        self._build_command_patterns()
        logger.info(f"🎤 Palabra de activación cambiada a: '{word}'")
    
    def set_voice_commands(self, commands: Dict[str, Dict]):
        """
        Configura los comandos de voz del perfil activo.
        
        Args:
            commands: Diccionario de comandos de voz desde ProfileRuntime
        """
        # Limpiar comandos anteriores
        self.voice_commands.clear()
        
        # Convertir a objetos VoiceCommand
        for cmd_id, cmd_data in commands.items():
            try:
                voice_cmd = VoiceCommand(
                    id=cmd_id,
                    text=cmd_data.get('text', cmd_id),
                    action=cmd_data.get('action', 'unknown'),
                    command=cmd_data.get('command', ''),
                    description=cmd_data.get('description', cmd_id),
                    enabled=cmd_data.get('enabled', True),
                    requires_activation=cmd_data.get('requires_activation', True),
                    confidence_threshold=cmd_data.get('confidence_threshold', self.min_confidence),
                    cooldown=cmd_data.get('cooldown', 0.0)
                )
                self.voice_commands[cmd_id] = voice_cmd
            except Exception as e:
                logger.error(f"❌ Error procesando comando {cmd_id}: {e}")
        
        self._build_command_patterns()
        
        logger.info(f"🎤 {len(self.voice_commands)} comandos de voz configurados")
        
        # Log de comandos disponibles
        if self.voice_commands:
            enabled_commands = [cmd.text for cmd in self.voice_commands.values() if cmd.enabled]
            if enabled_commands:
                logger.debug(f"📋 Comandos activos: {', '.join(enabled_commands[:5])}" + 
                            (f" y {len(enabled_commands)-5} más" if len(enabled_commands) > 5 else ""))
    
    def _build_command_patterns(self):
        """Construye patrones de reconocimiento para comandos de voz."""
        self.command_patterns = []
        self.activation_patterns.clear()
        
        for cmd_id, voice_cmd in self.voice_commands.items():
            if not voice_cmd.enabled:
                continue
            
            # Limpiar y normalizar comando
            clean_command = voice_cmd.text.lower().strip()
            
            # Extraer palabra de activación si está presente
            if clean_command.startswith(f"{self.activation_word} "):
                activation_part = self.activation_word
                command_part = clean_command[len(self.activation_word) + 1:]
            else:
                activation_part = None
                command_part = clean_command
            
            # Crear patrón flexible
            pattern = self._create_fuzzy_pattern(command_part)
            
            self.command_patterns.append((
                cmd_id,               # ID del comando
                voice_cmd,           # Objeto VoiceCommand
                activation_part,     # Parte de activación
                command_part,        # Parte del comando
                pattern              # Patrón regex
            ))
            
            # Agregar a patrones de activación
            if activation_part:
                self.activation_patterns.add(activation_part)
    
    def _create_fuzzy_pattern(self, text: str) -> re.Pattern:
        """
        Crea un patrón regex flexible para reconocimiento de voz.
        
        Args:
            text: Texto del comando
            
        Returns:
            Patrón regex compilado
        """
        # Escapar caracteres especiales
        escaped = re.escape(text)
        
        # Diccionario de variaciones para español
        variations = {
            'abre': r'(abre|abra|abrir|abreme|abrelo|abran)',
            'cierra': r'(cierra|cierre|cerrar|cierralo|cierren)',
            'captura': r'(captura|toma|haz|saca|tira|capturá)',
            'pantalla': r'(pantalla|pantallazo|screenshot|captura)',
            'graba': r'(graba|grabar|grabalo|grabame|graben)',
            'eso': r'(eso|esto|aquello|el|esa|ese)',
            'ventana': r'(ventana|ventanita|pestaña|ventanilla)',
            'discord': r'(discord|disco|disc|dis|cord)',
            'música': r'(música|musica|músicas|cancion|canciones|sonido)',
            'volumen': r'(volumen|volúmen|volumenes|sonido)',
            'sube': r'(sube|suba|subir|aumenta|aumentar|aumente)',
            'baja': r'(baja|baje|bajar|reduce|reducir|reduzca)',
            'silencio': r'(silencio|silencia|silenciar|mutea|mutear)'
        }
        
        # Aplicar variaciones
        pattern = escaped
        for word, variation in variations.items():
            escaped_word = re.escape(word)
            if escaped_word in pattern:
                pattern = pattern.replace(escaped_word, variation)
        
        # Permitir palabras adicionales opcionales
        optional_suffix = r'(?:\s+(?:por\s+favor|porfa|please|rapido|rápido|ahora))?'
        pattern = pattern.replace(r'\ ', r'\s+' + optional_suffix + r'\s*')
        
        # Hacer más flexible permitiendo sinónimos y variaciones
        pattern = pattern.replace(r'\ ', r'(?:\s+|\s*[.,]?\s*)')
        
        try:
            return re.compile(pattern, re.IGNORECASE)
        except Exception as e:
            logger.error(f"❌ Error creando patrón para '{text}': {e}")
            # Fallback: patrón simple
            return re.compile(re.escape(text), re.IGNORECASE)
    
    def _create_activation_pattern(self) -> re.Pattern:
        """Crea patrón para palabra de activación."""
        patterns = [
            rf'\b{re.escape(self.activation_word)}\b',
            rf'{re.escape(self.activation_word)}\s+',
            rf'^.*?\b{re.escape(self.activation_word)}\b.*?$'
        ]
        return re.compile('|'.join(patterns), re.IGNORECASE)
    
    def start(self) -> bool:
        """
        Inicia el reconocedor de voz de forma asíncrona.
        
        Returns:
            True (la inicialización continúa en segundo plano)
        """
        if self.is_running:
            logger.warning("⚠️ VoiceRecognizer ya está en ejecución")
            return True
        
        if not self.enabled:
            logger.info("🎤 VoiceRecognizer deshabilitado en configuración")
            self.state = VoiceState.DISABLED
            return False
        
        logger.info("▶️ Iniciando VoiceRecognizer (Asíncrono)...")
        self.state = VoiceState.INITIALIZING
        self.is_running = True
        
        # Iniciar hilo de inicialización para no bloquear el arranque
        self.init_thread = threading.Thread(
            target=self._async_init,
            daemon=True,
            name="NYX-VoiceInit"
        )
        self.init_thread.start()
        return True

    def _async_init(self):
        """Inicialización asíncrona de componentes de voz."""
        try:
            print("DEBUG_PRINT: Voice async init started")
            logger.info("🧵 Hilo de inicialización de voz comenzado")
            import speech_recognition as sr
            print("DEBUG_PRINT: Speech recognition imported")
            self.recognizer = sr.Recognizer()
            
            # Configurar reconocedor
            self.recognizer.energy_threshold = self.energy_threshold
            self.recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
            self.recognizer.pause_threshold = self.pause_threshold
            
            # Obtener micrófono
            try:
                print("DEBUG_PRINT: Attempting to connect microphone...")
                logger.info("🎤 Conectando con micrófono...")
                # Agregamos timeout simulado o checks previos si fuera posible
                self.microphone = sr.Microphone()
                print("DEBUG_PRINT: Microphone object created")
                self.microphone_available = True
                logger.info("✅ Micrófono conectado")
            except Exception as e:
                print(f"DEBUG_PRINT: Microphone init failed: {e}")
                logger.error(f"❌ Error obteniendo micrófono: {e}")
                self.microphone_available = False
                self.state = VoiceState.ERROR
                return
            
            self.state = VoiceState.READY
            self.last_activity_time = time.time()
            
            # Iniciar hilos funcionales
            print("DEBUG_PRINT: Starting voice threads...")
            self.listening_thread = threading.Thread(
                target=self._listening_loop,
                daemon=True,
                name="NYX-VoiceListening"
            )
            self.listening_thread.start()
            
            self.processing_thread = threading.Thread(
                target=self._processing_loop,
                daemon=True,
                name="NYX-VoiceProcessing"
            )
            self.processing_thread.start()
            
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="NYX-VoiceMonitoring"
            )
            self.monitoring_thread.start()
            print("DEBUG_PRINT: Voice threads started")
            
            # Calibrar micrófono
            print("DEBUG_PRINT: Calling _calibrate_microphone... DISABLED")
            # self._calibrate_microphone()
            print("DEBUG_PRINT: _calibrate_microphone finished (SKIPPED)")
            
            self._emit_state_change("started")
            logger.info("✅ VoiceRecognizer iniciado completamente")
            
        except Exception as e:
            print(f"DEBUG_PRINT: Async init failed: {e}")
            logger.error(f"❌ Error crítico en inicialización asíncrona de voz: {e}")
            self.state = VoiceState.ERROR
            self.is_running = False
            self._emit_error("start_error", str(e))

    def _calibrate_microphone(self):
        """Calibra el micrófono para ruido ambiente."""
        if not self.microphone_available or not self.recognizer:
            return
        
        try:
            print("DEBUG_PRINT: Inside _calibrate_microphone")
            logger.info("🔊 Calibrando micrófono para ruido ambiente...")
            self.state = VoiceState.CALIBRATING
            
            import speech_recognition as sr
            
            with self.microphone as source:
                print("DEBUG_PRINT: Adjusting for ambient noise...")
                # Calibrar una vez con timeout corto para evitar hangs
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                print("DEBUG_PRINT: Ambient noise adjusted")
                
                # Calcular nivel de ruido de fondo
                self.background_noise_level = self.recognizer.energy_threshold
                self.calibrated = True
                self.calibration_samples = 1
                
                logger.info(f"✅ Calibración completada. Nivel de ruido: {self.background_noise_level:.1f}")
                self.state = VoiceState.READY
                
        except Exception as e:
            print(f"DEBUG_PRINT: Calibration failed: {e}")
            logger.error(f"❌ Error calibrando micrófono: {e}")
            self.calibrated = False
            self.state = VoiceState.ERROR
    
    def _listening_loop(self):
        """Bucle principal de escucha de voz."""
        logger.info("🎧 Iniciando bucle de escucha de voz...")
        
        if not self.microphone_available or not self.recognizer:
            logger.error("❌ Micrófono no disponible para escucha")
            self.state = VoiceState.ERROR
            return
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        sleep_until = 0
        
        while self.is_running and self.microphone_available:
            try:
                # Verificar si está en modo sleep
                current_time = time.time()
                if current_time < sleep_until:
                    time.sleep(0.5)
                    continue
                
                # --- CHECK LISTENING ENABLED (Strict Push-to-Talk) ---
                if not self.listening_enabled:
                    time.sleep(0.1)
                    continue

                # Verificar inactividad
                if (current_time - self.last_activity_time) > self.silence_timeout:
                    if self.state != VoiceState.SLEEPING:
                        logger.debug("💤 Modo sleep por inactividad")
                        self.state = VoiceState.SLEEPING
                    time.sleep(1)
                    continue
                
                # Estado: listo para escuchar
                self.state = VoiceState.READY
                
                with self.microphone as source:
                    # Re-calibrar ocasionalmente
                    if not self.calibrated or self.calibration_samples < 10:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        self.calibration_samples += 1
                        if self.calibration_samples >= 10:
                            self.calibrated = True
                    
                    # Escuchar
                    audio = None
                    try:
                        self.state = VoiceState.LISTENING
                        audio = self.recognizer.listen(
                            source,
                            timeout=2.0,
                            phrase_time_limit=3.0
                        )
                        self.last_activity_time = time.time()
                        
                    except Exception as listen_error:
                        error_str = str(listen_error).lower()
                        if "timeout" in error_str:
                            # Timeout normal, continuar
                            continue
                        elif "wait" in error_str:
                            continue
                        else:
                            logger.debug(f"⚠️ Error en escucha: {listen_error}")
                            consecutive_errors += 1
                            continue
                    
                    if not audio:
                        continue
                    
                    # Estado: procesando audio
                    self.state = VoiceState.PROCESSING
                    
                    # Opcional: guardar muestra de audio
                    audio_data = None
                    if self.save_audio_samples and audio.frame_data:
                        audio_data = audio.frame_data
                    
                    # Reconocer texto
                    try:
                        start_time = time.time()
                        text = self.recognizer.recognize_google(
                            audio,
                            language=self.language,
                            show_all=False
                        ).lower()
                        
                        response_time = time.time() - start_time
                        self.stats.add_response_time(response_time)
                        
                        logger.info(f"🗣️ Voz detectada ({response_time:.2f}s): '{text}'")
                        
                        # Guardar audio si está habilitado
                        if audio_data and len(text.strip()) > 3:
                            self._save_audio_sample(audio_data, text)
                        
                        # Procesar texto reconocido
                        self._process_recognized_text(text)
                        
                        # Resetear contador de errores
                        consecutive_errors = 0
                        sleep_until = 0
                        
                    except Exception as recognition_error:
                        error_str = str(recognition_error).lower()
                        if "unknownvalueerror" in error_str or "not understand" in error_str:
                            # Silencio o ruido no reconocido
                            pass
                        elif "request" in error_str or "network" in error_str:
                            logger.warning("🌐 Error de red en reconocimiento de voz")
                            consecutive_errors += 1
                            sleep_until = time.time() + 5  # Esperar 5 segundos
                        else:
                            logger.debug(f"⚠️ Error reconociendo voz: {recognition_error}")
                            consecutive_errors += 1
                    
                    # Manejar muchos errores consecutivos
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"🚨 Demasiados errores consecutivos ({consecutive_errors})")
                        self.state = VoiceState.ERROR
                        sleep_until = time.time() + 30  # Esperar 30 segundos
                        consecutive_errors = 0
                        self._emit_error("consecutive_errors", f"{max_consecutive_errors} errores consecutivos")
                
            except Exception as e:
                logger.error(f"❌ Error crítico en listening loop: {e}")
                self.stats.audio_errors += 1
                consecutive_errors += 1
                time.sleep(2)
        
        logger.info("🎧 Bucle de escucha de voz terminado")
    
    def _save_audio_sample(self, audio_data: bytes, recognized_text: str):
        """Guarda una muestra de audio para análisis."""
        try:
            import speech_recognition as sr
            import wave
            
            # Crear nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_text = re.sub(r'[^\w\s]', '', recognized_text)[:30].strip().replace(' ', '_')
            filename = f"{timestamp}_{safe_text}.wav"
            filepath = os.path.join(self.audio_samples_dir, filename)
            
            # Guardar como WAV
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_data)
            
            # Guardar metadatos
            metadata = {
                'text': recognized_text,
                'timestamp': timestamp,
                'filepath': filepath,
                'language': self.language
            }
            
            with open(f"{filepath}.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 Audio guardado: {filename}")
            
        except Exception as e:
            logger.debug(f"⚠️ No se pudo guardar audio: {e}")
    
    def _process_recognized_text(self, text: str):
        """
        Procesa texto reconocido y busca comandos válidos.
        
        Args:
            text: Texto reconocido por speech recognition
        """
        self.stats.total_commands += 1
        
        # Limpiar y normalizar texto
        text = text.lower().strip()
        original_text = text
        
        # Verificar cache primero
        cache_key = f"{self.language}_{text}"
        if cache_key in self.recognition_cache:
            cached_result = self.recognition_cache[cache_key]
            if time.time() - cached_result['timestamp'] < 300:  # 5 minutos
                logger.debug(f"♻️ Usando resultado cacheado para: '{text}'")
                self._process_cached_result(cached_result)
                return
        
        # Verificar si contiene palabra de activación
        has_activation = False
        activation_pattern = self._create_activation_pattern()
        if activation_pattern.search(text):
            has_activation = True
            self.stats.activation_detected += 1
            self._emit_activation_detected(text)
            
            # Remover palabra de activación para matching
            text = activation_pattern.sub('', text).strip()
        
        # Buscar comandos que coincidan
        matched_commands = []
        
        for (cmd_id, voice_cmd, activation_part, command_part, pattern) in self.command_patterns:
            # Verificar si requiere activación
            if voice_cmd.requires_activation and not has_activation:
                continue
            
            # Verificar cooldown
            current_time = time.time()
            if voice_cmd.id in self.command_cooldowns:
                last_time = self.command_cooldowns[voice_cmd.id]
                if current_time - last_time < voice_cmd.cooldown:
                    continue
            
            # Buscar coincidencia
            if pattern.search(text):
                # Calcular confianza
                confidence = self._calculate_confidence(text, command_part, original_text)
                
                # Verificar umbral mínimo
                if confidence >= voice_cmd.confidence_threshold:
                    matched_commands.append({
                        'id': cmd_id,
                        'voice_command': voice_cmd,
                        'matched_text': original_text,
                        'processed_text': text,
                        'confidence': confidence,
                        'requires_activation': voice_cmd.requires_activation,
                        'has_activation': has_activation,
                        'timestamp': current_time
                    })
        
        # Procesar mejores coincidencias
        if matched_commands:
            # Ordenar por confianza
            matched_commands.sort(key=lambda x: x['confidence'], reverse=True)
            best_match = matched_commands[0]
            
            # Guardar en cache
            self._cache_recognition_result(cache_key, best_match)
            
            # Encolar comando
            self._enqueue_command(best_match)
            
            # Actualizar estadísticas por tipo
            cmd_type = best_match['voice_command'].action
            self.stats.commands_by_type[cmd_type] = self.stats.commands_by_type.get(cmd_type, 0) + 1
            
        else:
            # Texto no reconocido como comando
            self.stats.false_positives += 1
            
            # Solo log si contiene palabra de activación
            if has_activation:
                logger.info(f"❓ Comando no reconocido: '{original_text}'")
                
                # Intentar aprendizaje automático
                self._learn_from_unknown_command(original_text)

                # --- DICTATION FALLBACK (Dictado Inteligente) ---
                # Si no es un comando, enviarlo como texto para escribir.
                if len(text) > 0:
                     logger.info(f"✍️ Dictado detectado: '{original_text}'")
                     dictation_action = {
                        'id': 'dictation_fallback',
                        'voice_command': VoiceCommand(
                            id='dictation',
                            text='dictation',
                            action='keyboard',
                            command='type_text',
                            description='Dictado de voz'
                        ),
                        'matched_text': original_text,
                        'processed_text': text,
                        'confidence': 1.0, # Asumimos confianza total para dictado
                        'requires_activation': False,
                        'has_activation': has_activation,
                        'timestamp': time.time()
                     }
                     
                     # Encolar acción de dictado
                     self._enqueue_command(dictation_action)
                     return

    def activate_listening(self):
        """Activa la escucha del micrófono (Push-to-Talk Start)."""
        logger.info("🎤🔊 ACTIVANDO ESCUCHA (Push-to-Talk)")
        self.listening_enabled = True
        self.state = VoiceState.READY

    def deactivate_listening(self):
        """Desactiva la escucha del micrófono (Push-to-Talk Stop)."""
        logger.info("🎤🔇 DESACTIVANDO ESCUCHA (Push-to-Talk)")
        self.listening_enabled = False
        self.state = VoiceState.READY
    
    def _calculate_confidence(self, recognized: str, expected: str, original: str) -> float:
        """
        Calcula confianza de coincidencia entre texto reconocido y esperado.
        
        Args:
            recognized: Texto reconocido procesado
            expected: Texto esperado del comando
            original: Texto original reconocido
            
        Returns:
            Confianza entre 0.0 y 1.0
        """
        recognized_lower = recognized.lower()
        expected_lower = expected.lower()
        original_lower = original.lower()
        
        # Coincidencia exacta
        if expected_lower in original_lower:
            return 0.95
        
        # Coincidencia de palabras clave
        expected_words = set(expected_lower.split())
        recognized_words = set(recognized_lower.split())
        
        # Palabras coincidentes
        common_words = expected_words.intersection(recognized_words)
        if common_words:
            word_score = len(common_words) / len(expected_words)
            
            # Bonus por orden similar
            order_bonus = 0
            expected_list = expected_lower.split()
            recognized_list = recognized_lower.split()
            
            for i, word in enumerate(expected_list):
                if i < len(recognized_list) and word in recognized_list[i:min(i+2, len(recognized_list))]:
                    order_bonus += 0.1
            
            return min(0.9, word_score * 0.8 + order_bonus)
        
        # Coincidencia parcial con sinónimos
        synonym_score = 0
        synonyms = {
            'abre': ['abrir', 'abran', 'abra'],
            'cierra': ['cerrar', 'cierren', 'cierre'],
            'captura': ['toma', 'saca', 'haz'],
            'pantalla': ['pantallazo', 'screenshot'],
            'discord': ['disco', 'disc']
        }
        
        for exp_word in expected_words:
            for rec_word in recognized_words:
                if exp_word in synonyms and rec_word in synonyms[exp_word]:
                    synonym_score += 0.3
                elif exp_word[:3] == rec_word[:3]:  # Coincidencia de prefijo
                    synonym_score += 0.2
        
        if synonym_score > 0:
            return min(0.8, synonym_score)
        
        # Coincidencia de caracteres
        if len(recognized_lower) > 0:
            char_match = sum(1 for c in expected_lower if c in recognized_lower) / len(expected_lower)
            return char_match * 0.5
        
        return 0.3
    
    def _learn_from_unknown_command(self, text: str):
        """Intenta aprender de comandos no reconocidos."""
        # Esto podría integrarse con ML en el futuro
        # Por ahora solo log para análisis posterior
        pass
    
    def _cache_recognition_result(self, key: str, result: Dict):
        """Guarda resultado en cache."""
        result['timestamp'] = time.time()
        self.recognition_cache[key] = result
        
        # Limitar tamaño del cache
        if len(self.recognition_cache) > self.cache_max_size:
            # Eliminar entrada más antigua
            oldest_key = min(self.recognition_cache.keys(), 
                           key=lambda k: self.recognition_cache[k]['timestamp'])
            del self.recognition_cache[oldest_key]
    
    def _process_cached_result(self, cached_result: Dict):
        """Procesa resultado desde cache."""
        # Reutilizar resultado cacheado
        self._enqueue_command(cached_result)
        
        # Actualizar estadísticas
        self.stats.valid_commands += 1
        self.stats.last_command_time = time.time()
    
    def _enqueue_command(self, command_match: Dict):
        """
        Encuela un comando válido para procesamiento.
        
        Args:
            command_match: Datos del comando coincidente
        """
        voice_cmd = command_match['voice_command']
        
        # Crear comando para NYX
        command = {
            'type': 'voice',
            'id': command_match['id'],
            'command': voice_cmd.command,
            'action': voice_cmd.action,
            'description': voice_cmd.description,
            'voice_text': command_match['matched_text'],
            'processed_text': command_match.get('processed_text', ''),
            'original_command': voice_cmd.text,
            'confidence': command_match['confidence'],
            'timestamp': command_match['timestamp'],
            'requires_activation': command_match.get('requires_activation', True),
            'has_activation': command_match.get('has_activation', False),
            'profile': 'active',  # Será reemplazado por el perfil real
            'source': 'voice_recognizer'
        }
        
        try:
            self.command_queue.put_nowait(command)
            self.stats.valid_commands += 1
            self.stats.last_command_time = time.time()
            
            # Actualizar cooldown
            self.command_cooldowns[voice_cmd.id] = command_match['timestamp']
            
            logger.info(f"✅ Comando de voz '{voice_cmd.description}' "
                       f"(conf: {command_match['confidence']:.2f})")
            
            # Notificar callbacks
            self._emit_command_detected(command)
            
        except queue.Full:
            logger.warning("⚠️ Cola de comandos de voz llena, descartando comando")
    
    def _processing_loop(self):
        """Bucle de procesamiento de comandos."""
        logger.info("🔄 Iniciando bucle de procesamiento de comandos...")
        
        while self.is_running:
            try:
                # Obtener comando de la cola
                command = self.command_queue.get(timeout=1.0)
                if not command:
                    continue
                
                # Estado: procesando
                self.state = VoiceState.PROCESSING
                
                # Validar comando antes de enviar
                if self._validate_command(command):
                    # Enviar a la cola de acciones de NYX
                    try:
                        self.action_queue.put_nowait(command)
                        logger.debug(f"📤 Comando enviado a ActionExecutor: {command.get('description')}")
                        
                        # Emitir evento de audio procesado
                        self._emit_audio_processed(command)
                        
                    except queue.Full:
                        logger.warning("⚠️ Cola de acciones llena, descartando comando de voz")
                else:
                    logger.warning(f"⚠️ Comando no válido: {command.get('description')}")
                
                # Volver a estado listo
                self.state = VoiceState.READY
                
                self.command_queue.task_done()
                
            except queue.Empty:
                # Timeout normal, continuar
                continue
            except Exception as e:
                logger.error(f"❌ Error en processing loop: {e}")
                self.stats.processing_errors += 1
                time.sleep(0.5)
        
        logger.info("🔄 Bucle de procesamiento de comandos terminado")
    
    def _validate_command(self, command: Dict) -> bool:
        """Valida un comando antes de procesarlo."""
        try:
            # Verificar campos requeridos
            required_fields = ['id', 'action', 'command', 'confidence']
            for field in required_fields:
                if field not in command:
                    return False
            
            # Verificar confianza mínima
            if command['confidence'] < self.min_confidence:
                return False
            
            # Verificar si el comando está habilitado
            cmd_id = command['id']
            if cmd_id in self.voice_commands:
                voice_cmd = self.voice_commands[cmd_id]
                if not voice_cmd.enabled:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _monitoring_loop(self):
        """Bucle de monitoreo del estado del sistema."""
        logger.info("👁️ Iniciando bucle de monitoreo...")
        
        last_stats_log = time.time()
        stats_interval = 300  # 5 minutos
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Log de estadísticas periódico
                if current_time - last_stats_log >= stats_interval:
                    self._log_system_stats()
                    last_stats_log = current_time
                
                # Verificar estado del micrófono
                if self.microphone_available and hasattr(self, 'microphone'):
                    try:
                        import speech_recognition as sr
                        # Prueba simple del micrófono
                        test = sr.Microphone()
                        del test
                    except Exception:
                        logger.warning("🎤 Micrófono puede haber sido desconectado")
                        self.microphone_available = False
                
                # Limpiar cache viejo
                self._cleanup_old_cache()
                
                time.sleep(10)  # Revisar cada 10 segundos
                
            except Exception as e:
                logger.error(f"❌ Error en monitoring loop: {e}")
                time.sleep(30)
        
        logger.info("👁️ Bucle de monitoreo terminado")
    
    def _log_system_stats(self):
        """Registra estadísticas del sistema."""
        stats = self.get_stats()
        logger.info(f"📊 Stats voz: {stats['valid_commands']}/{stats['total_commands']} "
                   f"comandos, {stats['average_response_time']:.2f}s respuesta, "
                   f"{stats['uptime_seconds']:.0f}s activo")
    
    def _cleanup_old_cache(self):
        """Limpia entradas viejas del cache."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, value in self.recognition_cache.items():
            if current_time - value['timestamp'] > 1800:  # 30 minutos
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.recognition_cache[key]
        
        if keys_to_remove:
            logger.debug(f"🧹 Cache limpiado: {len(keys_to_remove)} entradas removidas")
    
    def listen(self, timeout: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Escucha y retorna el próximo comando de voz.
        
        Args:
            timeout: Tiempo máximo de espera
            
        Returns:
            Comando de voz o None si no hay
        """
        try:
            return self.command_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_action(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """
        Obtiene la próxima acción de voz para ejecutar.
        
        Args:
            timeout: Tiempo máximo de espera
            
        Returns:
            Acción de voz o None si no hay
        """
        try:
            return self.action_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_pending_commands_count(self) -> int:
        """Obtiene número de comandos pendientes."""
        return self.command_queue.qsize()
    
    def get_pending_actions_count(self) -> int:
        """Obtiene número de acciones pendientes."""
        return self.action_queue.qsize()
    
    def add_callback(self, callback_type: str, callback: Callable):
        """
        Agrega un callback para eventos de voz.
        
        Args:
            callback_type: Tipo de callback
            callback: Función callback
        """
        if callback_type in self.callbacks and callback not in self.callbacks[callback_type]:
            self.callbacks[callback_type].append(callback)
            logger.debug(f"✅ Callback '{callback_type}' agregado")
    
    def remove_callback(self, callback_type: str, callback: Callable):
        """Remueve un callback."""
        if callback_type in self.callbacks and callback in self.callbacks[callback_type]:
            self.callbacks[callback_type].remove(callback)
            logger.debug(f"✅ Callback '{callback_type}' removido")
    
    def remove_all_callbacks(self, callback_type: str = None):
        """Remueve todos los callbacks o de un tipo específico."""
        if callback_type:
            if callback_type in self.callbacks:
                self.callbacks[callback_type].clear()
                logger.debug(f"✅ Todos los callbacks '{callback_type}' removidos")
        else:
            for cb_type in self.callbacks:
                self.callbacks[cb_type].clear()
            logger.debug("✅ Todos los callbacks removidos")
    
    def _emit_command_detected(self, command: Dict):
        """Emite evento de comando detectado."""
        for callback in self.callbacks['on_command']:
            try:
                callback(command)
            except Exception as e:
                logger.error(f"❌ Error en callback on_command: {e}")
    
    def _emit_activation_detected(self, text: str):
        """Emite evento de activación detectada."""
        for callback in self.callbacks['on_activation']:
            try:
                callback(text)
            except Exception as e:
                logger.error(f"❌ Error en callback on_activation: {e}")
    
    def _emit_error(self, error_type: str, message: str):
        """Emite evento de error."""
        for callback in self.callbacks['on_error']:
            try:
                callback(error_type, message)
            except Exception as e:
                logger.error(f"❌ Error en callback on_error: {e}")
    
    def _emit_state_change(self, new_state: str):
        """Emite evento de cambio de estado."""
        for callback in self.callbacks['on_state_change']:
            try:
                callback(self.state.value, new_state)
            except Exception as e:
                logger.error(f"❌ Error en callback on_state_change: {e}")
    
    def _emit_audio_processed(self, command: Dict):
        """Emite evento de audio procesado."""
        for callback in self.callbacks['on_audio_captured']:
            try:
                callback(command)
            except Exception as e:
                logger.error(f"❌ Error en callback on_audio_captured: {e}")
    
    def clear_command_queue(self):
        """Limpia la cola de comandos."""
        with self.command_queue.mutex:
            self.command_queue.queue.clear()
        logger.debug("🧹 Cola de comandos limpiada")
    
    def clear_action_queue(self):
        """Limpia la cola de acciones."""
        with self.action_queue.mutex:
            self.action_queue.queue.clear()
        logger.debug("🧹 Cola de acciones limpiada")
        
    def _enqueue_command(self, command_data: Dict):
        """Encola un comando detectado."""
        try:
            self.command_queue.put(command_data, timeout=0.1)
            self._emit_command_detected(command_data)
        except queue.Full:
            logger.warning("⚠️ Cola de comandos llena")
    
    def _clear_queues(self):
        """Limpia todas las colas."""
        self.clear_command_queue()
        self.clear_action_queue()
    
    def update_config(self, new_config: Dict):
        """Actualiza configuración dinámicamente."""
        voice_config = new_config.get('voice_recognition', {})
        
        changes_made = []
        
        if 'activation_word' in voice_config:
            new_word = voice_config['activation_word'].lower()
            if new_word != self.activation_word:
                self.activation_word = new_word
                changes_made.append(f"activación a '{self.activation_word}'")
                # Reconstruir patrones
                self._build_command_patterns()
        
        if 'language' in voice_config:
            new_lang = voice_config['language']
            if new_lang != self.language:
                self.language = new_lang
                changes_made.append(f"idioma a {self.language}")
        
        if 'min_confidence' in voice_config:
            self.min_confidence = voice_config['min_confidence']
            changes_made.append(f"confianza mínima a {self.min_confidence}")
        
        if 'enabled' in voice_config:
            was_enabled = self.enabled
            self.enabled = voice_config['enabled']
            
            if was_enabled and not self.enabled:
                self.stop()
                changes_made.append("deshabilitado")
            elif not was_enabled and self.enabled:
                self.start()
                changes_made.append("habilitado")
        
        if 'energy_threshold' in voice_config and self.recognizer:
            self.energy_threshold = voice_config['energy_threshold']
            self.recognizer.energy_threshold = self.energy_threshold
            changes_made.append(f"umbral energía a {self.energy_threshold}")
        
        if changes_made:
            logger.info(f"🔄 Configuración actualizada: {', '.join(changes_made)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas para NYX UI."""
        stats = self.stats.to_dict()
        stats.update({
            'state': self.state.value,
            'enabled': self.enabled,
            'microphone_available': self.microphone_available,
            'speech_recognition_available': self.speech_recognition_available,
            'calibrated': self.calibrated,
            'background_noise_level': self.background_noise_level,
            'voice_commands_count': len(self.voice_commands),
            'enabled_commands_count': sum(1 for cmd in self.voice_commands.values() if cmd.enabled),
            'command_patterns_count': len(self.command_patterns),
            'activation_word': self.activation_word,
            'language': self.language,
            'command_queue_size': self.command_queue.qsize(),
            'action_queue_size': self.action_queue.qsize(),
            'cache_size': len(self.recognition_cache),
            'listening_enabled': self.listening_enabled,
            'last_activity_seconds': time.time() - self.last_activity_time,
            'cooldown_commands': len(self.command_cooldowns)
        })
        return stats
    
    def get_state(self) -> VoiceState:
        """Obtiene el estado actual."""
        return self.state
    
    def is_available(self) -> bool:
        """Verifica si el reconocimiento de voz está disponible."""
        return (self.speech_recognition_available and 
                self.enabled and 
                self.state != VoiceState.DISABLED and
                self.state != VoiceState.ERROR)
    
    def is_listening(self) -> bool:
        """Verifica si está escuchando activamente."""
        return (self.is_running and 
                self.listening_enabled and 
                self.state in [VoiceState.READY, VoiceState.LISTENING])
    
    def pause_listening(self):
        """Pausa la escucha temporalmente."""
        if self.listening_enabled:
            self.listening_enabled = False
            logger.info("⏸️ Escucha de voz pausada")
    
    def resume_listening(self):
        """Reanuda la escucha."""
        if not self.listening_enabled:
            self.listening_enabled = True
            logger.info("▶️ Escucha de voz reanudada")
    
    def test_microphone(self) -> Tuple[bool, str]:
        """
        Prueba el micrófono y reconocimiento de voz.
        
        Returns:
            (éxito, mensaje)
        """
        if not self.speech_recognition_available:
            return False, "Speech recognition no disponible"
        
        try:
            import speech_recognition as sr
            
            # Crear reconocedor temporal
            test_recognizer = sr.Recognizer()
            
            try:
                test_microphone = sr.Microphone()
            except Exception as e:
                return False, f"Error obteniendo micrófono: {str(e)}"
            
            with test_microphone as source:
                # Calibrar
                logger.info("🔊 Calibrando para prueba...")
                test_recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Escuchar
                logger.info("🎤 Habla ahora (tienes 5 segundos)...")
                try:
                    audio = test_recognizer.listen(source, timeout=5, phrase_time_limit=3)
                    
                    # Reconocer
                    try:
                        text = test_recognizer.recognize_google(audio, language=self.language)
                        return True, f"✅ Micrófono funciona. Reconocido: '{text}'"
                    except Exception as recog_error:
                        if "not understand" in str(recog_error).lower():
                            return True, "✅ Micrófono funciona pero no se reconoció voz clara"
                        else:
                            return False, f"❌ Error reconociendo voz: {str(recog_error)}"
                            
                except Exception as listen_error:
                    if "timeout" in str(listen_error).lower():
                        return True, "✅ Micrófono funciona pero no se detectó voz"
                    else:
                        return False, f"❌ Error escuchando: {str(listen_error)}"
                
        except Exception as e:
            error_msg = str(e)
            return False, f"❌ Error en prueba: {error_msg}"
    
    def simulate_voice_command(self, text: str) -> Dict:
        """
        Simula un comando de voz para pruebas.
        
        Args:
            text: Texto a simular
            
        Returns:
            Resultado del procesamiento
        """
        logger.info(f"🧪 Simulando comando de voz: '{text}'")
        
        # Procesar como si fuera reconocido
        self._process_recognized_text(text)
        
        # Obtener resultado si hay
        result = {
            'simulated_text': text,
            'processed': True,
            'timestamp': time.time()
        }
        
        # Verificar si se detectó como comando
        try:
            command = self.command_queue.get_nowait()
            result['detected_command'] = command
            result['detected'] = True
        except queue.Empty:
            result['detected'] = False
        
        return result
    
    def get_voice_commands_list(self) -> List[Dict]:
        """Obtiene lista de comandos de voz configurados."""
        commands_list = []
        for cmd_id, voice_cmd in self.voice_commands.items():
            cmd_dict = asdict(voice_cmd)
            cmd_dict['id'] = cmd_id
            commands_list.append(cmd_dict)
        return commands_list
    
    def toggle_command(self, command_id: str, enabled: bool = None) -> bool:
        """
        Habilita/deshabilita un comando específico.
        
        Args:
            command_id: ID del comando
            enabled: Nuevo estado (None para alternar)
            
        Returns:
            True si se cambió exitosamente
        """
        if command_id not in self.voice_commands:
            logger.warning(f"⚠️ Comando '{command_id}' no encontrado")
            return False
        
        voice_cmd = self.voice_commands[command_id]
        
        if enabled is None:
            voice_cmd.enabled = not voice_cmd.enabled
        else:
            voice_cmd.enabled = enabled
        
        # Reconstruir patrones
        self._build_command_patterns()
        
        status = "habilitado" if voice_cmd.enabled else "deshabilitado"
        logger.info(f"🔄 Comando '{command_id}' {status}")
        return True
    
    def reset_stats(self):
        """Reinicia todas las estadísticas."""
        self.stats = VoiceStats()
        logger.info("📊 Estadísticas de voz reiniciadas")
    
    def cleanup(self):
        """Limpia recursos del reconocedor."""
        logger.info("🧹 Limpiando VoiceRecognizer...")
        
        self.stop()
        
        # Esperar hilos
        threads = [self.listening_thread, self.processing_thread, self.monitoring_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=2)
        
        self._clear_queues()
        
        # Limpiar callbacks
        for callback_list in self.callbacks.values():
            callback_list.clear()
        
        # Limpiar módulos
        self.recognizer = None
        self.microphone = None
        
        # Limpiar cache
        self.recognition_cache.clear()
        self.command_cooldowns.clear()
        
        logger.info("✅ VoiceRecognizer limpiado")
    
    def export_audio_samples(self, output_dir: str = None) -> Tuple[bool, str]:
        """
        Exporta muestras de audio guardadas.
        
        Args:
            output_dir: Directorio de salida
            
        Returns:
            (éxito, mensaje)
        """
        if not self.save_audio_samples:
            return False, "Guardado de muestras no habilitado"
        
        try:
            import shutil
            
            source_dir = self.audio_samples_dir
            if not os.path.exists(source_dir):
                return False, "Directorio de muestras no existe"
            
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"./voice_export_{timestamp}"
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Copiar archivos
            files_copied = 0
            for filename in os.listdir(source_dir):
                if filename.endswith('.wav'):
                    src_path = os.path.join(source_dir, filename)
                    dst_path = os.path.join(output_dir, filename)
                    shutil.copy2(src_path, dst_path)
                    files_copied += 1
                    
                    # Copiar metadatos si existen
                    json_path = src_path + '.json'
                    if os.path.exists(json_path):
                        shutil.copy2(json_path, dst_path + '.json')
            
            return True, f"✅ {files_copied} muestras exportadas a {output_dir}"
            
        except Exception as e:
            return False, f"❌ Error exportando muestras: {str(e)}"
    
    def __del__(self):
        """Destructor para limpieza segura."""
        try:
            self.cleanup()
        except:
            pass


# Funciones de utilidad para integración con NYX
def create_voice_recognizer(config: Dict) -> Optional[VoiceRecognizer]:
    """
    Factory function para crear VoiceRecognizer.
    
    Args:
        config: Configuración del sistema
        
    Returns:
        VoiceRecognizer instanciado o None
    """
    try:
        return VoiceRecognizer(config)
    except Exception as e:
        logger.error(f"❌ Error creando VoiceRecognizer: {e}")
        return None


def validate_voice_config(config: Dict) -> Tuple[bool, List[str]]:
    """
    Valida configuración de voz.
    
    Args:
        config: Configuración a validar
        
    Returns:
        (válido, lista de errores)
    """
    errors = []
    
    voice_config = config.get('voice_recognition', {})
    
    # Validar campos requeridos
    if 'activation_word' not in voice_config:
        errors.append("Falta 'activation_word' en configuración de voz")
    elif not isinstance(voice_config['activation_word'], str) or len(voice_config['activation_word']) < 2:
        errors.append("'activation_word' debe ser un string de al menos 2 caracteres")
    
    if 'language' not in voice_config:
        errors.append("Falta 'language' en configuración de voz")
    
    if 'energy_threshold' in voice_config:
        try:
            et = int(voice_config['energy_threshold'])
            if et < 50 or et > 5000:
                errors.append("'energy_threshold' debe estar entre 50 y 5000")
        except (ValueError, TypeError):
            errors.append("'energy_threshold' debe ser un número entero")
    
    if 'min_confidence' in voice_config:
        try:
            mc = float(voice_config['min_confidence'])
            if mc < 0.1 or mc > 0.99:
                errors.append("'min_confidence' debe estar entre 0.1 y 0.99")
        except (ValueError, TypeError):
            errors.append("'min_confidence' debe ser un número")
    
    return len(errors) == 0, errors


# Ejemplo de uso avanzado
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('voice_recognizer.log'),
            logging.StreamHandler()
        ]
    )
    
    print("🎤 Probando VoiceRecognizer avanzado para NYX...")
    
    # Configuración detallada
    test_config = {
        'voice_recognition': {
            'enabled': True,
            'auto_start': True,
            'activation_word': 'nyx',
            'language': 'es-ES',
            'energy_threshold': 300,
            'pause_threshold': 0.8,
            'dynamic_energy_threshold': True,
            'continuous_listening': True,
            'silence_timeout': 15.0,
            'min_confidence': 0.6,
            'save_audio_samples': False,
            'audio_samples_dir': './test_samples'
        }
    }
    
    # Perfil gamer avanzado
    advanced_gamer_commands = {
        'open_discord': {
            'text': 'nyx abre discord',
            'action': 'bash',
            'command': 'discord',
            'description': 'Abrir Discord',
            'enabled': True,
            'requires_activation': True,
            'confidence_threshold': 0.5,
            'cooldown': 2.0
        },
        'screenshot': {
            'text': 'nyx captura pantalla',
            'action': 'bash',
            'command': 'gnome-screenshot -i',
            'description': 'Tomar screenshot interactivo',
            'enabled': True,
            'requires_activation': True,
            'confidence_threshold': 0.6,
            'cooldown': 1.0
        },
        'start_recording': {
            'text': 'nyx graba eso',
            'action': 'bash',
            'command': 'xdotool key ctrl+shift+r',
            'description': 'Iniciar grabación',
            'enabled': True,
            'requires_activation': True,
            'confidence_threshold': 0.7
        },
        'close_window': {
            'text': 'nyx cierra ventana',
            'action': 'window',
            'command': 'close',
            'description': 'Cerrar ventana actual',
            'enabled': True,
            'requires_activation': True
        },
        'volume_up': {
            'text': 'nyx sube volumen',
            'action': 'bash',
            'command': 'pactl set-sink-volume @DEFAULT_SINK@ +10%',
            'description': 'Subir volumen',
            'enabled': True,
            'requires_activation': True,
            'cooldown': 0.5
        },
        'volume_down': {
            'text': 'nyx baja volumen',
            'action': 'bash',
            'command': 'pactl set-sink-volume @DEFAULT_SINK@ -10%',
            'description': 'Bajar volumen',
            'enabled': True,
            'requires_activation': True,
            'cooldown': 0.5
        },
        'mute': {
            'text': 'nyx silencio',
            'action': 'bash',
            'command': 'pactl set-sink-mute @DEFAULT_SINK@ toggle',
            'description': 'Silenciar/activar sonido',
            'enabled': True,
            'requires_activation': True
        },
        'open_browser': {
            'text': 'abre navegador',
            'action': 'bash',
            'command': 'firefox',
            'description': 'Abrir navegador',
            'enabled': True,
            'requires_activation': False  # No requiere palabra de activación
        }
    }
    
    # Crear reconocedor
    recognizer = create_voice_recognizer(test_config)
    
    if recognizer:
        # Configurar comandos
        recognizer.set_voice_commands(advanced_gamer_commands)
        
        # Mostrar estado inicial
        print(f"\n📊 Estado inicial:")
        stats = recognizer.get_stats()
        for key, value in stats.items():
            if key in ['state', 'enabled', 'microphone_available', 
                      'voice_commands_count', 'activation_word', 'language']:
                print(f"  {key}: {value}")
        
        # Probar micrófono
        print(f"\n🔧 Probando micrófono...")
        success, message = recognizer.test_microphone()
        print(f"  Resultado: {message}")
        
        # Simular comandos
        print(f"\n🧪 Simulando comandos de voz:")
        
        test_scenarios = [
            "nyx abre discord por favor",
            "nyx captura la pantalla ahora",
            "nyx graba eso rápido",
            "nyx cierra esa ventana",
            "abre navegador",  # Sin activación
            "nyx sube el volumen",
            "nyx baja volumen",
            "nyx silencio por favor",
            "hola como estás",  # No debería reconocer
            "nyx abre disco",  # Variación
            "captura pantallazo",  # Sin activación (no debería funcionar)
            "nyx captura pantallazo"  # Con activación y variación
        ]
        
        for phrase in test_scenarios:
            print(f"\n  Prueba: '{phrase}'")
            result = recognizer.simulate_voice_command(phrase)
            if result.get('detected'):
                cmd = result['detected_command']
                print(f"    → ✅ Detectado: {cmd.get('description')} (conf: {cmd.get('confidence'):.2f})")
            else:
                print(f"    → ❌ No detectado como comando válido")
        
        # Mostrar estadísticas detalladas
        print(f"\n📈 Estadísticas finales:")
        final_stats = recognizer.get_stats()
        print(f"  Comandos totales: {final_stats['total_commands']}")
        print(f"  Comandos válidos: {final_stats['valid_commands']}")
        print(f"  Activaciones: {final_stats['activation_detected']}")
        print(f"  Falsos positivos: {final_stats['false_positives']}")
        print(f"  Tiempo respuesta promedio: {final_stats['average_response_time']:.2f}s")
        print(f"  Comandos por tipo: {final_stats['commands_by_type']}")
        
        # Probar gestión de comandos
        print(f"\n⚙️ Probando gestión de comandos:")
        
        # Listar comandos
        commands_list = recognizer.get_voice_commands_list()
        print(f"  Total comandos configurados: {len(commands_list)}")
        
        # Deshabilitar un comando
        if commands_list:
            sample_cmd = commands_list[0]
            print(f"  Deshabilitando comando: {sample_cmd['id']}")
            recognizer.toggle_command(sample_cmd['id'], False)
        
        # Re-habilitar
        print(f"  Habilitando nuevamente: {sample_cmd['id']}")
        recognizer.toggle_command(sample_cmd['id'], True)
        
        # Probar pausa/resume
        print(f"\n⏯️ Probando control de escucha:")
        print(f"  Escuchando actualmente: {recognizer.is_listening()}")
        
        recognizer.pause_listening()
        print(f"  Después de pausa: {recognizer.is_listening()}")
        
        recognizer.resume_listening()
        print(f"  Después de reanudar: {recognizer.is_listening()}")
        
        # Limpiar
        recognizer.cleanup()
        print("\n✅ Prueba avanzada completada exitosamente!")
    else:
        print("❌ No se pudo crear VoiceRecognizer")