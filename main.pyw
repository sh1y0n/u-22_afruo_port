import subprocess
import sys
import re
import json
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from datetime import datetime

PORT_MIN = 1
PORT_MAX = 65535


class PortGuardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Port Guard")
        self.root.geometry("520x560")
        self.root.minsize(520, 420)
        self.root.resizable(True, True)

        self.dark_mode = self._detect_windows_theme()
        self.opened_ports_set = set()

        self._build_ui()
        self._apply_theme()
        
        try:
            self.root.after(100, self._check_registered_presets)
            self.root.after(5000, self._schedule_periodic_check)
        except Exception:
            pass

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        except Exception:
            pass

    def _build_ui(self):
        self.root.configure(bg="#1e1e1e")

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="ポート管理ツール", font=("Yu Gothic", 16, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        ttk.Label(main, text="用途を選ぶ").pack(anchor="w")
        self.presets_file = "presets.json"
        self._load_presets()
        self.preset_names = [p["name"] for p in self.presets]
        self.preset_var = tk.StringVar(value=self.preset_names[0] if self.preset_names else "")
        combo_frame = ttk.Frame(main)
        combo_frame.pack(fill="x", pady=(0, 10))
        self.preset_combo = ttk.Combobox(
            combo_frame,
            textvariable=self.preset_var,
            state="readonly",
            values=self.preset_names,
        )
        self.preset_combo.pack(side="left", fill="x", expand=True)
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        
        btn_frame = ttk.Frame(combo_frame)
        btn_frame.pack(side="left", padx=(6, 0))
        ttk.Button(btn_frame, text="追加", width=6, command=self._add_preset).pack(side="top", pady=0)
        ttk.Button(btn_frame, text="編集", width=6, command=self._edit_preset).pack(side="top", pady=(4,0))
        ttk.Button(btn_frame, text="削除", width=6, command=self._delete_preset).pack(side="top", pady=(4,0))

        ttk.Label(main, text="ポート番号").pack(anchor="w")
        self.port_var = tk.StringVar(value="25565")
        self.port_entry = ttk.Entry(main, textvariable=self.port_var)
        self.port_entry.pack(fill="x", pady=(0, 10))

        proto_frame = ttk.Frame(main)
        proto_frame.pack(fill="x", pady=(0, 10))
        self.tcp_var = tk.IntVar(value=1)
        self.udp_var = tk.IntVar(value=0)
        ttk.Checkbutton(proto_frame, text="TCP", variable=self.tcp_var).pack(side="left", padx=(0,8))
        ttk.Checkbutton(proto_frame, text="UDP", variable=self.udp_var).pack(side="left")

        ttk.Label(main, text="警告する時間（時間）").pack(anchor="w")
        self.warning_var = tk.StringVar(value="2")
        self.warning_entry = ttk.Entry(main, textvariable=self.warning_var)
        self.warning_entry.pack(fill="x", pady=(0, 10))

        button_frame = ttk.Frame(main)
        button_frame.pack(fill="x", pady=(6, 12))

        ttk.Button(button_frame, text="開く", command=self._open_port, style="Custom.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="閉じる", command=self._close_port, style="Custom.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(button_frame, text="すべて閉じる", command=self._close_all_open_ports, style="Custom.TButton").pack(side="left")

        ttk.Button(main, text="確認", command=self._check_registered_presets, style="Custom.TButton").pack(anchor="w", pady=(0, 10))

        self.check_results_var = tk.StringVar(value="確認ボタンを押すか、自動チェックを待つと状態を表示します。")
        ttk.Label(main, text="確認結果", font=(None, 10, "bold")).pack(anchor="w")
        ttk.Label(main, textvariable=self.check_results_var, foreground="#4fc3f7", wraplength=480, justify="left").pack(anchor="w", pady=(4, 10))

        ttk.Label(main, text="※ Windowsのファイアウォール設定を変更するため、管理者権限で実行してください。", wraplength=480, justify="left").pack(anchor="w", pady=(0, 0))

    def _apply_theme(self):
        if self.dark_mode:
            self.root.configure(bg="#242424")
            self._set_style("#242424", "#ffffff", "#3a3a3a", "#4fc3f7")
        else:
            self.root.configure(bg="#f5f5f5")
            self._set_style("#f5f5f5", "#222222", "#e0e0e0", "#1976d2")

    def _detect_windows_theme(self):
        if sys.platform != "win32":
            return True
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return True

    def _set_style(self, bg, fg, border, accent):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Custom.TButton", background=border, foreground=fg, padding=6, relief="flat")
        style.configure("TEntry", fieldbackground="#ffffff", foreground="#222222")
        style.map(
            "Custom.TButton",
            background=[("active", accent), ("!disabled", border)],
            foreground=[("active", "#ffffff"), ("!disabled", fg)],
        )

    def _on_preset_selected(self, event=None):
        name = self.preset_var.get()
        for p in self.presets:
            if p["name"] == name:
                self.port_var.set(str(p.get("port", "")))
                return
        self.port_var.set("")

    def _selected_protocols(self):
        protos = []
        if getattr(self, 'tcp_var', None) and self.tcp_var.get():
            protos.append('TCP')
        if getattr(self, 'udp_var', None) and self.udp_var.get():
            protos.append('UDP')
        return protos

    def _ensure_protocol_selected(self):
        protos = self._selected_protocols()
        if not protos:
            messagebox.showwarning("入力エラー", "TCP または UDP のいずれかを選択してください。", parent=self.root)
        return protos

    def _load_presets(self):
        try:
            with open(self.presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.presets = [{"name": str(x.get("name", "")), "port": str(x.get("port", ""))} for x in data]
                else:
                    self.presets = []
        except Exception:
            self.presets = [{"name": "Minecraft", "port": "25565"}, {"name": "ARK", "port": "7778"}]

    def _validate_port(self, port_text, show_error=False):
        if not isinstance(port_text, str):
            port_text = str(port_text or "")
        port_text = port_text.strip()
        if not port_text.isdigit():
            if show_error:
                messagebox.showwarning("入力エラー", "有効なポート番号を入力してください。", parent=self.root)
            return ""
        port = int(port_text)
        if port < PORT_MIN or port > PORT_MAX:
            if show_error:
                messagebox.showwarning("入力エラー", f"ポート番号は {PORT_MIN} から {PORT_MAX} までです。", parent=self.root)
            return ""
        return str(port)

    def _save_presets(self):
        try:
            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._log(f"PRESETS_SAVE_ERROR: {exc}")

    def _add_preset(self):
        name = simpledialog.askstring("プリセット追加", "プリセット名を入力してください:", parent=self.root)
        if not name:
            return
        port = simpledialog.askstring("プリセット追加", "ポート番号を入力してください:", parent=self.root)
        port = self._validate_port(port, show_error=True)
        if not port:
            return
        self.presets.append({"name": name, "port": port})
        self._save_presets()
        self._refresh_presets_ui(name)

    def _edit_preset(self):
        name = self.preset_var.get()
        for i, p in enumerate(self.presets):
            if p["name"] == name:
                new_name = simpledialog.askstring("プリセット編集", "プリセット名:", initialvalue=p["name"], parent=self.root)
                if not new_name:
                    return
                new_port = simpledialog.askstring("プリセット編集", "ポート番号:", initialvalue=str(p.get("port", "")), parent=self.root)
                new_port = self._validate_port(new_port, show_error=True)
                if not new_port:
                    return
                self.presets[i] = {"name": new_name, "port": new_port}
                self._save_presets()
                self._refresh_presets_ui(new_name)
                return

    def _delete_preset(self):
        name = self.preset_var.get()
        idx = None
        for i, p in enumerate(self.presets):
            if p["name"] == name:
                idx = i
                break
        if idx is None:
            return
        if not messagebox.askyesno("削除確認", f"プリセット '{name}' を削除しますか?", parent=self.root):
            return
        del self.presets[idx]
        self._save_presets()
        self._refresh_presets_ui()

    def _refresh_presets_ui(self, selected_name=None):
        self.preset_names = [p["name"] for p in self.presets]
        try:
            self.preset_combo.configure(values=self.preset_names)
            if self.preset_names:
                if selected_name and selected_name in self.preset_names:
                    self.preset_var.set(selected_name)
                else:
                    self.preset_var.set(self.preset_names[0])
                self._on_preset_selected()
            else:
                self.preset_var.set("")
        except Exception:
            pass

    def _scan_firewall_rules(self):
        if sys.platform != "win32":
            return set()
        try:
            # 点滅対策のために creationflags を追加
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = (result.stdout or "") + (result.stderr or "")
        except Exception:
            return set()

        found = set()
        for raw_line in output.splitlines():
            line = raw_line.strip().replace('：', ':')
            if not line:
                continue
            name_match = re.search(r'(?:Rule Name|規則名)\s*[：:]\s*PortGuard-(TCP|UDP)-(\d+)', line, re.I)
            if name_match:
                proto = name_match.group(1).upper()
                port = name_match.group(2)
                found.add(f"{proto}:{port}")
        return found

    def _sync_firewall_rules(self):
        self.opened_ports_set = self._scan_firewall_rules()

    def _check_registered_presets(self):
        if sys.platform != "win32":
            return
        if not self.presets:
            try: self.check_results_var.set("登録済みのプリセットがありません。")
            except Exception: pass
            return

        lines = []
        for preset in self.presets:
            name = preset.get("name", "")
            port = str(preset.get("port", ""))
            if not port.isdigit():
                lines.append(f"{name} ({port}) : 無効なポート番号")
                continue

            tcp_open = self._rule_exists(self._rule_name(port, 'TCP'))
            udp_open = self._rule_exists(self._rule_name(port, 'UDP'))
            if tcp_open and udp_open:
                lines.append(f"{name} ({port}) : TCP/UDP 両方開放中")
            elif tcp_open:
                lines.append(f"{name} ({port}) : TCP のみ開放中")
            elif udp_open:
                lines.append(f"{name} ({port}) : UDP のみ開放中")
            else:
                lines.append(f"{name} ({port}) : 開放されていません")

        try:
            self.check_results_var.set("\n".join(lines))
        except Exception:
            pass

    def _rule_exists(self, rule_name: str) -> bool:
        if sys.platform != "win32":
            return False
        try:
            # 点滅対策のために creationflags を追加
            res = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            raw = (res.stdout or "") + (res.stderr or "")
            if re.search(r'指定された条件に一致する規則はありません', raw) or re.search(r'no rules match', raw, re.I):
                return False
            return True
        except Exception:
            return False

    def _log(self, msg: str):
        try:
            with open("portguard.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {msg}\n")
        except Exception:
            pass

    def _open_port(self):
        if sys.platform != "win32":
            messagebox.showerror("エラー", "このアプリはWindows向けです。")
            return

        port = self._get_port()
        if not port:
            messagebox.showwarning("入力エラー", "ポート番号を入力してください。", parent=self.root)
            return

        try:
            protos = self._ensure_protocol_selected()
            if not protos:
                return
            failures = []
            successes = []
            for proto in protos:
                rule_name = self._rule_name(port, proto)
                if self._rule_exists(rule_name):
                    successes.append(proto)
                    continue
                # 点滅対策のために creationflags を追加
                res = subprocess.run(
                    [
                        "netsh", "advfirewall", "firewall", "add", "rule",
                        f"name={rule_name}", "dir=in", "action=allow",
                        f"protocol={proto}", f"localport={port}", "profile=any",
                    ],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self._log(f"OPEN netsh add rule name={rule_name} -> returncode={res.returncode}")
                if res.returncode != 0:
                    raw = (res.stdout or "") + (res.stderr or "")
                    failures.append((proto, raw.strip()))
                else:
                    self.opened_ports_set.add(self._proto_port_key(proto, port))
                    successes.append(proto)

            if failures and not successes:
                messagebox.showerror("開放失敗", f"ルール作成に失敗しました。管理者権限を確認してください。\n詳細: {failures}")
            elif failures and successes:
                messagebox.showwarning("部分的成功", f"一部のプロトコルは開放に失敗しました: {failures}\n成功: {successes}")
            else:
                messagebox.showinfo("完了", f"ポート {port} を開きました。プロトコル: {', '.join(successes)}")
        except Exception as exc:
            messagebox.showerror("開放失敗", f"ポートの開放に失敗しました: {exc}")
        finally:
            self._sync_firewall_rules()
            self._check_registered_presets()

    def _close_port(self):
        if sys.platform != "win32":
            messagebox.showerror("エラー", "このアプリはWindows向けです。")
            return

        port = self._get_port()
        if not port:
            messagebox.showwarning("入力エラー", "ポート番号を入力してください。", parent=self.root)
            return

        try:
            protos = self._ensure_protocol_selected()
            if not protos:
                return
            failures = []
            successes = []
            no_match = []
            for proto in protos:
                rule_name = self._rule_name(port, proto)
                # 点滅対策のために creationflags を追加
                res = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self._log(f"CLOSE netsh delete rule name={rule_name} -> returncode={res.returncode}")
                raw = (res.stdout or "") + (res.stderr or "")
                
                if res.returncode != 0:
                    if re.search(r'no rules match', raw, re.I) or '指定された条件に一致する規則はありません' in raw:
                        self.opened_ports_set.discard(self._proto_port_key(proto, port))
                        no_match.append(proto)
                    else:
                        failures.append((proto, raw.strip()))
                else:
                    self.opened_ports_set.discard(self._proto_port_key(proto, port))
                    successes.append(proto)

            if failures and not successes and not no_match:
                messagebox.showerror("閉鎖失敗", f"ルールの削除に失敗しました: {failures}")
            elif not successes and no_match:
                messagebox.showinfo("情報", f"ポート {port} は指定したプロトコル ({', '.join(no_match)}) で開いていませんでした。")
            elif failures:
                messagebox.showwarning("部分的成功", f"一部の閉鎖に失敗しました: {failures}\n成功: {', '.join(successes)}")
            else:
                messagebox.showinfo("完了", f"ポート {port} を閉じました。")
        except Exception as exc:
            messagebox.showerror("閉鎖失敗", f"ポートの閉鎖に失敗しました: {exc}")
        finally:
            self._sync_firewall_rules()
            self._check_registered_presets()

    def _close_all_open_ports(self):
        open_ports = sorted(self._scan_firewall_rules())
        verified_open_ports = []
        for p in open_ports:
            if ':' in p:
                proto, port_num = p.split(':', 1)
                if self._rule_exists(self._rule_name(port_num, proto)):
                    verified_open_ports.append(p)

        if not verified_open_ports:
            messagebox.showinfo("情報", "現在、閉じるべき開放中のポートはありません。")
            return

        for port_key in verified_open_ports:
            try:
                self._close_port_silent(port_key)
            except Exception as exc:
                self._log(f"ERROR_CLOSE_ALL {port_key}: {exc}")

        self._sync_firewall_rules()
        still_open = sorted(self._scan_firewall_rules())
        if still_open:
            messagebox.showwarning("部分的完了", f"いくつかのポートは閉じられませんでした:\n" + "\n".join(['・' + p.replace(':', ' ') for p in still_open]))
        else:
            messagebox.showinfo("完了", "すべての開いているポートを閉じました。")
        self._check_registered_presets()

    def _on_close_attempt(self):
        opened = sorted(self._scan_firewall_rules())
        if opened:
            if len(opened) >= 2:
                try: self.root.attributes("-topmost", True)
                except Exception: pass
                try:
                    action, selected = self._multi_close_dialog(opened)
                finally:
                    try: self.root.attributes("-topmost", False)
                    except Exception: pass

                if action in ("all", "leave", "select"):
                    if action == "all":
                        for p in opened: self._close_port_silent(p)
                    elif action == "select":
                        for p in selected: self._close_port_silent(p)
                    self.root.destroy()
                return

            try: self.root.attributes("-topmost", True)
            except Exception: pass
            try:
                bullets = "\n".join([f"・{p}" for p in opened])
                msg = f"次のポートが開放されたままです:\n\n{bullets}\n\n安全のため、これらを閉じて終了しますか?\n\n[はい]：すべて閉じて終了\n[いいえ]：開けたまま終了\n[キャンセル]：終了を中止"
                choice = messagebox.askyesnocancel("終了確認", msg, parent=self.root)
            finally:
                try: self.root.attributes("-topmost", False)
                except Exception: pass

            if choice is True:
                for p in opened: self._close_port_silent(p)
                self.root.destroy()
            elif choice is False:
                self.root.destroy()
        else:
            self.root.destroy()

    def _close_port_silent(self, port=None):
        if port is None:
            target_port = self._get_port()
            if not target_port: return
            entries = [(proto, target_port) for proto in self._selected_protocols()]
        else:
            if isinstance(port, str) and ':' in port:
                proto, p = port.split(':', 1)
                entries = [(proto, p)]
            else:
                entries = [(proto, port) for proto in self._selected_protocols()]

        for proto, p in entries:
            try:
                rule_name = self._rule_name(p, proto)
                # 点滅対策のために creationflags を追加
                res = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                raw = (res.stdout or "") + (res.stderr or "")
                if res.returncode == 0 or re.search(r'no rules match', raw, re.I) or '指定された条件に一致する規則はありません' in raw:
                    self.opened_ports_set.discard(self._proto_port_key(proto, p))
            except Exception as exc:
                self._log(f"SILENT_CLOSE_EXCEPTION: {exc}")

    def _multi_close_dialog(self, opened_ports):
        dlg = tk.Toplevel(self.root)
        dlg.title("終了時のポート操作")
        dlg.transient(self.root)
        dlg.grab_set()
        
        lbl = ttk.Label(dlg, text="次のポートが開放されたままです:")
        lbl.pack(anchor="w", padx=12, pady=(12, 6))
        cb_frame = ttk.Frame(dlg)
        cb_frame.pack(fill="both", expand=True, padx=12)

        vars_map = {}
        for p in opened_ports:
            v = tk.IntVar(value=0)
            cb = ttk.Checkbutton(cb_frame, text=str(p), variable=v)
            cb.pack(anchor="w", pady=2)
            vars_map[p] = v

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill="x", pady=12, padx=12)
        result = {"action": None, "selected": []}

        def do_all():
            result["action"] = "all"
            dlg.destroy()

        def do_select():
            sel = [p for p, var in vars_map.items() if var.get()]
            if not sel:
                messagebox.showwarning("選択なし", "閉じたいポートを選択してください。", parent=dlg)
                return
            result["action"] = "select"
            result["selected"] = sel
            dlg.destroy()

        def do_leave():
            result["action"] = "leave"
            dlg.destroy()

        def do_cancel():
            result["action"] = "cancel"
            dlg.destroy()

        ttk.Button(btn_frame, text="すべて閉じて終了", command=do_all).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="選択して閉じる", command=do_select).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="開けたまま終了", command=do_leave).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="キャンセル", command=do_cancel).pack(side="right", padx=4)

        dlg.update_idletasks()
        x = self.root.winfo_rootx() + 40
        y = self.root.winfo_rooty() + 40
        dlg.geometry(f'+{x}+{y}')
        self.root.wait_window(dlg)
        return result.get("action"), result.get("selected", [])

    def _get_port(self, show_error=False):
        return self._validate_port(self.port_var.get(), show_error=show_error)

    def _proto_port_key(self, proto, port):
        return f"{proto}:{port}"

    def _rule_name(self, port, proto='TCP'):
        return f"PortGuard-{proto}-{port}"

    def _schedule_periodic_check(self):
        try:
            self._check_registered_presets()
        except Exception:
            pass
        try:
            self.root.after(5000, self._schedule_scheduler)
        except Exception:
            pass

    def _schedule_scheduler(self):
        self._schedule_periodic_check()


if __name__ == "__main__":
    root = tk.Tk()
    app = PortGuardApp(root)
    root.mainloop()