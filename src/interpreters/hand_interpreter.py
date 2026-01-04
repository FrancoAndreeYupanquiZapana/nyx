"""
🤏 HAND INTERPRETER - Interpretador de Gestos de Manos
=====================================================
Convierte los datos crudos de detección de manos en gestos significativos
con contexto, confianza y mapeo a acciones.
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class HandInterpreter:
    """Interpreta gestos de manos detectados."""
    
    def __init__(self, gesture_threshold: float = 0.7):
        """
        Inicializa el interpretador de manos.
        
        Args:
            gesture_threshold: Umbral mínimo de confianza para considerar un gesto válido
        """
        self.gesture_threshold = gesture_threshold
        
        # Mapeo de gestos a acciones (se carga desde perfiles)
        self.gesture_mappings = {}
        
        # Historial para estabilización
        self.gesture_history = []
        self.max_history = 10
        
        # Estados de gestos previos
        self.last_gestures = {}
        self.gesture_durations = {}
        
        # Configuración de estabilización
        self.stabilization_frames = 3  # Número de frames para estabilizar un gesto
        self.cooldown_frames = 5       # Frames de cooldown entre gestos repetidos
        
        # Estadísticas
        self.stats = {
            'gestures_interpreted': 0,
            'gestures_filtered': 0,
            'actions_triggered': 0,
            'avg_confidence': 0.0
        }

        # --- NUEVO: Estado para gestos precisos (Snippet Usuario) ---
        self.dragging = False
        self.last_click_time = 0
        self.prev_scroll_y = 0
        self.shaka_start_time = 0
        
        logger.info(f"✅ HandInterpreter inicializado (threshold={gesture_threshold})")
    
    def interpret(self, hands_data: List[Dict]) -> List[Dict]:
        """
        Interpreta los datos de manos detectadas en gestos significativos.
        """
        interpreted_gestures = []
        
        for hand in hands_data:
            if not hand:
                continue
            
            raw_gestures = hand.get('gestures', [])
            hand_info = hand.get('hand_info', {})
            
            for raw_gesture in raw_gestures:
                try:
                    interpreted = self._interpret_single_gesture(raw_gesture, hand_info)
                    
                    if interpreted:
                        if self._is_gesture_stable(interpreted, hand_info.get('handedness')):
                            interpreted = self._apply_gesture_mapping(interpreted)
                            interpreted_gestures.append(interpreted)
                            
                            self.stats['gestures_interpreted'] += 1
                            self.stats['avg_confidence'] = (
                                (self.stats['avg_confidence'] * (self.stats['gestures_interpreted'] - 1) + 
                                 interpreted['confidence']) / self.stats['gestures_interpreted']
                            )
                except Exception as e:
                    logger.debug(f"⚠️ Error interpretando gesto: {e}")
                    continue
        
        return interpreted_gestures
    
    def process_gesture(self, gesture_data: Dict) -> Optional[Dict]:
        """Procesa un único gesto (compatibilidad)."""
        try:
            # USAR hand_info real si viene en el dict (ahora el detector lo envía)
            hand_info = gesture_data.get('hand_info')
            if not hand_info:
                hand_info = {
                    'handedness': gesture_data.get('hand', 'unknown'),
                    'confidence': gesture_data.get('confidence', 0.5),
                    'landmarks': []
                }
            
            interpreted = self._interpret_single_gesture(gesture_data, hand_info)
            if interpreted:
                # Bypass stabilization for precision and speed in mouse gestures
                is_mouse = interpreted.get('category') in ['mouse', 'scroll', 'click']
                if is_mouse or self._is_gesture_stable(interpreted, gesture_data.get('hand', 'unknown')):
                    return self._apply_gesture_mapping(interpreted)
            return None
        except Exception as e:
            logger.error(f"❌ Error procesando gesto individual: {e}")
            return None
    
    def _interpret_single_gesture(self, raw_gesture: Dict, hand_info: Dict) -> Optional[Dict]:
        """Interpreta un gesto crudo individual."""
        confidence = raw_gesture.get('confidence', 0.0)
        if confidence < self.gesture_threshold:
            self.stats['gestures_filtered'] += 1
            return None
        
        gesture_name = raw_gesture.get('gesture', 'unknown')
        hand_type = raw_gesture.get('hand', 'unknown')
        
        contextual_confidence = self._calculate_contextual_confidence(raw_gesture, hand_info)
        final_confidence = min(confidence * contextual_confidence, 1.0)
        gesture_type = self._categorize_gesture(gesture_name)
        cursor_pos = self._calculate_cursor_position(gesture_name, hand_info)
        
        # --- NUEVO: Refine logic based on User Snippet ---
        refined_gesture = self._refine_gesture_with_distances(gesture_name, hand_info)
        if refined_gesture:
            gesture_name = refined_gesture
            gesture_type = self._categorize_gesture(gesture_name)

        interpreted_gesture = {
            'type': 'hand',
            'gesture': gesture_name,
            'category': gesture_type,
            'hand': hand_type,
            'confidence': final_confidence,
            'raw_confidence': confidence,
            'contextual_confidence': contextual_confidence,
            'timestamp': time.time(),
            'cursor': cursor_pos,
            'hand_info': {
                'landmarks_count': len(hand_info.get('landmarks', [])),
                'bbox_area': hand_info.get('bbox', {}).get('area', 0),
                'hand_confidence': hand_info.get('confidence', 0.0)
            },
            'raw_data': raw_gesture
        }

        # Pasar datos dinámicos (como scroll_amount)
        if 'scroll_amount' in hand_info:
            interpreted_gesture['scroll_amount'] = hand_info['scroll_amount']
            # Consumir después de usar
            del hand_info['scroll_amount']
        
        if 'finger_status' in hand_info: interpreted_gesture['finger_status'] = hand_info['finger_status']
        if 'angles' in hand_info: interpreted_gesture['angles'] = hand_info['angles']
        
        return interpreted_gesture
    
    def _calculate_contextual_confidence(self, raw_gesture: Dict, hand_info: Dict) -> float:
        """Calcula confianza contextual."""
        contextual_factors = []
        landmarks = hand_info.get('landmarks', [])
        if landmarks:
            avg_visibility = sum(lm.get('visibility', 0.0) for lm in landmarks) / len(landmarks)
            contextual_factors.append(avg_visibility)
        
        bbox = hand_info.get('bbox', {})
        bbox_area = bbox.get('width', 0) * bbox.get('height', 0)
        if bbox_area > 0:
            size_factor = min(bbox_area / 10000, 1.0)
            contextual_factors.append(size_factor)
        
        contextual_factors.append(hand_info.get('confidence', 0.0))
        
        finger_status = hand_info.get('finger_status', {})
        if finger_status:
            consistency = self._check_finger_consistency(raw_gesture.get('gesture', ''), finger_status)
            contextual_factors.append(consistency)
        
        return sum(contextual_factors) / len(contextual_factors) if contextual_factors else 0.5
    
    def _check_finger_consistency(self, gesture_name: str, finger_status: Dict) -> float:
        """Verifica consistencia del gesto."""
        expected_states = {
            'fist': {'thumb': 'bent', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'},
            'peace': {'thumb': 'bent', 'index': 'extended', 'middle': 'extended', 'ring': 'bent', 'pinky': 'bent'},
            'thumbs_up': {'thumb': 'extended', 'index': 'bent', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'},
            'ok': {'thumb': 'bent', 'index': 'bent', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'},
            'point': {'thumb': 'bent', 'index': 'extended', 'middle': 'bent', 'ring': 'bent', 'pinky': 'bent'},
            'palm': {'thumb': 'extended', 'index': 'extended', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'},
            'victory': {'thumb': 'bent', 'index': 'extended', 'middle': 'extended', 'ring': 'bent', 'pinky': 'bent'},
            'stop': {'thumb': 'extended', 'index': 'extended', 'middle': 'extended', 'ring': 'extended', 'pinky': 'extended'}
        }
        if gesture_name not in expected_states: return 0.7
        expected = expected_states[gesture_name]
        matches = sum(1 for f, s in expected.items() if f in finger_status and finger_status[f] == s)
        total = sum(1 for f in expected if f in finger_status)
        return matches / total if total > 0 else 0.5
    
    def _calculate_cursor_position(self, gesture_name: str, hand_info: Dict) -> Optional[Dict]:
        """Calcula posición del cursor usando el NUDILLO del índice para estabilidad."""
        relevant_gestures = ['point', 'ok', 'victory', 'pinch', 'fist', 'drag_start', 'call_me', 'rock']
        if gesture_name not in relevant_gestures: pass

        landmarks = hand_info.get('landmarks', [])
        if not landmarks: return None
        try:
            # USAR LANDMARK 5 (Nudillo/MCP) para máxima estabilidad
            if len(landmarks) > 5:
                index_mcp = landmarks[5]
                raw_x, raw_y = index_mcp.get('x', 0), index_mcp.get('y', 0)
                w, h = hand_info.get('frame_width', 640), hand_info.get('frame_height', 480)
                if raw_x > 1: raw_x /= w
                if raw_y > 1: raw_y /= h
                return {'x': raw_x, 'y': raw_y}
        except: pass
        return None

    def _categorize_gesture(self, gesture_name: str) -> str:
        """Categoriza un gesto para determinar comportamiento de estabilización."""
        categories = {
            'fist': 'command', 'peace': 'command', 'thumbs_up': 'feedback', 'thumbs_down': 'feedback',
            'ok': 'click', 'point': 'navigation', 'palm': 'control', 'victory': 'scroll',
            'stop': 'command', 'pinch': 'click', 'right_click_pinch': 'click', 
            'scroll_mode': 'scroll', 'drag_start': 'navigation', 'drag_end': 'navigation',
            'rock': 'scroll', 'call_me': 'click'
        }
        return categories.get(gesture_name, 'unknown')
    
    def _is_gesture_stable(self, interpreted_gesture: Dict, hand_type: str) -> bool:
        """Verifica estabilidad del gesto."""
        # BYPASS para gestos de mouse/precisión que deben ser instantáneos
        instant_gestures = [
            'point', 'scroll_mode', 'pinch', 'right_click_pinch', 
            'drag_start', 'drag_end', 'rock', 'victory', 'call_me'
        ]
        if interpreted_gesture['gesture'] in instant_gestures:
            return True

        gesture_key = f"{hand_type}_{interpreted_gesture['gesture']}"
        current_time = time.time()
        self.gesture_history.append({'key': gesture_key, 'timestamp': current_time})
        if len(self.gesture_history) > self.max_history: self.gesture_history.pop(0)
        self.gesture_history = [h for h in self.gesture_history if current_time - h['timestamp'] < 1.0]
        recent_same = sum(1 for h in self.gesture_history[-self.stabilization_frames:] if h['key'] == gesture_key)
        return recent_same >= 2
    
    def _apply_gesture_mapping(self, interpreted_gesture: Dict) -> Dict:
        """Aplica mapeo desde el perfil."""
        mapping = self.gesture_mappings.get(f"{interpreted_gesture['hand']}_{interpreted_gesture['gesture']}") or \
                  self.gesture_mappings.get(interpreted_gesture['gesture'])
        
        if mapping:
            # IMPORTANTE: El 'type' para ActionExecutor debe ser el tipo de acción (mouse, keyboard, etc.)
            # No el tipo de fuente ('hand')
            interpreted_gesture.update({
                'action': mapping.get('action'), 
                'type': mapping.get('action'), # Sobrescribir 'hand' con 'mouse'/'keyboard'
                'command': mapping.get('command'), 
                'mapped': True
            })
        else:
            interpreted_gesture['mapped'] = False
        return interpreted_gesture
    
    def load_gesture_mappings(self, mappings: Dict): self.gesture_mappings = mappings
    def add_gesture_mapping(self, gesture_name: str, action_config: Dict, hand_specific: str = None):
        key = f"{hand_specific}_{gesture_name}" if hand_specific else gesture_name
        self.gesture_mappings[key] = action_config
    
    def clear_history(self):
        self.gesture_history.clear()
        self.last_gestures.clear()
        self.gesture_durations.clear()
    
    def set_threshold(self, threshold: float): self.gesture_threshold = max(0.0, min(1.0, threshold))
    def set_stabilization(self, frames: int): self.stabilization_frames = max(2, frames)

    def _calculate_distance(self, p1: Dict, p2: Dict, w: int = 1, h: int = 1) -> float:
        x1, y1, x2, y2 = p1.get('x', 0), p1.get('y', 0), p2.get('x', 0), p2.get('y', 0)
        if x1 <= 1.1 and x2 <= 1.1: return np.hypot((x1 - x2) * w, (y1 - y2) * h)
        return np.hypot(x1 - x2, y1 - y2)

    def _refine_gesture_with_distances(self, gesture_name: str, hand_info: Dict) -> Optional[str]:
        """Implementación SIMPLE basada en código del usuario que FUNCIONA."""
        landmarks = hand_info.get('landmarks', [])
        if not landmarks or len(landmarks) < 21:
            return None
        
        w = hand_info.get('frame_width', 640)
        h = hand_info.get('frame_height', 480)
        
        try:
            # Obtener landmarks clave
            index_f  = landmarks[8]   # Punta Índice
            index_m  = landmarks[5]   # Nudillo Índice (ESTABLE para movimiento)
            middle_f = landmarks[12]
            middle_m = landmarks[9]
            thumb_f  = landmarks[4]
            ring_f   = landmarks[16]
            ring_m   = landmarks[13]
            pinky_f  = landmarks[20]
            pinky_m  = landmarks[17]
            
            # Coordenadas de movimiento (NUDILLO = ESTABILIDAD)
            ix = int(index_m.get('x', 0) * w)
            iy = int(index_m.get('y', 0) * h)
            
            # Coordenadas de puntas (PARA DISTANCIAS)
            itx = int(index_f.get('x', 0) * w)
            ity = int(index_f.get('y', 0) * h)
            mtx = int(middle_f.get('x', 0) * w)
            mty = int(middle_f.get('y', 0) * h)
            tx  = int(thumb_f.get('x', 0) * w)
            ty  = int(thumb_f.get('y', 0) * h)
            
            # Calcular distancias
            d_it = np.hypot(itx - tx, ity - ty)
            d_mt = np.hypot(mtx - tx, mty - ty)
            
            # Estados de dedos (Punta vs su propio nudillo)
            index_down  = index_f['y'] > index_m['y']
            ring_down   = ring_f['y'] > ring_m['y']
            pinky_down  = pinky_f['y'] > pinky_m['y']
            middle_down = middle_f['y'] > middle_m['y']
            
            # --------- CALL ME (RIGHT CLICK) ---------
            # EXIGENCIA USUARIO: Hold rápido (0.8s) y una sola ejecución.
            if gesture_name == 'call_me':
                if self.shaka_start_time == 0:
                    self.shaka_start_time = time.time()
                
                hold_duration = time.time() - self.shaka_start_time
                if hold_duration > 0.8:
                    if not getattr(self, 'shaka_triggered', False):
                        logger.info(f"🤙 CALL_ME hold verified (0.8s) -> RIGHT CLICK")
                        self.shaka_triggered = True
                        return "call_me"
                    return None
                return None
            else:
                # Margen de parpadeo (5 frames / ~0.2s) para no resetear el hold
                if not hasattr(self, '_shaka_lost_frames'): self._shaka_lost_frames = 0
                self._shaka_lost_frames += 1
                if self._shaka_lost_frames > 5: 
                    self.shaka_start_time = 0
                    self.shaka_triggered = False
                    self._shaka_lost_frames = 0
            
            # --------- MOVER (ÍNDICE + PULGAR EN L) ---------
            if not index_down and d_it > 60 and ring_down and pinky_down and middle_down:
                logger.info(f"🎯 POINT detected: d_it={d_it:.1f}")
                return "point"
            
            # --------- CLICK IZQUIERDO ---------
            elif d_it < 65 and ring_down and pinky_down:
                if time.time() - self.last_click_time > 0.35:
                    self.last_click_time = time.time()
                    logger.info(f"👆 PINCH detected (left click)")
                    return "pinch"
                return None
            
            # --------- CLICK DERECHO ---------
            elif d_mt < 65 and ring_down and pinky_down:
                logger.info(f"👆 RIGHT_CLICK_PINCH detected")
                return "right_click_pinch"
            
            # --------- VICTORY / PEACE (SCROLL UP) ---------
            elif not index_down and not middle_down and ring_down and pinky_down and d_it > 60 and d_mt > 60:
                logger.info(f"✌️ VICTORY detected (scroll_up)")
                hand_info['scroll_amount'] = 120
                return "victory"
            
            # --------- ROCK (SCROLL DOWN) ---------
            # ROCK DEBE tener el índice ARRIBA (not index_down)
            # El Shaka TIENE el índice ABAJO (index_down)
            elif not index_down and middle_down and ring_down and d_it > 60:
                if pinky_f['y'] < landmarks[18]['y']:
                    logger.info(f"🤘 ROCK detected (scroll_down)")
                    hand_info['scroll_amount'] = -120
                    return "rock"
            
            # --------- DRAG START ---------
            elif d_it < 65:
                if not self.dragging:
                    self.dragging = True
                    logger.info(f"✊ DRAG_START detected")
                    return "drag_start"
                return "pinch"  # Hold state
            
            # --------- DRAG END ---------
            elif d_it > 95 and self.dragging:
                self.dragging = False
                logger.info(f"🖐️ DRAG_END detected")
                return "drag_end"
            
            # --------- SCROLL DINÁMICO (Mano abierta moviéndose) ---------
            elif d_it > 80 and d_mt > 80 and not ring_down:
                # Si la mano está muy abierta, ignoramos scroll para evitar falsos positivos
                pass
            
            # Fallback para seguimiento
            if gesture_name == 'hand_tracking':
                return "point"
                
        except Exception as e:
            logger.error(f"❌ Error en refinamiento: {e}")
            return None
            
        return None
