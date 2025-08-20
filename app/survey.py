# app/survey.py
from datetime import datetime
from flask import Blueprint, request, jsonify

from .db import db_all, db_one, db_exec
from .utils import require_auth, level_from_score
from .ml import predict_level

# Este blueprint ya trae su prefijo /api/survey
bp = Blueprint("survey", __name__, url_prefix="/api/survey")


# ------------------ Cargar encuesta SCAS ------------------
@bp.get("/scas")
@require_auth()
def scas_def():
    """Devuelve metadatos de la encuesta SCAS + lista de ítems."""
    s = db_one("SELECT * FROM surveys WHERE code='SCAS_CHILD'")
    if not s:
        return jsonify({"error": "Encuesta no encontrada"}), 404

    items = db_all(
        """
        SELECT id, item_number, prompt, is_scored, subscale
        FROM survey_items
        WHERE survey_id=:sid
        ORDER BY item_number
        """,
        {"sid": s["id"]}
    )
    return jsonify({"survey": s, "items": items})


# ------------------ Enviar respuestas SCAS ------------------
@bp.post("/scas/submit")
@require_auth()
def scas_submit():
    """
    Recibe: { answers: [{item_id, value}, ...] }
    - Normaliza valores 0..3
    - Calcula total y subescalas
    - Previene doble click (si hay una respuesta del mismo usuario hace <5s)
    - Guarda cabecera en responses y detalle en response_items
    - Devuelve etiqueta por regla + predicción ML
    """
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []
    if not answers:
        return jsonify({"error": "Sin respuestas"}), 400

    s = db_one("SELECT id FROM surveys WHERE code='SCAS_CHILD'")
    if not s:
        return jsonify({"error": "Encuesta no encontrada"}), 404
    sid = s["id"]

    # --- Metadatos de ítems ---
    meta = db_all(
        "SELECT id, is_scored, subscale FROM survey_items WHERE survey_id=:sid",
        {"sid": sid}
    )
    info = {m["id"]: {"is_scored": m["is_scored"], "subscale": m["subscale"]} for m in meta}

    # --- Normalización + puntajes ---
    subs = {"GAD": 0, "SOC": 0, "OCD": 0, "PAA": 0, "PHB": 0, "SAD": 0}
    total = 0
    normalized = []
    for a in answers:
        try:
            iid = int(a.get("item_id"))
            val = int(a.get("value", 0))
        except (TypeError, ValueError):
            continue
        val = max(0, min(3, val))  # clamp 0..3
        normalized.append((iid, val))

        m = info.get(iid)
        if m and m["is_scored"]:
            total += val
            if m["subscale"]:
                subs[m["subscale"]] += val

    if not normalized:
        return jsonify({"error": "Respuestas inválidas"}), 400

    # --- Usuario actual ---
    user = db_one("SELECT id, fullname, email FROM users WHERE email=:e", {"e": request.user["email"]})
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 400
    uid = user["id"]

    # --- Anti doble click: reusar respuesta si la última es muy reciente ---
    last = db_one(
        """
        SELECT id, created_at
        FROM responses
        WHERE user_id=:u AND survey_id=:s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"u": uid, "s": sid}
    )

    reuse_last = False
    resp_id = None
    if last and isinstance(last.get("created_at"), datetime):
        # created_at viene como naive UTC (por nuestra conexión)
        delta = datetime.utcnow() - last["created_at"].replace(tzinfo=None)
        if delta.total_seconds() < 5:
            reuse_last = True
            resp_id = last["id"]

    # --- Insertar nueva respuesta (si no reusamos la última) ---
    if not reuse_last:
        # Cabecera
        db_exec(
            "INSERT INTO responses(user_id, survey_id, total_score) VALUES (:u,:s,:t)",
            {"u": uid, "s": sid, "t": total}
        )
        # Recupera ID de esa respuesta (por fecha más reciente del mismo usuario/encuesta)
        newrow = db_one(
            """
            SELECT id FROM responses
            WHERE user_id=:u AND survey_id=:s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"u": uid, "s": sid}
        )
        resp_id = newrow["id"] if newrow else None

        # Detalle de ítems
        if resp_id:
            for iid, val in normalized:
                db_exec(
                    "INSERT INTO response_items(response_id, item_id, value) VALUES (:r,:i,:v)",
                    {"r": resp_id, "i": iid, "v": val}
                )

    # --- Etiqueta por regla + ML ---
    features = {
        "total": float(total),
        "GAD": float(subs.get("GAD", 0)),
        "SOC": float(subs.get("SOC", 0)),
        "OCD": float(subs.get("OCD", 0)),
        "PAA": float(subs.get("PAA", 0)),
        "PHB": float(subs.get("PHB", 0)),
        "SAD": float(subs.get("SAD", 0)),
    }
    ml_out = predict_level(features)

    return jsonify({
        "response_id": resp_id,
        "total_score": total,
        "subscales": subs,
        "level": level_from_score(total),
        "ml": ml_out,
        "duplicate": reuse_last
    })
