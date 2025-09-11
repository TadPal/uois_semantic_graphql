from nicegui import ui
import uuid
import logging
from src.Utils.on_button_press import (
    FeedbackState,
    on_like_click,
    on_dislike_click,
)

log = logging.getLogger("feedback")

# SVG konstanty
LIKE_DEFAULT = """<svg class="w-6 h-6 text-blue-700 dark:text-gray-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 11c.889-.086 1.416-.543 2.156-1.057a22.323 22.323 0 0 0 3.958-5.084 1.6 1.6 0 0 1 .582-.628 1.549 1.549 0 0 1 1.466-.087c.205.095.388.233.537.406a1.64 1.64 0 0 1 .384 1.279l-1.388 4.114M7 11H4v6.5A1.5 1.5 0 0 0 5.5 19v0A1.5 1.5 0 0 0 7 17.5V11Zm6.5-1h4.915c.286 0 .372.014.626.15.254.135.472.332.637.572a1.874 1.874 0 0 1 .215 1.673l-2.098 6.4C17.538 19.52 17.368 20 16.12 20c-2.303 0-4.79-.943-6.67-1.475"/></svg>"""
LIKE_SELECTED = """<svg class="w-6 h-6 text-blue-700 dark:text-gray-200" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M15.03 9.684h3.965c.322 0 .64.08.925.232.286.153.532.374.717.645a2.109 2.109 0 0 1 .242 1.883l-2.36 7.201c-.288.814-.48 1.355-1.884 1.355-2.072 0-4.276-.677-6.157-1.256-.472-.145-.924-.284-1.348-.404h-.115V9.478a25.485 25.485 0 0 0 4.238-5.514 1.8 1.8 0 0 1 .901-.83 1.74 1.74 0 0 1 1.21-.048c.396.13.736.397.96.757.225.36.32.788.269 1.211l-1.562 4.63ZM4.177 10H7v8a2 2 0 1 1-4 0v-6.823C3 10.527 3.527 10 4.176 10Z" clip-rule="evenodd"/></svg>"""
DISLIKE_DEFAULT = """<svg class="w-6 h-6 text-blue-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 13c-.889.086-1.416.543-2.156 1.057a22.322 22.322 0 0 0-3.958 5.084 1.6 1.6 0 0 1-.582.628 1.549 1.549 0 0 1-1.466.087 1.587 1.587 0 0 1-.537-.406 1.666 1.666 0 0 1-.384-1.279l1.389-4.114M17 13h3V6.5A1.5 1.5 0 0 0 18.5 5v0A1.5 1.5 0 0 0 17 6.5V13Zm-6.5 1H5.585c-.286 0-.372-.014-.626-.15a1.797 1.797 0 0 1-.637-.572 1.873 1.873 0 0 1-.215-1.673l2.098-6.4C6.462 4.48 6.632 4 7.88 4c2.302 0 4.79.943 6.67 1.475"/></svg>"""
DISLIKE_SELECTED = """<svg class="w-6 h-6 text-blue-500 dark:text-gray-400" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M8.97 14.316H5.004c-.322 0-.64-.08-.925-.232a2.022 2.022 0 0 1-.717-.645 2.108 2.108 0 0 1-.242-1.883l-2.36-7.201C5.769 3.54 5.96 3 7.365 3c2.072 0 4.276.678 6.156 1.256.473.145.925.284 1.35.404h.114v9.862a25.485 25.485 0 0 0-4.238 5.514c-.197.376-.516.67-.901.83a1.74 1.74 0 0 1-1.21.048 1.79 1.79 0 0 1-.96-.757 1.867 1.867 0 0 1-.269-1.211l1.562-4.63ZM19.822 14H17V6a2 2 0 1 1 4 0v6.823c0 .65-.527 1.177-1.177 1.177Z" clip-rule="evenodd"/></svg>"""


def _instant_js_like(like_id: str, dislike_id: str) -> str:
    # čistě klientský swap (okamžitý)
    return f"""
    (function(){{
        const like = document.getElementById('{like_id}');
        const dislike = document.getElementById('{dislike_id}');
        if (!like || !dislike) return;
        like.innerHTML = `{LIKE_SELECTED}`;
        dislike.innerHTML = `{DISLIKE_DEFAULT}`;
    }})();"""


