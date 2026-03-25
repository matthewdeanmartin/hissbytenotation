"""HBN GUI — Tkinter interface for hissbytenotation.

Single-file GUI following the architecture spec in spec/tkinter.md.
Panels: Dashboard, Browse, Query, Mutate, Merge, Diff, REPL, Generate, Doctor.
"""

from __future__ import annotations

import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk
from pathlib import Path
from typing import Any

# ── Dark theme colours (Catppuccin Mocha inspired) ──────────────────
_CLR_OK = "#22c55e"
_CLR_WARN = "#eab308"
_CLR_ERR = "#ef4444"
_CLR_DIM = "#9ca3af"
_CLR_BG = "#1e1e2e"
_CLR_BG_ALT = "#252536"
_CLR_FG = "#cdd6f4"
_CLR_ACCENT = "#89b4fa"
_CLR_SIDEBAR = "#181825"
_CLR_BTN = "#313244"
_CLR_BTN_ACTIVE = "#45475a"
_CLR_PANEL_BG = "#1a1a2a"

_FONT_UI = ("Segoe UI", 10)
_FONT_UI_BOLD = ("Segoe UI", 10, "bold")
_FONT_MONO = ("Consolas", 10)
_FONT_MONO_SMALL = ("Consolas", 9)
_FONT_HEADING = ("Segoe UI", 12, "bold")
_FONT_CHEAT = ("Consolas", 9)


# ── Background runner ───────────────────────────────────────────────

class _BackgroundRunner:
    """Run functions off the UI thread and post results back via root.after."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root

    def run(
        self,
        func: Any,
        *,
        args: tuple[Any, ...] = (),
        on_success: Any = None,
        on_error: Any = None,
    ) -> None:
        def _worker() -> None:
            try:
                result = func(*args)
            except Exception as exc:
                if on_error:
                    self._root.after(0, on_error, exc)
                return
            if on_success:
                self._root.after(0, on_success, result)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


# ── Reusable widget helpers ─────────────────────────────────────────

def _make_tree(parent: tk.Widget, columns: list[tuple[str, str, int]], height: int = 12) -> ttk.Treeview:
    """Create a themed treeview with scrollbar and colour tags."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Path.Treeview",
        background=_CLR_BG_ALT,
        foreground=_CLR_FG,
        fieldbackground=_CLR_BG_ALT,
        font=_FONT_MONO,
        rowheight=22,
    )
    style.configure("Path.Treeview.Heading", background=_CLR_BTN, foreground=_CLR_FG, font=_FONT_UI_BOLD)
    style.map("Path.Treeview", background=[("selected", _CLR_BTN_ACTIVE)])

    frame = tk.Frame(parent, bg=_CLR_BG)
    frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    col_ids = [c[0] for c in columns]
    tree = ttk.Treeview(frame, columns=col_ids, show="headings", height=height, style="Path.Treeview")
    for col_id, heading, width in columns:
        tree.heading(col_id, text=heading)
        tree.column(col_id, width=width, minwidth=40)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    tree.tag_configure("ok", foreground=_CLR_OK)
    tree.tag_configure("warn", foreground=_CLR_WARN)
    tree.tag_configure("error", foreground=_CLR_ERR)
    tree.tag_configure("dim", foreground=_CLR_DIM)
    return tree


def _make_output(parent: tk.Widget, height: int = 16) -> tk.Text:
    """Create a read-only scrolled text area."""
    frame = tk.Frame(parent, bg=_CLR_BG)
    frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    text = tk.Text(
        frame,
        height=height,
        bg=_CLR_BG_ALT,
        fg=_CLR_FG,
        insertbackground=_CLR_FG,
        font=_FONT_MONO,
        wrap=tk.NONE,
        state=tk.DISABLED,
        relief=tk.FLAT,
        padx=6,
        pady=4,
    )
    v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
    text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    text.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll.grid(row=1, column=0, sticky="ew")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    return text


def _make_input(parent: tk.Widget, height: int = 6) -> tk.Text:
    """Create an editable text area for user input."""
    frame = tk.Frame(parent, bg=_CLR_BG)
    frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    text = tk.Text(
        frame,
        height=height,
        bg=_CLR_BG_ALT,
        fg=_CLR_FG,
        insertbackground=_CLR_FG,
        font=_FONT_MONO,
        wrap=tk.NONE,
        relief=tk.FLAT,
        padx=6,
        pady=4,
    )
    v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=v_scroll.set)
    text.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    return text


def _output_set(text_widget: tk.Text, content: str) -> None:
    """Replace text content in a read-only text widget."""
    text_widget.configure(state=tk.NORMAL)
    text_widget.delete("1.0", tk.END)
    text_widget.insert("1.0", content)
    text_widget.configure(state=tk.DISABLED)


def _make_toolbar(parent: tk.Widget) -> tk.Frame:
    """Create a horizontal toolbar frame."""
    bar = tk.Frame(parent, bg=_CLR_BG)
    bar.pack(fill=tk.X, padx=8, pady=4)
    return bar


def _toolbar_btn(bar: tk.Frame, text: str, command: Any) -> tk.Button:
    """Create a themed button inside a toolbar."""
    btn = tk.Button(
        bar,
        text=text,
        command=command,
        bg=_CLR_BTN,
        fg=_CLR_FG,
        activebackground=_CLR_BTN_ACTIVE,
        activeforeground=_CLR_FG,
        font=_FONT_UI,
        relief=tk.FLAT,
        padx=12,
        pady=4,
        cursor="hand2",
    )
    btn.pack(side=tk.LEFT, padx=(0, 6))
    return btn


def _make_label(parent: tk.Widget, text: str, font: tuple[str, ...] | None = None) -> tk.Label:
    """Create a themed label."""
    return tk.Label(parent, text=text, bg=_CLR_BG, fg=_CLR_FG, font=font or _FONT_UI)


def _make_heading(parent: tk.Widget, text: str) -> tk.Label:
    """Create a section heading label."""
    lbl = tk.Label(parent, text=text, bg=_CLR_BG, fg=_CLR_ACCENT, font=_FONT_HEADING, anchor=tk.W)
    lbl.pack(fill=tk.X, padx=8, pady=(12, 4))
    return lbl


