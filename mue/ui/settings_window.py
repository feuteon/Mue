"""Fenêtre de réglages (Mue.exe lancé sans argument, ou « Réglages de Mue… » dans le menu)."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
                             QSlider, QSpinBox, QVBoxLayout, QWidget)

from .. import APP_NAME, TAGLINE, VERSION, shell_menu
from ..formats import CATEGORIES, CATEGORY_LABELS
from ..settings import Settings
from . import theme
from .widgets import Toggle, app_icon, app_pixmap

IS_WIN = sys.platform == "win32"


def muted(text: str, size: float = 8.5, wrap: bool = True) -> QLabel:
    l = QLabel(text)
    l.setFont(theme.font(size))
    l.setProperty("muted", True)
    l.setWordWrap(wrap)
    return l


class Card(QFrame):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("Card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 16, 18, 16)
        self.lay.setSpacing(12)
        t = QLabel(title)
        t.setFont(theme.font(11, QFont.DemiBold))
        self.lay.addWidget(t)
        if subtitle:
            self.lay.addWidget(muted(subtitle))
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(0, 1)
        self.lay.addLayout(self.grid)
        self._row = 0

    def row(self, label: str, widget: QWidget, hint: str = "") -> None:
        box = QVBoxLayout()
        box.setSpacing(1)
        l = QLabel(label)
        l.setFont(theme.font(9.5))
        box.addWidget(l)
        if hint:
            box.addWidget(muted(hint, 8))
        self.grid.addLayout(box, self._row, 0)
        self.grid.addWidget(widget, self._row, 1, Qt.AlignRight | Qt.AlignVCenter)
        self._row += 1

    def full(self, widget: QWidget) -> None:
        self.grid.addWidget(widget, self._row, 0, 1, 2)
        self._row += 1


class SettingsWindow(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.s = settings
        self.setObjectName("Root")
        self.setWindowTitle(f"{APP_NAME} — Réglages")
        self.setWindowIcon(app_icon())
        self.resize(640, 780)
        self.setMinimumWidth(560)
        self._save_timer = QTimer(self, singleShot=True, interval=300)
        self._save_timer.timeout.connect(self.s.save)

        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(22, 22, 22, 26)
        col.setSpacing(14)
        col.addLayout(self._header())
        col.addWidget(self._menu_card())
        col.addWidget(self._output_card())
        col.addWidget(self._images_card())
        col.addWidget(self._av_card())
        col.addWidget(self._engines_card())
        col.addWidget(self._formats_card())
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        scroll.setFrameShape(QFrame.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.refresh_status()

    # --- Helpers ----------------------------------------------------------------------

    def _changed(self) -> None:
        self._save_timer.start()

    def _toggle(self, attr: str) -> Toggle:
        t = Toggle(getattr(self.s, attr))
        t.toggled.connect(lambda v: (setattr(self.s, attr, v), self._changed()))
        return t

    def _combo(self, attr: str, options: list[tuple[str, object]], after=None) -> QComboBox:
        c = QComboBox()
        c.setMinimumWidth(210)
        for label, val in options:
            c.addItem(label, val)
        idx = next((i for i, (_, v) in enumerate(options) if v == getattr(self.s, attr)), 0)
        c.setCurrentIndex(idx)

        def on(i):
            setattr(self.s, attr, c.itemData(i))
            self._changed()
            if after:
                after()
        c.currentIndexChanged.connect(on)
        return c

    def _spin(self, attr: str, lo: int, hi: int, suffix: str = "", step: int = 1) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setValue(getattr(self.s, attr))
        sp.setSuffix(suffix)
        sp.setMinimumWidth(110)
        sp.setAlignment(Qt.AlignRight)
        sp.valueChanged.connect(lambda v: (setattr(self.s, attr, v), self._changed()))
        return sp

    def _slider(self, attr: str, lo: int, hi: int) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(getattr(self.s, attr))
        sl.setFixedWidth(160)
        val = QLabel(str(sl.value()))
        val.setFixedWidth(28)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val.setFont(theme.font(9.5, QFont.DemiBold))

        def on(v):
            val.setText(str(v))
            setattr(self.s, attr, v)
            self._changed()
        sl.valueChanged.connect(on)
        h.addWidget(sl)
        h.addWidget(val)
        return w

    # --- Sections ---------------------------------------------------------------------

    def _header(self) -> QHBoxLayout:
        logo = QLabel()
        logo.setPixmap(app_pixmap(64))
        logo.setFixedSize(64, 64)
        name = QLabel(APP_NAME)
        name.setFont(theme.font(20, QFont.Bold))
        tag = muted(TAGLINE, 9.5, wrap=False)
        v = QVBoxLayout()
        v.setSpacing(0)
        v.addStretch(1)
        v.addWidget(name)
        v.addWidget(tag)
        v.addStretch(1)
        ver = muted(f"v{VERSION}", 8.5, wrap=False)
        ver.setProperty("faint", True)
        h = QHBoxLayout()
        h.setSpacing(16)
        h.addWidget(logo)
        h.addLayout(v, 1)
        h.addWidget(ver, 0, Qt.AlignTop)
        return h

    def _menu_card(self) -> Card:
        c = Card("Menu clic droit",
                 "Ajoute « Convertir vers » au clic droit des fichiers dans l'Explorateur. "
                 "Rien ne tourne en arrière-plan : Mue ne se lance que quand tu cliques.")
        self.status_lbl = QLabel()
        self.status_lbl.setFont(theme.font(9.5, QFont.DemiBold))
        self.install_btn = QPushButton("Ajouter au clic droit")
        self.install_btn.setProperty("primary", True)
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.clicked.connect(self.do_install)
        self.remove_btn = QPushButton("Retirer")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setProperty("danger", True)
        self.remove_btn.clicked.connect(self.do_uninstall)
        bar = QHBoxLayout()
        bar.addWidget(self.status_lbl, 1)
        bar.addWidget(self.remove_btn)
        bar.addWidget(self.install_btn)
        c.lay.addLayout(bar)

        if IS_WIN and shell_menu.is_windows_11():
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {theme.BORDER};")
            c.lay.addWidget(sep)
            self.classic = Toggle(shell_menu.classic_menu_enabled())
            self.classic.toggled.connect(self.set_classic)
            c.row("Menu classique (style Windows 10)", self.classic,
                  "Sous Windows 11, les entrées des applis sont rangées dans « Afficher plus "
                  "d'options » (ou Maj + clic droit). Active ceci pour avoir « Convertir vers » "
                  "directement. Réversible ; l'Explorateur redémarre.")
        return c

    def _output_card(self) -> Card:
        c = Card("Où enregistrer")
        self.sub_edit = QLineEdit(self.s.subfolder_name)
        self.sub_edit.setMinimumWidth(210)
        self.sub_edit.textChanged.connect(lambda t: (setattr(self.s, "subfolder_name", t), self._changed()))
        c.row("Emplacement des fichiers convertis",
              self._combo("output_mode", [("À côté de l'original", "same"),
                                          ("Dans un sous-dossier", "subfolder")],
                          after=lambda: self.sub_edit.setEnabled(self.s.output_mode == "subfolder")),
              "L'original n'est jamais modifié ni supprimé. Si le nom existe : « photo (1).png ».")
        c.row("Nom du sous-dossier", self.sub_edit)
        self.sub_edit.setEnabled(self.s.output_mode == "subfolder")
        c.row("Ouvrir le dossier à la fin", self._toggle("open_folder_when_done"))
        c.row("Fermer la fenêtre de progression automatiquement", self._toggle("auto_close"),
              "Seulement si tout s'est bien passé.")
        return c

    def _images_card(self) -> Card:
        c = Card("Images & PDF")
        c.row("Qualité JPG", self._slider("jpeg_quality", 50, 100), "92 = excellent compromis")
        c.row("Qualité WEBP", self._slider("webp_quality", 40, 100))
        c.row("Qualité AVIF", self._slider("avif_quality", 30, 100))
        c.row("Conserver les métadonnées (EXIF, profil couleur)", self._toggle("keep_metadata"),
              "Désactive pour retirer date, appareil, position GPS…")
        c.row("Fond quand la transparence est retirée (JPG, BMP)",
              self._combo("background", [("Blanc", "#FFFFFF"), ("Noir", "#000000")]))
        c.row("Rendu SVG : taille minimale", self._spin("svg_min_size", 64, 8192, " px", 64),
              "Côté le plus long de l'image produite.")
        c.row("PDF → images : résolution", self._spin("pdf_dpi", 72, 600, " dpi", 25))
        c.row("Images → PDF : format de page",
              self._combo("pdf_page", [("A4 (adapté à l'image)", "a4"), ("Taille de l'image", "image")]))
        return c

    def _av_card(self) -> Card:
        c = Card("Audio, vidéo & données")
        c.row("Qualité vidéo (si réencodage)",
              self._combo("video_quality", [("Rapide", "fast"), ("Équilibrée", "balanced"),
                                            ("Maximale (plus lent)", "best")]),
              "Quand c'est possible, Mue change juste le conteneur sans réencoder (instantané).")
        c.row("Débit audio (MP3, AAC, Opus)",
              self._combo("audio_bitrate", [("128 kb/s", 128), ("192 kb/s", 192),
                                            ("256 kb/s", 256), ("320 kb/s", 320)]))
        c.row("GIF animé : images/seconde", self._spin("gif_fps", 5, 50, " i/s"))
        c.row("GIF animé : largeur max", self._spin("gif_width", 120, 1920, " px", 40))
        c.row("Séparateur CSV produit",
              self._combo("csv_delimiter", [("Virgule  ,", ","), ("Point-virgule  ;  (Excel FR)", ";"),
                                            ("Tabulation", "\t")]))
        return c

    def _engines_card(self) -> Card:
        c = Card("Moteurs", "Tout est fait sur ta machine. Aucun fichier n'est envoyé sur Internet.")
        self.ff_lbl = muted("", 8.5)
        ff_btn = QPushButton("Choisir…")
        ff_btn.clicked.connect(self.pick_ffmpeg)
        c.row("FFmpeg (audio & vidéo)", ff_btn)
        c.full(self.ff_lbl)

        self.lo_lbl = muted("", 8.5)
        self.lo_lbl.setTextFormat(Qt.RichText)
        self.lo_lbl.setOpenExternalLinks(True)
        lo_btn = QPushButton("Choisir…")
        lo_btn.clicked.connect(self.pick_soffice)
        c.row("LibreOffice (documents)", lo_btn)
        c.full(self.lo_lbl)

        self.ms_lbl = muted("", 8.5)
        c.row("Moteur pour Word / Excel / PowerPoint",
              self._combo("office_engine", [("Automatique", "auto"), ("LibreOffice", "libreoffice"),
                                            ("Microsoft Office", "msoffice")],
                          after=self.refresh_status))
        c.full(self.ms_lbl)
        self.update_menu_btn = QPushButton("Mettre à jour le menu")
        self.update_menu_btn.setCursor(Qt.PointingHandCursor)
        self.update_menu_btn.clicked.connect(self.do_install)
        c.row("Après avoir installé LibreOffice ou changé un moteur", self.update_menu_btn,
              "Le menu ne propose que ce qui est réellement faisable sur ce PC.")
        return c

    def _formats_card(self) -> Card:
        c = Card("Formats reconnus")
        for cat, exts in CATEGORIES.items():
            lab = QLabel(CATEGORY_LABELS.get(cat, cat))
            lab.setFont(theme.font(9, QFont.DemiBold))
            lab.setStyleSheet(f"color: {theme.CATEGORY_COLORS.get(cat, theme.TEXT)};")
            c.grid.addWidget(lab, c._row, 0, Qt.AlignTop)
            l = muted("  ".join(sorted(e.upper() for e in exts)), 8.5)
            c.grid.addWidget(l, c._row, 1)
            c._row += 1
        c.grid.setColumnStretch(0, 0)
        c.grid.setColumnStretch(1, 1)
        return c

    # --- Statut & actions -----------------------------------------------------------------

    def refresh_status(self) -> None:
        from ..engines import av, office
        try:
            st = shell_menu.status() if IS_WIN else "absent"
        except Exception:
            st = "absent"
        text, color = {
            "ok": ("● Installé", theme.OK),
            "stale": ("● À réparer (Mue a été déplacé)", "#FFB86B"),
            "absent": ("● Pas encore installé", theme.MUTED),
        }[st]
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color};")
        self.install_btn.setText("Réinstaller" if st == "ok" else "Ajouter au clic droit")
        self.remove_btn.setVisible(st != "absent")

        ff = av.find_ffmpeg(self.s)
        self.ff_lbl.setText(f"✓ {ff}  (version {av.version(ff)})" if ff else
                            "✗ Introuvable — les conversions audio/vidéo ne seront pas proposées.")
        so = office.find_soffice(self.s)
        self.lo_lbl.setText(f"✓ {so}" if so else
                            "✗ Non installé — <a style='color:#8E7CFF' href='https://fr.libreoffice.org/download/telecharger-libreoffice/'>"
                            "télécharger LibreOffice</a> (gratuit) pour convertir Word, Excel, PowerPoint, ODT…")
        apps = [a for a in ("Word", "Excel", "PowerPoint") if office.has_ms(a)]
        self.ms_lbl.setText(("✓ Microsoft Office détecté : " + ", ".join(apps)) if apps else
                            "Microsoft Office non détecté.")

    def do_install(self) -> None:
        if not IS_WIN:
            QMessageBox.information(self, APP_NAME, "Le menu clic droit n'existe que sous Windows.")
            return
        self.s.save()
        try:
            n = shell_menu.install(self.s)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Impossible d'écrire dans le registre :\n{e}")
            return
        self.refresh_status()
        self.status_lbl.setText(f"● Installé pour {n} types de fichiers")

    def do_uninstall(self) -> None:
        try:
            shell_menu.uninstall()
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Erreur :\n{e}")
        self.refresh_status()

    def set_classic(self, on: bool) -> None:
        r = QMessageBox.question(
            self, APP_NAME,
            "L'Explorateur Windows va redémarrer (la barre des tâches clignote une seconde, "
            "les fenêtres de dossiers ouvertes se ferment).\n\nContinuer ?")
        if r != QMessageBox.Yes:
            self.classic.blockSignals(True)
            self.classic.setChecked(not on)
            self.classic.set_knob(1.0 if not on else 0.0)
            self.classic.blockSignals(False)
            return
        shell_menu.set_classic_menu(on)
        shell_menu.restart_explorer()

    def pick_ffmpeg(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Choisir ffmpeg", "", "ffmpeg (ffmpeg.exe ffmpeg);;Tous (*)")
        if f:
            self.s.ffmpeg_path = f
            self._after_engine_change()

    def pick_soffice(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Choisir soffice.exe (dossier program de LibreOffice)",
                                           "", "soffice (soffice.exe soffice);;Tous (*)")
        if f:
            self.s.soffice_path = f
            self._after_engine_change()

    def _after_engine_change(self) -> None:
        from ..engines import av
        av.encoders.cache_clear()
        self.s.save()
        self.refresh_status()
