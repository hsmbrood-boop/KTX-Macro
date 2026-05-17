import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import shutil, glob, os, sys, threading, time
import pyautogui
import cv2
import numpy as np
import pygame

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

pyautogui.FAILSAFE = True
pygame.mixer.init()

# ── 색상 팔레트 ─────────────────────────────────────────────────
BG        = "#1a1a2e"
HEADER_BG = "#16213e"
SEP       = "#2a2a4e"
TITLE_FG  = "#e94560"
SUB_FG    = "#8892b0"
STATUS_FG = "#64ffda"
START_BG  = "#1565c0"
STOP_BG   = "#c62828"
IMG_BG    = "#0d0d1a"
CAP_BG    = "#0f2030"
LOG_BG    = "#0d0d1a"
LOG_FG    = "#64ffda"


def find_image_file(prefix):
    for ext in ("png", "jpg", "jpeg", "bmp"):
        p = os.path.join(BASE_DIR, f"{prefix}.{ext}")
        if os.path.exists(p):
            return p
    return None


# ── 화면 범위 선택 오버레이 ──────────────────────────────────────
class RegionSelector(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.region = None
        self._sx = self._sy = 0

        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.25)
        self.attributes("-topmost", True)
        self.configure(bg="black", cursor="crosshair")
        self.overrideredirect(True)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.canvas = tk.Canvas(self, width=sw, height=sh,
                                bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(sw // 2, 30, fill="white",
                                font=("Malgun Gothic", 14, "bold"),
                                text="드래그하여 검색 범위를 지정하세요  (ESC: 취소)")
        self._rect = None

        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_press(self, e):
        self._sx, self._sy = e.x, e.y
        if self._rect:
            self.canvas.delete(self._rect)

    def _on_drag(self, e):
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            self._sx, self._sy, e.x, e.y,
            outline="red", width=2, fill="white", stipple="gray25")

    def _on_release(self, e):
        x1, y1 = min(self._sx, e.x), min(self._sy, e.y)
        x2, y2 = max(self._sx, e.x), max(self._sy, e.y)
        w, h = x2 - x1, y2 - y1
        if w > 10 and h > 10:
            self.region = (x1, y1, w, h)
        self.destroy()


