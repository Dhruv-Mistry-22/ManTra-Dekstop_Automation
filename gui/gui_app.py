# -*- coding: utf-8 -*-
# gui_app.py -- Mantra V2 // Holographic Command Interface
# Layout: Frameless | Circuit BG | Left Sidebar | Stacked Pages | Right Panel | Terminal Bar

import sys, math, random
from datetime import datetime

# CRITICAL WINDOWS FIX: Pre-import input_module on the main GUI thread.
# This forces PyTorch to initialize its DLLs safely on the main thread.
import modules.input_module

import winsound
import os

def play_sound(name):
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", f"{name}.wav")
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

# Disable PyAutoGUI fail-safe globally so all system commands work
# regardless of where the mouse cursor is on screen.
import pyautogui
pyautogui.FAILSAFE = False


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QStackedWidget, QFrame, QScrollArea, QGridLayout, QMessageBox,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QRectF, QPointF, pyqtProperty,
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QRadialGradient, QFont, QPainterPath,
)

import psutil

# ---- Safe module imports with stubs -----------------------------------------
try:
    from modules.app_controller import open_or_switch_app, close_app, list_running_apps
except Exception:
    def open_or_switch_app(name): return f"[stub] Would open: {name}"
    def close_app(name):          return f"[stub] Would close: {name}"
    def list_running_apps():      return "[stub] list_running_apps"

try:
    from modules.file_manager import (create_file, create_folder, delete_file,
                                       delete_folder, search_files, rename_file, move_file)
except Exception:
    def create_file(p):          return f"[stub] create_file: {p}"
    def create_folder(p):        return f"[stub] create_folder: {p}"
    def delete_file(p):          return f"[stub] delete_file: {p}"
    def delete_folder(p):        return f"[stub] delete_folder: {p}"
    def search_files(k):         return f"[stub] search: {k}"
    def rename_file(a, b):       return f"[stub] rename: {a} -> {b}"
    def move_file(a, b):         return f"[stub] move: {a} -> {b}"

try:
    from modules.system_control import (shutdown_system, restart_system, lock_system,
                                         logout_user, sleep_system, increase_volume,
                                         decrease_volume, mute_volume, get_system_info)
except Exception:
    def shutdown_system():  return "[stub] shutdown"
    def restart_system():   return "[stub] restart"
    def lock_system():      return "[stub] lock"
    def logout_user():      return "[stub] logout"
    def sleep_system():     return "[stub] sleep"
    def increase_volume():  return "[stub] vol+"
    def decrease_volume():  return "[stub] vol-"
    def mute_volume():      return "[stub] mute"
    def get_system_info():  return "[stub] sysinfo"

try:
    from modules.text_input_assistant import (type_text, copy_text, paste_text,
                                              select_all, undo_action, redo_action)
except Exception:
    def type_text(t):   return f"[stub] type: {t}"
    def copy_text():    return "[stub] copy"
    def paste_text():   return "[stub] paste"
    def select_all():   return "[stub] select all"
    def undo_action():  return "[stub] undo"
    def redo_action():  return "[stub] redo"

try:
    from modules.db_manager import get_recent_commands, log_command
    DB_OK = True
except Exception:
    DB_OK = False
    def get_recent_commands(n): return []

# ---- Design Tokens ----------------------------------------------------------
BG     = "#060D20"
PANEL  = "#091428"
CARD   = "#0C1A32"
BORDER = "#1A3355"
CYAN   = "#00D4FF"
BLUE   = "#0066FF"
GREEN  = "#00FF88"
RED    = "#FF2255"
AMBER  = "#FFB800"
VIOLET = "#8855FF"
WHITE  = "#E2EEFF"
MUTED  = "#3A5478"
DIM    = "#162840"
TEXT   = "#A8C4E0"


# =============================================================================
# CIRCUIT BOARD BACKGROUND
# =============================================================================
class HexLogo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
    def paintEvent(self, _):
        from PyQt5.QtCore import Qt, QPointF
        from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 2
        pts = [QPointF(cx + r * math.cos(math.pi/180*(60*i-30)), cy + r * math.sin(math.pi/180*(60*i-30))) for i in range(6)]
        poly = QPolygonF(pts)
        p.setBrush(QBrush(QColor(0, 212, 255, 20)))
        p.setPen(QPen(QColor(0, 212, 255, 64), 0.8))
        p.drawPolygon(poly)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 212, 255, 128), 1.5))
        p.drawPolygon(poly)
        p.setPen(QPen(QColor(0, 212, 255, 102), 1))
        for i in (0, 2, 4): p.drawLine(QPointF(cx, cy), pts[i])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#00D4FF")))
        p.drawEllipse(QPointF(cx, cy), 3, 3)
        p.end()

class SlimGauge(QWidget):
    def __init__(self, label, accent, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 20)
        self._label = label
        self._accent = QColor(accent)
        self._value = 0.0
    def set_value(self, v):
        self._value = max(0.0, min(100.0, v))
        self.update()
    def paintEvent(self, _):
        from PyQt5.QtCore import Qt, QRectF
        from PyQt5.QtGui import QPainter, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("Consolas", 7))
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(0, 0, 30, 10), Qt.AlignLeft, self._label)
        p.setPen(self._accent)
        p.drawText(QRectF(22, 0, 30, 10), Qt.AlignRight, f"{int(self._value)}%")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(0, 14, 52, 4, 2, 2)
        fw = int(52 * (self._value / 100))
        if fw > 0:
            p.setBrush(self._accent)
            p.drawRoundedRect(0, 14, fw, 4, 2, 2)
        p.end()

from PyQt5.QtWidgets import QStyledItemDelegate
class LogDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        from PyQt5.QtCore import Qt, QRectF
        from PyQt5.QtGui import QPainter, QColor, QFont
        painter.setRenderHint(QPainter.Antialiasing)
        r = option.rect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRect(r)
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawRect(r.x(), r.bottom(), r.width(), 1)
        
        text = index.data(Qt.DisplayRole)
        status = index.data(Qt.UserRole)
        intent = index.data(Qt.UserRole + 1) or ""
        ts = index.data(Qt.UserRole + 3) or ""
        
        bc = QColor("#00FF88")
        if status == "error": bc = QColor("#FF2255")
        bc.setAlpha(180)
        painter.setBrush(bc)
        painter.drawRect(r.x(), r.y(), 3, r.height())
        
        painter.setPen(QColor("#A8C4E0"))
        painter.setFont(QFont("Consolas", 10))
        painter.drawText(QRectF(r.x() + 12, r.y(), r.width() - 120, r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)
        
        if intent:
            fm = painter.fontMetrics()
            tw = fm.width(intent)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 212, 255, 20))
            pr = QRectF(r.x() + 12 + fm.width(text) + 10, r.y() + (r.height()-16)/2, tw + 12, 16)
            painter.drawRoundedRect(pr, 8, 8)
            painter.setPen(QColor(0, 212, 255, 178))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(pr, Qt.AlignCenter, intent)
            
        painter.setPen(QColor(255, 255, 255, 38))
        painter.drawText(QRectF(r.x(), r.y(), r.width() - 12, r.height()), Qt.AlignVCenter | Qt.AlignRight, ts)
    def sizeHint(self, option, index):
        from PyQt5.QtCore import QSize
        return QSize(200, 32)

