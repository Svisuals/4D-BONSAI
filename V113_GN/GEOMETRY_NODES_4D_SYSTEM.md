# Sistema de Animación 4D basado en Geometry Nodes

## Descripción General

Este sistema proporciona una implementación completa de animación 4D utilizando Geometry Nodes como alternativa de alto rendimiento al sistema tradicional de keyframes. El sistema mantiene **compatibilidad visual dual** y **integración completa** con todos los controles de UI existentes.

## Características Principales

### ✅ Compatibilidad Visual Dual
- **Modo Solid**: Manipulación dinámica de `object.color` a través de eventos
- **Modo Material/Rendered**: Súper Material procedural universal
- Sincronización perfecta entre ambos modos

### ✅ Integración Completa con Live Color Scheme
- Utiliza el mismo botón "Live Color Scheme" existente
- Detección automática del modo de animación (Keyframes vs GN)
- Cambio de manejadores automático según el modo

### ✅ Sistema de ColorTypes Individual
- Cada objeto lee su ColorType desde la asignación de tarea real
- Compatible con el sistema UnifiedColorTypeManager existente
- Soporte para todos los grupos de ColorType (DEFAULT, personalizados)

### ✅ Lógica de Visibilidad de Tres Estados
- **before_start**: Antes del inicio de la tarea
- **active**: Durante la ejecución de la tarea
- **after_end**: Después de completar la tarea
- Propiedades `consider_start`, `consider_active`, `consider_end`, `hide_at_end`

### ✅ Efectos de Aparición
- **Instant**: Aparición/desaparición instantánea
- **Growth**: Crecimiento gradual basado en coordenada Z
- Configuración por ColorType mediante `gn_appearance_effect`

### ✅ Integración Total con UI
- Utiliza operadores "Create Animation" y "Clear Animation" existentes
- Selector de modo de animación (Keyframes/Geometry Nodes)
- Re-horneado automático cuando cambian asignaciones de ColorType

## Arquitectura del Sistema

### Archivos Principales

```
tool/
├── gn_sequence_enhanced.py     # Sistema principal (4 etapas)
├── gn_ui_integration.py        # Integración con UI existente
├── gn_system_main.py          # Punto de entrada y coordinación
└── gn_integration.py          # Archivo original (mantenido para compatibilidad)
```

### Etapas de Implementación

#### **ETAPA 1: Preparación y Horneado de Datos**
```python
def bake_all_attributes_worker_enhanced(work_schedule, settings)
```
- Replica la lógica de `get_animation_settings()` y `get_animation_product_frames_enhanced()`
- Calcula fechas de inicio/fin para cada tarea usando `derive_date()`
- Obtiene ColorType real asignado usando `get_assigned_ColorType_for_task()`
- Hornea atributos completos:
  - `schedule_start/end` (fechas como números de día)
  - `visibility_before_start/after_end` (basado en propiedades ColorType)
  - `effect_type` (Instant=0, Growth=1)
  - `colortype_id` (ID numérico único)

#### **ETAPA 2: Lógica de Visibilidad en Árbol de Nodos**
```python
def create_advanced_nodetree_enhanced()
```
- Implementa lógica de tres estados proceduralmente:
  ```
  visible_final = (es_antes AND visibility_before_start) OR
                  (es_activo) OR
                  (es_después AND visibility_after_end)
  ```
- Sistema de efectos Instant/Growth
- Generación de atributos de salida para shader:
  - `animation_state` (0.0=before, 0.5=active, 1.0=after)
  - `colortype_id` (para selección de material)

#### **ETAPA 3: Sistema de Apariencia Dual**
```python
def create_super_material()                    # Para Material/Rendered
def gn_live_color_update_handler_enhanced()   # Para Solid
```
- **Súper Material**: Lee atributos de geometría y selecciona colores dinámicamente
- **Manejador de Eventos**: Actualiza `object.color` basado en atributos horneados
- Sincronización perfecta entre ambos sistemas

#### **ETAPA 4: Integración con UI**
```python
def enhanced_create_animation_execute()       # Wrapper para CreateAnimation
def enhanced_toggle_live_color_updates()     # Wrapper para Live Color Scheme
```
- Detección automática del modo de animación
- Modificación transparente de operadores existentes
- Preservación de toda la funcionalidad original

## Uso del Sistema

### Inicialización

```python
from bonsai.bim.module.sequence.tool.gn_system_main import initialize_complete_gn_system

# Inicializar sistema completo
success = initialize_complete_gn_system()
if success:
    print("Sistema GN listo para usar")
```

### Crear Animación

