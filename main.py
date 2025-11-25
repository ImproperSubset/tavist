from contextlib import redirect_stdout
import sys
import html
import re
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QCheckBox,
    QSizeGrip,
)
from tavist.model import (
    AttackAction,
    AttackRoll,
    Bonus,
    BonusType,
    DamageDice,
    DamageRoll,
    DamageType,
    Tavist,
    WeaponDamageDice,
    expected_full_attack,
    recommend_setup,
)
from tavist.tracking import ACTargetTracker, format_bound, accumulate_known_hits, damage_for_hit
from tavist.controller import (
    apply_tracking_selection,
    format_attack_line,
    summarize_damage_ranges,
)


DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QWidget {
    font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
    font-size: 18px;
    color: #cdd6f4;
    background-color: #1e1e2e;
}

QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
    color: #89b4fa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    left: 10px;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3b3e52, stop:1 #313244);
    border: 1px solid #45475a;
    border-bottom: 2px solid #1e1e2e;  /* 3D shadow effect */
    border-radius: 6px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #4a4d62, stop:1 #3b3e52);
    border-color: #585b70;
    border-bottom: 2px solid #252535;
    /* Lift effect on hover */
    padding: 7px 16px 9px 16px;
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #1e1e2e, stop:1 #252535);
    border: 1px solid #89b4fa;
    border-bottom: 1px solid #89b4fa;  /* Flattened when pressed */
    /* Pressed down effect */
    padding: 9px 16px 7px 16px;
}

QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #a6b9ff, stop:1 #89b4fa);
    color: #1e1e2e;
    border: 1px solid #89b4fa;
    border-bottom: 2px solid #6c7fa8;
    font-weight: 700;
}

