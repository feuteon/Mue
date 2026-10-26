# Mue

**Convertisseur de fichiers 100 % local, intégré au clic droit de Windows.**
Clic droit sur un fichier → **Convertir vers** → le format voulu. C'est tout. Aucun fichier ne quitte le PC.

```
photo.heic  ──clic droit──▶  Convertir vers ▸  PNG
                                               JPG
                                               WEBP
                                               …
                                               PDF — fusionner la sélection
                                               ─────────────
                                               Réglages de Mue…
```

## Fonctionnement

- **Rien ne tourne en arrière-plan.** Le menu fait partie de l'Explorateur (registre Windows) : pas besoin de
  lancer Mue au démarrage, il ne consomme rien tant que tu ne cliques pas.
- **Multi-sélection** : sélectionne 50 photos → Convertir vers → WEBP. Une seule fenêtre de progression, les
  conversions tournent en parallèle.
- **L'original n'est jamais touché.** Le résultat est créé à côté (ou dans un sous-dossier, au choix). Si le nom
  existe déjà : `photo (1).png`. Écriture dans un fichier temporaire puis renommage : jamais de fichier à moitié écrit.
- **Le menu s'adapte** : il ne propose que les conversions réellement faisables sur le PC (ex. Word → PDF
  n'apparaît que si LibreOffice ou Microsoft Office est installé).

## Formats

| Depuis | Vers |
|---|---|
| **Images** : JPG, PNG, WEBP, HEIC/HEIF (iPhone), AVIF, BMP, TIFF, ICO, TGA, PSD, QOI… | PNG, JPG, WEBP, AVIF, GIF, BMP, TIFF, ICO, PDF, *PDF fusionné* |
| **GIF animé** | WEBP animé, MP4, WEBM, PNG/JPG (1re image), PDF |
| **SVG** | PNG, JPG, WEBP, ICO, PDF vectoriel |
| **Photos RAW** : CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2… | JPG, PNG, TIFF, WEBP, AVIF |
| **Vidéo** : MP4, MKV, MOV, AVI, WEBM, WMV, FLV, TS, MTS, 3GP… | MP4, MKV, WEBM, MOV, AVI, GIF animé, MP3/WAV (audio seul) |
| **Audio** : MP3, WAV, FLAC, OGG, OPUS, M4A, AAC, WMA, AIFF, APE… | MP3, WAV, FLAC, OGG, OPUS, M4A, AIFF |
| **PDF** | PNG/JPG (une image par page), TXT, *PDF fusionné* |
| **EPUB, XPS, CBZ, FB2, MOBI** | PDF, TXT |
| **CSV / JSON / XLSX** | XLSX, CSV, JSON (sans Office) |
| **Word, Excel, PowerPoint, OpenDocument** | PDF, DOCX, ODT, RTF, TXT, HTML / XLSX, ODS, CSV / PPTX, ODP *(LibreOffice ou MS Office requis)* |

Quelques détails qui font la différence :
- **Vidéo** : quand le conteneur cible accepte les codecs d'origine (MKV H.264 → MP4…), Mue change juste le
  conteneur sans réencoder : quelques secondes au lieu de plusieurs minutes, zéro perte. Sinon réencodage H.264/AAC
  (ou VP9/Opus pour WEBM), avec repli automatique si la voie rapide échoue.
- **Photos** : rotation EXIF appliquée (fini les photos couchées), métadonnées et profil couleur conservés (option
  pour les retirer, GPS compris), transparence aplatie sur fond blanc pour le JPG.
- **Audio** : pochette conservée (MP3/FLAC/M4A), 24 bits préservés en WAV/AIFF.
- **PDF fusionné** : sélectionne des images et/ou des PDF → « PDF — fusionner la sélection » → un seul PDF, dans
  l'ordre des noms (pratique pour des scans). Un JPEG droit est inséré tel quel, sans recompression.
- **CSV** : détection du séparateur et de l'encodage, virgule décimale française, codes à zéros initiaux préservés.

## Installer (toi et tes potes)

1. Lancer `Mue-Setup-1.0.0.exe`. Pas besoin d'être administrateur ; le menu est ajouté automatiquement.
2. L'installeur n'est pas signé : Windows affiche « Windows a protégé votre ordinateur » → **Informations
   complémentaires** → **Exécuter quand même**.