def _make_format_selector(parent: tk.Widget, variable: tk.StringVar, formats: list[str]) -> tk.Frame:
    """Create a row of radio buttons for format selection."""
    frame = tk.Frame(parent, bg=_CLR_BG)
    frame.pack(fill=tk.X, padx=8, pady=2)
    _make_label(frame, "Format:").pack(side=tk.LEFT, padx=(0, 8))
    for fmt in formats:
        rb = tk.Radiobutton(
            frame,
            text=fmt.upper(),
            variable=variable,
            value=fmt,
            bg=_CLR_BG,
            fg=_CLR_FG,
            selectcolor=_CLR_BTN,
            activebackground=_CLR_BG,
            activeforeground=_CLR_ACCENT,
            font=_FONT_UI,
        )
        rb.pack(side=tk.LEFT, padx=4)
    return frame


def _make_cheat_panel(parent: tk.Widget, title: str, content: str, width: int = 32) -> tk.Frame:
    """Create a collapsible cheat-sheet side panel."""
    container = tk.Frame(parent, bg=_CLR_SIDEBAR, width=width * 7)
    container.pack_propagate(False)

    heading = tk.Label(
        container, text=title, bg=_CLR_SIDEBAR, fg=_CLR_ACCENT,
        font=_FONT_UI_BOLD, anchor=tk.W, padx=8, pady=6,
    )
    heading.pack(fill=tk.X)

    sep = tk.Frame(container, bg=_CLR_BTN, height=1)
    sep.pack(fill=tk.X, padx=4)

    text = tk.Text(
        container,
        bg=_CLR_SIDEBAR,
        fg=_CLR_FG,
        font=_FONT_CHEAT,
        wrap=tk.WORD,
        relief=tk.FLAT,
        padx=8,
        pady=6,
        state=tk.NORMAL,
        cursor="arrow",
        borderwidth=0,
    )
    text.insert("1.0", content)
    text.configure(state=tk.DISABLED)
    text.pack(fill=tk.BOTH, expand=True)
    return container


# ── Base panel ──────────────────────────────────────────────────────

class _BasePanel(tk.Frame):
    """Base class for all panels."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, bg=_CLR_BG)
        self._runner = runner
        self._status = status_var
        self._app = app


# ── Dashboard Panel ─────────────────────────────────────────────────

_HBN_CHEAT = """\
HBN = Hiss Byte Notation

Python literals as a data format.
Parsed with ast.literal_eval.

TYPES SUPPORTED
  str      'hello'
  bytes    b'data'
  int      42  -7
  float    3.14
  bool     True  False
  None     None
  ...      Ellipsis
  list     [1, 2, 3]
  tuple    (1, 2, 3)
  set      {1, 2, 3}
  dict     {'k': 'v'}

NESTING
  {'users': [
    {'name': 'Alice',
     'age': 30}
  ]}

FILES
  .hbn .py  → HBN format
  .json     → JSON (in/out)
  .toml     → TOML (input)
  .xml      → XML (in/out)
  .bash     → BMN (in/out)

SHELL OUTPUT FLAGS
  --raw          scalar text
  --lines        one item/line
  --bash-array   Bash array
  --bash-assoc   Bash assoc
