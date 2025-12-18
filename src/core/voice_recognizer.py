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
from typing import Dict, Optional, Callable, List, Set
from enum import Enum
import re

logger = logging.getLogger(__name__)


class VoiceState(Enum):
    """Estados del reconocedor de voz para NYX."""
    INITIALIZING = "initializing"  # Inicializando
    READY = "ready"               # Listo para escuchar
    LISTENING = "listening"       # Escuchando activamente
    PROCESSING = "processing"     # Procesando comando
    ERROR = "error"              # Error en el sistema
    DISABLED = "disabled"        # Deshabilitado por configuración


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
        
        # Comandos de voz del perfil activo
        self.voice_commands: Dict[str, Dict] = {}  # Comandos registrados
        self.command_patterns: List[tuple] = []    # Patrones para matching
        self.activation_patterns: Set[str] = set() # Patrones de activación
        
        # Estado del sistema
        self.state = VoiceState.INITIALIZING
        self.is_running = False
        self.microphone_available = False
        
        # Colas para comunicación con NYX
        self.command_queue = queue.Queue(maxsize=10)      # Comandos detectados
        self.action_queue = queue.Queue()                 # Acciones para ejecutar
        self.callbacks = {
            'on_command': [],
            'on_activation': [],
            'on_error': [],
            'on_state_change': []
        }
        
        # Hilos
        self.listening_thread = None
        self.processing_thread = None
        
        # Módulos de speech recognition (lazy loading)
        self.recognizer = None
        self.microphone = None
        self.speech_recognition_available = False
        
        # Estadísticas para NYX UI
        self.stats = {
            'total_commands': 0,
            'valid_commands': 0,
            'activation_detected': 0,
            'processing_errors': 0,
            'last_command_time': 0,
            'uptime': time.time(),
            'audio_errors': 0
        }
        
        # Calibración
        self.calibrated = False
        self.calibration_samples = 0
        
        # Inicializar módulos
        self._init_speech_modules()
        
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
    
    def set_voice_commands(self, voice_commands: Dict[str, Dict]):
        """
        Configura los comandos de voz del perfil activo.
        
        Args:
            voice_commands: Diccionario de comandos de voz desde ProfileRuntime
                Formato: {'nyx comando': {'action': 'bash', 'command': '...', ...}}
        """
        self.voice_commands = voice_commands
        self._build_command_patterns()
        
        logger.info(f"🎤 {len(voice_commands)} comandos de voz configurados")
        
        # Log de comandos disponibles (solo primeros 3 para no saturar)
        if voice_commands:
            sample_commands = list(voice_commands.keys())[:3]
            logger.debug(f"📋 Comandos de voz: {', '.join(sample_commands)}" + 
                        (f" y {len(voice_commands)-3} más" if len(voice_commands) > 3 else ""))
    
    def _build_command_patterns(self):
        """Construye patrones de reconocimiento para comandos de voz."""
        self.command_patterns = []
        self.activation_patterns.clear()
        
        for command_text, command_data in self.voice_commands.items():
            if not command_data.get('enabled', True):
                continue
            
            # Limpiar y normalizar comando
            clean_command = command_text.lower().strip()
            
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
                command_text,           # Comando original
                command_data,          # Datos del comando
                activation_part,       # Parte de activación
                command_part,          # Parte del comando
                pattern                # Patrón regex
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
        
        # Permitir variaciones comunes
        # Ej: "abre" -> "(abre|abra|abrir)"
        variations = {
            'abre': r'(abre|abra|abrir|abreme|abrelo)',
            'cierra': r'(cierra|cierre|cerrar|cierralo)',
            'maximiza': r'(maximiza|maximizar|maximize|agranda)',
            'minimiza': r'(minimiza|minimizar|minimize|reduce)',
            'captura': r'(captura|toma|haz|saca)',
            'pantalla': r'(pantalla|pantallazo|screenshot|captura)'
        }
        
        # Aplicar variaciones
        pattern = escaped
        for word, variation in variations.items():
            pattern = pattern.replace(re.escape(word), variation)
        
        # Permitir palabras adicionales opcionales
        pattern = pattern.replace(r'\ ', r'\s+(?:por\s+favor\s+)?')
        
        # Hacer el patrón más flexible
        pattern = fr'(?:{pattern})'
        
        try:
            return re.compile(pattern, re.IGNORECASE)
        except:
            # Fallback: patrón simple
            return re.compile(re.escape(text), re.IGNORECASE)
    
    def start(self) -> bool:
        """
        Inicia el reconocedor de voz.
        
        Returns:
            True si se inició correctamente
        """
        if self.is_running:
            logger.warning("⚠️ VoiceRecognizer ya está en ejecución")
            return True
        
        if not self.enabled:
            logger.info("🎤 VoiceRecognizer deshabilitado en configuración")
            self.state = VoiceState.DISABLED
            return False
        
        if not self.speech_recognition_available:
            logger.error("❌ No se puede iniciar VoiceRecognizer: módulos no disponibles")
            self.state = VoiceState.ERROR
            return False
        
        logger.info("▶️ Iniciando VoiceRecognizer...")
        
        try:
            # Inicializar reconocedor
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            
            # Configurar reconocedor
            self.recognizer.energy_threshold = self.energy_threshold
            self.recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
            self.recognizer.pause_threshold = self.pause_threshold
            
            # Obtener micrófono
            self.microphone = sr.Microphone()
            self.microphone_available = True
            
            # Marcar como listo
            self.is_running = True
            self.state = VoiceState.READY
            
            # Iniciar hilos
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
            
            # Calibrar micrófono
            self._calibrate_microphone()
            
            self._emit_state_change("started")
            logger.info("✅ VoiceRecognizer iniciado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error iniciando VoiceRecognizer: {e}")
            self.state = VoiceState.ERROR
            self._emit_error("start_error", str(e))
            return False
    
    def stop(self):
        """Detiene el reconocedor de voz de manera controlada."""
        if not self.is_running:
            return
        
        logger.info("⏹️ Deteniendo VoiceRecognizer...")
        
        self.is_running = False
        self.microphone_available = False
        
        # Esperar hilos
        if self.listening_thread and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=2)
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)
        
        # Limpiar colas
        self._clear_queues()
        
        self.state = VoiceState.DISABLED
        self._emit_state_change("stopped")
        
        logger.info("✅ VoiceRecognizer detenido")
    
    def _calibrate_microphone(self):
        """Calibra el micrófono para ruido ambiente."""
        if not self.microphone_available or not self.recognizer:
            return
        
        try:
            logger.info("🔊 Calibrando micrófono para ruido ambiente...")
            
            with self.microphone as source:
                # Calibrar múltiples veces para mejor precisión
                for i in range(3):
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    time.sleep(0.1)
                
                self.calibrated = True
                self.calibration_samples = 3
                
                logger.info("✅ Calibración de micrófono completada")
                
        except Exception as e:
            logger.error(f"❌ Error calibrando micrófono: {e}")
            self.calibrated = False
    
    def _listening_loop(self):
        """Bucle principal de escucha de voz."""
        logger.info("🎧 Iniciando bucle de escucha de voz...")
        
        if not self.microphone_available or not self.recognizer:
            logger.error("❌ Micrófono no disponible para escucha")
            self.state = VoiceState.ERROR
            return
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running and self.microphone_available:
            try:
                with self.microphone as source:
                    # Re-calibrar ocasionalmente
                    if not self.calibrated or self.calibration_samples < 5:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        self.calibration_samples += 1
                        if self.calibration_samples >= 5:
                            self.calibrated = True
                    
                    # Estado: listo para escuchar
                    self.state = VoiceState.READY
                    
                    # Escuchar con timeout
                    audio = None
                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=3.0,
                            phrase_time_limit=4.0
                        )
                    except Exception as timeout_error:
                        # Timeout es normal, continuar
                        if "timeout" not in str(timeout_error).lower():
                            logger.debug(f"⚠️ Error en escucha: {timeout_error}")
                        continue
                    
                    if not audio:
                        continue
                    
                    # Estado: procesando audio
                    self.state = VoiceState.PROCESSING
                    
                    # Reconocer texto
                    try:
                        text = self.recognizer.recognize_google(
                            audio,
                            language=self.language,
                            show_all=False
                        ).lower()
                        
                        logger.debug(f"🗣️ Voz detectada: '{text}'")
                        
                        # Procesar texto reconocido
                        self._process_recognized_text(text)
                        
                        # Resetear contador de errores
                        consecutive_errors = 0
                        
                    except Exception as recognition_error:
                        # Error de reconocimiento (puede ser silencio o ruido)
                        if "recognize" in str(recognition_error):
                            # No es un error crítico, solo continuar
                            pass
                        else:
                            logger.debug(f"⚠️ Error reconociendo voz: {recognition_error}")
                            consecutive_errors += 1
                    
                    # Verificar errores consecutivos
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning(f"⚠️ Muchos errores consecutivos ({consecutive_errors}), reintentando...")
                        time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error crítico en listening loop: {e}")
                self.stats['audio_errors'] += 1
                consecutive_errors += 1
                
                # Esperar antes de reintentar
                time.sleep(1)
                
                if consecutive_errors >= max_consecutive_errors * 2:
                    logger.error("🚨 Demasiados errores, deteniendo reconocimiento de voz")
                    self.state = VoiceState.ERROR
                    self._emit_error("audio_error", "Demasiados errores de audio")
                    break
        
        logger.info("🎧 Bucle de escucha de voz terminado")
    
    def _process_recognized_text(self, text: str):
        """
        Procesa texto reconocido y busca comandos válidos.
        
        Args:
            text: Texto reconocido por speech recognition
        """
        self.stats['total_commands'] += 1
        
        # Verificar si contiene palabra de activación
        has_activation = False
        if self.activation_word and self.activation_word in text.lower():
            has_activation = True
            self.stats['activation_detected'] += 1
            self._emit_activation_detected(text)
        
        # Buscar comandos que coincidan
        matched_commands = []
        
        for (original_cmd, cmd_data, activation_part, command_part, pattern) in self.command_patterns:
            # Verificar si requiere activación
            if activation_part and not has_activation:
                continue
            
            # Buscar coincidencia
            if pattern.search(text):
                # Calcular confianza (simplificado)
                confidence = self._calculate_confidence(text, command_part)
                
                matched_commands.append({
                    'original_command': original_cmd,
                    'command_data': cmd_data,
                    'matched_text': text,
                    'confidence': confidence,
                    'timestamp': time.time()
                })
        
        # Procesar mejor coincidencia
        if matched_commands:
            # Ordenar por confianza (mayor primero)
            matched_commands.sort(key=lambda x: x['confidence'], reverse=True)
            best_match = matched_commands[0]
            
            # Verificar confianza mínima
            min_confidence = 0.5  # Configurable
            if best_match['confidence'] >= min_confidence:
                self._enqueue_command(best_match)
            else:
                logger.debug(f"⚠️ Comando '{best_match['matched_text']}' con confianza baja: {best_match['confidence']:.2f}")
        else:
            # Log de texto no reconocido (solo si tiene palabra de activación)
            if has_activation:
                logger.info(f"❓ Comando no reconocido: '{text}'")
    
    def _calculate_confidence(self, recognized: str, expected: str) -> float:
        """
        Calcula confianza de coincidencia entre texto reconocido y esperado.
        
        Args:
            recognized: Texto reconocido
            expected: Texto esperado
            
        Returns:
            Confianza entre 0.0 y 1.0
        """
        recognized_lower = recognized.lower()
        expected_lower = expected.lower()
        
        # Coincidencia exacta
        if expected_lower in recognized_lower:
            return 0.9
        
        # Coincidencia de palabras clave
        expected_words = set(expected_lower.split())
        recognized_words = set(recognized_lower.split())
        
        common_words = expected_words.intersection(recognized_words)
        if common_words:
            return len(common_words) / len(expected_words) * 0.8
        
        # Coincidencia parcial
        for word in expected_words:
            if any(word in r_word for r_word in recognized_words):
                return 0.5
        
        return 0.3
    
    def _enqueue_command(self, command_match: Dict):
        """
        Encuela un comando válido para procesamiento.
        
        Args:
            command_match: Datos del comando coincidente
        """
        command_data = command_match['command_data']
        
        # Crear comando para NYX
        command = {
            'type': 'voice',
            'command': command_data.get('command', ''),
            'action': command_data.get('action', 'unknown'),
            'description': command_data.get('description', command_match['original_command']),
            'voice_text': command_match['matched_text'],
            'original_command': command_match['original_command'],
            'confidence': command_match['confidence'],
            'timestamp': command_match['timestamp'],
            'profile': 'active'  # Será reemplazado por el perfil real
        }
        
        try:
            self.command_queue.put_nowait(command)
            self.stats['valid_commands'] += 1
            self.stats['last_command_time'] = time.time()
            
            logger.info(f"✅ Comando de voz detectado: {command_match['original_command']} "
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
                command = self.command_queue.get(timeout=0.5)
                if not command:
                    continue
                
                # Estado: procesando
                self.state = VoiceState.PROCESSING
                
                # Enviar a la cola de acciones de NYX
                try:
                    self.action_queue.put_nowait(command)
                    logger.debug(f"📤 Comando enviado a ActionExecutor: {command.get('description')}")
                except queue.Full:
                    logger.warning("⚠️ Cola de acciones llena, descartando comando de voz")
                
                # Volver a estado listo
                self.state = VoiceState.READY
                
                self.command_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Error en processing loop: {e}")
                self.stats['processing_errors'] += 1
        
        logger.info("🔄 Bucle de procesamiento de comandos terminado")
    
    def listen(self) -> Optional[Dict]:
        """
        Escucha y retorna el próximo comando de voz.
        
        Returns:
            Comando de voz o None si no hay
        """
        try:
            return self.command_queue.get(timeout=0.1)
        except queue.Empty:
            return None
    
    def get_action(self) -> Optional[Dict]:
        """
        Obtiene la próxima acción de voz para ejecutar.
        
        Returns:
            Acción de voz o None si no hay
        """
        try:
            return self.action_queue.get(timeout=0.1)
        except queue.Empty:
            return None
    
    def add_callback(self, callback_type: str, callback: Callable):
        """
        Agrega un callback para eventos de voz.
        
        Args:
            callback_type: Tipo de callback (on_command, on_activation, on_error, on_state_change)
            callback: Función callback
        """
        if callback_type in self.callbacks and callback not in self.callbacks[callback_type]:
            self.callbacks[callback_type].append(callback)
    
    def remove_callback(self, callback_type: str, callback: Callable):
        """Remueve un callback."""
        if callback_type in self.callbacks and callback in self.callbacks[callback_type]:
            self.callbacks[callback_type].remove(callback)
    
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
    
    def _clear_queues(self):
        """Limpia todas las colas."""
        for q in [self.command_queue, self.action_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except (queue.Empty, queue.Full):
                    break
    
    def update_config(self, new_config: Dict):
        """Actualiza configuración dinámicamente."""
        voice_config = new_config.get('voice_recognition', {})
        
        if 'activation_word' in voice_config:
            self.activation_word = voice_config['activation_word'].lower()
            logger.info(f"🔄 Palabra de activación cambiada a: '{self.activation_word}'")
        
        if 'language' in voice_config:
            self.language = voice_config['language']
            logger.info(f"🔄 Idioma cambiado a: {self.language}")
        
        if 'enabled' in voice_config:
            was_enabled = self.enabled
            self.enabled = voice_config['enabled']
            
            if was_enabled and not self.enabled:
                self.stop()
            elif not was_enabled and self.enabled:
                self.start()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas para NYX UI."""
        stats = self.stats.copy()
        stats.update({
            'state': self.state.value,
            'enabled': self.enabled,
            'microphone_available': self.microphone_available,
            'speech_recognition_available': self.speech_recognition_available,
            'calibrated': self.calibrated,
            'voice_commands_count': len(self.voice_commands),
            'command_patterns_count': len(self.command_patterns),
            'command_queue_size': self.command_queue.qsize(),
            'action_queue_size': self.action_queue.qsize(),
            'uptime_seconds': time.time() - self.stats['uptime'],
            'activation_word': self.activation_word,
            'language': self.language
        })
        return stats
    
    def get_state(self) -> VoiceState:
        """Obtiene el estado actual."""
        return self.state
    
    def is_available(self) -> bool:
        """Verifica si el reconocimiento de voz está disponible."""
        return self.speech_recognition_available and self.enabled
    
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
            test_microphone = sr.Microphone()
            
            with test_microphone as source:
                # Calibrar
                logger.info("🔊 Calibrando para prueba...")
                test_recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Escuchar
                logger.info("🎤 Habla ahora...")
                audio = test_recognizer.listen(source, timeout=5, phrase_time_limit=3)
                
                # Reconocer
                text = test_recognizer.recognize_google(audio, language=self.language)
                
                return True, f"Micrófono funciona. Reconocido: '{text}'"
                
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                return False, "No se detectó voz (timeout)"
            elif "recognize" in error_msg.lower():
                return False, "No se pudo reconocer voz (posible ruido)"
            else:
                return False, f"Error: {error_msg}"
    
    def cleanup(self):
        """Limpia recursos del reconocedor."""
        self.stop()
        self._clear_queues()
        
        # Limpiar callbacks
        for callback_list in self.callbacks.values():
            callback_list.clear()
        
        # Limpiar módulos
        self.recognizer = None
        self.microphone = None
        
        logger.info("✅ VoiceRecognizer limpiado")


# Uso en NYX
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configuración de prueba
    test_config = {
        'voice_recognition': {
            'enabled': True,
            'activation_word': 'nyx',
            'language': 'es-ES',
            'energy_threshold': 300,
            'pause_threshold': 0.8,
            'dynamic_energy_threshold': True
        }
    }
    
    # Comandos de voz de prueba (simulando perfil gamer)
    test_voice_commands = {
        'nyx abre discord': {
            'action': 'bash',
            'command': 'discord',
            'description': 'Abrir Discord',
            'enabled': True
        },
        'nyx captura pantalla': {
            'action': 'bash',
            'command': 'gnome-screenshot',
            'description': 'Tomar screenshot',
            'enabled': True
        },
        'nyx cierra ventana': {
            'action': 'keyboard',
            'command': 'alt+f4',
            'description': 'Cerrar ventana',
            'enabled': True
        }
    }
    
    print("🎤 Probando VoiceRecognizer para NYX...")
    
    # Crear reconocedor
    recognizer = VoiceRecognizer(test_config)
    
    # Configurar comandos de voz
    recognizer.set_voice_commands(test_voice_commands)
    
    # Mostrar estado
    print(f"\n📊 Estado inicial:")
    print(f"  Disponible: {recognizer.is_available()}")
    print(f"  Palabra activación: '{recognizer.activation_word}'")
    print(f"  Comandos configurados: {len(test_voice_commands)}")
    
    # Probar micrófono (simulado)
    print("\n🔊 Probando micrófono (simulado)...")
    success, message = recognizer.test_microphone()
    print(f"  {'✅' if success else '❌'} {message}")
    
    # Mostrar patrones generados
    print(f"\n🔍 Patrones de reconocimiento generados: {len(recognizer.command_patterns)}")
    
    # Simular procesamiento de texto
    print("\n🧪 Simulando reconocimiento de comandos:")
    test_phrases = [
        "nyx abre discord por favor",
        "nyx captura la pantalla",
        "nyx cierra esa ventana",
        "hola mundo",  # No debería reconocer
        "abre discord"  # Sin palabra de activación
    ]
    
    for phrase in test_phrases:
        print(f"  Prueba: '{phrase}'")
        recognizer._process_recognized_text(phrase)
    
    # Mostrar estadísticas
    stats = recognizer.get_stats()
    print(f"\n📊 Estadísticas después de pruebas:")
    print(f"  Comandos totales: {stats['total_commands']}")
    print(f"  Comandos válidos: {stats['valid_commands']}")
    print(f"  Activaciones: {stats['activation_detected']}")
    
    # Limpiar
    recognizer.cleanup()
    print("\n✅ Prueba de VoiceRecognizer completada")