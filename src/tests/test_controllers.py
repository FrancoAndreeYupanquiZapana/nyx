"""
🧪 TEST CONTROLLERS - Pruebas para controladores
=================================================
Pruebas unitarias para los módulos de control.
"""

import pytest
import time
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Agregar al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controllers.keyboard_controller import KeyboardController
from controllers.mouse_controller import MouseController
from controllers.window_controller import WindowController
from controllers.bash_controller import BashController

class TestKeyboardController:
    """Pruebas para el controlador de teclado."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        # Usar mocks para keyboard module
        self.keyboard_patcher = patch('controllers.keyboard_controller.keyboard')
        self.mock_keyboard = self.keyboard_patcher.start()
        
        self.controller = KeyboardController()
    
    def teardown_method(self):
        """Limpieza después de cada test."""
        self.keyboard_patcher.stop()
        if hasattr(self, 'controller'):
            self.controller.cleanup()
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.controller is not None
        assert hasattr(self.controller, 'is_available')
        assert hasattr(self.controller, 'default_press_time')
        assert hasattr(self.controller, 'hold_keys')
    
    def test_press_key(self):
        """Test de presión de tecla individual."""
        # Configurar mock
        self.mock_keyboard.press.return_value = None
        self.mock_keyboard.release.return_value = None
        
        result = self.controller.press_key('a', 0.1)
        
        assert result == True
        self.mock_keyboard.press.assert_called_once_with('a')
        self.mock_keyboard.release.assert_called_once_with('a')
    
    def test_press_combination(self):
        """Test de combinación de teclas."""
        result = self.controller.press_combination(['ctrl', 'c'])
        
        assert result == True
        # Verificar que se llamó a press_and_release para la última tecla
        self.mock_keyboard.press_and_release.assert_called()
    
    def test_type_text(self):
        """Test de escritura de texto."""
        test_text = "Hola Mundo"
        
        result = self.controller.type_text(test_text)
        
        assert result == True
        # keyboard.write debería llamarse por cada caracter
        assert self.mock_keyboard.write.call_count == len(test_text)
    
    def test_hold_and_release_key(self):
        """Test de mantener y liberar tecla."""
        # Test hold
        result_hold = self.controller.hold_key('shift')
        assert result_hold == True
        assert 'shift' in self.controller.hold_keys
        
        # Test release
        result_release = self.controller.release_key('shift')
        assert result_release == True
        assert 'shift' not in self.controller.hold_keys
    
    def test_release_all_keys(self):
        """Test de liberar todas las teclas."""
        # Mantener varias teclas
        self.controller.hold_key('ctrl')
        self.controller.hold_key('alt')
        
        result = self.controller.release_all_keys()
        
        assert result == True
        assert len(self.controller.hold_keys) == 0
    
    def test_add_and_execute_macro(self):
        """Test de macros."""
        macro_name = "test_macro"
        macro_sequence = [
            {'type': 'press', 'key': 'ctrl'},
            {'type': 'press', 'key': 'c'},
            {'type': 'release', 'key': 'ctrl'}
        ]
        
        # Agregar macro
        result_add = self.controller.add_macro(macro_name, macro_sequence)
        assert result_add == True
        assert macro_name in self.controller.macros
        
        # Ejecutar macro
        result_execute = self.controller.execute_macro(macro_name)
        assert result_execute == True
    
    def test_parse_key_command(self):
        """Test de parseo de comandos de teclado."""
        test_cases = [
            ("ctrl+alt+delete", ['ctrl', 'alt', 'delete']),
            ("f11", ['f11']),
            ("shift+a", ['shift', 'a']),
            ("ctrl+shift+esc", ['ctrl', 'shift', 'esc'])
        ]
        
        for command, expected in test_cases:
            result = self.controller.parse_key_command(command)
            assert result == expected
    
    def test_get_available_keys(self):
        """Test de obtención de teclas disponibles."""
        keys = self.controller.get_available_keys()
        
        assert isinstance(keys, list)
        assert len(keys) > 0
        assert 'a' in keys  # Letras
        assert 'ctrl' in keys  # Teclas especiales
        assert 'f1' in keys  # Teclas función

class TestMouseController:
    """Pruebas para el controlador de mouse."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.pyautogui_patcher = patch('controllers.mouse_controller.pyautogui')
        self.mock_pyautogui = self.pyautogui_patcher.start()
        
        self.controller = MouseController()
    
    def teardown_method(self):
        """Limpieza después de cada test."""
        self.pyautogui_patcher.stop()
        if hasattr(self, 'controller'):
            self.controller.cleanup()
    
    def test_initialization(self):
        """Test de inicialización."""
        assert self.controller is not None
        assert hasattr(self.controller, 'screen_width')
        assert hasattr(self.controller, 'screen_height')
        assert hasattr(self.controller, 'sensitivity')
    
    def test_move_to(self):
        """Test de movimiento a coordenadas absolutas."""
        x, y = 100, 200
        
        result = self.controller.move_to(x, y)
        
        assert result == True
        self.mock_pyautogui.moveTo.assert_called_once_with(x, y, duration=0.1)
    
    def test_move_relative(self):
        """Test de movimiento relativo."""
        dx, dy = 50, -30
        
        result = self.controller.move_relative(dx, dy)
        
        assert result == True
        self.mock_pyautogui.moveRel.assert_called_once_with(dx, dy, duration=0.1)
    
    def test_click(self):
        """Test de clic de mouse."""
        # Clic izquierdo
        result_left = self.controller.click('left')
        assert result_left == True
        self.mock_pyautogui.click.assert_called_with(button='left')
        
        # Clic derecho
        result_right = self.controller.click('right')
        assert result_right == True
        self.mock_pyautogui.click.assert_called_with(button='right')
    
    def test_double_click(self):
        """Test de doble clic."""
        result = self.controller.double_click()
        
        assert result == True
        self.mock_pyautogui.doubleClick.assert_called_once()
    
    def test_scroll(self):
        """Test de scroll."""
        # Scroll up
        result_up = self.controller.scroll(100)
        assert result_up == True
        self.mock_pyautogui.scroll.assert_called_with(100)
        
        # Scroll down
        result_down = self.controller.scroll(-100)
        assert result_down == True
        self.mock_pyautogui.scroll.assert_called_with(-100)
    
    def test_drag(self):
        """Test de arrastre."""
        start_x, start_y = 100, 100
        end_x, end_y = 200, 200
        
        result = self.controller.drag(start_x, start_y, end_x, end_y)
        
        assert result == True
        self.mock_pyautogui.dragTo.assert_called_once_with(
            end_x, end_y, duration=0.2, button='left'
        )
    
    def test_get_position(self):
        """Test de obtención de posición actual."""
        self.mock_pyautogui.position.return_value = (150, 250)
        
        pos = self.controller.get_position()
        
        assert pos == (150, 250)
        self.mock_pyautogui.position.assert_called_once()

