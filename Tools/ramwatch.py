#!/usr/bin/env python3
import argparse
import os
import select
import shutil
import signal
import subprocess
import sys
import termios
import time
from collections import deque
from pathlib import Path

try:
    import psutil
except ImportError:
    sys.exit("psutil is required. Install it with:  pip install psutil")

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

class C:
    RESET = "\033[0m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    DIM = "\033[2m" if USE_COLOR else ""
    RED = "\033[31m" if USE_COLOR else ""
    GREEN = "\033[32m" if USE_COLOR else ""
    YELLOW = "\033[33m" if USE_COLOR else ""
    BLUE = "\033[34m" if USE_COLOR else ""
    MAGENTA = "\033[35m" if USE_COLOR else ""
    CYAN = "\033[36m" if USE_COLOR else ""

TIPS = {
    "chrome": "Close tabs you are not using — each tab eats RAM.",
    "chromium": "Close tabs you are not using — each tab eats RAM.",
    "firefox": "Close tabs you are not using; restart Firefox to release memory.",
    "code": "VS Code grows with open projects/extensions. Close unused windows.",
    "node": "A dev server or app is running in the background. Stop it if unused.",
    "java": "Java apps (IDEs/servers) reserve lots of RAM. Close if not needed.",
    "jetbrains": "Your IDE is indexing or holding a big project. Close it when done.",
    "idea": "IntelliJ IDEA holds large projects in memory. Close when done.",
    "pycharm": "PyCharm holds large projects in memory. Close when done.",
    "slack": "Slack is an Electron app — heavy for a chat app. Restart or quit.",
    "discord": "Discord runs in the background. Quit fully from the tray icon.",
    "spotify": "Spotify caches music in RAM. Restart it if it has grown huge.",
    "steam": "Steam + games use lots of RAM/CPU. Close games you finished.",
    "docker": "Containers are using resources. Stop unused ones: docker ps",
    "containerd": "Containers are using resources. Stop unused ones: docker ps",
    "vlc": "Videos use RAM. Close playback when done.",
    "zoom": "Video calls are heavy on CPU. Mute/stop video to reduce load.",
    "teams": "Teams is heavy. Quit fully from the tray icon when not in a call.",
    "gnome-shell": "The desktop itself is strained. Close apps or log out/in.",
    "mysqld": "A database server is running. Stop it if you do not need it.",
    "postgres": "A database server is running. Stop it if you do not need it.",
}

FRIENDLY_NAMES = {
    "chrome": "Google Chrome (browser)",
    "chromium": "Chromium (browser)",
    "firefox": "Firefox (browser)",
    "firefox-bin": "Firefox (browser)",
    "code": "VS Code (editor)",
    "node": "Node.js (dev server/app)",
    "java": "Java app/server",
    "python3": "Python script/app",
    "spotify": "Spotify (music)",
    "discord": "Discord (chat)",
    "slack": "Slack (chat)",
    "zoom": "Zoom (video calls)",
    "vlc": "VLC (video player)",
    "steam": "Steam (games)",
}


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def color_for(pct, warn=70, crit=90):
    if pct >= crit:
        return C.RED
    if pct >= warn:
        return C.YELLOW
    return C.GREEN


def bar(pct, width=26):
    filled = int(round(pct / 100 * width))
    filled = max(0, min(width, filled))
    col = color_for(pct)
    return f"{col}{'█' * filled}{C.DIM}{'░' * (width - filled)}{C.RESET}"


def sparkline(hist):
    chars = "▁▂▃▄▅▆▇█"
    if len(hist) < 3:
        return ""
    pts = list(hist)[-24:]
    s = "".join(chars[min(7, int(p / 100 * 7))] for p in pts)
    col = color_for(pts[-1])
    return f"  {C.DIM}trend{C.RESET} {col}{s}{C.RESET}"


def ram_status(pct):
    if pct < 60:
        return f"{C.GREEN}Healthy — plenty of room{C.RESET}", False
    if pct < 80:
        return f"{C.YELLOW}Moderate load — fine for now{C.RESET}", False
    if pct < 92:
        return f"{C.RED}Heavy — things may feel slow{C.RESET}", True
    return f"{C.RED}CRITICAL — close apps now!{C.RESET}", True


def swap_status(pct):
    if pct <= 0:
        return f"{C.GREEN}Not used — good{C.RESET}", False
    if pct < 50:
        return f"{C.YELLOW}Some overflow — okay{C.RESET}", False
    if pct < 80:
        return f"{C.YELLOW}Heavy swapping — expect slowness{C.RESET}", True
    return f"{C.RED}Almost full — system will stutter{C.RESET}", True


def cpu_status(pct):
    if pct < 60:
        return f"{C.GREEN}Relaxed{C.RESET}", False
    if pct < 85:
        return f"{C.YELLOW}Busy — something is working hard{C.RESET}", False
    return f"{C.RED}Maxed out — find the culprit below{C.RESET}", True


def health_score(mem_pct, swap_pct, cpu_pct, offenders):
    score = 10.0
    score -= max(0.0, mem_pct - 55) * 0.05
    score -= max(0.0, swap_pct - 20) * 0.03
    score -= max(0.0, cpu_pct - 50) * 0.02
    score -= min(2.0, 0.5 * len(offenders))
    score = max(0.0, min(10.0, score))

    culprit = None
    for g in offenders:
        if g["mem"] >= 15 and g["cpu"] >= 0:
            culprit = g
            break

    if score >= 8.5:
        verdict, col = "Excellent — nothing to worry about", C.GREEN
    elif score >= 7:
        verdict, col = "Good — minor drag only", C.GREEN
    elif score >= 5:
        verdict, col = "Fair — starting to feel sluggish", C.YELLOW
    elif score >= 3:
        verdict, col = "Poor — close some apps", C.RED
    else:
        verdict, col = "Critical — your PC is drowning", C.RED

    if culprit and score < 8.5:
        verdict += f" · main drag: {culprit['name']}"
    return score, verdict, col


def display_name(name):
    key = name.lower()
    base = FRIENDLY_NAMES.get(key)
    if base:
        return f"{base} ({name})"
    return name


def load_startup_apps():
    dirs = [Path.home() / ".config" / "autostart", Path("/etc/xdg/autostart")]
    apps = {}
    for d in dirs:
        user_level = d == dirs[0]
        try:
            files = list(d.glob("*.desktop"))
        except OSError:
            continue
        for f in files:
            name = exec_ = None
            hidden = False
            enabled = True
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("Name=") and name is None:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and exec_ is None:
                    exec_ = line[5:].strip()
                elif line == "Hidden=true":
                    hidden = True
                elif line == "X-GNOME-Autostart-enabled=false":
                    enabled = False
            if hidden or not enabled or not exec_:
                continue
            exe = exec_.split()[0].strip('"').strip("'")
            base = Path(exe).name.lower()
            if base in ("sh", "bash", "true", "false"):
                continue
            entry = {"name": name or base, "exe": base}
            if user_level or base not in apps:
                apps[base] = entry
    return list(apps.values())


class Monitor:
    def __init__(self, top_n, mem_thr, cpu_thr):
        self.top_n = top_n
        self.mem_thr = mem_thr
        self.cpu_thr = cpu_thr
        self.ncores = psutil.cpu_count(logical=True) or 1
        self.procs = {}
        self.hist_mem = deque(maxlen=40)
        self.hist_cpu = deque(maxlen=40)
        self.prev_net = psutil.net_io_counters()
        self.prev_net_t = time.monotonic()

    def _track(self):
        seen = set()
        for p in psutil.process_iter(["pid"]):
            seen.add(p.pid)
            if p.pid not in self.procs:
                try:
                    p.cpu_percent(None)
                except psutil.Error:
                    pass
                self.procs[p.pid] = p
        for pid in list(self.procs):
            if pid not in seen:
                del self.procs[pid]

    def net_rates(self):
        now = psutil.net_io_counters()
        t = time.monotonic()
        dt = t - self.prev_net_t
        if dt <= 0:
            return 0.0, 0.0
        down = (now.bytes_recv - self.prev_net.bytes_recv) / dt
        up = (now.bytes_sent - self.prev_net.bytes_sent) / dt
        return max(0.0, down), max(0.0, up)

    def collect(self):
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        cpu_pct = psutil.cpu_percent(interval=None)

        groups = {}
        for pid, p in self.procs.items():
            try:
                rss = p.memory_info().rss
                mpct = p.memory_percent()
                cpct = p.cpu_percent(None) / self.ncores
                name = p.name() or "?"
            except (psutil.Error, OSError):
                continue
            key = name.lower()
            g = groups.setdefault(
                key,
                {"name": name, "rss": 0, "mem": 0.0, "cpu": 0.0, "count": 0},
            )
            g["rss"] += rss
            g["mem"] += mpct
            g["cpu"] += cpct
            g["count"] += 1

        self.hist_mem.append(vm.percent)
        self.hist_cpu.append(cpu_pct)

        top = sorted(groups.values(), key=lambda g: g["rss"], reverse=True)
        offenders = [g for g in top if g["mem"] >= self.mem_thr or g["cpu"] >= self.cpu_thr]
        return vm, sm, cpu_pct, top[: self.top_n], offenders, groups


def render(mon, width=78, fit=True):
    vm, sm, cpu, top, offenders, groups = mon.collect()
    ts = shutil.get_terminal_size((78, 24))
    w = min(width, ts.columns)
    rows = max(12, ts.lines)

    compact = fit and rows < 30
    tiny = fit and rows < 19
    sep = f"  {'─' * (w - 4)}"

    mem_pct = vm.percent
    swap_pct = sm.percent
    status, bad = ram_status(mem_pct)
    s_status, s_bad = swap_status(swap_pct)
    c_status, c_bad = cpu_status(cpu)
    score, verdict, scol = health_score(mem_pct, swap_pct, cpu, offenders)

    head = [
        "",
        f"  {C.BOLD}RAMWATCH{C.RESET} {C.DIM}· plain-English task manager ·{C.RESET} "
        f"{time.strftime('%a %d %b %Y %H:%M:%S')}",
    ]
    if not tiny:
        head.append(f"  {C.BOLD}HEALTH  {scol}{score:.1f}/10{C.RESET}  {scol}{verdict}{C.RESET}")
    head.append(sep)

    vitals = []
    vitals.append(f"  {C.BOLD}MEMORY {bar(mem_pct)} {color_for(mem_pct)}{mem_pct:5.1f}%{C.RESET}"
                  f"   {human(vm.used)} of {human(vm.total)} used")
    if not tiny:
        vitals.append(f"         {status}  {C.DIM}· free: {human(vm.available)}{C.RESET}"
                      f"{'' if compact else sparkline(mon.hist_mem)}")
    vitals.append(f"  {C.BOLD}SWAP   {bar(swap_pct)} {color_for(swap_pct, 50, 80)}{swap_pct:5.1f}%{C.RESET}"
                  f"   {human(sm.used)} of {human(sm.total)} used")
    if not tiny:
        vitals.append(f"         {s_status}")
    vitals.append(f"  {C.BOLD}CPU    {bar(cpu)} {color_for(cpu)}{cpu:5.1f}%{C.RESET}"
                  f"   across {mon.ncores} cores")
    if not tiny:
        vitals.append(f"         {c_status}{'' if compact else sparkline(mon.hist_cpu)}")

    if not tiny:
        disks_shown = 0
        seen_mnts = set()
        max_disks = 1 if compact else 2
        for part in psutil.disk_partitions(all=False):
            mnt = part.mountpoint
            if mnt in seen_mnts or "snap" in mnt or "/boot" in mnt:
                continue
            seen_mnts.add(mnt)
            try:
                du = psutil.disk_usage(mnt)
            except (OSError, PermissionError):
                continue
            dpct = du.percent
            warn_col = color_for(dpct, 80, 92)
            note = ""
            if dpct >= 92:
                note = f"  {C.RED}· nearly full! delete old files/downloads{C.RESET}"
            elif dpct >= 80:
                note = f"  {C.YELLOW}· getting full{C.RESET}"
            vitals.append(f"  {C.BOLD}DISK   {bar(dpct)} {warn_col}{dpct:5.1f}%{C.RESET}"
                          f"   {human(du.used)} of {human(du.total)} on {mnt}{note}")
            disks_shown += 1
            if disks_shown >= max_disks:
                break
        down, up = mon.net_rates()
        net_note = "" if compact else "   " + C.DIM + "(internet speed right now)" + C.RESET
        vitals.append(f"  {C.BOLD}NET    {C.CYAN}↓ {human(down)}/s{C.RESET}   "
                      f"{C.BLUE}↑ {human(up)}/s{C.RESET}{net_note}")

    apps_hdr = [sep]
    if not tiny:
        apps_hdr.append(f"  {C.BOLD}{C.CYAN}TOP APPS{C.RESET} "
                        f"{C.DIM}(same app counted once, all its windows combined){C.RESET}")
        apps_hdr.append(f"  {C.DIM}{'APP':<38}{'×N':>4}  {'RAM':>9}  {'%MEM':>6}  {'%CPU':>6}{C.RESET}")

    app_rows = []
    if not top:
        app_rows.append(f"  {C.DIM}no readable processes{C.RESET}")
    limit = mon.top_n if not compact else min(mon.top_n, 5)
    for g in top[:limit]:
        label = display_name(g["name"])
        if len(label) > 37:
            label = label[:34] + "…"
        mcol = color_for(g["mem"], mon.mem_thr, 60)
        ccol = color_for(g["cpu"], mon.cpu_thr, 85)
        cnt = str(g["count"]) + ("s" if g["count"] > 1 else "")
        app_rows.append(
            f"  {label:<38.38}{C.DIM}×{cnt:<2}{C.RESET}  {human(g['rss']):>9}"
            f"  {mcol}{g['mem']:5.1f}%{C.RESET}  {ccol}{g['cpu']:5.1f}%{C.RESET}"
        )

    warn_hdr = [sep]
    if not tiny:
        warn_hdr.append(f"  {C.BOLD}{C.MAGENTA}⚠ NEEDS YOUR ATTENTION{C.RESET}")

    alert_rows = []
    alerts = []
    if bad and mem_pct >= 92:
        alerts.append("Your memory is nearly FULL. Close the biggest apps listed above.")
    elif bad:
        alerts.append("Memory usage is high. If things feel slow, close the biggest apps.")
    if s_bad:
        alerts.append("Swap is heavily used — your PC is borrowing disk as RAM. Free memory by closing apps.")
    if c_bad:
        alerts.append("CPU is maxed out — a program is working very hard (see %CPU column).")

    max_off = 2 if compact else 5
    for g in offenders[:max_off]:
        tip = TIPS.get(g["name"].lower())
        msg = (f"{display_name(g['name'])} is using "
               f"{human(g['rss'])} ({g['mem']:.0f}% of RAM)")
        if g["count"] > 1:
            msg += f" across {g['count']} processes"
        msg += "."
        alerts.append(msg)
        if tip and not compact:
            alerts.append(f"↳ Tip: {tip}")
        alerts.append(f"↳ Closing it frees about {human(g['rss'])}. Kill it later with: ramwatch --kill <PID>")

    if not alerts:
        alert_rows.append(f"  {C.GREEN}✓ All good — nothing needs your attention.{C.RESET}")
    else:
        for a in alerts:
            prefix = "• " if not a.startswith("↳") else "  "
            col = "" if a.startswith("↳") else C.YELLOW
            alert_rows.append(f"  {prefix}{col}{a}{C.RESET}")

    start_rows = []
    start_hdr = []
    if not compact and not tiny:
        startup = load_startup_apps()
        running_startup = []
        for app in startup:
            base = app["exe"]
            hits = []
            for key, g in groups.items():
                if key == base or (len(base) >= 4 and key.startswith(base)) or \
                   (len(key) >= 4 and base.startswith(key)):
                    hits.append(g)
            if hits:
                running_startup.append((app, sum(h["rss"] for h in hits),
                                        sum(h["count"] for h in hits)))
        start_hdr = [sep,
                     f"  {C.BOLD}{C.BLUE}STARTUP APPS RUNNING NOW{C.RESET} "
                     f"{C.DIM}(auto-launched at boot){C.RESET}"]
        if running_startup:
            running_startup.sort(key=lambda x: x[1], reverse=True)
            idle_count = len(startup) - len(running_startup)
            for app, rss, cnt in running_startup[:6]:
                nm = app["name"]
                if len(nm) > 44:
                    nm = nm[:41] + "…"
                col = color_for(rss / max(1, vm.total) * 100, 5, 15)
                extra = f" {C.DIM}(×{cnt}){C.RESET}" if cnt > 1 else ""
                start_rows.append(f"    {nm:<44.44}  {col}{human(rss):>9}{C.RESET}{extra}")
            if idle_count > 0:
                start_rows.append(f"    {C.DIM}… plus {idle_count} more autostart entries not running now{C.RESET}")
            start_rows.append(f"    {C.DIM}↳ Trim heavy ones in 'Startup Applications' to boot faster{C.RESET}")
        else:
            start_rows.append(f"  {C.GREEN}✓ No heavyweight autostart apps are running.{C.RESET}")

    foot = [sep]
    if not tiny:
        foot.append(f"  {C.DIM}-w live view · --kill PID close app · --top N rows · Ctrl+C to exit{C.RESET}")
    foot.append("")

    def _clip(items, alloc):
        if len(items) <= alloc:
            return items[:]
        kept = items[:max(0, alloc - 1)]
        hidden = len(items) - len(kept)
        if hidden > 0:
            kept.append(f"  {C.DIM}… {hidden} more lines hidden — enlarge the window{C.RESET}")
        return kept

    fixed_cost = (len(head) + len(vitals) + len(apps_hdr) + len(warn_hdr)
                  + len(start_hdr) + len(foot))
    avail = rows - fixed_cost
    total_needed = len(app_rows) + len(alert_rows) + len(start_rows)

    if not fit or avail >= total_needed:
        show_apps, show_alerts, show_start = app_rows, alert_rows, start_rows
    else:
        avail = max(avail, 2)
        want_alerts = min(len(alert_rows), max(1, int(avail * 0.45)))
        want_apps = min(len(app_rows), max(1, int(avail * 0.35)))
        want_start = max(0, min(len(start_rows), avail - want_alerts - want_apps))
        if want_start == 0 and len(start_rows) > 0 and avail > want_alerts + want_apps:
            want_start = 1
        show_alerts = _clip(alert_rows, want_alerts)
        show_apps = _clip(app_rows, want_apps)
        if want_start > 0:
            show_start = _clip(start_rows, want_start)
        else:
            show_start = []

    parts = head + vitals + apps_hdr + show_apps + warn_hdr + show_alerts
    if show_start:
        parts += start_hdr + show_start
    parts += foot
    return "\n".join(parts), vm


NOTIFY_THRESHOLD = 90.0
NOTIFY_COOLDOWN = 300


class Notifier:
    def __init__(self):
        self.available = shutil.which("notify-send") is not None
        self.alerting = False
        self.last_sent = 0.0

    def check(self, vm, offenders):
        if not self.available:
            return
        pct = vm.percent
        if pct >= NOTIFY_THRESHOLD:
            if not self.alerting and time.monotonic() - self.last_sent > NOTIFY_COOLDOWN:
                biggest = offenders[0]["name"] if offenders else "several apps"
                body = f"{biggest} is the heaviest. Close it to free memory."
                try:
                    subprocess.run(
                        ["notify-send", "-u", "critical",
                         "RAMWATCH: Memory is critical!",
                         f"RAM at {pct:.0f}%. {body}"],
                        timeout=5,
                        check=False,
                    )
                except Exception:
                    pass
                self.last_sent = time.monotonic()
                self.alerting = True
        elif pct < NOTIFY_THRESHOLD - 5:
            self.alerting = False


def kill_pid(pid):
    try:
        p = psutil.Process(pid)
        print(f"About to close: {display_name(p.name())} (PID {pid})")
        ans = input("Are you sure? [y/N] ").strip().lower()
        if ans == "y":
            p.terminate()
            try:
                p.wait(timeout=5)
            except psutil.TimeoutExpired:
                p.kill()
            print("✓ Closed.")
        else:
            print("Cancelled.")
    except psutil.NoSuchProcess:
        print(f"No process with PID {pid}.")
    except psutil.AccessDenied:
        print("Permission denied. Try: sudo ramwatch --kill <PID>")


def main():
    ap = argparse.ArgumentParser(
        prog="ramwatch",
        description="A plain-English memory & CPU monitor. Like htop, but for humans.",
    )
    ap.add_argument("-w", "--watch", action="store_true", help="keep refreshing live")
    ap.add_argument("-i", "--interval", type=float, default=2.0, help="seconds between refreshes (watch mode)")
    ap.add_argument("-n", "--top", type=int, default=8, help="number of apps to list")
    ap.add_argument("--mem-threshold", type=float, default=20.0, help="warn when an app uses more than this %% of RAM")
    ap.add_argument("--cpu-threshold", type=float, default=50.0, help="warn when an app uses more than this %% of CPU")
    ap.add_argument("--kill", type=int, metavar="PID", help="politely close the app with this PID")
    args = ap.parse_args()

    if args.kill is not None:
        kill_pid(args.kill)
        return

    mon = Monitor(args.top, args.mem_threshold, args.cpu_threshold)
    notifier = Notifier()

    def handler(sig, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    mon._track()
    time.sleep(0.5)

    old_attrs = None
    if args.watch and sys.stdin.isatty():
        try:
            old_attrs = termios.tcgetattr(sys.stdin)
            quiet = termios.tcgetattr(sys.stdin)
            quiet[3] &= ~(termios.ECHO | termios.ICANON)
            quiet[6][termios.VMIN] = 0
            quiet[6][termios.VTIME] = 0
            termios.tcsetattr(sys.stdin, termios.TCSANOW, quiet)
        except Exception:
            old_attrs = None

    if args.watch and sys.stdout.isatty():
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()

    offset = [0]
    running = [True]

    def read_keys():
        try:
            buf = b""
            while select.select([sys.stdin], [], [], 0)[0]:
                chunk = os.read(sys.stdin.fileno(), 256)
                if not chunk:
                    break
                buf += chunk
        except Exception:
            return
        s = buf.decode("utf-8", errors="ignore")
        i = 0
        while i < len(s):
            if s.startswith("\x1b[A", i):
                offset[0] -= 1
                i += 3
            elif s.startswith("\x1b[B", i):
                offset[0] += 1
                i += 3
            elif s.startswith("\x1b[5~", i):
                offset[0] -= 10
                i += 4
            elif s.startswith("\x1b[6~", i):
                offset[0] += 10
                i += 4
            elif s[i] == "q":
                running[0] = False
                i += 1
            elif s.startswith("\x1b[H", i):
                offset[0] = 0
                i += 3
            else:
                i += 1

    try:
        cached_lines = None
        last_refresh = 0.0
        painted_offset = -1
        while running[0]:
            read_keys()
            now = time.monotonic()
            if now - last_refresh >= args.interval or cached_lines is None:
                out, vm = render(mon, fit=not args.watch)
                if args.watch:
                    notifier.check(vm, [])
                    psutil.cpu_percent(None)
                    mon._track()
                    mon.prev_net = psutil.net_io_counters()
                    mon.prev_net_t = time.monotonic()
                    cached_lines = out.split("\n")
                    last_refresh = now
                else:
                    print(out)
                    break
            if not args.watch:
                time.sleep(0.05)
                continue
            tsz = shutil.get_terminal_size((78, 24))
            vis = max(5, tsz.lines - 1)
            max_off = max(0, len(cached_lines) - vis)
            offset[0] = max(0, min(offset[0], max_off))
            if offset[0] != painted_offset or now - last_refresh < 0.06:
                view = cached_lines[offset[0]:offset[0] + vis]
                while len(view) < vis:
                    view.append("")
                pos_lo = min(offset[0] + 1, len(cached_lines))
                pos_hi = min(offset[0] + vis, len(cached_lines))
                hint = (f" {C.DIM}↑↓ scroll · PgUp/PgDn jump · showing "
                        f"{pos_lo}-{pos_hi} of {len(cached_lines)} · q quit{C.RESET}")
                sys.stdout.write("\033[H\033[2J" + "\n".join(view) + "\n" + hint)
                sys.stdout.flush()
                painted_offset = offset[0]
            time.sleep(0.05)
    finally:
        if args.watch and sys.stdout.isatty():
            sys.stdout.write("\033[?1049l\033[?25h")
            sys.stdout.flush()
        if old_attrs is not None:
            try:
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
                termios.tcsetattr(sys.stdin, termios.TCSANOW, old_attrs)
            except Exception:
                pass
        if args.watch:
            print("\nBye! 👋")


if __name__ == "__main__":
    main()
