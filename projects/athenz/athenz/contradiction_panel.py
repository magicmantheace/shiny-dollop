"""Owner-operated Tk adjudication of contradiction candidates.

All Tk construction is lazy and nothing runs at mount time: opening the
panel is the owner's explicit request to scan and list. Detection is a
lexical hint, never a verdict; every change goes through the service's
confirmed adjudication after the owner reads both complete records.
"""
from __future__ import annotations

from .contradiction_review import ContradictionReviewError

ACTIONS = ('keep-a', 'keep-b', 'keep-both', 'dismiss', 'defer')
_ACTION_LABELS = {
    'keep-a': 'Confirm contradiction — keep the FIRST record (second is superseded)',
    'keep-b': 'Confirm contradiction — keep the SECOND record (first is superseded)',
    'keep-both': 'Confirm noted — keep BOTH records approved',
    'dismiss': 'Dismiss — not a contradiction',
    'defer': 'Defer — decide later',
}


def checked_adjudication(action: str, note: str) -> dict:
    """Validate manual form input before any private write or confirmation."""
    if action not in ACTIONS:
        raise ContradictionReviewError('Choose a supported adjudication action')
    if not isinstance(note, str) or len(note.strip()) > 1000:
        raise ContradictionReviewError('Note must be at most 1000 characters')
    if action in ('keep-a', 'keep-b', 'keep-both'):
        resolution = action
        return {'action': 'confirm', 'resolution': resolution, 'note': note.strip()}
    return {'action': action, 'resolution': None, 'note': note.strip()}


def mount_contradiction_review_button(toolbar, window, service, set_status, on_changed):
    """Add the owner-triggered contradiction review to the Review toolbar."""
    import json
    import tkinter as tk
    from tkinter import ttk, messagebox

    def open_panel():
        try:
            report = service.contradiction_candidates()
        except Exception:
            messagebox.showerror('Contradiction review unavailable',
                                 'The bounded scan could not complete.', parent=window)
            return
        panel = tk.Toplevel(window)
        panel.title('Contradiction candidates — owner adjudication')
        panel.geometry('820x560')
        panel.transient(window)
        scanned = report['scan']['records_scanned']
        total = sum(scanned.values())
        ttk.Label(panel,
                  text=(f"Scanned {total} approved records. "
                        f"{report['scan']['created']} new candidate(s); "
                        f"{len(report['candidates'])} awaiting a decision. "
                        'A candidate is a lexical hint, NOT proof of a contradiction. '
                        'Nothing changes until you adjudicate after reading both records.'),
                  wraplength=790, padding=12).pack(anchor='w')
        tree = ttk.Treeview(panel, columns=('id', 'route', 'pair', 'score', 'state'),
                            show='headings', selectmode='browse')
        for col, width in (('id', 55), ('route', 170), ('pair', 300),
                           ('score', 70), ('state', 90)):
            tree.heading(col, text=col.title())
            tree.column(col, width=width, stretch=col == 'pair')
        tree.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        indexed = {}

        def refresh():
            tree.delete(*tree.get_children())
            indexed.clear()
            try:
                current = service.contradiction_candidates()
            except Exception:
                messagebox.showerror('Contradiction review unavailable',
                                     'The candidate list could not be reloaded.',
                                     parent=panel)
                return
            for item in current['candidates']:
                key = str(item['id'])
                indexed[key] = item
                pair = (f"{item['a_table']}#{item['a_id']} x "
                        f"{item['b_table']}#{item['b_id']}")
                tree.insert('', 'end', iid=key,
                            values=(item['id'], item['route'], pair,
                                    item['score'], item['state']))

        for item in report['candidates']:
            key = str(item['id'])
            indexed[key] = item
            pair = (f"{item['a_table']}#{item['a_id']} x "
                    f"{item['b_table']}#{item['b_id']}")
            tree.insert('', 'end', iid=key,
                        values=(item['id'], item['route'], pair,
                                item['score'], item['state']))

        def inspect():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo('Select a candidate',
                                    'Choose one candidate pair first.', parent=panel)
                return
            item = indexed.get(selection[0])
            if item is None:
                return
            try:
                detail = service.contradiction_detail(item['id'])
            except Exception:
                messagebox.showerror('Candidate has changed',
                                     'This candidate could not be loaded. Refresh the list.',
                                     parent=panel)
                refresh()
                return
            dialog = tk.Toplevel(panel)
            dialog.title(f"Adjudicate candidate #{item['id']} — owner decision required")
            dialog.geometry('820x640')
            dialog.transient(panel)
            ttk.Label(dialog,
                      text='Read BOTH complete records and the matching signals. '
                           'Superseding rejects the losing record; it is recorded '
                           'with this candidate as provenance and cannot be undone '
                           'automatically.',
                      wraplength=790, padding=12).pack(anchor='w')
            text_area = tk.Text(dialog, wrap='word', padx=8, pady=8)
            text_area.pack(fill='both', expand=True, padx=12, pady=(0, 8))
            text_area.insert('end', json.dumps(detail, indent=2, ensure_ascii=False))
            text_area.config(state='disabled')
            controls = ttk.Frame(dialog, padding=12)
            controls.pack(fill='x')
            ttk.Label(controls, text='Decision').pack(side='left')
            selected = tk.StringVar(value='defer')
            ttk.Combobox(controls, state='readonly', textvariable=selected,
                         values=ACTIONS, width=14).pack(side='left', padx=(6, 12))
            ttk.Label(controls, text='Note (optional)').pack(side='left')
            note_entry = ttk.Entry(controls, width=44)
            note_entry.pack(side='left', fill='x', expand=True, padx=(6, 0))
            actions = ttk.Frame(dialog, padding=12)
            actions.pack(fill='x')

            def submit():
                try:
                    values = checked_adjudication(selected.get(), note_entry.get())
                except ContradictionReviewError as exc:
                    messagebox.showerror('Review input', str(exc), parent=dialog)
                    return
                if not messagebox.askyesno(
                        'Confirm exact reviewed action',
                        _ACTION_LABELS[selected.get()] + '?', parent=dialog):
                    return
                try:
                    service.adjudicate_contradiction(
                        item['id'], values['action'],
                        resolution=values['resolution'], note=values['note'],
                        confirmed=True)
                except Exception:
                    messagebox.showerror(
                        'Adjudication refused',
                        'Records changed or the decision is no longer valid. '
                        'Reopen the candidate.', parent=dialog)
                    refresh()
                    on_changed()
                    return
                dialog.destroy()
                refresh()
                on_changed()
                set_status(f"Contradiction candidate #{item['id']}: {selected.get()}")

            ttk.Button(actions, text='Close without action',
                       command=dialog.destroy).pack(side='right', padx=(6, 0))
            ttk.Button(actions, text='Apply decision…', command=submit).pack(side='right')

        bar = ttk.Frame(panel, padding=12)
        bar.pack(fill='x')
        ttk.Button(bar, text='Close', command=panel.destroy).pack(side='right')
        ttk.Button(bar, text='Refresh', command=refresh).pack(side='right', padx=8)
        ttk.Button(bar, text='Inspect and adjudicate selected',
                   command=inspect).pack(side='right')
        set_status('Contradiction candidates generated locally; no records changed')

    button = ttk.Button(toolbar, text='Review contradictions…', command=open_panel)
    button.pack(side='right', padx=(0, 6))
    return button
