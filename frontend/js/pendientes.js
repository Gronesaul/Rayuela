/**
 * Rayuela — pantalla de pendientes.
 * Carga la lista de planeaciones con estado "pendiente_voces" y permite
 * a Jimena agregar las observaciones del encuentro real para generar el
 * documento final (planeacion + voces completas).
 */

const BACKEND_URL = "https://rayuela-production.up.railway.app";

async function cargarPendientes() {
  const contenedor = document.getElementById("contenido-pendientes");

  try {
    const resp = await fetch(`${BACKEND_URL}/api/planeaciones`);
    if (!resp.ok) throw new Error("No se pudo cargar la lista.");
    const pendientes = await resp.json();

    if (!Array.isArray(pendientes) || pendientes.length === 0) {
      contenedor.innerHTML =
        '<p class="sin-pendientes">No hay encuentros pendientes por completar. ' +
        'Cuando planees uno, aparecera aqui.</p>';
      return;
    }

    const lista = document.createElement("div");
    lista.className = "lista-pendientes";

    for (const p of pendientes) {
      lista.appendChild(crearTarjetaPendiente(p));
    }

    contenedor.innerHTML = "";
    contenedor.appendChild(lista);

  } catch (err) {
    contenedor.innerHTML =
      '<p class="ayuda error">No se pudo cargar: ' + err.message + '</p>';
  }
}

function crearTarjetaPendiente(p) {
  const tipoTexto = p.tipo_cuaderno === "hogar"
    ? "Encuentro en el hogar"
    : "Acompanamiento por llamada";

  const fechaMostrar = p.fecha_encuentro
    ? new Date(p.fecha_encuentro + "T12:00:00").toLocaleDateString("es-CO", {
        day: "2-digit", month: "long", year: "numeric"
      })
    : "";

  const tarjeta = document.createElement("div");
  tarjeta.className = "item-pendiente";
  tarjeta.innerHTML =
    '<h3>' + p.nombre_nino + '</h3>' +
    '<p class="item-meta">' +
      tipoTexto +
      (fechaMostrar ? ' &nbsp;·&nbsp; ' + fechaMostrar : '') +
      (p.actividad_principal ? ' &nbsp;·&nbsp; ' + p.actividad_principal : '') +
    '</p>' +
    '<button class="btn-completar" data-id="' + p.id + '">Completar voces</button>' +
    '<div class="completar-panel" id="panel-' + p.id + '">' +
      '<label>¿Que paso en el encuentro? (escribe con tus palabras, sin pulir nada)</label>' +
      '<textarea rows="5" placeholder="Cuéntame qué viviste: como participo el nino o la nina, ' +
        'que hizo la familia, que fue lo que mas llamo la atencion, que funciono bien y que no..."></textarea>' +
      '<p class="ayuda" id="estado-' + p.id + '" aria-live="polite"></p>' +
      '<button type="button" class="btn-generar" data-id="' + p.id + '">' +
        '✨ Generar documento final' +
      '</button>' +
    '</div>';

  // Abre/cierra el panel de completar
  const btnCompletar = tarjeta.querySelector(".btn-completar");
  const panel = tarjeta.querySelector(".completar-panel");
  btnCompletar.addEventListener("click", () => {
    panel.classList.toggle("abierto");
    if (panel.classList.contains("abierto")) {
      panel.querySelector("textarea").focus();
    }
  });

  // Envio del formulario de completar
  const btnGenerar = tarjeta.querySelector(".btn-generar");
  btnGenerar.addEventListener("click", () => {
    const obs = panel.querySelector("textarea").value.trim();
    if (!obs) {
      mostrarEstado(p.id, "Escribe las observaciones antes de generar.", true);
      return;
    }
    completarEncuentro(p.id, obs, btnGenerar);
  });

  return tarjeta;
}

async function completarEncuentro(planeacionId, observaciones, boton) {
  const estadoEl = document.getElementById("estado-" + planeacionId);
  boton.disabled = true;
  mostrarEstado(planeacionId, "Generando el documento final con IA... esto puede tardar unos segundos ⏳");

  try {
    const resp = await fetch(
      `${BACKEND_URL}/api/planeacion/${planeacionId}/completar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ observaciones }),
      }
    );

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || "Algo salio mal.");
    }

    // Descarga el cuaderno completo
    const blob = await resp.blob();
    const cd = resp.headers.get("Content-Disposition") || "";
    const nombreArchivo = cd.split("filename=")[1]?.replaceAll('"', "")
                         || "cuaderno-completo-rayuela.pptx";
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombreArchivo;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();

    mostrarEstado(planeacionId,
      "Cuaderno completo generado y descargado. Esta planeacion queda marcada como completada.");

    // Quita la tarjeta de la lista tras un momento
    setTimeout(() => {
      const tarjeta = boton.closest(".item-pendiente");
      if (tarjeta) tarjeta.style.opacity = "0.4";
    }, 1500);

  } catch (err) {
    mostrarEstado(planeacionId, "No se pudo generar: " + err.message, true);
    boton.disabled = false;
  }
}

function mostrarEstado(id, texto, esError = false) {
  const el = document.getElementById("estado-" + id);
  if (!el) return;
  el.textContent = texto;
  el.classList.toggle("error", esError);
}

// Carga al abrir la pagina
cargarPendientes();
