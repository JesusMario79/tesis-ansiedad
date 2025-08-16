# app/seed/seed_scas.py
import os
from passlib.hash import bcrypt
from sqlalchemy import text
from ..db import db_one, db_all, db_exec

TEXTOS = [
 "Me preocupan las cosas.",  # 1
 "Me da miedo la oscuridad.",  # 2
 "Cuando tengo un problema, siento una sensación extraña en el estómago.",  # 3
 "Tengo miedo.",  # 4
 "Me daría miedo estar solo en casa.",  # 5
 "Tengo miedo cuando tengo que hacer un examen.",  # 6
 "Tengo miedo si tengo que usar baños públicos.",  # 7
 "Me preocupa estar lejos de mis padres.",  # 8
 "Tengo miedo de hacer el ridículo delante de la gente.",  # 9
 "Me preocupa que me vaya mal en el colegio.",  # 10
 "Soy popular entre otros niños de mi edad.",  # 11 (relleno)
 "Me preocupa que le pase algo malo a alguien de mi familia.",  # 12
 "De repente siento que no puedo respirar cuando no hay ninguna razón para ello.",  # 13
 "Tengo que comprobar constantemente que he hecho las cosas bien (como que el interruptor esté apagado o que la puerta esté cerrada con llave).",  # 14
 "Tengo miedo si tengo que dormir solo.",  # 15
 "Tengo problemas para ir a la escuela por las mañanas porque me siento nervioso o asustado.",  # 16
 "Soy bueno en los deportes.",  # 17 (relleno)
 "Tengo miedo a los perros.",  # 18
 "No puedo sacarme los pensamientos malos o tontos de la cabeza.",  # 19
 "Cuando tengo un problema, mi corazón late muy rápido.",  # 20
 "De repente empiezo a sacudirme cuando no hay ninguna razón para ello.",  # 21
 "Me preocupa que me pase algo malo.",  # 22
 "Tengo miedo de ir al médico o al dentista.",  # 23
 "Cuando tengo un problema, me siento inestable.",  # 24
 "Tengo miedo de estar en lugares altos o en ascensores.",  # 25
 "Soy una buena persona.",  # 26 (relleno)
 "Tengo que pensar en cosas especiales para evitar que pasen cosas malas (como números o palabras).",  # 27
 "Tengo miedo si tengo que viajar en coche, autobús o tren.",  # 28
 "Me preocupa lo que piensen los demás de mí.",  # 29
 "Tengo miedo de estar en lugares concurridos (como centros comerciales, cines, autobuses, parques infantiles concurridos).",  # 30
 "Me siento feliz.",  # 31 (relleno)
 "De repente siento mucho miedo sin ninguna razón.",  # 32
 "Tengo miedo de los insectos o las arañas.",  # 33
 "De repente me mareo o me desmayo sin ninguna razón.",  # 34
 "Tengo miedo si tengo que hablar delante de mi clase.",  # 35
 "Mi corazón empieza a latir demasiado rápido sin ninguna razón.",  # 36
 "Me preocupa sentir miedo de repente cuando no hay nada que temer.",  # 37
 "Me gusto a mí mismo.",  # 38 (relleno)
 "Tengo miedo de estar en lugares pequeños y cerrados, como túneles o habitaciones pequeñas.",  # 39
 "Tengo que hacer algunas cosas una y otra vez (como lavarme las manos, limpiar o poner las cosas en cierto orden).",  # 40
 "Me molestan los pensamientos o imágenes malos o tontos en mi mente.",  # 41
 "Tengo que hacer algunas cosas de la manera correcta para evitar que pasen cosas malas.",  # 42
 "Estoy orgulloso de mi trabajo escolar.",  # 43 (relleno)
 "Me daría miedo si tuviera que quedarme fuera de casa toda la noche."  # 44
]

SCORING = {
 1,2,3,4,5,6,7,8,9,10,12,13,14,15,16,18,19,20,21,22,23,24,25,
 27,28,29,30,32,33,34,35,36,37,39,40,41,42,44
}

SUB = {
 "GAD":[1,3,4,20,22,24],
 "SOC":[6,7,9,10,29,35],
 "OCD":[14,19,27,40,41,42],
 "PAA":[13,21,28,30,32,34,36,37,39],
 "PHB":[2,18,23,25,33],
 "SAD":[5,8,12,15,16,44]
}

