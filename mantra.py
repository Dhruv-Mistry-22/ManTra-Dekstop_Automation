# launcher.py - Mantra Launch Menu (Redesigned)
import sys
import os
import torch
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame, QWidget)
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty

# ── Palette (matches gui_app.py) ────────────────
DARK_BG      = "#0D0F14"
PANEL_BG     = "#141720"
CARD_BG      = "#1A1E2E"
BORDER_COLOR = "#1A3355"
ACCENT_CYAN  = "#00D4FF"
ACCENT_GREEN = "#00FF9C"
ACCENT_RED   = "#FF4D6A"
ACCENT_AMBER = "#FFB347"
TEXT_PRIMARY = "#E8EAF0"
TEXT_MUTED   = "#6B7280"
TEXT_DIM     = "#3D4459"

STYLESHEET = f"""
QDialog, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: 'Consolas', 'Courier New', monospace;
}}
QLabel {{
    background: transparent;
    border: none;
}}
QPushButton {{
    background: {CARD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 0.5px;
}}
QPushButton:hover {{
    background: #1E2335;
    border-color: {ACCENT_CYAN};
    color: {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background: #101525;
}}
"""


# ── Animated pulsing dot ────────────────────────
class PulseDot(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(10, 10)
        self._alpha = 255
        self._growing = False
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(30)

    def _tick(self):
        if self._growing:
            self._alpha = min(255, self._alpha + 6)
            if self._alpha >= 255: self._growing = False
        else:
            self._alpha = max(60, self._alpha - 6)
            if self._alpha <= 60: self._growing = True
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.color)
        c.setAlpha(self._alpha)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(c))
        p.drawEllipse(1, 1, 8, 8)
        p.end()


# ── Glowing card button ─────────────────────────
class ModeCard(QWidget):
    def __init__(self, icon, title, subtitle, badge_color, parent=None):
        super().__init__(parent)
        self.badge_color = QColor(badge_color)
        self.setMinimumHeight(110)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self._click_cb = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(16)

        # Icon box
        icon_box = QLabel(icon)
        icon_box.setFixedSize(54, 54)
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f"""
            background: {PANEL_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 14px;
            font-size: 26px;
        """)
        layout.addWidget(icon_box)

        # Text
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 15px; font-weight: bold; letter-spacing: 1px;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)
        layout.addLayout(text_col, 1)

        # Arrow
        arrow = QLabel("›")
        arrow.setStyleSheet(f"color: {TEXT_DIM}; font-size: 24px; font-weight: bold;")
        layout.addWidget(arrow)

    def set_callback(self, cb):
        self._click_cb = cb

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._click_cb:
            self._click_cb()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        # Background
        if self._hovered:
            bg = QColor("#1E2335")
        else:
            bg = QColor(CARD_BG)
        p.setBrush(QBrush(bg))

        # Border — glow when hovered
        if self._hovered:
            bc = QColor(self.badge_color)
            bc.setAlpha(200)
        else:
            bc = QColor(BORDER_COLOR)
        p.setPen(QPen(bc, 1.5))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 12, 12)

        # Left accent stripe
        stripe_color = QColor(self.badge_color)
        if not self._hovered:
            stripe_color.setAlpha(100)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(stripe_color))
        p.drawRoundedRect(0, 20, 4, r.height() - 40, 2, 2)
        p.end()


# ── Main launcher dialog ────────────────────────
class HexLogo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 3
        pts = []
        import math
        from PyQt5.QtCore import QPointF
        for i in range(6):
            pts.append(QPointF(cx + r * math.cos(math.pi/180*(60*i-30)), cy + r * math.sin(math.pi/180*(60*i-30))))
        from PyQt5.QtGui import QPolygonF
        poly = QPolygonF(pts)
        p.setBrush(QBrush(QColor(0, 212, 255, 20)))
        p.setPen(QPen(QColor(0, 212, 255, 64), 1.0))
        p.drawPolygon(poly)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 212, 255, 128), 1.5))
        p.drawPolygon(poly)
        p.setPen(QPen(QColor(0, 212, 255, 102), 1.2))
        for i in (0, 2, 4): p.drawLine(QPointF(cx, cy), pts[i])
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#00D4FF")))
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        p.end()

