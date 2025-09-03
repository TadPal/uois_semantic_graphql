import xml.etree.ElementTree as ET
from typing import List, Dict, Any


def extract_prompts_from_chat_xml(xml_content: str) -> Dict[str, List[str]]:
    """
    Extract system prompts, user prompts, and assistant prompts (non-function calls) from XML chat history.

    Args:
        xml_content (str): The XML content as a string

    Returns:
        Dict[str, List[str]]: Dictionary containing lists of prompts categorized by role
    """
    try:
        # Parse the XML
        root = ET.fromstring(xml_content)

        # Initialize result dictionary
        result = {
            "system_prompts": [],
            "user_prompts": [],
            "assistant_prompts": [],
            "tool_prompts": [],
        }

        # Find all message elements
        messages = root.findall(".//message")

        for message in messages:
            role = message.get("role")

            # Check if message has function calls (finish_reason="tool_calls" or contains function_call)
            finish_reason = message.get("finish_reason")
            has_function_call = message.find("function_call") is not None

            if finish_reason == "tool_calls" or has_function_call:
                continue

            # Extract text content
            text_element = message.find("text")
            if text_element is not None and text_element.text:
                text_content = text_element.text.strip()

            function_result = message.find("function_result")
            if function_result is not None and function_result.text:
                text_content = function_result.text.strip()

                # Categorize by role
                if role == "system":
                    result["system_prompts"].append(text_content)
                elif role == "user":
                    result["user_prompts"].append(text_content)
                elif role == "assistant":
                    result["assistant_prompts"].append(text_content)
                elif role == "tool":
                    result["tool_prompts"].append(text_content)

        return result

    except ET.ParseError as e:
        raise ValueError(f"Invalid XML format: {e}")
    except Exception as e:
        raise RuntimeError(f"Error processing XML: {e}")


def print_extracted_prompts(prompts: Dict[str, List[str]]) -> None:
    """
    Pretty print the extracted prompts.

    Args:
        prompts (Dict[str, List[str]]): Dictionary containing categorized prompts
    """
    for category, prompt_list in prompts.items():
        print(f"\n{'='*50}")
        print(f"{category.upper().replace('_', ' ')}")
        print(f"{'='*50}")

        if not prompt_list:
            print("No prompts found in this category.")
        else:
            for i, prompt in enumerate(prompt_list, 1):
                print(f"\n[{i}] {prompt}")
                print("-" * 30)