# ── 이미지 미리보기 패널 ────────────────────────────────────────
class ImagePreviewPanel(tk.LabelFrame):
    W, H = 200, 150

    def __init__(self, parent, prefix, **kw):
        super().__init__(parent, text=f" [{prefix}] ",
                         font=("Malgun Gothic", 9, "bold"), **kw)
        self._photo = None
        self._prefix = prefix

        self.canvas = tk.Canvas(self, width=self.W, height=self.H,
                                bg="#e8e8e8", cursor="hand2")
        self.canvas.pack(padx=4, pady=4)

        self._filename_var = tk.StringVar(value="파일 없음")
        tk.Label(self, textvariable=self._filename_var,
                 font=("Malgun Gothic", 7), fg="gray40").pack()

        self._draw_placeholder()
        self.canvas.bind("<Button-1>", lambda e: self._select_image())

        existing = find_image_file(self._prefix)
        if existing:
            self._show_image(existing)

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(2, 2, self.W - 2, self.H - 2,
                                     outline="gray60", dash=(4, 4))
        self.canvas.create_text(self.W // 2, self.H // 2 - 8,
                                text=f"{self._prefix} 이미지 없음",
                                font=("Malgun Gothic", 9), fill="gray50")
        self.canvas.create_text(self.W // 2, self.H // 2 + 10,
                                text="클릭하여 선택",
                                font=("Malgun Gothic", 8), fill="gray60")

    def _select_image(self):
        path = filedialog.askopenfilename(
            title=f"{self._prefix} 이미지 선택",
            filetypes=[("이미지 파일", "*.png *.jpg *.jpeg *.bmp"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        for old in glob.glob(os.path.join(BASE_DIR, f"{self._prefix}.*")):
            os.remove(old)
        ext = os.path.splitext(path)[1]
        dest = os.path.join(BASE_DIR, f"{self._prefix}{ext}")
        shutil.copy2(path, dest)
        self._show_image(dest)

    def _show_image(self, path):
        img = Image.open(path)
        img.thumbnail((self.W, self.H), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(self.W // 2, self.H // 2,
                                 anchor="center", image=self._photo)
        self._filename_var.set(os.path.basename(path))

    def clear(self):
        for old in glob.glob(os.path.join(BASE_DIR, f"{self._prefix}.*")):
            os.remove(old)
        self._photo = None
        self._filename_var.set("파일 없음")
        self._draw_placeholder()


# ── 메인 앱 ─────────────────────────────────────────────────────
class KTXMacroApp:
    IMG_W, IMG_H = 90, 46

    def __init__(self, root):
        self.root = root
        self.root.title("KTX 자동 예매 매크로")
        self.root.geometry("630x720+0+0")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)

        self._macro_running = False
        self._search_thread = None
        self._region = None
        self._pending_loop = None
        self._btn_photos = {}
        self._img_buttons = {}

        self.status_var = tk.StringVar(value="대기 중")

        self._build_ui()
        self.root.bind("<F12>", lambda e: self.stop_macro())

    # ── UI 구성 ──────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._sep()
        self._build_status()
        self._sep()
        self._build_image_grid()
        self._sep()
        self._build_stop_button()
        self._sep()
        self._build_log()
        self._build_footer()

    def _sep(self):
        tk.Frame(self.root, bg=SEP, height=1).pack(fill="x")

    def _build_header(self):
        f = tk.Frame(self.root, bg=HEADER_BG, pady=13)
        f.pack(fill="x")
        tk.Label(f, text="KTX 자동 예매 매크로",
                 font=("Malgun Gothic", 16, "bold"),
                 bg=HEADER_BG, fg=TITLE_FG).pack()

    def _build_status(self):
        f = tk.Frame(self.root, bg=BG, pady=7)
        f.pack(fill="x", padx=18)
        tk.Label(f, text="상태:", font=("Malgun Gothic", 9),
                 bg=BG, fg=SUB_FG).pack(side="left")
        self.status_lbl = tk.Label(f, textvariable=self.status_var,
                                   font=("Malgun Gothic", 9, "bold"),
                                   bg=BG, fg=STATUS_FG)
        self.status_lbl.pack(side="left", padx=4)

    def _build_image_grid(self):
        # 안내 문구
        lf = tk.Frame(self.root, bg=BG, padx=16, pady=5)
        lf.pack(fill="x")
        tk.Label(lf,
                 text="이미지 지정  (미리보기 클릭 → 크게 보기 / 이미지지정 클릭 → 캡처)",
                 font=("Malgun Gothic", 7), bg=BG, fg=SUB_FG).pack(anchor="w")

        gf = tk.Frame(self.root, bg=BG, padx=10, pady=4)
        gf.pack(fill="x")
        for c in range(5):
            gf.columnconfigure(c, weight=1)

        # (grid_row, col, label, cmd_or_None, prefix_or_None)
        layout = [
            (0, 0, "KTX\n좌석예매",    self.start_region_select_3, None),
            (0, 1, "b1",               None,                        "b1"),
            (0, 2, "b2",               None,                        "b2"),
            (0, 3, "b3",               None,                        "b3"),
            (0, 4, "b4",               None,                        "b4"),
            (2, 0, "KTX\n입석포함예매", self.start_region_select_5, None),
            (2, 1, "b5",               None,                        "b5"),
            (2, 2, "b6",               None,                        "b6"),
            (2, 3, "b7",               None,                        "b7"),
            (2, 4, "b8",               None,                        "b8"),
            (4, 1, "b9",               None,                        "b9"),
        ]

        for grid_row, col, label, cmd, prefix in layout:
            if prefix is None:
                # ── 매크로 시작 버튼 ──────────────────────────────
                btn = tk.Button(
                    gf, text=label,
                    font=("Malgun Gothic", 10, "bold"),
                    bg=START_BG, fg="white",
                    activebackground="#1976d2", activeforeground="white",
                    relief="flat", cursor="hand2",
                    command=cmd,
                )
                btn.grid(row=grid_row, column=col, rowspan=2,
                         padx=(4, 6), pady=4, sticky="nsew")
            else:
                # ── 이미지 썸네일 버튼 ───────────────────────────
                n = prefix[1:]
                preview_cmd = lambda _n=n: self._show_preview(_n)

                photo = self._load_thumb(prefix)
                if photo:
                    img_btn = tk.Button(
                        gf, image=photo, command=preview_cmd,
                        width=self.IMG_W, height=self.IMG_H,
                        bg=IMG_BG, activebackground="#1a1a3e",
                        relief="flat", cursor="hand2", bd=0,
                    )
                else:
                    img_btn = tk.Button(
                        gf, text=prefix,
                        font=("Malgun Gothic", 8), fg=SUB_FG,
                        bg=IMG_BG, activebackground="#1a1a3e",
                        relief="flat", cursor="hand2",
                        width=10, height=3,
                    )
                img_btn.grid(row=grid_row, column=col,
                             padx=3, pady=(4, 1), sticky="ew")
                self._img_buttons[prefix] = img_btn

                # ── 이미지지정 캡처 버튼 ─────────────────────────
                cap_btn = tk.Button(
                    gf, text=f"{prefix} 이미지지정",
                    font=("Malgun Gothic", 7),
                    bg=CAP_BG, fg=STATUS_FG,
                    activebackground="#1a3050", activeforeground=STATUS_FG,
                    relief="flat", cursor="hand2",
                    command=lambda p=prefix: self._capture_image(p),
                )
                cap_btn.grid(row=grid_row + 1, column=col,
                             padx=3, pady=(1, 4), sticky="ew")

    def _build_stop_button(self):
        f = tk.Frame(self.root, bg=BG, padx=16, pady=10)
        f.pack(fill="x")
        tk.Button(
            f, text="⏹  매크로 종료  (F12)",
            font=("Malgun Gothic", 12, "bold"),
            bg=STOP_BG, fg="white",
            activebackground="#d32f2f", activeforeground="white",
            relief="flat", cursor="hand2", height=2,
            command=self.stop_macro,
        ).pack(fill="x")

    def _build_footer(self):
        f = tk.Frame(self.root, bg=BG, pady=6)
        f.pack(fill="x")
        cv = tk.Canvas(f, bg=BG, highlightthickness=0, height=42, width=370)
        cv.pack()
        x1, y1, x2, y2, r = 2, 2, 368, 40, 14
        pts = [
            x1+r, y1,  x2-r, y1,  x2-r, y1,  x2, y1,
            x2, y1+r,  x2, y2-r,  x2, y2-r,  x2, y2,
            x2-r, y2,  x1+r, y2,  x1+r, y2,  x1, y2,
            x1, y2-r,  x1, y1+r,  x1, y1+r,  x1, y1,
        ]
        cv.create_polygon(pts, smooth=True, fill="white", outline="#cc2222", width=4)
        cv.create_text(185, 21, text="Developed by HSM of Orc Holdings.",
                       font=("Malgun Gothic", 11, "bold"), fill="#111111")

    def _build_log(self):
        f = tk.Frame(self.root, bg=HEADER_BG, padx=12, pady=8)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="로그", font=("Malgun Gothic", 8),
                 bg=HEADER_BG, fg=SUB_FG).pack(anchor="w")
        self.log_text = tk.Text(
            f, height=6,
            bg=LOG_BG, fg=LOG_FG,
            font=("Consolas", 8),
            relief="flat", state="disabled", wrap="word",
            insertbackground=LOG_FG,
        )
        self.log_text.pack(fill="both", expand=True)
        self._log("프로그램 시작됨.")

    # ── 헬퍼 ─────────────────────────────────────────────────────
    def _load_thumb(self, prefix):
        img_path = find_image_file(prefix)
        if not img_path:
            return None
        try:
            img = Image.open(img_path)
            img.thumbnail((self.IMG_W, self.IMG_H), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._btn_photos[prefix] = photo
            return photo
        except Exception:
            return None

    def _log(self, msg):
        self._set_status(msg)

    def _set_status(self, text):
        def _update():
            self.status_var.set(text)
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"> {text}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _update)

    # ── 미리보기 창 (s{n}) ───────────────────────────────────────
    def _show_preview(self, n):
        img_path = find_image_file(f"s{n}")
        if not img_path:
            messagebox.showinfo("미리보기", f"s{n} 파일이 없습니다.")
            return
        try:
            orig_img = Image.open(img_path)
        except Exception as e:
            messagebox.showerror("오류", f"이미지 로드 실패: {e}")
            return

        win = tk.Toplevel(self.root)
        win.title(f"s{n} 미리보기")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.geometry(f"{orig_img.width}x{orig_img.height}")

        canvas = tk.Canvas(win, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        state = {"photo": None}

        def _redraw(event=None):
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 2 or h < 2:
                return
            resized = orig_img.copy()
            resized.thumbnail((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            state["photo"] = photo
            canvas.delete("all")
            canvas.create_image(w // 2, h // 2, anchor="center", image=photo)

        canvas.bind("<Configure>", _redraw)

    # ── 이미지 캡처 저장 ─────────────────────────────────────────
    def _capture_image(self, prefix):
        self.root.withdraw()
        self.root.after(150, lambda: self._do_capture(prefix))

    def _do_capture(self, prefix):
        sel = RegionSelector(self.root)
        self.root.wait_window(sel)
        if not sel.region:
            self.root.deiconify()
            self._log("캡처 취소됨.")
            return
        time.sleep(0.15)
        x, y, w, h = sel.region
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.root.deiconify()
        for old in glob.glob(os.path.join(BASE_DIR, f"{prefix}.*")):
            os.remove(old)
        dest = os.path.join(BASE_DIR, f"{prefix}.png")
        shot.save(dest)
        self._reload_btn_image(prefix)
        self._log(f"{prefix}.png 저장됨.")

    def _reload_btn_image(self, prefix):
        photo = self._load_thumb(prefix)
        if photo and prefix in self._img_buttons:
            self._img_buttons[prefix].configure(image=photo, text="",
                                                width=self.IMG_W, height=self.IMG_H)

    # ── 매크로 범위 지정 진입 ───────────────────────────────────
    def _begin_region_select(self, required, loop_func):
        if self._macro_running:
            messagebox.showinfo("알림", "매크로가 실행 중입니다. 먼저 종료하세요.")
            return
        missing = [p for p in required if not find_image_file(p)]
        if missing:
            messagebox.showwarning("이미지 없음",
                f"{', '.join(missing)} 파일이 없습니다.\n이미지지정 버튼으로 먼저 캡처하세요.")
            return
        self._pending_loop = loop_func
        self.root.withdraw()
        self.root.after(150, self._open_selector)

    def _open_selector(self):
        sel = RegionSelector(self.root)
        self.root.wait_window(sel)
        self.root.deiconify()
        if sel.region:
            self._region = sel.region
            self._macro_running = True
            self._search_thread = threading.Thread(target=self._pending_loop, daemon=True)
            self._search_thread.start()
        else:
            self._log("범위 지정 취소됨.")

    def start_region_select_3(self):
        self._begin_region_select(("b1", "b2", "b3", "b4", "b5"), self._search_loop_3)

    def start_region_select_5(self):
        if self._macro_running:
            messagebox.showinfo("알림", "매크로가 실행 중입니다. 먼저 종료하세요.")
            return
        missing = [p for p in ("b2", "b3", "b4", "b5") if not find_image_file(p)]
        if missing:
            messagebox.showwarning("이미지 없음", f"{', '.join(missing)} 파일이 없습니다.")
            return
        if not find_image_file("b1") and not find_image_file("b6"):
            messagebox.showwarning("이미지 없음", "b1 또는 b6 파일이 필요합니다.")
            return
        self._pending_loop = self._search_loop_5
        self.root.withdraw()
        self.root.after(150, self._open_selector)

    def stop_macro(self):
        self._macro_running = False
        self._stop_sound()
        self._set_status("매크로 종료됨")

    # ── 공통 유틸 ────────────────────────────────────────────────
    def _press_f5(self):
        pyautogui.press("f5")

    def _stop_sound(self):
        pygame.mixer.music.stop()

    def _play_sound_loop(self):
        s1 = os.path.join(BASE_DIR, "s1.mp3")
        if not os.path.exists(s1):
            self._set_status("s1.mp3 파일 없음!")
            return
        pygame.mixer.music.load(s1)
        pygame.mixer.music.play(-1)

    def _match(self, template, region=None, threshold=0.85):
        if region:
            x, y, w, h = region
            shot = pyautogui.screenshot(region=(x, y, w, h))
            ox, oy = x, y
        else:
            shot = pyautogui.screenshot()
            ox, oy = 0, 0
        screen = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        try:
            wx = self.root.winfo_x(); wy = self.root.winfo_y()
            ww = self.root.winfo_width(); wh = self.root.winfo_height()
            sx1 = max(0, wx - ox); sy1 = max(0, wy - oy)
            sx2 = min(screen.shape[1], wx - ox + ww)
            sy2 = min(screen.shape[0], wy - oy + wh)
            if sx2 > sx1 and sy2 > sy1:
                screen[sy1:sy2, sx1:sx2] = 0
        except Exception:
            pass
        th_h, th_w = template.shape[:2]
        sc_h, sc_w = screen.shape[:2]
        if th_h > sc_h or th_w > sc_w:
            return None
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        if val >= threshold:
            return (ox + loc[0] + th_w // 2, oy + loc[1] + th_h // 2)
        return None

    # ── KTX 좌석예매 루프 ────────────────────────────────────────
    def _search_loop_3(self):
        region = self._region

        def load(prefix):
            p = find_image_file(prefix)
            if not p:
                self._set_status(f"{prefix} 파일 없음!")
                self._macro_running = False
                return None
            return cv2.imread(p, cv2.IMREAD_COLOR)

        def load_opt(prefix):
            p = find_image_file(prefix)
            return cv2.imread(p, cv2.IMREAD_COLOR) if p else None

        t1 = load("b1"); t2 = load("b2"); t3 = load("b3")
        t4 = load("b4"); t5 = load("b5")
        if any(t is None for t in (t1, t2, t3, t4, t5)):
            return

        while self._macro_running:
            self._set_status("b5 탐색 중... (전체화면)")
            pos10 = self._match(t5)
            if pos10:
                self._set_status("b5 발견 → 클릭!")
                pyautogui.click(pos10[0], pos10[1])
                time.sleep(0.5)
            else:
                self._set_status("b5 없음 → 건너뜀")

            while self._macro_running:
                self._set_status("b1 탐색 중... (범위)")
                pos = self._match(t1, region)
                if pos:
                    self._set_status("b1 발견 → 클릭!")
                    pyautogui.click(pos[0], pos[1])
                    break
                self._set_status("b1 없음 → F5")
                self._press_f5()
                time.sleep(1.0)
                while self._macro_running:
                    self._set_status("b5 대기 중... (페이지 로딩)")
                    if self._match(t5):
                        self._set_status("b5 감지 → 로딩 완료")
                        break
                    time.sleep(0.3)
                break

            if not self._macro_running:
                break

            self._set_status("b4 확인 중...")
            pos4 = self._match(t4)
            if pos4:
                self._set_status("b4 발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.5)
            else:
                self._set_status("b4 없음 → 바로 b2로")

            self._set_status("b2 탐색 중... (전체화면)")
            pos = self._match(t2)
            if not pos:
                self._set_status("b2 없음 → F5 후 b1부터 재시작")
                self._press_f5()
                time.sleep(1.0)
                while self._macro_running:
                    self._set_status("b5 대기 중... (재시작 로딩)")
                    if self._match(t5):
                        break
                    time.sleep(0.3)
                continue
            self._set_status("b2 발견 → 클릭!")
            time.sleep(0.2)
            pyautogui.click(pos[0], pos[1])
            time.sleep(0.5)

            self._set_status("b4 재확인 중...")
            pos4 = self._match(t4)
            if pos4:
                self._set_status("b4 재발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.5)

            self._set_status("b3 탐색 중... (전체화면)")
            pos = self._match(t3)
            if not pos:
                self._set_status("b3 없음 → 5초 후 재탐색")
                time.sleep(5.0)
                self._set_status("b3 재탐색 중... (전체화면)")
                pos = self._match(t3)
            if pos:
                self._set_status("b3 감지 → 소리 재생 중... (5분)")
                self._play_sound_loop()
                deadline = time.time() + 300
                while self._macro_running and time.time() < deadline:
                    time.sleep(0.5)
                self._stop_sound()
                self._macro_running = False
                self._set_status("소리 재생 완료")
                return
            self._set_status("b3 없음 → F5 후 b1부터 재시작")
            self._press_f5()
            time.sleep(1.0)
            while self._macro_running:
                self._set_status("b5 대기 중... (재시작 로딩)")
                if self._match(t5):
                    break
                time.sleep(0.3)

        self._stop_sound()
        self._set_status("대기 중")

    # ── KTX 입석포함예매 루프 ────────────────────────────────────
    def _search_loop_5(self):
        region = self._region

        def load_req(prefix):
            p = find_image_file(prefix)
            if not p:
                self._set_status(f"{prefix} 파일 없음!")
                self._macro_running = False
                return None
            return cv2.imread(p, cv2.IMREAD_COLOR)

        def load_opt(prefix):
            p = find_image_file(prefix)
            return cv2.imread(p, cv2.IMREAD_COLOR) if p else None

        t2 = load_req("b2"); t3 = load_req("b3")
        t4 = load_req("b4"); t5 = load_req("b5")
        if any(t is None for t in (t2, t3, t4, t5)):
            return
        t1 = load_opt("b1"); t6 = load_opt("b6")
        t7 = load_opt("b7"); t8 = load_opt("b8"); t9 = load_opt("b9")

        while self._macro_running:
            self._set_status("b5 탐색 중... (전체화면)")
            pos10 = self._match(t5)
            if pos10:
                self._set_status("b5 발견 → 클릭!")
                pyautogui.click(pos10[0], pos10[1])
                time.sleep(0.5)
            else:
                self._set_status("b5 없음 → 건너뜀")

            found_b7 = False

            while self._macro_running:
                self._set_status("b1/b6/b7 탐색 중... (범위)")
                pos = None
                if t1 is not None:
                    pos = self._match(t1, region)
                if pos is None and t6 is not None:
                    pos = self._match(t6, region)
                pos7 = self._match(t7, region) if t7 is not None else None

                if pos7:
                    self._set_status("b7 발견 → 클릭!")
                    pyautogui.click(pos7[0], pos7[1])
                    found_b7 = True
                    break
                if pos:
                    self._set_status("발견 → 클릭!")
                    pyautogui.click(pos[0], pos[1])
                    break

                self._set_status("b1/b6/b7 없음 → F5")
                self._press_f5()
                time.sleep(1.0)
                while self._macro_running:
                    self._set_status("b5 대기 중... (페이지 로딩)")
                    if self._match(t5):
                        self._set_status("b5 감지 → 로딩 완료")
                        break
                    time.sleep(0.3)
                break

            if not self._macro_running:
                break

            self._set_status("b4 확인 중...")
            pos4 = self._match(t4)
            if pos4:
                self._set_status("b4 발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.5)
            else:
                self._set_status("b4 없음 → 건너뜀")

            if found_b7:
                self._set_status("b8 탐색 중... (전체화면)")
                pos = self._match(t8) if t8 is not None else None
                if not pos:
                    self._set_status("b8 없음 → F5 후 재시작")
                    self._press_f5()
                    time.sleep(1.0)
                    continue
                self._set_status("b8 발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos[0], pos[1])
                time.sleep(0.5)
                self._set_status("b4 확인 중... (b8 후)")
                pos4 = self._match(t4)
                if pos4:
                    self._set_status("b4 발견 → 클릭!")
                    time.sleep(0.2)
                    pyautogui.click(pos4[0], pos4[1])
                    time.sleep(0.5)
                else:
                    self._set_status("b4 없음 → 건너뜀")
                self._set_status("b9 탐색 중... (전체화면)")
                pos9 = self._match(t9) if t9 is not None else None
                if pos9:
                    self._set_status("b9 발견 → 클릭!")
                    pyautogui.click(pos9[0], pos9[1])
                    time.sleep(0.5)
                self._set_status("b3 탐색 중... (전체화면)")
                pos = self._match(t3)
                if not pos:
                    self._set_status("b3 없음 → 5초 후 재탐색")
                    time.sleep(5.0)
                    self._set_status("b3 재탐색 중... (전체화면)")
                    pos = self._match(t3)
                if pos:
                    self._set_status("b3 감지 → 소리 재생 중... (5분)")
                    self._play_sound_loop()
                    deadline = time.time() + 300
                    while self._macro_running and time.time() < deadline:
                        time.sleep(0.5)
                    self._stop_sound()
                    self._macro_running = False
                    self._set_status("소리 재생 완료")
                    return
                self._set_status("b3 없음 → F5 후 처음부터 재시작")
                self._press_f5()
                time.sleep(1.0)
                while self._macro_running:
                    self._set_status("b5 대기 중... (재시작 로딩)")
                    if self._match(t5):
                        break
                    time.sleep(0.3)
                continue
            else:
                self._set_status("b2 탐색 중... (전체화면)")
                pos = self._match(t2)
                if not pos:
                    self._set_status("b2 없음 → F5 후 처음부터 재시작")
                    self._press_f5()
                    time.sleep(1.0)
                    while self._macro_running:
                        self._set_status("b5 대기 중... (재시작 로딩)")
                        if self._match(t5):
                            break
                        time.sleep(0.3)
                    continue
                self._set_status("b2 발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos[0], pos[1])
                time.sleep(0.5)

            self._set_status("b4 재확인 중...")
            pos4 = self._match(t4)
            if pos4:
                self._set_status("b4 재발견 → 클릭!")
                time.sleep(0.2)
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.5)
                if found_b7:
                    self._set_status("b9 탐색 중... (전체화면)")
                    pos9 = self._match(t9) if t9 is not None else None
                    if pos9:
                        self._set_status("b9 발견 → 클릭!")
                        pyautogui.click(pos9[0], pos9[1])
                        time.sleep(0.5)
            elif found_b7:
                self._set_status("b4 재확인 미발견 → F5 후 재시작")
                self._press_f5()
                time.sleep(1.0)
                while self._macro_running:
                    self._set_status("b5 대기 중... (재시작 로딩)")
                    if self._match(t5):
                        break
                    time.sleep(0.3)
                continue

            self._set_status("b3 탐색 중... (전체화면)")
            pos = self._match(t3)
            if not pos:
                self._set_status("b3 없음 → 5초 후 재탐색")
                time.sleep(5.0)
                self._set_status("b3 재탐색 중... (전체화면)")
                pos = self._match(t3)
            if pos:
                self._set_status("b3 감지 → 소리 재생 중... (5분)")
                self._play_sound_loop()
                deadline = time.time() + 300
                while self._macro_running and time.time() < deadline:
                    time.sleep(0.5)
                self._stop_sound()
                self._macro_running = False
                self._set_status("소리 재생 완료")
                return
            self._set_status("b3 없음 → F5 후 처음부터 재시작")
            self._press_f5()
            time.sleep(1.0)
            while self._macro_running:
                self._set_status("b5 대기 중... (재시작 로딩)")
                if self._match(t5):
                    break
                time.sleep(0.3)

        self._stop_sound()
        self._set_status("대기 중")

    def quit_app(self):
        if messagebox.askyesno("종료", "프로그램을 종료하시겠습니까?"):
            self._macro_running = False
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = KTXMacroApp(root)
    root.mainloop()
