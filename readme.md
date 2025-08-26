# Praxe 2025

1. Deploy docker

   - fix systemdata.json
   - add [pg_vector](https://github.com/pgvector/pgvector) to stack
   - removed replicas (commented)

2. Test graphiql

```graphql
{
  __schema {
    queryType {
      name
      fields {
        name
        description
        args {
          name
          description
        }
        type {
          name
        }
      }
    }
  }
}
```

```graphql
query GetServiceSDL {
  _service {
    sdl
  }
}
```

3. Extract desc from graphql

```python
from sdl.sdl_parser import extractor as parser
from sdl.sdl_extract_object import extractor
import json

if __name__ == "__main__":
    sdl_file = "sdl\schema.graphql"
    pass
```

4. Run Ollama and local embedding model

```bash
ollama pull mxbai-embed-large
```

5. Embed types

```python
 def get_embedding(text: str):
        response = ollama.embeddings(model=MODEL, prompt=text)
        return response["embedding"]
```

6. Embed queries and search

```python
 def get_embedding(text: str):
        response = ollama.embeddings(model=MODEL, prompt=text)
        return response["embedding"]

  query = "Show me all planned lessons for this semester"

  embedding = get_embeddings(query=query)
```

```sql
SELECT name, description
FROM graphql_types
ORDER BY embedding <-> %s::vector
LIMIT 5; (embedding,)
```
