"""
🎭 PROFILE RUNTIME - Gestor de perfiles en tiempo de ejecución para NYX
=======================================================================
Maneja la carga, validación, búsqueda y activación de perfiles durante la ejecución.
Es el puente CRÍTICO entre detección de gestos y ejecución de acciones.
"""

import json
import os
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
import threading
from collections import defaultdict
import copy

logger = logging.getLogger(__name__)


@dataclass
class GestureConfig:
    """Configuración completa de un gesto para NYX."""
    name: str
    action: str                    # keyboard, mouse, bash, window
    command: str                   # Comando a ejecutar
    description: str = ""
    source: str = "hand"           # Fuente: hand, arm, pose
    hand: str = "right"            # right, left, both, any
    enabled: bool = True
    confidence: float = 0.7        # Confianza mínima requerida
    cooldown: float = 0.3          # Tiempo entre ejecuciones
    last_executed: float = 0.0     # Timestamp de última ejecución
    parameters: Dict[str, Any] = field(default_factory=dict)  # Parámetros adicionales
    
    def can_execute(self, detected_hand: str = None, confidence: float = 0.0) -> Tuple[bool, str]:
        """
        Verifica si el gesto puede ejecutarse.
        
        Args:
            detected_hand: Mano detectada (right, left, both)
            confidence: Confianza de detección
            
        Returns:
            (puede_ejecutar, motivo)
        """
        # 1. Verificar si está habilitado
        if not self.enabled:
            return False, "Gesto deshabilitado"
        
        # 2. Verificar confianza mínima
        if confidence < self.confidence:
            return False, f"Confianza insuficiente ({confidence:.2f} < {self.confidence:.2f})"
        
        # 3. Verificar tipo de mano
        if self.hand != "any" and detected_hand and self.hand != detected_hand:
            # Verificar si es "both" y detectamos "right" o "left"
            if self.hand == "both" and detected_hand in ["right", "left"]:
                pass  # Permitir si es "both" y detectamos una mano
            else:
                return False, f"Mano incorrecta ({detected_hand} != {self.hand})"
        
        # 4. Verificar cooldown
        current_time = time.time()
        if current_time - self.last_executed < self.cooldown:
            remaining = self.cooldown - (current_time - self.last_executed)
            return False, f"En cooldown ({remaining:.1f}s restantes)"
        
        return True, "OK"
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return asdict(self)
    
    def copy(self) -> 'GestureConfig':
        """Crea una copia del objeto."""
        return copy.deepcopy(self)


@dataclass
class VoiceCommandConfig:
    """Configuración de un comando de voz para NYX."""
    trigger: str                   # Texto que activa el comando
    action: str                    # keyboard, mouse, bash, window
    command: str                   # Comando a ejecutar
    description: str = ""
    enabled: bool = True
    requires_activation: bool = True  # Requiere "nyx" antes del comando
    confidence_threshold: float = 0.6  # Umbral de confianza para reconocimiento
    cooldown: float = 0.0          # Tiempo entre ejecuciones
    last_executed: float = 0.0     # Timestamp de última ejecución
    parameters: Dict[str, Any] = field(default_factory=dict)  # Parámetros adicionales
    
    def matches(self, spoken_text: str, activation_word: str = "nyx") -> Tuple[bool, float]:
        """
        Verifica si el comando coincide con el texto hablado.
        
        Args:
            spoken_text: Texto detectado por voz
            activation_word: Palabra de activación
            
        Returns:
            (coincide, puntuación_coincidencia)
        """
        if not self.enabled:
            return False, 0.0
        
        spoken_text = spoken_text.lower().strip()
        trigger = self.trigger.lower().strip()
        
        # Si requiere palabra de activación
        if self.requires_activation:
            # Verificar formato: "nyx comando"
            expected = f"{activation_word} {trigger}"
            if expected in spoken_text:
                return True, 1.0
            # También verificar si el trigger está solo
            elif trigger in spoken_text:
                return True, 0.8
        else:
            # Coincidencia directa
            if trigger in spoken_text:
                return True, 1.0
        
        # Verificar coincidencia parcial
        words_spoken = spoken_text.split()
        words_trigger = trigger.split()
        
        if words_trigger and all(word in spoken_text for word in words_trigger):
            return True, 0.7
        
        return False, 0.0
    
    def can_execute(self, confidence: float = 0.0) -> Tuple[bool, str]:
        """
        Verifica si el comando de voz puede ejecutarse.
        
        Args:
            confidence: Confianza de reconocimiento
            
        Returns:
            (puede_ejecutar, motivo)
        """
        if not self.enabled:
            return False, "Comando deshabilitado"
        
        if confidence < self.confidence_threshold:
            return False, f"Confianza insuficiente ({confidence:.2f} < {self.confidence_threshold:.2f})"
        
        current_time = time.time()
        if current_time - self.last_executed < self.cooldown:
            remaining = self.cooldown - (current_time - self.last_executed)
            return False, f"En cooldown ({remaining:.1f}s restantes)"
        
        return True, "OK"
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return asdict(self)
    
    def copy(self) -> 'VoiceCommandConfig':
        """Crea una copia del objeto."""
        return copy.deepcopy(self)


