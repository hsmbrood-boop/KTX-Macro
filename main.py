import tkinter as tk
from tkinter import messagebox, filedialog
import os
import sys
import glob
import shutil
import time
import threading
import ctypes

import cv2
import numpy as np
import pyautogui
import pygame

if sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)          # exe 폴더 (유저 파일)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)     # _internal/ (번들 파일)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

pyautogui.FAILSAFE = True
pygame.mixer.init()

BG        = "#1a1a2e"
HEADER_BG = "#16213e"
SEP       = "#2a2a4e"
TITLE_FG  = "#e94560"
SUB_FG    = "#8892b0"
STATUS_FG = "#64ffda"
START_BG  = "#1565c0"
STOP_BG   = "#c62828"
IMG_BG    = "#0d0d1a"
LOG_BG    = "#0d0d1a"
LOG_FG    = "#64ffda"
CAP_BG    = "#1a3050"


def find_image_file(prefix):
    for search_dir in (BASE_DIR, BUNDLE_DIR):
        for ext in ('png', 'jpg', 'jpeg', 'bmp'):
            p = os.path.join(search_dir, f'{prefix}.{ext}')
            if os.path.exists(p):
                return p
    return None


class RegionSelector(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.region = None
        self._sx = self._sy = 0
        self._rect = None
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.25)
        self.attributes('-topmost', True)
        self.configure(bg='black', cursor='crosshair')
        self.overrideredirect(True)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.canvas = tk.Canvas(self, width=sw, height=sh,
                                bg='black', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.create_text(sw // 2, 30, fill='white',
                                font=('Malgun Gothic', 14, 'bold'),
                                text='드래그하여 검색 범위를 지정하세요  (ESC: 취소)')
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Escape>', lambda e: self.destroy())

    def _on_press(self, e):
        self._sx = e.x
        self._sy = e.y
        if self._rect:
            self.canvas.delete(self._rect)
            self._rect = None

    def _on_drag(self, e):
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            self._sx, self._sy, e.x, e.y,
            outline='red', width=2, fill='white', stipple='gray25'
        )

    def _on_release(self, e):
        x1 = min(self._sx, e.x)
        y1 = min(self._sy, e.y)
        x2 = max(self._sx, e.x)
        y2 = max(self._sy, e.y)
        w = x2 - x1
        h = y2 - y1
        if w > 10 and h > 10:
            self.region = (x1, y1, w, h)
        self.destroy()


