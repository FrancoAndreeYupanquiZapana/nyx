from src.interpreters.voice_interpreter import VoiceInterpreter
import logging

logging.basicConfig(level=logging.ERROR)

def test_debug_voice():
    interpreter = VoiceInterpreter()
    
    # Simular carga de comandos que suele hacer el sistema
    interpreter.load_command_mappings({
        "abre chrome": {"action": "bash", "command": "google-chrome", "description": "Abrir Chrome"},
        "cierra ventana": {"action": "window", "command": "close", "description": "Cerrar ventana"}
    })
    
    test_cases = [
        ("nyx abre chrome", "open"),
        ("nyx cierra ventana", "close"),
    ]
    
    for text, cmd_type in test_cases:
        print(f"Testing: {text}")
        result = interpreter.interpret({'text': text})
        print(f"Result: {result['action'] if result else 'None'}")

if __name__ == "__main__":
    try:
        test_debug_voice()
    except Exception as e:
        import traceback
        traceback.print_exc()
