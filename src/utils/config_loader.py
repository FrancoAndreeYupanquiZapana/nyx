"""
⚙️ CONFIG LOADER - Cargador de configuración NYX
================================================
Carga y gestiona configuraciones YAML/JSON para el sistema NYX.
Sigue la arquitectura modular y usa rutas relativas correctas.
"""

import yaml
from typing import Dict, List,Any, Optional, Union
import logging
import os
import json
import time
from pathlib import Path


logger = logging.getLogger(__name__)

class ConfigLoader:
    """Carga y gestiona configuraciones del sistema NYX."""
    
    def __init__(self, config_dir: str = None):
        """
        Inicializa el cargador de configuración para NYX.
        
        Args:
            config_dir: Directorio de configuraciones (opcional, auto-detecta)
        """

        # Auto-detectar directorio de configuración de NYX
        if config_dir is None:
            self.config_dir = self._find_config_dir()
        else:
            self.config_dir = Path(config_dir)
        
        logger.info(f"📂 ConfigLoader inicializado en: {self.config_dir}")
        
        # Crear directorio si no existe
        self.config_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuraciones en memoria
        self.system_config: Dict[str, Any] = {}
        self.settings: Dict[str, Any] = {}
        self.profiles: Dict[str, Dict[str, Any]] = {}
        
        # Cargar todas las configuraciones
        self._load_all_configs()
    
    def _find_config_dir(self) -> Path:
        """
        Encuentra automáticamente el directorio de configuración de NYX.
        
        Returns:
            Path al directorio de configuración
        """
        # Posibles ubicaciones (en orden de prioridad)
        # 1. Relativo al archivo actual (ubicación más segura: src/utils/config_loader.py -> src/config)
        src_dir = Path(__file__).resolve().parent.parent
        
        possible_paths = [
            src_dir / "config",
            Path.cwd() / "src" / "config",
            Path.cwd() / "config",
        ]
        
        # Filtrar paths None y verificar existencia
        valid_paths = [p for p in possible_paths if p is not None]
        
        for path in valid_paths:
            if path.exists():
                logger.debug(f"✅ Directorio de configuración encontrado: {path}")
                return path
        
        # Si no existe, crear el path estándar en src/
        default_path = Path.cwd() / "src" / "config"
        logger.info(f"📁 Creando directorio de configuración: {default_path}")
        return default_path
    
    def _load_all_configs(self):
        """Carga todas las configuraciones disponibles."""
        try:
            # 1. Cargar configuración del sistema
            system_file = self.config_dir / "system.yaml"
            if system_file.exists():
                self.system_config = self.load_yaml(system_file)
                logger.info("✅ Configuración del sistema cargada")
            else:
                self.system_config = self._create_default_system_config()
                self.save_system_config()
                logger.info("✅ Configuración del sistema creada por defecto")
            
            # 2. Cargar settings de la app
            settings_file = self.config_dir / "settings.yaml"
            if settings_file.exists():
                self.settings = self.load_yaml(settings_file)
                logger.info("✅ Settings de aplicación cargados")
            else:
                self.settings = self._create_default_settings()
                self.save_settings()
                logger.info("✅ Settings de aplicación creados por defecto")
            
            # 3. Cargar perfiles
            profiles_dir = self.config_dir / "profiles"
            profiles_dir.mkdir(exist_ok=True)
            
            # Cargar perfiles existentes
            profile_files = list(profiles_dir.glob("*.json"))
            if not profile_files:
                # Crear perfil por defecto si no hay
                default_profile = self._create_default_profile()
                self.save_profile("default", default_profile)
                profile_files = [profiles_dir / "default.json"]
            
            for profile_file in profile_files:
                profile_name = profile_file.stem
                self.profiles[profile_name] = self.load_json(profile_file)
                logger.info(f"✅ Perfil cargado: {profile_name}")
                
        except Exception as e:
            logger.error(f"❌ Error cargando configuraciones: {e}", exc_info=True)
    
    # ========== CONFIGURACIÓN DEL SISTEMA (para GesturePipeline) ==========
    
    def get_system_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuración del sistema para GesturePipeline.
        
        Returns:
            Diccionario con configuración del sistema
        """
        return self.system_config.copy()
    
    def update_system_config(self, updates: Dict[str, Any]):
        """
        Actualiza la configuración del sistema.
        
        Args:
            updates: Diccionario con actualizaciones
        """
        self._deep_update(self.system_config, updates)
    
    def save_system_config(self) -> bool:
        """Guarda la configuración del sistema en disco."""
        system_file = self.config_dir / "system.yaml"
        return self.save_yaml(self.system_config, system_file)
    
    # ========== PERFILES (para ProfileRuntime) ==========
    
    def get_profile(self, name: Union[str, Dict]) -> Optional[Dict[str, Any]]:
        """
        Obtiene un perfil por nombre.
        
        Args:
            name: Nombre del perfil o diccionario de perfil
            
        Returns:
            Datos del perfil o None si no existe
        """
        # Si se pasa un diccionario (por error de otras partes), extraer el nombre
        if isinstance(name, dict):
            # Si tiene 'profile_name', usalo
            if 'profile_name' in name:
                logger.warning(f"⚠️ get_profile recibió un dict, usando 'profile_name': {name['profile_name']}")
                name = name['profile_name']
            else:
                logger.error(f"❌ get_profile recibió un dict sin 'profile_name': {name}")
                return None
        
        if not isinstance(name, str):
            logger.error(f"❌ get_profile recibió un nombre inválido: {type(name)} - {name}")
            return None

        # Primero buscar en caché
        if name in self.profiles:
            return self.profiles[name].copy()
        
        # Intentar cargar desde disco
        profile_file = self.config_dir / "profiles" / f"{name}.json"
        if profile_file.exists():
            profile_data = self.load_json(profile_file)
            self.profiles[name] = profile_data
            return profile_data.copy()
        
        logger.warning(f"⚠️ Perfil no encontrado: {name}")
        return None
    
    def save_profile(self, name: str, profile_data: Dict[str, Any]) -> bool:
        """
        Guarda un perfil.
        
        Args:
            name: Nombre del perfil
            profile_data: Datos del perfil
            
        Returns:
            True si se guardó correctamente
        """
        try:
            profiles_dir = self.config_dir / "profiles"
            profiles_dir.mkdir(exist_ok=True)
            
            profile_file = profiles_dir / f"{name}.json"
            success = self.save_json(profile_data, profile_file)
            
            if success:
                self.profiles[name] = profile_data
                logger.info(f"💾 Perfil guardado: {name}")
            
            return success
        except Exception as e:
            logger.error(f"❌ Error guardando perfil {name}: {e}")
            return False
    
    def delete_profile(self, name: str) -> bool:
        """
        Elimina un perfil.
        
        Args:
            name: Nombre del perfil
            
        Returns:
            True si se eliminó correctamente
        """
        try:
            profile_file = self.config_dir / "profiles" / f"{name}.json"
            
            if profile_file.exists():
                profile_file.unlink()
                logger.info(f"🗑️ Perfil eliminado: {name}")
            
            # Remover de caché
            self.profiles.pop(name, None)
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando perfil {name}: {e}")
            return False
    
    def list_profiles(self) -> List[str]:
        """
        Lista todos los perfiles disponibles.
        
        Returns:
            Lista de nombres de perfiles
        """
        profiles_dir = self.config_dir / "profiles"
        return [f.stem for f in profiles_dir.glob("*.json")]
    
    # ========== SETTINGS (para UI y configuración de app) ==========
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.
        
        Args:
            key: Clave en formato 'seccion.subseccion.valor'
            default: Valor por defecto si no existe
            
        Returns:
            Valor de configuración
        """
        try:
            parts = key.split('.')
            value = self.settings
            
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, {})
                else:
                    return default
            
            return value if value != {} else default
        except Exception:
            return default
    
    def update_setting(self, key: str, value: Any) -> bool:
        """
        Actualiza un valor de configuración.
        
        Args:
            key: Clave en formato 'seccion.subseccion.valor'
            value: Nuevo valor
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            parts = key.split('.')
            target = self.settings
            
            # Navegar al diccionario padre
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            
            # Asignar valor
            target[parts[-1]] = value
            return True
        except Exception as e:
            logger.error(f"❌ Error actualizando configuración {key}: {e}")
            return False
    
    def save_settings(self) -> bool:
        """Guarda los settings actuales en disco."""
        settings_file = self.config_dir / "settings.yaml"
        return self.save_yaml(self.settings, settings_file)
    
    # ========== MÉTODOS UTILITARIOS ==========
    
    @staticmethod
    def load_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
        """Carga un archivo YAML."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"❌ Error cargando YAML {file_path}: {e}")
            return {}
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """Carga un archivo JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception as e:
            logger.error(f"❌ Error cargando JSON {file_path}: {e}")
            return {}
    
    @staticmethod
    def save_yaml(data: Dict[str, Any], file_path: Union[str, Path]) -> bool:
        """Guarda datos en archivo YAML."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando YAML {file_path}: {e}")
            return False
    
    @staticmethod
    def save_json(data: Dict[str, Any], file_path: Union[str, Path]) -> bool:
        """Guarda datos en archivo JSON."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando JSON {file_path}: {e}")
            return False
    
    @staticmethod
    def _deep_update(target: Dict, source: Dict):
        """Actualiza recursivamente un diccionario."""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                ConfigLoader._deep_update(target[key], value)
            else:
                target[key] = value
    
    # ========== CONFIGURACIONES POR DEFECTO ==========
    
    def _create_default_system_config(self) -> Dict[str, Any]:
        """Crea configuración del sistema por defecto para NYX."""
        return {
            'camera': {
                'device_id': 0,
                'width': 1280,
                'height': 720,
                'fps': 30,
                'mirror': True
            },
            'hand_detection': {
                'enabled': True,
                'max_num_hands': 2,
                'min_detection_confidence': 0.7,
                'min_tracking_confidence': 0.5,
                'model_complexity': 1
            },
            'arm_detection': {
                'enabled': False,
                'min_detection_confidence': 0.5,
                'min_tracking_confidence': 0.5,
                'model_complexity': 1
            },
            'voice_recognition': {
                'enabled': True,
                'activation_word': 'nyx',
                'energy_threshold': 300,
                'language': 'es-ES',
                'pause_threshold': 0.8,
                'dynamic_energy_threshold': True
            },
            'active_profile': 'gamer',
            'general': {
                'app_name': 'NYX',
                'version': '1.0.0',
                'debug_mode': False,
                'log_level': 'INFO',
                'language': 'es-ES',
                'theme': 'dark'
            },
            'quick_actions': {
                'screenshot': 'gnome-screenshot',
                'volume_up': 'amixer set Master 5%+',
                'volume_down': 'amixer set Master 5%-',
                'mute': 'amixer set Master mute',
                'unmute': 'amixer set Master unmute'
            },
            'ui': {
                'show_fps': True,
                'show_landmarks': True,
                'show_gesture_info': True,
                'camera_preview': True
            }
        }
    
    def _create_default_settings(self) -> Dict[str, Any]:
        """Crea settings por defecto para la app NYX."""
        return {
            'app': {
                'name': 'NYX',
                'version': '1.0.0',
                'activation_word': 'nyx',
                'log_level': 'INFO'
            },
            'detectors': {
                'hand': {'enabled': True, 'sensitivity': 0.7},
                'arm': {'enabled': False, 'sensitivity': 0.6},
                'voice': {'enabled': True, 'confidence': 0.8},
                'pose': {'enabled': False, 'sensitivity': 0.5}
            },
            'controllers': {
                'keyboard': {'enabled': True, 'press_delay': 0.1},
                'mouse': {'enabled': True, 'sensitivity': 1.0},
                'window': {'enabled': True},
                'bash': {'enabled': False, 'timeout': 30}
            },
            'ui': {
                'theme': 'dark',
                'show_fps': True,
                'show_landmarks': True,
                'camera_index': 0
            },
            'gestures': {
                'cooldown': 0.5,
                'min_confidence': 0.6,
                'max_gestures': 10
            }
        }
    
    def _create_default_profile(self) -> Dict[str, Any]:
        """Crea un perfil por defecto."""
        return {
            'profile_name': 'default',
            'description': 'Perfil por defecto de NYX',
            'version': '1.0.0',
            'author': 'Sistema',
            'gestures': {
                'fist': {
                    'action': 'keyboard',
                    'command': 'space',
                    'description': 'Saltar/Disparar',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                },
                'peace': {
                    'action': 'keyboard',
                    'command': 'esc',
                    'description': 'Menú/Pausa',
                    'hand': 'right',
                    'type': 'hand',
                    'enabled': True,
                    'confidence': 0.7
                }
            },
            'voice_commands': {
                'nyx ayuda': {
                    'action': 'help',
                    'command': 'show_help',
                    'description': 'Mostrar ayuda',
                    'enabled': True
                }
            },
            'settings': {
                'mouse_sensitivity': 1.0,
                'keyboard_delay': 0.1,
                'gesture_cooldown': 0.3
            },
            'enabled_modules': ['hand', 'voice', 'keyboard', 'mouse']
        }
    
    def reload(self):
        """Recarga todas las configuraciones desde disco."""
        logger.info("🔄 Recargando configuraciones...")
        self.profiles.clear()
        self._load_all_configs()
        logger.info("✅ Configuraciones recargadas")
    
    def get_config_info(self) -> Dict[str, Any]:
        """Obtiene información sobre la configuración cargada."""
        return {
            'config_dir': str(self.config_dir),
            'system_config_keys': list(self.system_config.keys()),
            'profiles_loaded': list(self.profiles.keys()),
            'settings_keys': list(self.settings.keys())
        }

# Instancia global para uso en toda la aplicación
config = ConfigLoader()