/**
 * Rayuela — formulario de planeacion.
 * Llama a POST /api/planeacion, descarga el PPTX con la planeacion lista
 * y guarda el id en localStorage para que el usuario sepa a cual pendiente
 * le corresponde este archivo.
 *
 * "Hogar" tiene una sola experiencia. "Llamada" tiene DOS planeaciones
 * independientes (tema + cancion cada una) y puede ser para nino, nina,
 * bebe o mujer gestante (sin fecha de nacimiento ni genero en ese caso).
 */

const BACKEND_URL = "https://rayuela-production.up.railway.app";

const formulario        = document.getElementById("formulario-planeacion");
const bandaInfo          = document.getElementById("banda-info");
const mensajeEstado      = document.getElementById("mensaje-estado");
const boton              = document.getElementById("boton-planear");
const camposHogar        = document.getElementById("campos-hogar");
const camposLlamada      = document.getElementById("campos-llamada");
const campoTipoParticipante = document.getElementById("campo-tipo-participante");
const filaEdad           = document.getElementById("fila-edad");

const CLAVE_LOCAL = "rayuela_borrador_planeacion";
const CAMPOS_GUARDABLES = [
  "nombre", "fecha_nacimiento", "genero", "tipo_participante",
  "actividad_principal", "nombre_ronda", "link_ronda",
  "actividad_principal_llamada", "nombre_ronda_llamada", "link_ronda_llamada",
  "actividad_principal_2", "nombre_ronda_2", "link_ronda_2",
  "modalidad_acompanamiento", "objetos_paquete", "aspectos_fortalecer",
];

function tipoCuadernoSeleccionado() {
  return formulario.querySelector('input[name="tipo_cuaderno"]:checked')?.value || "hogar";
}

// ── Borrador local ──────────────────────────────────────────────────────────
function cargarBorrador() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE_LOCAL) || "{}");
    for (const campo of CAMPOS_GUARDABLES) {
      const el = formulario.elements[campo];
      if (el && guardado[campo]) el.value = guardado[campo];
    }
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
  datos.tipo_cuaderno = tipoCuadernoSeleccionado();
  localStorage.setItem(CLAVE_LOCAL, JSON.stringify(datos));
}

formulario.addEventListener("input", guardarBorrador);
cargarBorrador();

// ── Mostrar/ocultar bloques segun tipo de cuaderno y participante ──────────
function actualizarVisibilidad() {
  const tipo = tipoCuadernoSeleccionado();
  const esLlamada = tipo === "llamada";
  const tipoParticipante = formulario.elements["tipo_participante"]?.value || "nino";
  const esGestante = esLlamada && tipoParticipante === "gestante";

  campoTipoParticipante.classList.toggle("oculto", !esLlamada);
  camposHogar.classList.toggle("oculto", esLlamada);
  camposLlamada.classList.toggle("oculto", !esLlamada);
  filaEdad.classList.toggle("oculto", esGestante);

  if (esGestante) {
    bandaInfo.textContent = "Mujer gestante — no se calcula edad ni banda de desarrollo.";
    bandaInfo.classList.remove("error");
  } else if (!formulario.elements["fecha_nacimiento"].value) {
    bandaInfo.textContent = "";
  } else {
    actualizarBanda();
  }
}
formulario.querySelectorAll('input[name="tipo_cuaderno"]').forEach(r =>
  r.addEventListener("change", actualizarVisibilidad)
);
formulario.elements["tipo_participante"]?.addEventListener("change", actualizarVisibilidad);
actualizarVisibilidad();

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

  const tipo = tipoCuadernoSeleccionado();
  const tipoParticipante = formulario.elements["tipo_participante"]?.value || "nino";
  const esGestante = tipo === "llamada" && tipoParticipante === "gestante";

  const cuerpo = {
    nombre:          formulario.elements["nombre"].value.trim(),
    tipo_cuaderno:   tipo,
    objetos_paquete: formulario.elements["objetos_paquete"].value.trim(),
  };

  if (!esGestante) {
    cuerpo.fecha_nacimiento = formulario.elements["fecha_nacimiento"].value;
    cuerpo.genero           = formulario.elements["genero"].value;
  }

  if (tipo === "hogar") {
    cuerpo.actividad_principal = formulario.elements["actividad_principal"].value.trim();
    cuerpo.nombre_ronda         = formulario.elements["nombre_ronda"].value.trim();
    cuerpo.link_ronda           = formulario.elements["link_ronda"].value.trim();
  } else {
    cuerpo.tipo_participante     = tipoParticipante;
    cuerpo.actividad_principal   = formulario.elements["actividad_principal_llamada"].value.trim();
    cuerpo.nombre_ronda          = formulario.elements["nombre_ronda_llamada"].value.trim();
    cuerpo.link_ronda            = formulario.elements["link_ronda_llamada"].value.trim();
    cuerpo.actividad_principal_2 = formulario.elements["actividad_principal_2"].value.trim();
    cuerpo.nombre_ronda_2        = formulario.elements["nombre_ronda_2"].value.trim();
    cuerpo.link_ronda_2          = formulario.elements["link_ronda_2"].value.trim();
    cuerpo.modalidad_acompanamiento = formulario.elements["modalidad_acompanamiento"].value.trim();
    cuerpo.aspectos_fortalecer      = formulario.elements["aspectos_fortalecer"].value.trim();
  }

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
