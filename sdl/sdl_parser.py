from graphql import (
    build_schema,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLInputObjectType,
)


def extractor(sdl: str) -> dict:
    """
    Parser, který vrací strukturu
    {
      "types": [
        {
          "name": "AcClassificationGQLModel",
          "kind": "OBJECT",
          "description": "Entity which holds ...",
          "fields": [
            {"name": "id", "description": "Entity primary key"},
            {"name": "name", "description": "Name "},
            {"name": "nameEn", "description": "English name"},
            ...
          ]
        },
        ...
      ]
    }
    """
    schema = build_schema(sdl)
    result = {"types": []}

    for name, t in sorted(schema.type_map.items()):
        # Fitted for our purpose (Add Query and Mutation for completeness)
        if "_" in name or name == "Query" or name == "Mutation":
            continue

        kind = None
        fields_out = []

        if isinstance(t, GraphQLObjectType):
            kind = "OBJECT"
            for fname, f in t.fields.items():
                fields_out.append(
                    {"attribute": fname, "description": f.description or ""}
                )

        # elif isinstance(t, GraphQLInterfaceType):
        #     kind = "INTERFACE"
        #     for fname, f in t.fields.items():
        #         fields_out.append(
        #             {"attribute": fname, "description": f.description or ""}
        #         )

        # elif isinstance(t, GraphQLInputObjectType):
        #     kind = "INPUT_OBJECT"
        #     for fname, f in t.fields.items():
        #         fields_out.append(
        #             {"attribute": fname, "description": f.description or ""}
        #         )

        # elif isinstance(t, GraphQLEnumType):
        #     kind = "ENUM"
        #     for vname, v in t.values.items():
        #         fields_out.append(
        #             {"attribute": vname, "description": v.description or ""}
        #         )

        # elif isinstance(t, GraphQLUnionType):
        #     kind = "UNION"
        #     # union nemá fields, ale typy členů – můžeš uložit jako "members"
        #     fields_out = [
        #         {"attribute": m.name, "description": m.description or ""}
        #         for m in t.types
        #     ]

        else:
            # skalární typy atd.
            # kind = (
            #     getattr(t, "ast_node", None)
            #     .__class__.__name__.replace("DefinitionNode", "")
            #     .upper()
            #     or "SCALAR"
            # )
            continue

        result["types"].append(
            {
                "name": name,
                "kind": kind,
                "description": t.description or "",
                "fields": fields_out,
            }
        )
    return result
