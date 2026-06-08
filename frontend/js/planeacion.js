/**
 * Rayuela — formulario de planeacion.
 * Llama a POST /api/planeacion, descarga el PPTX con la planeacion lista
 * y guarda el id en localStorage para que el usuario sepa a cual pendiente
 * le corresponde este archivo.
 */

const BACKEND_URL = "https://rayuela-production.up.railway.app";

const formulario   = document.getElementById("formulario-planeacion");
const bandaInfo    = document.getElementById("banda-info");
const mensajeEstado = document.getElementById("mensaje-estado");
const boton        = document.getElementById("boton-planear");
const camposHogar  = document.getElementById("campos-hogar");

const CLAVE_LOCAL = "rayuela_borrador_planeacion";
const CAMPOS_GUARDABLES = [
  "nombre", "fecha_nacimiento", "genero",
  "actividad_principal", "nombre_ronda", "link_ronda", "objetos_paquete"
];

// ── Borrador local ──────────────────────────────────────────────────────────
function cargarBorrador() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE_LOCAL) || "{}");
    for (const campo of CAMPOS_GUARDABLES) {
      const el = formulario.elements[campo];
      if (el && guardado[campo]) el.value = guardado[campo];
    }
    // Tipo cuaderno (radio)
    if (guardado.tipo_cuaderno) {
      const radio = formulario.querySelector(`input[value="${guardado.tipo_cuaderno}"]`);
      if (radio) radio.checked = true;
    }
  } catch (e) { /* en blanco si algo falla */ }
}

function guardarBorrador() {
  const datos = {};
  for (const campo of CAMPOS_GUARDABLES) {
    const el = formulario.elements[campo];
    datos[campo] = el ? el.value : "";
  }
  datos.tipo_cuaderno = formulario.querySelector('input[name="tipo_cuaderno"]:checked')?.value || "hogar";
  localStorage.setItem(CLAVE_LOCAL, JSON.stringify(datos));
}

formulario.addEventListener("input", guardarBorrador);
cargarBorrador();

// ── Mostrar/ocultar campos solo de hogar ────────────────────────────────────
function actualizarCamposHogar() {
  const tipo = formulario.querySelector('input[name="tipo_cuaderno"]:checked')?.value;
  camposHogar.classList.toggle("oculto", tipo !== "hogar");
}
formulario.querySelectorAll('input[name="tipo_cuaderno"]').forEach(r =>
  r.addEventListener("change", actualizarCamposHogar)
);
actualizarCamposHogar();

// ── Banda de edad en vivo ───────────────────────────────────────────────────
async function actualizarBanda() {
  const fecha  = formulario.elements["fecha_nacimiento"].value;
  const genero = formulario.elements["genero"].value;
  if (!fecha) { bandaInfo.textContent = ""; return; }
  try {
    const resp = await fetch(`${BACKEND_URL}/api/calcular-edad`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fecha_nacimiento: fecha, genero }),
    });
    if (!resp.ok) throw new Error();
    const datos = await resp.json();
    bandaInfo.textContent =
      `Edad: ${datos.edad_legible} · Etapa: ${datos.banda.etiqueta}`;
    bandaInfo.classList.remove("error");
  } catch (e) { bandaInfo.textContent = ""; }
}
formulario.elements["fecha_nacimiento"].addEventListener("change", actualizarBanda);
formulario.elements["genero"].addEventListener("change", actualizarBanda);

// ── Enviar formulario ───────────────────────────────────────────────────────
formulario.addEventListener("submit", async (e) => {
  e.preventDefault();
  mensajeEstado.classList.remove("error");
  mensajeEstado.textContent = "Generando la planeacion con IA... puede tardar unos segundos ⏳";
  boton.disabled = true;

  const tipo = formulario.querySelector('input[name="tipo_cuaderno"]:checked')?.value || "hogar";
  const cuerpo = {
    nombre:             formulario.elements["nombre"].value.trim(),
    fecha_nacimiento:   formulario.elements["fecha_nacimiento"].value,
    genero:             formulario.elements["genero"].value,
    tipo_cuaderno:      tipo,
    actividad_principal: formulario.elements["actividad_principal"].value.trim(),
    nombre_ronda:       formulario.elements["nombre_ronda"]?.value.trim() || "",
    link_ronda:         formulario.elements["link_ronda"]?.value.trim() || "",
    objetos_paquete:    formulario.elements["objetos_paquete"].value.trim(),
  };

  try {
    const resp = await fetch(`${BACKEND_URL}/api/planeacion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || "Algo salio mal.");
    }

    // Guarda el id devuelto en la cabecera para referencia
    const planeacionId = resp.headers.get("X-Rayuela-Planeacion-Id");
    if (planeacionId) {
      localStorage.setItem("rayuela_ultimo_id", planeacionId);
    }

    // Descarga el PPTX
    const blob = await resp.blob();
    const cd = resp.headers.get("Content-Disposition") || "";
    const nombreArchivo = cd.split("filename=")[1]?.replaceAll('"', "")
                         || "planeacion-rayuela.pptx";
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombreArchivo;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();

    mensajeEstado.textContent =
      "Planeacion lista y descargada. Imprimela antes del encuentro. " +
      "Cuando termines el encuentro, ve a Pendientes para completar las voces.";
    localStorage.removeItem(CLAVE_LOCAL);

  } catch (err) {
    mensajeEstado.textContent = "No se pudo generar: " + err.message;
    mensajeEstado.classList.add("error");
  } finally {
    boton.disabled = false;
  }
});
