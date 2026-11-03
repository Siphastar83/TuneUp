import ctypes
import json
import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import psutil

try:
    import winreg
except ImportError:  # lancé hors Windows
    winreg = None

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


# ----------------------------------------------------------------- utilitaires
def ps(cmd, timeout=60):
    """Exécute une commande PowerShell et renvoie la sortie texte."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=NO_WINDOW,
        )
        return (r.stdout or r.stderr).strip()
    except Exception as e:
        return f"Erreur : {e}"


def fmt(n):
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} Po"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_bg(fn):
    threading.Thread(target=fn, daemon=True).start()


# ------------------------------------------------------------------ diagnostic
def get_disks_type():
    out = ps("Get-PhysicalDisk | Select FriendlyName,MediaType,Size | ConvertTo-Json")
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return [(d["FriendlyName"], str(d["MediaType"]), int(d["Size"])) for d in data]
    except Exception:
        return []


def get_cpu_temp():
    out = ps(
        "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
        "| Select -First 1 -ExpandProperty CurrentTemperature"
    )
    try:
        return round(int(out) / 10 - 273.15, 1)
    except Exception:
        return None


def diagnostic():
    lines = []
    ram = psutil.virtual_memory()
    ram_go = ram.total / 1024**3
    lines.append("=== SYSTÈME ===")
    lines.append(f"Windows : {platform.system()} {platform.release()} (build {platform.version()})")
    lines.append(f"Processeur : {platform.processor()}")
    lines.append(f"Cœurs : {psutil.cpu_count(logical=False)} physiques / {psutil.cpu_count()} logiques")
    lines.append(f"Charge CPU : {psutil.cpu_percent(interval=1)} %")
    lines.append(f"RAM : {fmt(ram.total)} (utilisée à {ram.percent} %)")

    lines.append("\n=== DISQUES ===")
    physical = get_disks_type()
    has_hdd = False
    for name, media, size in physical:
        lines.append(f"{name} - {media} - {fmt(size)}")
        if media.upper() == "HDD":
            has_hdd = True
    full = []
    for p in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        lines.append(f"{p.device} : {fmt(u.used)} / {fmt(u.total)} ({u.percent} %)")
        if u.percent > 85:
            full.append(p.device)

    lines.append("\n=== TEMPÉRATURE ===")
    t = get_cpu_temp()
    if t is None:
        lines.append("Non disponible via Windows. Utilise HWiNFO ou LibreHardwareMonitor.")
    else:
        lines.append(f"Zone thermique : {t} °C" + ("  (ÉLEVÉE)" if t > 85 else ""))

    lines.append("\n=== TOP 5 PROCESSUS (RAM) ===")
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            procs.append((p.info["memory_info"].rss, p.info["name"]))
        except Exception:
            pass
    for rss, name in sorted(procs, reverse=True)[:5]:
        lines.append(f"{name} : {fmt(rss)}")

    lines.append("\n=== COMPATIBILITÉ WINDOWS 11 (indicatif) ===")
    if platform.release() == "11" or int(platform.version().split(".")[-1]) >= 22000:
        lines.append("Tu es déjà sous Windows 11.")
    else:
        tpm = ps("(Get-Tpm).TpmPresent")
        sb = ps("Confirm-SecureBootUEFI")
        lines.append(f"TPM présent : {tpm}")
        lines.append(f"Secure Boot : {sb}")
        lines.append(f"RAM >= 4 Go : {'oui' if ram_go >= 3.8 else 'non'}")
        lines.append("Le processeur doit aussi être compatible : vérifie avec l'appli « PC Health Check ».")

    lines.append("\n=== MES CONSEILS ===")
    tips = []
    if has_hdd:
        tips.append("• Disque dur HDD détecté : passer à un SSD est le gain le plus spectaculaire.")
    if ram_go < 12:
        tips.append("• RAM de 8 Go ou moins : passer à 16 Go si possible.")
    if full:
        tips.append(f"• Disque(s) presque plein(s) {', '.join(full)} : libère de l'espace.")
    if ram.percent > 80:
        tips.append("• RAM très sollicitée : ferme des applis ou désactive des programmes au démarrage.")
    if t is not None and t > 85:
        tips.append("• Ça chauffe : dépoussiérage + vérification des ventilateurs / pâte thermique.")
    if not tips:
        tips.append("• Rien d'alarmant. Fais le ménage au démarrage et dans les fichiers temporaires.")
    lines += tips
    return "\n".join(lines)


# ------------------------------------------------------------------- démarrage
STARTUP_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
     r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"),
]
HIVES = {}
if winreg:
    HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}


def list_startup():
    items = []
    if not winreg:
        return items
    for hive, run, approved in STARTUP_KEYS:
        try:
            with winreg.OpenKey(HIVES[hive], run) as k:
                i = 0
                while True:
                    try:
                        name, cmd, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    enabled = True
                    try:
                        with winreg.OpenKey(HIVES[hive], approved) as ak:
                            data, _ = winreg.QueryValueEx(ak, name)
                            enabled = not (data[0] & 1)
                    except OSError:
                        pass
                    items.append((name, enabled, hive, run, approved, cmd))
        except OSError:
            continue
    return items


def set_startup(item, enable):
    name, _, hive, _, approved, _ = item
    data = (b"\x02" if enable else b"\x03") + b"\x00" * 11
    with winreg.CreateKeyEx(HIVES[hive], approved, 0, winreg.KEY_SET_VALUE) as ak:
        winreg.SetValueEx(ak, name, 0, winreg.REG_BINARY, data)


# ------------------------------------------------------------------ nettoyage
def temp_dirs():
    dirs = [os.environ.get("TEMP"), os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp")]
    return [d for d in dirs if d and os.path.isdir(d)]


def dir_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def clean_dir(path):
    freed = 0
    for entry in os.scandir(path):
        try:
            if entry.is_dir(follow_symlinks=False):
                s = dir_size(entry.path)
                shutil.rmtree(entry.path, ignore_errors=True)
                if not os.path.exists(entry.path):
                    freed += s
            else:
                s = entry.stat().st_size
                os.remove(entry.path)
                freed += s
        except Exception:
            pass  # fichier utilisé : on l'ignore
    return freed


def empty_recycle_bin():
    # 0x7 = pas de confirmation, pas de progression, pas de son
    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)


# ------------------------------------------------------------------------- GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TuneUp")
        self.geometry("780x560")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_diag, self.tab_start = ttk.Frame(nb), ttk.Frame(nb)
        self.tab_clean, self.tab_tools = ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.tab_diag, text="Diagnostic")
        nb.add(self.tab_start, text="Démarrage")
        nb.add(self.tab_clean, text="Nettoyage")
        nb.add(self.tab_tools, text="Outils")
        self.build_diag()
        self.build_start()
        self.build_clean()
        self.build_tools()
        if not is_admin():
            ttk.Label(self, foreground="#b45309",
                      text="Astuce : lance en administrateur pour tout nettoyer / modifier.").pack(pady=(0, 6))

    def ui(self, fn, *a):
        self.after(0, lambda: fn(*a))

    # -- diagnostic
    def build_diag(self):
        ttk.Button(self.tab_diag, text="Analyser mon PC", command=self.do_diag).pack(pady=6)
        self.diag_txt = tk.Text(self.tab_diag, wrap="word", font=("Consolas", 10))
        self.diag_txt.pack(fill="both", expand=True, padx=6, pady=6)

    def do_diag(self):
        self.diag_txt.delete("1.0", "end")
        self.diag_txt.insert("end", "Analyse en cours...")
        def work():
            res = diagnostic()
            self.ui(lambda: (self.diag_txt.delete("1.0", "end"), self.diag_txt.insert("end", res)))
        run_bg(work)

    # -- démarrage
    def build_start(self):
        cols = ("Nom", "État", "Commande")
        self.tree = ttk.Treeview(self.tab_start, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (180, 80, 440)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        bar = ttk.Frame(self.tab_start)
        bar.pack(pady=4)
        ttk.Button(bar, text="Actualiser", command=self.refresh_start).pack(side="left", padx=4)
        ttk.Button(bar, text="Désactiver", command=lambda: self.toggle_start(False)).pack(side="left", padx=4)
        ttk.Button(bar, text="Réactiver", command=lambda: self.toggle_start(True)).pack(side="left", padx=4)
        ttk.Label(self.tab_start, foreground="gray",
                  text="Ne désactive pas l'antivirus, les pilotes audio ni les composants système inconnus.").pack()
        self.items = []
        self.refresh_start()

    def refresh_start(self):
        self.tree.delete(*self.tree.get_children())
        self.items = list_startup()
        for i, it in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i),
                             values=(it[0], "Activé" if it[1] else "Désactivé", it[5][:80]))

    def toggle_start(self, enable):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            set_startup(self.items[int(sel[0])], enable)
        except PermissionError:
            messagebox.showerror("Droits insuffisants", "Relance le logiciel en administrateur.")
            return
        self.refresh_start()

    # -- nettoyage
    def build_clean(self):
        bar = ttk.Frame(self.tab_clean)
        bar.pack(pady=6)
        ttk.Button(bar, text="Analyser", command=self.scan_clean).pack(side="left", padx=4)
        ttk.Button(bar, text="Nettoyer", command=self.do_clean).pack(side="left", padx=4)
        self.bin_var = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Vider aussi la corbeille", variable=self.bin_var).pack(side="left", padx=8)
        self.clean_txt = tk.Text(self.tab_clean, height=18, font=("Consolas", 10))
        self.clean_txt.pack(fill="both", expand=True, padx=6, pady=6)

    def log_clean(self, msg):
        self.ui(lambda: (self.clean_txt.insert("end", msg + "\n"), self.clean_txt.see("end")))

    def scan_clean(self):
        self.clean_txt.delete("1.0", "end")
        def work():
            total = 0
            for d in temp_dirs():
                s = dir_size(d)
                total += s
                self.log_clean(f"{d} : {fmt(s)}")
            self.log_clean(f"\nTotal récupérable (environ) : {fmt(total)}")
        run_bg(work)

    def do_clean(self):
        if not messagebox.askyesno("Confirmation", "Supprimer les fichiers temporaires ?"):
            return
        self.clean_txt.delete("1.0", "end")
        def work():
            total = 0
            for d in temp_dirs():
                f = clean_dir(d)
                total += f
                self.log_clean(f"{d} : {fmt(f)} libérés")
            if self.bin_var.get():
                try:
                    empty_recycle_bin()
                    self.log_clean("Corbeille vidée.")
                except Exception as e:
                    self.log_clean(f"Corbeille : {e}")
            self.log_clean(f"\nTotal libéré : {fmt(total)}")
        run_bg(work)

    # -- outils
    def build_tools(self):
        tools = [
            ("Créer un point de restauration (recommandé avant tout)", self.restore_point),
            ("Réglage des effets visuels (Meilleures performances)", lambda: subprocess.Popen("SystemPropertiesPerformance.exe")),
            ("Gestionnaire des tâches", lambda: subprocess.Popen("taskmgr")),
            ("Applications installées (désinstaller l'inutile)", lambda: os.startfile("ms-settings:appsfeatures")),
            ("Stockage / Assistant de stockage", lambda: os.startfile("ms-settings:storagesense")),
            ("Windows Update", lambda: os.startfile("ms-settings:windowsupdate")),
            ("Réparer les fichiers système (sfc /scannow)", self.run_sfc),
            ("Analyse du disque (chkdsk lecture seule)", self.run_chkdsk),
        ]
        for text, cmd in tools:
            ttk.Button(self.tab_tools, text=text, command=cmd, width=60).pack(pady=5)
        self.tool_lbl = ttk.Label(self.tab_tools, text="")
        self.tool_lbl.pack(pady=8)

    def restore_point(self):
        def work():
            out = ps('Checkpoint-Computer -Description "TuneUp" -RestorePointType MODIFY_SETTINGS')
            self.ui(lambda: messagebox.showinfo("Point de restauration",
                    out or "Point de restauration créé (si la protection système est activée)."))
        run_bg(work)

    def run_sfc(self):
        if is_admin():
            subprocess.Popen("cmd /k sfc /scannow")
        else:
            messagebox.showwarning("Administrateur requis", "Relance le logiciel en administrateur.")

    def run_chkdsk(self):
        subprocess.Popen("cmd /k chkdsk C:")


if __name__ == "__main__":
    if platform.system() != "Windows":
        print("Ce logiciel est prévu pour Windows.")
    else:
        App().mainloop()