class KTXMacroApp:
    IMG_W = 90
    IMG_H = 46

    def __init__(self, root):
        self.root = root
        self.root.title('KTX 자동 예매 매크로')
        self.root.resizable(False, False)
        sh = self.root.winfo_screenheight()
        win_h = min(720, sh - 60)
        self.root.geometry(f'630x{win_h}+0+0')
        self.root.configure(bg=BG)
        self.root.attributes('-topmost', True)

        self._macro_running = False
        self._search_thread = None
        self._region = None
        self._pending_loop = None
        self._btn_photos = {}
        self._img_buttons = {}
        self._active_blink_frame = None
        self._active_blink_btn = None
        self._blink_job = None
        self._blink_state = False

        self.status_var = tk.StringVar(value='대기 중')

        self._build_ui()
        self.root.bind('<F12>', lambda e: self.stop_macro())

    # ── UI 빌드 ─────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._sep()
        self._build_status()
        self._build_image_grid()
        self._sep()
        self._build_stop_button()
        self._sep()
        self._build_log()
        self._build_footer()

    def _sep(self):
        tk.Frame(self.root, bg=SEP, height=1).pack(fill='x')

    def _build_header(self):
        f = tk.Frame(self.root, bg=HEADER_BG, pady=13)
        f.pack(fill='x')
        tk.Label(f, text='KTX 자동 예매 매크로',
                 font=('Malgun Gothic', 16, 'bold'),
                 bg=HEADER_BG, fg=TITLE_FG).pack()

    def _build_status(self):
        f = tk.Frame(self.root, bg=BG, pady=7)
        f.pack(fill='x', padx=18)
        tk.Label(f, text='상태:', font=('Malgun Gothic', 9),
                 bg=BG, fg=SUB_FG).pack(side='left')
        self.status_lbl = tk.Label(f, textvariable=self.status_var,
                                   font=('Malgun Gothic', 9, 'bold'),
                                   bg=BG, fg=STATUS_FG)
        self.status_lbl.pack(side='left', padx=4)

    def _build_image_grid(self):
        lf = tk.Frame(self.root, bg=BG, padx=16, pady=5)
        lf.pack(fill='x')

        gf = tk.Frame(self.root, bg=BG, padx=10, pady=4)
        gf.pack(fill='x')

        for c in range(1, 5):
            gf.columnconfigure(c, weight=1)

        groups = [
            ('KTX\n좌석예매',    self.start_region_select_3, [
                (0, 1, 'b1', 'b1'),
                (0, 2, 'b2', 'b2'),
                (0, 3, 'b3', 'b3'),
                (0, 4, 'b4', 'b4'),
            ]),
            ('KTX\n입석포함예매', self.start_region_select_5, [
                (2, 1, 'b5', 'b5'),
                (2, 2, 'b6', 'b6'),
                (2, 3, 'b7', 'b7'),
                (2, 4, 'b8', 'b8'),
            ]),
        ]
        extra = [(4, 1, 'b9', 'b9')]

        for i, (label, cmd, items) in enumerate(groups):
            border_f = tk.Frame(gf, bg=BG, padx=5, pady=5)
            border_f.grid(row=i * 2, column=0, rowspan=2, padx=4, pady=6, sticky='nsew')
            btn = tk.Button(border_f, text=label,
                            font=('Malgun Gothic', 10, 'bold'),
                            bg=START_BG, fg='white',
                            activebackground='#1976d2',
                            activeforeground='white',
                            relief='flat', cursor='hand2')
            btn.configure(command=lambda c=cmd, f=border_f, b=btn: self._on_mode_btn(c, f, b))
            btn.pack(fill='both', expand=True)

            for grid_row, col, prefix, n in items:
                self._make_img_cell(gf, grid_row, col, prefix, n)

        for grid_row, col, prefix, n in extra:
            self._make_img_cell(gf, grid_row, col, prefix, n)

    def _make_img_cell(self, gf, grid_row, col, prefix, n):
        photo = self._load_thumb(prefix)
        img_btn = tk.Button(gf,
                            image=photo if photo else '',
                            command=lambda p=n: self._show_preview(p),
                            width=self.IMG_W, height=self.IMG_H,
                            bg=IMG_BG, activebackground='#1a1a3e',
                            relief='flat', cursor='hand2', bd=0)
        if not photo:
            img_btn.configure(text=n, font=('Malgun Gothic', 9), fg='#555577')
        img_btn.grid(row=grid_row, column=col, padx=4, pady=6, sticky='nsew')
        self._img_buttons[prefix] = img_btn

        cap_btn = tk.Button(gf,
                            text=n + ' 이미지지정',
                            font=('Malgun Gothic', 8),
                            fg=STATUS_FG,
                            bg=CAP_BG, activebackground='#1a3050',
                            relief='flat', cursor='hand2',
                            command=lambda p=prefix: self._capture_image(p))
        cap_btn.grid(row=grid_row + 1, column=col, padx=(4, 1), pady=1, sticky='ew')

    def _build_stop_button(self):
        f = tk.Frame(self.root, bg=BG, padx=16, pady=10)
        f.pack(fill='x')
        tk.Button(f, text='⏹  매크로 종료  (F12)',
                  font=('Malgun Gothic', 12, 'bold'),
                  bg=STOP_BG, fg='white',
                  activebackground='#d32f2f', activeforeground='white',
                  relief='flat', cursor='hand2', height=2,
                  command=self.stop_macro).pack(fill='x')

    def _build_log(self):
        f = tk.Frame(self.root, bg=HEADER_BG, padx=12, pady=8)
        f.pack(fill='both', expand=True)
        tk.Label(f, text='로그', font=('Malgun Gothic', 8),
                 bg=HEADER_BG, fg=SUB_FG).pack(anchor='w')
        self.log_text = tk.Text(f, height=6, bg=LOG_BG, fg=LOG_FG,
                                font=('Consolas', 8), relief='flat',
                                state='disabled', wrap='word',
                                insertbackground=LOG_FG)
        self.log_text.pack(fill='both', expand=True)
        self._log('프로그램 시작됨.')

    def _build_footer(self):
        f = tk.Frame(self.root, bg=BG, pady=6)
        f.pack(fill='x')
        cv = tk.Canvas(f, bg=BG, highlightthickness=0, height=42, width=370)
        cv.pack()
        x1, y1, x2, y2, r = 2, 2, 368, 40, 14
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1,
            x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2,
            x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        cv.create_polygon(pts, smooth=True, fill='white', outline='#cc2222', width=4)
        cv.create_text(185, 21, text='Developed by HSM of Orc Holdings.',
                       font=('Malgun Gothic', 11, 'bold'), fill='#111111')

    # ── 헬퍼 ────────────────────────────────────────────────────

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
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'> {text}\n')
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
        self.root.after(0, _update)

    def _show_preview(self, n):
        img_path = find_image_file('s' + n[1:])
        if not img_path:
            messagebox.showinfo('오류', f'{n} 파일이 없습니다.')
            return
        try:
            img = Image.open(img_path)
        except Exception as e:
            messagebox.showerror('오류', f'이미지 로드 실패: {e}')
            return
        win = tk.Toplevel(self.root)
        win.title(f'{n} 미리보기')
        win.attributes('-topmost', True)
        win.resizable(True, True)
        win.geometry(f'{img.width}x{img.height}')
        cv = tk.Canvas(win, bg='black', highlightthickness=0)
        cv.pack(fill='both', expand=True)
        _img_ref = [img]

        def _redraw(event=None):
            cv.delete('photo')
            w = cv.winfo_width() or img.width
            h = cv.winfo_height() or img.height
            display = _img_ref[0].copy()
            display.thumbnail((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(display)
            cv._photo = photo
            cv.create_image(w // 2, h // 2, anchor='center', image=photo, tags='photo')

        win.bind('<Configure>', _redraw)
        win.after(50, _redraw)

    def _capture_image(self, prefix):
        self.root.withdraw()
        self.root.after(150, lambda: self._do_capture(prefix))

    def _do_capture(self, prefix):
        try:
            sel = RegionSelector(self.root)
            self.root.wait_window(sel)
            self.root.deiconify()
            if sel.region is None:
                self._log('캡처 취소됨.')
                return
            x, y, w, h = sel.region
            time.sleep(0.15)
            shot = pyautogui.screenshot(region=(x, y, w, h))
            for old in glob.glob(os.path.join(BASE_DIR, f'{prefix}.*')):
                os.remove(old)
            dest = os.path.join(BASE_DIR, f'{prefix}.png')
            shot.save(dest)
            if os.path.exists(dest):
                self._log(f'{prefix}.png 저장됨. ({dest})')
            else:
                self._log(f'[오류] {prefix}.png 저장 실패! 경로: {dest}')
            self._reload_btn_image(prefix)
        except Exception as e:
            self.root.deiconify()
            self._log(f'[오류] 캡처 실패: {e}')

    def _reload_btn_image(self, prefix):
        photo = self._load_thumb(prefix)
        btn = self._img_buttons.get(prefix)
        if btn:
            if photo:
                btn.configure(image=photo, text='', width=self.IMG_W, height=self.IMG_H)
            else:
                btn.configure(image='', text=prefix)

    def _begin_region_select(self, required, loop_func):
        if self._macro_running:
            messagebox.showinfo('알림', '매크로가 실행 중입니다. 먼저 종료하세요.')
            return
        missing = [b for b in required if not find_image_file(b)]
        if missing:
            messagebox.showwarning('이미지 없음',
                                   f'아래 이미지를 먼저 지정하세요:\n{", ".join(missing)}\n\n각 버튼 옆 "이미지지정" 버튼으로 캡처하세요.')
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
            self._set_status('매크로 시작!')
            t = threading.Thread(target=self._pending_loop, daemon=True)
            self._search_thread = t
            t.start()
            self._start_blink()
        else:
            self._reset_blink_ui()
            self._active_blink_frame = None
            self._active_blink_btn = None
            self._set_status('범위 지정 취소됨.')

    def _on_mode_btn(self, cmd, border_frame, btn=None):
        self._active_blink_frame = border_frame
        self._active_blink_btn = btn
        cmd()

    def start_region_select_3(self):
        self._begin_region_select(('b1', 'b2', 'b3', 'b4', 'b5'), self._search_loop_3)

    def start_region_select_5(self):
        if self._macro_running:
            messagebox.showinfo('알림', '매크로가 실행 중입니다. 먼저 종료하세요.')
            return
        missing = [b for b in ('b2', 'b3', 'b4', 'b5') if not find_image_file(b)]
        if missing:
            messagebox.showwarning('이미지 없음', f'아래 이미지를 먼저 지정하세요:\n{", ".join(missing)}')
            return
        if not find_image_file('b1') and not find_image_file('b6'):
            messagebox.showwarning('이미지 없음', 'b1 또는 b6 파일이 필요합니다.')
            return
        self._pending_loop = self._search_loop_5
        self.root.withdraw()
        self.root.after(150, self._open_selector)

    def stop_macro(self):
        self._macro_running = False
        self._stop_sound()
        self._stop_blink()
        self._set_status('매크로 종료됨')

    def _start_blink(self):
        if self._blink_job:
            self.root.after_cancel(self._blink_job)
            self._blink_job = None
        self._blink_state = True
        self._do_blink()

    def _do_blink(self):
        if not self._macro_running or self._active_blink_frame is None:
            self._reset_blink_ui()
            return
        if self._blink_state:
            try:
                self._active_blink_frame.configure(
                    highlightbackground='#ffd700', highlightthickness=4)
            except Exception:
                pass
            try:
                if self._active_blink_btn:
                    self._active_blink_btn.configure(bg='#ffd700', fg='#1a1a2e')
            except Exception:
                pass
        else:
            try:
                self._active_blink_frame.configure(
                    highlightbackground=BG, highlightthickness=4)
            except Exception:
                pass
            try:
                if self._active_blink_btn:
                    self._active_blink_btn.configure(bg=START_BG, fg='white')
            except Exception:
                pass
        self._blink_state = not self._blink_state
        self._blink_job = self.root.after(400, self._do_blink)

    def _reset_blink_ui(self):
        try:
            if self._active_blink_frame:
                self._active_blink_frame.configure(
                    highlightbackground=BG, highlightthickness=0)
        except Exception:
            pass
        try:
            if self._active_blink_btn:
                self._active_blink_btn.configure(bg=START_BG, fg='white')
        except Exception:
            pass

    def _stop_blink(self):
        if self._blink_job:
            self.root.after_cancel(self._blink_job)
            self._blink_job = None
        self._reset_blink_ui()
        self._active_blink_frame = None
        self._active_blink_btn = None

    # ── 매크로 유틸 ─────────────────────────────────────────────

    def _press_f5(self):
        pyautogui.press('f5')

    def _stop_sound(self):
        pygame.mixer.music.stop()

    def _play_sound_loop(self):
        s1 = os.path.join(BASE_DIR, 's1.mp3')
        if not os.path.exists(s1):
            s1 = os.path.join(BUNDLE_DIR, 's1.mp3')
        if not os.path.exists(s1):
            self._set_status('s1.mp3 파일 없음!')
            return
        pygame.mixer.music.load(s1)
        pygame.mixer.music.play(-1)

    def _match(self, template, region=None, threshold=0.80):
        if region:
            x, y, w, h = region
            shot = pyautogui.screenshot(region=(x, y, w, h))
            ox, oy = x, y
        else:
            shot = pyautogui.screenshot()
            ox, oy = 0, 0
        screen = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        try:
            wx = self.root.winfo_x();  wy = self.root.winfo_y()
            ww = self.root.winfo_width(); wh = self.root.winfo_height()
            sx1 = max(0, wx - ox);  sy1 = max(0, wy - oy)
            sx2 = min(screen.shape[1], wx - ox + ww)
            sy2 = min(screen.shape[0], wy - oy + wh)
            if sx2 > sx1 and sy2 > sy1:
                screen[sy1:sy2, sx1:sx2] = 0
        except Exception:
            pass
        th_h, th_w = template.shape[:2]
        if th_h > screen.shape[0] or th_w > screen.shape[1]:
            return None
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        if val >= threshold:
            return (ox + loc[0] + th_w // 2, oy + loc[1] + th_h // 2)
        return None

    def _load(self, prefix):
        p = find_image_file(prefix)
        if not p:
            self._set_status(f'{prefix} 파일 없음!')
            self._macro_running = False
            return None
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            self._set_status(f'{prefix} 로드 실패! (경로 오류)')
            self._macro_running = False
        return img

    # ── 매크로 루프 3 (좌석예매) ─────────────────────────────────

    def _search_loop_3(self):
        region = self._region
        t1 = self._load('b1')
        t2 = self._load('b2')
        t3 = self._load('b3')
        t4 = self._load('b4')
        t5 = self._load('b5')

        if any(t is None for t in [t1, t2, t3, t4, t5]):
            self.root.after(0, self._stop_blink)
            return
        self._set_status('이미지 로드 완료. 탐색 시작...')

        while self._macro_running:
            # b5 1회 탐색
            self._set_status('b5 탐색 중... (전체화면)')
            pos10 = self._match(t5)
            if pos10:
                self._set_status('b5 발견 → 클릭!')
                pyautogui.click(pos10[0], pos10[1])
                time.sleep(0.5)
            else:
                self._set_status('b5 없음 → 건너뜀')
                continue

            # b1 범위 탐색
            self._set_status('b1 탐색 중... (범위)')
            pos = self._match(t1, region=region)
            if pos:
                self._set_status('b1 발견 → 클릭!')
                pyautogui.click(pos[0], pos[1])
            else:
                self._set_status('b1 없음 → F5')
                self._press_f5()
                time.sleep(1.0)
                continue

            # 페이지 로딩 대기 (b5)
            self._set_status('b5 대기 중... (페이지 로딩)')
            while self._macro_running:
                pos10 = self._match(t5)
                if pos10:
                    self._set_status('b5 감지 → 로딩 완료')
                    break
                time.sleep(0.3)

            if not self._macro_running:
                break

            # b4 확인
            self._set_status('b4 확인 중...')
            pos4 = self._match(t4)
            if pos4:
                self._set_status('b4 발견 → 클릭!')
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.2)
            else:
                self._set_status('b4 없음 → 바로 b2로')

            # b2 탐색
            self._set_status('b2 탐색 중... (전체화면)')
            pos = self._match(t2)
            if not pos:
                self._set_status('b2 없음 → F5 후 b1부터 재시작')
                self._press_f5()
                time.sleep(1.0)
                self._set_status('b5 대기 중... (재시작 로딩)')
                while self._macro_running:
                    pos10 = self._match(t5)
                    if pos10:
                        break
                    time.sleep(0.3)
                continue

            self._set_status('b2 발견 → 클릭!')
            pyautogui.click(pos[0], pos[1])

            # b4 재확인
            self._set_status('b4 재확인 중...')
            pos4 = self._match(t4)
            if pos4:
                self._set_status('b4 재발견 → 클릭!')
                pyautogui.click(pos4[0], pos4[1])

            # b3 탐색: 즉시 → 2초 후 재탐색 → 3초 후 재탐색
            self._set_status('b3 탐색 중... (전체화면)')
            pos = self._match(t3)
            if not pos:
                self._set_status('b3 없음 → 2초 후 재탐색')
                time.sleep(2.0)
                self._set_status('b3 재탐색 중... (전체화면)')
                pos = self._match(t3)
            if not pos:
                self._set_status('b3 없음 → 3초 후 재탐색')
                time.sleep(3.0)
                self._set_status('b3 재탐색 중... (전체화면)')
                pos = self._match(t3)

            if pos:
                self._set_status('b3 감지 → 소리 재생 중... (5분)')
                self._play_sound_loop()
                deadline = time.time() + 300
                while self._macro_running and time.time() < deadline:
                    time.sleep(0.5)
                self._stop_sound()
                self._macro_running = False
                self.root.after(0, self._stop_blink)
                self._set_status('소리 재생 완료')
                return
            else:
                self._set_status('b3 없음 → F5 후 b1부터 재시작')
                self._press_f5()
                time.sleep(1.0)

        self._set_status('대기 중')

    # ── 매크로 루프 5 (입석포함예매) ─────────────────────────────

    def _search_loop_5(self):
        region = self._region
        t2 = self._load('b2')
        t3 = self._load('b3')
        t4 = self._load('b4')
        t5 = self._load('b5')
        t1 = self._load('b1') if find_image_file('b1') else None
        t6 = self._load('b6') if find_image_file('b6') else None
        t7 = self._load('b7') if find_image_file('b7') else None
        t8 = self._load('b8') if find_image_file('b8') else None
        t9 = self._load('b9') if find_image_file('b9') else None

        if any(t is None for t in [t2, t3, t4, t5]):
            self.root.after(0, self._stop_blink)
            return
        self._set_status('이미지 로드 완료. 탐색 시작...')

        while self._macro_running:
            # 1. b5 1회 탐색
            self._set_status('b5 탐색 중... (전체화면)')
            pos10 = self._match(t5)
            if pos10:
                self._set_status('b5 발견 → 클릭!')
                pyautogui.click(pos10[0], pos10[1])
                time.sleep(0.5)
            else:
                self._set_status('b5 없음 → 건너뜀')
                continue

            # 2. 범위 탐색: b7 우선, 없으면 b1/b6
            found_b7 = False
            self._set_status('b1/b6/b7 탐색 중... (범위)')
            if t7 is not None:
                pos7 = self._match(t7, region=region)
                if pos7:
                    found_b7 = True
                    self._set_status('b7 발견 → 클릭!')
                    pyautogui.click(pos7[0], pos7[1])

            if not found_b7:
                pos = None
                for key, t in [('b1', t1), ('b6', t6)]:
                    if t is not None:
                        pos = self._match(t, region=region)
                        if pos:
                            self._set_status(f'{key} 발견 → 클릭!')
                            pyautogui.click(pos[0], pos[1])
                            break
                if not pos:
                    self._set_status('b1/b6/b7 없음 → F5')
                    self._press_f5()
                    time.sleep(1.0)
                    continue

            # 3. 페이지 로딩 대기 (b5)
            self._set_status('b5 대기 중... (페이지 로딩)')
            while self._macro_running:
                pos10 = self._match(t5)
                if pos10:
                    self._set_status('b5 감지 → 로딩 완료')
                    break
                time.sleep(0.3)

            if not self._macro_running:
                break

            # 4. b4 확인 (공통)
            self._set_status('b4 확인 중...')
            pos4 = self._match(t4)
            if pos4:
                self._set_status('b4 발견 → 클릭!')
                pyautogui.click(pos4[0], pos4[1])
                time.sleep(0.2)
            else:
                self._set_status('b4 없음 → 건너뜀')

            if found_b7:
                # b7 경로: b8 탐색
                self._set_status('b8 탐색 중... (전체화면)')
                pos = self._match(t8) if t8 is not None else None
                if not pos:
                    self._set_status('b8 없음 → F5 후 재시작')
                    self._press_f5()
                    time.sleep(1.0)
                    continue
                self._set_status('b8 발견 → 클릭!')
                pyautogui.click(pos[0], pos[1])

                # b4 재확인 (b8 후)
                self._set_status('b4 확인 중... (b8 후)')
                pos4 = self._match(t4)
                if pos4:
                    pyautogui.click(pos4[0], pos4[1])
                    time.sleep(0.2)

                # b9 탐색
                self._set_status('b9 탐색 중... (전체화면)')
                pos9 = self._match(t9) if t9 is not None else None
                if pos9:
                    self._set_status('b9 발견 → 클릭!')
                    pyautogui.click(pos9[0], pos9[1])

                # b3 탐색: 즉시 → 2초 후 재탐색 → 3초 후 재탐색
                self._set_status('b3 탐색 중... (전체화면)')
                pos = self._match(t3)
                if not pos:
                    self._set_status('b3 없음 → 2초 후 재탐색')
                    time.sleep(2.0)
                    self._set_status('b3 재탐색 중... (전체화면)')
                    pos = self._match(t3)
                if not pos:
                    self._set_status('b3 없음 → 3초 후 재탐색')
                    time.sleep(3.0)
                    self._set_status('b3 재탐색 중... (전체화면)')
                    pos = self._match(t3)

                if pos:
                    self._set_status('b3 감지 → 소리 재생 중... (5분)')
                    self._play_sound_loop()
                    deadline = time.time() + 300
                    while self._macro_running and time.time() < deadline:
                        time.sleep(0.5)
                    self._stop_sound()
                    self._macro_running = False
                    self.root.after(0, self._stop_blink)
                    self._set_status('소리 재생 완료')
                    return
                else:
                    self._set_status('b3 없음 → F5 후 처음부터 재시작')
                    self._press_f5()
                    time.sleep(1.0)
                    self._set_status('b5 대기 중... (재시작 로딩)')
                    while self._macro_running:
                        pos10 = self._match(t5)
                        if pos10:
                            break
                        time.sleep(0.3)

            else:
                # b1/b6 경로: b2 탐색
                self._set_status('b2 탐색 중... (전체화면)')
                pos = self._match(t2)
                if not pos:
                    self._set_status('b2 없음 → F5 후 처음부터 재시작')
                    self._press_f5()
                    time.sleep(1.0)
                    self._set_status('b5 대기 중... (재시작 로딩)')
                    while self._macro_running:
                        pos10 = self._match(t5)
                        if pos10:
                            break
                        time.sleep(0.3)
                    continue
                self._set_status('b2 발견 → 클릭!')
                pyautogui.click(pos[0], pos[1])

                # b4 재확인 (있으면 클릭, 없으면 그냥 진행)
                self._set_status('b4 재확인 중...')
                pos4 = self._match(t4)
                if pos4:
                    self._set_status('b4 재발견 → 클릭!')
                    pyautogui.click(pos4[0], pos4[1])
                    time.sleep(0.2)
                else:
                    self._set_status('b4 없음 → 그냥 진행')

                # b3 탐색: 즉시 → 2초 후 재탐색 → 3초 후 재탐색
                self._set_status('b3 탐색 중... (전체화면)')
                pos = self._match(t3)
                if not pos:
                    self._set_status('b3 없음 → 2초 후 재탐색')
                    time.sleep(2.0)
                    self._set_status('b3 재탐색 중... (전체화면)')
                    pos = self._match(t3)
                if not pos:
                    self._set_status('b3 없음 → 3초 후 재탐색')
                    time.sleep(3.0)
                    self._set_status('b3 재탐색 중... (전체화면)')
                    pos = self._match(t3)

                if pos:
                    self._set_status('b3 감지 → 소리 재생 중... (5분)')
                    self._play_sound_loop()
                    deadline = time.time() + 300
                    while self._macro_running and time.time() < deadline:
                        time.sleep(0.5)
                    self._stop_sound()
                    self._macro_running = False
                    self.root.after(0, self._stop_blink)
                    self._set_status('소리 재생 완료')
                    return
                else:
                    self._set_status('b3 없음 → F5 후 처음부터 재시작')
                    self._press_f5()
                    time.sleep(1.0)
                    self._set_status('b5 대기 중... (재시작 로딩)')
                    while self._macro_running:
                        pos10 = self._match(t5)
                        if pos10:
                            break
                        time.sleep(0.3)

        self._set_status('대기 중')

    def quit_app(self):
        if messagebox.askyesno('종료', '프로그램을 종료하시겠습니까?'):
            self._macro_running = False
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = KTXMacroApp(root)
    root.mainloop()
