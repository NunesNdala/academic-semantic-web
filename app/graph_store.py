"""
graph_store.py

Módulo responsável por carregar, manter e persistir o grafo RDF
(ontologia + instâncias), e fornecer operações CRUD básicas sobre
estudantes, UCs, docentes e avaliações, além de execução de consultas
SPARQL.
"""

import os
import threading
from rdflib import Graph, Namespace, RDF, XSD, Literal, URIRef

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ONTOLOGY_PATH = os.path.join(BASE_DIR, "ontology", "academic.ttl")
DATA_PATH = os.path.join(BASE_DIR, "data", "instances.ttl")

ACAD = Namespace("http://www.example.org/academic#")

_lock = threading.Lock()


class GraphStore:
    """Encapsula o grafo RDF em memória, com persistência em ficheiro .ttl"""

    def __init__(self):
        self.graph = Graph()
        self.graph.bind("academic", ACAD)
        self._load()

    def _load(self):
        self.graph.parse(ONTOLOGY_PATH, format="turtle")
        self.graph.parse(DATA_PATH, format="turtle")

    def save(self):
        """Persiste apenas os dados de instâncias (não a ontologia) em data/instances.ttl"""
        instance_graph = Graph()
        instance_graph.bind("academic", ACAD)

        # Re-serializa apenas os triplos cujo sujeito não pertence à definição da ontologia
        ontology_graph = Graph()
        ontology_graph.parse(ONTOLOGY_PATH, format="turtle")
        ontology_subjects = set(ontology_graph.subjects())

        for s, p, o in self.graph:
            if s not in ontology_subjects:
                instance_graph.add((s, p, o))

        with _lock:
            instance_graph.serialize(destination=DATA_PATH, format="turtle")

    def query(self, sparql_query):
        """Executa uma consulta SPARQL (SELECT/ASK) e devolve resultados como lista de dicts."""
        results = self.graph.query(sparql_query)
        rows = []
        for row in results:
            row_dict = {}
            for var in results.vars:
                value = row[var]
                if value is None:
                    row_dict[str(var)] = None
                else:
                    row_dict[str(var)] = str(value)
            rows.append(row_dict)
        return rows

    # ------------------------------------------------------------------
    # CRUD: Estudantes
    # ------------------------------------------------------------------

    def list_estudantes(self):
        q = """
        PREFIX : <http://www.example.org/academic#>
        SELECT ?estudante ?nome ?email ?numero ?curso
        WHERE {
            ?estudante a :Estudante ;
                       :temNome ?nome ;
                       :numeroAluno ?numero .
            OPTIONAL { ?estudante :temEmail ?email }
            OPTIONAL { ?estudante :pertenceACurso ?cursoUri . ?cursoUri :designacao ?curso }
        }
        ORDER BY ?nome
        """
        return self.query(q)

    def get_estudante(self, numero_aluno):
        q = f"""
        PREFIX : <http://www.example.org/academic#>
        SELECT ?estudante ?nome ?email ?curso
        WHERE {{
            ?estudante a :Estudante ;
                       :temNome ?nome ;
                       :numeroAluno "{numero_aluno}" .
            OPTIONAL {{ ?estudante :temEmail ?email }}
            OPTIONAL {{ ?estudante :pertenceACurso ?cursoUri . ?cursoUri :designacao ?curso }}
        }}
        """
        rows = self.query(q)
        return rows[0] if rows else None

    def create_estudante(self, numero_aluno, nome, email=None, curso_uri=None):
        uri = ACAD[f"Estudante_{numero_aluno}"]
        if (uri, RDF.type, ACAD.Estudante) in self.graph:
            raise ValueError("Estudante já existe")

        self.graph.add((uri, RDF.type, ACAD.Estudante))
        self.graph.add((uri, ACAD.numeroAluno, Literal(numero_aluno, datatype=XSD.string)))
        self.graph.add((uri, ACAD.temNome, Literal(nome, datatype=XSD.string)))
        if email:
            self.graph.add((uri, ACAD.temEmail, Literal(email, datatype=XSD.string)))
        if curso_uri:
            self.graph.add((uri, ACAD.pertenceACurso, URIRef(curso_uri)))

        self.save()
        return str(uri)

    def delete_estudante(self, numero_aluno):
        q = f"""
        PREFIX : <http://www.example.org/academic#>
        SELECT ?estudante WHERE {{
            ?estudante a :Estudante ; :numeroAluno "{numero_aluno}" .
        }}
        """
        rows = self.query(q)
        if not rows:
            return False
        uri = URIRef(rows[0]["estudante"])
        for p, o in list(self.graph.predicate_objects(uri)):
            self.graph.remove((uri, p, o))
        for s, p in list(self.graph.subject_predicates(uri)):
            self.graph.remove((s, p, uri))
        self.save()
        return True

    # ------------------------------------------------------------------
    # CRUD: Unidades Curriculares
    # ------------------------------------------------------------------

    def list_ucs(self):
        q = """
        PREFIX : <http://www.example.org/academic#>
        SELECT ?uc ?codigo ?nome ?ects ?semestre ?curso
        WHERE {
            ?uc a :UnidadeCurricular ;
                :codigoUC ?codigo ;
                :temNome ?nome ;
                :ects ?ects ;
                :semestre ?semestre .
            OPTIONAL { ?uc :pertenceAoCurso ?cursoUri . ?cursoUri :designacao ?curso }
        }
        ORDER BY ?codigo
        """
        return self.query(q)

    def create_uc(self, codigo, nome, ects, semestre, curso_uri=None):
        uri = ACAD[f"UC_{codigo}"]
        if (uri, RDF.type, ACAD.UnidadeCurricular) in self.graph:
            raise ValueError("UC já existe")

        self.graph.add((uri, RDF.type, ACAD.UnidadeCurricular))
        self.graph.add((uri, ACAD.codigoUC, Literal(codigo, datatype=XSD.string)))
        self.graph.add((uri, ACAD.temNome, Literal(nome, datatype=XSD.string)))
        self.graph.add((uri, ACAD.ects, Literal(int(ects), datatype=XSD.integer)))
        self.graph.add((uri, ACAD.semestre, Literal(int(semestre), datatype=XSD.integer)))
        if curso_uri:
            self.graph.add((uri, ACAD.pertenceAoCurso, URIRef(curso_uri)))

        self.save()
        return str(uri)

    # ------------------------------------------------------------------
    # CRUD: Docentes
    # ------------------------------------------------------------------

    def list_docentes(self):
        q = """
        PREFIX : <http://www.example.org/academic#>
        SELECT ?docente ?nome ?email (GROUP_CONCAT(?ucNome; separator=", ") AS ?ucs)
        WHERE {
            ?docente a :Docente ;
                     :temNome ?nome .
            OPTIONAL { ?docente :temEmail ?email }
            OPTIONAL { ?docente :leciona ?ucUri . ?ucUri :temNome ?ucNome }
        }
        GROUP BY ?docente ?nome ?email
        ORDER BY ?nome
        """
        return self.query(q)

    # ------------------------------------------------------------------
    # CRUD: Avaliações
    # ------------------------------------------------------------------

    def list_avaliacoes(self, numero_aluno=None):
        filtro = ""
        if numero_aluno:
            filtro = f'?estudante :numeroAluno "{numero_aluno}" .'

        q = f"""
        PREFIX : <http://www.example.org/academic#>
        SELECT ?estudanteNome ?ucNome ?nota ?ano
        WHERE {{
            ?estudante a :Estudante ;
                       :temNome ?estudanteNome ;
                       :temAvaliacao ?avaliacao .
            {filtro}
            ?avaliacao :avaliaUC ?uc ;
                       :nota ?nota .
            ?uc :temNome ?ucNome .
            OPTIONAL {{ ?avaliacao :noAnoLetivo ?anoUri . ?anoUri :anoLetivoLabel ?ano }}
        }}
        ORDER BY ?estudanteNome ?ucNome
        """
        return self.query(q)

    def create_avaliacao(self, numero_aluno, codigo_uc, nota, ano_letivo=None):
        q = f"""
        PREFIX : <http://www.example.org/academic#>
        SELECT ?estudante WHERE {{
            ?estudante a :Estudante ; :numeroAluno "{numero_aluno}" .
        }}
        """
        rows = self.query(q)
        if not rows:
            raise ValueError("Estudante não encontrado")
        estudante_uri = URIRef(rows[0]["estudante"])

        uc_uri = ACAD[f"UC_{codigo_uc}"]
        if (uc_uri, RDF.type, ACAD.UnidadeCurricular) not in self.graph:
            raise ValueError("UC não encontrada")

        # gera um id incremental simples para a avaliação
        existing = list(self.graph.subjects(RDF.type, ACAD.Avaliacao))
        novo_id = len(existing) + 1
        aval_uri = ACAD[f"Avaliacao_{novo_id:03d}"]

        self.graph.add((aval_uri, RDF.type, ACAD.Avaliacao))
        self.graph.add((aval_uri, ACAD.avaliaUC, uc_uri))
        self.graph.add((aval_uri, ACAD.nota, Literal(float(nota), datatype=XSD.decimal)))
        self.graph.add((estudante_uri, ACAD.temAvaliacao, aval_uri))

        if ano_letivo:
            ano_uri = ACAD[f"AnoLetivo_{ano_letivo.replace('/', '_')}"]
            if (ano_uri, RDF.type, ACAD.AnoLetivo) not in self.graph:
                self.graph.add((ano_uri, RDF.type, ACAD.AnoLetivo))
                self.graph.add((ano_uri, ACAD.anoLetivoLabel, Literal(ano_letivo, datatype=XSD.string)))
            self.graph.add((aval_uri, ACAD.noAnoLetivo, ano_uri))

        self.save()
        return str(aval_uri)

    # ------------------------------------------------------------------
    # CRUD: Cursos (auxiliar, para popular formulários)
    # ------------------------------------------------------------------

    def list_cursos(self):
        q = """
        PREFIX : <http://www.example.org/academic#>
        SELECT ?curso ?designacao
        WHERE {
            ?curso a :Curso ; :designacao ?designacao .
        }
        ORDER BY ?designacao
        """
        return self.query(q)


# Instância única (singleton) partilhada pela aplicação
store = GraphStore()