def _create_tables_if_missing():
    # --- USERS ---
    db_exec("""
    CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      fullname VARCHAR(120) NOT NULL,
      email VARCHAR(190) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      role ENUM('admin','student') NOT NULL DEFAULT 'student',
      gender ENUM('M','F') NULL,
      age TINYINT UNSIGNED NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # --- SURVEYS ---
    db_exec("""
    CREATE TABLE IF NOT EXISTS surveys (
      id INT AUTO_INCREMENT PRIMARY KEY,
      code VARCHAR(50) NOT NULL UNIQUE,
      title VARCHAR(120) NOT NULL,
      description TEXT NULL,
      min_age TINYINT UNSIGNED NULL,
      max_age TINYINT UNSIGNED NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # --- SURVEY ITEMS ---
    db_exec("""
    CREATE TABLE IF NOT EXISTS survey_items (
      id INT AUTO_INCREMENT PRIMARY KEY,
      survey_id INT NOT NULL,
      item_number INT NOT NULL,
      prompt TEXT NOT NULL,
      is_scored TINYINT(1) NOT NULL DEFAULT 1,
      subscale ENUM('GAD','SOC','OCD','PAA','PHB','SAD') NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_si_survey FOREIGN KEY (survey_id) REFERENCES surveys(id) ON DELETE CASCADE,
      UNIQUE KEY uq_survey_item (survey_id, item_number),
      INDEX idx_survey (survey_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # --- RESPONSES ---
    db_exec("""
    CREATE TABLE IF NOT EXISTS responses (
      id INT AUTO_INCREMENT PRIMARY KEY,
      user_id INT NOT NULL,
      survey_id INT NOT NULL,
      total_score INT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_resp_user   FOREIGN KEY (user_id)  REFERENCES users(id),
      CONSTRAINT fk_resp_survey FOREIGN KEY (survey_id) REFERENCES surveys(id),
      INDEX idx_resp_user (user_id),
      INDEX idx_resp_survey (survey_id),
      INDEX idx_resp_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # --- RESPONSE ITEMS ---
    db_exec("""
    CREATE TABLE IF NOT EXISTS response_items (
      id INT AUTO_INCREMENT PRIMARY KEY,
      response_id INT NOT NULL,
      item_id INT NOT NULL,
      value TINYINT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_ri_resp  FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE,
      CONSTRAINT fk_ri_item  FOREIGN KEY (item_id)    REFERENCES survey_items(id),
      INDEX idx_ri_resp (response_id),
      INDEX idx_ri_item (item_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

def _ensure_admin():
    if db_one("SELECT id FROM users WHERE role='admin' LIMIT 1"):
        return
    email = (os.getenv("ADMIN_EMAIL","admin@upn.com")).lower()
    fullname = os.getenv("ADMIN_FULLNAME","Administrador")
    password = os.getenv("ADMIN_PASSWORD","admin123")
    db_exec("""INSERT INTO users(fullname,email,password_hash,role)
               VALUES (:fn,:em,:ph,'admin')""",
            {"fn": fullname, "em": email, "ph": bcrypt.hash(password)})

def _ensure_scas():
    s = db_one("SELECT id FROM surveys WHERE code='SCAS_CHILD'")
    if not s:
        db_exec("""INSERT INTO surveys(code,title,description,min_age,max_age)
                   VALUES('SCAS_CHILD','SCAS Child (12-15)',
                          '44 ítems (38 puntúan + 6 relleno)',12,15)""")
        s = db_one("SELECT id FROM surveys WHERE code='SCAS_CHILD'")
    sid = s["id"]

    existing = {r["item_number"]: r for r in db_all(
        "SELECT id, item_number FROM survey_items WHERE survey_id=:sid", {"sid": sid}
    )}

    for n in range(1, 45):
        is_scored = 1 if n in SCORING else 0
        sub = None
        for k, arr in SUB.items():
            if n in arr:
                sub = k
                break

        if n in existing:
            db_exec(
                """UPDATE survey_items
                   SET prompt=:p, is_scored=:sc, subscale=:su
                   WHERE survey_id=:sid AND item_number=:n""",
                {"p": TEXTOS[n-1], "sc": is_scored, "su": sub, "sid": sid, "n": n}
            )
        else:
            db_exec(
                """INSERT INTO survey_items(survey_id,item_number,prompt,is_scored,subscale)
                   VALUES (:sid,:n,:p,:sc,:su)""",
                {"sid": sid, "n": n, "p": TEXTOS[n-1], "sc": is_scored, "su": sub}
            )

def run_seed():
    _create_tables_if_missing()
    _ensure_admin()
    _ensure_scas()
    print("Esquema y datos SCAS listos en MySQL.")
