from nicegui import ui


def build_history_ui(parent, history):
    """Vykreslí přehled konverzací (Q/A) do daného parent kontejneru.
    Parametr `history` je instance UserChatHistory (má get_all_history()).
    """
    with parent:
        ui.label("Conversation history").classes("font-bold mb-2")
        # znovu vykresli celý obsah (jednoduchá verze)
        for q, a in history.get_all_history():
            with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                ui.markdown(f"**Q:** {q}")
                ui.markdown(f"**A:** {a}")


def rebuild_history_container(container, history):
    """Pomocník pro refresh: smaže a přestaví obsah containeru dle `history`."""
    container.clear()
    with container:
        for q, a in history.get_all_history():
            with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                ui.markdown(f"**Q:** {q}")
                ui.markdown(f"**A:** {a}")
