import json
import time
from pathlib import Path
from nicegui import ui
from src.Utils.log_bus import LOG_BUS, LEVEL_COLORS


def build_logs_ui(parent):
    """Vykreslí panel s logy do daného parent kontejneru (NiceGUI)."""
    state = {
        "running": True,
        "tail": 500,
        "level": "ALL",  # SINGLE select: ALL / DEBUG / INFO / WARNING / ERROR / CRITICAL
        "logger_filter": "",
        "search": "",
        "autoscroll": False,
        "user_filter": "",
        "open_keys": set(),
    }

    def normalize_level(x: str | None) -> str | None:
        if not x:
            return x
        x = str(x).upper()
        aliases = {"WARN": "WARNING", "FATAL": "CRITICAL", "CRIT": "CRITICAL"}
        return aliases.get(x, x)

    def make_key(r: dict) -> str:
        return f"{r.get('ts','')}|{r.get('logger','')}|{r.get('module','')}|{r.get('line','')}"

    def passes_for_view(r: dict) -> bool:
        if state["level"] != "ALL":
            if normalize_level(r.get("level")) != normalize_level(state["level"]):
                return False
        if lf := state["logger_filter"].strip().lower():
            cand = (r.get("logger", "") + "." + r.get("module", "")).lower()
            if lf not in cand:
                return False
        if uf := state["user_filter"].strip().lower():
            if uf not in (str(r.get("user_id", "")) or "").lower():
                return False
        if s := state["search"].strip().lower():
            hay = " ".join(
                [
                    r.get("message", ""),
                    r.get("logger", ""),
                    r.get("module", ""),
                    r.get("exc_text", "") or "",
                    str(r.get("extra", "") or ""),
                ]
            ).lower()
            if s not in hay:
                return False
        return True

    def export_ndjson():
        # uloží do src/tmp/ (změň podle potřeby)
        base_dir = Path(__file__).resolve().parent.parent / "tmp"
        base_dir.mkdir(parents=True, exist_ok=True)

        rows = LOG_BUS.get_last(state["tail"])
        if state["level"] != "ALL":
            lvl = normalize_level(state["level"])
            rows = [r for r in rows if normalize_level(r.get("level")) == lvl]

        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = "ALL" if state["level"] == "ALL" else normalize_level(state["level"])
        path = base_dir / f"logs-{suffix}-{ts}.ndjson"

        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        ui.download(str(path))

    with parent:
        with ui.row().classes("items-end gap-3"):
            level_select = ui.select(
                options=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                value="ALL",
                label="Level",
                with_input=False,
                clearable=False,
            )
            level_select.bind_value(state, "level")

            logger_in = ui.input("Logger/module contains")
            logger_in.on(
                "update:model-value",
                lambda e: (state.update(logger_filter=e.args or ""), paint.refresh()),
            )

            user_in = ui.input("User ID contains")
            user_in.on(
                "update:model-value",
                lambda e: (state.update(user_filter=e.args or ""), paint.refresh()),
            )

            search_in = ui.input("Search in message/traceback")
            search_in.on(
                "update:model-value",
                lambda e: (state.update(search=e.args or ""), paint.refresh()),
            )

            ui.number("Tail", value=500, min=50, max=10000, step=50).on(
                "change",
                lambda e: (state.update(tail=int(e.args or 500)), paint.refresh()),
            )

            ui.button("Export NDJSON", on_click=export_ndjson)

        container = ui.column().classes("w-full gap-0")

        @ui.refreshable
        def paint():
            container.clear()
            rows = LOG_BUS.get_last(state["tail"])

            for r in (rr for rr in rows if passes_for_view(rr)):
                row_key = make_key(r)
                with ui.card().classes("w-full mb-1"):
                    with ui.row().classes("w-full items-start gap-2 no-wrap"):
                        ui.label(r.get("iso", "")).classes(
                            "text-xs text-gray-500"
                        ).style("min-width: 140px")
                        ui.html(
                            f"<b style='color:{LEVEL_COLORS.get(r.get('level','INFO'), '#374151')}'>{r.get('level')}</b>"
                        )
                        ui.label(
                            f"{r.get('logger','')}.{r.get('module','')}:{r.get('line','')}"
                        ).classes("text-xs text-gray-600")
                        ui.label(r.get("message", "")).classes("text-sm break-words")
                        if r.get("user_id"):
                            ui.badge(f"user:{r['user_id']}").classes("text-[10px]")
                        if r.get("req_id"):
                            ui.badge(f"req:{r['req_id']}").classes("text-[10px]")

                    if r.get("exc_text"):
                        exp = ui.expansion(
                            "Traceback", value=(row_key in state["open_keys"])
                        )

                        def on_expansion_toggle(e, k=row_key):
                            is_open = bool(e.args)
                            if is_open:
                                state["open_keys"].add(k)
                                state["autoscroll"] = False
                                state["running"] = False
                            else:
                                state["open_keys"].discard(k)
                                if not state["open_keys"]:
                                    state["running"] = True
                            paint.refresh()

                        exp.on("update:model-value", on_expansion_toggle)

                        with exp:
                            ui.markdown(f"```\n{r['exc_text']}\n```")

            if state["autoscroll"]:
                ui.run_javascript("window.scrollTo(0, document.body.scrollHeight);")

        paint()

        def on_timer():
            if state["running"]:
                paint.refresh()

        ui.timer(0.5, on_timer)

    # sticky panel pro ovládání
    ui.add_css(".q-page-sticky{z-index:10000;}")
    with ui.page_sticky(position="bottom-left", x_offset=16, y_offset=16):
        with ui.column().classes("gap-2"):
            with ui.row().classes(
                "bg-white/90 dark:bg-neutral-800/90 backdrop-blur rounded-xl shadow-lg "
                "px-3 py-2 items-center gap-3 pointer-events-auto"
            ):
                ui.label("Autoscroll").classes("text-xs text-gray-600")
                ui.switch().bind_value(state, "autoscroll")
                ui.badge().bind_text_from(
                    state, "autoscroll", backward=lambda v: "ON" if v else "OFF"
                )

            with ui.row().classes(
                "bg-white/90 dark:bg-neutral-800/90 backdrop-blur rounded-xl shadow-lg "
                "px-3 py-2 items-center gap-3 pointer-events-auto"
            ):
                ui.label("Logs feed").classes("text-xs text-gray-600")
                ui.button("Pause", on_click=lambda: state.update(running=False))
                ui.button("Resume", on_click=lambda: state.update(running=True))
                ui.badge().bind_text_from(
                    state, "running", backward=lambda v: "RUNNING" if v else "PAUSED"
                )