def _instant_js_dislike(like_id: str, dislike_id: str) -> str:
    return f"""
    (function(){{
        const like = document.getElementById('{like_id}');
        const dislike = document.getElementById('{dislike_id}');
        if (!like || !dislike) return;
        dislike.innerHTML = `{DISLIKE_SELECTED}`;
        like.innerHTML = `{LIKE_DEFAULT}`;
    }})();"""


def add_feedback_row(parent, query, question):
    """Like/Dislike: 1) okamžitý client-side swap, 2) backend commit, 3) případný revert při chybě."""
    state = FeedbackState()
    uid = uuid.uuid4().hex[:8]
    like_id = f"like-{uid}"
    dislike_id = f"dislike-{uid}"
    busy = {"v": False}  # jednoduchá ochrana proti dvojkliku

    with parent:
        row = ui.row().classes("feedback-row ml-12 gap-1 -mt-2 mb-2")

        with row:
            like_btn = ui.html(
                f'<button id="{like_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">'
                f"{LIKE_DEFAULT}</button>"
            )
            dislike_btn = ui.html(
                f'<button id="{dislike_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">'
                f"{DISLIKE_DEFAULT}</button>"
            )

            async def commit_like(_):
                if busy["v"]:
                    return
                busy["v"] = True

                # 1) okamžitý vizuální swap (klient)
                await ui.run_javascript(_instant_js_like(like_id, dislike_id))

                try:
                    # 2) backend commit
                    await on_like_click(
                        like_btn,
                        dislike_btn,
                        state,
                        {
                            "like_default": LIKE_DEFAULT,
                            "like_selected": LIKE_SELECTED,
                            "dislike_default": DISLIKE_DEFAULT,
                            "dislike_selected": DISLIKE_SELECTED,
                        },
                        on_commit=(query, question),
                    )
                    # 2b) synchronizace serverového stavu (aby se DOM = server)
                    like_btn.content = f'<button id="{like_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">{LIKE_SELECTED}</button>'
                    dislike_btn.content = f'<button id="{dislike_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">{DISLIKE_DEFAULT}</button>'
                    like_btn.update()
                    dislike_btn.update()
                except Exception:
                    log.exception("Like commit failed")
                    # 3) revert vizuálu
                    await ui.run_javascript(
                        f"""
                        const like = document.getElementById('{like_id}');
                        const dislike = document.getElementById('{dislike_id}');
                        if (like && dislike) {{
                            like.innerHTML = `{LIKE_DEFAULT}`;
                            dislike.innerHTML = `{DISLIKE_DEFAULT}`;
                        }}
                    """
                    )
                finally:
                    busy["v"] = False

            async def commit_dislike(_):
                if busy["v"]:
                    return
                busy["v"] = True

                # 1) okamžitý vizuální swap (klient)
                await ui.run_javascript(_instant_js_dislike(like_id, dislike_id))

                try:
                    # 2) backend commit
                    await on_dislike_click(
                        like_btn,
                        dislike_btn,
                        state,
                        {
                            "like_default": LIKE_DEFAULT,
                            "like_selected": LIKE_SELECTED,
                            "dislike_default": DISLIKE_DEFAULT,
                            "dislike_selected": DISLIKE_SELECTED,
                        },
                        "dislike",
                    )
                    # 2b) synchronizace serverového stavu
                    like_btn.content = f'<button id="{like_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">{LIKE_DEFAULT}</button>'
                    dislike_btn.content = f'<button id="{dislike_id}" style="background:none;border:none;padding:2px;cursor:pointer;display:inline-flex;align-items:center;">{DISLIKE_SELECTED}</button>'
                    like_btn.update()
                    dislike_btn.update()
                except Exception:
                    log.exception("Dislike commit failed")
                    # 3) revert vizuálu
                    await ui.run_javascript(
                        f"""
                        const like = document.getElementById('{like_id}');
                        const dislike = document.getElementById('{dislike_id}');
                        if (like && dislike) {{
                            like.innerHTML = `{LIKE_DEFAULT}`;
                            dislike.innerHTML = `{DISLIKE_DEFAULT}`;
                        }}
                    """
                    )
                finally:
                    busy["v"] = False

            # serverové handlery (UI swap proběhne nahoře přes run_javascript)
            like_btn.on("click", commit_like)
            dislike_btn.on("click", commit_dislike)

    return row