class TestWindowController:
    """Pruebas para el controlador de ventanas."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.pygetwindow_patcher = patch('controllers.window_controller.gw')
        self.mock_gw = self.pygetwindow_patcher.start()
        
        self.controller = WindowController()
    
    def teardown_method(self):
        """Limpieza después de cada test."""
        self.pygetwindow_patcher.stop()
    
    def test_get_all_windows(self):
        """Test de obtención de todas las ventanas."""
        # Mock de ventanas de prueba
        mock_window1 = Mock(title="Ventana 1", isMinimized=False, isMaximized=False)
        mock_window2 = Mock(title="Ventana 2", isMinimized=True, isMaximized=False)
        
        self.mock_gw.getAllWindows.return_value = [mock_window1, mock_window2]
        
        windows = self.controller.get_all_windows()
        
        assert isinstance(windows, list)
        assert len(windows) == 2
        self.mock_gw.getAllWindows.assert_called_once()
    
    def test_get_active_window(self):
        """Test de obtención de ventana activa."""
        mock_window = Mock(title="Ventana Activa")
        self.mock_gw.getActiveWindow.return_value = mock_window
        
        window = self.controller.get_active_window()
        
        assert window is not None
        assert window.title == "Ventana Activa"
    
    def test_minimize_window(self):
        """Test de minimizar ventana."""
        mock_window = Mock()
        
        result = self.controller.minimize_window(mock_window)
        
        assert result == True
        mock_window.minimize.assert_called_once()
    
    def test_maximize_window(self):
        """Test de maximizar ventana."""
        mock_window = Mock()
        
        result = self.controller.maximize_window(mock_window)
        
        assert result == True
        mock_window.maximize.assert_called_once()
    
    def test_close_window(self):
        """Test de cerrar ventana."""
        mock_window = Mock()
        
        result = self.controller.close_window(mock_window)
        
        assert result == True
        mock_window.close.assert_called_once()
    
    def test_find_window_by_title(self):
        """Test de búsqueda de ventana por título."""
        mock_window = Mock(title="Calculadora")
        self.mock_gw.getWindowsWithTitle.return_value = [mock_window]
        
        window = self.controller.find_window_by_title("Calculadora")
        
        assert window is not None
        assert window.title == "Calculadora"

class TestBashController:
    """Pruebas para el controlador de comandos Bash."""
    
    def setup_method(self):
        """Configuración antes de cada test."""
        self.subprocess_patcher = patch('controllers.bash_controller.subprocess')
        self.mock_subprocess = self.subprocess_patcher.start()
        
        self.os_patcher = patch('controllers.bash_controller.os')
        self.mock_os = self.os_patcher.start()
        
        self.controller = BashController()
    
    def teardown_method(self):
        """Limpieza después de cada test."""
        self.subprocess_patcher.stop()
        self.os_patcher.stop()
        
        if hasattr(self, 'controller'):
            self.controller.cleanup()
    
    def test_execute_success(self):
        """Test de ejecución exitosa de comando."""
        # Mock de proceso exitoso
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "Hello World"
        mock_process.stderr = ""
        
        self.mock_subprocess.run.return_value = mock_process
        
        result = self.controller.execute("echo Hello World")
        
        assert result['success'] == True
        assert result['return_code'] == 0
        assert "Hello World" in result['output']
    
    def test_execute_error(self):
        """Test de ejecución con error."""
        # Mock de proceso con error
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "Command not found"
        
        self.mock_subprocess.run.return_value = mock_process
        
        result = self.controller.execute("invalid_command")
        
        assert result['success'] == False
        assert result['return_code'] == 1
        assert "Command not found" in result['error']
    
    def test_execute_timeout(self):
        """Test de timeout en ejecución."""
        self.mock_subprocess.run.side_effect = TimeoutError("Command timed out")
        
        result = self.controller.execute("sleep 10", timeout=1)
        
        assert result['success'] == False
        assert result['timed_out'] == True
    
    def test_execute_background(self):
        """Test de ejecución en background."""
        result = self.controller.execute("sleep 5", background=True)
        
        assert result['success'] == True
        assert result['background'] == True
        assert 'process_id' in result
    
    def test_execute_python_code(self):
        """Test de ejecución de código Python."""
        python_code = """
