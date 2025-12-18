"""
🎭 PROFILE RUNTIME - Gestor de perfiles en tiempo de ejecución para NYX
=======================================================================
Maneja la carga, validación, búsqueda y activación de perfiles durante la ejecución.
Es el puente CRÍTICO entre detección de gestos y ejecución de acciones.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class GestureConfig:
    """Configuración completa de un gesto para NYX."""
    name: str
    action: str                    # keyboard, mouse, bash, window
    command: str                   # Comando a ejecutar
    description: str = ""
    hand: str = "right"            # right, left, both, any
    type: str = "hand"             # hand, arm, pose
    enabled: bool = True
    confidence: float = 0.7        # Confianza mínima requerida
    cooldown: float = 0.3          # Tiempo entre ejecuciones
    last_executed: float = 0.0     # Timestamp de última ejecución
    
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
            return False, f"Mano incorrecta ({detected_hand} != {self.hand})"
        
        # 4. Verificar cooldown
        current_time = time.time()
        if current_time - self.last_executed < self.cooldown:
            remaining = self.cooldown - (current_time - self.last_executed)
            return False, f"En cooldown ({remaining:.1f}s restantes)"
        
        return True, "OK"


@dataclass
class VoiceCommandConfig:
    """Configuración de un comando de voz para NYX."""
    trigger: str                   # Texto que activa el comando
    action: str                    # keyboard, mouse, bash, window
    command: str                   # Comando a ejecutar
    description: str = ""
    enabled: bool = True
    requires_activation: bool = True  # Requiere "nyx" antes del comando
    
    def matches(self, spoken_text: str, activation_word: str = "nyx") -> bool:
        """
        Verifica si el comando coincide con el texto hablado.
        
        Args:
            spoken_text: Texto detectado por voz
            activation_word: Palabra de activación
            
        Returns:
            True si coincide
        """
        if not self.enabled:
            return False
        
        spoken_text = spoken_text.lower().strip()
        trigger = self.trigger.lower().strip()
        
        # Si requiere palabra de activación
        if self.requires_activation:
            # Verificar formato: "nyx comando"
            expected = f"{activation_word} {trigger}"
            return expected in spoken_text
        else:
            # Coincidencia directa
            return trigger in spoken_text


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
        
        # Cache y estado
        self._gesture_cache: Dict[str, GestureConfig] = {}    # Cache por nombre
        self._hand_gestures: Dict[str, List[str]] = {         # Gestos por mano
            'right': [],
            'left': [],
            'both': [],
            'any': []
        }
        self._type_gestures: Dict[str, List[str]] = {         # Gestos por tipo
            'hand': [],
            'arm': [],
            'pose': []
        }
        self._voice_cache: Dict[str, VoiceCommandConfig] = {} # Cache de comandos
        
        # Estadísticas
        self.stats = {
            'gestures_loaded': 0,
            'voice_commands_loaded': 0,
            'gestures_executed': 0,
            'voice_commands_executed': 0,
            'last_execution': 0.0,
            'load_time': time.time()
        }
        
        # Cargar perfil si se proporciona
        if profile_data:
            self.load_profile_data(profile_data)
        
        logger.info(f"✅ ProfileRuntime inicializado: {self.name}")
    
    def load_profile_data(self, profile_data: Dict[str, Any]) -> bool:
        """
        Carga datos de un perfil con validación completa.
        
        Args:
            profile_data: Diccionario con datos del perfil
            
        Returns:
            True si se cargó correctamente
        """
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
            
            # 8. Actualizar estadísticas
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
                    hand=gesture_data.get('hand', 'right').lower(),
                    type=gesture_data.get('type', 'hand').lower(),
                    enabled=gesture_data.get('enabled', True),
                    confidence=float(gesture_data.get('confidence', 0.7)),
                    cooldown=float(gesture_data.get('cooldown', 0.3))
                )
                
                # Validar valores
                if gesture.hand not in ['right', 'left', 'both', 'any']:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' con mano inválida: {gesture.hand}")
                    gesture.hand = 'right'
                
                if gesture.type not in ['hand', 'arm', 'pose']:
                    logger.warning(f"⚠️ Gesto '{gesture_name}' con tipo inválido: {gesture.type}")
                    gesture.type = 'hand'
                
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
                    requires_activation=voice_data.get('requires_activation', True)
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
            'visual_feedback': True
        }
        
        # Aplicar valores por defecto si no existen
        for key, default_value in default_settings.items():
            if key not in self.settings:
                self.settings[key] = default_value
    
    def _build_indices(self):
        """Construye índices para búsqueda rápida."""
        # Reiniciar índices
        self._hand_gestures = {'right': [], 'left': [], 'both': [], 'any': []}
        self._type_gestures = {'hand': [], 'arm': [], 'pose': []}
        
        # Construir índices
        for gesture_name, gesture in self.gestures.items():
            if gesture.enabled:
                # Indexar por mano
                self._hand_gestures[gesture.hand].append(gesture_name)
                
                # Indexar por tipo
                self._type_gestures[gesture.type].append(gesture_name)
    
    def get_gesture(self, gesture_name: str) -> Optional[GestureConfig]:
        """
        Obtiene configuración completa de un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            
        Returns:
            GestureConfig o None si no existe
        """
        return self.gestures.get(gesture_name)
    
    def get_gesture_action(self, gesture_name: str, hand_type: str = None, 
                          confidence: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Obtiene acción para ejecutar basada en un gesto.
        
        Args:
            gesture_name: Nombre del gesto detectado
            hand_type: Tipo de mano detectada (right, left, both)
            confidence: Confianza de detección (0.0-1.0)
            
        Returns:
            Configuración de acción o None
        """
        # Obtener gesto
        gesture = self.get_gesture(gesture_name)
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
            'hand': hand_type or gesture.hand,
            'confidence': confidence,
            'timestamp': time.time(),
            'profile': self.name
        }
        
        # Actualizar timestamp de última ejecución
        gesture.last_executed = time.time()
        
        # Actualizar estadísticas
        self.stats['gestures_executed'] += 1
        self.stats['last_execution'] = time.time()
        
        return action
    
    def get_voice_action(self, command_text: str, activation_word: str = "nyx") -> Optional[Dict[str, Any]]:
        """
        Obtiene acción para ejecutar basada en comando de voz.
        
        Args:
            command_text: Texto del comando de voz
            activation_word: Palabra de activación
            
        Returns:
            Configuración de acción o None
        """
        # Buscar comando coincidente
        voice_cmd = None
        for trigger, cmd_config in self.voice_commands.items():
            if cmd_config.matches(command_text, activation_word):
                voice_cmd = cmd_config
                break
        
        if not voice_cmd:
            return None
        
        # Crear acción
        action = {
            'type': voice_cmd.action,
            'command': voice_cmd.command,
            'description': voice_cmd.description,
            'voice_command': command_text,
            'timestamp': time.time(),
            'profile': self.name
        }
        
        # Actualizar estadísticas
        self.stats['voice_commands_executed'] += 1
        self.stats['last_execution'] = time.time()
        
        return action
    
    def get_gestures_by_hand(self, hand_type: str) -> List[str]:
        """
        Obtiene nombres de gestos configurados para una mano específica.
        
        Args:
            hand_type: Tipo de mano (right, left, both, any)
            
        Returns:
            Lista de nombres de gestos
        """
        return self._hand_gestures.get(hand_type, [])
    
    def get_gestures_by_type(self, gesture_type: str) -> List[str]:
        """
        Obtiene nombres de gestos de un tipo específico.
        
        Args:
            gesture_type: Tipo de gesto (hand, arm, pose)
            
        Returns:
            Lista de nombres de gestos
        """
        return self._type_gestures.get(gesture_type, [])
    
    def get_all_gestures(self) -> List[str]:
        """
        Obtiene todos los nombres de gestos habilitados.
        
        Returns:
            Lista de nombres de gestos
        """
        return [name for name, gesture in self.gestures.items() if gesture.enabled]
    
    def get_all_gesture_configs(self) -> Dict[str, GestureConfig]:
        """
        Obtiene todos los gestos con sus configuraciones.
        
        Returns:
            Diccionario de nombre -> GestureConfig
        """
        return {name: gesture for name, gesture in self.gestures.items() if gesture.enabled}
    
    def get_voice_commands(self) -> Dict[str, VoiceCommandConfig]:
        """
        Obtiene todos los comandos de voz habilitados.
        
        Returns:
            Diccionario de trigger -> VoiceCommandConfig
        """
        return {trigger: cmd for trigger, cmd in self.voice_commands.items() if cmd.enabled}
    
    def is_module_enabled(self, module_name: str) -> bool:
        """
        Verifica si un módulo está habilitado en el perfil.
        
        Args:
            module_name: Nombre del módulo
            
        Returns:
            True si el módulo está habilitado
        """
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
        return self.enabled_modules.copy()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.
        
        Args:
            key: Clave de configuración
            default: Valor por defecto si no existe
            
        Returns:
            Valor de configuración o default
        """
        return self.settings.get(key, default)
    
    def update_setting(self, key: str, value: Any):
        """
        Actualiza un valor de configuración.
        
        Args:
            key: Clave de configuración
            value: Nuevo valor
        """
        self.settings[key] = value
    
    def enable_gesture(self, gesture_name: str) -> bool:
        """
        Habilita un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            
        Returns:
            True si se habilitó correctamente
        """
        if gesture_name in self.gestures:
            self.gestures[gesture_name].enabled = True
            self._build_indices()  # Reconstruir índices
            return True
        return False
    
    def disable_gesture(self, gesture_name: str) -> bool:
        """
        Deshabilita un gesto.
        
        Args:
            gesture_name: Nombre del gesto
            
        Returns:
            True si se deshabilitó correctamente
        """
        if gesture_name in self.gestures:
            self.gestures[gesture_name].enabled = False
            self._build_indices()  # Reconstruir índices
            return True
        return False
    
    def get_gesture_count(self) -> int:
        """Obtiene número total de gestos."""
        return len(self.gestures)
    
    def get_enabled_gesture_count(self) -> int:
        """Obtiene número de gestos habilitados."""
        return len([g for g in self.gestures.values() if g.enabled])
    
    def get_voice_command_count(self) -> int:
        """Obtiene número total de comandos de voz."""
        return len(self.voice_commands)
    
    def get_enabled_voice_command_count(self) -> int:
        """Obtiene número de comandos de voz habilitados."""
        return len([c for c in self.voice_commands.values() if c.enabled])
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el perfil a diccionario para guardar.
        
        Returns:
            Diccionario compatible con formato JSON de NYX
        """
        # Convertir gestos
        gestures_dict = {}
        for name, gesture in self.gestures.items():
            gestures_dict[name] = {
                'action': gesture.action,
                'command': gesture.command,
                'description': gesture.description,
                'hand': gesture.hand,
                'type': gesture.type,
                'enabled': gesture.enabled,
                'confidence': gesture.confidence,
                'cooldown': gesture.cooldown
            }
        
        # Convertir comandos de voz
        voice_dict = {}
        for trigger, voice_cmd in self.voice_commands.items():
            voice_dict[trigger] = {
                'action': voice_cmd.action,
                'command': voice_cmd.command,
                'description': voice_cmd.description,
                'enabled': voice_cmd.enabled,
                'requires_activation': voice_cmd.requires_activation
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del runtime."""
        stats = self.stats.copy()
        stats.update({
            'name': self.name,
            'gesture_count': self.get_gesture_count(),
            'enabled_gesture_count': self.get_enabled_gesture_count(),
            'voice_command_count': self.get_voice_command_count(),
            'enabled_voice_command_count': self.get_enabled_voice_command_count(),
            'enabled_modules': self.enabled_modules,
            'uptime': time.time() - self.stats['load_time']
        })
        return stats
    
    def clear_stats(self):
        """Limpia estadísticas de ejecución."""
        self.stats.update({
            'gestures_executed': 0,
            'voice_commands_executed': 0,
            'last_execution': 0.0
        })
    
    def cleanup(self):
        """Limpia recursos del runtime."""
        self.gestures.clear()
        self.voice_commands.clear()
        self._gesture_cache.clear()
        self._voice_cache.clear()
        self._hand_gestures.clear()
        self._type_gestures.clear()
        
        logger.info(f"✅ ProfileRuntime limpiado: {self.name}")


# Uso en NYX
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Datos de perfil de ejemplo (gamer corregido)
    gamer_profile = {
        'profile_name': 'gamer',
        'description': 'Perfil para gaming - gestos rápidos y precisos',
        'version': '1.0.0',
        'author': 'NYX Sistema',
        'gestures': {
            'fist': {
                'action': 'keyboard',
                'command': 'ctrl+f',
                'description': 'Abrir búsqueda en juego',
                'hand': 'right',
                'type': 'hand',
                'enabled': True,
                'confidence': 0.7,
                'cooldown': 0.3
            },
            'peace': {
                'action': 'keyboard',
                'command': 'esc',
                'description': 'Abrir menú/pausa',
                'hand': 'right',
                'type': 'hand',
                'enabled': True,
                'confidence': 0.7
            }
        },
        'voice_commands': {
            'nyx abre discord': {
                'action': 'bash',
                'command': 'discord',
                'description': 'Abrir Discord',
                'enabled': True
            }
        },
        'settings': {
            'mouse_sensitivity': 1.5,
            'keyboard_delay': 0.1
        },
        'enabled_modules': ['hand', 'voice', 'keyboard', 'mouse', 'bash']
    }
    
    # Crear ProfileRuntime
    print("🎭 Probando ProfileRuntime para NYX...")
    runtime = ProfileRuntime(gamer_profile)
    
    # Mostrar información
    print(f"\n📋 Perfil: {runtime.name}")
    print(f"   Descripción: {runtime.description}")
    print(f"   Gestos cargados: {runtime.get_gesture_count()}")
    print(f"   Comandos voz: {runtime.get_voice_command_count()}")
    
    # Probar búsqueda de gestos
    print("\n🔍 Probando búsqueda de gestos:")
    
    # Gesto válido
    action = runtime.get_gesture_action('fist', hand_type='right', confidence=0.8)
    if action:
        print(f"  ✅ Gesto 'fist' encontrado:")
        print(f"     Acción: {action['type']}")
        print(f"     Comando: {action['command']}")
        print(f"     Descripción: {action['description']}")
    else:
        print("  ❌ Gesto 'fist' no encontrado")
    
    # Gesto con confianza baja
    action = runtime.get_gesture_action('fist', confidence=0.5)
    if action:
        print("  ❌ ERROR: Gesto ejecutado con confianza baja")
    else:
        print("  ✅ Correcto: Gesto rechazado por confianza baja")
    
    # Probar comandos de voz
    print("\n🎤 Probando comandos de voz:")
    
    voice_action = runtime.get_voice_action("nyx abre discord")
    if voice_action:
        print(f"  ✅ Comando 'nyx abre discord' encontrado:")
        print(f"     Acción: {voice_action['type']}")
        print(f"     Comando: {voice_action['command']}")
    else:
        print("  ❌ Comando no encontrado")
    
    # Probar comandos de voz sin palabra de activación
    voice_action = runtime.get_voice_action("abre discord")
    if voice_action:
        print("  ❌ ERROR: Comando ejecutado sin palabra de activación")
    else:
        print("  ✅ Correcto: Comando rechazado sin palabra de activación")
    
    # Mostrar estadísticas
    stats = runtime.get_stats()
    print(f"\n📊 Estadísticas:")
    print(f"   Gestos ejecutados: {stats['gestures_executed']}")
    print(f"   Comandos voz ejecutados: {stats['voice_commands_executed']}")
    
    # Mostrar gestos por mano
    print(f"\n👋 Gestos por mano derecha: {runtime.get_gestures_by_hand('right')}")
    
    # Limpiar
    runtime.cleanup()
    print("\n✅ Prueba de ProfileRuntime completada")