class ProfileRuntime:
    """Gestor de perfiles en tiempo de ejecución para NYX."""
    
    def __init__(self, profile_data: Dict[str, Any] = None, profile_name: str = None):
        """
        Inicializa el runtime del perfil.
        
        Args:
            profile_data: Datos del perfil a cargar
            profile_name: Nombre del perfil (si no está en profile_data)
        """
        # Información del perfil
        self.name = profile_name or "default"
        self.description = "Perfil por defecto"
        self.version = "1.0.0"
        self.author = "NYX Sistema"
        self.file_path = None
        
        # Estructura del perfil
        self.gestures: Dict[str, GestureConfig] = {}          # Gestos configurados
        self.voice_commands: Dict[str, VoiceCommandConfig] = {}  # Comandos de voz
        self.settings: Dict[str, Any] = {}                    # Configuración
        self.enabled_modules: List[str] = []                  # Módulos habilitados
        
        # Callbacks para integración
        self.on_profile_changed: Optional[Callable] = None    # Callback cuando cambia el perfil
        self.on_gesture_executed: Optional[Callable] = None   # Callback cuando se ejecuta gesto
        self.on_voice_executed: Optional[Callable] = None     # Callback cuando se ejecuta voz
        
        # Cache y estado
        self._gesture_cache: Dict[str, GestureConfig] = {}    # Cache por nombre
        self._hand_gestures: Dict[str, List[str]] = {         # Gestos por mano
            'right': [],
            'left': [],
            'both': [],
            'any': []
        }
        self._source_gestures: Dict[str, List[str]] = {       # Gestos por fuente
            'hand': [],
            'arm': [],
            'pose': [],
            'voice': []
        }
        self._voice_cache: Dict[str, VoiceCommandConfig] = {} # Cache de comandos
        self._action_cache: Dict[str, Dict] = {}              # Cache de acciones
        
        # Estadísticas
        self.stats = {
            'gestures_loaded': 0,
            'voice_commands_loaded': 0,
            'gestures_executed': 0,
            'voice_commands_executed': 0,
            'last_execution': 0.0,
            'load_time': time.time(),
            'execution_history': []
        }
        
        # Bloqueo para acceso concurrente
        self._lock = threading.RLock()
        
        # Cargar perfil si se proporciona
        if profile_data:
            self.load_profile_data(profile_data)
        else:
            # Cargar perfil por defecto
            self.load_profile("gamer")
        
        logger.info(f"✅ ProfileRuntime inicializado: {self.name}")
    
    def load_profile(self, profile_name: str) -> bool:
        """
        Carga un perfil desde archivo.
        
        Args:
            profile_name: Nombre del perfil
            
        Returns:
            True si se cargó correctamente
        """
        try:
            # Buscar archivo de perfil
            profiles_dir = os.path.join('src', 'config', 'profiles')
            profile_path = os.path.join(profiles_dir, f"{profile_name}.json")
            
            if not os.path.exists(profile_path):
                # Intentar con extensión .yaml
                profile_path = os.path.join(profiles_dir, f"{profile_name}.yaml")
                if not os.path.exists(profile_path):
                    logger.error(f"❌ Perfil no encontrado: {profile_name}")
                    return False
            
            # Cargar archivo
            if profile_path.endswith('.json'):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
            else:
                import yaml
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile_data = yaml.safe_load(f)
            
            # Cargar datos
            self.file_path = profile_path
            success = self.load_profile_data(profile_data)
            
            if success:
                logger.info(f"✅ Perfil '{profile_name}' cargado correctamente")
                # Notificar cambio de perfil
                if self.on_profile_changed:
                    self.on_profile_changed(self.name, profile_path)
                return True
            else:
                logger.error(f"❌ Error cargando perfil {profile_name}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error cargando perfil {profile_name}: {e}")
            return False
    
    def load_profile_data(self, profile_data: Dict[str, Any]) -> bool:
        """
        Carga datos de un perfil con validación completa.
        
        Args:
            profile_data: Diccionario con datos del perfil
            
        Returns:
            True si se cargó correctamente
        """
        with self._lock:
            try:
                # 1. Información básica
                self.name = profile_data.get('profile_name', self.name)
                self.description = profile_data.get('description', self.description)
                self.version = profile_data.get('version', self.version)
                self.author = profile_data.get('author', self.author)
                
                # 2. Cargar gestos con validación
                raw_gestures = profile_data.get('gestures', {})
                self._load_gestures(raw_gestures)
                
                # 3. Cargar comandos de voz
                raw_voice = profile_data.get('voice_commands', {})
                self._load_voice_commands(raw_voice)
                
                # 4. Configuración
                self.settings = profile_data.get('settings', {})
                
                # 5. Módulos habilitados
                self.enabled_modules = profile_data.get('enabled_modules', [])
                
                # 6. Normalizar configuración
                self._normalize_settings()
                
                # 7. Construir índices para búsqueda rápida
                self._build_indices()
                
                # 8. Pre-cache de acciones
                self._build_action_cache()
                
                # 9. Actualizar estadísticas
                self.stats['gestures_loaded'] = len(self.gestures)
                self.stats['voice_commands_loaded'] = len(self.voice_commands)
                
                logger.info(f"📋 Perfil '{self.name}' cargado: "
                           f"{len(self.gestures)} gestos, "
                           f"{len(self.voice_commands)} comandos voz")
                
                # Log de configuración
                logger.debug(f"⚙️ Configuración: {self.settings}")
                logger.debug(f"🔧 Módulos habilitados: {self.enabled_modules}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error cargando perfil '{self.name}': {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
    
    def _load_gestures(self, raw_gestures: Dict[str, Dict]):
        """Carga y valida gestos desde datos crudos."""
        self.gestures.clear()
        self._gesture_cache.clear()
        
        for gesture_name, gesture_data in raw_gestures.items():
            try:
                # Validar campos obligatorios
                if 'action' not in gesture_data or 'command' not in gesture_data:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' sin acción/comando, omitiendo")
                    continue
                
                # Crear configuración de gesto
                gesture = GestureConfig(
                    name=gesture_name,
                    action=gesture_data.get('action', 'unknown'),
                    command=gesture_data.get('command', ''),
                    description=gesture_data.get('description', gesture_name),
                    source=gesture_data.get('source', 'hand').lower(),
                    hand=gesture_data.get('hand', 'right').lower(),
                    enabled=gesture_data.get('enabled', True),
                    confidence=float(gesture_data.get('confidence', 0.7)),
                    cooldown=float(gesture_data.get('cooldown', 0.3)),
                    parameters=gesture_data.get('parameters', {})
                )
                
                # Validar valores
                if gesture.hand not in ['right', 'left', 'both', 'any']:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' con mano inválida: {gesture.hand}")
                    gesture.hand = 'right'
                
                if gesture.source not in ['hand', 'arm', 'pose']:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' con fuente inválida: {gesture.source}")
                    gesture.source = 'hand'
                
                if not 0 <= gesture.confidence <= 1:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' con confianza inválida: {gesture.confidence}")
                    gesture.confidence = 0.7
                
                # Guardar gesto
                self.gestures[gesture_name] = gesture
                self._gesture_cache[gesture_name] = gesture
                
            except Exception as e:
                logger.error(f"❌ Error procesando gesto '{gesture_name}': {e}")
                continue
    
    def _load_voice_commands(self, raw_voice: Dict[str, Dict]):
        """Carga y valida comandos de voz."""
        self.voice_commands.clear()
        self._voice_cache.clear()
        
        for trigger, voice_data in raw_voice.items():
            try:
                # Validar campos obligatorios
                if 'action' not in voice_data or 'command' not in voice_data:
                    logger.warning(f"⚠️ Comando voz '{trigger}' sin acción/comando, omitiendo")
                    continue
                
                # Crear configuración de comando
                voice_cmd = VoiceCommandConfig(
                    trigger=trigger,
                    action=voice_data.get('action', 'unknown'),
                    command=voice_data.get('command', ''),
                    description=voice_data.get('description', trigger),
                    enabled=voice_data.get('enabled', True),
                    requires_activation=voice_data.get('requires_activation', True),
                    confidence_threshold=float(voice_data.get('confidence_threshold', 0.6)),
                    cooldown=float(voice_data.get('cooldown', 0.0)),
                    parameters=voice_data.get('parameters', {})
                )
                
                # Guardar comando
                self.voice_commands[trigger] = voice_cmd
                self._voice_cache[trigger] = voice_cmd
                
            except Exception as e:
                logger.error(f"❌ Error procesando comando voz '{trigger}': {e}")
                continue
    
    def _normalize_settings(self):
        """Normaliza y completa la configuración."""
        # Configuración por defecto
        default_settings = {
            'mouse_sensitivity': 1.0,
            'keyboard_delay': 0.1,
            'gesture_cooldown': 0.3,
            'min_confidence': 0.5,
            'require_confirmation': False,
            'sound_feedback': True,
            'visual_feedback': True,
            'voice_activation_word': 'nyx',
            'auto_switch_profiles': False,
            'profile_switch_timeout': 300,  # 5 minutos
            'voice_recognition_engine': 'google',  # google, vosk, whisper
            'voice_timeout': 3.0,  # Tiempo de silencio para fin de frase
            'voice_language': 'es-ES',
            'voice_confidence': 0.7,
            'hotkeys_enabled': True,
            'hotkey_modifier': 'ctrl+shift',
            'profiles_directory': 'src/config/profiles',
            'backup_enabled': True,
            'backup_interval': 3600,  # 1 hora
            'auto_save': False,
            'log_level': 'INFO'
        }
        
        # Aplicar valores por defecto si no existen
        for key, default_value in default_settings.items():
            if key not in self.settings:
                self.settings[key] = default_value
        
        # Asegurar tipos correctos
        numeric_keys = ['mouse_sensitivity', 'keyboard_delay', 'gesture_cooldown', 
                       'min_confidence', 'profile_switch_timeout', 'voice_timeout',
                       'voice_confidence', 'backup_interval']
        
        for key in numeric_keys:
            if key in self.settings:
                try:
                    self.settings[key] = float(self.settings[key])
                except (ValueError, TypeError):
                    self.settings[key] = default_settings.get(key, 0.0)
    
    def _build_indices(self):
        """Construye índices para búsqueda rápida."""
        # Reiniciar índices
        self._hand_gestures = {'right': [], 'left': [], 'both': [], 'any': []}
        self._source_gestures = {'hand': [], 'arm': [], 'pose': [], 'voice': []}
        
        # Construir índices
        for gesture_name, gesture in self.gestures.items():
            if gesture.enabled:
                # Indexar por mano
                self._hand_gestures[gesture.hand].append(gesture_name)
                
                # Indexar por fuente
                if gesture.source in self._source_gestures:
                    self._source_gestures[gesture.source].append(gesture_name)
        
        # Indexar comandos de voz
        for trigger, voice_cmd in self.voice_commands.items():
            if voice_cmd.enabled:
                self._source_gestures['voice'].append(trigger)
    
    def _build_action_cache(self):
        """Construye cache de acciones para acceso rápido."""
        self._action_cache.clear()
        
        # Cache de gestos
        for gesture_name, gesture in self.gestures.items():
            if gesture.enabled:
                self._action_cache[f"gesture:{gesture_name}"] = {
                    'type': gesture.action,
                    'command': gesture.command,
                    'description': gesture.description,
                    'source': gesture.source,
                    'hand': gesture.hand,
                    'confidence': gesture.confidence,
                    'cooldown': gesture.cooldown,
                    'parameters': gesture.parameters
                }
        
        # Cache de comandos de voz
        for trigger, voice_cmd in self.voice_commands.items():
            if voice_cmd.enabled:
                self._action_cache[f"voice:{trigger}"] = {
                    'type': voice_cmd.action,
                    'command': voice_cmd.command,
                    'description': voice_cmd.description,
                    'requires_activation': voice_cmd.requires_activation,
                    'confidence_threshold': voice_cmd.confidence_threshold,
                    'cooldown': voice_cmd.cooldown,
                    'parameters': voice_cmd.parameters
                }
    
    # ========== MÉTODOS DE INTEGRACIÓN CON GESTUREPIPELINE ==========
    
    def set_gesture_callback(self, callback: Callable):
        """
        Configura callback para cuando se ejecuta un gesto.
        
        Args:
            callback: Función que recibe (gesture_name, action_result)
        """
        self.on_gesture_executed = callback
    
    def set_voice_callback(self, callback: Callable):
        """
        Configura callback para cuando se ejecuta un comando de voz.
        
        Args:
            callback: Función que recibe (command_text, action_result)
        """
        self.on_voice_executed = callback
    
    def set_profile_change_callback(self, callback: Callable):
        """
        Configura callback para cuando cambia el perfil.
        
        Args:
            callback: Función que recibe (profile_name, profile_path)
        """
        self.on_profile_changed = callback
    
    def process_gesture(self, gesture_data: Dict) -> Optional[Dict]:
        """
        Procesa datos de gesto desde GesturePipeline.
        
        Args:
            gesture_data: Diccionario con datos del gesto detectado
            
        Returns:
            Acción a ejecutar o None
        """
        try:
            # Extraer datos del gesto
            gesture_name = gesture_data.get('gesture')
            source = gesture_data.get('source', 'hand')
            confidence = gesture_data.get('confidence', 0.0)
            hand_type = gesture_data.get('hand_type', 'right')
            
            if not gesture_name:
                return None
            
            # Obtener acción
            action = self.get_gesture_action(
                gesture_name=gesture_name,
                source=source,
                hand_type=hand_type,
                confidence=confidence
            )
            
            if action:
                # Registrar en historial
                self._add_to_history('gesture', gesture_name, action)
                
                # Notificar callback si existe
                if self.on_gesture_executed:
                    self.on_gesture_executed(gesture_name, action)
                
                logger.info(f"🎯 Gesto procesado: {gesture_name} -> {action.get('type', 'unknown')}")
            
            return action
            
        except Exception as e:
            logger.error(f"❌ Error procesando gesto: {e}")
            return None
    
    def process_voice_command(self, voice_data: Dict) -> Optional[Dict]:
        """
        Procesa comando de voz desde GesturePipeline.
        
        Args:
            voice_data: Diccionario con datos del comando de voz
            
        Returns:
            Acción a ejecutar o None
        """
        try:
            command_text = voice_data.get('text', '')
            confidence = voice_data.get('confidence', 1.0)
            
            if not command_text:
                return None
            
            # Obtener acción
            action = self.get_voice_action(command_text, confidence)
            
            if action:
                # Registrar en historial
                self._add_to_history('voice', command_text, action)
                
                # Notificar callback si existe
                if self.on_voice_executed:
                    self.on_voice_executed(command_text, action)
                
                logger.info(f"🎤 Comando voz procesado: '{command_text}' -> {action.get('type', 'unknown')}")
            
            return action
            
        except Exception as e:
            logger.error(f"❌ Error procesando comando voz: {e}")
            return None
    
    def _add_to_history(self, action_type: str, identifier: str, action: Dict):
        """Agrega acción al historial de ejecuciones."""
        with self._lock:
            entry = {
                'timestamp': time.time(),
                'type': action_type,
                'identifier': identifier,
                'action_type': action.get('type'),
                'command': action.get('command'),
                'profile': self.name,
                'confidence': action.get('confidence', 0.0)
            }
            
            self.stats['execution_history'].append(entry)
            
            # Mantener solo las últimas 1000 entradas
            if len(self.stats['execution_history']) > 1000:
                self.stats['execution_history'] = self.stats['execution_history'][-1000:]
    
    # ========== MÉTODOS DE BÚSQUEDA Y ACCIÓN ==========
    
    def get_gesture(self, gesture_name: str, source: str = None) -> Optional[GestureConfig]:
        """
        Obtiene configuración completa de un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente del gesto (hand, arm, pose)
            
        Returns:
            GestureConfig o None si no existe
        """
        with self._lock:
            if source:
                gesture_key = f"{source}_{gesture_name}"
                return self._gesture_cache.get(gesture_key)
            return self.gestures.get(gesture_name)
    
    def get_gesture_action(self, gesture_name: str, source: str = "hand", 
                          hand_type: str = None, confidence: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Obtiene acción para ejecutar basada en un gesto.
        
        Args:
            gesture_name: Nombre del gesto detectado
            source: Fuente del gesto (hand, arm, pose)
            hand_type: Tipo de mano detectada (right, left, both)
            confidence: Confianza de detección (0.0-1.0)
            
        Returns:
            Configuración de acción o None
        """
        with self._lock:
            # Obtener gesto
            gesture = self.get_gesture(gesture_name, source)
            if not gesture:
                return None
            
            # Verificar si puede ejecutarse
            can_execute, reason = gesture.can_execute(hand_type, confidence)
            if not can_execute:
                logger.debug(f"⚠️ Gesto '{gesture_name}' no ejecutable: {reason}")
                return None
            
            # Crear acción
            action = {
                'type': gesture.action,
                'command': gesture.command,
                'description': gesture.description,
                'gesture': gesture_name,
                'source': source,
                'hand': hand_type or gesture.hand,
                'confidence': confidence,
                'timestamp': time.time(),
                'profile': self.name,
                'parameters': gesture.parameters
            }
            
            # Actualizar timestamp de última ejecución
            gesture.last_executed = time.time()
            
            # Actualizar estadísticas
            self.stats['gestures_executed'] += 1
            self.stats['last_execution'] = time.time()
            
            return action
    
    def get_voice_command(self, command_text: str) -> Optional[VoiceCommandConfig]:
        """
        Obtiene configuración de un comando de voz.
        
        Args:
            command_text: Texto del comando
            
        Returns:
            VoiceCommandConfig o None si no existe
        """
        with self._lock:
            # Buscar coincidencia exacta primero
            for trigger, cmd in self.voice_commands.items():
                if cmd.enabled:
                    matches, score = cmd.matches(command_text, 
                                                self.settings.get('voice_activation_word', 'nyx'))
                    if matches and score > 0.8:
                        return cmd
            
            # Si no hay coincidencia exacta, buscar la mejor coincidencia
            best_match = None
            best_score = 0.0
            
            for trigger, cmd in self.voice_commands.items():
                if cmd.enabled:
                    matches, score = cmd.matches(command_text,
                                                self.settings.get('voice_activation_word', 'nyx'))
                    if matches and score > best_score:
                        best_score = score
                        best_match = cmd
            
            return best_match
    
    def get_voice_action(self, command_text: str, confidence: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Obtiene acción para ejecutar basada en comando de voz.
        
        Args:
            command_text: Texto del comando de voz
            confidence: Confianza de reconocimiento (0.0-1.0)
            
        Returns:
            Configuración de acción o None
        """
        with self._lock:
            # Buscar el mejor comando coincidente
            voice_cmd = self.get_voice_command(command_text)
            
            if not voice_cmd:
                return None
            
            # Verificar si puede ejecutarse
            can_execute, reason = voice_cmd.can_execute(confidence)
            if not can_execute:
                logger.debug(f"⚠️ Comando voz no ejecutable: {reason}")
                return None
            
            # Crear acción
            action = {
                'type': voice_cmd.action,
                'command': voice_cmd.command,
                'description': voice_cmd.description,
                'voice_command': command_text,
                'trigger': voice_cmd.trigger,
                'timestamp': time.time(),
                'profile': self.name,
                'confidence': confidence,
                'parameters': voice_cmd.parameters
            }
            
            # Actualizar timestamp de última ejecución
            voice_cmd.last_executed = time.time()
            
            # Actualizar estadísticas
            self.stats['voice_commands_executed'] += 1
            self.stats['last_execution'] = time.time()
            
            return action
    
    # ========== MÉTODOS DE BÚSQUEDA POR CRITERIOS ==========
    
    def get_gestures_by_hand(self, hand_type: str) -> List[str]:
        """
        Obtiene nombres de gestos configurados para una mano específica.
        
        Args:
            hand_type: Tipo de mano (right, left, both, any)
            
        Returns:
            Lista de nombres de gestos
        """
        with self._lock:
            return self._hand_gestures.get(hand_type, []).copy()
    
    def get_gestures_by_source(self, source_type: str) -> List[str]:
        """
        Obtiene nombres de gestos de una fuente específica.
        
        Args:
            source_type: Fuente del gesto (hand, arm, pose, voice)
            
        Returns:
            Lista de nombres de gestos
        """
        with self._lock:
            return self._source_gestures.get(source_type, []).copy()
    
    def get_gestures_by_action_type(self, action_type: str) -> List[str]:
        """
        Obtiene gestos por tipo de acción.
        
        Args:
            action_type: Tipo de acción (keyboard, mouse, bash, window)
            
        Returns:
            Lista de nombres de gestos
        """
        with self._lock:
            return [
                name for name, gesture in self.gestures.items()
                if gesture.enabled and gesture.action == action_type
            ]
    
    def get_gestures_with_low_confidence(self, threshold: float = 0.5) -> List[str]:
        """
        Obtiene gestos con confianza mínima baja.
        
        Args:
            threshold: Umbral de confianza
            
        Returns:
            Lista de nombres de gestos
        """
        with self._lock:
            return [
                name for name, gesture in self.gestures.items()
                if gesture.enabled and gesture.confidence < threshold
            ]
    
    # ========== MÉTODOS DE OBTENCIÓN DE DATOS ==========
    
    def get_config(self) -> Dict[str, Any]:
        """
        Obtiene toda la configuración del perfil.
        
        Returns:
            Diccionario con toda la configuración
        """
        with self._lock:
            return {
                'profile_name': self.name,
                'description': self.description,
                'version': self.version,
                'author': self.author,
                'settings': self.settings.copy(),
                'enabled_modules': self.enabled_modules.copy()
            }
    
    def get_all_gestures(self) -> Dict[str, Dict]:
        """
        Obtiene todos los gestos del perfil.
        Para compatibilidad con código existente.
        
        Returns:
            Diccionario con todos los gestos
        """
        with self._lock:
            gestures_dict = {}
            for name, gesture in self.gestures.items():
                if gesture.enabled:
                    gestures_dict[name] = {
                        'name': name,
                        'action': gesture.action,
                        'command': gesture.command,
                        'description': gesture.description,
                        'source': gesture.source,
                        'hand': gesture.hand,
                        'enabled': gesture.enabled,
                        'confidence': gesture.confidence,
                        'cooldown': gesture.cooldown,
                        'parameters': gesture.parameters,
                        'last_executed': gesture.last_executed
                    }
            return gestures_dict
    
    def get_all_gesture_configs(self) -> Dict[str, GestureConfig]:
        """
        Obtiene todos los gestos con sus configuraciones completas.
        
        Returns:
            Diccionario de nombre -> GestureConfig
        """
        with self._lock:
            return {name: gesture.copy() for name, gesture in self.gestures.items() 
                   if gesture.enabled}
    
    def get_voice_commands(self) -> Dict[str, Dict]:
        """
        Obtiene todos los comandos de voz habilitados.
        Compatible con el método que mencionaste.
        
        Returns:
            Diccionario de trigger -> configuración
        """
        with self._lock:
            commands_dict = {}
            for trigger, voice_cmd in self.voice_commands.items():
                if voice_cmd.enabled:
                    commands_dict[trigger] = {
                        'text': voice_cmd.trigger,
                        'action': voice_cmd.action,
                        'command': voice_cmd.command,
                        'description': voice_cmd.description,
                        'enabled': voice_cmd.enabled,
                        'requires_activation': voice_cmd.requires_activation,
                        'confidence_threshold': voice_cmd.confidence_threshold,
                        'cooldown': voice_cmd.cooldown,
                        'parameters': voice_cmd.parameters,
                        'last_executed': voice_cmd.last_executed
                    }
            return commands_dict
    
    def get_all_voice_command_configs(self) -> Dict[str, VoiceCommandConfig]:
        """
        Obtiene todos los comandos de voz con configuraciones completas.
        
        Returns:
            Diccionario de trigger -> VoiceCommandConfig
        """
        with self._lock:
            return {trigger: cmd.copy() for trigger, cmd in self.voice_commands.items() 
                   if cmd.enabled}
    
    # ========== MÉTODOS DE CONFIGURACIÓN ==========
    
    def is_module_enabled(self, module_name: str) -> bool:
        """
        Verifica si un módulo está habilitado en el perfil.
        
        Args:
            module_name: Nombre del módulo
            
        Returns:
            True si el módulo está habilitado
        """
        with self._lock:
            # Si no hay módulos especificados, todos están habilitados
            if not self.enabled_modules:
                return True
            
            return module_name in self.enabled_modules
    
    def get_enabled_modules(self) -> List[str]:
        """
        Obtiene lista de módulos habilitados.
        
        Returns:
            Lista de nombres de módulos
        """
        with self._lock:
            return self.enabled_modules.copy()
    
    def enable_module(self, module_name: str) -> bool:
        """
        Habilita un módulo en el perfil.
        
        Args:
            module_name: Nombre del módulo
            
        Returns:
            True si se habilitó correctamente
        """
        with self._lock:
            if module_name not in self.enabled_modules:
                self.enabled_modules.append(module_name)
                logger.info(f"✅ Módulo habilitado: {module_name}")
                return True
            return False
    
    def disable_module(self, module_name: str) -> bool:
        """
        Deshabilita un módulo en el perfil.
        
        Args:
            module_name: Nombre del módulo
            
        Returns:
            True si se deshabilitó correctamente
        """
        with self._lock:
            if module_name in self.enabled_modules:
                self.enabled_modules.remove(module_name)
                logger.info(f"⏸️ Módulo deshabilitado: {module_name}")
                return True
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.
        
        Args:
            key: Clave de configuración
            default: Valor por defecto si no existe
            
        Returns:
            Valor de configuración o default
        """
        with self._lock:
            return self.settings.get(key, default)
    
    def update_setting(self, key: str, value: Any):
        """
        Actualiza un valor de configuración.
        
        Args:
            key: Clave de configuración
            value: Nuevo valor
        """
        with self._lock:
            self.settings[key] = value
            logger.debug(f"⚙️ Configuración actualizada: {key} = {value}")
    
    def update_settings(self, updates: Dict[str, Any]):
        """
        Actualiza múltiples configuraciones.
        
        Args:
            updates: Diccionario con configuraciones a actualizar
        """
        with self._lock:
            self.settings.update(updates)
            logger.info(f"⚙️ {len(updates)} configuraciones actualizadas")
    
    # ========== MÉTODOS DE GESTIÓN DE GESTOS ==========
    
    def enable_gesture(self, gesture_name: str, source: str = None) -> bool:
        """
        Habilita un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente del gesto (opcional)
            
        Returns:
            True si se habilitó correctamente
        """
        with self._lock:
            gesture = self.get_gesture(gesture_name, source)
            if gesture:
                gesture.enabled = True
                self._build_indices()  # Reconstruir índices
                self._build_action_cache()  # Reconstruir cache
                logger.info(f"✅ Gesto habilitado: {gesture_name}")
                return True
            return False
    
    def disable_gesture(self, gesture_name: str, source: str = None) -> bool:
        """
        Deshabilita un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente del gesto (opcional)
            
        Returns:
            True si se deshabilitó correctamente
        """
        with self._lock:
            gesture = self.get_gesture(gesture_name, source)
            if gesture:
                gesture.enabled = False
                self._build_indices()  # Reconstruir índices
                self._build_action_cache()  # Reconstruir cache
                logger.info(f"⏸️ Gesto deshabilitado: {gesture_name}")
                return True
            return False
    
    def add_gesture(self, gesture_name: str, gesture_config: Dict, source: str = "hand") -> bool:
        """
        Agrega un gesto al perfil.
        
        Args:
            gesture_name: Nombre del gesto
            gesture_config: Configuración del gesto
            source: Fuente del gesto
            
        Returns:
            True si se agregó correctamente
        """
        with self._lock:
            try:
                # Crear configuración de gesto
                gesture = GestureConfig(
                    name=gesture_name,
                    action=gesture_config.get('action', 'unknown'),
                    command=gesture_config.get('command', ''),
                    description=gesture_config.get('description', gesture_name),
                    source=source,
                    hand=gesture_config.get('hand', 'right'),
                    enabled=gesture_config.get('enabled', True),
                    confidence=float(gesture_config.get('confidence', 0.7)),
                    cooldown=float(gesture_config.get('cooldown', 0.3)),
                    parameters=gesture_config.get('parameters', {})
                )
                
                # Guardar gesto
                self.gestures[gesture_name] = gesture
                self._build_indices()
                self._build_action_cache()
                
                logger.info(f"➕ Gesto agregado: {gesture_name}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error agregando gesto '{gesture_name}': {e}")
                return False
    
    def remove_gesture(self, gesture_name: str, source: str = None) -> bool:
        """
        Elimina un gesto del perfil.
        
        Args:
            gesture_name: Nombre del gesto
            source: Fuente del gesto (opcional)
            
        Returns:
            True si se eliminó correctamente
        """
        with self._lock:
            if gesture_name in self.gestures:
                del self.gestures[gesture_name]
                self._build_indices()
                self._build_action_cache()
                logger.info(f"➖ Gesto eliminado: {gesture_name}")
                return True
            return False
    
    def update_gesture(self, gesture_name: str, updates: Dict, source: str = None) -> bool:
        """
        Actualiza un gesto existente.
        
        Args:
            gesture_name: Nombre del gesto
            updates: Diccionario con campos a actualizar
            source: Fuente del gesto (opcional)
            
        Returns:
            True si se actualizó correctamente
        """
        with self._lock:
            gesture = self.get_gesture(gesture_name, source)
            if not gesture:
                return False
            
            # Actualizar campos permitidos
            for key, value in updates.items():
                if hasattr(gesture, key):
                    setattr(gesture, key, value)
            
            self._build_indices()
            self._build_action_cache()
            
            logger.info(f"✏️ Gesto actualizado: {gesture_name}")
            return True
    
    # ========== MÉTODOS DE GESTIÓN DE COMANDOS DE VOZ ==========
    
    def enable_voice_command(self, trigger: str) -> bool:
        """
        Habilita un comando de voz.
        
        Args:
            trigger: Texto que activa el comando
            
        Returns:
            True si se habilitó correctamente
        """
        with self._lock:
            if trigger in self.voice_commands:
                self.voice_commands[trigger].enabled = True
                self._build_indices()
                self._build_action_cache()
                logger.info(f"✅ Comando voz habilitado: {trigger}")
                return True
            return False
    
    def disable_voice_command(self, trigger: str) -> bool:
        """
        Deshabilita un comando de voz.
        
        Args:
            trigger: Texto que activa el comando
            
        Returns:
            True si se deshabilitó correctamente
        """
        with self._lock:
            if trigger in self.voice_commands:
                self.voice_commands[trigger].enabled = False
                self._build_indices()
                self._build_action_cache()
                logger.info(f"⏸️ Comando voz deshabilitado: {trigger}")
                return True
            return False
    
    def add_voice_command(self, trigger: str, voice_config: Dict) -> bool:
        """
        Agrega un comando de voz al perfil.
        
        Args:
            trigger: Texto que activa el comando
            voice_config: Configuración del comando
            
        Returns:
            True si se agregó correctamente
        """
        with self._lock:
            try:
                # Crear configuración de comando
                voice_cmd = VoiceCommandConfig(
                    trigger=trigger,
                    action=voice_config.get('action', 'unknown'),
                    command=voice_config.get('command', ''),
                    description=voice_config.get('description', trigger),
                    enabled=voice_config.get('enabled', True),
                    requires_activation=voice_config.get('requires_activation', True),
                    confidence_threshold=float(voice_config.get('confidence_threshold', 0.6)),
                    cooldown=float(voice_config.get('cooldown', 0.0)),
                    parameters=voice_config.get('parameters', {})
                )
                
                # Guardar comando
                self.voice_commands[trigger] = voice_cmd
                self._build_indices()
                self._build_action_cache()
                
                logger.info(f"➕ Comando voz agregado: {trigger}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error agregando comando voz '{trigger}': {e}")
                return False
    
    def remove_voice_command(self, trigger: str) -> bool:
        """
        Elimina un comando de voz del perfil.
        
        Args:
            trigger: Texto que activa el comando
            
        Returns:
            True si se eliminó correctamente
        """
        with self._lock:
            if trigger in self.voice_commands:
                del self.voice_commands[trigger]
                self._build_indices()
                self._build_action_cache()
                logger.info(f"➖ Comando voz eliminado: {trigger}")
                return True
            return False
    
    def update_voice_command(self, trigger: str, updates: Dict) -> bool:
        """
        Actualiza un comando de voz existente.
        
        Args:
            trigger: Texto que activa el comando
            updates: Diccionario con campos a actualizar
            
        Returns:
            True si se actualizó correctamente
        """
        with self._lock:
            if trigger not in self.voice_commands:
                return False
            
            voice_cmd = self.voice_commands[trigger]
            
            # Actualizar campos permitidos
            for key, value in updates.items():
                if hasattr(voice_cmd, key):
                    setattr(voice_cmd, key, value)
            
            self._build_indices()
            self._build_action_cache()
            
            logger.info(f"✏️ Comando voz actualizado: {trigger}")
            return True
    
    # ========== MÉTODOS DE ESTADÍSTICAS ==========
    
    def get_gesture_count(self) -> int:
        """Obtiene número total de gestos."""
        with self._lock:
            return len(self.gestures)
    
    def get_enabled_gesture_count(self) -> int:
        """Obtiene número de gestos habilitados."""
        with self._lock:
            return len([g for g in self.gestures.values() if g.enabled])
    
    def get_voice_command_count(self) -> int:
        """Obtiene número total de comandos de voz."""
        with self._lock:
            return len(self.voice_commands)
    
    def get_enabled_voice_command_count(self) -> int:
        """Obtiene número de comandos de voz habilitados."""
        with self._lock:
            return len([c for c in self.voice_commands.values() if c.enabled])
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del runtime."""
        with self._lock:
            stats = self.stats.copy()
            stats.update({
                'name': self.name,
                'gesture_count': self.get_gesture_count(),
                'enabled_gesture_count': self.get_enabled_gesture_count(),
                'voice_command_count': self.get_voice_command_count(),
                'enabled_voice_command_count': self.get_enabled_voice_command_count(),
                'enabled_modules': self.enabled_modules.copy(),
                'uptime': time.time() - self.stats['load_time'],
                'history_size': len(self.stats['execution_history']),
                'settings_count': len(self.settings)
            })
            return stats
    
    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        """
        Obtiene historial de ejecuciones.
        
        Args:
            limit: Número máximo de entradas a devolver
            
        Returns:
            Lista de entradas del historial
        """
        with self._lock:
            history = self.stats['execution_history'][-limit:] if limit else self.stats['execution_history']
            return [entry.copy() for entry in history]
    
    def clear_stats(self):
        """Limpia estadísticas de ejecución."""
        with self._lock:
            self.stats.update({
                'gestures_executed': 0,
                'voice_commands_executed': 0,
                'last_execution': 0.0,
                'execution_history': []
            })
            logger.info("📊 Estadísticas limpiadas")
    
    # ========== MÉTODOS DE PERSISTENCIA ==========
    
    def save_profile(self, profile_name: str = None) -> bool:
        """
        Guarda el perfil actual.
        
        Args:
            profile_name: Nombre del perfil (si None, usa el actual)
            
        Returns:
            True si se guardó correctamente
        """
        with self._lock:
            try:
                if profile_name:
                    self.name = profile_name
                
                # Convertir a diccionario
                profile_dict = self.to_dict()
                
                # Guardar archivo
                profiles_dir = os.path.join('src', 'config', 'profiles')
                os.makedirs(profiles_dir, exist_ok=True)
                
                profile_path = os.path.join(profiles_dir, f"{self.name}.json")
                with open(profile_path, 'w', encoding='utf-8') as f:
                    json.dump(profile_dict, f, indent=2, ensure_ascii=False)
                
                self.file_path = profile_path
                logger.info(f"💾 Perfil '{self.name}' guardado correctamente")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error guardando perfil: {e}")
                return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el perfil a diccionario para guardar.
        
        Returns:
            Diccionario compatible con formato JSON de NYX
        """
        with self._lock:
            # Convertir gestos
            gestures_dict = {}
            for name, gesture in self.gestures.items():
                gestures_dict[name] = {
                    'action': gesture.action,
                    'command': gesture.command,
                    'description': gesture.description,
                    'source': gesture.source,
                    'hand': gesture.hand,
                    'enabled': gesture.enabled,
                    'confidence': gesture.confidence,
                    'cooldown': gesture.cooldown,
                    'parameters': gesture.parameters
                }
            
            # Convertir comandos de voz
            voice_dict = {}
            for trigger, voice_cmd in self.voice_commands.items():
                voice_dict[trigger] = {
                    'action': voice_cmd.action,
                    'command': voice_cmd.command,
                    'description': voice_cmd.description,
                    'enabled': voice_cmd.enabled,
                    'requires_activation': voice_cmd.requires_activation,
                    'confidence_threshold': voice_cmd.confidence_threshold,
                    'cooldown': voice_cmd.cooldown,
                    'parameters': voice_cmd.parameters
                }
            
            return {
                'profile_name': self.name,
                'description': self.description,
                'version': self.version,
                'author': self.author,
                'gestures': gestures_dict,
                'voice_commands': voice_dict,
                'settings': self.settings,
                'enabled_modules': self.enabled_modules
            }
    
    # ========== MÉTODOS DE UTILIDAD ==========
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Valida la integridad del perfil.
        
        Returns:
            (es_válido, lista_de_errores)
        """
        errors = []
        
        with self._lock:
            # Validar gestos
            for name, gesture in self.gestures.items():
                if not gesture.action:
                    errors.append(f"Gesto '{name}' sin acción definida")
                if not gesture.command:
                    errors.append(f"Gesto '{name}' sin comando definido")
                if gesture.confidence < 0 or gesture.confidence > 1:
                    errors.append(f"Gesto '{name}' con confianza inválida: {gesture.confidence}")
            
            # Validar comandos de voz
            for trigger, cmd in self.voice_commands.items():
                if not cmd.action:
                    errors.append(f"Comando voz '{trigger}' sin acción definida")
                if not cmd.command:
                    errors.append(f"Comando voz '{trigger}' sin comando definido")
            
            # Validar configuración
            if not self.settings.get('voice_activation_word'):
                errors.append("No hay palabra de activación de voz configurada")
        
        return len(errors) == 0, errors
    
    def export_for_ui(self) -> Dict[str, Any]:
        """
        Exporta datos del perfil para interfaz de usuario.
        
        Returns:
            Diccionario con datos formateados para UI
        """
        with self._lock:
            return {
                'profile_info': {
                    'name': self.name,
                    'description': self.description,
                    'version': self.version,
                    'author': self.author,
                    'file_path': self.file_path,
                    'load_time': time.strftime('%Y-%m-%d %H:%M:%S', 
                                              time.localtime(self.stats['load_time'])),
                    'is_valid': self.validate()[0]
                },
                'gestures': [
                    {
                        'name': name,
                        'action': gesture.action,
                        'command': gesture.command,
                        'description': gesture.description,
                        'source': gesture.source,
                        'hand': gesture.hand,
                        'enabled': gesture.enabled,
                        'confidence': gesture.confidence,
                        'cooldown': gesture.cooldown,
                        'parameters': gesture.parameters,
                        'last_executed': gesture.last_executed
                    }
                    for name, gesture in self.gestures.items()
                ],
                'voice_commands': [
                    {
                        'trigger': trigger,
                        'action': cmd.action,
                        'command': cmd.command,
                        'description': cmd.description,
                        'enabled': cmd.enabled,
                        'requires_activation': cmd.requires_activation,
                        'confidence_threshold': cmd.confidence_threshold,
                        'cooldown': cmd.cooldown,
                        'parameters': cmd.parameters,
                        'last_executed': cmd.last_executed
                    }
                    for trigger, cmd in self.voice_commands.items()
                ],
                'settings': self.settings,
                'enabled_modules': self.enabled_modules,
                'stats': self.get_stats()
            }
    
    def get_available_profiles(self) -> List[str]:
        """
        Obtiene lista de perfiles disponibles.
        
        Returns:
            Lista de nombres de perfiles
        """
        profiles_dir = os.path.join('src', 'config', 'profiles')
        profiles = []
        
        if os.path.exists(profiles_dir):
            for file in os.listdir(profiles_dir):
                if file.endswith(('.json', '.yaml', '.yml')):
                    profile_name = os.path.splitext(file)[0]
                    profiles.append(profile_name)
        
        return sorted(profiles)
    
    def switch_profile(self, profile_name: str) -> bool:
        """
        Cambia a otro perfil.
        
        Args:
            profile_name: Nombre del perfil al que cambiar
            
        Returns:
            True si se cambió correctamente
        """
        return self.load_profile(profile_name)
    
    def create_backup(self) -> bool:
        """
        Crea una copia de seguridad del perfil actual.
        
        Returns:
            True si se creó correctamente
        """
        with self._lock:
            try:
                if not self.file_path:
                    return False
                
                # Crear directorio de backups si no existe
                backup_dir = os.path.join('src', 'config', 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # Nombre del archivo de backup
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                backup_name = f"{self.name}_{timestamp}.json"
                backup_path = os.path.join(backup_dir, backup_name)
                
                # Guardar backup
                profile_dict = self.to_dict()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(profile_dict, f, indent=2, ensure_ascii=False)
                
                logger.info(f"💾 Backup creado: {backup_path}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error creando backup: {e}")
                return False
    
    def cleanup(self):
        """Limpia recursos del runtime."""
        with self._lock:
            self.gestures.clear()
            self.voice_commands.clear()
            self._gesture_cache.clear()
            self._voice_cache.clear()
            self._action_cache.clear()
            self._hand_gestures.clear()
            self._source_gestures.clear()
            self.settings.clear()
            self.enabled_modules.clear()
            
            # Limpiar callbacks
            self.on_profile_changed = None
            self.on_gesture_executed = None
            self.on_voice_executed = None
            
            logger.info(f"🧹 ProfileRuntime limpiado: {self.name}")


# ========== CLASE DE INTEGRACIÓN PARA GESTUREPIPELINE ==========

class GesturePipelineIntegration:
    """
    Clase auxiliar para integrar ProfileRuntime con GesturePipeline.
    Usa este mixin en tu GesturePipeline.
    """
    
    def __init__(self):
        """Inicializa la integración con ProfileRuntime."""
        super().__init__()  # Si heredas de algo
        
        # ProfileRuntime
        self.profile_runtime = ProfileRuntime()
        
        # Configurar callbacks
        self.profile_runtime.set_gesture_callback(self._on_gesture_executed)
        self.profile_runtime.set_voice_callback(self._on_voice_executed)
        self.profile_runtime.set_profile_change_callback(self._on_profile_changed)
        
        logger.info("🔗 ProfileRuntime integrado en GesturePipeline")
    
    def _on_gesture_executed(self, gesture_name: str, action: Dict):
        """
        Callback cuando se ejecuta un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            action: Acción ejecutada
        """
        # Aquí puedes agregar lógica específica del pipeline
        logger.debug(f"GesturePipeline: Gesto '{gesture_name}' ejecutado")
        
        # Ejemplo: Actualizar estadísticas del pipeline
        if hasattr(self, 'stats'):
            self.stats['gestures_processed'] = self.stats.get('gestures_processed', 0) + 1
    
    def _on_voice_executed(self, command_text: str, action: Dict):
        """
        Callback cuando se ejecuta un comando de voz.
        
        Args:
            command_text: Texto del comando
            action: Acción ejecutada
        """
        # Aquí puedes agregar lógica específica del pipeline
        logger.debug(f"GesturePipeline: Comando voz '{command_text}' ejecutado")
        
        # Ejemplo: Actualizar estadísticas del pipeline
        if hasattr(self, 'stats'):
            self.stats['voice_commands_processed'] = self.stats.get('voice_commands_processed', 0) + 1
    
    def _on_profile_changed(self, profile_name: str, profile_path: str):
        """
        Callback cuando cambia el perfil.
        
        Args:
            profile_name: Nombre del nuevo perfil
            profile_path: Ruta del archivo del perfil
        """
        # Aquí puedes agregar lógica específica del pipeline
        logger.info(f"GesturePipeline: Perfil cambiado a '{profile_name}'")
        
        # Ejemplo: Reiniciar módulos específicos
        if hasattr(self, 'modules'):
            self._reinitialize_modules_for_profile(profile_name)
    
    def _reinitialize_modules_for_profile(self, profile_name: str):
        """
        Reinicializa módulos basados en el perfil cargado.
        
        Args:
            profile_name: Nombre del perfil
        """
        # Aquí puedes agregar lógica para reinicializar módulos
        # según los módulos habilitados en el perfil
        pass
    
    def load_profile(self, profile_name: str) -> bool:
        """
        Carga un perfil en el pipeline.
        
        Args:
            profile_name: Nombre del perfil
            
        Returns:
            True si se cargó correctamente
        """
        return self.profile_runtime.load_profile(profile_name)
    
    def process_gesture(self, gesture_data: Dict) -> Optional[Dict]:
        """
        Procesa datos de gesto a través del ProfileRuntime.
        
        Args:
            gesture_data: Datos del gesto detectado
            
        Returns:
            Acción a ejecutar o None
        """
        return self.profile_runtime.process_gesture(gesture_data)
    
    def process_voice_command(self, voice_data: Dict) -> Optional[Dict]:
        """
        Procesa comando de voz a través del ProfileRuntime.
        
        Args:
            voice_data: Datos del comando de voz
            
        Returns:
            Acción a ejecutar o None
        """
        return self.profile_runtime.process_voice_command(voice_data)
    
    def get_profile_stats(self) -> Dict:
        """
        Obtiene estadísticas del ProfileRuntime.
        
        Returns:
            Diccionario con estadísticas
        """
        return self.profile_runtime.get_stats()
    
    def get_gestures(self) -> Dict[str, Dict]:
        """
        Obtiene gestos del perfil actual.
        
        Returns:
            Diccionario con gestos
        """
        return self.profile_runtime.get_all_gestures()
    
    def get_voice_commands(self) -> Dict[str, Dict]:
        """
        Obtiene comandos de voz del perfil actual.
        
        Returns:
            Diccionario con comandos de voz
        """
        return self.profile_runtime.get_voice_commands()


# ========== EJEMPLO DE USO EN TU GESTUREPIPELINE ==========

"""
class GesturePipeline(GesturePipelineIntegration):
    def __init__(self, config):
        # Inicializar integración primero
        super().__init__()
        
        # Tu configuración existente
        self.config = config
        
        # Inicializar otros componentes
        self.initialize_components()
        
    def initialize_components(self):
        # Tu lógica de inicialización existente
        pass
    
    def process_frame(self, frame_data):
        # Tu lógica de procesamiento
        gesture_result = self.detect_gesture(frame_data)
        
        if gesture_result:
            # Usar ProfileRuntime para procesar el gesto
            action = self.process_gesture(gesture_result)
            
            if action and hasattr(self, 'action_executor'):
                self.action_executor.execute(action)
    
    def process_audio(self, audio_data):
        # Tu lógica de procesamiento de voz
        voice_result = self.detect_voice_command(audio_data)
        
        if voice_result:
            # Usar ProfileRuntime para procesar el comando
            action = self.process_voice_command(voice_result)
            
            if action and hasattr(self, 'action_executor'):
                self.action_executor.execute(action)
"""


# ========== PRUEBA DE INTEGRACIÓN ==========

if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🎭 PROFILE RUNTIME - Prueba de integración completa\n")
    
    # Crear ProfileRuntime
    runtime = ProfileRuntime()
    
    # Probar integración con callbacks
    print("🔗 Probando integración con callbacks...")
    
    def on_gesture_callback(gesture_name, action):
        print(f"   📞 Callback gesto: {gesture_name} -> {action.get('type')}")
    
    def on_voice_callback(command_text, action):
        print(f"   📞 Callback voz: '{command_text}' -> {action.get('type')}")
    
    def on_profile_callback(profile_name, profile_path):
        print(f"   📞 Callback perfil: Cambiado a '{profile_name}'")
    
    # Configurar callbacks
    runtime.set_gesture_callback(on_gesture_callback)
    runtime.set_voice_callback(on_voice_callback)
    runtime.set_profile_change_callback(on_profile_callback)
    
    # Probar procesamiento de gestos (simulado)
    print("\n🤚 Probando procesamiento de gestos...")
    
    gesture_data = {
        'gesture': 'fist',
        'source': 'hand',
        'confidence': 0.8,
        'hand_type': 'right'
    }
    
    action = runtime.process_gesture(gesture_data)
    if action:
        print(f"   ✅ Acción obtenida: {action.get('type')} - {action.get('command')}")
    
    # Probar procesamiento de voz (simulado)
    print("\n🎤 Probando procesamiento de voz...")
    
    voice_data = {
        'text': 'nyx abre discord',
        'confidence': 0.9
    }
    
    action = runtime.process_voice_command(voice_data)
    if action:
        print(f"   ✅ Acción obtenida: {action.get('type')} - {action.get('command')}")
    
    # Probar método get_voice_commands específico
    print("\n📝 Probando get_voice_commands...")
    voice_commands = runtime.get_voice_commands()
    print(f"   ✅ Obtenidos {len(voice_commands)} comandos de voz")
    for trigger, cmd in list(voice_commands.items())[:3]:  # Mostrar primeros 3
        print(f"   - {trigger}: {cmd.get('action')} -> {cmd.get('command')}")
    
    # Probar gestión de gestos
    print("\n🔧 Probando gestión de gestos...")
    
    # Agregar un nuevo gesto
    new_gesture = {
        'action': 'keyboard',
        'command': 'alt+tab',
        'description': 'Cambiar ventana',
        'hand': 'right',
        'enabled': True,
        'confidence': 0.6,
        'cooldown': 0.5,
        'parameters': {'repeat': 1}
    }
    
    if runtime.add_gesture('swipe_left', new_gesture):
        print(f"   ✅ Gesto 'swipe_left' agregado")
        print(f"   Total gestos: {runtime.get_gesture_count()} ({runtime.get_enabled_gesture_count()} habilitados)")
    
    # Probar estadísticas
    print("\n📊 Probando estadísticas...")
    stats = runtime.get_stats()
    print(f"   Gestos ejecutados: {stats['gestures_executed']}")
    print(f"   Comandos voz ejecutados: {stats['voice_commands_executed']}")
    print(f"   Historial: {stats['history_size']} entradas")
    
    # Probar validación
    print("\n✅ Probando validación...")
    is_valid, errors = runtime.validate()
    if is_valid:
        print("   ✅ Perfil válido")
    else:
        print(f"   ❌ Errores encontrados: {errors}")
    
    # Probar export para UI
    print("\n🖥️ Probando export para UI...")
    ui_data = runtime.export_for_ui()
    print(f"   Datos exportados: {len(ui_data['gestures'])} gestos, {len(ui_data['voice_commands'])} comandos voz")
    
    # Probar método get_config
    print("\n⚙️ Probando get_config...")
    config = runtime.get_config()
    print(f"   Configuración obtenida: {len(config['settings'])} ajustes")
    
    # Probar backup
    print("\n💾 Probando creación de backup...")
    if runtime.create_backup():
        print("   ✅ Backup creado correctamente")
    else:
        print("   ⚠️ No se pudo crear backup (posiblemente sin archivo cargado)")
    
    # Limpiar
    runtime.cleanup()
    print("\n✨ Prueba de integración completada exitosamente!")