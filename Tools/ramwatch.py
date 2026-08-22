#!/usr/bin/env python3
import argparse
import os
import shutil
import signal
import sys
import time

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
    "winbindd": "A background service stuck. A reboot usually clears it.",
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


def display_name(name):
    key = name.lower()
    base = FRIENDLY_NAMES.get(key)
    if base:
        return f"{base} ({name})"
    return name


class Monitor:
    def __init__(self, top_n, mem_thr, cpu_thr):
        self.top_n = top_n
        self.mem_thr = mem_thr
        self.cpu_thr = cpu_thr
        self.ncores = psutil.cpu_count(logical=True) or 1
        self.procs = {}

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

    def collect(self):
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        cpu_pct = psutil.cpu_percent(interval=None)

        groups = {}
        for pid, p in self.procs.items():
            try:
                info = p.info
            except psutil.Error:
                continue
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

        top = sorted(groups.values(), key=lambda g: g["rss"], reverse=True)
        offenders = [g for g in top if g["mem"] >= self.mem_thr or g["cpu"] >= self.cpu_thr]
        return vm, sm, cpu_pct, top[: self.top_n], offenders


def render(mon, width=78):
    vm, sm, cpu, top, offenders = mon.collect()
    lines = []
    w = min(width, shutil.get_terminal_size((78, 24)).columns)

    lines.append("")
    lines.append(f"  {C.BOLD}RAMWATCH{C.RESET} {C.DIM}· plain-English task manager ·{C.RESET} "
                 f"{time.strftime('%a %d %b %Y %H:%M:%S')}")
    lines.append(f"  {'─' * (w - 4)}")

    mem_pct = vm.percent
    status, bad = ram_status(mem_pct)
    lines.append(f"  {C.BOLD}MEMORY {bar(mem_pct)} {color_for(mem_pct)}{mem_pct:5.1f}%{C.RESET}"
                 f"   {human(vm.used)} of {human(vm.total)} used")
    lines.append(f"         {status}  {C.DIM}· free: {human(vm.available)}{C.RESET}")

    swap_pct = sm.percent
    s_status, s_bad = swap_status(swap_pct)
    lines.append(f"  {C.BOLD}SWAP   {bar(swap_pct)} {color_for(swap_pct, 50, 80)}{swap_pct:5.1f}%{C.RESET}"
                 f"   {human(sm.used)} of {human(sm.total)} used")
    lines.append(f"         {s_status}")

    c_status, c_bad = cpu_status(cpu)
    lines.append(f"  {C.BOLD}CPU    {bar(cpu)} {color_for(cpu)}{cpu:5.1f}%{C.RESET}"
                 f"   across {mon.ncores} cores")
    lines.append(f"         {c_status}")

    lines.append(f"  {'─' * (w - 4)}")
    lines.append(f"  {C.BOLD}{C.CYAN}TOP APPS{C.RESET} {C.DIM}(same app counted once, all its windows combined){C.RESET}")
    lines.append(f"  {C.DIM}{'APP':<38}{'×N':>4}  {'RAM':>9}  {'%MEM':>6}  {'%CPU':>6}{C.RESET}")

    if not top:
        lines.append(f"  {C.DIM}no readable processes{C.RESET}")
    for g in top:
        nm = g["name"]
        label = display_name(nm)
        if len(label) > 37:
            label = label[:34] + "…"
        mcol = color_for(g["mem"], mon.mem_thr, 60)
        ccol = color_for(g["cpu"], mon.cpu_thr, 85)
        cnt = str(g["count"]) + ("s" if g["count"] > 1 else "")
        lines.append(
            f"  {label:<38.38}{C.DIM}×{cnt:<2}{C.RESET}  {human(g['rss']):>9}"
            f"  {mcol}{g['mem']:5.1f}%{C.RESET}  {ccol}{g['cpu']:5.1f}%{C.RESET}"
        )

    lines.append(f"  {'─' * (w - 4)}")
    lines.append(f"  {C.BOLD}{C.MAGENTA}⚠ NEEDS YOUR ATTENTION{C.RESET}")

    alerts = []
    if bad and mem_pct >= 92:
        alerts.append("Your memory is nearly FULL. Close the biggest apps listed above.")
    elif bad:
        alerts.append("Memory usage is high. If things feel slow, close the biggest apps.")
    if s_bad:
        alerts.append("Swap is heavily used — your PC is borrowing disk as RAM. Free memory by closing apps.")
    if c_bad:
        alerts.append("CPU is maxed out — a program is working very hard (see %CPU column).")

    for g in offenders[:5]:
        tip = TIPS.get(g["name"].lower())
        msg = (f"{display_name(g['name'])} is using "
               f"{human(g['rss'])} ({g['mem']:.0f}% of RAM)")
        if g["count"] > 1:
            msg += f" across {g['count']} processes"
        msg += "."
        alerts.append(msg)
        if tip:
            alerts.append(f"↳ Tip: {tip}")
        alerts.append(f"↳ Closing it frees about {human(g['rss'])}. Kill it later with: ramwatch --kill <PID>")

    if not alerts:
        lines.append(f"  {C.GREEN}✓ All good — nothing needs your attention.{C.RESET}")
    else:
        for i, a in enumerate(alerts):
            prefix = "• " if not a.startswith("↳") else "  "
            col = "" if a.startswith("↳") else C.YELLOW
            lines.append(f"  {prefix}{col}{a}{C.RESET}")

    lines.append(f"  {'─' * (w - 4)}")
    lines.append(f"  {C.DIM}-w live view · --kill PID close app · --top N rows · Ctrl+C to exit{C.RESET}")
    lines.append("")
    return "\n".join(lines)


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
            print(f"✓ Closed.")
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

    def handler(sig, frame):
        print("\nBye! 👋")
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)

    mon._track()
    time.sleep(0.5)

    first = True
    while True:
        out = render(mon)
        if args.watch:
            if not first:
                sys.stdout.write("\033[H\033[J")
            first = False
            print(out)
            psutil.cpu_percent(None)
            mon._track()
            time.sleep(args.interval)
        else:
            print(out)
            break


if __name__ == "__main__":
    main()
