"""Review window: pick samples, tune per-channel display windows, hide channels, draw an ROI."""
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

import core
import imaging

PREVIEW = 480  # merge preview size (px)
THUMB = 120    # per-channel thumbnail size (px)


def roi_from_drag(x0, y0, x1, y1, view_w, view_h):
    """Square ROI (x, y, size) as fractions of the view, from a drag; clamped inside the image."""
    side = max(abs(x1 - x0), abs(y1 - y0))
    cx = x0 if x1 >= x0 else x0 - side
    cy = y0 if y1 >= y0 else y0 - side
    return imaging.clamp_roi((cx / view_w, cy / view_h, side / view_w))


class ReviewWindow(tk.Toplevel):
    def __init__(self, parent, samples, settings):
        super().__init__(parent)
        self.title("Review images")
        self.geometry("1040x700")
        self.samples, self.settings = samples, settings
        self.cache = {}      # key -> (merge preview, [channel previews])
        self.cur = None      # current Sample
        self._drag = None
        self._photos = []    # keep PhotoImage references alive

        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=8, pady=8)
        st = ttk.Style(self)
        fg, bg = st.lookup("TEntry", "foreground") or "black", st.lookup("TEntry", "fieldbackground") or "white"
        self.listbox = tk.Listbox(left, width=34, exportselection=False, relief="flat", bd=0, highlightthickness=0,
                                  fg=fg, bg=bg, activestyle="none", selectbackground="#0067c0", selectforeground="white")
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.select(self.listbox.curselection()))
        bulk = ttk.Frame(left)
        bulk.pack(fill="x", pady=(6, 0))
        ttk.Button(bulk, text="Select all", command=lambda: self.set_all(True)).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(bulk, text="Uncheck all", command=lambda: self.set_all(False)).pack(side="left", expand=True, fill="x", padx=(3, 0))
        self.include = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Include in deck", variable=self.include, command=self.toggle_include).pack(anchor="w", pady=4)

        mid = ttk.Frame(self)
        mid.pack(side="left", padx=8, pady=8)
        self.canvas = tk.Canvas(mid, width=PREVIEW, height=PREVIEW, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        ttk.Label(mid, text="Drag on the merge to draw a square ROI. Channel panels will show only the ROI.").pack(pady=4)
        row = ttk.Frame(mid)
        row.pack()
        ttk.Button(row, text="Clear ROI", command=self.clear_roi).pack(side="left", padx=4)
        ttk.Button(row, text="Apply windows to all samples", command=self.apply_all).pack(side="left", padx=4)
        ttk.Button(row, text="Close", command=self.destroy).pack(side="left", padx=4)

        self.right = ttk.Frame(self)
        self.right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        for s in samples:
            self.listbox.insert("end", "")
        self.refresh_list()
        if samples:
            self.listbox.selection_set(0)
            self.select((0,))

    # --- data -------------------------------------------------------------
    def previews(self, s):
        if s.key not in self.cache:
            load = lambda p: Image.open(p).convert("RGB").resize((PREVIEW, PREVIEW), Image.BILINEAR)
            self.cache[s.key] = (load(s.merge), [load(p) for p in s.channels])
        return self.cache[s.key]

    def st(self):
        return self.settings[self.cur.key]

    def refresh_list(self):
        for i, s in enumerate(self.samples):
            self.listbox.delete(i)
            self.listbox.insert(i, ("☑ " if self.settings[s.key].include else "☐ ") + s.base)
        if self.cur:
            self.listbox.selection_set(self.samples.index(self.cur))

    # --- selection --------------------------------------------------------
    def select(self, sel):
        if not sel:
            return
        self.cur = self.samples[sel[0]]
        self.include.set(self.st().include)
        self.build_controls()
        self.redraw()

    def set_all(self, value):
        core.set_include_all(self.settings, value)
        if self.cur:
            self.include.set(value)
        self.refresh_list()

    def toggle_include(self):
        self.st().include = self.include.get()
        self.refresh_list()

    def build_controls(self):
        for w in self.right.winfo_children():
            w.destroy()
        self.rows = []
        for k, name in enumerate(self.cur.names):
            cs = self.st().channels[k]
            f = ttk.LabelFrame(self.right, text=name)
            f.pack(fill="x", pady=3)
            thumb = tk.Label(f, bg="black")
            thumb.grid(row=0, column=0, rowspan=3, padx=4, pady=4)
            lo, hi = tk.DoubleVar(value=cs.lo), tk.DoubleVar(value=cs.hi)
            vis, lock = tk.BooleanVar(value=cs.visible), tk.BooleanVar(value=cs.locked)
            lo_txt, hi_txt = tk.StringVar(value=f"Min {cs.lo}"), tk.StringVar(value=f"Max {cs.hi}")
            s_lo = ttk.Scale(f, from_=0, to=254, orient="horizontal", variable=lo, length=170,
                             command=lambda v, k=k: self.on_slider(k, "lo"))
            s_hi = ttk.Scale(f, from_=1, to=255, orient="horizontal", variable=hi, length=170,
                             command=lambda v, k=k: self.on_slider(k, "hi"))
            ttk.Label(f, textvariable=lo_txt, width=7).grid(row=0, column=1, sticky="w")
            ttk.Label(f, textvariable=hi_txt, width=7).grid(row=1, column=1, sticky="w")
            s_lo.grid(row=0, column=2, columnspan=2, padx=4, pady=2)
            s_hi.grid(row=1, column=2, columnspan=2, padx=4, pady=2)
            ttk.Checkbutton(f, text="Show", variable=vis, command=lambda k=k: self.on_show(k)).grid(row=2, column=1)
            ttk.Checkbutton(f, text="Lock", variable=lock, command=lambda k=k: self.on_lock(k)).grid(row=2, column=2)
            ttk.Button(f, text="Reset", command=lambda k=k: self.on_reset(k)).grid(row=2, column=3)
            self.rows.append(dict(thumb=thumb, lo=lo, hi=hi, vis=vis, lock=lock, s_lo=s_lo, s_hi=s_hi, lo_txt=lo_txt, hi_txt=hi_txt))
            self.set_lock_state(k)

    def set_lock_state(self, k):
        r, state = self.rows[k], ("disabled" if self.st().channels[k].locked else "normal")
        r["s_lo"].config(state=state)
        r["s_hi"].config(state=state)

    # --- handlers ---------------------------------------------------------
    def on_slider(self, k, which):
        cs, r = self.st().channels[k], self.rows[k]
        cs.lo, cs.hi = int(round(r["lo"].get())), int(round(r["hi"].get()))
        if cs.hi <= cs.lo:  # keep min below max
            if which == "lo":
                cs.lo = cs.hi - 1
                r["lo"].set(cs.lo)
            else:
                cs.hi = cs.lo + 1
                r["hi"].set(cs.hi)
        r["lo_txt"].set(f"Min {cs.lo}")
        r["hi_txt"].set(f"Max {cs.hi}")
        self.redraw()

    def on_show(self, k):
        self.st().channels[k].visible = self.rows[k]["vis"].get()
        self.redraw()

    def on_lock(self, k):
        self.st().channels[k].locked = self.rows[k]["lock"].get()
        self.set_lock_state(k)

    def on_reset(self, k):
        cs, r = self.st().channels[k], self.rows[k]
        if cs.locked:
            return
        cs.lo, cs.hi = 0, 255
        r["lo"].set(0)
        r["hi"].set(255)
        r["lo_txt"].set("Min 0")
        r["hi_txt"].set("Max 255")
        self.redraw()

    def apply_all(self):
        core.apply_to_all(self.settings, self.cur.key)
        self.redraw()

    def clear_roi(self):
        self.st().roi = None
        self.redraw()

    def on_press(self, e):
        self._drag = (e.x, e.y)

    def on_motion(self, e):
        if self._drag:
            self.st().roi = roi_from_drag(*self._drag, e.x, e.y, PREVIEW, PREVIEW)
            self.redraw()

    def on_release(self, e):
        if self._drag:
            roi = roi_from_drag(*self._drag, e.x, e.y, PREVIEW, PREVIEW)
            self.st().roi = roi if roi[2] > 0.01 else None  # a plain click clears the ROI
            self._drag = None
            self.redraw()

    # --- drawing ----------------------------------------------------------
    def redraw(self):
        if not self.cur:
            return
        st = self.st()
        merge, chans = self.previews(self.cur)
        windowed = [imaging.apply_window(c, cs.lo, cs.hi) for c, cs in zip(chans, st.channels)]
        visible = [w for w, cs in zip(windowed, st.channels) if cs.visible]
        shown = merge if st.is_untouched() or not visible else imaging.composite(visible)
        self._photos = [ImageTk.PhotoImage(shown)]
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photos[0], anchor="nw")
        if st.roi:
            x, y, s = st.roi
            self.canvas.create_rectangle(x * PREVIEW, y * PREVIEW, (x + s) * PREVIEW, (y + s) * PREVIEW,
                                         outline="#ffc800", width=2)
        for w, r in zip(windowed, self.rows):
            t = ImageTk.PhotoImage(imaging.crop_roi(w, st.roi).resize((THUMB, THUMB)))
            self._photos.append(t)
            r["thumb"].config(image=t)


def open_review(parent, samples, settings):
    return ReviewWindow(parent, samples, settings)
