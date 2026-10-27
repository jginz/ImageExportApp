"""Drag a folder of confocal exports onto the window to build a PowerPoint."""
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

import sv_ttk

import core
import review

try:
    import darkdetect
except ImportError:
    darkdetect = None


def apply_theme(root):
    """Sun Valley theme, following the system light/dark setting."""
    dark = bool(darkdetect) and (darkdetect.theme() or "").lower() == "dark"
    sv_ttk.set_theme("dark" if dark else "light")
    st = ttk.Style(root)
    root.option_add("*Font", ("Segoe UI" if sys.platform.startswith("win") else "Helvetica Neue", 12))
    return st


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Confocal Deck Builder")
        self.geometry("640x700")
        self.style = apply_theme(self)
        self.folder = None
        self.samples, self.settings = [], {}

        card = ttk.Frame(self, style="Card.TFrame", padding=24)
        card.pack(fill="x", padx=20, pady=(20, 8))
        self.drop = ttk.Label(card, text="Drop a folder here\nor click to browse", anchor="center", justify="center",
                              font=("Helvetica Neue", 15), cursor="hand2")
        self.drop.pack(fill="x", ipady=18)
        for w in (card, self.drop):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)
            w.bind("<Button-1>", lambda e: self.browse())

        o = ttk.LabelFrame(self, text="Options")
        o.pack(fill="x", padx=20, pady=8, ipady=4)
        self.recursive = tk.BooleanVar(value=True)
        self.merge = tk.BooleanVar(value=True)
        self.title_on = tk.BooleanVar(value=True)
        self.fname = tk.BooleanVar(value=True)
        self.scalebar = tk.BooleanVar(value=True)
        self.lsize = tk.IntVar(value=12)
        self.px = tk.IntVar(value=900)
        self.order = tk.StringVar(value="")
        ttk.Checkbutton(o, text="Include subfolders", variable=self.recursive).grid(row=0, column=0, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(o, text="Show merged image", variable=self.merge).grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(o, text="Show image name", variable=self.fname).grid(row=2, column=0, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(o, text="Show title", variable=self.title_on).grid(row=2, column=1, columnspan=2, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(o, text="Scale bar on merge", variable=self.scalebar).grid(row=3, column=0, sticky="w", padx=8, pady=2)
        ttk.Label(o, text="Channel label size (pt)").grid(row=0, column=1, sticky="e", padx=8)
        ttk.Spinbox(o, from_=8, to=36, textvariable=self.lsize, width=5).grid(row=0, column=2, padx=8)
        ttk.Label(o, text="Image size (px)").grid(row=1, column=1, sticky="e", padx=8)
        ttk.Spinbox(o, from_=300, to=2048, increment=100, textvariable=self.px, width=5).grid(row=1, column=2, padx=8)
        ttk.Label(o, text="Slide order by prefix (comma-separated, e.g. BRPC-26, 26-T)").grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 0))
        ttk.Entry(o, textvariable=self.order).grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 8))
        o.columnconfigure(0, weight=1)

        row = ttk.Frame(self)
        row.pack(pady=10)
        self.rbtn = ttk.Button(row, text="Review...", command=self.open_review, state="disabled")
        self.rbtn.pack(side="left", padx=4)
        self.btn = ttk.Button(row, text="Create PowerPoint", command=self.run, state="disabled", style="Accent.TButton")
        self.btn.pack(side="left", padx=4)
        self.pbtn = ttk.Button(row, text="Export PNGs...", command=lambda: self.run("png"), state="disabled")
        self.pbtn.pack(side="left", padx=4)
        self.bar = ttk.Progressbar(self, mode="determinate")
        self.bar.pack(fill="x", padx=20)
        fg, bg = self.style.lookup("TEntry", "foreground") or "black", self.style.lookup("TEntry", "fieldbackground") or "white"
        self.log = tk.Text(self, height=9, state="disabled", font=("Menlo" if sys.platform == "darwin" else "Consolas", 10),
                           relief="flat", bd=0, padx=10, pady=8, fg=fg, bg=bg, highlightthickness=0)
        self.log.pack(fill="both", expand=True, padx=20, pady=(10, 20))

    def say(self, msg):
        self.log.configure(state="normal"); self.log.insert("end", msg + "\n"); self.log.see("end"); self.log.configure(state="disabled")

    def set_folder(self, p):
        p = Path(p)
        if not p.is_dir():
            messagebox.showerror("Not a folder", f"{p} is not a folder."); return
        self.folder = p
        self.drop.config(text=f"{p.name}\n{p}")
        self.btn.config(state="normal")
        self.pbtn.config(state="normal")
        samples, skipped = core.find_samples(p, self.recursive.get())
        self.samples = core.order_samples(samples, [x.strip() for x in self.order.get().split(",") if x.strip()])
        self.settings = core.default_settings(self.samples)
        self.rbtn.config(state="normal" if self.samples else "disabled")
        self.say(f"Found {len(samples)} images in {p.name}" + (f" ({len(skipped)} skipped)" if skipped else ""))

    def open_review(self):
        review.open_review(self, self.samples, self.settings)

    def on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        if paths:
            self.set_folder(paths[0])

    def browse(self):
        p = filedialog.askdirectory(title="Choose folder of confocal exports")
        if p:
            self.set_folder(p)

    def run(self, kind="pptx"):
        if kind == "png":
            out = filedialog.askdirectory(title="Choose folder for PNGs", initialdir=str(self.folder))
        else:
            out = filedialog.asksaveasfilename(defaultextension=".pptx", filetypes=[("PowerPoint", "*.pptx")],
                                               initialdir=str(self.folder), initialfile=f"{self.folder.name}_deck.pptx")
        if not out:
            return
        opts = core.Options(recursive=self.recursive.get(), show_merge=self.merge.get(), show_title=self.title_on.get(), show_filename=self.fname.get(), scale_bar=self.scalebar.get(),
                            label_size=self.lsize.get(), image_px=self.px.get(),
                            prefix_order=[s.strip() for s in self.order.get().split(",") if s.strip()])
        self.btn.config(state="disabled"); self.pbtn.config(state="disabled")
        threading.Thread(target=self.work, args=(out, opts, kind), daemon=True).start()

    def work(self, out, opts, kind="pptx"):
        try:
            samples, skipped = core.find_samples(self.folder, opts.recursive)
            for b, why in skipped:
                self.after(0, self.say, f"Skipped {b}: {why}")
            if not samples:
                self.after(0, messagebox.showwarning, "Nothing found", "No *.tif.frames folders with a merged image were found.")
                return
            samples = core.order_samples(samples, opts.prefix_order)
            settings = self.settings
            if any(x.key not in settings for x in samples):  # folder options changed since loading
                settings = {**core.default_settings(samples), **settings}
            samples = [x for x in samples if settings[x.key].include]
            if not samples:
                self.after(0, messagebox.showwarning, "Nothing selected", "No images are included in the deck.")
                return
            self.after(0, lambda: self.bar.config(maximum=len(samples), value=0))
            prog = lambda i, n, m: self.after(0, lambda: (self.bar.config(value=i), self.say(m) if m != "done" else None))
            if kind == "png":
                core.export_pngs(samples, out, opts, settings=settings, progress=prog)
                self.after(0, self.say, f"Saved PNGs to {out}")
                self.after(0, messagebox.showinfo, "Done", f"Saved PNGs for {len(samples)} images to\n{out}")
            else:
                core.build_deck(samples, out, opts, settings=settings, progress=prog)
                self.after(0, self.say, f"Saved {out}")
                self.after(0, messagebox.showinfo, "Done", f"Saved {len(samples)} slides to\n{out}")
        except Exception as e:
            self.after(0, messagebox.showerror, "Error", str(e))
        finally:
            self.after(0, lambda: (self.btn.config(state="normal"), self.pbtn.config(state="normal")))


if __name__ == "__main__":
    App().mainloop()
