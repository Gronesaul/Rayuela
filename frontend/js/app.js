/**
 * Rayuela — frontend del módulo "voces".
 *
 * Pensado para conectividad limitada:
 *  - guarda lo que Jimena va escribiendo en localStorage, para que si se
 *    cae la señal a mitad de camino no pierda lo que llevaba.
 *  - muestra mensajes de estado claros, sin jerga técnica.
 *
 * IMPORTANTE: cambia BACKEND_URL por la URL real de tu backend en Railway
 * una vez esté desplegado (algo como https://rayuela-backend.up.railway.app).
 */

const BACKEND_URL = "https://rayuela-production.up.railway.app";

const formulario = document.getElementById("formulario-voces");
const bandaInfo = document.getElementById("banda-info");
const mensajeEstado = document.getElementById("mensaje-estado");
const botonGenerar = document.getElementById("boton-generar");

const CAMPOS_GUARDABLES = ["nombre", "fecha_nacimiento", "genero", "actividad", "observaciones"];
const CLAVE_LOCAL = "rayuela_borrador_voces";

// --- 1. Recuperar borrador guardado localmente (si existe) ---
function cargarBorrador() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE_LOCAL) || "{}");
    for (const campo of CAMPOS_GUARDABLES) {
      if (guardado[campo] && formulario.elements[campo]) {
        formulario.elements[campo].value = guardado[campo];
      }
    }
  } catch (e) { /* si algo sale mal, simplemente empezamos en blanco */ }
}

function guardarBorrador() {
  const datos = {};
  for (const campo of CAMPOS_GUARDABLES) {
    datos[campo] = formulario.elements[campo]?.value || "";
  }
  localStorage.setItem(CLAVE_LOCAL, JSON.stringify(datos));
}

formulario.addEventListener("input", guardarBorrador);
cargarBorrador();

// --- 2. Calcular y mostrar la banda de edad en vivo ---
async function actualizarBanda() {
  const fecha = formulario.elements["fecha_nacimiento"].value;
  const genero = formulario.elements["genero"].value;
  if (!fecha) { bandaInfo.textContent = ""; return; }

  try {
    const resp = await fetch(`${BACKEND_URL}/api/calcular-edad`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fecha_nacimiento: fecha, genero }),
    });
    if (!resp.ok) throw new Error("no se pudo calcular");
    const datos = await resp.json();
    bandaInfo.textContent =
      `Edad: ${datos.edad_meses} meses · Etapa: ${datos.banda.etiqueta} · ` +
      `Rayuela usará "${datos.sustantivo}" para referirse a él/ella.`;
    bandaInfo.classList.remove("error");
  } catch (e) {
    bandaInfo.textContent = "";
  }
}
formulario.elements["fecha_nacimiento"].addEventListener("change", actualizarBanda);
formulario.elements["genero"].addEventListener("change", actualizarBanda);

// --- 3. Enviar el formulario y descargar el documento generado ---
formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mensajeEstado.classList.remove("error");
  mensajeEstado.textContent = "Redactando con cariño y armando tu documento... esto puede tardar unos segundos ⏳";
  botonGenerar.disabled = true;

  const datosFormulario = new FormData(formulario);
  const cuerpo = Object.fromEntries(datosFormulario.entries());

  try {
    const resp = await fetch(`${BACKEND_URL}/api/generar-voces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      throw new Error(error.error || "Algo salió mal generando el documento.");
    }

    // Descargamos el archivo que devuelve el backend
    const blob = await resp.blob();
    const nombreArchivo = (resp.headers.get("Content-Disposition") || "")
      .split("filename=")[1]?.replaceAll('"', "") || "voces-rayuela.pptx";

    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombreArchivo;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();

    mensajeEstado.textContent = "¡Listo! Tu documento se descargó. Revísalo y ajústalo con lo que de verdad viviste 🌼";
    localStorage.removeItem(CLAVE_LOCAL);
  } catch (error) {
    mensajeEstado.textContent = `No se pudo generar el documento: ${error.message}`;
    mensajeEstado.classList.add("error");
  } finally {
    botonGenerar.disabled = false;
  }
});
