# 🌼 Rayuela

Aplicación web que ayuda a Jimena (educadora del programa ICBF "De Cero a
Siempre") a redactar y armar sus cuadernos de "voces de familia" sin pasar
72 horas sin dormir cada vez que tiene que entregarlos.

Rayuela **no inventa lo que pasó en el encuentro**: toma lo que Jimena
escribe en bruto (qué actividad hizo, qué observó) y lo amplía/redacta con
un vocabulario apropiado para la edad del niño o niña, usando la API de
Claude. Después llena automáticamente la plantilla oficial en PowerPoint
y se la entrega lista para revisar y ajustar.

## Cómo está organizado

```
rayuela/
├── backend/        → servidor Flask (Python) que llama a la API de Claude
│                      y llena la plantilla .pptx
│   ├── app/
│   │   ├── main.py            → rutas de la API
│   │   ├── edades.py          → lógica de bandas de edad (0-6m, 6-11m, 1-2a, 3-4a)
│   │   ├── redactor.py        → conexión con la API de Claude
│   │   └── plantilla_pptx.py  → motor que llena la plantilla PowerPoint
│   ├── templates/             → aquí van los moldes oficiales (molde_hogar.pptx, molde_llamada.pptx)
│   ├── requirements.txt
│   ├── Procfile               → para desplegar en Railway
│   └── .env.example
│
└── frontend/       → página web que ve Jimena (HTML + CSS + JS, sin frameworks)
    ├── index.html
    ├── css/estilo.css
    └── js/app.js
```

## Por qué respeta la edad de cada niño/a

Jimena nos corrigió algo clave: a un bebé de 0 a 6 meses **no se le puede
decir que "participa activamente"** — eso solo aplica de 6 a 11 meses en
adelante. Esa regla quedó codificada directamente en `edades.py` y en las
instrucciones que recibe la API en `redactor.py`, así Rayuela nunca vuelve
a cometer ese error, sin importar quién la use.

## Cómo desplegarlo (con las cuentas que ya tienes)

### 1. Backend → Railway
1. Crea un proyecto nuevo en Railway y conéctalo a este repositorio (carpeta `backend/`).
2. En "Variables", agrega:
   - `ANTHROPIC_API_KEY` = tu llave de la API de Claude (la que tú vas a regalar)
   - `RAYUELA_TEMPLATE_DIR` = `templates`
3. Sube los archivos `molde_hogar.pptx` y `molde_llamada.pptx` (las plantillas
   oficiales del ICBF, sin datos de niños) a `backend/templates/`.
4. Railway detecta el `Procfile` y lo despliega solo. Copia la URL pública
   que te entrega (algo como `https://rayuela-backend.up.railway.app`).

### 2. Frontend → Netlify
1. Crea un sitio nuevo en Netlify apuntando a la carpeta `frontend/`.
2. Antes de publicar, abre `frontend/js/app.js` y reemplaza la línea:
   ```js
   const BACKEND_URL = "https://CAMBIA-ESTO-rayuela-backend.up.railway.app";
   ```
   por la URL real que te dio Railway en el paso anterior.
3. Publica. Netlify te da una URL pública para compartirle a Jimena
   (puedes ponerle un nombre lindo desde "Site settings").

### 3. Datos / respaldo → Firebase (opcional, para una siguiente fase)
Por ahora Rayuela no guarda nada en una base de datos — genera el archivo
y listo. Si más adelante quieres que Jimena pueda ver un historial de los
documentos que ha generado, Firebase (Firestore + Storage) es el siguiente
paso natural y ya tienes la cuenta lista.

## Costos de la API
Cada generación hace 4 llamadas cortas a Claude (una por pregunta). Esto
tiene un costo muy bajo por documento. Te recomendamos revisar el uso en
la consola de Anthropic durante el primer mes para calibrar el presupuesto.

## Próximos pasos sugeridos
- Módulo de "planeación" (Fase 1, antes del encuentro) — mismo motor, plantilla distinta.
- Guardado de borradores en Firebase para que Jimena no pierda su trabajo
  si se va la conexión a mitad de camino (el frontend ya guarda en el
  navegador como respaldo local).