QLineEdit {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus {
    border: 1px solid #89b4fa;
}

QTextEdit {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px;
    color: #cdd6f4;
    font-family: "Consolas", "Monaco", monospace;
}

QLabel {
    color: #a6adc8;
}

QCheckBox {
    spacing: 5px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475a;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMxZTFlMmUiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSIyMCA2IDkgMTcgNCAxMiI+PC9wb2x5bGluZT48L3N2Zz4=);
}
"""



class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.host_window = parent
        # Make title bar background transparent so container border shows through
        self.setStyleSheet("background-color: transparent;")
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(10, 5, 10, 5)
        self.title = QLabel("Tavist")
        self.title.setStyleSheet("font-weight: bold; font-size: 16px; color: #cdd6f4; border: none; background-color: transparent;")

        self.btn_minimize = QPushButton("—")
        self.btn_minimize.clicked.connect(parent.showMinimized)
        self.btn_minimize.setFixedSize(30, 30)
        self.btn_minimize.setStyleSheet("background-color: #313244; color: #cdd6f4; border: none; border-radius: 4px;")

        self.btn_close = QPushButton("✕")
        self.btn_close.clicked.connect(parent.close)
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet("background-color: #f38ba8; color: #1e1e2e; border: none; border-radius: 4px;")

        self.layout.addWidget(self.title)
        self.layout.addStretch()
        self.layout.addWidget(self.btn_minimize)
        self.layout.addWidget(self.btn_close)
        self.setLayout(self.layout)

        self.oldPos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Try to let the OS handle the move (smoother, no clipping)
            if self.host_window.windowHandle():
                if self.host_window.windowHandle().startSystemMove():
                    return
            # Fallback to manual dragging
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos is not None:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.host_window.move(self.host_window.pos() + delta)
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tavist")
        self.setWindowFlags(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground) # Removed to prevent artifacts
        
        # Set minimum window size
        self.setMinimumSize(600, 500)
        
        # Main container to hold the title bar and content
        container = QWidget()
        container.setObjectName("MainContainer")
        # Subtle border outline
        container.setStyleSheet("#MainContainer { border: 1px solid #45475a; background-color: #1e1e2e; border-radius: 8px; }")
        
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(2, 2, 2, 2)  # Margins to show border and rounded corners
        outer_layout.setSpacing(0)
        
        self.title_bar = TitleBar(self)
        outer_layout.addWidget(self.title_bar)

        # Content widget for the actual app controls
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 10, 20, 20)

        font = self.font()
        font.setPointSize(font.pointSize() + 2)
        self.setFont(font)

        self.target_ac = QLineEdit()
        self.target_ac.setText("")
        int_validator = QIntValidator(0, 99, self)
        self.target_ac.setValidator(int_validator)

        self.expertise = QLineEdit()
        self.expertise.setText("")
        self.expertise.setValidator(int_validator)

        self.auto_button = QPushButton("New Opponent")

        self.two_handed = QPushButton()
        self.two_handed.setCheckable(True)
        self.two_handed.setChecked(False)
        self.two_handed.setText("Two-Handed")

        targeting_layout = QHBoxLayout()
        targeting_layout.addWidget(QLabel("Est. AC:"))
        targeting_layout.addWidget(self.target_ac)
        targeting_layout.addWidget(QLabel("Combat Expertise:"))
        targeting_layout.addWidget(self.expertise)
        targeting_layout.addWidget(self.auto_button)
        targeting_group = QGroupBox("Targeting")
        targeting_group.setLayout(targeting_layout)

        extra_layout = QHBoxLayout()
        self.ext_hit = QLineEdit("0")
        self.ext_str = QLineEdit("0")
        self.ext_hit.setValidator(QIntValidator(-99, 99, self))
        self.ext_str.setValidator(QIntValidator(-99, 99, self))
        self.fatigued = QPushButton("Fatigued")
        self.fatigued.setCheckable(True)
        self.fatigued.setChecked(False)
        self.tracking = QPushButton("Tracking")
        self.tracking.setCheckable(True)
        self.tracking.setChecked(True)
        extra_layout.addWidget(QLabel("Ext Hit:"))
        extra_layout.addWidget(self.ext_hit)
        extra_layout.addWidget(QLabel("Ext Str:"))
        extra_layout.addWidget(self.ext_str)
        extra_layout.addWidget(self.fatigued)
        extra_layout.addWidget(self.tracking)
        extra_group = QGroupBox("External Effects")
        extra_group.setLayout(extra_layout)

        poweratt_layout = QHBoxLayout()
        self.reccommended_poweratt = QLabel()
        self.poweratt = QLineEdit("0")
        self.poweratt.setValidator(QIntValidator(0, 12, self))
        self.poweratt_lock = QCheckBox("Lock")
        poweratt_layout.addWidget(QLabel("Pwr Att:"))
        poweratt_layout.addWidget(self.poweratt)
        poweratt_layout.addWidget(QLabel("Suggested:"))
        poweratt_layout.addWidget(self.reccommended_poweratt)
        poweratt_layout.addWidget(self.poweratt_lock)
        poweratt_layout.addWidget(self.two_handed)

        poweratt_group = QGroupBox("Attack Mode")
        poweratt_group.setLayout(poweratt_layout)

        status_layout = QHBoxLayout()

        self.evil = QPushButton()
        self.evil.setCheckable(True)
        self.evil.setChecked(False)
        self.evil.setText("Evil")

        self.surge = QPushButton()
        self.surge.setCheckable(True)
        self.surge.setChecked(False)
        self.surge.setText("Power Surge")

        status_layout.addWidget(self.evil)
        status_layout.addWidget(self.surge)
        status_layout.addWidget(self.tracking)

        status_group = QGroupBox("Status")
        status_group.setLayout(status_layout)

        # Attack buttons group
        attacks_layout = QVBoxLayout()
        
        # Darker green for both attack buttons
        attack_button_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                            stop:0 #7fb574, stop:1 #6a9d5f);
                color: #1e1e2e;
                border: 1px solid #5a8d4f;
                border-bottom: 2px solid #4a7d3f;
                font-weight: 600;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #8fc584, stop:1 #7ab56f);
                border-color: #6a9d5f;
                border-bottom: 2px solid #5a8d4f;
                padding: 7px 16px 9px 16px;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 #3a5d2f, stop:1 #2a4d1f);
                border: 1px solid #4a7d3f;
                border-bottom: 1px solid #3a6d2f;
                padding: 9px 16px 7px 16px;
            }
        """
        
        self.attack_button = QPushButton("Attack")
        self.attack_button.setStyleSheet(attack_button_style)
        self.attack_button.setCursor(Qt.PointingHandCursor)
        attacks_layout.addWidget(self.attack_button)
        
        self.full_attack = QPushButton("Full Attack")
        self.full_attack.setStyleSheet(attack_button_style + "QPushButton { font-size: 16px; padding: 10px 16px; }")
        self.full_attack.setCursor(Qt.PointingHandCursor)
        attacks_layout.addWidget(self.full_attack)
        
        attacks_group = QGroupBox("Attacks")
        attacks_group.setLayout(attacks_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(targeting_group)
        main_layout.addWidget(extra_group)
        main_layout.addWidget(poweratt_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(attacks_group)

        dpr_row = QHBoxLayout()
        self.dpr_label = QLabel("Expected DPR: —")
        self.ac_bound = QLabel("AC bound: ?>")
        self.damage_done = QLabel("Damage done: 0")
        dpr_row.addWidget(self.dpr_label)
        dpr_row.addWidget(self.ac_bound)
        dpr_row.addWidget(self.damage_done)
        dpr_row.addStretch()
        
        main_layout.addLayout(dpr_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(160)
        log_font = self.log_output.font()
        log_font.setPointSize(log_font.pointSize() + 2)
        self.log_output.setFont(log_font)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        self.log_output.setMinimumWidth(800)
        main_layout.addWidget(self.log_output)

        # Add all the main controls to the content layout
        content_layout.addLayout(main_layout)
        
        # Add content widget to outer layout
        outer_layout.addWidget(content_widget)
        
        container.setLayout(outer_layout)
        self.setCentralWidget(container)
        
        # Add size grip for resizing (positioned in bottom-right corner)
        from PySide6.QtGui import QPainter, QPen
        
        class CustomSizeGrip(QSizeGrip):
            def paintEvent(self, event):
                super().paintEvent(event)
                painter = QPainter(self)
                pen = QPen(Qt.GlobalColor.white, 2)
                painter.setPen(pen)
                # Draw diagonal grip lines
                for i in range(3):
                    offset = i * 5
                    painter.drawLine(self.width() - 4 - offset, self.height() - 4,
                                   self.width() - 4, self.height() - 4 - offset)
                painter.end()
        
        self.size_grip = CustomSizeGrip(container)
        self.size_grip.setFixedSize(14, 14)
        # Style with visible background
        self.size_grip.setStyleSheet("""
            QSizeGrip {
                background-color: #313244;
                border: 1px solid #6c7086;
                border-radius: 3px;
            }
        """)
        self.size_grip.setToolTip("Drag to resize")
        self.resize(900, 750)
        # Force minimum size constraint
        self.setMinimumSize(600, 500)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        # Manually enforce minimum size (needed for frameless windows with QSizeGrip)
        min_width = 600
        min_height = 500
        if self.width() < min_width or self.height() < min_height:
            new_width = max(self.width(), min_width)
            new_height = max(self.height(), min_height)
            self.resize(new_width, new_height)
        
        # Position size grip in bottom-right corner with padding
        rect = self.rect()
        self.size_grip.move(rect.right() - self.size_grip.width() - 6, 
                           rect.bottom() - self.size_grip.height() - 6)


class DualWriter:
    def __init__(self):
        self.parts: list[str] = []

    def write(self, text: str):
        sys.__stdout__.write(text)
        self.parts.append(text)

    def flush(self):
        sys.__stdout__.flush()

    def text(self) -> str:
        return "".join(self.parts)


def append_log(window: MainWindow, text: str):
    def _escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;")

    for raw_line in text.split("\n"):
        escaped = _escape(raw_line)
        bold_match = re.search(r"\*\*(.+?)\*\*", escaped)
        if bold_match:
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", escaped)
            # Gold for hits/important info
            window.log_output.append(f'<span style="font-weight:bold; color: #f9e2af;">{content}</span>')
        else:
            # Subtle text for normal logs
            window.log_output.append(f'<span style="color: #bac2de;">{escaped}</span>')
    cursor = window.log_output.textCursor()
    cursor.movePosition(QTextCursor.End)
    window.log_output.setTextCursor(cursor)
    window.log_output.ensureCursorVisible()


def make_dice_toggle(roll: DamageRoll, cond: DamageDice):
    def damage_toggle(checked: bool):
        match checked:
            case True:
                if cond not in roll.dice:
                    roll.dice.append(cond)
            case False:
                if cond in roll.dice:
                    roll.dice.remove(cond)

    return damage_toggle


def make_bonus_toggle(roll: DamageRoll, cond: Bonus):
    def damage_toggle(checked: bool):
        match checked:
            case True:
                if cond not in roll.bonuses:
                    roll.bonuses.append(cond)
            case False:
                if cond in roll.bonuses:
                    roll.bonuses.remove(cond)

    return damage_toggle


def make_damage_update_scaled(bonus: Bonus, scale: float):
    def damage_update(text: str):
        try:
            val = int(text)
            bonus.bonus = int(val * scale)
        except ValueError:
            bonus.bonus = 0

    return damage_update


def make_attack_update(bonus: Bonus):
    def attack_update(text: str):
        try:
            bonus.bonus = -int(text)
        except ValueError:
            bonus.bonus = 0

    return attack_update


def make_power_attack_update(tavist: "Tavist"):
    def update(text: str):
        try:
            val = int(text)
        except ValueError:
            val = 0
        tavist.set_power_attack(val)

    return update


def perform_attack_with_log(attack: AttackAction, window: MainWindow):
    def do_attack():
        writer = DualWriter()
        with redirect_stdout(writer):
            result = attack.do_attack()
        log_text = writer.text().rstrip()
        if log_text:
            append_log(window, log_text)
            append_log(window, "")
        return result

    return do_attack


def wrap_full_attack(
    window: MainWindow, tavist: "Tavist", attack_names: list[str], attacks: list[int]
):
    def do_full_attack():
        tracker = getattr(window, "_ac_tracker", None)
        if tracker:
            append_log(window, f"AC bound: {format_bound(tracker)}")
        append_log(window, "=== Full Attack ===")
        results: list[dict] = []

        for idx, bonus in enumerate(attacks):
            wrap_bonus_adjustment(
                tavist.katana_attack_action, attack_names[idx], tavist.bab, bonus
            )()
            results.append(perform_attack_with_log(tavist.katana_attack_action, window)())

        if not tavist.two_handed_mode:
            wrap_bonus_adjustment(tavist.wakasashi_attack_action, "off-hand", tavist.bab, 12)()
            results.append(perform_attack_with_log(tavist.wakasashi_attack_action, window)())

        ranges = summarize_damage_ranges(results)
        if ranges:
            append_log(window, "--- Damage by AC ---")
            for lower, upper, damage, breakdown in ranges:
                def bd_text():
                    if not breakdown:
                        return ""
                    parts = [f"{k} {v}" for k, v in sorted(breakdown.items())]
                    return " (" + ", ".join(parts) + ")"

                if upper is None and lower is not None:
                    append_log(window, f"AC > {lower}: {damage} dmg{bd_text()}")
                elif lower is None:
                    append_log(window, f"AC ≤ {upper}: {damage} dmg{bd_text()}")
                else:
                    append_log(window, f"{lower} < AC ≤ {upper}: {damage} dmg{bd_text()}")
        if results:
            append_log(window, "--- Per attack ---")
            tracker = getattr(window, "_ac_tracker", None)
            if tracker:
                append_log(window, f"AC bound: {format_bound(tracker)}")
            for r in results:
                append_log(window, format_attack_line(r, tracker))
        append_log(window, "")

        return results

    return do_full_attack


def wrap_single_attack(window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]):
    def do_attack():
        tracker = getattr(window, "_ac_tracker", None)
        if tracker:
            append_log(window, f"AC bound: {format_bound(tracker)}")
        results: list[dict] = []
        wrap_bonus_adjustment(
            tavist.katana_attack_action, attack_names[0], tavist.bab, attacks[0]
        )()
        results.append(perform_attack_with_log(tavist.katana_attack_action, window)())

        if results:
            tracker = getattr(window, "_ac_tracker", None)
            append_log(window, format_attack_line(results[0], tracker))
            append_log(window, "")
        return results

    return do_attack


def wrap_bonus_adjustment(attack: AttackAction, name: str, bonus: Bonus, value: int):
    def bonus_adjustment():
        attack.label = name
        bonus.bonus = value

    return bonus_adjustment


def wrap_auto_recommend(
    window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]
):
    def do_auto():
        try:
            ac = int(window.target_ac.text() or "0")
        except ValueError:
            ac = 99
        tracker = getattr(window, "_ac_tracker", None)
        if tracker:
            tracker.reset()
            window.damage_done.setText("Damage done: 0")
        pa, two = recommend_setup(tavist, ac, attacks, attack_names)
        tavist.set_two_handed(two)
        window.two_handed.setChecked(two)
        tavist.set_power_attack(pa)
        window.poweratt.blockSignals(True)
        window.poweratt.setText(str(pa))
        window.poweratt.blockSignals(False)
        window.reccommended_poweratt.setText(str(pa))
        mode = "two-handed" if two else "dual-wield"
        append_log(window, f"Auto set for AC {ac}: PA {pa}, {mode}")

    return do_auto


def update_dpr_label(
    window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]
):
    try:
        ac = int(window.target_ac.text() or "0")
    except ValueError:
        ac = 99
    curr_two = tavist.two_handed_mode
    dpr = expected_full_attack(tavist, ac, curr_two, attacks, attack_names)
    window.dpr_label.setText(f"Expected DPR (AC {ac}): {dpr:.1f}")

    best_pa, best_two = recommend_setup(tavist, ac, attacks, attack_names)
    mode = "2H" if best_two else "TWF"
    window.reccommended_poweratt.setText(str(best_pa))
    if not window.poweratt_lock.isChecked():
        window.poweratt.blockSignals(True)
        window.poweratt.setText(str(best_pa))
        window.poweratt.blockSignals(False)
        tavist.set_power_attack(best_pa)
    window.dpr_label.setText(
        f"Expected DPR (AC {ac}): {dpr:.1f} | Best: PA {best_pa} {mode}"
    )
    tracker = getattr(window, "_ac_tracker", None)
    if tracker:
        window.ac_bound.setText(f"AC bound: {format_bound(tracker)}")
        window.damage_done.setText(f"Damage done: {tracker.damage_done}")


