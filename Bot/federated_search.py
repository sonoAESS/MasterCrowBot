from SPARQLWrapper import SPARQLWrapper, JSON


def federated_sparql_query():
    local_endpoint = "https://query.wikidata.org/sparql"
    uniprot_endpoint = "https://sparql.uniprot.org/sparql"

    sparql = SPARQLWrapper(local_endpoint)
    sparql.setReturnFormat(JSON)
    query = f"""
    PREFIX up: <http://purl.uniprot.org/core/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?source ?entity ?label ?sequence ?sequenceType WHERE {{
      {{
        SERVICE <{uniprot_endpoint}> {{
          BIND("UniProt" AS ?source)
          ?entity a up:Protein .
          ?entity rdfs:label ?label .
          ?entity up:sequence ?seqResource .
          ?seqResource rdf:value ?sequence .
          ?seqResource a ?sequenceType .
          FILTER (?sequenceType IN (up:ProteinSequence, up:DnaSequence, up:RnaSequence))
        }}
      }}
    }}
    LIMIT 10
    """
    sparql.setQuery(query)
    results = sparql.query().convert()
    return results["results"]["bindings"]


def format_results(results):
    if not results:
        return "No se encontraron resultados."
    messages = []
    for r in results:
        source = r.get("source", {}).get("value", "Desconocido")
        label = r.get("label", {}).get("value", "N/A")
        sequence = r.get("sequence", {}).get("value", "No disponible")
        seq_type = r.get("sequenceType", {}).get("value", "Tipo no especificado")
        msg = f"[{source}] {label}\nTipo: {seq_type}\nSecuencia: {sequence[:60]}..."
        messages.append(msg)
    return "\n\n".join(messages)
