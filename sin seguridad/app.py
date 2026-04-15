# ============================================================
# app.py — Backend Flask para HealthSecure (versión sin seguridad)
# Expone una API REST con endpoints para pacientes e historias clínicas
# ============================================================

from flask import Flask, request, jsonify   # Flask: micro-framework web
from flask_cors import CORS                 # Permite que el HTML llame a la API desde otro origen
import mysql.connector                      # Conector oficial de MySQL para Python
from mysql.connector import Error

app = Flask(__name__)
CORS(app)  # Habilita CORS: el navegador lo exige cuando el HTML y la API están en puertos distintos

# -------------------------------------------------------
# Configuración de la conexión a MySQL (XAMPP)
# Ajusta "password" si pusiste contraseña en phpMyAdmin
# -------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",   # XAMPP siempre usa localhost
    "port":     3306,          # Puerto por defecto de MySQL
    "user":     "root",        # Usuario por defecto de XAMPP
    "password": "",            # XAMPP sin contraseña por defecto
    "database": "healthsecure"
}

def get_connection():
    """
    Abre una nueva conexión a MySQL.
    Se crea una conexión por petición para simplificar el ejemplo.
    En producción se usaría un pool de conexiones.
    """
    return mysql.connector.connect(**DB_CONFIG)


# ==============================================================
# ENDPOINTS DE PACIENTES
# ==============================================================

@app.route("/pacientes", methods=["GET"])
def listar_pacientes():
    """
    GET /pacientes
    Devuelve la lista completa de pacientes.
    Respuesta: lista JSON con los campos del registro.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)  # dictionary=True → cada fila es un dict
    cursor.execute("SELECT id, nombre, fecha_nacimiento, genero, telefono, email FROM pacientes")
    pacientes = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convertir fecha_nacimiento (objeto date) a string para que JSON pueda serializarlo
    for p in pacientes:
        if p["fecha_nacimiento"]:
            p["fecha_nacimiento"] = str(p["fecha_nacimiento"])

    return jsonify(pacientes), 200  # 200 OK


@app.route("/pacientes", methods=["POST"])
def crear_paciente():
    """
    POST /pacientes
    Cuerpo esperado (JSON):
      { "nombre": "...", "fecha_nacimiento": "YYYY-MM-DD",
        "genero": "M|F|Otro", "telefono": "...", "email": "..." }
    Respuesta: el id del nuevo paciente.
    """
    datos = request.get_json()  # Parsea el cuerpo JSON que envía el frontend

    # Validación básica: campos obligatorios
    if not datos or not datos.get("nombre") or not datos.get("fecha_nacimiento"):
        return jsonify({"error": "nombre y fecha_nacimiento son obligatorios"}), 400  # 400 Bad Request

    conn = get_connection()
    cursor = conn.cursor()

    # Consulta parametrizada con %s → evita inyección SQL
    sql = """
        INSERT INTO pacientes (nombre, fecha_nacimiento, genero, telefono, email)
        VALUES (%s, %s, %s, %s, %s)
    """
    valores = (
        datos["nombre"],
        datos["fecha_nacimiento"],
        datos.get("genero", "Otro"),   # valor por defecto si no se envía
        datos.get("telefono", ""),
        datos.get("email", "")
    )
    cursor.execute(sql, valores)
    conn.commit()                      # Confirma la transacción en la BD
    nuevo_id = cursor.lastrowid        # Recupera el ID generado por AUTO_INCREMENT

    cursor.close()
    conn.close()

    return jsonify({"id": nuevo_id, "mensaje": "Paciente creado"}), 201  # 201 Created


@app.route("/pacientes/<int:paciente_id>", methods=["DELETE"])
def eliminar_paciente(paciente_id):
    """
    DELETE /pacientes/<id>
    Elimina el paciente y sus historias (CASCADE en BD).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pacientes WHERE id = %s", (paciente_id,))
    conn.commit()
    afectadas = cursor.rowcount   # rowcount indica cuántas filas se modificaron
    cursor.close()
    conn.close()

    if afectadas == 0:
        return jsonify({"error": "Paciente no encontrado"}), 404  # 404 Not Found

    return jsonify({"mensaje": "Paciente eliminado"}), 200


# ==============================================================
# ENDPOINTS DE HISTORIAS CLÍNICAS
# ==============================================================

@app.route("/historias/<int:paciente_id>", methods=["GET"])
def listar_historias(paciente_id):
    """
    GET /historias/<paciente_id>
    Devuelve todas las historias clínicas de un paciente específico.
    JOIN con medicos para incluir el nombre del médico en la respuesta.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT h.id, h.fecha_consulta, h.motivo, h.diagnostico, h.tratamiento,
               m.nombre AS medico, m.especialidad
        FROM historias_clinicas h
        JOIN medicos m ON h.medico_id = m.id
        WHERE h.paciente_id = %s
        ORDER BY h.fecha_consulta DESC
    """
    cursor.execute(sql, (paciente_id,))
    historias = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convertir datetime a string para JSON
    for h in historias:
        if h["fecha_consulta"]:
            h["fecha_consulta"] = str(h["fecha_consulta"])

    return jsonify(historias), 200


@app.route("/historias", methods=["POST"])
def crear_historia():
    """
    POST /historias
    Cuerpo esperado (JSON):
      { "paciente_id": 1, "medico_id": 1,
        "motivo": "...", "diagnostico": "...", "tratamiento": "..." }
    """
    datos = request.get_json()

    campos_requeridos = ["paciente_id", "medico_id", "motivo"]
    for campo in campos_requeridos:
        if not datos or not datos.get(campo):
            return jsonify({"error": f"El campo '{campo}' es obligatorio"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO historias_clinicas (paciente_id, medico_id, motivo, diagnostico, tratamiento)
        VALUES (%s, %s, %s, %s, %s)
    """
    valores = (
        datos["paciente_id"],
        datos["medico_id"],
        datos["motivo"],
        datos.get("diagnostico", ""),
        datos.get("tratamiento", "")
    )
    cursor.execute(sql, valores)
    conn.commit()
    nuevo_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify({"id": nuevo_id, "mensaje": "Historia clínica creada"}), 201


@app.route("/medicos", methods=["GET"])
def listar_medicos():
    """
    GET /medicos
    Devuelve el catálogo de médicos (para poblar el <select> del formulario).
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, especialidad FROM medicos")
    medicos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(medicos), 200


# -------------------------------------------------------
# Punto de entrada: ejecuta el servidor Flask
# debug=True recarga automáticamente al guardar el archivo
# port=5000 es el puerto por defecto de Flask
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)