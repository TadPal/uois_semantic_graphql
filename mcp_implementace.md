# MCP implementace

## SK skills -> MCP servery
- Každý původní SK skill (detekce typů, build query, běh query, tabulka…) zveřejníme jako MCP server. 
- Implementace: FastAPI (HTTP) + MCP (pro přímou integraci s MCP klientem). Stejné funkce, stejné signatury.

## Orchestrátor
Vytvoříme orchestrator/ modul, který:
- Načte SDL (tvé sdl_fetch.py, sdl_parser.py).
- Rozhodne in-domain vs. out-of-domain (podle typu dotazu a SDL types_prompt).

In-domain:
- volá MCP endpointy (HTTP nebo MCP client SDK) k vybudování & spuštění GraphQL dotazu a vrátí:
```json
{Response, Query, Variables}.
```
Out-of-domain:
- pošle dotaz na Azure (deployment = AZURE_ORCHESTRATION_DEPLOYMENT_NAME, tj. tvůj “primár”) a vrátí:
```json
{Response, Query:"", Variables:""}.
```
## NiceGUI
Nahradíme openChat() z SK -> orchestrator.open_chat(). 
- UI dál očekává JSON s trojicí {Response, Query, Variables} – beze změny.




Teorie – proč MCP a proč SDL-first

MCP (Model Context Protocol) ti odpojí runtime nástroje od orchestrátoru. Tvoje dřívější SK skills se stanou samostatně nasaditelnými službami (nebo stdio tooly), které může používat libovolný orchestrátor, nejen SK.

SDL-first: GraphQL dotazy tvoříš z toho, co server skutečně umí (SDL). Minimalizuješ halucinace, špatné názvy fieldů, špatné typy. LLM jen “páruje” přirozený jazyk na typy a vztahy – a builder vyrobí validní query.

Fallback: U dotazů “mimo doménu” (vtip o kočkách) je nesmysl lámat to přes GraphQL. Proto s pomocí jednoho Azure deploymentu (AZURE_ORCHESTRATION_DEPLOYMENT_NAME) odpovíš přirozeně – žádné další proměnné, žádný separátní fallback deployment.

9) FAQ / tipy

Proč importy utils v MCP serverech?
Tady je využíváme naplno (builder z tvých utilit). Nicméně, pokud budeš chtít MCP servery super-jednoduché, můžeš builder logiku přesunout do orchestrátoru. Já to nechal v MCP, ať jsou znovupoužitelné.

HTTP vs. MCP SDK
Teď voláme HTTP (jednoduché, hned funkční). Později můžeš přidat čistý MCP stdio/ws a v mcp_client.py vyměnit transport.

Extrahovat id pro scalar dotazy
V ukázce scalar dotaz odmítnu, pokud nepřijde id. Prakticky se hodí malý pomocný prompt (Azure), který z otázky vytáhne UUID, a když najde validní, voláš runQuerySingle.



Odkud bereme “znalosti” GQL modelů?

Zdroj pravdy je živé SDL – tahá se runtime přes sdl_fetch.fetch_sdl() z běžícího gatewaye.

types_prompt.txt je jen šablona promptu pro LLM, do které orchestrátor vkládá aktuální seznam typů vytažený ze SDL.

schema.graphql soubor se v aktuální implementaci nepoužívá (je dobrý jen jako offline fallback/fixture).

Navíc i GraphQLQueryBuilder uvnitř MCP volá fetch_sdl(), takže builder/runner vždy pracují proti aktuálnímu schématu v dockeru.