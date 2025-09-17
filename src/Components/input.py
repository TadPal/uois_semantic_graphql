from nicegui import ui


def build_chat_input(on_send, placeholder: str = "Type a message..."):
    """Vykreslí chat footer s inputem a Send tlačítkem.
    Vrací referenci na `ui.input`, abys s ní mohl pracovat v okolním scope.

    Args:
        on_send: callback (async nebo sync) volaný při Enter i kliknutí na tlačítko
        placeholder: text v inputu

    Returns:
        ui.input instance (např. ji uložíš do proměnné `text`)
    """
    with ui.row().classes("w-full justify-center"):
        with ui.card().classes(
            "w-full max-w-2xl rounded-2xl shadow-2xl light:bg-white dark:bg-neutral-900"
        ):
            with ui.row().classes("items-center w-full no-wrap"):
                text = (
                    ui.input(placeholder=placeholder)
                    .props("borderless dense input-class")
                    .classes("flex-grow px-3")
                    .on("keydown.enter", on_send)
                )
                ui.button(on_click=on_send).props(
                    "flat round dense color=primary icon=send"
                ).classes("ml-auto")
    return text
