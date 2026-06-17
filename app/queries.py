"""
queries.py

Conjunto de consultas SPARQL inteligentes sobre o domínio académico,
demonstrando a exploração semântica dos dados (objetivo do Tema 4).
"""

PREFIX = "PREFIX : <http://www.example.org/academic#>\n"

QUERIES = {

    "ucs_com_pre_requisitos": {
        "label": "UCs e respetivos pré-requisitos",
        "description": "Lista todas as UCs e os pré-requisitos de que dependem.",
        "sparql": PREFIX + """
        SELECT ?ucNome ?preRequisitoNome
        WHERE {
            ?uc a :UnidadeCurricular ; :temNome ?ucNome .
            OPTIONAL {
                ?uc :temPreRequisito ?pre .
                ?pre :temNome ?preRequisitoNome .
            }
        }
        ORDER BY ?ucNome
        """
    },

    "estudantes_em_risco": {
        "label": "Estudantes com nota inferior a 10 (reprovados)",
        "description": "Identifica estudantes com avaliações negativas, úteis para acompanhamento.",
        "sparql": PREFIX + """
        SELECT ?estudanteNome ?ucNome ?nota
        WHERE {
            ?estudante a :Estudante ; :temNome ?estudanteNome ; :temAvaliacao ?aval .
            ?aval :avaliaUC ?uc ; :nota ?nota .
            ?uc :temNome ?ucNome .
            FILTER (?nota < 10)
        }
        ORDER BY ?nota
        """
    },

    "media_por_uc": {
        "label": "Média de notas por UC",
        "description": "Calcula a média das notas obtidas em cada Unidade Curricular.",
        "sparql": PREFIX + """
        SELECT ?ucNome (AVG(?nota) AS ?media) (COUNT(?nota) AS ?numAvaliacoes)
        WHERE {
            ?aval a :Avaliacao ; :avaliaUC ?uc ; :nota ?nota .
            ?uc :temNome ?ucNome .
        }
        GROUP BY ?ucNome
        ORDER BY DESC(?media)
        """
    },

    "docentes_e_ucs_comuns": {
        "label": "Docentes que partilham pré-requisitos entre as UCs que lecionam",
        "description": "Para cada docente, mostra as UCs que leciona e os respetivos pré-requisitos, "
                        "revelando relações semânticas entre cadeiras de diferentes docentes.",
        "sparql": PREFIX + """
        SELECT ?docenteNome ?ucNome ?preRequisitoNome
        WHERE {
            ?docente a :Docente ; :temNome ?docenteNome ; :leciona ?uc .
            ?uc :temNome ?ucNome .
            OPTIONAL {
                ?uc :temPreRequisito ?pre .
                ?pre :temNome ?preRequisitoNome .
            }
        }
        ORDER BY ?docenteNome
        """
    },

    "estudantes_prontos_para_uc": {
        "label": "Estudantes que já cumprem os pré-requisitos de uma UC",
        "description": "Inferência simples: cruza as UCs concluídas (com avaliação) de cada estudante "
                        "com os pré-requisitos exigidos por outra UC (ex: Arquitetura de Sistemas).",
        "sparql": PREFIX + """
        SELECT DISTINCT ?estudanteNome ?ucDestinoNome
        WHERE {
            ?ucDestino a :UnidadeCurricular ; :temNome ?ucDestinoNome ; :temPreRequisito ?pre .
            ?estudante a :Estudante ; :temNome ?estudanteNome ; :temAvaliacao ?aval .
            ?aval :avaliaUC ?pre ; :nota ?nota .
            FILTER (?nota >= 10)

            # garante que cumpre TODOS os pré-requisitos dessa UC destino
            FILTER NOT EXISTS {
                ?ucDestino :temPreRequisito ?outroPre .
                FILTER NOT EXISTS {
                    ?estudante :temAvaliacao ?aval2 .
                    ?aval2 :avaliaUC ?outroPre ; :nota ?nota2 .
                    FILTER (?nota2 >= 10)
                }
            }
        }
        ORDER BY ?ucDestinoNome ?estudanteNome
        """
    },

    "ucs_por_curso": {
        "label": "UCs organizadas por curso e semestre",
        "description": "Mostra a estrutura curricular: que UCs pertencem a que curso e em que semestre.",
        "sparql": PREFIX + """
        SELECT ?cursoNome ?semestre ?ucNome ?ects
        WHERE {
            ?uc a :UnidadeCurricular ;
                :temNome ?ucNome ;
                :ects ?ects ;
                :semestre ?semestre ;
                :pertenceAoCurso ?curso .
            ?curso :designacao ?cursoNome .
        }
        ORDER BY ?cursoNome ?semestre ?ucNome
        """
    },

    "melhor_aluno_por_uc": {
        "label": "Melhor nota obtida em cada UC",
        "description": "Para cada UC, mostra o estudante com a melhor nota registada.",
        "sparql": PREFIX + """
        SELECT ?ucNome ?estudanteNome (MAX(?nota) AS ?melhorNota)
        WHERE {
            ?estudante a :Estudante ; :temNome ?estudanteNome ; :temAvaliacao ?aval .
            ?aval :avaliaUC ?uc ; :nota ?nota .
            ?uc :temNome ?ucNome .
        }
        GROUP BY ?ucNome ?estudanteNome
        ORDER BY ?ucNome DESC(?melhorNota)
        """
    },
}
