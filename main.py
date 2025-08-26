from sdl.sdl_parser import extractor as parser
from sdl.sdl_extract_object import extractor
import json

if __name__ == "__main__":
    sdl_file = "sdl\\schema.graphql"
    with open(sdl_file, "r", encoding="utf-8") as f:
        sdl = f.read()

    parsed = parser(sdl)

    with open("json\\sld_parsed.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(parsed, indent=2, ensure_ascii=False))

    extracted = extractor(parsed["types"])
    with open("json\\sld_extracted.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(extracted, indent=2, ensure_ascii=False))