print("Python test")
import platform
print(f"System: {platform.system()}")
        """
        
        result = self.controller.execute_python(python_code)
        
        assert 'python_code' in result
        assert 'temp_file' in result
        assert result['success'] in [True, False]
    
    def test_kill_process(self):
        """Test de terminación de proceso."""
        # Primero ejecutar en background
        bg_result = self.controller.execute("sleep 10", background=True)
        process_id = bg_result['process_id']
        
        # Intentar matar
        result = self.controller.kill_process(process_id)
        
        assert result == True
    
    def test_list_directory(self):
        """Test de listado de directorio."""
        self.mock_os.listdir.return_value = ['file1.txt', 'file2.py', 'folder1']
        self.mock_os.path.isdir.side_effect = lambda x: x == 'folder1'
        self.mock_os.path.exists.return_value = True
        
        result = self.controller.list_directory()
        
        assert result['success'] == True
        assert 'files' in result
        assert len(result['files']) == 3

def test_integration_controllers():
    """Test de integración entre controladores."""
    # Crear instancias de todos los controladores
    keyboard = KeyboardController()
    mouse = MouseController()
    window = WindowController()
    bash = BashController()
    
    # Verificar que todos se inicializan correctamente
    assert keyboard is not None
    assert mouse is not None
    assert window is not None
    assert bash is not None
    
    # Verificar métodos básicos
    assert hasattr(keyboard, 'press_key')
    assert hasattr(mouse, 'move_to')
    assert hasattr(window, 'get_all_windows')
    assert hasattr(bash, 'execute')
    
    # Limpiar
    keyboard.cleanup()
    mouse.cleanup()
    bash.cleanup()

if __name__ == "__main__":
    """Ejecutar pruebas directamente."""
    import sys
    sys.exit(pytest.main([__file__, "-v"]))