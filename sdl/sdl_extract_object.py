def extractor(json: dict) -> dict:
    result = []
    for t in json:
        if "name" in t.keys() and "description" in t.keys():
            type = {"name": t["name"], "description": t["description"]}
            result.append(type)
    return result
