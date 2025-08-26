from sld_parser import extractor
import json

if __name__ == "__main__":
    sdl_file = "schema.graphql"
    with open(sdl_file, "r", encoding="utf-8") as f:
        sdl = f.read()

    parsed = extractor(sdl)

    print(json.dumps(parsed, indent=2, ensure_ascii=False))