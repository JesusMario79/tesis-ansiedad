# app/survey.py
from flask import Blueprint, request, jsonify
from .db import db_all, db_one, db_exec
from .utils import require_auth, level_from_score
from .ml import predict_level  # ← añade esta importación

bp = Blueprint("survey", __name__)

@bp.get("/scas")
@require_auth()
def scas_def():
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
    return jsonify({"survey": dict(s), "items": [dict(i) for i in items]})


@bp.post("/scas/submit")
@require_auth()
def scas_submit():
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []  # [{item_id, value}]
    if not answers:
        return jsonify({"error": "Sin respuestas"}), 400

    s = db_one("SELECT id FROM surveys WHERE code='SCAS_CHILD'")
    if not s:
        return jsonify({"error": "Encuesta no encontrada"}), 404

    # Metadatos de ítems (cuáles puntúan y su subescala)
    meta = db_all(
        "SELECT id, is_scored, subscale FROM survey_items WHERE survey_id=:sid",
        {"sid": s["id"]}
    )
    info = {m["id"]: {"is_scored": m["is_scored"], "subscale": m["subscale"]} for m in meta}

    # Normalización de respuestas y cálculo de puntajes
    subs = {"GAD": 0, "SOC": 0, "OCD": 0, "PAA": 0, "PHB": 0, "SAD": 0}
    total = 0
    normalized = []

    for a in answers:
        try:
            iid = int(a.get("item_id"))
            val = int(a.get("value", 0))
        except (TypeError, ValueError):
            # si viene mal alguno, lo saltamos
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

    # Usuario actual
    user = db_one("SELECT id FROM users WHERE email=:e", {"e": request.user["email"]})
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 400

    # Guardar respuesta total
    db_exec(
        "INSERT INTO responses(user_id, survey_id, total_score) VALUES (:u,:s,:t)",
        {"u": user["id"], "s": s["id"], "t": total}
    )
    resp = db_one(
        """
        SELECT id
        FROM responses
        WHERE user_id=:u AND survey_id=:s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"u": user["id"], "s": s["id"]}
    )

    # Guardar cada ítem de la respuesta
    if resp:
        for iid, val in normalized:
            db_exec(
                "INSERT INTO response_items(response_id, item_id, value) VALUES (:r,:i,:v)",
                {"r": resp["id"], "i": iid, "v": val}
            )

    # Etiqueta por regla (umbral)
    level = level_from_score(total)

    # === Predicción ML ===
    # Construimos features en el orden esperado por el modelo
    features = {
        "total": float(total),
        "GAD": float(subs.get("GAD", 0)),
        "SOC": float(subs.get("SOC", 0)),
        "OCD": float(subs.get("OCD", 0)),
        "PAA": float(subs.get("PAA", 0)),
        "PHB": float(subs.get("PHB", 0)),
        "SAD": float(subs.get("SAD", 0)),
    }
    ml_out = predict_level(features)  # devuelve {'pred':..., 'proba':{...}, 'source':'ml|rule'}

    return jsonify({
        "response_id": resp["id"] if resp else None,
        "total_score": total,
        "subscales": subs,
        "level": level_from_score(total),   # etiqueta referencial por umbral
        "ml": ml_out      
    })
