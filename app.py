#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import shutil
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


DEFAULT_DATABASE_DIR = (
    Path.home()
    / "AndroidStudioProjects"
    / "chemsearch"
    / "app"
    / "src"
    / "main"
    / "assets"
    / "chemical_database"
)


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str = "entry"
    hint: str = ""


@dataclass(frozen=True)
class DatasetSpec:
    label: str
    file_name: str
    root_key: str
    primary_key: str
    secondary_key: str
    fields: tuple[FieldSpec, ...]


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        label="Substances",
        file_name="substances.json",
        root_key="substances",
        primary_key="name",
        secondary_key="formula",
        fields=(
            FieldSpec("id", "ID"),
            FieldSpec("name", "Common name"),
            FieldSpec("formula", "Formula"),
            FieldSpec("otherNames", "Other names", "list", "One name per line"),
            FieldSpec("type", "Type", "entry", "Acid, Base, Alkane, Alcohol, Aldehyde, Salt..."),
            FieldSpec("uses", "Uses", "text"),
            FieldSpec("notes", "Notes", "text"),
            FieldSpec("tags", "Tags", "list", "One tag per line"),
            FieldSpec("sourceLabel", "Source label"),
            FieldSpec("sourceUrl", "Source URL"),
            FieldSpec("searchQuery", "ChemSearch query"),
        ),
    ),
    DatasetSpec(
        label="Ions",
        file_name="ions.json",
        root_key="ions",
        primary_key="name",
        secondary_key="formula",
        fields=(
            FieldSpec("id", "ID"),
            FieldSpec("name", "Name"),
            FieldSpec("formula", "Formula"),
            FieldSpec("otherNames", "Other names", "list", "One name per line"),
            FieldSpec("type", "Type", "entry", "Monoatomic cation, Polyatomic anion..."),
            FieldSpec("charge", "Charge"),
            FieldSpec("commonCompounds", "Common compounds", "list", "One compound per line"),
            FieldSpec("notes", "Notes", "text"),
            FieldSpec("tags", "Tags", "list", "One tag per line"),
            FieldSpec("sourceLabel", "Source label"),
            FieldSpec("sourceUrl", "Source URL"),
        ),
    ),
    DatasetSpec(
        label="Functional Groups",
        file_name="functional_groups.json",
        root_key="functionalGroups",
        primary_key="name",
        secondary_key="structure",
        fields=(
            FieldSpec("id", "ID"),
            FieldSpec("name", "Name"),
            FieldSpec("generalFormula", "General formula"),
            FieldSpec("structure", "Structure"),
            FieldSpec("type", "Type", "entry", "Alcohol, Aldehyde, Amine, Aromatic..."),
            FieldSpec("namingCue", "Naming cue"),
            FieldSpec("example", "Example"),
            FieldSpec("behavior", "Behavior", "text"),
            FieldSpec("tags", "Tags", "list", "One tag per line"),
            FieldSpec("sourceLabel", "Source label"),
            FieldSpec("sourceUrl", "Source URL"),
        ),
    ),
    DatasetSpec(
        label="Reactions",
        file_name="reactions.json",
        root_key="reactions",
        primary_key="name",
        secondary_key="equation",
        fields=(
            FieldSpec("id", "ID"),
            FieldSpec("name", "Name"),
            FieldSpec("equation", "Balanced equation"),
            FieldSpec("type", "Type", "entry", "Combustion, Neutralization, Redox..."),
            FieldSpec("conditions", "Conditions"),
            FieldSpec("observation", "Observation", "text"),
            FieldSpec("notes", "Notes", "text"),
            FieldSpec("tags", "Tags", "list", "One tag per line"),
            FieldSpec("sourceLabel", "Source label"),
            FieldSpec("sourceUrl", "Source URL"),
        ),
    ),
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "new-entry"


class ScrollFrame(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_content_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)


class DataEditApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ChemSearch DataEdit")
        self.geometry("1180x760")
        self.minsize(980, 620)

        self.database_dir = DEFAULT_DATABASE_DIR
        self.specs = {spec.label: spec for spec in DATASETS}
        self.data: dict[str, list[dict[str, object]]] = {}
        self.current_spec = DATASETS[0]
        self.current_index: int | None = None
        self.field_widgets: dict[str, tk.Widget] = {}
        self.search_var = tk.StringVar()
        self.path_var = tk.StringVar(value=str(self.database_dir))
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self.load_database()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(12, 10))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Database folder").grid(row=0, column=0, sticky="w", padx=(0, 8))
        path_entry = ttk.Entry(top, textvariable=self.path_var)
        path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(top, text="Browse", command=self.choose_database_dir).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(top, text="Reload", command=self.load_database).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(top, text="Validate", command=self.validate_database).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(top, text="Save All", command=self.save_all).grid(row=0, column=5)

        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        left = ttk.Frame(pane, padding=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)
        pane.add(left, weight=1)

        right = ttk.Frame(pane, padding=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        pane.add(right, weight=3)

        ttk.Label(left, text="Data files", font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, sticky="w")
        dataset_buttons = ttk.Frame(left)
        dataset_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 10))
        dataset_buttons.columnconfigure((0, 1), weight=1)
        for idx, spec in enumerate(DATASETS):
            button = ttk.Button(
                dataset_buttons,
                text=spec.label,
                command=lambda item=spec: self.select_dataset(item),
            )
            button.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)

        search = ttk.Entry(left, textvariable=self.search_var)
        search.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        search.insert(0, "")
        search.bind("<KeyRelease>", lambda _event: self.refresh_tree())

        self.tree = ttk.Treeview(left, columns=("formula", "type"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Name")
        self.tree.heading("formula", text="Formula / Equation")
        self.tree.heading("type", text="Type")
        self.tree.column("#0", width=180, anchor="w")
        self.tree.column("formula", width=120, anchor="w")
        self.tree.column("type", width=120, anchor="w")
        self.tree.grid(row=3, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        tree_scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=3, column=1, sticky="ns")

        entry_actions = ttk.Frame(left)
        entry_actions.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        entry_actions.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(entry_actions, text="New", command=self.new_entry).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(entry_actions, text="Duplicate", command=self.duplicate_entry).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(entry_actions, text="Delete", command=self.delete_entry).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.form_title = ttk.Label(right, text="", font=("TkDefaultFont", 16, "bold"))
        self.form_title.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.form_hint = ttk.Label(right, text="", foreground="#666")
        self.form_hint.grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.form_frame = ScrollFrame(right)
        self.form_frame.grid(row=2, column=0, sticky="nsew")

        form_actions = ttk.Frame(right)
        form_actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(form_actions, text="Apply Form", command=self.apply_form_to_current).pack(side="left")
        ttk.Button(form_actions, text="Save This File", command=self.save_current_file).pack(side="left", padx=(8, 0))

        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 4))
        status.grid(row=2, column=0, sticky="ew")

    def choose_database_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.database_dir), title="Choose chemical_database folder")
        if not selected:
            return
        self.database_dir = Path(selected)
        self.path_var.set(str(self.database_dir))
        self.load_database()

    def select_dataset(self, spec: DatasetSpec) -> None:
        self.apply_form_to_current(silent=True)
        self.current_spec = spec
        self.current_index = None
        self.build_form()
        self.refresh_tree()
        self.select_first_entry()

    def load_database(self) -> None:
        self.database_dir = Path(self.path_var.get()).expanduser()
        loaded: dict[str, list[dict[str, object]]] = {}
        missing: list[str] = []
        for spec in DATASETS:
            path = self.database_dir / spec.file_name
            if not path.exists():
                loaded[spec.label] = []
                missing.append(spec.file_name)
                continue
            try:
                payload = json.loads(path.read_text())
                entries = payload.get(spec.root_key, [])
                if not isinstance(entries, list):
                    raise ValueError(f"{spec.root_key} must be a list")
                loaded[spec.label] = [dict(item) for item in entries if isinstance(item, dict)]
            except Exception as exc:
                messagebox.showerror("Load failed", f"Could not load {path}:\n{exc}")
                loaded[spec.label] = []

        self.data = loaded
        self.current_index = None
        self.build_form()
        self.refresh_tree()
        self.select_first_entry()
        if missing:
            self.status_var.set("Loaded with missing files: " + ", ".join(missing))
        else:
            self.status_var.set(f"Loaded database from {self.database_dir}")

    def build_form(self) -> None:
        for child in self.form_frame.content.winfo_children():
            child.destroy()
        self.field_widgets.clear()
        self.form_title.configure(text=self.current_spec.label)
        self.form_hint.configure(text=f"Editing {self.current_spec.file_name}")

        for row, field in enumerate(self.current_spec.fields):
            label = ttk.Label(self.form_frame.content, text=field.label)
            label.grid(row=row * 2, column=0, sticky="w", pady=(8, 2))
            if field.hint:
                label.configure(text=f"{field.label} ({field.hint})")

            if field.kind in {"text", "list"}:
                widget = tk.Text(self.form_frame.content, height=4 if field.kind == "list" else 5, wrap="word")
                widget.grid(row=row * 2 + 1, column=0, sticky="ew")
            else:
                widget = ttk.Entry(self.form_frame.content)
                widget.grid(row=row * 2 + 1, column=0, sticky="ew")
            self.field_widgets[field.key] = widget

        self.form_frame.content.columnconfigure(0, weight=1)
        self.clear_form()

    def refresh_tree(self) -> None:
        query = self.search_var.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, entry in enumerate(self.current_entries()):
            if query and query not in self.entry_search_blob(entry):
                continue
            name = str(entry.get(self.current_spec.primary_key) or "(untitled)")
            formula = str(entry.get(self.current_spec.secondary_key) or "")
            entry_type = str(entry.get("type") or "")
            self.tree.insert("", "end", iid=str(index), text=name, values=(formula, entry_type))

    def select_first_entry(self) -> None:
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self.populate_form(int(children[0]))
        else:
            self.current_index = None
            self.clear_form()

    def on_tree_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        next_index = int(selected[0])
        if self.current_index == next_index:
            return
        self.apply_form_to_current(silent=True)
        self.populate_form(next_index)

    def populate_form(self, index: int) -> None:
        entries = self.current_entries()
        if index < 0 or index >= len(entries):
            self.current_index = None
            self.clear_form()
            return
        self.current_index = index
        entry = entries[index]
        for field in self.current_spec.fields:
            value = entry.get(field.key, "")
            widget = self.field_widgets[field.key]
            text_value = "\n".join(value) if isinstance(value, list) else str(value or "")
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", text_value)
            else:
                widget.delete(0, "end")
                widget.insert(0, text_value)
        self.status_var.set(f"Editing {self.current_spec.label}: {entry.get(self.current_spec.primary_key, '(untitled)')}")

    def clear_form(self) -> None:
        for widget in self.field_widgets.values():
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
            else:
                widget.delete(0, "end")

    def apply_form_to_current(self, silent: bool = False) -> None:
        if self.current_index is None:
            return
        entries = self.current_entries()
        if self.current_index < 0 or self.current_index >= len(entries):
            return

        updated: dict[str, object] = {}
        for field in self.current_spec.fields:
            widget = self.field_widgets[field.key]
            if isinstance(widget, tk.Text):
                raw = widget.get("1.0", "end").strip()
            else:
                raw = widget.get().strip()
            if field.kind == "list":
                value = [line.strip() for line in raw.splitlines() if line.strip()]
            else:
                value = raw
            if value != "" and value != []:
                updated[field.key] = value

        if not updated.get("id") and updated.get(self.current_spec.primary_key):
            updated["id"] = slugify(str(updated[self.current_spec.primary_key]))

        entries[self.current_index] = updated
        self.refresh_tree()
        if not silent:
            self.status_var.set("Applied form changes. Use Save to write JSON files.")

    def current_entries(self) -> list[dict[str, object]]:
        return self.data.setdefault(self.current_spec.label, [])

    def new_entry(self) -> None:
        self.apply_form_to_current(silent=True)
        self.search_var.set("")
        template = self.empty_entry()
        self.current_entries().append(template)
        index = len(self.current_entries()) - 1
        self.refresh_tree()
        self.tree.selection_set(str(index))
        self.tree.focus(str(index))
        self.populate_form(index)

    def duplicate_entry(self) -> None:
        if self.current_index is None:
            return
        self.apply_form_to_current(silent=True)
        self.search_var.set("")
        duplicate = copy.deepcopy(self.current_entries()[self.current_index])
        duplicate["id"] = f"{duplicate.get('id', 'entry')}-copy"
        duplicate[self.current_spec.primary_key] = f"{duplicate.get(self.current_spec.primary_key, 'Entry')} copy"
        self.current_entries().append(duplicate)
        index = len(self.current_entries()) - 1
        self.refresh_tree()
        self.tree.selection_set(str(index))
        self.tree.focus(str(index))
        self.populate_form(index)

    def delete_entry(self) -> None:
        if self.current_index is None:
            return
        entry = self.current_entries()[self.current_index]
        name = entry.get(self.current_spec.primary_key, "(untitled)")
        if not messagebox.askyesno("Delete entry", f"Delete {name}?"):
            return
        del self.current_entries()[self.current_index]
        self.current_index = None
        self.refresh_tree()
        self.select_first_entry()

    def empty_entry(self) -> dict[str, object]:
        entry: dict[str, object] = {}
        for field in self.current_spec.fields:
            if field.kind == "list":
                entry[field.key] = []
            else:
                entry[field.key] = ""
        entry["id"] = "new-entry"
        return entry

    def save_current_file(self) -> None:
        self.apply_form_to_current(silent=True)
        self.write_dataset(self.current_spec)
        self.status_var.set(f"Saved {self.current_spec.file_name}")

    def save_all(self) -> None:
        self.apply_form_to_current(silent=True)
        self.database_dir.mkdir(parents=True, exist_ok=True)
        for spec in DATASETS:
            self.write_dataset(spec)
        self.status_var.set("Saved all database files.")

    def write_dataset(self, spec: DatasetSpec) -> None:
        path = self.database_dir / spec.file_name
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        payload = {
            "version": 1,
            spec.root_key: self.data.get(spec.label, []),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def validate_database(self) -> None:
        self.apply_form_to_current(silent=True)
        problems: list[str] = []
        for spec in DATASETS:
            seen_ids: set[str] = set()
            for index, entry in enumerate(self.data.get(spec.label, []), start=1):
                name = str(entry.get(spec.primary_key) or "").strip()
                entry_id = str(entry.get("id") or "").strip()
                if not name:
                    problems.append(f"{spec.label} #{index}: missing {spec.primary_key}")
                if not entry_id:
                    problems.append(f"{spec.label} #{index}: missing id")
                elif entry_id in seen_ids:
                    problems.append(f"{spec.label} #{index}: duplicate id {entry_id}")
                seen_ids.add(entry_id)

        if problems:
            messagebox.showwarning("Validation issues", "\n".join(problems[:40]))
            self.status_var.set(f"Validation found {len(problems)} issue(s).")
        else:
            messagebox.showinfo("Validation passed", "All files look structurally OK.")
            self.status_var.set("Validation passed.")

    def entry_search_blob(self, entry: dict[str, object]) -> str:
        parts: list[str] = []
        for value in entry.values():
            if isinstance(value, list):
                parts.extend(str(item) for item in value)
            else:
                parts.append(str(value))
        return " ".join(parts).lower()


if __name__ == "__main__":
    app = DataEditApp()
    app.mainloop()