1. **Opción 1: UI Existente**
   - Usar botón "Create Animation" normal
   - El sistema detecta automáticamente el modo
   - Configurar "Live Color Scheme" igual que antes

2. **Opción 2: Programática**
```python
from bonsai.bim.module.sequence.tool.gn_system_main import create_gn_animation_auto

result = create_gn_animation_auto(preserve_current_frame=True)
if result == {'FINISHED'}:
    print("Animación GN creada exitosamente")
```

### Limpiar Animación

```python
from bonsai.bim.module.sequence.tool.gn_system_main import clear_gn_animation_auto

result = clear_gn_animation_auto()
```

### Debug y Diagnóstico

```python
from bonsai.bim.module.sequence.tool.gn_system_main import debug_gn_system, test_gn_system

# Información de debug detallada
debug_gn_system()

# Prueba completa del sistema
test_passed = test_gn_system()
```

## Flujo de Datos

### 1. Preparación de Datos
```
IFC WorkSchedule → get_animation_settings() →
Task Dates + ColorType Assignments →
Baked Attributes (schedule_start, visibility_*, effect_type, colortype_id)
```

### 2. Procesamiento en Geometry Nodes
```
Current Frame + Baked Attributes →
Three-State Logic →
Effect System (Instant/Growth) →
Delete Geometry + Material Assignment
```

### 3. Visualización Dual
```
GN Output → Súper Material (Material/Rendered Mode)
         → Event Handler → object.color (Solid Mode)
```

## Compatibilidad

### ✅ Sistema de Keyframes Existente
- Totalmente compatible - no interfiere
- Los usuarios pueden alternar entre modos
- Mismo comportamiento visual garantizado

### ✅ Herramientas Existentes
- HUD (Timeline, Schedule, Legend) - funciona igual
- Speed Settings (1x, 2x, 4x) - integración completa
- Camera Tools - sin cambios
- Export/Import - compatible

### ✅ ColorType System
- UnifiedColorTypeManager - integración completa
- Grupos personalizados - soporte total
- Live updates - funcionalidad preservada

## Rendimiento

### Ventajas sobre Keyframes
- **Sin keyframes**: No satura la timeline de Blender
- **Procedural**: Cálculos en GPU
- **Escalable**: Rendimiento constante con modelos grandes
- **Memoria**: Menor uso que miles de keyframes

### Optimizaciones Implementadas
- Procesamiento en lotes de atributos
- Caché de ColorType mapping
- Drivers optimizados para propiedades dinámicas
- Lazy evaluation en árbol de nodos

## Solución de Problemas

### Problema: Animación no funciona
```python
# Verificar estado del sistema
from bonsai.bim.module.sequence.tool.gn_system_main import get_gn_system_status
status = get_gn_system_status()
print(status)

# Si no está inicializado
if not status['initialized']:
    initialize_complete_gn_system()
```

### Problema: Colores incorrectos
```python
# Verificar Live Color Scheme
anim_props = tool.Sequence.get_animation_props()
print(f"Live Color enabled: {anim_props.enable_live_color_updates}")

# Re-activar si es necesario
from bonsai.bim.module.sequence.tool.gn_system_main import toggle_gn_live_color_auto
toggle_gn_live_color_auto(True)
```

### Problema: Objetos no aparecen
```python
# Verificar atributos horneados
obj = bpy.context.active_object
if obj and obj.data:
    attrs = [attr.name for attr in obj.data.attributes]
    required = ['schedule_start', 'schedule_end', 'visibility_before_start', 'colortype_id']
    missing = [attr for attr in required if attr not in attrs]
    print(f"Missing attributes: {missing}")
```

## Desarrollo Futuro

### Posibles Mejoras
1. **Efectos Avanzados**: Fade, Scale, Rotation
2. **Optimización GPU**: Compute Shaders para modelos enormes
3. **Cache Persistente**: Guardar atributos horneados en .blend
4. **UI Dedicada**: Panel específico para configuración GN
5. **Profile System**: Perfiles de rendimiento (High/Medium/Low)

### API Extensions
```python
# Ejemplo de API futura
gn_system.add_custom_effect('fade_in', fade_duration=30)
gn_system.set_performance_profile('high_performance')
gn_system.export_animation_cache('project.gncache')
```

## Créditos y Licencia

Desarrollado como extensión del sistema Bonsai 4D existente.
Compatible con todas las características del add-on original.
Mantiene la licencia GPL v3 del proyecto Bonsai.

---

**Versión**: 1.0
**Fecha**: 2024
**Compatibilidad**: Blender 4.x, Bonsai 0.8.x+
**Estado**: Implementación completa de 4 etapas ✅