"""
API Academia RDF — Instituto Politécnico da Huíla (IPH / UMN)
Autenticação por papel: Estudante · Docente · Admin
Persistência semântica: RDFLib + inferência OWL-RL
"""

from flask import Flask, request, jsonify, session, send_from_directory
from functools import wraps
from rdflib import Graph, Namespace, Literal, RDF
from rdflib.namespace import RDFS, XSD
from owlrl import DeductiveClosure, OWLRL_Semantics
from flask_cors import CORS
import hashlib, secrets, os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

# ================================================================
#  ROTA PRINCIPAL — serve o frontend HTML
# ================================================================
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'frontend.html')

ACAD = Namespace("http://exemplo.org/academia#")
ONTOLOGIA_PATH = "ontologia.ttl"
DADOS_PATH = "dados.ttl"

# ================================================================
#  BASE DE UTILIZADORES (em produção usar base de dados)
#  Senhas: sha256(texto)
# ================================================================
def sha(texto):
    return hashlib.sha256(texto.encode()).hexdigest()

UTILIZADORES = {
    # estudantes — número de estudante como login
    "joao.luvumba@iph.edu.ao":     {"senha": sha("joao123"),    "papel": "estudante", "id_rdf": "Joao"},
    "maria.tchissola@iph.edu.ao":  {"senha": sha("maria123"),   "papel": "estudante", "id_rdf": "Maria"},
    "pedro.sachikolo@iph.edu.ao":  {"senha": sha("pedro123"),   "papel": "estudante", "id_rdf": "Pedro"},
    "ana.muenho@iph.edu.ao":       {"senha": sha("ana123"),     "papel": "estudante", "id_rdf": "Ana"},
    "sofia.calunga@iph.edu.ao":    {"senha": sha("sofia123"),   "papel": "estudante", "id_rdf": "Sofia"},
    "carlos.mutemba@iph.edu.ao":   {"senha": sha("carlos123"),  "papel": "estudante", "id_rdf": "Carlos"},
    "paulo.kangamba@iph.edu.ao":   {"senha": sha("paulo123"),   "papel": "estudante", "id_rdf": "PauloX"},
    # docentes
    "csilva@iph.edu.ao":           {"senha": sha("csilva123"),  "papel": "docente",   "id_rdf": "ProfSilva"},
    "amendes@iph.edu.ao":          {"senha": sha("amendes123"), "papel": "docente",   "id_rdf": "ProfMendes"},
    "rcosta@iph.edu.ao":           {"senha": sha("rcosta123"),  "papel": "docente",   "id_rdf": "ProfCosta"},
    "dnunes@iph.edu.ao":           {"senha": sha("dnunes123"),  "papel": "docente",   "id_rdf": "ProfNunes"},
    # admin
    "admin@iph.edu.ao":            {"senha": sha("admin2025"),  "papel": "admin",     "id_rdf": None},
}

# ================================================================
#  GRAFO RDF
# ================================================================
def carregar_grafo():
    g = Graph()
    g.bind("acad", ACAD)
    g.parse(ONTOLOGIA_PATH, format="turtle")
    g.parse(DADOS_PATH, format="turtle")
    DeductiveClosure(OWLRL_Semantics).expand(g)
    return g

def carregar_grafo_base():
    g = Graph()
    g.bind("acad", ACAD)
    g.parse(DADOS_PATH, format="turtle")
    return g

def guardar_grafo_base(g_base):
    g_base.bind("acad", ACAD)
    g_base.serialize(destination=DADOS_PATH, format="turtle")
    recarregar_memoria()

def recarregar_memoria():
    global grafo
    grafo = carregar_grafo()

def uri(local):
    return ACAD[local]

def local_id(valor):
    texto = str(valor)
    return texto.split("#")[-1] if "#" in texto else texto

def lit(sujeito, predicado):
    valor = grafo.value(sujeito, predicado)
    return str(valor) if valor is not None else None

def existe(recurso, classe=None):
    if classe is None:
        return any(grafo.triples((recurso, None, None)))
    return (recurso, RDF.type, classe) in grafo

def erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status

def remover_sujeito(g, s):
    g.remove((s, None, None))

def remover_objeto(g, o):
    g.remove((None, None, o))

grafo = carregar_grafo()

# ================================================================
#  DECORADORES DE AUTORIZAÇÃO
# ================================================================
def requer_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "email" not in session:
            return jsonify({"erro": "Autenticação necessária. Faça login primeiro."}), 401
        return f(*args, **kwargs)
    return wrapper

