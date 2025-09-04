import json

# Simulovaný výstup od LLM, který byste získali.
# V reálné situaci byste sem dali proměnnou s obsahem odpovědi.
llm_output = """
{
  "Response": {
    "data": {
      "programPage": [
        {
          "id": "123",
          "name": "Computer Science"
        }
      ]
    }
  },
  "Query": "query($limit: Int, $skip: Int) {\\n  programPage(limit: $limit, skip: $skip) {\\n    id\\n    name\\n  }\\n}"
}
"""

try:
    # Parsuje se celý JSON objekt.
    data = json.loads(llm_output)

    # Získá se pouze hodnota z klíče "Query".
    query = data["Response"]
    print("Extrahovaný GraphQL dotaz:")
    print(query)

except json.JSONDecodeError as e:
    print(f"Chyba při parsování JSONu: {e}")
except KeyError as e:
    print(f"Klíč nebyl nalezen: {e}")