def apply_external(window: MainWindow, tavist: Tavist, attacks: list[int], attack_names: list[str]):
    try:
        hit = int(window.ext_hit.text() or "0")
    except ValueError:
        hit = 0
    try:
        strength = int(window.ext_str.text() or "0")
    except ValueError:
        strength = 0
    tavist.set_external_hit(hit)
    tavist.set_external_str(strength)
    update_dpr_label(window, tavist, attacks, attack_names)


def tracking_dialog(window: MainWindow, tavist: Tavist, tracker: ACTargetTracker, results: list[dict], attacks: list[int], attack_names: list[str]):
    if tracker.upper != 99 and (tracker.upper - tracker.lower) <= 1:
        return False
    candidates = [
        r
        for r in results
        if (tracker.lower < r["attack_total"] < tracker.upper and not r.get("natural_twenty"))
        or (r.get("confirm_total") and tracker.lower < r["confirm_total"] < tracker.upper)
    ]
    if not candidates:
        return False

    dialog = QDialog(window)
    dialog.setWindowTitle("Attack Results")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(f"Current AC range: {format_bound(tracker)}"))
    layout.addWidget(QLabel("Select the lowest-AC attack that HIT, or All Misses."))

    selection = {"total": None, "all_miss": False}

    for r in sorted(candidates, key=lambda x: x["attack_total"]):
        label = f"{r['label']} (AC {r['attack_total']})"
        if r.get("threat") and r.get("confirm_total"):
            label += f" / confirm {r['confirm_total']}"
        btn = QPushButton(label)
        btn.setEnabled(True)

        def make_handler(total):
            def handler():
                selection["total"] = total
                dialog.accept()

            return handler

        btn.clicked.connect(make_handler(r["attack_total"]))
        layout.addWidget(btn)

    miss_btn = QPushButton("All Misses")
    miss_btn.clicked.connect(lambda: (selection.update({"all_miss": True}), dialog.accept()))
    layout.addWidget(miss_btn)

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dialog.reject)
    layout.addWidget(cancel_btn)

    if dialog.exec() == QDialog.Accepted:
        apply_tracking_selection(tracker, selection, candidates)
        est = tracker.estimate()
        window.target_ac.blockSignals(True)
        window.target_ac.setText(str(est))
        window.target_ac.blockSignals(False)
        update_dpr_label(window, tavist, attacks, attack_names)
        append_log(
            window,
            f"Updated AC bound: {format_bound(tracker)} (est {est})",
        )
        return True
    return False


