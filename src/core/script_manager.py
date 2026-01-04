"""
🚀 SCRIPT MANAGER - Gestor de Scripts para Quick Menu
====================================================
Carga, filtra y ejecuta scripts del catálogo según el OS del perfil activo.
"""

import json
import platform
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScriptManager:
    """Gestor centralizado de scripts para el Quick Menu."""
    
    def __init__(self):
        """Inicializa el gestor de scripts."""
        self.catalog_path = self._get_catalog_path()
        self.scripts: List[Dict[str, Any]] = []
        self.current_os = self._detect_os()
        
        # Cargar catálogo
        self.load_catalog()
    
    def _get_catalog_path(self) -> Path:
        """Obtiene la ruta del catálogo de scripts."""
        # Relativo a este archivo: src/core/script_manager.py -> src/config/scripts_catalog.json
        current_file = Path(__file__).resolve()
        src_dir = current_file.parent.parent
        catalog_path = src_dir / "config" / "scripts_catalog.json"
        return catalog_path
    
    def _detect_os(self) -> str:
        """Detecta el sistema operativo actual."""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        else:
            return "any"
    
    def load_catalog(self) -> bool:
        """
        Carga el catálogo de scripts desde el JSON.
        
        Returns:
            True si se cargó correctamente, False en caso de error
        """
        try:
            if not self.catalog_path.exists():
                logger.warning(f"Catálogo de scripts no encontrado: {self.catalog_path}")
                self.scripts = []
                return False
            
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.scripts = data.get('scripts', [])
            logger.info(f"✅ Catálogo de scripts cargado: {len(self.scripts)} scripts")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando catálogo de scripts: {e}")
            self.scripts = []
            return False
    
    def get_scripts_for_os(self, os_type: str = None) -> List[Dict[str, Any]]:
        """
        Obtiene scripts compatibles con el OS especificado.
        
        Args:
            os_type: Sistema operativo ('windows', 'linux', 'any'). 
                     Si es None, usa el OS actual del sistema.
        
        Returns:
            Lista de scripts compatibles
        """
        if os_type is None:
            os_type = self.current_os
        
        compatible_scripts = []
        
        for script in self.scripts:
            if not script.get('enabled', True):
                continue
            
            script_os = script.get('os_type', 'any')
            
            # Script es compatible si:
            # 1. Script es 'any' (funciona en todos)
            # 2. OS del perfil es 'any' (acepta todos)
            # 3. OS del perfil coincide con el script
            if script_os == 'any' or os_type == 'any' or script_os == os_type:
                compatible_scripts.append(script)
        
        return compatible_scripts
    
    def get_script_path(self, script: Dict[str, Any], os_type: str = None) -> Optional[Path]:
        """
        Obtiene la ruta del script según el OS.
        
        Args:
            script: Diccionario con datos del script
            os_type: Sistema operativo. Si es None, usa el OS actual.
        
        Returns:
            Path absoluto al script, o None si no existe
        """
        if os_type is None:
            os_type = self.current_os
        
        # Seleccionar la ruta correcta según el OS
        if os_type == "windows":
            relative_path = script.get('windows_path')
        elif os_type == "linux":
            relative_path = script.get('linux_path')
        else:
            # Si es 'any', intentar con el OS actual del sistema
            if self.current_os == "windows":
                relative_path = script.get('windows_path')
            else:
                relative_path = script.get('linux_path')
        
        if not relative_path:
            logger.warning(f"No se encontró ruta para script '{script.get('name')}' en OS '{os_type}'")
            return None
        
        # Convertir ruta relativa a absoluta
        # Relativo a src/config/scripts_catalog.json -> raíz del proyecto
        src_dir = self.catalog_path.parent.parent
        project_root = src_dir.parent
        script_path = project_root / relative_path
        
        return script_path
    
    def execute_script(self, script_id: str, os_type: str = None) -> bool:
        """
        Ejecuta un script por su ID.
        
        Args:
            script_id: ID del script a ejecutar
            os_type: Sistema operativo. Si es None, usa el OS actual.
        
        Returns:
            True si se ejecutó correctamente, False en caso de error
        """
        # Buscar el script por ID
        script = None
        for s in self.scripts:
            if s.get('id') == script_id:
                script = s
                break
        
        if not script:
            logger.error(f"❌ Script no encontrado: {script_id}")
            return False
        
        # Obtener ruta del script
        script_path = self.get_script_path(script, os_type)
        
        if not script_path or not script_path.exists():
            logger.error(f"❌ Archivo de script no existe: {script_path}")
            return False
        
        # Ejecutar el script
        try:
            import platform
            
            # Método ROBUSTO para Windows: os.startfile
            # Esto evita todos los problemas de quoting de cmd/powershell
            if platform.system().lower() == 'windows':
                logger.info(f"🚀 Ejecutando script con os.startfile: {script_path}")
                os.startfile(script_path)
                logger.info(f"✅ Script lanzado: {script.get('name')}")
                return True
                
            # Método para Linux: BashController
            else:
                from controllers.bash_controller import BashController
                bash_controller = BashController()
                
                cmd_str = f'"{str(script_path)}"'
                logger.info(f"🚀 Enviando comando a BashController (Linux): {cmd_str}")
                
                result = bash_controller.execute(cmd_str)
                
                if result.get('success'):
                    logger.info(f"✅ Script ejecutado: {script.get('name')}")
                    return True
                else:
                    logger.error(f"❌ Error ejecutando script: {result.get('error')}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ Excepción ejecutando script '{script.get('name')}': {e}")
            return False
    
    def get_script_by_id(self, script_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un script por su ID.
        
        Args:
            script_id: ID del script
        
        Returns:
            Diccionario con datos del script, o None si no existe
        """
        for script in self.scripts:
            if script.get('id') == script_id:
                return script
        return None
    
    def get_categories(self) -> List[str]:
        """
        Obtiene todas las categorías únicas de scripts.
        
        Returns:
            Lista de nombres de categorías
        """
        categories = set()
        for script in self.scripts:
            category = script.get('category', 'otros')
            categories.add(category)
        return sorted(list(categories))