def main():
    # Example XML content (you would replace this with your actual XML)
    xml_sample = """<chat_history>
    <message role="system">
        <text>
        You are an assistant and your primary task is to help query databases using graphql.

        Rules:
        1. Build a new query before running it against the API.
        2. You build the graphql queries only using available kernel_functions.
        3. Every time the query returns with an Error you provide the used query in your response.
        4. Never use graphqlFilterBuilder with id.
        </text>
    </message>
    <message role="user">
        <text>
        give me a user
        </text>
    </message>
    <message finish_reason="tool_calls" role="assistant" ai_model_id="summarization-deployment">
        <function_call id="call_dpyoF39dCDugjRZYXB7neGZz" name="graphqlQueryBuilder-buildVectorQuery">
            {"graphql_types":["UserGQLModel"],"arguments":{}}
        </function_call>
    </message>
    <message role="tool">
    <function_result id="call_dpyoF39dCDugjRZYXB7neGZz" name="graphqlQueryBuilder-buildVectorQuery">#
    # @param {Int} skip - The `Int` scalar type represents non-fractional signed whole numeric values. Int can represent values between -(2^31) and 2^31 - 1.
    # @param {Int} limit - The `Int` scalar type represents non-fractional signed whole numeric values. Int can represent values between -(2^31) and 2^31 - 1.
    # @param {String} orderby - The `String` scalar type represents textual data, represented as UTF-8 character sequences. The String type is most often used by GraphQL to represent free-form human-readable text.
    # @param {UserInputWhereFilter} where - UserInputWhereFilter operator for UserInputWhereFilter
    # @returns {Object}
    #
    # @property {UserGQLModel} userPage - ## Description Fetches a paginated list of users. Načte stránkovaný seznam uživatelů. ## Details Returns a list of users based on filtering criteria defined in UserInputWhereFilter. Supports pagination, sorting, and advanced filtering options. Vrací seznam uživatelů na základě filtračních kritérií definovaných ve třídě UserInputWhereFilter. Podporuje stránkování, řazení a pokročilé filtrovací možnosti. ## Permissions Accessible only to authenticated users. Přístup pouze pro autentizované uživatele.
    # @property {UUID} userPage.id - Primary key of the entity. Primární klíč entity.
    # @property {DateTime} userPage.lastchange - Timestamp of the last change. Časové razítko poslední změny.
    # @property {DateTime} userPage.created - Date and time when the entity was created. Datum a čas vytvoření entity.
    # @property {UUID} userPage.createdbyId - Identifier of the user who created this entity. Identifikátor uživatele, který vytvořil tuto entitu.
    # @property {UUID} userPage.changedbyId - Identifier of the user who last modified this entity. Identifikátor uživatele, který naposledy upravil tuto entitu.
    # @property {UUID} userPage.rbacobjectId - Reference to the RBAC object governing permissions. Reference na RBAC objekt, který řídí oprávnění.
    # @property {String} userPage.name - Full name (if in database) Celé jméno (pokud je v databázi)
    # @property {String} userPage.givenname - User's name (like John) Jméno uživatele (např. John)
    # @property {String} userPage.middlename - Middle name Střední jméno
    # @property {String} userPage.email - Email address Emailová adresa
    # @property {String} userPage.firstname - User's first name (like John) Křestní jméno uživatele (např. John)
    # @property {String} userPage.surname - User's family name (like Obama) Rodinné jméno uživatele (např. Obama)
    # @property {Boolean} userPage.valid - User validity status Stav platnosti uživatele
    # @property {DateTime} userPage.startdate - Account start date Datum zahájení účtu
    # @property {DateTime} userPage.enddate - Account end date Datum ukončení účtu
    # @property {UUID} userPage.typeId - User type identifier Identifikátor typu uživatele
    # @property {Boolean} userPage.isThisMe - Checks if the current record belongs to the logged-in user Zjistí, zda záznam patří přihlášenému uživateli
    # @property {String} userPage.gdpr - Performs GDPR compliance check Provádí kontrolu souladu s GDPR
    # @property {String} userPage.fullname - Concatenates user's name parts into full name Spojí části jména uživatele do celého jména
    # @property {PresenceGQLModel} userPage.presences - presences of the user
    # @property {UUID} userPage.presences.id - Entity primary key
    # @property {ExternalIdGQLModel} userPage.externalIds - All related external ids
    # @property {UUID} userPage.externalIds.id - Entity primary key
    # @property {AcProgramStudentGQLModel} userPage.studies - Program owing this subjects
    # @property {UUID} userPage.studies.id - Entity primary key
    # @property {AcClassificationGQLModel} userPage.classifications - user classifications
    # @property {UUID} userPage.classifications.id - Entity primary key
    # @property {PublicationAuthorGQLModel} userPage.authorPublications - List of authors
    # @property {UUID} userPage.authorPublications.id - Entity primary key
    # @property {AnswerGQLModel} userPage.answers - List
    # @property {UUID} userPage.answers.id - Entity primary key
    # @property {UserGQLModel} userPage.createdby - The user who created this entity. Uživatel, který vytvořil tuto entitu.
    # @property {UUID} userPage.createdby.id - Primary key of the entity. Primární klíč entity.
    # @property {UserGQLModel} userPage.changedby - The user who last modified this entity. Uživatel, který naposledy upravil tuto entitu.
    # @property {UUID} userPage.changedby.id - Primary key of the entity. Primární klíč entity.
    # @property {RBACObjectGQLModel} userPage.rbacobject - The RBAC object associated with this entity. RBAC objekt spojený s touto entitou.
    # @property {UUID} userPage.rbacobject.id - id
    # @property {MembershipGQLModel} userPage.memberships - List of memberships associated with the user Seznam členství spojených s uživatelem
    # @property {UUID} userPage.memberships.id - Primary key of the entity. Primární klíč entity.
    # @property {MembershipGQLModel} userPage.membership - Deprecated: list of memberships (use memberships) Zastaralé: seznam členství (použijte memberships)
    # @property {UUID} userPage.membership.id - Primary key of the entity. Primární klíč entity.
    # @property {RoleGQLModel} userPage.roles - Roles assigned to the user Role přiřazené uživateli
    # @property {UUID} userPage.roles.id - Primary key of the entity. Primární klíč entity.
    # @property {RoleGQLModel} userPage.rolesOn - Fetches roles related to the user Načte role vztažené k uživateli
    # @property {UUID} userPage.rolesOn.id - Primary key of the entity. Primární klíč entity.
    # @property {GroupGQLModel} userPage.memberOf - Retrieves a list of groups of a specified type where the user is a member Načte seznam skupin daného typu, kde je uživatel členem
    # @property {UUID} userPage.memberOf.id - Primary key of the entity. Primární klíč entity.

    query userPage($skip: Int, $limit: Int, $orderby: String, $where: UserInputWhereFilter) {
    userPage(skip: $skip, limit: $limit, orderby: $orderby, where: $where) {
        ...UserGQLModelMediumFragment
        ...UserGQLModelLargeFragment
    }
    }

    fragment UserGQLModelMediumFragment on UserGQLModel {
    __typename
    id
    lastchange
    created
    createdbyId
    changedbyId
    rbacobjectId
    name
    givenname
    middlename
    email
    firstname
    surname
    valid
    startdate
    enddate
    typeId
    isThisMe
    gdpr
    fullname
    }

    fragment UserGQLModelLargeFragment on UserGQLModel {
    __typename
    id
    presences {
        __typename
        id
    }
    externalIds {
        __typename
        id
    }
    studies {
        __typename
        id
    }
    classifications {
        __typename
        id
    }
    authorPublications {
        __typename
        id
    }
    answers {
        __typename
        id
    }
    lastchange
    created
    createdbyId
    changedbyId
    rbacobjectId
    createdby {
        __typename
        id
    }
    changedby {
        __typename
        id
    }
    rbacobject {
        __typename
        id
    }
    name
    givenname
    middlename
    email
    firstname
    surname
    valid
    startdate
    enddate
    typeId
    memberships {
        __typename
        id
    }
    membership {
        __typename
        id
    }
    roles {
        __typename
        id
    }
    isThisMe
    rolesOn {
        __typename
        id
    }
    gdpr
    fullname
    memberOf {
        __typename
        id
    }
    }
    </function_result>
    </message>
    
    <message finish_reason="tool_calls" role="assistant" ai_model_id="summarization-deployment">
        <function_call id="call_w3J7PpoQIogGGyWHs4QcfblT" name="graphqlRunQuery-runQueryPage">{"graphql_query":"query userPage($skip: Int, $limit: Int, $orderby: String, $where: UserInputWhereFilter) {\n  userPage(skip: $skip, limit: $limit, orderby: $orderby, where: $where) {\n    ...UserGQLModelMediumFragment\n    ...UserGQLModelLargeFragment\n  }\n}\n\nfragment UserGQLModelMediumFragment on UserGQLModel {\n  __typename\n  id\n  lastchange\n  created\n  createdbyId\n  changedbyId\n  rbacobjectId\n  name\n  givenname\n  middlename\n  email\n  firstname\n  surname\n  valid\n  startdate\n  enddate\n  typeId\n  isThisMe\n  gdpr\n  fullname\n}\n\nfragment UserGQLModelLargeFragment on UserGQLModel {\n  __typename\n  id\n  presences {\n    __typename\n    id\n  }\n  externalIds {\n    __typename\n    id\n  }\n  studies {\n    __typename\n    id\n  }\n  classifications {\n    __typename\n    id\n  }\n  authorPublications {\n    __typename\n    id\n  }\n  answers {\n    __typename\n    id\n  }\n  lastchange\n  created\n  createdbyId\n  changedbyId\n  rbacobjectId\n  createdby {\n    __typename\n    id\n  }\n  changedby {\n    __typename\n    id\n  }\n  rbacobject {\n    __typename\n    id\n  }\n  name\n  givenname\n  middlename\n  email\n  firstname\n  surname\n  valid\n  startdate\n  enddate\n  typeId\n  memberships {\n    __typename\n    id\n  }\n  membership {\n    __typename\n    id\n  }\n  roles {\n    __typename\n    id\n  }\n  isThisMe\n  rolesOn {\n    __typename\n    id\n  }\n  gdpr\n  fullname\n  memberOf {\n    __typename\n    id\n  }\n}","skip":0,"limit":1,"arguments":{}}</function_call></message><message role="tool"><function_result id="call_w3J7PpoQIogGGyWHs4QcfblT" name="graphqlRunQuery-runQueryPage">[{'__typename': 'UserGQLModel', 'id': '51d101a0-81f1-44ca-8366-6cf51432e8d6', 'lastchange': '2024-08-19T20:34:24.539770', 'created': '2024-08-19T20:34:24.539770', 'createdbyId': None, 'changedbyId': None, 'rbacobjectId': None, 'name': 'Zdeňka', 'givenname': None, 'middlename': None, 'email': 'Zdeňka.Šimečková@world.com', 'firstname': None, 'surname': 'Šimečková', 'valid': True, 'startdate': None, 'enddate': None, 'typeId': None, 'isThisMe': True, 'gdpr': None, 'fullname': 'Zdeňka Šimečková', 'presences': [{'__typename': 'PresenceGQLModel', 'id': 'd62ca26f-5a94-4eab-94c5-2f4503e28dc6'}, {'__typename': 'PresenceGQLModel', 'id': 'c2c29d97-4d47-4736-b1a9-7183c91d95fa'}, {'__typename': 'PresenceGQLModel', 'id': 'e4d7fbbf-eb61-43fd-b2ca-b82994432c0e'}, {'__typename': 'PresenceGQLModel', 'id': 'fa559be6-636b-43dc-8d36-dbd6b8dd6094'}, {'__typename': 'PresenceGQLModel', 'id': '83feb716-1fd6-4bd2-88ad-c4c947ba7d18'}, {'__typename': 'PresenceGQLModel', 'id': 'a04d8d50-ca74-4865-8c02-bb47a277319e'}, {'__typename': 'PresenceGQLModel', 'id': '8a836fb0-6b65-4e3b-9961-1920ba0413cd'}, {'__typename': 'PresenceGQLModel', 'id': '98aef9f0-5ea6-418d-9241-78906abd6e4e'}, {'__typename': 'PresenceGQLModel', 'id': 'e2a21773-1170-4fc7-855f-a370754c30e9'}], 'externalIds': [], 'studies': [], 'classifications': [], 'authorPublications': [], 'answers': [], 'createdby': None, 'changedby': None, 'rbacobject': None, 'memberships': [{'__typename': 'MembershipGQLModel', 'id': '2ef47ed9-aacf-405d-b5fb-d62a836524bc'}, {'__typename': 'MembershipGQLModel', 'id': '23ccfdf7-deef-4327-bdc1-dfe1b4d3fa4c'}, {'__typename': 'MembershipGQLModel', 'id': 'e1e7dc28-9d12-4de1-bef9-c252f676fa31'}], 'membership': [{'__typename': 'MembershipGQLModel', 'id': '2ef47ed9-aacf-405d-b5fb-d62a836524bc'}, {'__typename': 'MembershipGQLModel', 'id': '23ccfdf7-deef-4327-bdc1-dfe1b4d3fa4c'}, {'__typename': 'MembershipGQLModel', 'id': 'e1e7dc28-9d12-4de1-bef9-c252f676fa31'}], 'roles': [{'__typename': 'RoleGQLModel', 'id': '0d9c9a8a-16a9-485a-bda5-08c1830ae654'}, {'__typename': 'RoleGQLModel', 'id': '817cdd94-9174-45da-aa0c-f2607b7fed13'}], 'rolesOn': [{'__typename': 'RoleGQLModel', 'id': 'd1bf927a-92a5-4738-bee9-07a6d2a68c53'}, {'__typename': 'RoleGQLModel', 'id': '8fc984da-01b3-4bb8-bf08-453dc5632156'}, {'__typename': 'RoleGQLModel', 'id': 'b469df34-f05f-4fad-9cbe-3e52a423b3f1'}, {'__typename': 'RoleGQLModel', 'id': 'f2360a06-accf-4aeb-b400-39e2deddbed3'}, {'__typename': 'RoleGQLModel', 'id': '84ddf181-0f36-4cd2-bcbc-514bad02c08e'}, {'__typename': 'RoleGQLModel', 'id': '0d9c9a8a-16a9-485a-bda5-08c1830ae654'}, {'__typename': 'RoleGQLModel', 'id': 'c8a410f1-89e8-4bd0-b638-f07ddedad11e'}, {'__typename': 'RoleGQLModel', 'id': 'ec0673a8-6899-483b-9c2f-cad672f61b90'}, {'__typename': 'RoleGQLModel', 'id': '0da281f5-84d8-4f2f-b47c-34c8264c5275'}, {'__typename': 'RoleGQLModel', 'id': '440f41b3-58de-4598-a51c-239ad5b22dd2'}, {'__typename': 'RoleGQLModel', 'id': 'ce6df868-637f-460e-9d33-239640d4cf7c'}], 'memberOf': []}]
        </function_result>
    </message>
    <message role="assistant">
    <text>Here is a user retrieved from the database:

    - **Name:** Zdeňka Šimečková
    - **Email:** Zdeňka.Šimečková@world.com
    - **Valid:** True
    - **Created On:** 2024-08-19T20:34:24.539770
    - **Last Changed:** 2024-08-19T20:34:24.539770
    - **Full Name:** Zdeňka Šimečková
    - **Memberships:**
    - ID: 2ef47ed9-aacf-405d-b5fb-d62a836524bc
    - ID: 23ccfdf7-deef-4327-bdc1-dfe1b4d3fa4c
    - ID: e1e7dc28-9d12-4de1-bef9-c252f676fa31
    - **Roles:**
    - ID: 0d9c9a8a-16a9-485a-bda5-08c1830ae654
    - ID: 817cdd94-9174-45da-aa0c-f2607b7fed13

    If you need any more information or another user, just let me know!</text></message>
</chat_history>"""

    try:
        # Extract prompts
        extracted_prompts = extract_prompts_from_chat_xml(xml_sample)

        # Print results
        print_extracted_prompts(extracted_prompts)

        # You can also access individual categories:
        print(f"\nFound {len(extracted_prompts['system_prompts'])} system prompts")
        print(f"Found {len(extracted_prompts['user_prompts'])} user prompts")
        print(f"Found {len(extracted_prompts['assistant_prompts'])} assistant prompts")

    except Exception as e:
        print(f"Error: {e}")


# main()