class LaunchMenu(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mantra — Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(480, 520)
        self._drag_pos = None
        self._build_ui()

    # ── Drag to move (frameless) ──
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Outer shadow / glow
        glow = QColor(ACCENT_CYAN)
        glow.setAlpha(18)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(self.rect(), 18, 18)
        # Main body
        p.setBrush(QBrush(QColor(DARK_BG)))
        p.setPen(QPen(QColor(BORDER_COLOR), 1.5))
        p.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 16, 16)
        p.end()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(0)

        # ── Custom title bar ──
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(8, 0, 8, 0)

        dot_row = QHBoxLayout()
        dot_row.setSpacing(6)
        # Three macOS-style dots
        for color in ["#FF5F57", "#FEBC2E", "#28C840"]:
            d = QWidget()
            d.setFixedSize(12, 12)
            d.setStyleSheet(f"background: {color}; border-radius: 6px;")
            dot_row.addWidget(d)
        dot_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                border: none; font-size: 14px; border-radius: 14px;
            }}
            QPushButton:hover {{ background: #2A1018; color: {ACCENT_RED}; }}
        """)
        close_btn.clicked.connect(self.close)

        title_bar.addLayout(dot_row)
        title_bar.addStretch()
        title_bar.addWidget(close_btn)
        root.addLayout(title_bar)
        root.addSpacing(10)

        # ── Logo / hero section ──
        hero = QVBoxLayout()
        hero.setAlignment(Qt.AlignCenter)
        hero.setSpacing(6)
        
        hl = QHBoxLayout(); hl.setAlignment(Qt.AlignCenter); hl.addWidget(HexLogo())
        hero.addLayout(hl)

        logo_lbl = QLabel("MANTRA")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet(f"""
            color: {ACCENT_CYAN};
            font-size: 30px;
            font-weight: bold;
            letter-spacing: 8px;
            font-family: 'Consolas', monospace;
        """)

        tagline = QLabel("AI Desktop Automation  ·  Offline")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; letter-spacing: 2px;")

        # Status row
        status_row = QHBoxLayout()
        status_row.setAlignment(Qt.AlignCenter)
        status_row.setSpacing(6)
        dot = PulseDot(ACCENT_GREEN)
        status_lbl = QLabel("System Ready")
        status_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 11px; letter-spacing: 1px;")
        status_row.addWidget(dot)
        status_row.addWidget(status_lbl)

        hero.addWidget(logo_lbl)
        hero.addWidget(tagline)
        hero.addSpacing(8)
        hero.addLayout(status_row)
        root.addLayout(hero)
        root.addSpacing(24)

        # ── Divider ──
        root.addWidget(self._divider())
        root.addSpacing(16)

        # ── Mode label ──
        choose_lbl = QLabel("SELECT MODE")
        choose_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; letter-spacing: 3px;")
        choose_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(choose_lbl)
        root.addSpacing(12)

        # ── Mode cards ──
        gui_card = ModeCard(
            "🖥",
            "GUI Control Center",
            "Visual dashboard  ·  All features  ·  Voice control",
            ACCENT_CYAN
        )
        gui_card.set_callback(self.start_gui)

        cli_card = ModeCard(
            "🎤",
            "Voice / Text CLI",
            "Terminal mode  ·  Wake word  ·  Advanced users",
            ACCENT_AMBER
        )
        cli_card.set_callback(self.start_cli)

        root.addWidget(gui_card)
        root.addSpacing(10)
        root.addWidget(cli_card)
        root.addSpacing(20)

        # ── Footer ──
        root.addWidget(self._divider())
        root.addSpacing(12)

        footer_row = QHBoxLayout()
        footer_row.setAlignment(Qt.AlignCenter)

        stats = [("55+", "Commands"), ("5", "Modules"), ("BUILD 2", "Version")]
        for val, lbl in stats:
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignCenter)
            col.setSpacing(1)
            v_lbl = QLabel(val)
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet(f"color: {ACCENT_CYAN}; font-size: 16px; font-weight: bold;")
            l_lbl = QLabel(lbl)
            l_lbl.setAlignment(Qt.AlignCenter)
            l_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; letter-spacing: 1px;")
            col.addWidget(v_lbl)
            col.addWidget(l_lbl)
            footer_row.addLayout(col)

            if lbl != "Version":
                sep = QLabel("|")
                sep.setStyleSheet(f"color: {TEXT_DIM}; font-size: 18px; padding: 0 14px;")
                footer_row.addWidget(sep)

        root.addLayout(footer_row)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {BORDER_COLOR}; border: none; max-height: 1px;")
        return line

    # ── Launch actions ────────────────────────
    def start_gui(self):
        try:
            from gui.gui_app import MantraGUI
            self.close()
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            app.setStyle("Fusion")
            window = MantraGUI()
            window.show()
            app.exec_()
        except Exception as e:
            print(f"Error starting GUI: {e}")

    def start_cli(self):
        self.close()
        print("Switching to CLI mode…")
        import subprocess
        subprocess.Popen([sys.executable, "main.py"], cwd=os.getcwd())
        sys.exit()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    launcher = LaunchMenu()
    # Centre on screen
    screen = app.primaryScreen().geometry()
    launcher.move(
        (screen.width()  - launcher.width())  // 2,
        (screen.height() - launcher.height()) // 2
    )
    launcher.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()