"""
app.py

Aplicação Web com componente semântica:
- API REST (CRUD) sobre estudantes, UCs, docentes e avaliações
- Endpoint genérico de consultas SPARQL sobre o grafo RDF/OWL
- Interface web simples para demonstração das consultas inteligentes

Para correr:
    pip install -r requirements.txt
    python app/app.py

Depois aceder a http://localhost:5000
"""

from flask import Flask, jsonify, request, render_template
from graph_store import store
from queries import QUERIES

app = Flask(__name__)


# ----------------------------------------------------------------------
# Interface Web
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", queries=QUERIES)


# ----------------------------------------------------------------------
# API REST: Estudantes
# ----------------------------------------------------------------------

@app.route("/api/estudantes", methods=["GET"])
def get_estudantes():
    return jsonify(store.list_estudantes())


@app.route("/api/estudantes/<numero_aluno>", methods=["GET"])
def get_estudante(numero_aluno):
    estudante = store.get_estudante(numero_aluno)
    if estudante is None:
        return jsonify({"erro": "Estudante não encontrado"}), 404
    return jsonify(estudante)


@app.route("/api/estudantes", methods=["POST"])
def create_estudante():
    data = request.get_json(force=True)
    try:
        uri = store.create_estudante(
            numero_aluno=data["numeroAluno"],
            nome=data["nome"],
            email=data.get("email"),
            curso_uri=data.get("cursoUri"),
        )
    except (KeyError, ValueError) as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"uri": uri}), 201


@app.route("/api/estudantes/<numero_aluno>", methods=["DELETE"])
def delete_estudante(numero_aluno):
    if store.delete_estudante(numero_aluno):
        return jsonify({"mensagem": "Estudante removido"}), 200
    return jsonify({"erro": "Estudante não encontrado"}), 404


# ----------------------------------------------------------------------
# API REST: Unidades Curriculares
# ----------------------------------------------------------------------

@app.route("/api/ucs", methods=["GET"])
def get_ucs():
    return jsonify(store.list_ucs())


@app.route("/api/ucs", methods=["POST"])
def create_uc():
    data = request.get_json(force=True)
    try:
        uri = store.create_uc(
            codigo=data["codigo"],
            nome=data["nome"],
            ects=data["ects"],
            semestre=data["semestre"],
            curso_uri=data.get("cursoUri"),
        )
    except (KeyError, ValueError) as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"uri": uri}), 201


# ----------------------------------------------------------------------
# API REST: Docentes
# ----------------------------------------------------------------------

@app.route("/api/docentes", methods=["GET"])
def get_docentes():
    return jsonify(store.list_docentes())


# ----------------------------------------------------------------------
# API REST: Avaliações
# ----------------------------------------------------------------------

@app.route("/api/avaliacoes", methods=["GET"])
def get_avaliacoes():
    numero_aluno = request.args.get("numeroAluno")
    return jsonify(store.list_avaliacoes(numero_aluno))


@app.route("/api/avaliacoes", methods=["POST"])
def create_avaliacao():
    data = request.get_json(force=True)
    try:
        uri = store.create_avaliacao(
            numero_aluno=data["numeroAluno"],
            codigo_uc=data["codigoUC"],
            nota=data["nota"],
            ano_letivo=data.get("anoLetivo"),
        )
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"uri": uri}), 201


# ----------------------------------------------------------------------
# API REST: Cursos (auxiliar)
# ----------------------------------------------------------------------

@app.route("/api/cursos", methods=["GET"])
def get_cursos():
    return jsonify(store.list_cursos())


# ----------------------------------------------------------------------
# Consultas semânticas (SPARQL)
# ----------------------------------------------------------------------

@app.route("/api/sparql/predefinidas", methods=["GET"])
def list_predefined_queries():
    """Lista as consultas SPARQL inteligentes pré-definidas."""
    return jsonify({
        key: {"label": q["label"], "description": q["description"]}
        for key, q in QUERIES.items()
    })


@app.route("/api/sparql/predefinidas/<query_id>", methods=["GET"])
def run_predefined_query(query_id):
    """Executa uma consulta SPARQL pré-definida."""
    query = QUERIES.get(query_id)
    if query is None:
        return jsonify({"erro": "Consulta não encontrada"}), 404
    results = store.query(query["sparql"])
    return jsonify({
        "label": query["label"],
        "description": query["description"],
        "resultados": results,
    })


@app.route("/api/sparql", methods=["POST"])
def run_custom_query():
    """Executa uma consulta SPARQL arbitrária (SELECT/ASK) submetida pelo utilizador."""
    data = request.get_json(force=True)
    sparql = data.get("query", "")
    if not sparql.strip():
        return jsonify({"erro": "Campo 'query' em falta"}), 400
    try:
        results = store.query(sparql)
    except Exception as e:
        return jsonify({"erro": f"Erro na consulta SPARQL: {e}"}), 400
    return jsonify({"resultados": results})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

