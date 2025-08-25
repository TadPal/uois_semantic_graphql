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

**SIGN IN**
