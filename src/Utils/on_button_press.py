# feedback_handlers.py
from dataclasses import dataclass

# provides a decorator and functions for automatically adding generated special methods such as __init__() and __repr__() to user-defined classes
#* https://docs.python.org/3/library/dataclasses.html
@dataclass
class FeedbackState:
    like: bool = False
    dislike: bool = False
    locked: bool = False


def _btn_html(kind: str, pressed: bool, svgs: dict,  disabled: bool = False) -> str:
    """Vyrenderuje <button> s příslušným SVG a správnými ARIA atributy."""
    if kind == "like":
        svg = svgs["like_selected"] if pressed else svgs["like_default"]
        label = "Like"
        title = "Označit jako užitečné"
    elif kind == "dislike":
        svg = svgs["dislike_selected"] if pressed else svgs["dislike_default"]
        label = "Dislike"
        title = "Označit jako neužitečné"
    else:
        raise ValueError("Unknown kind")

    # Button je fokusovatelný, přístupný a má konzistentní velikost přes Tailwind utility.
    # `aria-pressed` vyjadřuje stav toggle pro čtečky.
    disabled_attrs = (
        ' disabled aria-disabled="true" tabindex="-1" '
        ' class="inline-flex items-center justify-center w-8 h-8 rounded-md opacity-50 pointer-events-none" '
        if disabled else
        ' class="inline-flex items-center justify-center w-8 h-8 rounded-md focus:outline-none focus:ring focus:ring-offset-2 focus:ring-blue-500" '
    )

    return f'''
    <button type="button" aria-pressed="{str(pressed).lower()}" aria-label="{label}" title="{title}" {disabled_attrs}>
        {svg}
    </button>
    '''


def render_buttons(state: FeedbackState, svgs: dict) -> tuple[str, str]:
    """Vrátí HTML obou tlačítek pro úvodní render."""
    return (
        _btn_html("like", state.like, svgs),
        _btn_html("dislike", state.dislike, svgs),
    )

def _disable_both(like_btn, dislike_btn, state: FeedbackState, svgs: dict):
    state.locked = True
    like_btn.set_content(_btn_html("like", state.like, svgs, disabled=True))
    dislike_btn.set_content(_btn_html("dislike", state.dislike, svgs, disabled=True))


def on_like_click(like_btn, dislike_btn, state: FeedbackState, svgs: dict, on_commit=None):
    #! safeguard
    if state.locked:
        return
    
    if state.like:
        state.like = False
        like_btn.set_content(_btn_html("like", state.like, svgs, disabled=False))
        return

    if not state.dislike:
        state.like = True
        like_btn.set_content(_btn_html("like", state.like, svgs, disabled=False))

        if on_commit:
            print(f'{on_commit}')  # např. uloží do DB
        _disable_both(like_btn, dislike_btn, state, svgs)


def on_dislike_click(like_btn, dislike_btn, state: FeedbackState, svgs: dict, on_commit=None):
    #! safeguard
    if state.locked:
        return

    if state.dislike:
        # vypnout dislike
        state.dislike = False
        dislike_btn.set_content(_btn_html("dislike", state.dislike, svgs, disabled=False))
        return

    if not state.like:
        # zapnout dislike
        state.dislike = True
        dislike_btn.set_content(_btn_html("dislike", state.dislike, svgs, disabled=False))

        if on_commit:
            print(f'{on_commit}')  # např. uloží do DB
        _disable_both(like_btn, dislike_btn, state, svgs)
