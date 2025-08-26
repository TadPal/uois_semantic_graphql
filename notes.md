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

**SIGN IN**
