"""
🎭 PROFILE MANAGER - Gestor centralizado de perfiles para NYX
=============================================================
Maneja la carga, guardado, creación y sincronización de perfiles.
Integra con ProfileRuntime para ejecución en tiempo real.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class ProfileData:
    """Estructura de datos para un perfil de NYX."""
    profile_name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = "Sistema"
    gestures: Dict[str, Dict] = field(default_factory=dict)
    voice_commands: Dict[str, Dict] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    enabled_modules: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validar y normalizar datos del perfil."""
        # Normalizar nombres de módulos
        valid_modules = ['hand', 'arm', 'voice', 'keyboard', 'mouse', 'window', 'bash']
        self.enabled_modules = [m for m in self.enabled_modules if m in valid_modules]
        
        # Asegurar campos mínimos en gestos
        for gesture_name, gesture_data in self.gestures.items():
            gesture_data.setdefault('enabled', True)
            gesture_data.setdefault('confidence', 0.7)
            gesture_data.setdefault('type', 'hand')
            gesture_data.setdefault('hand', 'right')
            
        # Asegurar campos mínimos en comandos de voz
        for cmd_name, cmd_data in self.voice_commands.items():
            cmd_data.setdefault('enabled', True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para JSON."""
        return {
            'profile_name': self.profile_name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'gestures': self.gestures,
            'voice_commands': self.voice_commands,
            'settings': self.settings,
            'enabled_modules': self.enabled_modules
        }


class ProfileManager:
    """Gestor centralizado de perfiles para NYX."""
    
    # Singleton para acceso global
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProfileManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Inicializa el gestor de perfiles (solo una vez)."""
        if self._initialized:
            return
        
        self.profiles_dir = self._get_profiles_dir()
        self.profiles: Dict[str, ProfileData] = {}
        self.profile_runtimes: Dict[str, Any] = {}  # Cache de ProfileRuntime
        
        # Crear directorio si no existe
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Cargar perfiles
        self.load_all_profiles()
        
        # Verificar perfiles por defecto
        self._ensure_default_profiles()
        
        self._initialized = True
        logger.info(f"✅ ProfileManager inicializado en {self.profiles_dir}")
    
    def _get_profiles_dir(self) -> Path:
        """Obtiene el directorio de perfiles según la arquitectura de NYX."""
        # Intentar diferentes rutas en orden de prioridad
        possible_paths = [
            Path("src/config/profiles"),           # Estructura estándar
            Path("config/profiles"),                # Alternativa
            Path("profiles"),                       # Raíz del proyecto
            Path.home() / ".config" / "nyx" / "profiles"  # Config global
        ]
        
        for path in possible_paths:
            if path.exists():
                logger.debug(f"📁 Directorio de perfiles encontrado: {path}")
                return path
        
        # Crear estructura estándar si no existe
        default_path = Path("src/config/profiles")
        default_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Directorio de perfiles creado: {default_path}")
        return default_path
    
    def load_all_profiles(self) -> int:
        """
        Carga todos los perfiles desde disco.
        
        Returns:
            Número de perfiles cargados
        """
        try:
            self.profiles.clear()
            self.profile_runtimes.clear()
            
            profile_files = list(self.profiles_dir.glob("*.json"))
            
            if not profile_files:
                logger.warning("⚠️ No se encontraron perfiles en disco")
                return 0
            
            loaded_count = 0
            for profile_file in profile_files:
                try:
                    profile_data = self._load_profile_file(profile_file)
                    if profile_data:
                        self.profiles[profile_data.profile_name] = profile_data
                        loaded_count += 1
                        logger.debug(f"📂 Perfil cargado: {profile_data.profile_name}")
                        
                except Exception as e:
                    logger.error(f"❌ Error cargando {profile_file.name}: {e}")
            
            logger.info(f"✅ Cargados {loaded_count}/{len(profile_files)} perfiles")
            return loaded_count
            
        except Exception as e:
            logger.error(f"❌ Error cargando perfiles: {e}")
            return 0
    
    def _load_profile_file(self, file_path: Path) -> Optional[ProfileData]:
        """Carga un perfil desde archivo JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validar estructura básica
            if 'profile_name' not in data:
                logger.warning(f"⚠️ Archivo {file_path.name} no tiene profile_name")
                data['profile_name'] = file_path.stem
            
            # Crear objeto ProfileData
            profile = ProfileData(
                profile_name=data['profile_name'],
                description=data.get('description', ''),
                version=data.get('version', '1.0.0'),
                author=data.get('author', 'Sistema'),
                gestures=data.get('gestures', {}),
                voice_commands=data.get('voice_commands', {}),
                settings=data.get('settings', {}),
                enabled_modules=data.get('enabled_modules', [])
            )
            
            return profile
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON inválido en {file_path.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error procesando {file_path.name}: {e}")
            return None
    
    def _ensure_default_profiles(self):
        """Crea perfiles por defecto si no existen."""
        default_profiles = ['gamer', 'productivity', 'custom']
        
        for profile_name in default_profiles:
            if profile_name not in self.profiles:
                logger.info(f"🔄 Creando perfil por defecto: {profile_name}")
                self.create_default_profile(profile_name)
    
    def get_profile(self, name: str) -> Optional[ProfileData]:
        """
        Obtiene un perfil por nombre.
        
        Args:
            name: Nombre del perfil
            
        Returns:
            ProfileData o None si no existe
        """
        # Verificar en caché primero
        if name in self.profiles:
            return self.profiles[name]
        
        # Intentar cargar desde disco
        profile_file = self.profiles_dir / f"{name}.json"
        if profile_file.exists():
            profile_data = self._load_profile_file(profile_file)
            if profile_data:
                self.profiles[name] = profile_data
                return profile_data
        
        return None
    
    def get_profile_runtime(self, name: str) -> Optional[Any]:
        """
        Obtiene (o crea) un ProfileRuntime para un perfil.
        
        Args:
            name: Nombre del perfil
            
        Returns:
            ProfileRuntime o None si no existe
        """
        # Usar caché si está disponible
        if name in self.profile_runtimes:
            return self.profile_runtimes[name]
        
        # Obtener datos del perfil
        profile_data = self.get_profile(name)
        if not profile_data:
            logger.error(f"❌ No se puede crear ProfileRuntime: perfil '{name}' no existe")
            return None
        
        try:
            # Importar y crear ProfileRuntime
            from core.profile_runtime import ProfileRuntime
            
            profile_runtime = ProfileRuntime(profile_data.to_dict())
            self.profile_runtimes[name] = profile_runtime  # Cachear
            
            logger.info(f"✅ ProfileRuntime creado para perfil: {name}")
            return profile_runtime
            
        except ImportError as e:
            logger.error(f"❌ No se pudo importar ProfileRuntime: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error creando ProfileRuntime: {e}")
            return None
    
    def save_profile(self, profile_data: ProfileData) -> Tuple[bool, str]:
        """
        Guarda un perfil en disco.
        
        Args:
            profile_data: Datos del perfil
            
        Returns:
            (success, message)
        """
        try:
            # Validar nombre
            if not profile_data.profile_name or profile_data.profile_name.strip() == "":
                return False, "Nombre de perfil inválido"
            
            # Preparar ruta
            profile_name = profile_data.profile_name
            profile_file = self.profiles_dir / f"{profile_name}.json"
            
            # Guardar en disco
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Actualizar caché
            self.profiles[profile_name] = profile_data
            
            # Invalidar ProfileRuntime cache si existe
            if profile_name in self.profile_runtimes:
                del self.profile_runtimes[profile_name]
            
            logger.info(f"💾 Perfil guardado: {profile_name}")
            return True, f"Perfil '{profile_name}' guardado correctamente"
            
        except PermissionError:
            error_msg = f"Permiso denegado para guardar perfil: {profile_data.profile_name}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error guardando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def delete_profile(self, name: str) -> Tuple[bool, str]:
        """
        Elimina un perfil.
        
        Args:
            name: Nombre del perfil a eliminar
            
        Returns:
            (success, message)
        """
        try:
            # Verificar que existe
            if name not in self.profiles:
                return False, f"Perfil '{name}' no existe"
            
            # Eliminar de caché
            if name in self.profiles:
                del self.profiles[name]
            
            if name in self.profile_runtimes:
                del self.profile_runtimes[name]
            
            # Eliminar archivo
            profile_file = self.profiles_dir / f"{name}.json"
            if profile_file.exists():
                profile_file.unlink()
            
            logger.info(f"🗑️ Perfil eliminado: {name}")
            return True, f"Perfil '{name}' eliminado correctamente"
            
        except PermissionError:
            error_msg = f"Permiso denegado para eliminar perfil: {name}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Error eliminando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def create_default_profile(self, name: str, profile_type: str = None) -> Optional[ProfileData]:
        """
        Crea un perfil por defecto.
        
        Args:
            name: Nombre del perfil
            profile_type: Tipo de perfil (gamer, productivity, custom)
            
        Returns:
            ProfileData creado o None si hay error
        """
        try:
            # Determinar tipo si no se especifica
            if profile_type is None:
                if name.lower() in ['gamer', 'gaming', 'juego']:
                    profile_type = 'gamer'
                elif name.lower() in ['productivity', 'productividad', 'trabajo']:
                    profile_type = 'productivity'
                else:
                    profile_type = 'custom'
            
            # Crear perfil según tipo
            if profile_type == 'gamer':
                profile_data = self._create_gamer_profile(name)
            elif profile_type == 'productivity':
                profile_data = self._create_productivity_profile(name)
            else:
                profile_data = self._create_custom_profile(name)
            
            # Guardar automáticamente
            success, message = self.save_profile(profile_data)
            if success:
                logger.info(f"✅ Perfil por defecto creado: {name} ({profile_type})")
                return profile_data
            else:
                logger.error(f"❌ Error guardando perfil por defecto: {message}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error creando perfil por defecto: {e}")
            return None
    
    def _create_gamer_profile(self, name: str) -> ProfileData:
        """Crea perfil para gaming."""
        return ProfileData(
            profile_name=name,
            description="Perfil para gaming - gestos rápidos y precisos",
            version="1.0.0",
            author="NYX Sistema",
            gestures={
                "fist": {
                    "action": "keyboard",
                    "command": "ctrl+f",
                    "description": "Abrir búsqueda en juego",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.7
                },
                "peace": {
                    "action": "keyboard",
                    "command": "esc",
                    "description": "Abrir menú/pausa",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.7
                },
                "thumbs_up": {
                    "action": "bash",
                    "command": "xdotool key F11",
                    "description": "Pantalla completa",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "enabled": True,
                    "confidence": 0.6
                },
                "point": {
                    "action": "mouse",
                    "command": "move",
                    "description": "Controlar cursor",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.5
                }
            },
            voice_commands={
                "nyx abre discord": {
                    "action": "bash",
                    "command": "discord",
                    "description": "Abrir Discord",
                    "enabled": True
                },
                "nyx captura pantalla": {
                    "action": "bash",
                    "command": "gnome-screenshot",
                    "description": "Tomar screenshot",
                    "enabled": True
                }
            },
            settings={
                "mouse_sensitivity": 1.5,
                "keyboard_delay": 0.1,
                "gesture_cooldown": 0.3,
                "sensitivity": 7,
                "response_time": 0.3
            },
            enabled_modules=["hand", "voice", "keyboard", "mouse", "bash"]
        )
    
    def _create_productivity_profile(self, name: str) -> ProfileData:
        """Crea perfil para productividad."""
        return ProfileData(
            profile_name=name,
            description="Perfil para trabajo y productividad",
            version="1.0.0",
            author="NYX Sistema",
            gestures={
                "ok": {
                    "action": "keyboard",
                    "command": "enter",
                    "description": "Confirmar/Aceptar",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.7
                },
                "thumbs_up": {
                    "action": "keyboard",
                    "command": "ctrl+s",
                    "description": "Guardar documento",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.7
                },
                "peace": {
                    "action": "keyboard",
                    "command": "ctrl+z",
                    "description": "Deshacer",
                    "hand": "right",
                    "type": "hand",
                    "enabled": True,
                    "confidence": 0.7
                }
            },
            voice_commands={
                "nyx abre chrome": {
                    "action": "bash",
                    "command": "google-chrome",
                    "description": "Abrir Chrome",
                    "enabled": True
                },
                "nyx abre terminal": {
                    "action": "bash",
                    "command": "gnome-terminal",
                    "description": "Abrir terminal",
                    "enabled": True
                }
            },
            settings={
                "mouse_sensitivity": 1.0,
                "keyboard_delay": 0.2,
                "gesture_cooldown": 0.5,
                "sensitivity": 5,
                "response_time": 0.4
            },
            enabled_modules=["hand", "voice", "keyboard", "mouse", "bash", "window"]
        )
    
    def _create_custom_profile(self, name: str) -> ProfileData:
        """Crea perfil personalizado vacío."""
        return ProfileData(
            profile_name=name,
            description="Perfil personalizado",
            version="1.0.0",
            author="Usuario",
            gestures={},
            voice_commands={},
            settings={},
            enabled_modules=["hand", "voice"]
        )
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        Lista todos los perfiles disponibles con información.
        
        Returns:
            Lista de diccionarios con información de perfiles
        """
        profiles_info = []
        
        for name, profile in self.profiles.items():
            profiles_info.append({
                'name': name,
                'description': profile.description,
                'version': profile.version,
                'author': profile.author,
                'gesture_count': len(profile.gestures),
                'voice_command_count': len(profile.voice_commands),
                'enabled_modules': profile.enabled_modules,
                'file_path': str(self.profiles_dir / f"{name}.json")
            })
        
        return profiles_info
    
    def get_profile_names(self) -> List[str]:
        """Obtiene lista de nombres de perfiles."""
        return list(self.profiles.keys())
    
    def get_profile_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de un perfil."""
        profile = self.get_profile(name)
        if not profile:
            return None
        
        return {
            'name': profile.profile_name,
            'description': profile.description,
            'version': profile.version,
            'author': profile.author,
            'gestures': list(profile.gestures.keys()),
            'voice_commands': list(profile.voice_commands.keys()),
            'settings': profile.settings,
            'enabled_modules': profile.enabled_modules,
            'gesture_count': len(profile.gestures),
            'voice_command_count': len(profile.voice_commands),
            'has_runtime': name in self.profile_runtimes
        }
    
    def update_profile(self, name: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Actualiza un perfil existente.
        
        Args:
            name: Nombre del perfil
            updates: Diccionario con actualizaciones
            
        Returns:
            (success, message)
        """
        profile = self.get_profile(name)
        if not profile:
            return False, f"Perfil '{name}' no encontrado"
        
        try:
            # Aplicar actualizaciones
            if 'description' in updates:
                profile.description = updates['description']
            if 'version' in updates:
                profile.version = updates['version']
            if 'author' in updates:
                profile.author = updates['author']
            if 'gestures' in updates:
                profile.gestures.update(updates['gestures'])
            if 'voice_commands' in updates:
                profile.voice_commands.update(updates['voice_commands'])
            if 'settings' in updates:
                profile.settings.update(updates['settings'])
            if 'enabled_modules' in updates:
                profile.enabled_modules = updates['enabled_modules']
            
            # Guardar cambios
            return self.save_profile(profile)
            
        except Exception as e:
            error_msg = f"Error actualizando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def duplicate_profile(self, source_name: str, new_name: str) -> Tuple[bool, str]:
        """
        Duplica un perfil existente.
        
        Args:
            source_name: Nombre del perfil original
            new_name: Nombre para la copia
            
        Returns:
            (success, message)
        """
        source_profile = self.get_profile(source_name)
        if not source_profile:
            return False, f"Perfil original '{source_name}' no encontrado"
        
        # Verificar que el nuevo nombre no exista
        if new_name in self.profiles:
            return False, f"Ya existe un perfil con nombre '{new_name}'"
        
        try:
            # Crear copia
            new_profile = ProfileData(
                profile_name=new_name,
                description=f"Copia de {source_profile.description}",
                version=source_profile.version,
                author=source_profile.author,
                gestures=source_profile.gestures.copy(),
                voice_commands=source_profile.voice_commands.copy(),
                settings=source_profile.settings.copy(),
                enabled_modules=source_profile.enabled_modules.copy()
            )
            
            # Guardar copia
            return self.save_profile(new_profile)
            
        except Exception as e:
            error_msg = f"Error duplicando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def export_profile(self, name: str, export_path: Path) -> Tuple[bool, str]:
        """
        Exporta un perfil a un archivo.
        
        Args:
            name: Nombre del perfil
            export_path: Ruta donde exportar
            
        Returns:
            (success, message)
        """
        profile = self.get_profile(name)
        if not profile:
            return False, f"Perfil '{name}' no encontrado"
        
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.info(f"📤 Perfil exportado: {name} -> {export_path}")
            return True, f"Perfil exportado a {export_path}"
            
        except Exception as e:
            error_msg = f"Error exportando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def import_profile(self, import_path: Path) -> Tuple[bool, str]:
        """
        Importa un perfil desde un archivo.
        
        Args:
            import_path: Ruta del archivo a importar
            
        Returns:
            (success, message)
        """
        try:
            profile_data = self._load_profile_file(import_path)
            if not profile_data:
                return False, "Archivo de perfil inválido"
            
            # Verificar que no exista
            if profile_data.profile_name in self.profiles:
                return False, f"Ya existe un perfil con nombre '{profile_data.profile_name}'"
            
            # Guardar en la ubicación estándar
            return self.save_profile(profile_data)
            
        except Exception as e:
            error_msg = f"Error importando perfil: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg
    
    def cleanup(self):
        """Limpia recursos y caché."""
        self.profile_runtimes.clear()
        logger.info("✅ ProfileManager limpiado")


# Uso en NYX
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Obtener instancia del ProfileManager
    print("🎭 Probando ProfileManager para NYX...")
    manager = ProfileManager()
    
    # Listar perfiles
    profiles = manager.list_profiles()
    print(f"\n📋 Perfiles disponibles ({len(profiles)}):")
    for profile_info in profiles:
        print(f"  • {profile_info['name']}: {profile_info['description']}")
        print(f"    Gestos: {profile_info['gesture_count']}, "
              f"Comandos voz: {profile_info['voice_command_count']}")
    
    # Obtener ProfileRuntime para un perfil
    print("\n🔧 Probando ProfileRuntime...")
    runtime = manager.get_profile_runtime("gamer")
    if runtime:
        print(f"  ✅ ProfileRuntime creado para 'gamer'")
        print(f"  📊 Gestos disponibles: {runtime.get_gesture_count()}")
    else:
        print("  ❌ Error creando ProfileRuntime")
    
    # Crear un perfil de prueba
    print("\n➕ Creando perfil de prueba...")
    test_profile = manager.create_default_profile("prueba", "custom")
    if test_profile:
        print(f"  ✅ Perfil 'prueba' creado")
        
        # Actualizar perfil
        print("\n✏️ Actualizando perfil...")
        success, message = manager.update_profile("prueba", {
            "description": "Perfil de prueba actualizado",
            "settings": {"test_setting": "valor"}
        })
        print(f"  {'✅' if success else '❌'} {message}")
        
        # Duplicar perfil
        print("\n📋 Duplicando perfil...")
        success, message = manager.duplicate_profile("prueba", "prueba_copia")
        print(f"  {'✅' if success else '❌'} {message}")
        
        # Eliminar perfiles de prueba
        print("\n🗑️ Limpiando perfiles de prueba...")
        manager.delete_profile("prueba")
        manager.delete_profile("prueba_copia")
        print("  ✅ Perfiles de prueba eliminados")
    
    # Mostrar estadísticas finales
    profiles = manager.list_profiles()
    print(f"\n📊 Perfiles finales: {len(profiles)}")
    
    # Limpiar
    manager.cleanup()
    print("\n✅ Prueba de ProfileManager completada")