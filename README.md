<p align="center">
  <img src="assets/logo.png" alt="Logo TuneUp" width="140">
</p>

<h1 align="center">TuneUp</h1>

<p align="center">
  Un petit outil Windows, simple et sûr, pour redonner un coup de frais à un PC de 3-4 ans.
</p>

---

## À propos

**TuneUp** automatise les gestes d'optimisation recommandés pour Windows, sans promesse
miracle : pas de nettoyeur de registre, pas de désactivation de services, pas de
« booster en un clic ». Toutes les actions sont **sûres et réversibles**.

## Fonctionnalités

| Onglet         | Ce que ça fait                                                                                                                                                   |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Diagnostic** | CPU, RAM, type de disque (HDD/SSD), espace libre, température (si disponible), top 5 des processus gourmands, compatibilité Windows 11 et conseils personnalisés |
| **Démarrage**  | Liste des programmes lancés au démarrage, avec activation / désactivation (même mécanisme que le Gestionnaire des tâches)                                        |
| **Nettoyage**  | Analyse et suppression des fichiers temporaires (`%TEMP%` et `Windows\Temp`), vidage de la corbeille en option                                                   |
| **Outils**     | Point de restauration, effets visuels, Gestionnaire des tâches, applications installées, Assistant de stockage, Windows Update, `sfc /scannow`, `chkdsk`         |

## Installation

1. Va dans l'onglet **Releases** du dépôt (ou **Actions → dernier run → Artifacts**).
2. Télécharge `TuneUp.exe`.
3. Lance-le. Windows demandera les droits administrateur, nécessaires pour nettoyer les
   dossiers système et créer un point de restauration.

> **SmartScreen / antivirus** : l'exécutable n'est pas signé numériquement. Windows peut
> afficher un avertissement (« Informations complémentaires » puis « Exécuter quand même »),
> et certains antivirus signalent à tort les `.exe` créés avec PyInstaller.
> Tu peux aussi lancer directement le code source (voir ci-dessous).

## Utilisation conseillée

1. **Crée un point de restauration** (onglet Outils) avant toute modification.
2. Lance une **analyse** dans l'onglet Diagnostic et lis les conseils.
3. Fais le ménage dans l'onglet **Démarrage** : désactive Discord, Teams, Spotify,
   launchers de jeux, etc. si tu ne t'en sers pas systématiquement.
   Ne désactive pas l'antivirus, les pilotes audio ni les composants système inconnus.
4. Lance le **Nettoyage** des fichiers temporaires.

## Lancer depuis le code source

Prérequis : Windows et Python 3.10 ou plus.

```bash
pip install -r requirements.txt
python tuneup.py
```

## Compiler soi-même en .exe

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --uac-admin --name TuneUp --icon assets/logo.ico tuneup.py
```

Le fichier se trouve ensuite dans `dist/TuneUp.exe`.

## Compilation automatique (GitHub Actions)

Le workflow `.github/workflows/build.yml` compile l'application sur une machine Windows :

- à chaque push sur `main`, à chaque pull request et à la demande (**Run workflow**) :
  le `.exe` est disponible dans les **Artifacts** du run ;
- à chaque tag `v*` : le `.exe` est aussi publié dans les **Releases**.

Publier une version :

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Structure du projet

```
tuneup.py                      Application (interface tkinter)
requirements.txt               Dépendances (psutil)
assets/logo.png                Logo
assets/logo.ico                Icône de l'exécutable
.github/workflows/build.yml    Compilation automatique en .exe
```

## Limites

- Windows uniquement.
- La température du processeur n'est pas toujours exposée par Windows. Pour un suivi fiable,
  utilise HWiNFO ou LibreHardwareMonitor.
- Le test de compatibilité Windows 11 est indicatif : vérifie aussi avec l'application
  Microsoft « PC Health Check ».
- Les plus gros gains viennent souvent du matériel : passer d'un HDD à un SSD, ou de 8 à 16 Go
  de RAM.

## Avertissement

Cet outil est fourni tel quel, sans garantie. Crée un point de restauration avant de modifier
ton système. « TuneUp » est aussi le nom de logiciels commerciaux existants ; ce projet n'a
aucun lien avec eux.