"""


class DashboardPanel(_BasePanel):
    """Welcome screen with quick actions and current data summary."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)

        # Horizontal split: main content + cheat sheet
        pane = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        pane.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(pane, bg=_CLR_BG)
        pane.add(left, stretch="always")

        _make_heading(left, "HBN Explorer")

        info_text = (
            "Welcome to the Hiss Byte Notation GUI.\n\n"
            "Use the sidebar to navigate between panels:\n\n"
            "  Browse      Load and inspect .hbn files\n"
            "  Query       Run glom queries on loaded data\n"
            "  Mutate      Set, delete, append, insert values\n"
            "  Merge       Merge two data sources\n"
            "  Diff        Compare two data sources\n"
            "  REPL        Interactive command shell\n"
            "  Generate    Create random sample data\n"
            "  Doctor      Check optional capabilities\n"
        )
        self._output = _make_output(left, height=14)
        _output_set(self._output, info_text)

        toolbar = _make_toolbar(left)
        _toolbar_btn(toolbar, "Open File...", self._open_file)
        _toolbar_btn(toolbar, "Generate Sample", self._generate_sample)
        _toolbar_btn(toolbar, "Format (Black)", self._format_value)
        self._fmt_status = _make_label(left, "", font=_FONT_MONO_SMALL)
        self._fmt_status.pack(fill=tk.X, padx=8)

        cheat = _make_cheat_panel(pane, "HBN Notation", _HBN_CHEAT, width=30)
        pane.add(cheat, minsize=180, stretch="never")

        if app.current_value is not None:
            self._show_summary()

    def _show_summary(self) -> None:
        value = self._app.current_value
        if value is None:
            return
        from hissbytenotation import dumps
        try:
            text = dumps(value, validate=False)
        except Exception:
            text = repr(value)
        summary = f"Current value ({type(value).__name__}):\n\n{text}"
        _output_set(self._output, summary)

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open HBN File",
            filetypes=[("HBN files", "*.hbn *.py"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._app.load_file(path)

    def _generate_sample(self) -> None:
        self._app.show_panel("generate")

    def _format_value(self) -> None:
        if self._app.current_value is None:
            self._fmt_status.configure(text="No data loaded.", fg=_CLR_WARN)
            return
        self._runner.run(
            self._do_format,
            args=(self._app.current_value,),
            on_success=self._on_format_success,
            on_error=self._on_format_error,
        )

    @staticmethod
    def _do_format(value: Any) -> str:
        import importlib.util
        from hissbytenotation import dumps
        raw = dumps(value, validate=False)
        if importlib.util.find_spec("black") is None:
            raise RuntimeError("black not installed — run: uv sync --extra fmt")
        import black  # type: ignore[import]
        return black.format_str(raw, mode=black.FileMode(line_length=120))

    def _on_format_success(self, text: str) -> None:
        _output_set(self._output, text)
        self._fmt_status.configure(text="Formatted with Black.", fg=_CLR_OK)

    def _on_format_error(self, exc: Exception) -> None:
        msg = str(exc)
        if "black not installed" in msg:
            self._fmt_status.configure(
                text="Formatter not installed.  Run:  uv sync --extra fmt", fg=_CLR_WARN,
            )
        else:
            self._fmt_status.configure(text=f"Format error: {msg}", fg=_CLR_ERR)


# ── Browse Panel ────────────────────────────────────────────────────

class BrowsePanel(_BasePanel):
    """Load and view HBN files."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)
        _make_heading(self, "Browse Data")

        toolbar = _make_toolbar(self)
        _toolbar_btn(toolbar, "Open File...", self._open_file)
        _toolbar_btn(toolbar, "Save As...", self._save_as)
        self._format_var = tk.StringVar(value="hbn")
        _make_format_selector(self, self._format_var, ["hbn", "json", "xml", "bmn"])

        # Display options
        opt_bar = _make_toolbar(self)
        self._pretty_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opt_bar, text="Pretty", variable=self._pretty_var, command=self._refresh,
            bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_BTN, activebackground=_CLR_BG, font=_FONT_UI,
        ).pack(side=tk.LEFT, padx=4)
        self._sort_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            opt_bar, text="Sort Keys", variable=self._sort_var, command=self._refresh,
            bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_BTN, activebackground=_CLR_BG, font=_FONT_UI,
        ).pack(side=tk.LEFT, padx=4)

        # Path label
        self._path_label = _make_label(self, "No file loaded", font=_FONT_MONO_SMALL)
        self._path_label.pack(fill=tk.X, padx=8, pady=2)

        # Type/size info
        self._info_label = _make_label(self, "", font=_FONT_UI)
        self._info_label.pack(fill=tk.X, padx=8, pady=2)

        self._output = _make_output(self, height=20)
        self._refresh()

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open File",
            filetypes=[("HBN files", "*.hbn *.py"), ("JSON files", "*.json"), ("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if path:
            self._app.load_file(path)
            self._refresh()

    def _save_as(self) -> None:
        if self._app.current_value is None:
            messagebox.showwarning("No Data", "Load data first before saving.")
            return
        fmt = self._format_var.get()
        ext_map = {"hbn": ".hbn", "json": ".json", "xml": ".xml", "bmn": ".bash"}
        path = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=ext_map.get(fmt, ".hbn"),
            filetypes=[("HBN files", "*.hbn"), ("JSON files", "*.json"), ("XML files", "*.xml"), ("All files", "*.*")],
        )
        if not path:
            return
        self._runner.run(
            self._do_save,
            args=(self._app.current_value, path, fmt, self._pretty_var.get(), self._sort_var.get()),
            on_success=lambda _: self._status.set(f"Saved to {path}"),
            on_error=lambda e: messagebox.showerror("Save Error", str(e)),
        )

    @staticmethod
    def _do_save(value: Any, path: str, fmt: str, pretty: bool, sort_keys: bool) -> None:
        from hissbytenotation.cli.codecs import render_value
        text = render_value(value, fmt, pretty=pretty, sort_keys=sort_keys)
        if text and not text.endswith("\n"):
            text += "\n"
        Path(path).write_text(text, encoding="utf-8")

    def _refresh(self) -> None:
        value = self._app.current_value
        if value is None:
            _output_set(self._output, "No data loaded. Use 'Open File' or the Generate panel.")
            self._path_label.configure(text="No file loaded")
            self._info_label.configure(text="")
            return
        path = self._app.current_path
        self._path_label.configure(text=path or "(in-memory)")
        type_name = type(value).__name__
        size_info = ""
        if isinstance(value, (list, tuple, dict, set, str, bytes)):
            size_info = f", length={len(value)}"
        self._info_label.configure(text=f"Type: {type_name}{size_info}")
        self._runner.run(
            self._render_value,
            args=(value, self._format_var.get(), self._pretty_var.get(), self._sort_var.get()),
            on_success=lambda text: _output_set(self._output, text),
            on_error=lambda e: _output_set(self._output, f"Render error: {e}"),
        )

    @staticmethod
    def _render_value(value: Any, fmt: str, pretty: bool, sort_keys: bool) -> str:
        from hissbytenotation.cli.codecs import render_value
        return render_value(value, fmt, pretty=pretty, sort_keys=sort_keys)


# ── Query Panel ─────────────────────────────────────────────────────

_QUERY_CHEAT = """\
PATH SYNTAX
  key           top-level key
  key.sub       nested dict key
  list.0        list index 0
  a.b.0.c       deep path

EXAMPLES
  users
  users.0
  users.0.email
  config.database.port

GLOM SPEC EXAMPLES
  ('users', ['email'])
    → list of all emails

  {'names': ('users', ['name']),
   'count': ('users', len)}
    → reshaped dict

  (T.upper(),)
    → transform scalar

TIPS
  • Path uses dots as separators
  • Integer segments = list index
  • Glom spec is a Python expression
  • Use HBN or JSON output format
"""

_FULL_DOC_PLACEHOLDER = "(no data loaded)"


class QueryPanel(_BasePanel):
    """Run glom queries on the current data."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)

        # Outer horizontal split: left work area + right side panels
        outer = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        outer.pack(fill=tk.BOTH, expand=True)

        work = tk.Frame(outer, bg=_CLR_BG)
        outer.add(work, stretch="always")

        _make_heading(work, "Query Data")

        if app.current_value is None:
            _make_label(work, "No data loaded. Load a file or generate data first.").pack(padx=8, pady=8)
            cheat = _make_cheat_panel(outer, "Query Cheat Sheet", _QUERY_CHEAT, width=30)
            outer.add(cheat, minsize=180, stretch="never")
            return

        # Query path input
        path_bar = _make_toolbar(work)
        _make_label(path_bar, "Path:").pack(side=tk.LEFT, padx=(0, 4))
        self._path_entry = tk.Entry(
            path_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO, width=40,
        )
        self._path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._path_entry.bind("<Return>", lambda _: self._run_query())
        _toolbar_btn(path_bar, "Query", self._run_query)

        # Glom spec input
        spec_bar = _make_toolbar(work)
        _make_label(spec_bar, "Glom Spec:").pack(side=tk.LEFT, padx=(0, 4))
        self._spec_entry = tk.Entry(
            spec_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO, width=40,
        )
        self._spec_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._spec_entry.bind("<Return>", lambda _: self._run_glom_query())
        _toolbar_btn(spec_bar, "Glom Query", self._run_glom_query)

        # Output format
        self._format_var = tk.StringVar(value="hbn")
        _make_format_selector(work, self._format_var, ["hbn", "json"])

        # Vertical split inside work: query result + full document
        vpane = tk.PanedWindow(work, orient=tk.VERTICAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        vpane.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        result_frame = tk.Frame(vpane, bg=_CLR_BG)
        vpane.add(result_frame, stretch="always")
        tk.Label(result_frame, text="Query Result", bg=_CLR_BG, fg=_CLR_DIM, font=_FONT_UI, anchor=tk.W).pack(
            fill=tk.X, padx=0, pady=(2, 0)
        )
        self._output = _make_output(result_frame, height=10)

        doc_frame = tk.Frame(vpane, bg=_CLR_BG)
        vpane.add(doc_frame, stretch="always")
        tk.Label(doc_frame, text="Full Document", bg=_CLR_BG, fg=_CLR_DIM, font=_FONT_UI, anchor=tk.W).pack(
            fill=tk.X, padx=0, pady=(2, 0)
        )
        self._doc_output = _make_output(doc_frame, height=8)
        self._refresh_doc()

        cheat = _make_cheat_panel(outer, "Query Cheat Sheet", _QUERY_CHEAT, width=30)
        outer.add(cheat, minsize=180, stretch="never")

        self._status.set("Enter a path like 'users.0.email' or a glom spec.")

    def _refresh_doc(self) -> None:
        value = self._app.current_value
        if value is None:
            _output_set(self._doc_output, _FULL_DOC_PLACEHOLDER)
            return
        self._runner.run(
            self._render_doc,
            args=(value,),
            on_success=lambda t: _output_set(self._doc_output, t),
            on_error=lambda e: _output_set(self._doc_output, f"Render error: {e}"),
        )

    @staticmethod
    def _render_doc(value: Any) -> str:
        from hissbytenotation.cli.codecs import render_value
        return render_value(value, "hbn", pretty=True)

    def _run_query(self) -> None:
        path_text = self._path_entry.get().strip()
        if not path_text:
            self._status.set("Enter a query path.")
            return
        self._status.set(f"Querying: {path_text}")
        self._runner.run(
            self._do_query,
            args=(self._app.current_value, path_text, None, self._format_var.get()),
            on_success=self._show_result,
            on_error=self._show_error,
        )

    def _run_glom_query(self) -> None:
        spec_text = self._spec_entry.get().strip()
        if not spec_text:
            self._status.set("Enter a glom spec.")
            return
        self._status.set("Querying with glom spec...")
        self._runner.run(
            self._do_query,
            args=(self._app.current_value, None, spec_text, self._format_var.get()),
            on_success=self._show_result,
            on_error=self._show_error,
        )

    @staticmethod
    def _do_query(value: Any, path_text: str | None, spec_text: str | None, fmt: str) -> str:
        from hissbytenotation.cli.glom_integration import query_value
        from hissbytenotation.cli.codecs import render_value
        result = query_value(value, path_text=path_text, spec_text=spec_text)
        return render_value(result, fmt, pretty=True)

    def _show_result(self, text: str) -> None:
        _output_set(self._output, text)
        self._status.set("Query complete.")

    def _show_error(self, exc: Exception) -> None:
        _output_set(self._output, f"Error: {exc}")
        self._status.set(f"Query failed: {exc}")


# ── Mutate Panel ────────────────────────────────────────────────────

_MUTATE_CHEAT = """\
PATH NOTATION
  Uses dot-separated segments.
  Integer segments = list index.

EXAMPLES
  key               top-level key
  a.b               nested dict
  users.0           first user
  users.0.email     user email
  config.tags.2     3rd tag

OPERATIONS
  set   PATH --value V
    Deep-set a value.
    Creates intermediate dicts.

  del   PATH
    Delete key or list item.

  append  PATH --value V
    Append V to the list at PATH.

  insert  PATH --index N --value V
    Insert V at position N in list.

VALUE FORMAT
  Values are HBN (Python literals):
    'hello'         string
    42              integer
    True / False    boolean
    None            null
    [1, 2, 3]       list
    {'k': 'v'}      dict

TIPS
  • Path must exist for set/del/append
  • insert requires the target to be a list
  • Result becomes the new current value
"""


class MutatePanel(_BasePanel):
    """Set, delete, append, insert values in the current data."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)

        outer = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        outer.pack(fill=tk.BOTH, expand=True)

        work = tk.Frame(outer, bg=_CLR_BG)
        outer.add(work, stretch="always")

        _make_heading(work, "Mutate Data")

        if app.current_value is None:
            _make_label(work, "No data loaded. Load a file or generate data first.").pack(padx=8, pady=8)
            cheat = _make_cheat_panel(outer, "Path Notation", _MUTATE_CHEAT, width=30)
            outer.add(cheat, minsize=180, stretch="never")
            return

        # Operation selector
        op_bar = _make_toolbar(work)
        _make_label(op_bar, "Operation:").pack(side=tk.LEFT, padx=(0, 4))
        self._op_var = tk.StringVar(value="set")
        for op in ["set", "del", "append", "insert"]:
            tk.Radiobutton(
                op_bar, text=op, variable=self._op_var, value=op,
                bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_BTN, activebackground=_CLR_BG, font=_FONT_UI,
            ).pack(side=tk.LEFT, padx=4)

        # Path
        path_bar = _make_toolbar(work)
        _make_label(path_bar, "Path:").pack(side=tk.LEFT, padx=(0, 4))
        self._path_entry = tk.Entry(
            path_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO, width=40,
        )
        self._path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Value
        value_bar = _make_toolbar(work)
        _make_label(value_bar, "Value (HBN):").pack(side=tk.LEFT, padx=(0, 4))
        self._value_entry = tk.Entry(
            value_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO, width=40,
        )
        self._value_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Index (for insert)
        idx_bar = _make_toolbar(work)
        _make_label(idx_bar, "Index (insert only):").pack(side=tk.LEFT, padx=(0, 4))
        self._index_entry = tk.Entry(
            idx_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO, width=10,
        )
        self._index_entry.pack(side=tk.LEFT, padx=4)
        self._index_entry.insert(0, "0")

        # Execute
        exec_bar = _make_toolbar(work)
        _toolbar_btn(exec_bar, "Execute", self._execute)

        self._output = _make_output(work, height=14)
        self._show_current()

        cheat = _make_cheat_panel(outer, "Path Notation", _MUTATE_CHEAT, width=30)
        outer.add(cheat, minsize=180, stretch="never")

    def _show_current(self) -> None:
        from hissbytenotation import dumps
        value = self._app.current_value
        try:
            text = dumps(value, validate=False)
        except Exception:
            text = repr(value)
        _output_set(self._output, text)

    def _execute(self) -> None:
        op = self._op_var.get()
        path_text = self._path_entry.get().strip()
        value_text = self._value_entry.get().strip()
        index_text = self._index_entry.get().strip()
        if not path_text:
            self._status.set("Enter a path.")
            return
        if op in ("set", "append", "insert") and not value_text:
            self._status.set("Enter a value.")
            return
        self._status.set(f"Executing {op}...")
        self._runner.run(
            self._do_mutate,
            args=(self._app.current_value, op, path_text, value_text, index_text),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    @staticmethod
    def _do_mutate(value: Any, op: str, path_text: str, value_text: str, index_text: str) -> Any:
        from hissbytenotation.cli.glom_integration import set_value, delete_value, append_value, insert_value
        from hissbytenotation.cli.codecs import parse_value
        if op == "set":
            new_val = parse_value(value_text, "hbn")
            return set_value(value, path_text, new_val)
        if op == "del":
            return delete_value(value, path_text)
        if op == "append":
            new_val = parse_value(value_text, "hbn")
            return append_value(value, path_text, new_val)
        if op == "insert":
            new_val = parse_value(value_text, "hbn")
            idx = int(index_text) if index_text else 0
            return insert_value(value, path_text, idx, new_val)
        raise ValueError(f"Unknown operation: {op}")

    def _on_success(self, result: Any) -> None:
        self._app.current_value = result
        self._show_current()
        self._status.set("Mutation applied.")

    def _on_error(self, exc: Exception) -> None:
        _output_set(self._output, f"Error: {exc}")
        self._status.set(f"Mutation failed: {exc}")


# ── Merge Panel ─────────────────────────────────────────────────────

class MergePanel(_BasePanel):
    """Merge two data sources."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)
        _make_heading(self, "Merge Data")

        # Left source
        _make_label(self, "Left (current value or paste HBN):", font=_FONT_UI_BOLD).pack(fill=tk.X, padx=8, pady=(8, 2))
        self._left_input = _make_input(self, height=6)
        if app.current_value is not None:
            from hissbytenotation import dumps
            try:
                self._left_input.insert("1.0", dumps(app.current_value, validate=False))
            except Exception:
                self._left_input.insert("1.0", repr(app.current_value))

        # Right source
        right_bar = _make_toolbar(self)
        _make_label(right_bar, "Right:", font=_FONT_UI_BOLD).pack(side=tk.LEFT, padx=(0, 4))
        _toolbar_btn(right_bar, "Load File...", self._load_right_file)
        _toolbar_btn(right_bar, "Generate Random", self._generate_random_right)
        self._right_input = _make_input(self, height=6)

        # Strategy and conflict
        opt_bar = _make_toolbar(self)
        _make_label(opt_bar, "Strategy:").pack(side=tk.LEFT, padx=(0, 4))
        self._strategy_var = tk.StringVar(value="deep")
        from hissbytenotation.cli.merge_ops import MERGE_STRATEGIES, CONFLICT_POLICIES
        strategy_combo = ttk.Combobox(opt_bar, textvariable=self._strategy_var, values=list(MERGE_STRATEGIES), state="readonly", width=16)
        strategy_combo.pack(side=tk.LEFT, padx=4)
        _make_label(opt_bar, "Conflict:").pack(side=tk.LEFT, padx=(8, 4))
        self._conflict_var = tk.StringVar(value="error")
        conflict_combo = ttk.Combobox(opt_bar, textvariable=self._conflict_var, values=list(CONFLICT_POLICIES), state="readonly", width=12)
        conflict_combo.pack(side=tk.LEFT, padx=4)
        _toolbar_btn(opt_bar, "Merge", self._execute_merge)

        self._output = _make_output(self, height=10)

    def _load_right_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Load Right Value",
            filetypes=[("HBN files", "*.hbn *.py"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                text = Path(path).read_text(encoding="utf-8")
                self._right_input.delete("1.0", tk.END)
                self._right_input.insert("1.0", text)
            except OSError as exc:
                messagebox.showerror("File Error", str(exc))

    def _generate_random_right(self) -> None:
        self._runner.run(
            self._do_generate_random,
            on_success=self._on_random_generated,
            on_error=lambda e: messagebox.showerror("Generate Error", str(e)),
        )

    @staticmethod
    def _do_generate_random() -> str:
        import random
        from hissbytenotation.gui.sample_data import GENERATORS
        from hissbytenotation.cli.codecs import render_value
        gen_func = random.choice(list(GENERATORS.values()))
        value = gen_func()
        return render_value(value, "hbn", pretty=True)

    def _on_random_generated(self, text: str) -> None:
        self._right_input.delete("1.0", tk.END)
        self._right_input.insert("1.0", text)
        self._status.set("Random right value generated.")

    def _execute_merge(self) -> None:
        left_text = self._left_input.get("1.0", tk.END).strip()
        right_text = self._right_input.get("1.0", tk.END).strip()
        if not left_text or not right_text:
            self._status.set("Both left and right values are required.")
            return
        self._status.set("Merging...")
        self._runner.run(
            self._do_merge,
            args=(left_text, right_text, self._strategy_var.get(), self._conflict_var.get()),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    @staticmethod
    def _do_merge(left_text: str, right_text: str, strategy: str, conflict: str) -> tuple[Any, str]:
        from hissbytenotation.cli.codecs import parse_value, render_value
        from hissbytenotation.cli.merge_ops import merge_values
        left = parse_value(left_text, "hbn")
        right = parse_value(right_text, "hbn")
        result = merge_values(left, right, strategy=strategy, conflict=conflict)
        return result, render_value(result, "hbn", pretty=True)

    def _on_success(self, result_tuple: tuple[Any, str]) -> None:
        value, text = result_tuple
        self._app.current_value = value
        _output_set(self._output, text)
        self._status.set("Merge complete. Result stored as current value.")

    def _on_error(self, exc: Exception) -> None:
        _output_set(self._output, f"Merge error: {exc}")
        self._status.set(f"Merge failed: {exc}")


# ── Diff Panel ──────────────────────────────────────────────────────

class DiffPanel(_BasePanel):
    """Compare two data sources."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)
        _make_heading(self, "Diff Data")

        # Left source
        left_bar = _make_toolbar(self)
        _make_label(left_bar, "Left:", font=_FONT_UI_BOLD).pack(side=tk.LEFT, padx=(0, 4))
        _toolbar_btn(left_bar, "Load File...", lambda: self._load_to(self._left_input))
        _toolbar_btn(left_bar, "Use Current", lambda: self._paste_current(self._left_input))
        _toolbar_btn(left_bar, "Generate Random", lambda: self._generate_random(self._left_input))
        self._left_input = _make_input(self, height=6)

        # Right source
        right_bar = _make_toolbar(self)
        _make_label(right_bar, "Right:", font=_FONT_UI_BOLD).pack(side=tk.LEFT, padx=(0, 4))
        _toolbar_btn(right_bar, "Load File...", lambda: self._load_to(self._right_input))
        _toolbar_btn(right_bar, "Generate Random", lambda: self._generate_random(self._right_input))
        self._right_input = _make_input(self, height=6)

        # Options and execute
        opt_bar = _make_toolbar(self)
        self._format_var = tk.StringVar(value="hbn")
        _make_label(opt_bar, "Canonical:").pack(side=tk.LEFT, padx=(0, 4))
        for fmt in ["hbn", "json"]:
            tk.Radiobutton(
                opt_bar, text=fmt.upper(), variable=self._format_var, value=fmt,
                bg=_CLR_BG, fg=_CLR_FG, selectcolor=_CLR_BTN, activebackground=_CLR_BG, font=_FONT_UI,
            ).pack(side=tk.LEFT, padx=4)
        _toolbar_btn(opt_bar, "Diff", self._execute_diff)

        self._output = _make_output(self, height=12)

    def _load_to(self, target: tk.Text) -> None:
        path = filedialog.askopenfilename(
            title="Load Value",
            filetypes=[("HBN files", "*.hbn *.py"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                text = Path(path).read_text(encoding="utf-8")
                target.delete("1.0", tk.END)
                target.insert("1.0", text)
            except OSError as exc:
                messagebox.showerror("File Error", str(exc))

    def _paste_current(self, target: tk.Text) -> None:
        if self._app.current_value is None:
            messagebox.showinfo("No Data", "No current value loaded.")
            return
        from hissbytenotation import dumps
        try:
            text = dumps(self._app.current_value, validate=False)
        except Exception:
            text = repr(self._app.current_value)
        target.delete("1.0", tk.END)
        target.insert("1.0", text)

    def _generate_random(self, target: tk.Text) -> None:
        self._runner.run(
            self._do_generate_random,
            on_success=lambda t: self._on_random_ready(target, t),
            on_error=lambda e: messagebox.showerror("Generate Error", str(e)),
        )

    @staticmethod
    def _do_generate_random() -> str:
        import random
        from hissbytenotation.gui.sample_data import GENERATORS
        from hissbytenotation.cli.codecs import render_value
        gen_func = random.choice(list(GENERATORS.values()))
        value = gen_func()
        return render_value(value, "hbn", pretty=True)

    def _on_random_ready(self, target: tk.Text, text: str) -> None:
        target.delete("1.0", tk.END)
        target.insert("1.0", text)
        self._status.set("Random value generated.")

    def _execute_diff(self) -> None:
        left_text = self._left_input.get("1.0", tk.END).strip()
        right_text = self._right_input.get("1.0", tk.END).strip()
        if not left_text or not right_text:
            self._status.set("Both left and right values are required.")
            return
        self._status.set("Computing diff...")
        self._runner.run(
            self._do_diff,
            args=(left_text, right_text, self._format_var.get()),
            on_success=self._on_success,
            on_error=self._on_error,
        )

    @staticmethod
    def _do_diff(left_text: str, right_text: str, fmt: str) -> str:
        from hissbytenotation.cli.codecs import parse_value, render_value
        from hissbytenotation.cli.diff_ops import diff_texts
        left_val = parse_value(left_text, "hbn")
        right_val = parse_value(right_text, "hbn")
        left_canon = render_value(left_val, fmt, pretty=True, sort_keys=True)
        right_canon = render_value(right_val, fmt, pretty=True, sort_keys=True)
        if not left_canon.endswith("\n"):
            left_canon += "\n"
        if not right_canon.endswith("\n"):
            right_canon += "\n"
        _exit_code, output = diff_texts(
            left_canon, right_canon,
            left_label="left", right_label="right",
            tool="auto", context=3, output_format=fmt,
        )
        return output or "(No differences found)"

    def _on_success(self, text: str) -> None:
        _output_set(self._output, text)
        self._status.set("Diff complete.")

    def _on_error(self, exc: Exception) -> None:
        _output_set(self._output, f"Diff error: {exc}")
        self._status.set(f"Diff failed: {exc}")


# ── REPL Panel ──────────────────────────────────────────────────────

_RENDER_OPTIONS_HELP = """\
RENDER OPTIONS  (append to show/get/q)

OUTPUT FORMAT
  --to hbn          HBN (default)
  --to json         JSON
  --to xml          XML
  --to bmn          Bash Map Notation

STRUCTURE
  --pretty          indent + newlines
  --compact         minimal whitespace
  --sort-keys       sort dict keys
  --indent N        indentation width

SCALAR / SHELL OUTPUT
  --raw             bare string (no quotes)
                    requires scalar result
  --lines           one item per line
  --nul             one item per NUL byte

SHELL ASSIGNMENT
  --shell-quote     shell-escape a token
  --shell-assign N  emit  N='value'
  --shell-export N  emit  export N='value'

BASH ARRAYS
  --bash-array N    NAME=(a b c)
  --bash-assoc N    associative array
                    (flat dicts only)

FALLBACK
  --default VALUE   use VALUE when
                    result is empty

EXAMPLES
  show --pretty
  get config.port --raw
  q users --to json --pretty
  q tags --bash-array TAGS
  show --to json --sort-keys --compact
"""


class ReplPanel(_BasePanel):
    """Interactive REPL panel embedded in the GUI."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)

        outer = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        outer.pack(fill=tk.BOTH, expand=True)

        work = tk.Frame(outer, bg=_CLR_BG)
        outer.add(work, stretch="always")

        _make_heading(work, "REPL")

        from hissbytenotation.cli.repl import ReplSession, execute_line, REPL_HELP

        self._session = ReplSession(current_value=app.current_value, current_path=app.current_path)
        self._execute_line = execute_line

        # Output area
        self._output = _make_output(work, height=18)
        welcome = "HBN REPL (GUI). Type commands below.\n\n" + REPL_HELP
        _output_set(self._output, welcome)

        # Input area
        input_bar = _make_toolbar(work)
        _make_label(input_bar, "hbn>").pack(side=tk.LEFT, padx=(0, 4))
        self._input_entry = tk.Entry(
            input_bar, bg=_CLR_BG_ALT, fg=_CLR_FG, insertbackground=_CLR_FG, font=_FONT_MONO,
        )
        self._input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._input_entry.bind("<Return>", lambda _: self._execute())
        self._input_entry.bind("<Up>", lambda _: self._history_prev())
        self._input_entry.bind("<Down>", lambda _: self._history_next())
        _toolbar_btn(input_bar, "Run", self._execute)

        cheat = _make_cheat_panel(outer, "Render Options", _RENDER_OPTIONS_HELP, width=32)
        outer.add(cheat, minsize=200, stretch="never")

        self._history: list[str] = []
        self._history_index: int = -1
        self._input_entry.focus_set()

    def _execute(self) -> None:
        line = self._input_entry.get().strip()
        if not line:
            return
        self._history.append(line)
        self._history_index = -1
        self._input_entry.delete(0, tk.END)

        # Capture output
        import io
        import sys
        from hissbytenotation.cli.errors import CliError

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        buf = io.StringIO()
        sys.stdout = buf
        sys.stderr = buf
        try:
            should_exit = self._execute_line(self._session, line)
        except CliError as exc:
            buf.write(f"Error: {exc}\n")
            should_exit = False
        except Exception as exc:
            buf.write(f"Error: {exc}\n")
            should_exit = False
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        output_text = buf.getvalue()
        self._append_output(f"hbn> {line}\n{output_text}")

        # Sync session back to app
        self._app.current_value = self._session.current_value
        self._app.current_path = self._session.current_path

        if should_exit:
            self._status.set("REPL session ended.")
        else:
            self._status.set("Ready.")

    def _append_output(self, text: str) -> None:
        self._output.configure(state=tk.NORMAL)
        self._output.insert(tk.END, text)
        self._output.see(tk.END)
        self._output.configure(state=tk.DISABLED)

    def _history_prev(self) -> None:
        if not self._history:
            return
        if self._history_index == -1:
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self._input_entry.delete(0, tk.END)
        self._input_entry.insert(0, self._history[self._history_index])

    def _history_next(self) -> None:
        if not self._history or self._history_index == -1:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._input_entry.delete(0, tk.END)
            self._input_entry.insert(0, self._history[self._history_index])
        else:
            self._history_index = -1
            self._input_entry.delete(0, tk.END)


# ── Generate Panel ──────────────────────────────────────────────────

class GeneratePanel(_BasePanel):
    """Generate random sample data for exploration."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)
        _make_heading(self, "Generate Sample Data")

        from hissbytenotation.gui.sample_data import GENERATORS

        # Generator selector
        sel_bar = _make_toolbar(self)
        _make_label(sel_bar, "Template:").pack(side=tk.LEFT, padx=(0, 4))
        self._gen_var = tk.StringVar(value=list(GENERATORS.keys())[0])
        gen_combo = ttk.Combobox(sel_bar, textvariable=self._gen_var, values=list(GENERATORS.keys()), state="readonly", width=24)
        gen_combo.pack(side=tk.LEFT, padx=4)
        _toolbar_btn(sel_bar, "Generate", self._generate)
        _toolbar_btn(sel_bar, "Use as Current", self._use_as_current)
        _toolbar_btn(sel_bar, "Save As...", self._save_as)

        # Display format
        self._format_var = tk.StringVar(value="hbn")
        _make_format_selector(self, self._format_var, ["hbn", "json"])

        self._output = _make_output(self, height=20)
        self._last_value: Any = None

    def _generate(self) -> None:
        from hissbytenotation.gui.sample_data import GENERATORS
        name = self._gen_var.get()
        gen_func = GENERATORS.get(name)
        if not gen_func:
            return
        self._status.set(f"Generating {name}...")
        self._runner.run(
            self._do_generate,
            args=(gen_func, self._format_var.get()),
            on_success=self._on_success,
            on_error=lambda e: messagebox.showerror("Generate Error", str(e)),
        )

    @staticmethod
    def _do_generate(gen_func: Any, fmt: str) -> tuple[Any, str]:
        from hissbytenotation.cli.codecs import render_value
        value = gen_func()
        text = render_value(value, fmt, pretty=True)
        return value, text

    def _on_success(self, result: tuple[Any, str]) -> None:
        self._last_value, text = result
        _output_set(self._output, text)
        self._status.set("Generated. Click 'Use as Current' to load this data.")

    def _use_as_current(self) -> None:
        if self._last_value is None:
            self._status.set("Generate data first.")
            return
        self._app.current_value = self._last_value
        self._app.current_path = None
        self._status.set("Generated data loaded as current value.")

    def _save_as(self) -> None:
        if self._last_value is None:
            self._status.set("Generate data first.")
            return
        fmt = self._format_var.get()
        ext_map = {"hbn": ".hbn", "json": ".json"}
        path = filedialog.asksaveasfilename(
            title="Save Generated Data",
            defaultextension=ext_map.get(fmt, ".hbn"),
            filetypes=[("HBN files", "*.hbn"), ("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        from hissbytenotation.cli.codecs import render_value
        try:
            text = render_value(self._last_value, fmt, pretty=True)
            if text and not text.endswith("\n"):
                text += "\n"
            Path(path).write_text(text, encoding="utf-8")
            self._status.set(f"Saved to {path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))


# ── Doctor Panel ────────────────────────────────────────────────────

_STATUS_ICON = {True: "✓", False: "✗"}
_STATUS_TAG = {True: "ok", False: "error"}


class DoctorPanel(_BasePanel):
    """Show optional capability report as a formatted visual table."""

    def __init__(self, parent: tk.Widget, runner: _BackgroundRunner, status_var: tk.StringVar, app: HbnApp) -> None:
        super().__init__(parent, runner, status_var, app)
        _make_heading(self, "Doctor — Capability Report")

        toolbar = _make_toolbar(self)
        _toolbar_btn(toolbar, "Refresh", self._load)

        # Rich text output
        frame = tk.Frame(self, bg=_CLR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self._text = tk.Text(
            frame,
            bg=_CLR_BG_ALT,
            fg=_CLR_FG,
            font=_FONT_MONO,
            wrap=tk.NONE,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=12,
            pady=8,
        )
        v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=v_scroll.set)
        self._text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Text tags for colour
        self._text.tag_configure("ok", foreground=_CLR_OK)
        self._text.tag_configure("error", foreground=_CLR_ERR)
        self._text.tag_configure("warn", foreground=_CLR_WARN)
        self._text.tag_configure("dim", foreground=_CLR_DIM)
        self._text.tag_configure("accent", foreground=_CLR_ACCENT)
        self._text.tag_configure("bold", font=_FONT_UI_BOLD)
        self._text.tag_configure("heading", foreground=_CLR_ACCENT, font=("Segoe UI", 11, "bold"))
        self._text.tag_configure("mono", font=_FONT_MONO)

        self._load()

    def _load(self) -> None:
        self._status.set("Running doctor checks...")
        self._runner.run(
            self._fetch,
            on_success=self._display,
            on_error=self._on_error,
        )

    @staticmethod
    def _fetch() -> dict[str, Any]:
        from hissbytenotation.cli.doctor import collect_doctor_report
        return collect_doctor_report()

    def _display(self, report: dict[str, Any]) -> None:
        t = self._text
        t.configure(state=tk.NORMAL)
        t.delete("1.0", tk.END)

        def w(text: str, *tags: str) -> None:
            t.insert(tk.END, text, tags)

        def nl(n: int = 1) -> None:
            t.insert(tk.END, "\n" * n)

        # Package info
        pkg = report.get("package", {})
        w("  HBN Explorer — Capability Report\n", "heading")
        nl()
        w(f"  Package : ", "dim")
        w(f"{pkg.get('name', '?')} {pkg.get('version', '?')}\n", "mono")
        w(f"  Python  : ", "dim")
        w(f"{pkg.get('python', '?')}\n", "mono")
        nl()

        # Optional features
        w("  Optional Features\n", "heading")
        w("  " + "─" * 54 + "\n", "dim")
        features = report.get("optional_features", {})
        for name, info in features.items():
            ok = info.get("available", False)
            icon = _STATUS_ICON[ok]
            tag = _STATUS_TAG[ok]
            ver = info.get("version") or ""
            ver_str = f"  v{ver}" if ver else ""
            w(f"  {icon} ", tag)
            w(f"{name:<12}", "bold")
            w(f"{ver_str:<12}", "dim")
            w(f"  {info.get('summary', '')}\n")
            if not ok:
                hint = info.get("install_hint")
                if hint:
                    w(f"      → {hint}\n", "warn")
        nl()

        # Tools
        w("  System Tools\n", "heading")
        w("  " + "─" * 54 + "\n", "dim")
        tools = report.get("tools", {})
        for name, info in tools.items():
            ok = info.get("available", False)
            icon = _STATUS_ICON[ok]
            tag = _STATUS_TAG[ok]
            path_str = info.get("path") or "not found"
            w(f"  {icon} ", tag)
            w(f"{name:<12}", "bold")
            w(f"  {path_str}\n", "dim")
            w(f"      {info.get('summary', '')}\n")
        nl()

        # Recommendations
        recs = report.get("recommendations", [])
        if recs:
            w("  Recommendations\n", "heading")
            w("  " + "─" * 54 + "\n", "dim")
            for rec in recs:
                w(f"  • {rec}\n", "warn")
        else:
            w("  All optional features are available.\n", "ok")

        t.configure(state=tk.DISABLED)
        self._status.set("Doctor report ready.")

    def _on_error(self, exc: Exception) -> None:
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", f"Error running doctor: {exc}")
        self._text.configure(state=tk.DISABLED)
        self._status.set(f"Doctor failed: {exc}")


# ── Main Application ────────────────────────────────────────────────

class HbnApp:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("HBN Explorer")
        self.root.geometry("1100x720")
        self.root.configure(bg=_CLR_BG)
        self.root.minsize(800, 500)

        self.current_value: Any = None
        self.current_path: str | None = None

        self._runner = _BackgroundRunner(self.root)
        self._status_var = tk.StringVar(value="Ready.")

        self._current_panel: _BasePanel | None = None
        self._current_panel_name: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        # Main container
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=_CLR_BG, sashwidth=2, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        sidebar = tk.Frame(main, bg=_CLR_SIDEBAR, width=140)
        main.add(sidebar, minsize=120, stretch="never")

        # Title in sidebar
        title_lbl = tk.Label(
            sidebar, text="HBN", bg=_CLR_SIDEBAR, fg=_CLR_ACCENT,
            font=("Segoe UI", 16, "bold"), pady=12,
        )
        title_lbl.pack(fill=tk.X)

        items = [
            ("dashboard", "Dashboard"),
            ("browse", "Browse"),
            ("query", "Query"),
            ("mutate", "Mutate"),
            ("merge", "Merge"),
            ("diff", "Diff"),
            ("repl", "REPL"),
            ("generate", "Generate"),
            ("doctor", "Doctor"),
        ]

        self._sidebar_buttons: dict[str, tk.Button] = {}
        for panel_id, label in items:
            btn = tk.Button(
                sidebar,
                text=label,
                command=lambda pid=panel_id: self.show_panel(pid),
                bg=_CLR_SIDEBAR,
                fg=_CLR_FG,
                activebackground=_CLR_BTN_ACTIVE,
                activeforeground=_CLR_FG,
                font=_FONT_UI,
                relief=tk.FLAT,
                anchor=tk.W,
                padx=16,
                pady=6,
                cursor="hand2",
            )
            btn.pack(fill=tk.X)
            self._sidebar_buttons[panel_id] = btn

        # Content area
        self._content = tk.Frame(main, bg=_CLR_BG)
        main.add(self._content, stretch="always")

        # Status bar
        status_bar = tk.Frame(self.root, bg=_CLR_BTN, height=24)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(
            status_bar, textvariable=self._status_var, bg=_CLR_BTN, fg=_CLR_DIM,
            font=_FONT_MONO_SMALL, anchor=tk.W, padx=8,
        ).pack(fill=tk.X)

        self.show_panel("dashboard")

    def show_panel(self, panel_id: str) -> None:
        """Destroy the current panel and create a new one."""
        builders: dict[str, type[_BasePanel]] = {
            "dashboard": DashboardPanel,
            "browse": BrowsePanel,
            "query": QueryPanel,
            "mutate": MutatePanel,
            "merge": MergePanel,
            "diff": DiffPanel,
            "repl": ReplPanel,
            "generate": GeneratePanel,
            "doctor": DoctorPanel,
        }
        if self._current_panel is not None:
            self._current_panel.destroy()

        # Update sidebar highlight
        for pid, btn in self._sidebar_buttons.items():
            if pid == panel_id:
                btn.configure(bg=_CLR_BTN, fg=_CLR_ACCENT)
            else:
                btn.configure(bg=_CLR_SIDEBAR, fg=_CLR_FG)

        panel_class = builders.get(panel_id, DashboardPanel)
        panel = panel_class(self._content, self._runner, self._status_var, self)
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_panel = panel
        self._current_panel_name = panel_id

    def load_file(self, path: str) -> None:
        """Load a file and set it as the current value."""
        self._status_var.set(f"Loading {path}...")
        self._runner.run(
            self._do_load_file,
            args=(path,),
            on_success=lambda result: self._on_file_loaded(result, path),
            on_error=lambda exc: self._on_load_error(exc),
        )

    @staticmethod
    def _do_load_file(path: str) -> Any:
        from hissbytenotation.cli.codecs import parse_value, infer_format_from_path
        text = Path(path).read_text(encoding="utf-8")
        fmt = infer_format_from_path(path, output=False)
        return parse_value(text, fmt)

    def _on_file_loaded(self, value: Any, path: str) -> None:
        self.current_value = value
        self.current_path = path
        self._status_var.set(f"Loaded {path}")
        # Refresh current panel
        if self._current_panel_name:
            self.show_panel(self._current_panel_name)

    def _on_load_error(self, exc: Exception) -> None:
        self._status_var.set(f"Load failed: {exc}")
        messagebox.showerror("Load Error", str(exc))

    def run(self) -> None:
        """Start the tkinter main loop."""
        self.root.mainloop()


def launch_gui() -> None:
    """Entry point for the GUI."""
    app = HbnApp()
    app.run()
