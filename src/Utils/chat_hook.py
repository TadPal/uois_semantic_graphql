import json
import asyncio
from nicegui import ui

from src.Utils.fetch_graphQLdata import fetch_graphql_data
from src.Utils.graphQLdata import GraphQLData
from src.Components.likeDislikeButton import add_feedback_row
from Database.ChatHistory.add_to_db import add_chat_history


async def run_chat_hook_flow(
    question: str,
    chat_hook,
    log_chat,
    thinking_message,
    animation_task,
    feedback_row,
    chat_stream,
    gql_client,
    history,
    user_id: str,
):
    query = None
    variables = None
    response = None
    try:
        result = await chat_hook(question)
        log_chat.info("Chat hook answered", extra={"answer_len": len(str(result))})
    except Exception:
        log_chat.exception("Chat hook failed")
        raise

    try:
        data = json.loads(result.content)
        print("data", data)
        query = data["Query"]
        variables = data["Variables"]
        response = data["Response"]
        response = [{"type": "md", "content": f'{data["Response"]}'}]

    except json.JSONDecodeError as e:
        print(f"Chyba při parsování JSONu: {e}")
        data = result.content
        response = [{"type": "md", "content": f"{data}"}]

    animation_task.cancel()
    print("\n Response from chat hook", response)

    try:
        await animation_task
    except asyncio.CancelledError:
        pass

    for part in response:
        await asyncio.sleep(1)
        thinking_message.clear()
        with thinking_message:
            if part["type"] == "text":
                ui.html(part["content"])
            elif part["type"] == "md":
                ui.markdown(part["content"])

    if feedback_row:
        try:
            feedback_row.delete()
        except Exception:
            pass
    with chat_stream:
        feedback_row = add_feedback_row(
            chat_stream, query=query, question=question, variables=variables
        )

    if query:
        with chat_stream:
            GraphQLData(
                gqlclient=gql_client,
                query=query,
                variables=variables,
            )

    try:
        answer_text = response["Response"]
    except Exception:
        answer_text = str(result)

    # ulož do historie v paměti
    history.add_entry(question=question, answer=answer_text)

    # ulož do DB jen čistý text
    add_chat_history(
        message=question,
        answer=data,
        user_id=user_id,
        session_id=history.get_history_id(),
    )