3. **Windows 11** : les applis tierces sont rangées dans **« Afficher plus d'options »** (ou **Maj + clic droit**).
   Pour avoir « Convertir vers » directement, active « Menu classique » dans les réglages de Mue (réversible).
4. Pour Word / Excel / PowerPoint / ODT : installer [LibreOffice](https://fr.libreoffice.org/) (gratuit) si
   Microsoft Office n'est pas là, puis Réglages de Mue → **Mettre à jour le menu**.

Désinstallation : Paramètres Windows → Applications → Mue. Le menu est retiré avec.

Les réglages (qualité JPG/WEBP/AVIF, qualité vidéo, débit audio, dossier de sortie, séparateur CSV…) s'ouvrent
via le menu Démarrer → Mue, ou « Réglages de Mue… » en bas du sous-menu.

## Construire l'installeur

### Option A — GitHub Actions (rien à installer)
1. Pousser le dossier sur un dépôt GitHub (privé, c'est très bien).
2. Onglet **Actions** → **Build Windows** → **Run workflow**.
3. ~5 min plus tard : `Mue-Setup-x.y.z.exe` et `Mue-portable.zip` dans les *Artifacts* du run.
   Pousser un tag (`git tag v1.0.0 && git push --tags`) crée en plus une Release téléchargeable.

### Option B — sur ton PC
- Python 3.11+ (python.org, « Add to PATH » coché) et, pour l'installeur, [Inno Setup 6](https://jrsoftware.org/isdl.php).
- Double-clic sur `build.bat`. Résultat : `dist\Mue\Mue.exe` (portable) et `dist\Mue-Setup-1.0.0.exe`.

### Mode développement
```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py              :: réglages
python main.py --install    :: menu clic droit pointant vers ce dossier (pythonw main.py)
python main.py --to png "C:\chemin\photo.heic"
```
En dev, FFmpeg est pris dans le paquet pip `imageio-ffmpeg` (aucune installation séparée).
Pour l'icône : `python tools\make_icon.py`. La version est à changer dans `mue/__init__.py` et `installer.iss`.

## Organisation du code

```
main.py                  point d'entrée (--to / --install / --uninstall / réglages)
mue/formats.py           extensions reconnues + contenu du menu par catégorie   ← ajouter un format ici
mue/converter.py         aiguillage fichier + cible → moteur, filtrage du menu selon les moteurs dispo
mue/engines/images.py    Pillow, pillow-heif (HEIC), rawpy (RAW), rendu SVG
mue/engines/av.py        FFmpeg : sondage, copie de flux / réencodage, progression, annulation
mue/engines/docs.py      PyMuPDF : PDF → images/texte, EPUB/XPS → PDF, fusion
mue/engines/office.py    LibreOffice headless (profil isolé) ou Microsoft Office (COM)
mue/engines/data.py      CSV ↔ XLSX ↔ JSON (openpyxl)
mue/outputs.py           noms libres, fichiers temporaires, commit/rollback
mue/ipc.py               instance unique (named pipe) : 1 fenêtre pour N fichiers
mue/jobs.py              file d'attente, threads, limites de parallélisme
mue/shell_menu.py        registre : menu en cascade, désinstallation, menu classique Win 11
mue/ui/                  fenêtre de progression, réglages, thème
```

**Ajouter une conversion** : ajouter `(cible, "Libellé")` dans `MENUS` (`formats.py`), gérer la cible dans le
moteur concerné, puis « Mettre à jour le menu » dans les réglages.

## Limites connues

- PDF → Word n'est pas proposé (sans outil lourd, le résultat local est médiocre).
- PDF scanné → texte : pas d'OCR, Mue le signale.
- Les PDF protégés par mot de passe sont refusés.
- Une erreur inattendue est notée dans `%APPDATA%\Mue\crash.log`.

## Licences

Mue s'appuie sur FFmpeg (GPL), PyMuPDF (AGPL), PyQt5 (GPL), Pillow, pillow-heif, rawpy, openpyxl.
Partage gratuit entre amis : aucun souci. Pour une diffusion commerciale, il faudrait revoir ces licences
(et publier le code source, ce qui est déjà le cas ici).