class TitleBarBg(QWidget):
    def paintEvent(self, _):
        from PyQt5.QtGui import QPainter, QLinearGradient, QColor
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(0, 212, 255, 18))
        g.setColorAt(1, QColor(0, 212, 255, 5))
        p.fillRect(self.rect(), g)
        p.setPen(QColor(0, 212, 255, 64))
        p.drawLine(0, self.height()-1, self.width(), self.height()-1)

class CircuitBG(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._scan  = 0
        self._frame = 0
        self._segs  = []
        self._dots  = []
        self._ready = False
        t = QTimer(self); t.timeout.connect(self._tick); t.start(28)

    def _build(self):
        w, h = self.width(), self.height()
        if w < 50: return
        random.seed(7)
        G = 44
        self._segs, self._dots = [], []
        for r in range(h // G + 2):
            for c in range(w // G + 2):
                x, y = c * G, r * G
                if random.random() < 0.55:
                    if c < w // G and random.random() < 0.5:
                        self._segs.append((x, y, x + G, y))
                    if r < h // G and random.random() < 0.5:
                        self._segs.append((x, y, x, y + G))
                    if random.random() < 0.28:
                        self._dots.append((x, y, random.choice([2, 3, 4])))
        self._ready = True

    def _tick(self):
        h = max(self.height(), 1)
        self._scan  = (self._scan + 1) % h
        self._frame = (self._frame + 1) % 360
        self.update()

    def paintEvent(self, _):
        if not self._ready and self.width() > 100:
            self._build()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0,  QColor("#060D20"))
        g.setColorAt(0.5,  QColor("#091428"))
        g.setColorAt(1.0,  QColor("#060D20"))
        p.fillRect(self.rect(), g)

        if not self._ready:
            p.end(); return

        # Circuit traces
        tc = QColor(CYAN); tc.setAlpha(28)
        p.setPen(QPen(tc, 1))
        for x1, y1, x2, y2 in self._segs:
            p.drawLine(x1, y1, x2, y2)

        # Junction dots
        dc = QColor(CYAN); dc.setAlpha(45)
        p.setPen(Qt.NoPen); p.setBrush(dc)
        for dx, dy, dr in self._dots:
            p.drawEllipse(QPointF(dx, dy), dr, dr)

        # Horizontal grid
        gc = QColor(BLUE); gc.setAlpha(12)
        p.setPen(QPen(gc, 1))
        for y in range(0, h, 80):
            p.drawLine(0, y, w, y)

        # Scanner sweep
        sy = self._scan
        sg = QLinearGradient(0, sy - 70, 0, sy + 2)
        sg.setColorAt(0.0, QColor(0, 0, 0, 0))
        c1 = QColor(CYAN); c1.setAlpha(18)
        sg.setColorAt(0.85, c1)
        c2 = QColor(CYAN); c2.setAlpha(55)
        sg.setColorAt(1.0,  c2)
        p.fillRect(0, max(0, sy - 70), w, 72, sg)
        sl = QColor(CYAN); sl.setAlpha(90)
        p.setPen(QPen(sl, 1))
        p.drawLine(0, sy, w, sy)

        # Corner glows
        for cx, cy in [(0, 0), (w, 0), (0, h), (w, h)]:
            rg = QRadialGradient(cx, cy, 220)
            cc = QColor(BLUE); cc.setAlpha(35)
            rg.setColorAt(0, cc); rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen); p.setBrush(rg)
            p.drawEllipse(cx - 220, cy - 220, 440, 440)
        p.end()


# =============================================================================
# SIDEBAR NAVIGATION BUTTON
# =============================================================================
class NavBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon, label, accent=CYAN, parent=None):
        super().__init__(parent)
        self._icon   = icon
        self._label  = label.upper()
        self._accent = QColor(accent)
        self._active = False
        self._alpha  = 0
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"_fa")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def get_fa(self): return self._alpha
    def set_fa(self, v): self._alpha = v; self.update()
    _fa = pyqtProperty(int, get_fa, set_fa)

    def setActive(self, v):
        self._active = v
        self._alpha  = 45 if v else 0
        self.update()

    def enterEvent(self, _):
        if not self._active:
            self._anim.stop()
            self._anim.setStartValue(self._alpha)
            self._anim.setEndValue(30)
            self._anim.start()

    def leaveEvent(self, _):
        if not self._active:
            self._anim.stop()
            self._anim.setStartValue(self._alpha)
            self._anim.setEndValue(0)
            self._anim.start()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        # Fill
        if self._alpha > 0:
            fc = QColor(self._accent); fc.setAlpha(self._alpha)
            p.fillRect(r, fc)

        # Active left bar + glow
        if self._active:
            p.setPen(Qt.NoPen)
            p.setBrush(self._accent)
            p.drawRect(0, 0, 3, r.height())
            rg = QRadialGradient(16, r.height() // 2, 45)
            gc = QColor(self._accent); gc.setAlpha(28)
            rg.setColorAt(0, gc); rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(rg)
            p.drawEllipse(-20, r.height() // 2 - 45, 90, 90)

        # Faint right-side vertical line on hover
        if not self._active and self._alpha > 0:
            hc = QColor(self._accent); hc.setAlpha(38)
            p.setPen(QPen(hc, 1))
            p.drawLine(r.width() - 1, 0, r.width() - 1, r.height())

        # Icon
        icon_col = self._accent if (self._active or self._alpha > 0) else QColor(MUTED)
        p.setPen(QPen(icon_col))
        p.setFont(QFont("Consolas", 13))
        p.drawText(QRectF(14, 0, 28, r.height()), Qt.AlignVCenter | Qt.AlignLeft, self._icon)

        # Label
        lc = QColor(WHITE if self._active else (TEXT if self._alpha > 0 else MUTED))
        p.setPen(QPen(lc))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(QRectF(48, 0, r.width() - 56, r.height()), Qt.AlignVCenter | Qt.AlignLeft, self._label)
        p.end()


# =============================================================================
# ARC GAUGE (spinning ring + value)
# =============================================================================
class ArcGauge(QWidget):
    def __init__(self, label, accent=CYAN, parent=None):
        super().__init__(parent)
        self._label  = label
        self._accent = QColor(accent)
        self._value  = 0.0
        self._spin   = 0
        self.setFixedSize(86, 86)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(38)

    def _tick(self): self._spin = (self._spin + 2) % 360; self.update()

    def set_value(self, v): self._value = max(0.0, min(100.0, float(v))); self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, R = self.width() // 2, self.height() // 2, 32

        # Track ring
        bg = QColor(self._accent); bg.setAlpha(25)
        p.setPen(QPen(bg, 5, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
        p.drawArc(cx - R, cy - R, R * 2, R * 2, 225 * 16, -270 * 16)

        # Value arc
        span = int((self._value / 100.0) * 270 * 16)
        p.setPen(QPen(self._accent, 5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx - R, cy - R, R * 2, R * 2, 225 * 16, -span)

        # Spinning tick
        rad = math.radians(self._spin - 90)
        tx  = cx + (R + 6) * math.cos(rad)
        ty  = cy + (R + 6) * math.sin(rad)
        tc  = QColor(self._accent); tc.setAlpha(100)
        p.setPen(QPen(tc, 2)); p.drawPoint(int(tx), int(ty))

        # Center value
        p.setPen(QPen(self._accent))
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(self.rect().adjusted(0, 6, 0, 0), Qt.AlignCenter, f"{int(self._value)}%")

        # Label
        p.setPen(QPen(QColor(TEXT)))
        p.setFont(QFont("Consolas", 7))
        p.drawText(self.rect().adjusted(0, 24, 0, 0), Qt.AlignCenter, self._label)
        p.end()


# =============================================================================
# NEON BUTTON
# =============================================================================
class NBtn(QPushButton):
    def __init__(self, text, accent=CYAN, parent=None):
        super().__init__(text, parent)
        c = QColor(accent)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba({c.red()},{c.green()},{c.blue()},15);
                color: rgba({c.red()},{c.green()},{c.blue()},190);
                border: 1px solid rgba({c.red()},{c.green()},{c.blue()},55);
                border-radius: 5px;
                padding: 8px 16px;
                font-family: Consolas;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1.5px;
            }}
            QPushButton:hover {{
                background: rgba({c.red()},{c.green()},{c.blue()},38);
                color: rgb({c.red()},{c.green()},{c.blue()});
                border: 1px solid rgba({c.red()},{c.green()},{c.blue()},180);
            }}
            QPushButton:pressed {{
                background: rgba({c.red()},{c.green()},{c.blue()},60);
            }}
        """)


# =============================================================================
# GLASS CARD (breathing border + corner accents)
# =============================================================================
class GlassCard(QWidget):
    def __init__(self, title="", accent=CYAN, parent=None):
        super().__init__(parent)
        self._title  = title.upper()
        self._accent = QColor(accent)
        self._frame  = random.randint(0, 100)

        t = QTimer(self); t.timeout.connect(self._tick); t.start(48)

        self._layout = QVBoxLayout(self)
        top_pad = 38 if title else 14
        self._layout.setContentsMargins(16, top_pad, 16, 14)
        self._layout.setSpacing(8)

    def _tick(self): self._frame = (self._frame + 1) % 120; self.update()

    def layout(self): return self._layout

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        # Glass fill
        path = QPainterPath()
        path.addRoundedRect(r, 7, 7)
        p.fillPath(path, QColor(9, 22, 50, 220))

        # Breathing border
        alpha = int(70 + 35 * math.sin(self._frame * 0.052))
        bc = QColor(self._accent); bc.setAlpha(alpha)
        p.setPen(QPen(bc, 1.2)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 7, 7)

        # Top glow line
        ta = QColor(self._accent); ta.setAlpha(220)
        tg = QLinearGradient(r.left() + 30, r.top(), r.right() - 30, r.top())
        tg.setColorAt(0, QColor(0, 0, 0, 0))
        tg.setColorAt(0.3, ta); tg.setColorAt(0.7, ta)
        tg.setColorAt(1, QColor(0, 0, 0, 0))
        from PyQt5.QtGui import QBrush as QB
        p.setPen(QPen(QB(tg), 1.5))
        p.drawLine(QPointF(r.left() + 30, r.top() + 0.75),
                   QPointF(r.right() - 30, r.top() + 0.75))

        # Corner accents
        ca = QColor(self._accent); ca.setAlpha(150)
        p.setPen(QPen(ca, 1.5))
        L = int(r.left()); T = int(r.top())
        Ri = int(r.right()); B = int(r.bottom()); S = 14
        p.drawLine(L, T + S, L, T + 1); p.drawLine(L + 1, T, L + S, T)
        p.drawLine(Ri - S, T, Ri - 1, T); p.drawLine(Ri, T + 1, Ri, T + S)
        p.drawLine(L, B - S, L, B - 1); p.drawLine(L + 1, B, L + S, B)
        p.drawLine(Ri - S, B, Ri - 1, B); p.drawLine(Ri, B - S, Ri, B - 1)

        # Title
        if self._title:
            p.setFont(QFont("Consolas", 8, QFont.Bold))
            p.setPen(QPen(self._accent))
            p.drawText(QRectF(r.left() + 14, r.top() + 10, 400, 16),
                       Qt.AlignLeft | Qt.AlignVCenter, self._title)
            div = QColor(self._accent); div.setAlpha(40)
            p.setPen(QPen(div, 1))
            p.drawLine(QPointF(r.left() + 14, r.top() + 30),
                       QPointF(r.right() - 14, r.top() + 30))
        p.end()


# =============================================================================
# PROGRESS BAR (right panel telemetry)
# =============================================================================
class ProgressBar(QWidget):
    def __init__(self, accent=CYAN, parent=None):
        super().__init__(parent)
        self._value  = 0.0
        self._accent = QColor(accent)
        self.setFixedHeight(10)

    def set_value(self, v):
        self._value = max(0.0, min(100.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Track
        bg = QColor(self._accent); bg.setAlpha(25)
        p.setPen(Qt.NoPen); p.setBrush(bg)
        p.drawRoundedRect(0, 0, w, h, 5, 5)

        # Fill
        fw = int(w * self._value / 100)
        if fw > 4:
            grad = QLinearGradient(0, 0, fw, 0)
            dim = QColor(self._accent); dim.setAlpha(130)
            grad.setColorAt(0, dim); grad.setColorAt(1, self._accent)
            p.setBrush(grad)
            p.drawRoundedRect(0, 0, fw, h, 5, 5)

            # End glow
            rg = QRadialGradient(fw, h // 2, 16)
            rg.setColorAt(0, self._accent); rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(rg)
            p.drawEllipse(fw - 12, -4, 24, h + 8)
        p.end()


# =============================================================================
# STATUS BAR
# =============================================================================
class StatusBar(QLabel):
    def __init__(self, parent=None):
        super().__init__(" >> SYSTEM READY", parent)
        self._set(GREEN)
        self.setWordWrap(True)
        self.setMinimumHeight(36)

    def _set(self, col, txt=None):
        if txt: self.setText(txt)
        self.setStyleSheet(f"""
            color: {col};
            background: rgba(0, 0, 0, 180);
            border: 1px solid {col}44;
            border-left: 3px solid {col};
            border-radius: 4px;
            padding: 7px 14px;
            font-family: Consolas;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
        """)

    def ok(self, m):   self._set(GREEN,  f" >> {m}")
    def err(self, m):  self._set(RED,    f" !! {m}")
    def info(self, m): self._set(CYAN,   f" -- {m}")
    def warn(self, m): self._set(AMBER,  f" ** {m}")
    def reset(self):   self._set(GREEN,  " >> SYSTEM READY")


# =============================================================================
# VOICE THREAD
# =============================================================================
class VoiceThread(QThread):
    heard   = pyqtSignal(str)
    command = pyqtSignal(str)
    status  = pyqtSignal(str)

    def __init__(self):
        super().__init__(); self._running = False

    def start_listening(self):
        self._running = True
        if not self.isRunning(): self.start()

    def stop_listening(self): self._running = False

    def run(self):
        try:
            from modules.input_module import (
                get_voice_command, is_wake_word, extract_command_from_wake
            )
            from modules.tts_module import speak
            import time

            self.status.emit("LISTENING")

            while self._running:
                try:
                    # ── Record one 7-second window ────────────────────────
                    t = get_voice_command()

                    if not t:
                        continue   # silence — keep listening

                    self.heard.emit(t)

                    # ── Check for wake word ───────────────────────────────
                    if not is_wake_word(t):
                        continue   # not a wake word — ignore

                    # ── Wake word detected ────────────────────────────────
                    self.status.emit("ACTIVATED")
                    play_sound("activate")

                    # Try to extract inline command ("hey mantra open chrome")
                    cmd = extract_command_from_wake(t)

                    if cmd:
                        self.heard.emit(f"[CMD] {cmd}")
                        self.command.emit(cmd)
                        self.status.emit("LISTENING")
                        continue

                    # No inline command — simple spoken prompt
                    speak("I am listening.")
                    self.status.emit("WAITING — speak your command")

                    t2 = get_voice_command()
                    if t2:
                        self.heard.emit(f"[CMD] {t2}")
                        self.command.emit(t2)
                    else:
                        speak("I didn't hear anything.")
                        
                    self.status.emit("LISTENING")

                except Exception as ex:
                    self.status.emit(f"ERROR: {ex}")
                    time.sleep(0.3)

        except Exception as ex:
            self.status.emit(f"FATAL: {ex}")

        except Exception as ex:
                    self.status.emit(f"ERROR: {ex}")
                    time.sleep(0.3)


        except Exception as ex:
            self.status.emit(f"FATAL: {ex}")



# =============================================================================
# HELPERS: input field + button row
# =============================================================================
_INP_QSS = (f"background: rgba(0,20,42,0.8); border: 1px solid {BORDER}; "
            f"border-radius: 5px; padding: 9px 12px; color: {WHITE}; "
            f"font-family: Consolas; font-size: 12px;")

def _mk_inp(ph):
    e = QLineEdit(); e.setPlaceholderText(ph); e.setStyleSheet(_INP_QSS)
    return e

def _mk_row(ph, btn_txt, accent=CYAN):
    w = QWidget(); w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
    e = _mk_inp(ph)
    b = NBtn(btn_txt, accent); b.setFixedWidth(120)
    h.addWidget(e, 1); h.addWidget(b)
    return w, e, b


# =============================================================================
# PAGE WRAPPER
# =============================================================================
class Page(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("background: transparent; border: none;")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget(); inner.setStyleSheet("background: transparent;")
        self.setWidget(inner)
        self.vbox = QVBoxLayout(inner)
        self.vbox.setContentsMargins(16, 14, 16, 14)
        self.vbox.setSpacing(12)
        self._last_card = None

    def card(self, title="", accent=CYAN):
        c = GlassCard(title, accent)
        self.vbox.addWidget(c)
        self._last_card = c
        return c.layout()


# =============================================================================
# MAIN WINDOW
# =============================================================================
class SideBar(QWidget):
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(0, 100, 200, 15))
        g.setColorAt(1, QColor(0, 212, 255, 8))
        p.fillRect(self.rect(), g)
        p.end()

class MantraGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MANTRA  //  AI DESKTOP AUTOMATION")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setGeometry(40, 30, 1400, 880)
        self.setMinimumSize(1100, 700)

        self.bot_active = True
        self.history    = []
        self._drag_pos  = None

        self._voice     = VoiceThread()
        self._voice.heard.connect(self._on_heard)
        self._voice.command.connect(self._on_voice_cmd)
        self._voice.status.connect(self._on_voice_status)

        self._build_ui()
        self._start_timers()

    # ---- Drag (frameless) ---------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.y() < 56:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, _): self._drag_pos = None

    # ---- Root ---------------------------------------------------------------
    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background: {BG};")
        self.setCentralWidget(root)

        # Animated circuit BG (behind everything)
        self._bg = CircuitBG(root)

        # Content layer (on top, transparent so BG shows through)
        self._body = QWidget(root)
        self._body.setStyleSheet("background: transparent;")

        vbox = QVBoxLayout(self._body)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self._build_titlebar())

        center = QWidget(); center.setStyleSheet("background: transparent;")
        cbox = QHBoxLayout(center)
        cbox.setContentsMargins(0, 0, 0, 0); cbox.setSpacing(0)
        cbox.addWidget(self._build_sidebar())
        cbox.addWidget(self._build_pages(), 1)
        cbox.addWidget(self._build_right())
        vbox.addWidget(center, 1)
        vbox.addWidget(self._build_terminal())

        # Stack root children
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._body)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_bg"):
            self._bg.setGeometry(self.centralWidget().rect())
            self._body.setGeometry(self.centralWidget().rect())
            self._bg._ready = False

    # ---- Title bar ----------------------------------------------------------
    def _build_titlebar(self):
        tb = TitleBarBg()
        tb.setFixedHeight(54)
        row = QHBoxLayout(tb)
        row.setContentsMargins(20, 0, 16, 0); row.setSpacing(14)

        row.addWidget(HexLogo())
        logo = QLabel(">> MANTRA")
        logo.setStyleSheet(f"color: {CYAN}; font-family: Consolas; font-size: 18px; "
                           f"font-weight: bold; letter-spacing: 8px; background: transparent;")
        sub = QLabel("AI DESKTOP AUTOMATION  //  OFFLINE")
        sub.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 9px; "
                          f"letter-spacing: 3px; background: transparent;")
        lc = QVBoxLayout(); lc.setSpacing(1); lc.addWidget(logo); lc.addWidget(sub)
        row.addLayout(lc)
        row.addStretch()

        self._g_cpu  = SlimGauge("CPU",  CYAN)
        self._g_ram  = SlimGauge("RAM",  AMBER)
        self._g_disk = SlimGauge("DSK", VIOLET)
        for g in [self._g_cpu, self._g_ram, self._g_disk]:
            row.addWidget(g)

        row.addSpacing(10)

        # Voice pill
        self._vpill = QLabel("  [MIC OFF]  ")
        self._vpill.setStyleSheet(f"color: {MUTED}; background: rgba(0,0,0,140); "
                                  f"border: 1px solid {MUTED}44; border-radius: 11px; "
                                  f"padding: 4px 12px; font-family: Consolas; font-size: 9px; "
                                  f"font-weight: bold; letter-spacing: 2px;")
        row.addWidget(self._vpill)
        row.addSpacing(10)

        # Window controls
        for color, fn, tip in [("#FF5F57", self.close, "X"),
                                ("#FEBC2E", self.showMinimized, "-"),
                                ("#28C840", self.showMaximized, "+")]:
            b = QPushButton(tip)
            b.setFixedSize(18, 18)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 9px; "
                            f"border: none; color: #000; font-size: 10px; font-weight: bold; }}"
                            f"QPushButton:hover {{ background: white; color: #000; }}")
            b.clicked.connect(fn)
            row.addWidget(b)
        return tb

    # ---- Sidebar ------------------------------------------------------------
    def _build_sidebar(self):
        side = SideBar()
        side.setFixedWidth(164)
        side.setStyleSheet(f"background: rgba(6,13,30,220); border-right: 1px solid rgba(0,212,255,46);")
        vbox = QVBoxLayout(side)
        vbox.setContentsMargins(0, 14, 0, 14)
        vbox.setSpacing(2)

        nav_items = [
            (">>", "Dashboard",  CYAN,   0),
            ("[A]","Apps",       BLUE,   1),
            ("[F]","Files",      GREEN,  2),
            ("[S]","System",     AMBER,  3),
            ("[T]","Text Input", VIOLET, 4),
            ("[V]","Voice",      GREEN,  5),
            ("[H]","History",    CYAN,   6),
        ]
        self._nav_btns = []
        for icon, label, accent, idx in nav_items:
            b = NavBtn(icon, label, accent)
            b.clicked.connect(lambda _=None, i=idx: self._goto(i))
            self._nav_btns.append(b)
            vbox.addWidget(b)

        self._nav_btns[0].setActive(True)
        vbox.addStretch()

        status_lbl = QLabel("[ ONLINE ]")
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setStyleSheet(f"color: {GREEN}; font-family: Consolas; font-size: 8px; "
                                 f"letter-spacing: 2px; background: transparent;")
        vbox.addWidget(status_lbl)
        return side

    def _goto(self, idx):
        for i, b in enumerate(self._nav_btns):
            b.setActive(i == idx)
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(idx)

    # ---- Stacked pages ------------------------------------------------------
    def _build_pages(self):
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        self._stack.addWidget(self._pg_dashboard())
        self._stack.addWidget(self._pg_apps())
        self._stack.addWidget(self._pg_files())
        self._stack.addWidget(self._pg_system())
        self._stack.addWidget(self._pg_text())
        self._stack.addWidget(self._pg_voice())
        self._stack.addWidget(self._pg_history())
        return self._stack

    # ---- Right panel --------------------------------------------------------
    def _build_right(self):
        rp = QWidget()
        rp.setFixedWidth(250)
        rp.setStyleSheet(f"background: rgba(6,13,30,220); border-left: 1px solid rgba(0,212,255,46);")
        vbox = QVBoxLayout(rp)
        vbox.setContentsMargins(12, 14, 12, 14)
        vbox.setSpacing(8)

        # Section header
        t = QLabel("LIVE TELEMETRY")
        t.setStyleSheet(f"color: {CYAN}; font-family: Consolas; font-size: 8px; "
                        f"font-weight: bold; letter-spacing: 4px;")
        vbox.addWidget(t)

        # Metric bars
        self._bars = {}
        for label, accent in [("CPU LOAD", CYAN), ("MEMORY", AMBER),
                                ("DISK I/O", VIOLET), ("NETWORK", GREEN)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {accent}; font-family: Consolas; font-size: 8px; letter-spacing: 2px;")
            vbox.addWidget(lbl)
            bar = ProgressBar(accent)
            self._bars[label] = bar
            vbox.addWidget(bar)
            vbox.addSpacing(2)

        # Divider
        d = QFrame(); d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(f"background: {CYAN}22; border: none; max-height: 1px;")
        vbox.addWidget(d)

        # Command log
        cl = QLabel("COMMAND LOG")
        cl.setStyleSheet(f"color: {CYAN}; font-family: Consolas; font-size: 8px; "
                         f"font-weight: bold; letter-spacing: 4px;")
        vbox.addWidget(cl)

        self._rlog = QListWidget()
        self._rlog.setItemDelegate(LogDelegate(self._rlog))
        self._rlog.setStyleSheet(f"""
            QListWidget {{
                background: rgba(0,10,22,160);
                border: 1px solid {BORDER};
                border-radius: 4px;
                color: {TEXT};
                font-family: Consolas;
                font-size: 9px;
            }}
            QListWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {DIM}; }}
            QListWidget::item:selected {{ background: {CYAN}22; color: {CYAN}; }}
            QScrollBar:vertical {{ background: {PANEL}; width: 5px; border-radius: 2px; }}
            QScrollBar::handle:vertical {{ background: {MUTED}; border-radius: 2px; }}
        """)
        vbox.addWidget(self._rlog, 1)
        return rp

    # ---- Terminal bar -------------------------------------------------------
    def _build_terminal(self):
        t = QWidget()
        t.setFixedHeight(48)
        t.setStyleSheet(f"background: rgba(4,10,24,245); border-top: 1px solid rgba(0,212,255,89);")
        row = QHBoxLayout(t)
        row.setContentsMargins(20, 6, 20, 6)
        row.setSpacing(10)

        prompt = QLabel(">_")
        prompt.setStyleSheet(f"color: {GREEN}; font-family: Consolas; font-size: 15px; "
                             f"font-weight: bold; background: transparent;")

        self._term = QLineEdit()
        self._term.setPlaceholderText(
            "Command terminal  --  try: 'open chrome'  'lock screen'  'volume up'  'system info'")
        self._term.setStyleSheet(f"background: transparent; border: none; color: {WHITE}; "
                                 f"font-family: Consolas; font-size: 12px; "
                                 f"selection-background-color: {CYAN}55;")
        self._term.returnPressed.connect(self._run_terminal)

        self._tstat = QLabel("OK")
        self._tstat.setFixedWidth(70)
        self._tstat.setAlignment(Qt.AlignCenter)
        self._tstat.setStyleSheet(f"color: {GREEN}; font-family: Consolas; font-size: 9px; "
                                  f"letter-spacing: 2px; background: transparent;")

        row.addWidget(prompt); row.addWidget(self._term, 1); row.addWidget(self._tstat)
        return t

    def _run_terminal(self):
        cmd = self._term.text().strip()
        if not cmd: return
        self._term.clear()
        self._tstat.setText("EXEC")
        self._tstat.setStyleSheet(f"color: {AMBER}; font-family: Consolas; font-size: 9px; "
                                  f"letter-spacing: 2px; background: transparent;")
        try:
            from modules.nlp_module import process_command
            from modules.intent_module import detect_intent
            from modules.execution_module import execute_task
            parsed = process_command(cmd)
            intent = detect_intent(parsed)
            result = execute_task(intent, parsed.get("keywords", []), cmd)
            self._tstat.setText("OK")
            self._tstat.setStyleSheet(f"color: {GREEN}; font-family: Consolas; font-size: 9px; "
                                      f"letter-spacing: 2px; background: transparent;")
            self._log(cmd, str(result))
            if hasattr(self, "_sb"): self._sb.ok(str(result)[:180])
        except Exception as ex:
            self._tstat.setText("ERR")
            self._tstat.setStyleSheet(f"color: {RED}; font-family: Consolas; font-size: 9px; "
                                      f"letter-spacing: 2px; background: transparent;")
            if hasattr(self, "_sb"): self._sb.err(str(ex)[:120])
        QTimer.singleShot(3500, lambda: (
            self._tstat.setText("OK"),
            self._tstat.setStyleSheet(f"color: {GREEN}; font-family: Consolas; "
                                      f"font-size: 9px; letter-spacing: 2px; background: transparent;")))

    # ---- Shared execute + log -----------------------------------------------
    def _run(self, func, *args, sb=None):
        if not sb: sb = getattr(self, "_sb", None)
        try:
            res = func(*args)
            
            # Check if the result implies a failure or error
            is_err = any(err_word in str(res) for err_word in ["Failed", "Could not find", "❌", "⚠️", "cannot be opened"])
            
            if sb:
                if is_err: sb.err(res)
                else:      sb.ok(res)
                
            from modules.tts_module import speak
            if is_err: 
                speak("I am not able to do that.")
            else:      
                speak("Task done.")
                
        except Exception as ex:
            if sb: sb.err(str(ex)[:120])
            from modules.tts_module import speak
            speak("I am not able to do that.")

    def _log(self, cmd, result):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.history.insert(0, {"t": ts, "cmd": cmd, "r": result})
        if len(self.history) > 300: self.history.pop()
        
        from PyQt5.QtWidgets import QListWidgetItem
        from PyQt5.QtCore import Qt
        item = QListWidgetItem()
        item.setData(Qt.DisplayRole, result[:100])
        item.setData(Qt.UserRole, "success" if "error" not in result.lower() else "error")
        item.setData(Qt.UserRole + 1, cmd[:20])
        item.setData(Qt.UserRole + 3, ts)
        
        if hasattr(self, "_rlog"):
            self._rlog.insertItem(0, item)
            if self._rlog.count() > 60: self._rlog.takeItem(60)
        if hasattr(self, "_hlist"):
            self._hlist.insertItem(0, QListWidgetItem(
                f"[{ts}]  {cmd}  ->  {result[:50]}"))


    # =========================================================================
    # PAGES
    # =========================================================================
    def _pg_dashboard(self):
        pg = Page()
        self._sb = StatusBar()

        # Quick launch
        lay = pg.card("QUICK LAUNCH", CYAN)
        grid = QGridLayout(); grid.setSpacing(8)
        apps = [("CHROME",  "chrome",     CYAN),  ("NOTEPAD", "notepad",    BLUE),
                ("SPOTIFY", "spotify",    GREEN), ("DISCORD", "discord",    VIOLET),
                ("CALC",    "calculator", AMBER), ("VS CODE", "code",       CYAN),
                ("EXPLORE", "explorer",   AMBER), ("TEAMS",   "teams",      VIOLET)]
        for i, (lbl, app, col) in enumerate(apps):
            b = NBtn(lbl, col); b.setMinimumHeight(48)
            b.clicked.connect(lambda _=None, a=app: self._run(open_or_switch_app, a, sb=self._sb))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)

        # System ops
        lay2 = pg.card("SYSTEM OPERATIONS", AMBER)
        sg = QHBoxLayout(); sg.setSpacing(8)
        for lbl, fn, col in [("LIST APPS", list_running_apps, CYAN),
                               ("LOCK PC",   lock_system,       AMBER),
                               ("SLEEP",     sleep_system,      BLUE),
                               ("SYS INFO",  get_system_info,   GREEN)]:
            b = NBtn(lbl, col)
            b.clicked.connect(lambda _=None, f=fn: self._run(f, sb=self._sb))
            sg.addWidget(b)
        lay2.addLayout(sg)

        pg.vbox.addWidget(self._sb)
        return pg

    def _pg_apps(self):
        pg = Page()
        self._sb_apps = StatusBar()

        lay = pg.card("LAUNCH APPLICATION", CYAN)
        rw, self._app_inp, ab = _mk_row("App name  (chrome, spotify, vlc, notepad...)", "LAUNCH", CYAN)
        ab.clicked.connect(lambda: self._run(open_or_switch_app, self._app_inp.text(), sb=self._sb_apps))
        lay.addWidget(rw)

        lay2 = pg.card("TERMINATE PROCESS", RED)
        rw2, self._kill_inp, kb = _mk_row("Process name to kill  (notepad, chrome...)", "KILL", RED)
        kb.clicked.connect(lambda: self._run(close_app, self._kill_inp.text(), sb=self._sb_apps))
        lay2.addWidget(rw2)

        lay3 = pg.card("PROCESS SCANNER", GREEN)
        lb = NBtn("  SCAN ALL RUNNING PROCESSES  ", GREEN); lb.setMinimumHeight(52)
        lb.clicked.connect(lambda: self._run(list_running_apps, sb=self._sb_apps))
        lay3.addWidget(lb)

        pg.vbox.addWidget(self._sb_apps)
        pg.vbox.addStretch()
        return pg

    def _pg_files(self):
        pg = Page()
        self._sb_files = StatusBar()
        for title, ph, fn, col in [
            ("CREATE FILE",   "Full path  (C:\\Users\\file.txt)",  create_file,   CYAN),
            ("CREATE FOLDER", "Folder path",                       create_folder, GREEN),
            ("DELETE FILE",   "File path to delete",               delete_file,   RED),
            ("DELETE FOLDER", "Folder path to delete",             delete_folder, RED),
            ("SEARCH FILES",  "Search keyword",                    search_files,  AMBER),
        ]:
            lay = pg.card(title, col)
            rw, e, b = _mk_row(ph, "EXEC", col)
            b.clicked.connect(lambda _=None, f=fn, ei=e: self._run(f, ei.text(), sb=self._sb_files))
            lay.addWidget(rw)

        lay_r = pg.card("RENAME FILE", VIOLET)
        rr = QHBoxLayout(); rr.setSpacing(8)
        self._ren_old = _mk_inp("Old path"); self._ren_new = _mk_inp("New path")
        rb = NBtn("RENAME", VIOLET); rb.setFixedWidth(120)
        rb.clicked.connect(lambda: self._run(rename_file, self._ren_old.text(),
                                             self._ren_new.text(), sb=self._sb_files))
        rr.addWidget(self._ren_old); rr.addWidget(self._ren_new); rr.addWidget(rb)
        lay_r.addLayout(rr)

        pg.vbox.addWidget(self._sb_files)
        return pg

    def _pg_system(self):
        pg = Page()
        self._sb_sys = StatusBar()

        lay_p = pg.card("POWER CONTROLS", RED)
        pg2 = QGridLayout(); pg2.setSpacing(8)
        for i, (lbl, fn, col) in enumerate([
            ("SHUTDOWN", shutdown_system, RED),
            ("RESTART",  restart_system,  AMBER),
            ("LOCK",     lock_system,     CYAN),
            ("LOGOUT",   logout_user,     VIOLET),
            ("SLEEP",    sleep_system,    BLUE),
        ]):
            b = NBtn(lbl, col); b.setMinimumHeight(52)
            if lbl in ("SHUTDOWN", "RESTART"):
                b.clicked.connect(lambda _=None, f=fn, l=lbl: self._confirm(l, f))
            else:
                b.clicked.connect(lambda _=None, f=fn: self._run(f, sb=self._sb_sys))
            pg2.addWidget(b, 0, i)
        lay_p.addLayout(pg2)

        lay_a = pg.card("AUDIO CONTROLS", GREEN)
        ag = QHBoxLayout(); ag.setSpacing(8)
        for lbl, fn, col in [("VOL UP", increase_volume, GREEN),
                               ("VOL DOWN", decrease_volume, AMBER),
                               ("MUTE", mute_volume, RED)]:
            b = NBtn(lbl, col); b.setMinimumHeight(52)
            b.clicked.connect(lambda _=None, f=fn: self._run(f, sb=self._sb_sys))
            ag.addWidget(b)
        lay_a.addLayout(ag)

        lay_d = pg.card("DIAGNOSTICS", CYAN)
        db = NBtn("  FETCH FULL SYSTEM INFORMATION  ", CYAN); db.setMinimumHeight(52)
        db.clicked.connect(lambda: self._run(get_system_info, sb=self._sb_sys))
        lay_d.addWidget(db)

        pg.vbox.addWidget(self._sb_sys)
        pg.vbox.addStretch()
        return pg

    def _confirm(self, label, fn):
        box = QMessageBox(self)
        box.setWindowTitle(f"CONFIRM: {label}")
        box.setText(f"Execute [{label}]?\n\nSystem will proceed immediately.")
        box.setStyleSheet(f"background: {PANEL}; color: {WHITE}; font-family: Consolas;")
        box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if box.exec_() == QMessageBox.Ok:
            self._run(fn, sb=self._sb_sys)

    def _pg_text(self):
        pg = Page()
        self._sb_text = StatusBar()

        lay = pg.card("TYPE INTO ACTIVE WINDOW", CYAN)
        rw, self._type_e, tb = _mk_row("Text to inject into focused application...", "TYPE", CYAN)
        tb.clicked.connect(lambda: self._run(type_text, self._type_e.text(), sb=self._sb_text))
        lay.addWidget(rw)

        lay2 = pg.card("KEYBOARD SHORTCUTS", VIOLET)
        kg = QGridLayout(); kg.setSpacing(8)
        for i, (lbl, fn, col) in enumerate([
            ("COPY",       copy_text,   CYAN),
            ("PASTE",      paste_text,  CYAN),
            ("SELECT ALL", select_all,  GREEN),
            ("UNDO",       undo_action, AMBER),
            ("REDO",       redo_action, AMBER),
        ]):
            b = NBtn(lbl, col); b.setMinimumHeight(52)
            b.clicked.connect(lambda _=None, f=fn: self._run(f, sb=self._sb_text))
            kg.addWidget(b, 0, i)
        lay2.addLayout(kg)

        pg.vbox.addWidget(self._sb_text)
        pg.vbox.addStretch()
        return pg

    def _pg_voice(self):
        pg = Page()

        lay = pg.card("VOICE ENGINE  //  WHISPER (OFFLINE)", GREEN)
        self._vgauge = ArcGauge("VOICE", GREEN)
        self._vgauge.setFixedSize(120, 120)
        lay.addWidget(self._vgauge, 0, Qt.AlignCenter)

        self._vstate = QLabel("OFFLINE")
        self._vstate.setAlignment(Qt.AlignCenter)
        self._vstate.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 12px; "
                                   f"letter-spacing: 4px; background: transparent;")
        lay.addWidget(self._vstate)

        self._vheard = QLabel("")
        self._vheard.setAlignment(Qt.AlignCenter)
        self._vheard.setWordWrap(True)
        self._vheard.setStyleSheet(f"color: {GREEN}; font-family: Consolas; font-size: 12px; background: transparent;")
        lay.addWidget(self._vheard)

        br = QHBoxLayout(); br.setAlignment(Qt.AlignCenter); br.setSpacing(12)
        self._vstart = NBtn("  ACTIVATE VOICE  ", GREEN); self._vstart.setMinimumWidth(180)
        self._vstop  = NBtn("  DEACTIVATE  ",    RED);   self._vstop.setMinimumWidth(150)
        self._vstop.setEnabled(False)
        self._vstart.clicked.connect(self._voice_on)
        self._vstop.clicked.connect(self._voice_off)
        br.addWidget(self._vstart); br.addWidget(self._vstop)
        lay.addLayout(br)

        info = QLabel("WAKE WORDS:  hey mantra  //  hi mantra  //  wakeup mantra  //  mantra")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 9px; background: transparent;")
        lay.addWidget(info)

        lay2 = pg.card("TRANSCRIPT LOG", CYAN)
        self._vlog = QListWidget()
        self._vlog.setMaximumHeight(160)
        self._vlog.setStyleSheet(f"""
            QListWidget {{ background: rgba(0,10,22,160); border: 1px solid {BORDER};
                border-radius: 4px; color: {TEXT}; font-family: Consolas; font-size: 10px; }}
            QListWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {DIM}; }}
        """)
        lay2.addWidget(self._vlog)

        pg.vbox.addStretch()
        return pg

    def _voice_on(self):
        self._voice.start_listening()
        self._vstart.setEnabled(False); self._vstop.setEnabled(True)
        self._vpill.setText("  [MIC ON]  ")
        self._vpill.setStyleSheet(f"color: {GREEN}; background: rgba(0,40,20,140); "
                                  f"border: 1px solid {GREEN}44; border-radius: 11px; "
                                  f"padding: 4px 12px; font-family: Consolas; font-size: 9px; "
                                  f"font-weight: bold; letter-spacing: 2px;")

    def _voice_off(self):
        self._voice.stop_listening()
        self._vstart.setEnabled(True); self._vstop.setEnabled(False)
        self._vpill.setText("  [MIC OFF]  ")
        self._vpill.setStyleSheet(f"color: {MUTED}; background: rgba(0,0,0,140); "
                                  f"border: 1px solid {MUTED}44; border-radius: 11px; "
                                  f"padding: 4px 12px; font-family: Consolas; font-size: 9px; "
                                  f"font-weight: bold; letter-spacing: 2px;")
        self._vstate.setText("OFFLINE")
        self._vstate.setStyleSheet(f"color: {MUTED}; font-family: Consolas; font-size: 12px; "
                                   f"letter-spacing: 4px; background: transparent;")

    def _on_heard(self, t):
        self._vheard.setText(f'"{t}"')
        if hasattr(self, "_vlog"): self._vlog.insertItem(0, QListWidgetItem(f"HEARD  >>  {t}"))

    def _on_voice_cmd(self, cmd):
        """Handle a confirmed voice command — run full NLP pipeline and show result."""
        ts = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "_vlog"):
            self._vlog.insertItem(0, QListWidgetItem(f"CMD    >>  {cmd}"))
        try:
            from modules.nlp_module    import process_command
            from modules.intent_module import detect_intent
            from modules.execution_module import execute_task
            from modules.tts_module    import speak

            parsed = process_command(cmd)
            intent = detect_intent(parsed)
            result = execute_task(intent, parsed.get("keywords", []), cmd)

            # Show result in voice log
            if hasattr(self, "_vlog"):
                self._vlog.insertItem(0, QListWidgetItem(
                    f"RESULT >>  [{intent}]  {str(result)[:80]}"))

            # Show in status bar
            if hasattr(self, "_sb"):
                if str(result).startswith(("Error", "Failed", "\u274c")):
                    self._sb.err(str(result)[:180])
                    speak("I am not able to do that.")
                else:
                    self._sb.ok(str(result)[:180])
                    speak("Done.")

            self._log(cmd, str(result))

        except Exception as ex:
            err_msg = f"Voice exec error: {ex}"
            if hasattr(self, "_vlog"):
                self._vlog.insertItem(0, QListWidgetItem(f"ERROR  >>  {err_msg}"))
            if hasattr(self, "_sb"):
                self._sb.err(err_msg[:180])
            try:
                from modules.tts_module import speak
                speak("I am not able to do that.")
            except Exception:
                pass


    def _on_voice_status(self, s):
        if hasattr(self, "_vstate"):
            self._vstate.setText(s)
            col = {"LISTENING": CYAN, "ACTIVATED": GREEN,
                   "WAITING": AMBER, "OFFLINE": MUTED}.get(s.split(":")[0], RED)
            self._vstate.setStyleSheet(f"color: {col}; font-family: Consolas; font-size: 12px; "
                                       f"letter-spacing: 4px; background: transparent; font-weight: bold;")

    def _pg_history(self):
        pg = Page()
        lay = pg.card("FULL COMMAND HISTORY", CYAN)
        self._hlist = QListWidget()
        self._hlist.setStyleSheet(f"""
            QListWidget {{ background: rgba(0,10,22,160); border: 1px solid {BORDER};
                border-radius: 4px; color: {TEXT}; font-family: Consolas; font-size: 10px; }}
            QListWidget::item {{ padding: 5px 10px; border-bottom: 1px solid {DIM}; }}
            QListWidget::item:selected {{ background: {CYAN}22; color: {CYAN}; border-left: 2px solid {CYAN}; }}
            QScrollBar:vertical {{ background: {PANEL}; width: 5px; border-radius: 2px; }}
            QScrollBar::handle:vertical {{ background: {MUTED}; border-radius: 2px; }}
        """)
        lay.addWidget(self._hlist)

        if DB_OK:
            try:
                for c in get_recent_commands(100):
                    ts = str(c.get("timestamp", ""))[-8:]
                    self._hlist.addItem(f"[{ts}]  {c.get('utterance','')}  ->  {c.get('outcome','')}")
            except Exception: pass

        clr = NBtn("CLEAR HISTORY", RED); clr.setFixedWidth(160)
        clr.clicked.connect(lambda: (self.history.clear(), self._hlist.clear()))
        pg.vbox.addWidget(clr, 0, Qt.AlignRight)
        return pg

    # ---- Timers -------------------------------------------------------------
    def _start_timers(self):
        self._stimer = QTimer()
        self._stimer.timeout.connect(self._refresh_stats)
        self._stimer.start(1500)
        self._refresh_stats()

    def _refresh_stats(self):
        try:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            net  = min(100.0, psutil.net_io_counters().bytes_sent / 1e6)
            self._g_cpu.set_value(cpu)
            self._g_ram.set_value(ram)
            self._g_disk.set_value(disk)
            self._bars["CPU LOAD"].set_value(cpu)
            self._bars["MEMORY"].set_value(ram)
            self._bars["DISK I/O"].set_value(disk)
            self._bars["NETWORK"].set_value(net)
        except Exception: pass


# =============================================================================
# ENTRY
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MantraGUI()
    win.show()
    sys.exit(app.exec_())