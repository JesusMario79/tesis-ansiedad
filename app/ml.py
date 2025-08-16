# app/ml.py
from __future__ import annotations
from pathlib import Path
import numpy as np
import joblib
from typing import Dict, Any, Tuple, Optional, List
from sklearn.linear_model import LogisticRegression

from .db import db_all  # asumimos helpers db_all/db_one como en tus otros módulos

BASE_DIR   = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "scas_model.joblib"
CLASSES    = ["Bajo", "Moderado", "Alto"]  # orden fijo

FEATURES = ["total", "GAD", "SOC", "OCD", "PAA", "PHB", "SAD"]

def _score_to_label(total: int) -> str:
    if total >= 76: return "Alto"
    if total >= 38: return "Moderado"
    return "Bajo"

def _fetch_dataset() -> Tuple[np.ndarray, np.ndarray]:
    """
    Arma dataset X (features) e y (label) desde la base para SCAS_CHILD.
    X columnas = [total, GAD, SOC, OCD, PAA, PHB, SAD]
    y = label por umbrales (Bajo/Moderado/Alto) – puedes reemplazarlo por etiquetas clínicas en el futuro.
    """
    rows = db_all("""
      WITH sub AS (
        SELECT
          r.id AS response_id,
          SUM(CASE WHEN si.subscale='GAD' THEN ri.value ELSE 0 END) AS GAD,
          SUM(CASE WHEN si.subscale='SOC' THEN ri.value ELSE 0 END) AS SOC,
          SUM(CASE WHEN si.subscale='OCD' THEN ri.value ELSE 0 END) AS OCD,
          SUM(CASE WHEN si.subscale='PAA' THEN ri.value ELSE 0 END) AS PAA,
          SUM(CASE WHEN si.subscale='PHB' THEN ri.value ELSE 0 END) AS PHB,
          SUM(CASE WHEN si.subscale='SAD' THEN ri.value ELSE 0 END) AS SAD
        FROM responses r
        JOIN response_items ri ON ri.response_id = r.id
        JOIN survey_items si   ON si.id = ri.item_id
        JOIN surveys s         ON s.id = r.survey_id AND s.code='SCAS_CHILD'
        GROUP BY r.id
      )
      SELECT
        r.total_score AS total,
        sub.GAD, sub.SOC, sub.OCD, sub.PAA, sub.PHB, sub.SAD
      FROM responses r
      JOIN surveys s ON s.id = r.survey_id AND s.code='SCAS_CHILD'
      JOIN sub      ON sub.response_id = r.id
      ORDER BY r.created_at ASC;
    """)
    if not rows:
        return np.empty((0, len(FEATURES))), np.empty((0,), dtype=int)

    X = []
    y = []
    for row in rows:
        total = int(row["total"])
        gad   = int(row["GAD"] or 0)
        soc   = int(row["SOC"] or 0)
        ocd   = int(row["OCD"] or 0)
        paa   = int(row["PAA"] or 0)
        phb   = int(row["PHB"] or 0)
        sad   = int(row["SAD"] or 0)

        X.append([total, gad, soc, ocd, paa, phb, sad])
        y.append(CLASSES.index(_score_to_label(total)))
    return np.array(X, dtype=float), np.array(y, dtype=int)

def train_from_db(min_samples: int = 30) -> Dict[str, Any]:
    """
    Entrena y guarda el modelo si hay suficientes muestras. Devuelve info resumida.
    """
    X, y = _fetch_dataset()
    info = {"n_samples": int(len(y)), "trained": False, "classes": CLASSES}

    if len(y) < min_samples:
        # no entrenamos con muy pocos datos (evita overfitting)
        return info

    clf = LogisticRegression(
        multi_class="multinomial",
        class_weight="balanced",
        max_iter=2000,
        n_jobs=None
    )
    clf.fit(X, y)
    joblib.dump({"model": clf, "features": FEATURES, "classes": CLASSES}, MODEL_PATH)
    info["trained"] = True
    info["model_path"] = str(MODEL_PATH)
    return info

def _load_model() -> Optional[Dict[str, Any]]:
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return None

def predict_level(features: Dict[str, float]) -> Dict[str, Any]:
    """
    features = dict con keys en FEATURES. Devuelve:
    {
      'pred': 'Moderado',
      'proba': {'Bajo':0.2, 'Moderado':0.6, 'Alto':0.2},
      'source': 'ml' | 'rule'
    }
    """
    # Ordenar X en el orden esperado
    x = np.array([[features.get(k, 0.0) for k in FEATURES]], dtype=float)

    pack = _load_model()
    if pack:
        clf = pack["model"]
        probs = clf.predict_proba(x)[0]
        idx   = int(np.argmax(probs))
        return {
            "pred": CLASSES[idx],
            "proba": {CLASSES[i]: float(probs[i]) for i in range(len(CLASSES))},
            "source": "ml"
        }

    # Fallback por regla si no hay modelo entrenado
    total = float(features.get("total", 0.0))
    label = _score_to_label(int(total))
    probs = {
        "Bajo": 0.7 if label == "Bajo" else 0.15,
        "Moderado": 0.7 if label == "Moderado" else 0.15,
        "Alto": 0.7 if label == "Alto" else 0.15,
    }
    return {"pred": label, "proba": probs, "source": "rule"}