def requer_papel(*papeis):
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "email" not in session:
                return jsonify({"erro": "Autenticação necessária."}), 401
            papel_atual = session.get("papel")
            if papel_atual not in papeis:
                return jsonify({"erro": f"Acesso negado. Rota reservada a: {', '.join(papeis)}."}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorador

# ================================================================
#  AUTENTICAÇÃO
# ================================================================
@app.route('/auth/login', methods=['POST'])
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""
    utilizador = UTILIZADORES.get(email)
    if not utilizador or utilizador["senha"] != sha(senha):
        return jsonify({"erro": "Credenciais inválidas."}), 401
    session["email"] = email
    session["papel"] = utilizador["papel"]
    session["id_rdf"] = utilizador["id_rdf"]
    return jsonify({
        "mensagem": "Login efectuado com sucesso.",
        "email": email,
        "papel": utilizador["papel"],
        "id_rdf": utilizador["id_rdf"]
    })

@app.route('/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"mensagem": "Sessão terminada."})

@app.route('/auth/eu', methods=['GET'])
@requer_login
def quem_sou():
    return jsonify({
        "email": session["email"],
        "papel": session["papel"],
        "id_rdf": session.get("id_rdf")
    })

@app.route('/auth/cadastro', methods=['POST'])
def cadastro():
    """
    Cadastro público: cria conta de estudante + registo RDF.
    O docente ou admin pode cadastrar via /admin/utilizadores (futuro).
    """
    dados = request.get_json(silent=True) or {}
    for campo in ["email", "senha", "nome", "numero", "curso"]:
        if not dados.get(campo):
            return erro(f"Campo obrigatório em falta: '{campo}'")

    email = dados["email"].strip().lower()
    if email in UTILIZADORES:
        return erro("Email já registado.", 409)

    # Valida domínio institucional
    if not email.endswith("@iph.edu.ao") and not email.endswith("@umn.edu.ao"):
        return erro("Apenas emails institucionais (@iph.edu.ao ou @umn.edu.ao) são aceites.")

    # Gera ID RDF a partir do nome
    id_rdf = dados["nome"].split()[0].capitalize() + dados["nome"].split()[-1].capitalize()
    id_rdf = ''.join(c for c in id_rdf if c.isalnum())

    curso = uri(dados["curso"])
    if not existe(curso, ACAD.Curso):
        return erro(f"Curso '{dados['curso']}' não existe.", 404)

    novo = uri(id_rdf)
    if any(grafo.triples((novo, None, None))):
        id_rdf = id_rdf + "2"
        novo = uri(id_rdf)

    tipo = ACAD.EstudanteBolseiro if dados.get("valor_bolsa") not in (None, "") else ACAD.Estudante
    g_base = carregar_grafo_base()
    g_base.add((novo, RDF.type, tipo))
    g_base.add((novo, ACAD.temNome, Literal(dados["nome"], datatype=XSD.string)))
    g_base.add((novo, ACAD.temNumeroEstudante, Literal(dados["numero"], datatype=XSD.string)))
    g_base.add((novo, ACAD.temEmail, Literal(email, datatype=XSD.string)))
    g_base.add((novo, ACAD.estaMatriculadoEm, curso))
    if tipo == ACAD.EstudanteBolseiro:
        g_base.add((novo, ACAD.temValorBolsa, Literal(float(dados["valor_bolsa"]), datatype=XSD.decimal)))
        g_base.add((novo, ACAD.temMoedaBolsa, Literal("AOA", datatype=XSD.string)))
    guardar_grafo_base(g_base)

    UTILIZADORES[email] = {
        "senha": sha(dados["senha"]),
        "papel": "estudante",
        "id_rdf": id_rdf
    }
    return jsonify({"mensagem": "Cadastro efectuado com sucesso.", "id_rdf": id_rdf}), 201

# ================================================================
#  SERIALIZAÇÃO JSON
# ================================================================
def estudante_json(estudante):
    curso = grafo.value(estudante, ACAD.estaMatriculadoEm)
    curso_nome = grafo.value(curso, ACAD.temNomeCurso) if curso else None
    bolsa = grafo.value(estudante, ACAD.temValorBolsa)
    moeda = grafo.value(estudante, ACAD.temMoedaBolsa)
    reprovado = any(
        (av, ACAD.estaReprovado, Literal(True)) in grafo
        for av in grafo.objects(estudante, ACAD.temAvaliacao)
    )
    return {
        "id": local_id(estudante),
        "nome": lit(estudante, ACAD.temNome),
        "email": lit(estudante, ACAD.temEmail),
        "numero": lit(estudante, ACAD.temNumeroEstudante),
        "curso_id": local_id(curso) if curso else None,
        "curso": str(curso_nome) if curso_nome else None,
        "bolseiro": (estudante, RDF.type, ACAD.EstudanteBolseiro) in grafo,
        "valor_bolsa": float(bolsa) if bolsa is not None else None,
        "moeda_bolsa": str(moeda) if moeda else "AOA",
        "tem_reprovacao": reprovado,
    }

def avaliacao_json(avaliacao):
    estudante = grafo.value(avaliacao, ACAD.avaliacaoDe)
    disciplina = grafo.value(avaliacao, ACAD.avaliaDisciplina)
    nota = grafo.value(avaliacao, ACAD.temNota)
    data = grafo.value(avaliacao, ACAD.temData)
    reprovado_val = grafo.value(avaliacao, ACAD.estaReprovado)
    nota_float = float(nota) if nota is not None else None
    return {
        "id": local_id(avaliacao),
        "estudante_id": local_id(estudante) if estudante else None,
        "estudante": lit(estudante, ACAD.temNome) if estudante else None,
        "disciplina_id": local_id(disciplina) if disciplina else None,
        "disciplina": str(grafo.value(disciplina, RDFS.label)) if disciplina else None,
        "nota": nota_float,
        "situacao": "Reprovado" if (nota_float is not None and nota_float < 10) else "Aprovado" if nota_float is not None else None,
        "data": str(data) if data is not None else None,
    }

def docente_json(docente):
    dep = grafo.value(docente, ACAD.trabalhaEm)
    disciplinas = [
        {"id": local_id(d), "nome": str(grafo.value(d, RDFS.label) or "")}
        for d in grafo.objects(docente, ACAD.leciona)
    ]
    return {
        "id": local_id(docente),
        "nome": lit(docente, ACAD.temNome),
        "email": lit(docente, ACAD.temEmail),
        "departamento_id": local_id(dep) if dep else None,
        "departamento": str(grafo.value(dep, RDFS.label)) if dep else None,
        "disciplinas": sorted(disciplinas, key=lambda x: x["nome"]),
    }

def disciplina_json(disc):
    curso = grafo.value(disc, ACAD.pertenceA)
    docente = grafo.value(disc, ACAD.leccionadaPor)
    prereqs = [
        {"id": local_id(p), "nome": str(grafo.value(p, RDFS.label) or "")}
        for p in grafo.objects(disc, ACAD.requerPreRequisito)
    ]
    return {
        "id": local_id(disc),
        "nome": str(grafo.value(disc, RDFS.label) or ""),
        "codigo": lit(disc, ACAD.temCodigo),
        "carga_horaria": int(grafo.value(disc, ACAD.temCargaHoraria) or 0),
        "curso_id": local_id(curso) if curso else None,
        "curso": str(grafo.value(curso, ACAD.temNomeCurso)) if curso else None,
        "docente_id": local_id(docente) if docente else None,
        "docente": lit(docente, ACAD.temNome) if docente else None,
        "prerequisitos": prereqs,
    }

# ================================================================
#  ROTAS PÚBLICAS
# ================================================================
@app.route('/', methods=['GET'])
def inicio():
    return jsonify({
        "sistema": "API Academia RDF — IPH/UMN Angola",
        "versao": "3.0",
        "autenticacao": {
            "POST /auth/login":   "Login (email + senha)",
            "POST /auth/logout":  "Terminar sessão",
            "POST /auth/cadastro":"Cadastro de estudante",
            "GET  /auth/eu":      "Utilizador autenticado",
        },
        "estudante": {
            "GET /minha-area":             "Perfil e notas do estudante autenticado",
            "GET /minhas-avaliacoes":      "Avaliações pessoais",
            "GET /meus-colegas":           "Colegas (simetria OWL)",
        },
        "docente": {
            "GET  /minhas-disciplinas":    "Disciplinas leccionadas",
            "GET  /turma/<disc_id>":       "Estudantes da turma",
            "POST /avaliacoes":            "Lançar avaliação",
            "PUT  /avaliacoes/<id>":       "Editar avaliação",
            "DELETE /avaliacoes/<id>":     "Eliminar avaliação",
        },
        "publico": {
            "GET /estudantes":             "Listar estudantes",
            "GET /docentes":               "Listar docentes",
            "GET /disciplinas":            "Listar disciplinas",
            "GET /bolseiros":              "Bolseiros (AOA)",
            "GET /avaliacoes":             "Todas as avaliações",
            "GET /api/semantica/prerequisitos/<id>": "Pré-requisitos (OWL transitivo)",
            "GET /api/semantica/elegiveis/<id>":     "Estudantes elegíveis",
            "GET /api/semantica/estatisticas":       "Estatísticas SPARQL",
        },
        "admin": {
            "GET  /admin/resumo":          "Resumo institucional",
            "POST /admin/utilizadores":    "Criar conta docente/admin",
            "CRUD /admin/departamentos":   "Gerir departamentos",
            "CRUD /admin/cursos":          "Gerir cursos",
            "CRUD /admin/docentes":        "Gerir docentes",
            "CRUD /admin/disciplinas":     "Gerir disciplinas",
        }
    })

# ================================================================
#  ÁREA DO ESTUDANTE (só o próprio)
# ================================================================
@app.route('/minha-area', methods=['GET'])
@requer_papel("estudante")
def minha_area():
    id_rdf = session["id_rdf"]
    estudante = uri(id_rdf)
    if not existe(estudante, ACAD.Estudante):
        return erro("Perfil RDF não encontrado.", 404)
    perfil = estudante_json(estudante)
    # notas pessoais
    avaliacoes = [
        avaliacao_json(av)
        for av in grafo.objects(estudante, ACAD.temAvaliacao)
    ]
    perfil["avaliacoes"] = sorted(avaliacoes, key=lambda x: x.get("data") or "")
    return jsonify(perfil)

@app.route('/minhas-avaliacoes', methods=['GET'])
@requer_papel("estudante")
def minhas_avaliacoes():
    estudante = uri(session["id_rdf"])
    avaliacoes = [avaliacao_json(av) for av in grafo.objects(estudante, ACAD.temAvaliacao)]
    return jsonify(sorted(avaliacoes, key=lambda x: x.get("data") or ""))

@app.route('/meus-colegas', methods=['GET'])
@requer_papel("estudante")
def meus_colegas():
    estudante = uri(session["id_rdf"])
    colegas = [
        {"id": local_id(c), "nome": lit(c, ACAD.temNome), "email": lit(c, ACAD.temEmail)}
        for c in grafo.objects(estudante, ACAD.colegaDe)
    ]
    return jsonify({"estudante": session["id_rdf"], "colegas": colegas, "total": len(colegas)})

# ================================================================
#  ÁREA DO DOCENTE
# ================================================================
@app.route('/minhas-disciplinas', methods=['GET'])
@requer_papel("docente", "admin")
def minhas_disciplinas():
    if session["papel"] == "admin":
        # admin vê tudo
        query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?disc WHERE { ?disc a :Disciplina . } ORDER BY ?disc"
        return jsonify([disciplina_json(r.disc) for r in grafo.query(query)])
    docente = uri(session["id_rdf"])
    disciplinas = [disciplina_json(d) for d in grafo.objects(docente, ACAD.leciona)]
    return jsonify(sorted(disciplinas, key=lambda x: x.get("nome") or ""))

@app.route('/turma/<disciplina_id>', methods=['GET'])
@requer_papel("docente", "admin")
def turma(disciplina_id):
    disc = uri(disciplina_id)
    if not existe(disc, ACAD.Disciplina):
        return erro("Disciplina não encontrada.", 404)
    # Verificar se docente leciona esta disciplina (admin bypassa)
    if session["papel"] == "docente":
        docente = uri(session["id_rdf"])
        if (docente, ACAD.leciona, disc) not in grafo:
            return erro("Não lecciona esta disciplina.", 403)
    estudantes = [
        estudante_json(e)
        for e in grafo.subjects(ACAD.frequenta, disc)
        if (e, RDF.type, ACAD.Estudante) in grafo
    ]
    return jsonify({
        "disciplina_id": disciplina_id,
        "disciplina": str(grafo.value(disc, RDFS.label) or ""),
        "estudantes": sorted(estudantes, key=lambda x: x.get("nome") or ""),
        "total": len(estudantes)
    })

# ================================================================
#  AVALIAÇÕES (docente lança; estudante só lê as suas)
# ================================================================
@app.route('/avaliacoes', methods=['POST'])
@requer_papel("docente", "admin")
def criar_avaliacao():
    dados = request.get_json(silent=True) or {}
    for campo in ["id", "estudante", "disciplina", "nota", "data"]:
        if dados.get(campo) in (None, ""):
            return erro(f"Campo obrigatório em falta: '{campo}'")
    av = uri(dados["id"])
    if existe(av):
        return erro("ID de avaliação já existe.", 409)
    estudante = uri(dados["estudante"])
    disc = uri(dados["disciplina"])
    if not existe(estudante, ACAD.Estudante):
        return erro("Estudante não encontrado.", 404)
    if not existe(disc, ACAD.Disciplina):
        return erro("Disciplina não encontrada.", 404)
    # Docente só lança notas nas suas disciplinas
    if session["papel"] == "docente":
        docente = uri(session["id_rdf"])
        if (docente, ACAD.leciona, disc) not in grafo:
            return erro("Apenas pode lançar notas nas disciplinas que lecciona.", 403)
    nota = float(dados["nota"])
    g_base = carregar_grafo_base()
    g_base.add((av, RDF.type, ACAD.Avaliacao))
    g_base.add((av, ACAD.avaliacaoDe, estudante))
    g_base.add((av, ACAD.avaliaDisciplina, disc))
    g_base.add((av, ACAD.temNota, Literal(nota, datatype=XSD.decimal)))
    g_base.add((av, ACAD.temData, Literal(dados["data"], datatype=XSD.date)))
    g_base.add((estudante, ACAD.temAvaliacao, av))
    if nota < 10:
        g_base.add((av, ACAD.estaReprovado, Literal(True)))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Avaliação criada.", "id": dados["id"], "situacao": "Reprovado" if nota < 10 else "Aprovado"}), 201

@app.route('/avaliacoes', methods=['GET'])
@requer_login
def listar_avaliacoes():
    papel = session["papel"]
    if papel == "estudante":
        estudante = uri(session["id_rdf"])
        avaliacoes = [avaliacao_json(av) for av in grafo.objects(estudante, ACAD.temAvaliacao)]
    else:
        query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?av WHERE { ?av a :Avaliacao . } ORDER BY ?av"
        avaliacoes = [avaliacao_json(r.av) for r in grafo.query(query)]
    return jsonify(sorted(avaliacoes, key=lambda x: x.get("data") or ""))

@app.route('/avaliacoes/<av_id>', methods=['PUT'])
@requer_papel("docente", "admin")
def editar_avaliacao(av_id):
    av = uri(av_id)
    if not existe(av, ACAD.Avaliacao):
        return erro("Avaliação não encontrada.", 404)
    dados = request.get_json(silent=True) or {}
    g_base = carregar_grafo_base()
    if "nota" in dados:
        nota = float(dados["nota"])
        g_base.remove((av, ACAD.temNota, None))
        g_base.remove((av, ACAD.estaReprovado, None))
        g_base.add((av, ACAD.temNota, Literal(nota, datatype=XSD.decimal)))
        if nota < 10:
            g_base.add((av, ACAD.estaReprovado, Literal(True)))
    if "data" in dados:
        g_base.remove((av, ACAD.temData, None))
        g_base.add((av, ACAD.temData, Literal(dados["data"], datatype=XSD.date)))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Avaliação actualizada.", "id": av_id})

@app.route('/avaliacoes/<av_id>', methods=['DELETE'])
@requer_papel("docente", "admin")
def eliminar_avaliacao(av_id):
    av = uri(av_id)
    if not existe(av, ACAD.Avaliacao):
        return erro("Avaliação não encontrada.", 404)
    g_base = carregar_grafo_base()
    g_base.remove((None, ACAD.temAvaliacao, av))
    remover_sujeito(g_base, av)
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Avaliação eliminada.", "id": av_id})

# ================================================================
#  CONSULTAS PÚBLICAS
# ================================================================
@app.route('/estudantes', methods=['GET'])
def listar_estudantes():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?est WHERE { ?est a :Estudante . } ORDER BY ?est"
    lista = [estudante_json(r.est) for r in grafo.query(query)]
    return jsonify(sorted(lista, key=lambda x: x.get("nome") or ""))

@app.route('/estudantes/<est_id>', methods=['GET'])
def detalhe_estudante(est_id):
    est = uri(est_id)
    if not existe(est, ACAD.Estudante):
        return erro("Estudante não encontrado.", 404)
    dados = estudante_json(est)
    dados["avaliacoes"] = [avaliacao_json(av) for av in grafo.objects(est, ACAD.temAvaliacao)]
    return jsonify(dados)

@app.route('/docentes', methods=['GET'])
def listar_docentes():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?doc WHERE { ?doc a :Docente . } ORDER BY ?doc"
    lista = [docente_json(r.doc) for r in grafo.query(query)]
    return jsonify(sorted(lista, key=lambda x: x.get("nome") or ""))

@app.route('/disciplinas', methods=['GET'])
def listar_disciplinas():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?disc WHERE { ?disc a :Disciplina . } ORDER BY ?disc"
    return jsonify(sorted([disciplina_json(r.disc) for r in grafo.query(query)], key=lambda x: x.get("codigo") or ""))

@app.route('/bolseiros', methods=['GET'])
def listar_bolseiros():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?est WHERE { ?est a :EstudanteBolseiro . } ORDER BY ?est"
    lista = [estudante_json(r.est) for r in grafo.query(query)]
    return jsonify(sorted(lista, key=lambda x: x.get("nome") or ""))

@app.route('/estudantes/<est_id>/colegas', methods=['GET'])
def colegas_estudante(est_id):
    est = uri(est_id)
    if not existe(est, ACAD.Estudante):
        return erro("Estudante não encontrado.", 404)
    colegas = [
        {"id": local_id(c), "nome": lit(c, ACAD.temNome)}
        for c in grafo.objects(est, ACAD.colegaDe)
    ]
    return jsonify({"estudante": est_id, "colegas": colegas})

# ================================================================
#  SEMÂNTICA OWL / SPARQL
# ================================================================
@app.route('/api/semantica/prerequisitos/<disciplina_id>', methods=['GET'])
def prerequisitos_disciplina(disciplina_id):
    query = f"""
    PREFIX : <http://exemplo.org/academia#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?disciplina ?nomeDisciplina WHERE {{
        :{disciplina_id} :requerPreRequisito ?disciplina .
        ?disciplina rdfs:label ?nomeDisciplina .
    }} ORDER BY ?nomeDisciplina
    """
    prereqs = [{"id": local_id(r.disciplina), "nome": str(r.nomeDisciplina)} for r in grafo.query(query)]
    return jsonify({
        "disciplina": disciplina_id,
        "prerequisitos": prereqs,
        "nota": "Inclui pré-requisitos inferidos via transitividade OWL-RL"
    })

@app.route('/api/semantica/elegiveis/<disciplina_id>', methods=['GET'])
def estudantes_elegiveis(disciplina_id):
    query = f"""
    PREFIX : <http://exemplo.org/academia#>
    SELECT DISTINCT ?estudante ?nomeEstudante WHERE {{
        ?estudante a :Estudante ; :temNome ?nomeEstudante .
        FILTER EXISTS {{ :{disciplina_id} :requerPreRequisito ?algumPre . }}
        FILTER NOT EXISTS {{
            :{disciplina_id} :requerPreRequisito ?preObrigatorio .
            FILTER NOT EXISTS {{ ?estudante :frequenta ?preObrigatorio . }}
        }}
        FILTER NOT EXISTS {{ ?estudante :frequenta :{disciplina_id} }}
    }} ORDER BY ?nomeEstudante
    """
    elegiveis = [{"id": local_id(r.estudante), "nome": str(r.nomeEstudante)} for r in grafo.query(query)]
    return jsonify({
        "disciplina": disciplina_id,
        "estudantes": elegiveis,
        "total": len(elegiveis),
        "explicacao": "Cumprem todos os pré-requisitos inferidos e ainda não frequentam a disciplina."
    })

@app.route('/api/semantica/estatisticas', methods=['GET'])
def estatisticas_disciplinas():
    query = """
    PREFIX : <http://exemplo.org/academia#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?nomeDisciplina ?nomeDocente (AVG(?nota) AS ?media) (COUNT(?av) AS ?total) WHERE {
        ?av a :Avaliacao ; :avaliaDisciplina ?disc ; :temNota ?nota .
        ?disc rdfs:label ?nomeDisciplina .
        OPTIONAL { ?disc :leccionadaPor ?doc . ?doc :temNome ?nomeDocente . }
    } GROUP BY ?nomeDisciplina ?nomeDocente ORDER BY DESC(?media)
    """
    return jsonify([{
        "disciplina": str(r.nomeDisciplina),
        "docente": str(r.nomeDocente) if r.nomeDocente else None,
        "media": round(float(r.media), 2),
        "total_avaliacoes": int(r.total)
    } for r in grafo.query(query)])

@app.route('/api/semantica/reprovados', methods=['GET'])
def estudantes_reprovados():
    """Estudantes com pelo menos uma reprovação (nota < 10)."""
    query = """
    PREFIX : <http://exemplo.org/academia#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?est ?nome ?disc ?nomedisc ?nota WHERE {
        ?av a :Avaliacao ; :avaliacaoDe ?est ; :avaliaDisciplina ?disc ; :temNota ?nota .
        ?est :temNome ?nome .
        ?disc rdfs:label ?nomedisc .
        FILTER(?nota < 10)
    } ORDER BY ?nome
    """
    resultados = [{
        "estudante": str(r.nome),
        "disciplina": str(r.nomedisc),
        "nota": float(r.nota),
        "situacao": "Reprovado"
    } for r in grafo.query(query)]
    return jsonify({"reprovados": resultados, "total": len(resultados)})

# ================================================================
#  ADMINISTRAÇÃO
# ================================================================
@app.route('/admin/resumo', methods=['GET'])
@requer_papel("admin")
def resumo_admin():
    bolseiros = list(grafo.subjects(RDF.type, ACAD.EstudanteBolseiro))
    return jsonify({
        "instituicao": "Instituto Politécnico da Huíla (IPH / UMN)",
        "departamentos": len(set(grafo.subjects(RDF.type, ACAD.Departamento))),
        "cursos": len(set(grafo.subjects(RDF.type, ACAD.Curso))),
        "disciplinas": len(set(grafo.subjects(RDF.type, ACAD.Disciplina))),
        "docentes": len(set(grafo.subjects(RDF.type, ACAD.Docente))),
        "estudantes": len(set(grafo.subjects(RDF.type, ACAD.Estudante))),
        "bolseiros": len(bolseiros),
        "avaliacoes": len(set(grafo.subjects(RDF.type, ACAD.Avaliacao))),
        "total_triplas": len(grafo),
    })

@app.route('/admin/utilizadores', methods=['POST'])
@requer_papel("admin")
def criar_utilizador():
    """Admin cria conta para docente ou outro admin."""
    dados = request.get_json(silent=True) or {}
    for campo in ["email", "senha", "papel", "id_rdf"]:
        if not dados.get(campo):
            return erro(f"Campo obrigatório: '{campo}'")
    if dados["papel"] not in ("docente", "admin", "estudante"):
        return erro("Papel inválido. Use: estudante, docente ou admin.")
    email = dados["email"].strip().lower()
    if email in UTILIZADORES:
        return erro("Email já registado.", 409)
    UTILIZADORES[email] = {
        "senha": sha(dados["senha"]),
        "papel": dados["papel"],
        "id_rdf": dados["id_rdf"]
    }
    return jsonify({"mensagem": f"Utilizador '{email}' criado com papel '{dados['papel']}'."}), 201

@app.route('/admin/departamentos', methods=['GET'])
@requer_papel("admin")
def listar_departamentos():
    query = "PREFIX : <http://exemplo.org/academia#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT DISTINCT ?dep ?sigla ?label WHERE { ?dep a :Departamento ; :temSigla ?sigla . OPTIONAL { ?dep rdfs:label ?label . } } ORDER BY ?sigla"
    return jsonify([{
        "id": local_id(r.dep),
        "sigla": str(r.sigla),
        "nome": str(r.label) if r.label else str(r.sigla)
    } for r in grafo.query(query)])

@app.route('/admin/departamentos', methods=['POST'])
@requer_papel("admin")
def criar_departamento():
    dados = request.get_json(silent=True) or {}
    for campo in ["id", "sigla", "nome"]:
        if not dados.get(campo):
            return erro(f"Campo obrigatório: '{campo}'")
    dep = uri(dados["id"])
    if existe(dep):
        return erro("Departamento já existe.", 409)
    g_base = carregar_grafo_base()
    g_base.add((dep, RDF.type, ACAD.Departamento))
    g_base.add((dep, ACAD.temSigla, Literal(dados["sigla"], datatype=XSD.string)))
    g_base.add((dep, RDFS.label, Literal(dados["nome"], datatype=XSD.string)))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Departamento criado.", "id": dados["id"]}), 201

@app.route('/admin/departamentos/<dep_id>', methods=['PUT'])
@requer_papel("admin")
def editar_departamento(dep_id):
    dep = uri(dep_id)
    if not existe(dep, ACAD.Departamento):
        return erro("Departamento não encontrado.", 404)
    dados = request.get_json(silent=True) or {}
    g_base = carregar_grafo_base()
    if dados.get("sigla"):
        g_base.remove((dep, ACAD.temSigla, None))
        g_base.add((dep, ACAD.temSigla, Literal(dados["sigla"], datatype=XSD.string)))
    if dados.get("nome"):
        g_base.remove((dep, RDFS.label, None))
        g_base.add((dep, RDFS.label, Literal(dados["nome"], datatype=XSD.string)))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Departamento actualizado.", "id": dep_id})

@app.route('/admin/departamentos/<dep_id>', methods=['DELETE'])
@requer_papel("admin")
def eliminar_departamento(dep_id):
    dep = uri(dep_id)
    if not existe(dep, ACAD.Departamento):
        return erro("Departamento não encontrado.", 404)
    if any(grafo.subjects(ACAD.pertenceDepartamento, dep)):
        return erro("Não é possível eliminar: existem cursos associados.", 409)
    g_base = carregar_grafo_base()
    remover_sujeito(g_base, dep)
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Departamento eliminado.", "id": dep_id})

@app.route('/admin/cursos', methods=['GET'])
@requer_papel("admin", "docente")
def listar_cursos():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?c WHERE { ?c a :Curso . } ORDER BY ?c"
    return jsonify([{
        "id": local_id(r.c),
        "nome": str(grafo.value(r.c, ACAD.temNomeCurso) or ""),
        "departamento_id": local_id(grafo.value(r.c, ACAD.pertenceDepartamento)) if grafo.value(r.c, ACAD.pertenceDepartamento) else None,
    } for r in grafo.query(query)])

@app.route('/admin/cursos', methods=['POST'])
@requer_papel("admin")
def criar_curso():
    dados = request.get_json(silent=True) or {}
    for campo in ["id", "nome", "departamento"]:
        if not dados.get(campo):
            return erro(f"Campo obrigatório: '{campo}'")
    curso = uri(dados["id"])
    dep = uri(dados["departamento"])
    if existe(curso, ACAD.Curso):
        return erro("Curso já existe.", 409)
    if not existe(dep, ACAD.Departamento):
        return erro("Departamento não encontrado.", 404)
    g_base = carregar_grafo_base()
    g_base.add((curso, RDF.type, ACAD.Curso))
    g_base.add((curso, ACAD.temNomeCurso, Literal(dados["nome"], datatype=XSD.string)))
    g_base.add((curso, ACAD.pertenceDepartamento, dep))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Curso criado.", "id": dados["id"]}), 201

@app.route('/admin/cursos/<curso_id>', methods=['PUT'])
@requer_papel("admin")
def editar_curso(curso_id):
    curso = uri(curso_id)
    if not existe(curso, ACAD.Curso):
        return erro("Curso não encontrado.", 404)
    dados = request.get_json(silent=True) or {}
    g_base = carregar_grafo_base()
    if dados.get("nome"):
        g_base.remove((curso, ACAD.temNomeCurso, None))
        g_base.add((curso, ACAD.temNomeCurso, Literal(dados["nome"], datatype=XSD.string)))
    if dados.get("departamento"):
        dep = uri(dados["departamento"])
        if existe(dep, ACAD.Departamento):
            g_base.remove((curso, ACAD.pertenceDepartamento, None))
            g_base.add((curso, ACAD.pertenceDepartamento, dep))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Curso actualizado.", "id": curso_id})

@app.route('/admin/cursos/<curso_id>', methods=['DELETE'])
@requer_papel("admin")
def eliminar_curso(curso_id):
    curso = uri(curso_id)
    if not existe(curso, ACAD.Curso):
        return erro("Curso não encontrado.", 404)
    if any(grafo.subjects(ACAD.estaMatriculadoEm, curso)):
        return erro("Não é possível eliminar: existem estudantes matriculados.", 409)
    g_base = carregar_grafo_base()
    remover_sujeito(g_base, curso)
    remover_objeto(g_base, curso)
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Curso eliminado.", "id": curso_id})

@app.route('/admin/docentes', methods=['GET'])
@requer_papel("admin")
def listar_docentes_admin():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?doc WHERE { ?doc a :Docente . } ORDER BY ?doc"
    return jsonify([docente_json(r.doc) for r in grafo.query(query)])

@app.route('/admin/docentes', methods=['POST'])
@requer_papel("admin")
def criar_docente():
    dados = request.get_json(silent=True) or {}
    for campo in ["id", "nome", "email", "departamento"]:
        if not dados.get(campo):
            return erro(f"Campo obrigatório: '{campo}'")
    doc = uri(dados["id"])
    dep = uri(dados["departamento"])
    if existe(doc, ACAD.Docente):
        return erro("Docente já existe.", 409)
    if not existe(dep, ACAD.Departamento):
        return erro("Departamento não encontrado.", 404)
    g_base = carregar_grafo_base()
    g_base.add((doc, RDF.type, ACAD.Docente))
    g_base.add((doc, ACAD.temNome, Literal(dados["nome"], datatype=XSD.string)))
    g_base.add((doc, ACAD.temEmail, Literal(dados["email"], datatype=XSD.string)))
    g_base.add((doc, ACAD.trabalhaEm, dep))
    for disc_id in dados.get("disciplinas", []):
        disc = uri(disc_id)
        if existe(disc, ACAD.Disciplina):
            g_base.add((doc, ACAD.leciona, disc))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Docente criado.", "id": dados["id"]}), 201

@app.route('/admin/docentes/<doc_id>', methods=['PUT'])
@requer_papel("admin")
def editar_docente(doc_id):
    doc = uri(doc_id)
    if not existe(doc, ACAD.Docente):
        return erro("Docente não encontrado.", 404)
    dados = request.get_json(silent=True) or {}
    g_base = carregar_grafo_base()
    for pred in [ACAD.temNome, ACAD.temEmail, ACAD.trabalhaEm, ACAD.leciona]:
        g_base.remove((doc, pred, None))
    dep = uri(dados.get("departamento") or local_id(grafo.value(doc, ACAD.trabalhaEm)))
    g_base.add((doc, ACAD.temNome, Literal(dados.get("nome") or lit(doc, ACAD.temNome), datatype=XSD.string)))
    g_base.add((doc, ACAD.temEmail, Literal(dados.get("email") or lit(doc, ACAD.temEmail), datatype=XSD.string)))
    g_base.add((doc, ACAD.trabalhaEm, dep))
    for disc_id in dados.get("disciplinas", []):
        disc = uri(disc_id)
        if existe(disc, ACAD.Disciplina):
            g_base.add((doc, ACAD.leciona, disc))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Docente actualizado.", "id": doc_id})

@app.route('/admin/docentes/<doc_id>', methods=['DELETE'])
@requer_papel("admin")
def eliminar_docente(doc_id):
    doc = uri(doc_id)
    if not existe(doc, ACAD.Docente):
        return erro("Docente não encontrado.", 404)
    g_base = carregar_grafo_base()
    remover_sujeito(g_base, doc)
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Docente eliminado.", "id": doc_id})

@app.route('/admin/disciplinas', methods=['GET'])
@requer_papel("admin", "docente")
def listar_disciplinas_admin():
    query = "PREFIX : <http://exemplo.org/academia#> SELECT DISTINCT ?disc WHERE { ?disc a :Disciplina . } ORDER BY ?disc"
    return jsonify(sorted([disciplina_json(r.disc) for r in grafo.query(query)], key=lambda x: x.get("codigo") or ""))

@app.route('/admin/disciplinas', methods=['POST'])
@requer_papel("admin")
def criar_disciplina():
    dados = request.get_json(silent=True) or {}
    for campo in ["id", "codigo", "nome", "carga_horaria", "curso"]:
        if dados.get(campo) in (None, ""):
            return erro(f"Campo obrigatório: '{campo}'")
    disc = uri(dados["id"])
    curso = uri(dados["curso"])
    if existe(disc, ACAD.Disciplina):
        return erro("Disciplina já existe.", 409)
    if not existe(curso, ACAD.Curso):
        return erro("Curso não encontrado.", 404)
    g_base = carregar_grafo_base()
    g_base.add((disc, RDF.type, ACAD.Disciplina))
    g_base.add((disc, ACAD.temCodigo, Literal(dados["codigo"], datatype=XSD.string)))
    g_base.add((disc, ACAD.temCargaHoraria, Literal(int(dados["carga_horaria"]), datatype=XSD.integer)))
    g_base.add((disc, RDFS.label, Literal(dados["nome"], datatype=XSD.string)))
    g_base.add((disc, ACAD.pertenceA, curso))
    if dados.get("docente"):
        doc = uri(dados["docente"])
        if existe(doc, ACAD.Docente):
            g_base.add((doc, ACAD.leciona, disc))
    for pre_id in dados.get("prerequisitos", []):
        pre = uri(pre_id)
        if existe(pre, ACAD.Disciplina) and pre != disc:
            g_base.add((disc, ACAD.requerPreRequisito, pre))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Disciplina criada.", "id": dados["id"]}), 201

@app.route('/admin/disciplinas/<disc_id>', methods=['PUT'])
@requer_papel("admin")
def editar_disciplina(disc_id):
    disc = uri(disc_id)
    if not existe(disc, ACAD.Disciplina):
        return erro("Disciplina não encontrada.", 404)
    dados = request.get_json(silent=True) or {}
    curso = uri(dados.get("curso") or local_id(grafo.value(disc, ACAD.pertenceA)))
    if not existe(curso, ACAD.Curso):
        return erro("Curso não encontrado.", 404)
    g_base = carregar_grafo_base()
    for pred in [ACAD.temCodigo, ACAD.temCargaHoraria, RDFS.label, ACAD.pertenceA, ACAD.requerPreRequisito]:
        g_base.remove((disc, pred, None))
    g_base.remove((None, ACAD.leciona, disc))
    g_base.add((disc, ACAD.temCodigo, Literal(dados.get("codigo") or lit(disc, ACAD.temCodigo), datatype=XSD.string)))
    g_base.add((disc, ACAD.temCargaHoraria, Literal(int(dados.get("carga_horaria") or grafo.value(disc, ACAD.temCargaHoraria)), datatype=XSD.integer)))
    g_base.add((disc, RDFS.label, Literal(dados.get("nome") or str(grafo.value(disc, RDFS.label) or ""), datatype=XSD.string)))
    g_base.add((disc, ACAD.pertenceA, curso))
    if dados.get("docente"):
        doc = uri(dados["docente"])
        if existe(doc, ACAD.Docente):
            g_base.add((doc, ACAD.leciona, disc))
    for pre_id in dados.get("prerequisitos", []):
        pre = uri(pre_id)
        if existe(pre, ACAD.Disciplina) and pre != disc:
            g_base.add((disc, ACAD.requerPreRequisito, pre))
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Disciplina actualizada.", "id": disc_id})

@app.route('/admin/disciplinas/<disc_id>', methods=['DELETE'])
@requer_papel("admin")
def eliminar_disciplina(disc_id):
    disc = uri(disc_id)
    if not existe(disc, ACAD.Disciplina):
        return erro("Disciplina não encontrada.", 404)
    if any(grafo.triples((None, ACAD.frequenta, disc))) or any(grafo.triples((None, ACAD.avaliaDisciplina, disc))):
        return erro("Não é possível eliminar: disciplina tem estudantes ou avaliações associadas.", 409)
    g_base = carregar_grafo_base()
    remover_sujeito(g_base, disc)
    remover_objeto(g_base, disc)
    guardar_grafo_base(g_base)
    return jsonify({"mensagem": "Disciplina eliminada.", "id": disc_id})

@app.route('/api/sistema/recarregar', methods=['POST'])
@requer_papel("admin")
def recarregar_grafo():
    recarregar_memoria()
    return jsonify({"mensagem": "Grafo recarregado e inferência reaplicada.", "total_triplas": len(grafo)})

# ================================================================
#  ERROS
# ================================================================
@app.errorhandler(404)
def nao_encontrado(e):
    return jsonify({"erro": "Rota não encontrada.", "dica": "Aceda a GET / para ver os endpoints."}), 404

@app.errorhandler(405)
def metodo_nao_permitido(e):
    return jsonify({"erro": "Método HTTP não permitido nesta rota."}), 405

@app.errorhandler(500)
def erro_interno(e):
    return jsonify({"erro": "Erro interno do servidor.", "detalhe": str(e)}), 500

if __name__ == '__main__':
    print(f"[IPH/UMN] Grafo carregado: {len(grafo)} triplas (incluindo inferidas).")
   # print("Utilizadores de teste:")
    #print("  Estudante : joao.luvumba@iph.edu.ao / joao123")
    #print("  Docente   : csilva@iph.edu.ao / csilva123")
    #print("  Admin     : admin@iph.edu.ao / admin2025")
    app.run(debug=True, port=5000)