def main() -> None:
    app = QApplication([])
    app.setStyleSheet(DARK_THEME_QSS)
    window = MainWindow()

    tavist = Tavist()
    tracker = ACTargetTracker()
    window._ac_tracker = tracker

    attacks = [12, 12, 7, 2]
    attack_names = [f"{name} (+{atk})" for name, atk in zip(["first", "speed", "second", "third"], attacks)]

    def do_single():
        results = wrap_single_attack(window, tavist, attacks, attack_names)()
        if window.tracking.isChecked():
            shown = tracking_dialog(window, tavist, tracker, results, attacks, attack_names)
            if not shown:
                accumulate_known_hits(tracker, results)
                update_dpr_label(window, tavist, attacks, attack_names)
    window.attack_button.clicked.connect(do_single)

    def do_full():
        results = wrap_full_attack(window, tavist, attack_names, attacks)()
        if window.tracking.isChecked():
            shown = tracking_dialog(window, tavist, tracker, results, attacks, attack_names)
            if not shown:
                accumulate_known_hits(tracker, results)
        update_dpr_label(window, tavist, attacks, attack_names)
    window.full_attack.clicked.connect(do_full)

    def apply_two_handed(checked: bool):
        tavist.set_two_handed(checked)
        tavist.bab.bonus = attacks[0]
        update_dpr_label(window, tavist, attacks, attack_names)

    window.two_handed.toggled.connect(apply_two_handed)
    window.auto_button.clicked.connect(
        wrap_auto_recommend(window, tavist, attacks, attack_names)
    )
    apply_two_handed(window.two_handed.isChecked())

    window.evil.clicked.connect(
        make_dice_toggle(tavist.katana_damage, tavist.holy_dice)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.katana_damage, tavist.surge_bonus_main)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.wakasashi_damage, tavist.surge_bonus_off)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.katana_attack, tavist.surge_bonus_attack_main)
    )

    window.poweratt.textChanged.connect(make_power_attack_update(tavist))
    window.poweratt.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )

    window.expertise.textChanged.connect(make_attack_update(tavist.combat_expertise))
    window.expertise.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )
    window.target_ac.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )
    window.ext_hit.textChanged.connect(lambda _: apply_external(window, tavist, attacks, attack_names))
    window.ext_str.textChanged.connect(lambda _: apply_external(window, tavist, attacks, attack_names))

    def apply_fatigue(checked: bool):
        tavist.set_fatigued(checked)
        update_dpr_label(window, tavist, attacks, attack_names)
    window.fatigued.toggled.connect(apply_fatigue)

    def on_tracking_toggled(checked: bool):
        if checked:
            tracker.reset()
            window.damage_done.setText("Damage done: 0")
    window.tracking.toggled.connect(on_tracking_toggled)

    update_dpr_label(window, tavist, attacks, attack_names)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
