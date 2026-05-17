import tkinter as tk
from tkinter import messagebox
import os

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 색상 팔레트 ─────────────────────────────────────────────────
BG         = "#1a1a2e"
HEADER_BG  = "#16213e"
SEP        = "#2a2a4e"
TITLE_FG   = "#e94560"
SUB_FG     = "#8892b0"
STATUS_FG  = "#64ffda"
WARN_FG    = "#ffd700"
START_BG   = "#1565c0"
STOP_BG    = "#c62828"
IMG_BG     = "#0d0d1a"
LOG_BG     = "#0d0d1a"
LOG_FG     = "#64ffda"
ACTIVE_BG  = "#533483"


class KTXMacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KTX 자동 예매 매크로")
        self.root.geometry("420x720")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.macro_running = False
        self._photo_cache = {}

        self._build_ui()

    # ── 레이아웃 구성 ────────────────────────────────────────────
    def _build_ui(self):
        self._header()
        self._separator()
        self._status_bar()
        self._separator()
        self._start_button()
        self._separator()
        self._image_section()
        self._separator()
        self._stop_button()
        self._separator()
        self._log_section()

    def _separator(self):
        tk.Frame(self.root, bg=SEP, height=1).pack(fill="x")

    def _header(self):
        f = tk.Frame(self.root, bg=HEADER_BG, pady=14)
        f.pack(fill="x")

        tk.Label(
            f,
            text="KTX 자동 예매 매크로",
            font=("Malgun Gothic", 17, "bold"),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack()

        tk.Label(
            f,
            text="수서발 고속철도 자동화 프로그램",
            font=("Malgun Gothic", 9),
            bg=HEADER_BG,
            fg=SUB_FG,
        ).pack()

    def _status_bar(self):
        f = tk.Frame(self.root, bg=BG, pady=7)
        f.pack(fill="x", padx=18)

        tk.Label(f, text="상태:", font=("Malgun Gothic", 9),
                 bg=BG, fg=SUB_FG).pack(side="left")

        self.status_var = tk.StringVar(value="대기 중")
        self.status_lbl = tk.Label(
            f,
            textvariable=self.status_var,
            font=("Malgun Gothic", 9, "bold"),
            bg=BG,
            fg=STATUS_FG,
        )
        self.status_lbl.pack(side="left", padx=4)

    def _start_button(self):
        f = tk.Frame(self.root, bg=BG, padx=18, pady=10)
        f.pack(fill="x")

        self.start_btn = tk.Button(
            f,
            text="🚄  KTX 좌석 매크로 시작",
            font=("Malgun Gothic", 12, "bold"),
            bg=START_BG,
            fg="white",
            activebackground="#1976d2",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.toggle_macro,
        )
        self.start_btn.pack(fill="x")

    def _image_section(self):
        header_f = tk.Frame(self.root, bg=BG, padx=18, pady=6)
        header_f.pack(fill="x")

        tk.Label(
            header_f,
            text="이미지 지정  (미리보기 클릭 → 크게 보기 / 버튼 클릭 → 캡처)",
            font=("Malgun Gothic", 7),
            bg=BG,
            fg=SUB_FG,
        ).pack(anchor="w")

        grid_f = tk.Frame(self.root, bg=BG, padx=14)
        grid_f.pack(fill="x", pady=(0, 6))

        COLS = 2
        IMG_W, IMG_H = 130, 65

        for i in range(1, 10):
            name = f"b{i}"
            row = (i - 1) // COLS
            col = (i - 1) % COLS

            cell = tk.Frame(grid_f, bg=BG, padx=5, pady=4)
            cell.grid(row=row, column=col, sticky="nsew")
            grid_f.columnconfigure(col, weight=1)

            photo = self._load_thumb(name, IMG_W, IMG_H)

            btn_kw = dict(
                bg=IMG_BG,
                activebackground="#1a1a3e",
                relief="flat",
                cursor="hand2",
                width=IMG_W,
                height=IMG_H,
                command=lambda n=name: self.capture_image(n),
            )

            if photo:
                btn = tk.Button(cell, image=photo, **btn_kw)
            else:
                btn = tk.Button(
                    cell,
                    text=name,
                    font=("Malgun Gothic", 9),
                    fg="#555577",
                    **btn_kw,
                )

            btn.pack()

            tk.Label(
                cell,
                text=f"{name} 이미지지정",
                font=("Malgun Gothic", 7),
                bg=BG,
                fg=STATUS_FG,
            ).pack()

    def _stop_button(self):
        f = tk.Frame(self.root, bg=BG, padx=18, pady=10)
        f.pack(fill="x")

        tk.Button(
            f,
            text="⏹  매크로 종료  (F12)",
            font=("Malgun Gothic", 12, "bold"),
            bg=STOP_BG,
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.quit_app,
        ).pack(fill="x")

        self.root.bind("<F12>", lambda e: self.quit_app())

    def _log_section(self):
        f = tk.Frame(self.root, bg=HEADER_BG, padx=12, pady=8)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="로그", font=("Malgun Gothic", 8),
                 bg=HEADER_BG, fg=SUB_FG).pack(anchor="w")

        self.log_text = tk.Text(
            f,
            height=4,
            bg=LOG_BG,
            fg=LOG_FG,
            font=("Consolas", 8),
            relief="flat",
            state="disabled",
            wrap="word",
            insertbackground=LOG_FG,
        )
        self.log_text.pack(fill="both", expand=True)

        self._log("KTX 매크로 준비 완료.  b1~b9 이미지를 캡처 후 시작하세요.")

    # ── 헬퍼 ────────────────────────────────────────────────────
    def _load_thumb(self, name, w, h):
        if not PIL_AVAILABLE:
            return None
        path = os.path.join(BASE_DIR, f"{name}.png")
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path).resize((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._photo_cache[name] = photo
            return photo
        except Exception:
            return None

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str, color: str = STATUS_FG):
        self.status_var.set(text)
        self.status_lbl.configure(fg=color)

    # ── 버튼 콜백 ───────────────────────────────────────────────
    def toggle_macro(self):
        if not self.macro_running:
            self.macro_running = True
            self.start_btn.configure(
                text="⏸  매크로 실행 중...",
                bg=ACTIVE_BG,
                activebackground="#6a44a0",
            )
            self._set_status("매크로 실행 중", TITLE_FG)
            self._log("매크로 시작됨.")
        else:
            self.macro_running = False
            self.start_btn.configure(
                text="🚄  KTX 좌석 매크로 시작",
                bg=START_BG,
                activebackground="#1976d2",
            )
            self._set_status("대기 중")
            self._log("매크로 정지됨.")

    def capture_image(self, name: str):
        self._log(f"{name} 이미지 캡처 시작...")

    def quit_app(self):
        if messagebox.askyesno("종료", "프로그램을 종료하시겠습니까?"):
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = KTXMacroApp(root)
    root.mainloop()
