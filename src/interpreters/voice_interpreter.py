"""
🎤 VOICE INTERPRETER - Interpretador de Comandos de Voz
======================================================
Procesa comandos de voz reconocidos y los convierte en acciones ejecutables.
Incluye procesamiento de lenguaje natural básico y manejo de contexto.
"""

import re
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VoiceInterpreter:
    """Interpreta comandos de voz y los mapea a acciones."""
    
    def __init__(self, language: str = "es-ES"):
        """
        Inicializa el interpretador de voz.
        
        Args:
            language: Idioma para procesamiento de comandos
        """
        self.language = language.lower()
        
        # Mapeo de comandos de voz a acciones
        self.command_mappings = {}
        self.contextual_commands = {}
        
        # Contexto actual de la conversación
        self.context = {
            'last_command': None,
            'last_action': None,
            'last_topic': None,
            'conversation_history': [],
            'user_preferences': {}
        }
        
        # Historial de comandos
        self.command_history = []
        self.max_history = 50
        
        # Patrones de reconocimiento para comandos naturales
        self.patterns = self._initialize_patterns()
        
        # Para procesamiento en tiempo real
        self.processing_queue = []
        self.processing_lock = threading.Lock()
        self.is_processing = False
        
        # Estadísticas
        self.stats = {
            'commands_received': 0,
            'commands_processed': 0,
            'commands_matched': 0,
            'commands_failed': 0,
            'processing_time_avg': 0.0,
            'last_command_time': 0
        }
        
        # Parámetros de configuración
        self.confidence_threshold = 0.7
        self.similarity_threshold = 0.8
        self.max_context_age = 300  # 5 minutos en segundos
        
        # Para aprendizaje básico
        self.learned_commands = {}
        self.command_frequency = {}
        
        logger.info(f"✅ VoiceInterpreter inicializado (idioma: {language})")
    
    def _initialize_patterns(self) -> Dict[str, List[re.Pattern]]:
        """
        Inicializa patrones de regex para comandos comunes.
        
        Returns:
            Diccionario de categorías de patrones
        """
        patterns = {
            'open_app': [
                re.compile(r'abre\s+(.+)', re.IGNORECASE),
                re.compile(r'inicia\s+(.+)', re.IGNORECASE),
                re.compile(r'ejecuta\s+(.+)', re.IGNORECASE),
                re.compile(r'lanzar?\s+(.+)', re.IGNORECASE)
            ],
            'close_app': [
                re.compile(r'cierra\s+(.+)', re.IGNORECASE),
                re.compile(r'termina\s+(.+)', re.IGNORECASE),
                re.compile(r'finaliza\s+(.+)', re.IGNORECASE),
                re.compile(r'sal(?:ir|e)?\s+de\s+(.+)', re.IGNORECASE)
            ],
            'search': [
                re.compile(r'busca\s+(.+)', re.IGNORECASE),
                re.compile(r'buscar\s+(.+)', re.IGNORECASE),
                re.compile(r'encontrar?\s+(.+)', re.IGNORECASE),
                re.compile(r'googlea?\s+(.+)', re.IGNORECASE)
            ],
            'volume': [
                re.compile(r'(?:sube|aumenta)\s+(?:el\s+)?volumen', re.IGNORECASE),
                re.compile(r'(?:baja|reduce)\s+(?:el\s+)?volumen', re.IGNORECASE),
                re.compile(r'(?:silencia|mutea?)\s+(?:el\s+)?volumen', re.IGNORECASE),
                re.compile(r'volumen\s+(?:al\s+)?(máximo|mínimo|medio)', re.IGNORECASE)
            ],
            'navigation': [
                re.compile(r'(?:ir|navegar?)\s+a\s+(.+)', re.IGNORECASE),
                re.compile(r'abre\s+(?:la\s+)?página\s+(.+)', re.IGNORECASE),
                re.compile(r've\s+a\s+(.+)', re.IGNORECASE)
            ],
            'system': [
                re.compile(r'(?:apaga|apagar)\s+(?:la\s+)?computadora', re.IGNORECASE),
                re.compile(r'(?:reinicia|reiniciar)\s+(?:la\s+)?computadora', re.IGNORECASE),
                re.compile(r'(?:suspende?|dormir?)\s+(?:la\s+)?computadora', re.IGNORECASE),
                re.compile(r'toma\s+(?:una\s+)?captura\s+(?:de\s+)?pantalla', re.IGNORECASE)
            ],
            'media': [
                re.compile(r'(?:reproduce?|play)\s+(.+)', re.IGNORECASE),
                re.compile(r'(?:pausa?|stop)\s+(.+)', re.IGNORECASE),
                re.compile(r'(?:siguiente|next)', re.IGNORECASE),
                re.compile(r'(?:anterior|previo|previous)', re.IGNORECASE)
            ],
            'help': [
                re.compile(r'qué\s+puedo\s+decir', re.IGNORECASE),
                re.compile(r'ayuda', re.IGNORECASE),
                re.compile(r'comandos\s+disponibles', re.IGNORECASE),
                re.compile(r'qué\s+comandos\s+hay', re.IGNORECASE)
            ]
        }
        
        # Añadir patrones específicos por idioma
        if self.language.startswith('es'):
            patterns['greeting'] = [
                re.compile(r'hola', re.IGNORECASE),
                re.compile(r'buenos\s+(días|tardes|noches)', re.IGNORECASE),
                re.compile(r'cómo\s+estás', re.IGNORECASE)
            ]
            patterns['thanks'] = [
                re.compile(r'gracias', re.IGNORECASE),
                re.compile(r'muchas\s+gracias', re.IGNORECASE),
                re.compile(r'te\s+agradezco', re.IGNORECASE)
            ]
        elif self.language.startswith('en'):
            patterns['greeting'] = [
                re.compile(r'hello', re.IGNORECASE),
                re.compile(r'hi', re.IGNORECASE),
                re.compile(r'good\s+(morning|afternoon|evening)', re.IGNORECASE),
                re.compile(r'how\s+are\s+you', re.IGNORECASE)
            ]
            patterns['thanks'] = [
                re.compile(r'thank\s+you', re.IGNORECASE),
                re.compile(r'thanks', re.IGNORECASE),
                re.compile(r'appreciate\s+it', re.IGNORECASE)
            ]
        
        return patterns
    
    def interpret(self, voice_command: Dict) -> Optional[Dict]:
        """
        Interpreta un comando de voz y lo convierte en acción.
        
        Args:
            voice_command: Diccionario con comando de voz del VoiceRecognizer
            
        Returns:
            Acción interpretada o None si no se pudo interpretar
        """
        if not voice_command or 'text' not in voice_command:
            logger.warning("⚠️ Comando de voz inválido recibido")
            return None
        
        command_text = voice_command.get('text', '').strip()
        if not command_text:
            return None
        
        start_time = time.time()
        self.stats['commands_received'] += 1
        self.stats['last_command_time'] = start_time
        
        logger.info(f"🎤 Procesando comando: '{command_text}'")
        
        try:
            # Paso 1: Normalizar y limpiar el texto
            normalized_text = self._normalize_text(command_text)
            
            # Paso 2: Verificar si es un comando conocido
            mapped_action = self._check_command_mappings(normalized_text)
            if mapped_action:
                result = self._create_action_result(mapped_action, normalized_text, voice_command)
                self._update_stats(True, start_time)
                return result
            
            # Paso 3: Intentar reconocer con patrones
            pattern_match = self._match_with_patterns(normalized_text)
            if pattern_match:
                result = self._create_pattern_action(pattern_match, normalized_text, voice_command)
                self._update_stats(True, start_time)
                return result
            
            # Paso 4: Verificar comandos contextuales
            contextual_action = self._check_contextual_commands(normalized_text)
            if contextual_action:
                result = self._create_action_result(contextual_action, normalized_text, voice_command)
                self._update_stats(True, start_time)
                return result
            
            # Paso 5: Intentar con comandos aprendidos
            learned_action = self._check_learned_commands(normalized_text)
            if learned_action:
                result = self._create_action_result(learned_action, normalized_text, voice_command)
                self._update_stats(True, start_time)
                return result
            
            # Paso 6: Buscar el comando más similar
            similar_action = self._find_similar_command(normalized_text)
            if similar_action:
                result = similar_action
                result['interpretation']['confidence'] *= 0.7  # Reducir confianza
                self._update_stats(True, start_time)
                return result
            
            # Comando no reconocido
            logger.warning(f"⚠️ Comando no reconocido: '{command_text}'")
            self._handle_unknown_command(normalized_text, voice_command)
            self._update_stats(False, start_time)
            
            # Devolver comando de ayuda
            return self._create_help_action(normalized_text, voice_command)
            
        except Exception as e:
            logger.error(f"❌ Error interpretando comando: {e}")
            self.stats['commands_failed'] += 1
            return None
    
    def _normalize_text(self, text: str) -> str:
        """
        Normaliza el texto del comando.
        
        Args:
            text: Texto del comando
            
        Returns:
            Texto normalizado
        """
        # Convertir a minúsculas
        normalized = text.lower()
        
        # Remover puntuación excesiva
        normalized = re.sub(r'[^\w\sáéíóúñüÁÉÍÓÚÑÜ]', ' ', normalized)
        
        # Remover espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Expansión de contracciones (español)
        if self.language.startswith('es'):
            contractions = {
                'pa ': 'para ',
                'q ': 'que ',
                'd ': 'de ',
                ' x ': ' por ',
                'k': 'que'
            }
            for contr, exp in contractions.items():
                normalized = normalized.replace(contr, exp)
        
        return normalized
    
    def _check_command_mappings(self, normalized_text: str) -> Optional[Dict]:
        """
        Verifica si el texto coincide con comandos mapeados.
        
        Args:
            normalized_text: Texto normalizado del comando
            
        Returns:
            Configuración de acción si hay coincidencia
        """
        # Coincidencia exacta
        if normalized_text in self.command_mappings:
            self.command_frequency[normalized_text] = self.command_frequency.get(normalized_text, 0) + 1
            return self.command_mappings[normalized_text]
        
        # Coincidencia parcial (comando contiene texto mapeado)
        for command, action_config in self.command_mappings.items():
            if command in normalized_text:
                self.command_frequency[command] = self.command_frequency.get(command, 0) + 1
                
                # Crear copia con parámetros extraídos
                enhanced_config = action_config.copy()
                enhanced_config['extracted_text'] = normalized_text.replace(command, '').strip()
                
                return enhanced_config
        
        return None
    
    def _match_with_patterns(self, normalized_text: str) -> Optional[Dict]:
        """
        Intenta hacer coincidir el texto con patrones conocidos.
        
        Args:
            normalized_text: Texto normalizado del comando
            
        Returns:
            Información de coincidencia con patrón
        """
        for category, pattern_list in self.patterns.items():
            for pattern in pattern_list:
                match = pattern.match(normalized_text)
                if match:
                    groups = match.groups()
                    
                    # Calcular confianza basada en longitud de coincidencia
                    confidence = min(len(match.group(0)) / len(normalized_text) * 1.2, 1.0)
                    
                    return {
                        'category': category,
                        'pattern': pattern.pattern,
                        'matched_text': match.group(0),
                        'groups': groups,
                        'confidence': confidence
                    }
        
        return None
    
    def _check_contextual_commands(self, normalized_text: str) -> Optional[Dict]:
        """
        Verifica comandos que dependen del contexto.
        
        Args:
            normalized_text: Texto normalizado del comando
            
        Returns:
            Configuración de acción contextual
        """
        current_time = time.time()
        
        # Limpiar contexto viejo
        self.context['conversation_history'] = [
            entry for entry in self.context['conversation_history']
            if current_time - entry.get('timestamp', 0) < self.max_context_age
        ]
        
        # Buscar comandos que dependen del último comando
        if self.context['last_command']:
            contextual_key = f"{self.context['last_command']}|{normalized_text}"
            if contextual_key in self.contextual_commands:
                return self.contextual_commands[contextual_key]
        
        # Buscar comandos relacionados con el último tema
        if self.context['last_topic']:
            topic_commands = self.contextual_commands.get(self.context['last_topic'], {})
            if normalized_text in topic_commands:
                return topic_commands[normalized_text]
        
        return None
    
    def _check_learned_commands(self, normalized_text: str) -> Optional[Dict]:
        """
        Verifica comandos aprendidos automáticamente.
        
        Args:
            normalized_text: Texto normalizado del comando
            
        Returns:
            Configuración de acción aprendida
        """
        # Buscar coincidencia exacta en comandos aprendidos
        if normalized_text in self.learned_commands:
            self.command_frequency[normalized_text] = self.command_frequency.get(normalized_text, 0) + 1
            return self.learned_commands[normalized_text]
        
        # Buscar similitud semántica básica
        words = set(normalized_text.split())
        best_match = None
        best_score = 0
        
        for learned_command, action_config in self.learned_commands.items():
            learned_words = set(learned_command.split())
            common_words = words.intersection(learned_words)
            
            if common_words:
                score = len(common_words) / max(len(words), len(learned_words))
                if score > best_score and score >= self.similarity_threshold:
                    best_score = score
                    best_match = action_config
        
        if best_match:
            # Ajustar confianza basada en similitud
            best_match = best_match.copy()
            best_match['learned_confidence'] = best_score
            return best_match
        
        return None
    
    def _find_similar_command(self, normalized_text: str) -> Optional[Dict]:
        """
        Busca el comando mapeado más similar al texto.
        
        Args:
            normalized_text: Texto normalizado del comando
            
        Returns:
            Acción del comando más similar
        """
        if not self.command_mappings:
            return None
        
        words = normalized_text.split()
        best_command = None
        best_similarity = 0
        
        for command in self.command_mappings.keys():
            command_words = command.split()
            common_words = set(words).intersection(set(command_words))
            
            if common_words:
                similarity = len(common_words) / max(len(words), len(command_words))
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_command = command
        
        if best_similarity >= self.similarity_threshold and best_command:
            action_config = self.command_mappings[best_command].copy()
            
            # Crear resultado con información de similitud
            result = self._create_action_result(action_config, normalized_text, {})
            result['interpretation']['similarity'] = best_similarity
            result['interpretation']['matched_command'] = best_command
            result['interpretation']['confidence'] *= best_similarity
            
            return result
        
        return None
    
    def _handle_unknown_command(self, normalized_text: str, voice_command: Dict):
        """
        Maneja comandos no reconocidos.
        
        Args:
            normalized_text: Texto normalizado del comando
            voice_command: Comando de voz original
        """
        # Agregar a historial para análisis futuro
        unknown_entry = {
            'text': normalized_text,
            'original': voice_command.get('text', ''),
            'timestamp': time.time(),
            'context': self.context.copy()
        }
        
        self.command_history.append(unknown_entry)
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
        
        logger.debug(f"📝 Comando desconocido guardado: {normalized_text}")
        
        # Podrías agregar lógica para aprendizaje automático aquí
        # Por ejemplo, pedir confirmación al usuario
    
    def _create_help_action(self, normalized_text: str, voice_command: Dict) -> Dict:
        """
        Crea una acción de ayuda cuando el comando no es reconocido.
        
        Args:
            normalized_text: Texto normalizado del comando
            voice_command: Comando de voz original
            
        Returns:
            Acción de ayuda
        """
        # Obtener comandos disponibles
        available_commands = list(self.command_mappings.keys())[:10]  # Primeros 10
        
        return {
            'type': 'voice',
            'action': 'help',
            'command': 'show_help',
            'description': 'Mostrar ayuda de comandos',
            'voice_command': voice_command,
            'interpretation': {
                'original_text': voice_command.get('text', ''),
                'normalized_text': normalized_text,
                'confidence': 1.0,
                'method': 'help_response',
                'timestamp': time.time()
            },
            'parameters': {
                'available_commands': available_commands,
                'total_commands': len(self.command_mappings),
                'suggestion': 'No entendí el comando. Aquí tienes algunos comandos disponibles:'
            }
        }
    
    def _create_action_result(self, action_config: Dict, normalized_text: str, 
                            voice_command: Dict) -> Dict:
        """
        Crea el resultado final de una acción interpretada.
        
        Args:
            action_config: Configuración de la acción
            normalized_text: Texto normalizado del comando
            voice_command: Comando de voz original
            
        Returns:
            Resultado de acción completo
        """
        # Extraer parámetros si los hay
        parameters = {}
        extracted_text = action_config.get('extracted_text', '')
        if extracted_text:
            parameters['query'] = extracted_text
        
        # Actualizar contexto
        self._update_context(normalized_text, action_config.get('action', 'unknown'))
        
        return {
            'type': 'voice',
            'action': action_config.get('action', 'unknown'),
            'command': action_config.get('command', ''),
            'description': action_config.get('description', ''),
            'voice_command': voice_command,
            'interpretation': {
                'original_text': voice_command.get('text', ''),
                'normalized_text': normalized_text,
                'confidence': action_config.get('confidence', 0.8),
                'method': 'exact_match' if 'extracted_text' not in action_config else 'partial_match',
                'timestamp': time.time(),
                'learned': 'learned_confidence' in action_config
            },
            'parameters': parameters
        }
    
    def _create_pattern_action(self, pattern_match: Dict, normalized_text: str, 
                             voice_command: Dict) -> Dict:
        """
        Crea una acción basada en coincidencia con patrón.
        
        Args:
            pattern_match: Información de coincidencia con patrón
            normalized_text: Texto normalizado del comando
            voice_command: Comando de voz original
            
        Returns:
            Resultado de acción basada en patrón
        """
        category = pattern_match['category']
        groups = pattern_match['groups']
        
        # Mapear categoría a acción
        category_actions = {
            'open_app': {'action': 'bash', 'command': 'open_app', 'description': 'Abrir aplicación'},
            'close_app': {'action': 'window', 'command': 'close', 'description': 'Cerrar aplicación'},
            'search': {'action': 'bash', 'command': 'search_web', 'description': 'Buscar en web'},
            'volume': {'action': 'bash', 'command': 'adjust_volume', 'description': 'Ajustar volumen'},
            'navigation': {'action': 'bash', 'command': 'open_url', 'description': 'Navegar a URL'},
            'system': {'action': 'bash', 'command': 'system_command', 'description': 'Comando de sistema'},
            'media': {'action': 'keyboard', 'command': 'media_control', 'description': 'Control multimedia'},
            'help': {'action': 'help', 'command': 'show_help', 'description': 'Mostrar ayuda'},
            'greeting': {'action': 'response', 'command': 'greeting', 'description': 'Saludo'},
            'thanks': {'action': 'response', 'command': 'thanks', 'description': 'Agradecimiento'}
        }
        
        action_config = category_actions.get(category, {'action': 'unknown', 'command': ''})
        
        # Extraer parámetros de los grupos del patrón
        parameters = {}
        if groups:
            if category in ['open_app', 'close_app', 'search', 'navigation', 'media']:
                parameters['query'] = groups[0] if groups else ''
            elif category == 'volume':
                if 'sube' in normalized_text or 'aumenta' in normalized_text:
                    parameters['direction'] = 'up'
                elif 'baja' in normalized_text or 'reduce' in normalized_text:
                    parameters['direction'] = 'down'
                elif 'silencia' in normalized_text:
                    parameters['direction'] = 'mute'
                elif groups:
                    parameters['level'] = groups[0]
        
        # Actualizar contexto
        self._update_context(normalized_text, action_config['action'])
        
        return {
            'type': 'voice',
            'action': action_config['action'],
            'command': action_config['command'],
            'description': action_config['description'],
            'voice_command': voice_command,
            'interpretation': {
                'original_text': voice_command.get('text', ''),
                'normalized_text': normalized_text,
                'confidence': pattern_match['confidence'],
                'method': 'pattern_match',
                'category': category,
                'pattern': pattern_match['pattern'],
                'timestamp': time.time()
            },
            'parameters': parameters
        }
    
    def _update_context(self, command_text: str, action: str):
        """
        Actualiza el contexto de la conversación.
        
        Args:
            command_text: Texto del comando
            action: Acción ejecutada
        """
        current_time = time.time()
        
        # Actualizar último comando y acción
        self.context['last_command'] = command_text
        self.context['last_action'] = action
        self.context['last_topic'] = self._extract_topic(command_text)
        
        # Agregar al historial de conversación
        conversation_entry = {
            'command': command_text,
            'action': action,
            'timestamp': current_time
        }
        
        self.context['conversation_history'].append(conversation_entry)
        
        # Mantener historial manejable
        if len(self.context['conversation_history']) > 20:
            self.context['conversation_history'].pop(0)
    
    def _extract_topic(self, command_text: str) -> Optional[str]:
        """
        Extrae el tema principal de un comando.
        
        Args:
            command_text: Texto del comando
            
        Returns:
            Tema extraído o None
        """
        topics = {
            'chrome': ['chrome', 'navegador', 'internet'],
            'terminal': ['terminal', 'consola', 'bash'],
            'music': ['música', 'spotify', 'reproducir', 'canción'],
            'files': ['archivo', 'carpeta', 'documento', 'explorador'],
            'system': ['sistema', 'computadora', 'apagar', 'reiniciar']
        }
        
        command_lower = command_text.lower()
        
        for topic, keywords in topics.items():
            for keyword in keywords:
                if keyword in command_lower:
                    return topic
        
        return None
    
    def _update_stats(self, success: bool, start_time: float):
        """
        Actualiza estadísticas de procesamiento.
        
        Args:
            success: True si el comando fue procesado exitosamente
            start_time: Tiempo de inicio del procesamiento
        """
        processing_time = time.time() - start_time
        
        if success:
            self.stats['commands_processed'] += 1
            self.stats['commands_matched'] += 1
        else:
            self.stats['commands_failed'] += 1
        
        # Actualizar tiempo promedio de procesamiento
        if self.stats['commands_processed'] > 0:
            self.stats['processing_time_avg'] = (
                (self.stats['processing_time_avg'] * (self.stats['commands_processed'] - 1) + 
                 processing_time) / self.stats['commands_processed']
            )
    
    def load_command_mappings(self, mappings: Dict):
        """
        Carga mapeos de comandos de voz a acciones.
        
        Args:
            mappings: Diccionario con mapeos
                Formato: {
                    'comando de voz': {
                        'action': 'bash',
                        'command': 'google-chrome',
                        'description': 'Abrir Chrome'
                    }
                }
        """
        self.command_mappings = mappings
        logger.info(f"✅ Cargados {len(mappings)} mapeos de comandos de voz")
    
    def add_command_mapping(self, voice_command: str, action_config: Dict):
        """
        Agrega un mapeo de comando de voz.
        
        Args:
            voice_command: Comando de voz
            action_config: Configuración de la acción
        """
        self.command_mappings[voice_command] = action_config
        logger.debug(f"✅ Mapeo de voz agregado: '{voice_command}'")
    
    def add_contextual_command(self, context_key: str, voice_command: str, action_config: Dict):
        """
        Agrega un comando contextual.
        
        Args:
            context_key: Clave de contexto (ej: 'last_command|new_command')
            voice_command: Comando de voz
            action_config: Configuración de la acción
        """
        if context_key not in self.contextual_commands:
            self.contextual_commands[context_key] = {}
        
        self.contextual_commands[context_key][voice_command] = action_config
        logger.debug(f"✅ Comando contextual agregado: {context_key} -> '{voice_command}'")
    
    def learn_command(self, voice_command: str, action_config: Dict):
        """
        Aprende un nuevo comando automáticamente.
        
        Args:
            voice_command: Comando de voz
            action_config: Configuración de la acción
        """
        self.learned_commands[voice_command] = action_config
        logger.info(f"🎓 Comando aprendido: '{voice_command}'")
    
    def get_available_commands(self) -> List[str]:
        """
        Obtiene lista de comandos disponibles.
        
        Returns:
            Lista de comandos de voz
        """
        commands = list(self.command_mappings.keys())
        commands.extend(self.learned_commands.keys())
        return sorted(list(set(commands)))
    
    def get_command_stats(self) -> Dict:
        """
        Obtiene estadísticas de comandos.
        
        Returns:
            Diccionario con estadísticas
        """
        return {
            'total_mappings': len(self.command_mappings),
            'total_learned': len(self.learned_commands),
            'total_contextual': len(self.contextual_commands),
            'stats': self.stats.copy(),
            'most_used': sorted(self.command_frequency.items(), key=lambda x: x[1], reverse=True)[:5],
            'context': {
                'last_command': self.context['last_command'],
                'last_action': self.context['last_action'],
                'last_topic': self.context['last_topic'],
                'history_size': len(self.context['conversation_history'])
            }
        }
    
    def clear_context(self):
        """Limpia el contexto de conversación."""
        self.context = {
            'last_command': None,
            'last_action': None,
            'last_topic': None,
            'conversation_history': [],
            'user_preferences': {}
        }
        logger.debug("✅ Contexto de conversación limpiado")
    
    def set_confidence_threshold(self, threshold: float):
        """
        Establece umbral de confianza.
        
        Args:
            threshold: Nuevo umbral (0.0 a 1.0)
        """
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"🔄 Umbral de confianza cambiado: {threshold:.2f}")
    
    def set_similarity_threshold(self, threshold: float):
        """
        Establece umbral de similitud.
        
        Args:
            threshold: Nuevo umbral (0.0 a 1.0)
        """
        self.similarity_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"🔄 Umbral de similitud cambiado: {threshold:.2f}")
    
    def suggest_commands(self, partial_text: str, limit: int = 5) -> List[str]:
        """
        Sugiere comandos basados en texto parcial.
        
        Args:
            partial_text: Texto parcial del comando
            limit: Número máximo de sugerencias
            
        Returns:
            Lista de comandos sugeridos
        """
        suggestions = []
        partial_lower = partial_text.lower()
        
        for command in self.get_available_commands():
            if partial_lower in command.lower():
                suggestions.append(command)
                if len(suggestions) >= limit:
                    break
        
        # Ordenar por frecuencia de uso
        suggestions.sort(key=lambda x: self.command_frequency.get(x, 0), reverse=True)
        
        return suggestions[:limit]