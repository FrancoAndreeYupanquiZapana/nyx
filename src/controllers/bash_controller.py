"""
📁 BASH CONTROLLER - Control de Comandos Bash/Shell
==================================================
Ejecuta comandos de terminal/bash en el sistema operativo.
Usa subprocess para ejecutar comandos de forma segura y controlada.
"""

import os
import sys
import subprocess
import threading
import time
import shlex
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class BashController:
    """Controlador de comandos Bash/Shell."""
    
    def __init__(self, working_dir: str = None, timeout: int = 30):
        """
        Inicializa el controlador de bash.
        
        Args:
            working_dir: Directorio de trabajo por defecto
            timeout: Tiempo máximo de ejecución por defecto (segundos)
        """
        # Configuración de ejecución
        self.default_timeout = timeout
        self.default_working_dir = working_dir or os.getcwd()
        self.shell = self._detect_shell()
        
        # Estado y seguimiento de procesos
        self.active_processes = {}
        self.process_counter = 0
        
        # Historial de comandos
        self.command_history = []
        self.max_history_size = 100
        
        # Scripts y comandos predefinidos
        self.scripts = {}
        self.aliases = {}
        
        # Estadísticas
        self.stats = {
            'commands_executed': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'total_execution_time': 0.0,
            'background_commands': 0,
            'scripts_executed': 0
        }
        
        # Configurar aliases básicos
        self._setup_default_aliases()
        
        logger.info(f"✅ BashController inicializado (shell: {self.shell}, dir: {self.default_working_dir})")
    
    def _detect_shell(self) -> str:
        """Detecta el shell del sistema."""
        if os.name == 'nt':  # Windows
            return 'cmd' if 'COMSPEC' in os.environ else 'powershell'
        else:  # Unix/Linux/Mac
            return os.environ.get('SHELL', 'bash')
    
    def _setup_default_aliases(self):
        """Configura aliases por defecto."""
        self.aliases = {
            'll': 'ls -la',
            'la': 'ls -a',
            'l': 'ls -CF',
            '..': 'cd ..',
            '...': 'cd ../..',
            '....': 'cd ../../..',
            'clean': 'rm -f *~ .*~ 2>/dev/null || del *~ 2>nul',
            'py': 'python',
            'py3': 'python3',
            'ip': 'ipconfig' if os.name == 'nt' else 'ifconfig',
            'ports': 'netstat -tulpn' if os.name != 'nt' else 'netstat -ano',
        }
    
    def execute(self, 
                command: str, 
                working_dir: str = None, 
                timeout: int = None,
                background: bool = False,
                capture_output: bool = True,
                realtime_output: bool = False,
                callback: callable = None) -> Dict[str, Any]:
        """
        Ejecuta un comando bash/shell.
        
        Args:
            command: Comando a ejecutar
            working_dir: Directorio de trabajo
            timeout: Tiempo máximo de ejecución
            background: Ejecutar en segundo plano
            capture_output: Capturar salida del comando
            realtime_output: Mostrar salida en tiempo real
            callback: Función a llamar al terminar (para background)
            
        Returns:
            Diccionario con resultados
        """
        start_time = time.time()
        process_id = self.process_counter
        self.process_counter += 1
        
        # Resolver alias
        original_command = command
        command = self._resolve_alias(command)
        
        # Preparar directorio de trabajo
        wd = working_dir or self.default_working_dir
        if not os.path.exists(wd):
            logger.warning(f"⚠️ Directorio no existe: {wd}, usando actual")
            wd = self.default_working_dir
        
        # Preparar comando para el shell específico
        shell_cmd = self._prepare_command(command)
        
        logger.debug(f"💻 Ejecutando comando: {command}")
        logger.debug(f"   En directorio: {wd}")
        
        # Guardar en historial
        self._add_to_history({
            'id': process_id,
            'command': original_command,
            'timestamp': time.time(),
            'working_dir': wd,
            'background': background
        })
        
        if background:
            return self._execute_background(
                process_id, shell_cmd, wd, callback, capture_output
            )
        else:
            return self._execute_foreground(
                process_id, shell_cmd, wd, timeout, capture_output, realtime_output
            )
    
    def _prepare_command(self, command: str) -> List[str]:
        """Prepara el comando según el shell."""
        if os.name == 'nt':  # Windows
            if self.shell == 'powershell':
                return ['powershell', '-Command', command]
            else:  # cmd
                return ['cmd', '/c', command]
        else:  # Unix/Linux/Mac
            return ['bash', '-c', command]
    
    def _resolve_alias(self, command: str) -> str:
        """Resuelve alias en el comando."""
        parts = command.strip().split(maxsplit=1)
        if parts and parts[0] in self.aliases:
            alias_cmd = self.aliases[parts[0]]
            if len(parts) > 1:
                return f"{alias_cmd} {parts[1]}"
            return alias_cmd
        return command
    
    def _add_to_history(self, entry: Dict):
        """Añade comando al historial."""
        self.command_history.append(entry)
        if len(self.command_history) > self.max_history_size:
            self.command_history.pop(0)
    
    def _execute_foreground(self, 
                           process_id: int, 
                           shell_cmd: List[str], 
                           working_dir: str,
                           timeout: int = None,
                           capture_output: bool = True,
                           realtime_output: bool = False) -> Dict[str, Any]:
        """Ejecuta comando en primer plano."""
        result = {
            'success': False,
            'process_id': process_id,
            'command': ' '.join(shell_cmd),
            'working_dir': working_dir,
            'output': '',
            'error': '',
            'return_code': -1,
            'execution_time': 0.0,
            'timed_out': False
        }
        
        timeout = timeout or self.default_timeout
        
        try:
            start_time = time.time()
            
            if capture_output:
                if realtime_output:
                    # Ejecutar con salida en tiempo real
                    process = subprocess.Popen(
                        shell_cmd,
                        cwd=working_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    output_lines = []
                    error_lines = []
                    
                    # Leer salida en tiempo real
                    from threading import Thread
                    
                    def read_output(pipe, store_list):
                        for line in iter(pipe.readline, ''):
                            store_list.append(line)
                            if realtime_output:
                                print(line.rstrip())
                    
                    # Hilos para leer stdout y stderr
                    stdout_thread = Thread(target=read_output, args=(process.stdout, output_lines))
                    stderr_thread = Thread(target=read_output, args=(process.stderr, error_lines))
                    
                    stdout_thread.start()
                    stderr_thread.start()
                    
                    # Esperar a que termine el proceso
                    process.wait(timeout=timeout)
                    
                    stdout_thread.join()
                    stderr_thread.join()
                    
                    result['output'] = ''.join(output_lines)
                    result['error'] = ''.join(error_lines)
                else:
                    # Capturar salida completa
                    process = subprocess.run(
                        shell_cmd,
                        cwd=working_dir,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        shell=False
                    )
                    
                    result['output'] = process.stdout
                    result['error'] = process.stderr
                    result['return_code'] = process.returncode
            else:
                # Sin capturar salida
                process = subprocess.run(
                    shell_cmd,
                    cwd=working_dir,
                    timeout=timeout,
                    shell=False
                )
                result['return_code'] = process.returncode
            
            execution_time = time.time() - start_time
            result['execution_time'] = execution_time
            result['success'] = result['return_code'] == 0
            
            if result['success']:
                self.stats['successful_commands'] += 1
                logger.debug(f"✅ Comando ejecutado exitosamente en {execution_time:.2f}s")
            else:
                self.stats['failed_commands'] += 1
                logger.warning(f"⚠️ Comando falló con código {result['return_code']}")
            
        except subprocess.TimeoutExpired:
            result['timed_out'] = True
            result['error'] = f"Comando expiró después de {timeout} segundos"
            self.stats['failed_commands'] += 1
            logger.error(f"❌ Timeout ejecutando comando")
            
        except FileNotFoundError:
            result['error'] = f"Comando no encontrado: {shell_cmd[0]}"
            self.stats['failed_commands'] += 1
            logger.error(f"❌ Comando no encontrado: {shell_cmd[0]}")
            
        except Exception as e:
            result['error'] = str(e)
            self.stats['failed_commands'] += 1
            logger.error(f"❌ Error ejecutando comando: {e}")
        
        finally:
            self.stats['commands_executed'] += 1
            self.stats['total_execution_time'] += result['execution_time']
        
        return result
    
    def _execute_background(self,
                           process_id: int,
                           shell_cmd: List[str],
                           working_dir: str,
                           callback: callable = None,
                           capture_output: bool = True) -> Dict[str, Any]:
        """Ejecuta comando en segundo plano."""
        result = {
            'success': True,
            'process_id': process_id,
            'command': ' '.join(shell_cmd),
            'working_dir': working_dir,
            'background': True,
            'thread': None
        }
        
        def run_background():
            try:
                if capture_output:
                    process = subprocess.Popen(
                        shell_cmd,
                        cwd=working_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        shell=False
                    )
                else:
                    process = subprocess.Popen(
                        shell_cmd,
                        cwd=working_dir,
                        shell=False
                    )
                
                self.active_processes[process_id] = process
                
                # Esperar a que termine
                stdout, stderr = process.communicate()
                return_code = process.returncode
                
                # Preparar resultado
                bg_result = {
                    'process_id': process_id,
                    'success': return_code == 0,
                    'return_code': return_code,
                    'output': stdout if capture_output else '',
                    'error': stderr if capture_output else '',
                    'completed': True
                }
                
                # Llamar callback si existe
                if callback:
                    callback(bg_result)
                
                logger.debug(f"✅ Comando en background {process_id} completado")
                
            except Exception as e:
                logger.error(f"❌ Error en comando background {process_id}: {e}")
                
                if callback:
                    callback({
                        'process_id': process_id,
                        'success': False,
                        'error': str(e),
                        'completed': True
                    })
            finally:
                # Remover del registro de procesos activos
                self.active_processes.pop(process_id, None)
                self.stats['background_commands'] += 1
        
        # Iniciar hilo
        thread = threading.Thread(target=run_background, daemon=True)
        thread.start()
        
        result['thread'] = thread
        self.active_processes[process_id] = thread
        
        logger.debug(f"🔁 Comando iniciado en background (ID: {process_id})")
        return result
    
    def execute_sudo(self, 
                     command: str, 
                     password: str = None,
                     **kwargs) -> Dict[str, Any]:
        """
        Ejecuta comando con privilegios de superusuario.
        
        Args:
            command: Comando a ejecutar
            password: Contraseña para sudo
            **kwargs: Argumentos adicionales para execute()
            
        Returns:
            Diccionario con resultados
        """
        if os.name == 'nt':
            # En Windows, ejecutar como administrador
            logger.warning("⚠️ Sudo no disponible en Windows, ejecutando normalmente")
            return self.execute(command, **kwargs)
        
        # En Unix/Linux, usar sudo
        sudo_cmd = f"sudo {command}"
        
        if password:
            # Usar echo para proporcionar contraseña (no muy seguro)
            full_cmd = f'echo "{password}" | {sudo_cmd}'
            return self.execute(full_cmd, **kwargs)
        else:
            return self.execute(sudo_cmd, **kwargs)
    
    def execute_python(self, 
                      code: str, 
                      **kwargs) -> Dict[str, Any]:
        """
        Ejecuta código Python.
        
        Args:
            code: Código Python a ejecutar
            **kwargs: Argumentos adicionales para execute()
            
        Returns:
            Diccionario con resultados
        """
        # Guardar código en archivo temporal
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            cmd = f"python {temp_file}"
            result = self.execute(cmd, **kwargs)
            
            # Añadir información adicional
            result['python_code'] = code
            result['temp_file'] = temp_file
            
            return result
        finally:
            # Limpiar archivo temporal
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def add_script(self, name: str, script: str) -> bool:
        """
        Agrega un script reutilizable.
        
        Args:
            name: Nombre del script
            script: Contenido del script
            
        Returns:
            True si se agregó correctamente
        """
        if not name or not script:
            logger.warning("⚠️ Nombre o script vacío")
            return False
        
        self.scripts[name] = script
        logger.debug(f"✅ Script agregado: '{name}'")
        return True
    
    def run_script(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta un script predefinido.
        
        Args:
            name: Nombre del script
            **kwargs: Argumentos adicionales para execute()
            
        Returns:
            Diccionario con resultados
        """
        if name not in self.scripts:
            logger.error(f"❌ Script '{name}' no encontrado")
            return {
                'success': False,
                'error': f"Script '{name}' no encontrado"
            }
        
        script_content = self.scripts[name]
        result = self.execute(script_content, **kwargs)
        result['script_name'] = name
        
        if result['success']:
            self.stats['scripts_executed'] += 1
        
        return result
    
    def add_alias(self, alias: str, command: str) -> bool:
        """
        Agrega un alias de comando.
        
        Args:
            alias: Nombre del alias
            command: Comando al que apunta
            
        Returns:
            True si se agregó correctamente
        """
        if not alias or not command:
            logger.warning("⚠️ Alias o comando vacío")
            return False
        
        self.aliases[alias] = command
        logger.debug(f"✅ Alias agregado: '{alias}' -> '{command}'")
        return True
    
    def get_process_status(self, process_id: int) -> Dict[str, Any]:
        """
        Obtiene estado de un proceso en background.
        
        Args:
            process_id: ID del proceso
            
        Returns:
            Diccionario con estado del proceso
        """
        if process_id in self.active_processes:
            process = self.active_processes[process_id]
            
            if isinstance(process, threading.Thread):
                return {
                    'process_id': process_id,
                    'alive': process.is_alive(),
                    'type': 'thread',
                    'active': True
                }
            elif isinstance(process, subprocess.Popen):
                return {
                    'process_id': process_id,
                    'alive': process.poll() is None,
                    'return_code': process.poll(),
                    'type': 'subprocess',
                    'active': True
                }
        
        return {
            'process_id': process_id,
            'alive': False,
            'active': False,
            'error': 'Proceso no encontrado'
        }
    
    def kill_process(self, process_id: int) -> bool:
        """
        Mata un proceso en ejecución.
        
        Args:
            process_id: ID del proceso
            
        Returns:
            True si se mató correctamente
        """
        if process_id not in self.active_processes:
            logger.warning(f"⚠️ Proceso {process_id} no encontrado")
            return False
        
        process = self.active_processes[process_id]
        
        try:
            if isinstance(process, subprocess.Popen):
                process.terminate()
                process.wait(timeout=5)
                logger.debug(f"✅ Proceso {process_id} terminado")
            elif isinstance(process, threading.Thread):
                # Los hilos no se pueden matar directamente en Python
                logger.warning(f"⚠️ No se puede terminar hilo {process_id}")
                return False
            
            self.active_processes.pop(process_id, None)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error terminando proceso {process_id}: {e}")
            return False
    
    def kill_all_processes(self) -> Dict[str, Any]:
        """
        Mata todos los procesos activos.
        
        Returns:
            Diccionario con resultados
        """
        results = {
            'total_processes': len(self.active_processes),
            'killed': 0,
            'failed': 0,
            'details': []
        }
        
        process_ids = list(self.active_processes.keys())
        
        for pid in process_ids:
            success = self.kill_process(pid)
            if success:
                results['killed'] += 1
                results['details'].append({'process_id': pid, 'status': 'killed'})
            else:
                results['failed'] += 1
                results['details'].append({'process_id': pid, 'status': 'failed'})
        
        logger.info(f"✅ Terminados {results['killed']}/{results['total_processes']} procesos")
        return results
    
    def change_directory(self, path: str) -> bool:
        """
        Cambia el directorio de trabajo por defecto.
        
        Args:
            path: Nuevo directorio
            
        Returns:
            True si se cambió correctamente
        """
        try:
            # Expandir variables de entorno y usuario
            expanded_path = os.path.expanduser(os.path.expandvars(path))
            
            if not os.path.exists(expanded_path):
                logger.error(f"❌ Directorio no existe: {expanded_path}")
                return False
            
            if not os.path.isdir(expanded_path):
                logger.error(f"❌ No es un directorio: {expanded_path}")
                return False
            
            self.default_working_dir = os.path.abspath(expanded_path)
            logger.info(f"📁 Directorio cambiado a: {self.default_working_dir}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cambiando directorio: {e}")
            return False
    
    def list_directory(self, path: str = None, detailed: bool = False) -> Dict[str, Any]:
        """
        Lista contenido de un directorio.
        
        Args:
            path: Directorio a listar (None = directorio actual)
            detailed: Mostrar información detallada
            
        Returns:
            Diccionario con resultados
        """
        target_dir = path or self.default_working_dir
        
        if not os.path.exists(target_dir):
            return {
                'success': False,
                'error': f"Directorio no existe: {target_dir}",
                'files': []
            }
        
        try:
            if detailed:
                import stat
                import datetime
                
                files = []
                for item in os.listdir(target_dir):
                    item_path = os.path.join(target_dir, item)
                    stat_info = os.stat(item_path)
                    
                    file_info = {
                        'name': item,
                        'is_dir': os.path.isdir(item_path),
                        'size': stat_info.st_size,
                        'modified': datetime.datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        'permissions': stat.filemode(stat_info.st_mode)
                    }
                    files.append(file_info)
                
                return {
                    'success': True,
                    'directory': target_dir,
                    'files': files,
                    'count': len(files)
                }
            else:
                files = os.listdir(target_dir)
                return {
                    'success': True,
                    'directory': target_dir,
                    'files': files,
                    'count': len(files)
                }
                
        except Exception as e:
            logger.error(f"❌ Error listando directorio: {e}")
            return {
                'success': False,
                'error': str(e),
                'files': []
            }
    
    def get_history(self, limit: int = None) -> List[Dict]:
        """
        Obtiene historial de comandos.
        
        Args:
            limit: Límite de comandos a retornar
            
        Returns:
            Lista de comandos ejecutados
        """
        history = self.command_history.copy()
        
        if limit:
            history = history[-limit:]
        
        return history[::-1]  # Más recientes primero
    
    def clear_history(self) -> bool:
        """Limpia el historial de comandos."""
        self.command_history.clear()
        logger.debug("✅ Historial limpiado")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del controlador."""
        return {
            'shell': self.shell,
            'working_dir': self.default_working_dir,
            'stats': self.stats.copy(),
            'active_processes': len(self.active_processes),
            'scripts_count': len(self.scripts),
            'aliases_count': len(self.aliases),
            'history_size': len(self.command_history)
        }
    
    def execute_command(self, command: Dict) -> Dict[str, Any]:
        """
        Ejecuta un comando desde el formato estandarizado.
        
        Args:
            command: Diccionario con comando
                Formato: {
                    'type': 'bash',
                    'command': 'execute' | 'sudo' | 'python' | 'script' | 'cd' | 'ls' | 'kill',
                    'cmd': 'comando' (para execute),
                    'code': 'código python' (para python),
                    'script': 'nombre_script' (para script),
                    'path': 'ruta' (para cd/ls),
                    'process_id': 123 (para kill),
                    'background': False,
                    'timeout': 30,
                    'working_dir': '/path',
                    'capture_output': True
                }
            
        Returns:
            Diccionario con resultados
        """
        cmd_type = command.get('command', 'execute')
        
        try:
            if cmd_type == 'execute':
                cmd = command.get('cmd', '')
                if not cmd:
                    return {'success': False, 'error': 'Comando vacío'}
                
                return self.execute(
                    command=cmd,
                    working_dir=command.get('working_dir'),
                    timeout=command.get('timeout'),
                    background=command.get('background', False),
                    capture_output=command.get('capture_output', True),
                    realtime_output=command.get('realtime_output', False)
                )
            
            elif cmd_type == 'sudo':
                cmd = command.get('cmd', '')
                password = command.get('password')
                
                if not cmd:
                    return {'success': False, 'error': 'Comando vacío'}
                
                return self.execute_sudo(cmd, password, **{
                    'working_dir': command.get('working_dir'),
                    'timeout': command.get('timeout'),
                    'background': command.get('background', False)
                })
            
            elif cmd_type == 'python':
                code = command.get('code', '')
                
                if not code:
                    return {'success': False, 'error': 'Código vacío'}
                
                return self.execute_python(code, **{
                    'working_dir': command.get('working_dir'),
                    'timeout': command.get('timeout'),
                    'background': command.get('background', False)
                })
            
            elif cmd_type == 'script':
                script_name = command.get('script', '')
                
                if not script_name:
                    return {'success': False, 'error': 'Nombre de script vacío'}
                
                return self.run_script(script_name, **{
                    'working_dir': command.get('working_dir'),
                    'timeout': command.get('timeout'),
                    'background': command.get('background', False)
                })
            
            elif cmd_type == 'cd':
                path = command.get('path', '')
                
                if not path:
                    return {'success': False, 'error': 'Ruta vacía'}
                
                success = self.change_directory(path)
                return {
                    'success': success,
                    'new_directory': self.default_working_dir if success else None
                }
            
            elif cmd_type == 'ls':
                path = command.get('path')
                detailed = command.get('detailed', False)
                return self.list_directory(path, detailed)
            
            elif cmd_type == 'kill':
                if command.get('all', False):
                    return self.kill_all_processes()
                else:
                    process_id = command.get('process_id')
                    if process_id is None:
                        return {'success': False, 'error': 'ID de proceso requerido'}
                    
                    success = self.kill_process(process_id)
                    return {'success': success, 'process_id': process_id}
            
            elif cmd_type == 'status':
                process_id = command.get('process_id')
                if process_id is None:
                    return {'success': False, 'error': 'ID de proceso requerido'}
                
                return self.get_process_status(process_id)
            
            elif cmd_type == 'history':
                limit = command.get('limit')
                return {'success': True, 'history': self.get_history(limit)}
            
            elif cmd_type == 'stats':
                return {'success': True, 'stats': self.get_stats()}
            
            else:
                return {'success': False, 'error': f'Tipo de comando desconocido: {cmd_type}'}
                
        except Exception as e:
            logger.error(f"❌ Error ejecutando comando bash {cmd_type}: {e}")
            return {'success': False, 'error': str(e)}
    
    def cleanup(self):
        """Limpia recursos y termina procesos activos."""
        self.kill_all_processes()
        logger.info("✅ BashController limpiado")

"""

# Ejemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Crear controlador
    bash = BashController()
    
    # Ejecutar comandos básicos
    print("=== Comando simple ===")
    result = bash.execute("echo 'Hola Mundo'")
    print(f"Éxito: {result['success']}")
    print(f"Salida: {result['output']}")
    
    print("\n=== Listar directorio ===")
    result = bash.list_directory(detailed=True)
    for file in result['files'][:5]:
        print(f"  {file['name']} ({'dir' if file['is_dir'] else 'file'})")
    
    print("\n=== Python code ===")
    result = bash.execute_python("""    """)
        
    import platform
    print(f"Sistema: {platform.system()}")
    print(f"Python: {platform.python_version()}")
    
    print(result['output'])
    
    # Mostrar estadísticas
    stats = bash.get_stats()
    print(f"\n=== Estadísticas ===")
    print(f"Comandos ejecutados: {stats['stats']['commands_executed']}")
    print(f"Éxitos: {stats['stats']['successful_commands']}")
    print(f"Scripts: {stats['scripts_count']}")
    
    # Limpiar
    bash.cleanup()
"""