"""台灣統一發票線上對獎工具。僅使用 Python 標準函式庫。"""
from __future__ import annotations

import html
import re
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
from html.parser import HTMLParser

OFFICIAL_HOME = "https://invoice.etax.nat.gov.tw/"
OFFICIAL_PERIOD = "https://www.etax.nat.gov.tw/etw-main/ETW183W2_{term}/"
PRIZES = [("特別獎", 10_000_000), ("特獎", 2_000_000), ("頭獎", 200_000),
          ("二獎", 40_000), ("三獎", 10_000), ("四獎", 4_000),
          ("五獎", 1_000), ("六獎", 200)]


def resource_path(relative_path: str) -> str:
    """Resolve bundled assets in both source and PyInstaller one-file builds."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; InvoicePrizeChecker/1.0)"})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def parse_periods(page: str):
    """取回官方頁面列出的期別。"""
    found = set(re.findall(r"(?:ETW183W2_|invoYm[=/])([0-9]{3}(?:0[2-9]|1[02]))", page, re.I))
    # 官方首頁的純文字期別如「115年05-06月」
    for year, month in re.findall(r"([0-9]{3})年\s*([0-9]{2})\s*[-~－]\s*[0-9]{2}\s*月", page):
        found.add(year + month)
    return sorted(found, reverse=True)


def parse_numbers(page: str):
    parser = TextParser()
    parser.feed(page)
    text = " ".join(parser.parts)
    # 頁面可能以獎別欄位呈現；取每個獎別標籤後第一個八位號碼。
    def get(label):
        m = re.search(label + r"\s*([0-9]{8})", text)
        return m.group(1) if m else ""
    first = []
    m = re.search(r"頭獎\s*((?:[0-9]{8}\s*){1,10})", text)
    if m:
        first = re.findall(r"[0-9]{8}", m.group(1))
    sixth = []
    m = re.search(r"增開六獎\s*((?:[0-9]{3}\s*){1,10})", text)
    if m:
        sixth = re.findall(r"[0-9]{3}", m.group(1))
    data = {"special": get(r"特別獎"), "grand": get(r"特獎"), "first": first, "sixth": sixth}
    if not data["special"] or not data["grand"] or not data["first"]:
        raise ValueError("官方頁面格式無法辨識，請稍後重試或查看財政部網站。")
    return data


def prize_for(number: str, data):
    """3 碼僅能判六獎；8 碼按官方規則回報單張最高獎。"""
    if len(number) == 3:
        if number in data["sixth"] or any(n.endswith(number) for n in data["first"]):
            return "六獎", 200
        return "未中獎", 0
    if number == data["special"]:
        return "特別獎", 10_000_000
    if number == data["grand"]:
        return "特獎", 2_000_000
    for digits, title, amount in [(8, "頭獎", 200_000), (7, "二獎", 40_000),
                                  (6, "三獎", 10_000), (5, "四獎", 4_000),
                                  (4, "五獎", 1_000), (3, "六獎", 200)]:
        if any(number[-digits:] == n[-digits:] for n in data["first"]):
            return title, amount
    if number[-3:] in data["sixth"]:
        return "六獎", 200
    return "未中獎", 0


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("統一發票線上對獎")
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "invoice_prize_icon.ico")))
        except tk.TclError:
            pass
        self.geometry("930x700")
        self.minsize(760, 580)
        self.configure(bg="#f4f6fa")
        self.period_data = {}
        self.records = []
        self.periods = []
        self._build()
        self.status.set("正在連線財政部取得開獎期別…")
        self.after(100, self.load_periods)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", padding=7, font=("Microsoft JhengHei UI", 11))
        style.configure("Treeview", rowheight=34, font=("Microsoft JhengHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft JhengHei UI", 10, "bold"))
        header = tk.Frame(self, bg="#173b62", padx=28, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="統一發票對獎", font=("Microsoft JhengHei UI", 23, "bold"),
                 fg="white", bg="#173b62").pack(anchor="w")
        tk.Label(header, text="連線財政部官方開獎資訊 · 每張發票只計最高獎項", font=("Microsoft JhengHei UI", 10),
                 fg="#c6d8ea", bg="#173b62").pack(anchor="w", pady=(4, 0))
        body = tk.Frame(self, bg="#f4f6fa", padx=28, pady=20)
        body.pack(fill="both", expand=True)
        controls = tk.Frame(body, bg="white", padx=18, pady=16)
        controls.pack(fill="x")
        tk.Label(controls, text="開獎期別", bg="white", font=("Microsoft JhengHei UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.period = tk.StringVar()
        self.combo = ttk.Combobox(controls, textvariable=self.period, state="readonly", width=20)
        self.combo.grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.combo.bind("<<ComboboxSelected>>", self.on_period_change)
        tk.Label(controls, text="輸入發票末 3 碼（或完整 8 碼）", bg="white", font=("Microsoft JhengHei UI", 10, "bold")).grid(row=0, column=1, sticky="w", padx=(24, 0))
        self.entry = ttk.Entry(controls, font=("Consolas", 15), width=22)
        self.entry.grid(row=1, column=1, sticky="w", padx=(24, 0), pady=(5, 0))
        self.entry.bind("<Return>", lambda _e: self.check())
        self.check_btn = tk.Button(controls, text="對獎並記錄", command=self.check, bg="#1570c8", fg="white",
                                   activebackground="#0f5da8", activeforeground="white", relief="flat",
                                   padx=20, pady=9, font=("Microsoft JhengHei UI", 10, "bold"), cursor="hand2")
        self.check_btn.grid(row=1, column=2, padx=(18, 0), sticky="w")
        self.status = tk.StringVar(value="初始化…")
        tk.Label(body, textvariable=self.status, bg="#f4f6fa", fg="#536577", anchor="w",
                 font=("Microsoft JhengHei UI", 9)).pack(fill="x", pady=(9, 12))
        tk.Label(body, text="本次對獎紀錄", bg="#f4f6fa", fg="#173b62", font=("Microsoft JhengHei UI", 14, "bold")).pack(anchor="w", pady=(0, 9))
        cols = ("period", "number", "prize", "amount")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
        for col, label, width in [("period", "期別", 140), ("number", "發票號碼", 180), ("prize", "獎項", 180), ("amount", "獎金", 160)]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)
        bottom = tk.Frame(body, bg="#f4f6fa")
        bottom.pack(fill="x", pady=(13, 0))
        self.total_label = tk.Label(bottom, text="累計獎金　NT$ 0", bg="#f4f6fa", fg="#14734c",
                                    font=("Microsoft JhengHei UI", 17, "bold"))
        self.total_label.pack(side="left")
        tk.Button(bottom, text="清除紀錄", command=self.clear_records, bg="#e8edf3", fg="#34485c", relief="flat",
                  padx=14, pady=7, font=("Microsoft JhengHei UI", 9), cursor="hand2").pack(side="right")
        tk.Label(body, text="對獎結果僅依中獎號碼判定；領獎資格、期限及應納稅費請依財政部公告。",
                 bg="#f4f6fa", fg="#778493", font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(12, 0))

    def load_periods(self):
        def worker():
            try:
                page = fetch_text(OFFICIAL_HOME)
                periods = parse_periods(page)
                # 官方首頁有最新開獎月份；額外逐期查前兩期頁面以保證三期可選。
                if not periods:
                    raise ValueError("財政部首頁沒有提供可辨識的期別。")
                latest = periods[0]
                y, m = int(latest[:3]), int(latest[3:])
                available = []
                for _ in range(3):
                    available.append(f"{y:03d}{m:02d}")
                    if m == 2:
                        y, m = y - 1, 12
                    else:
                        m -= 2
                self.after(0, lambda: self.set_periods(available))
            except Exception as exc:
                self.after(0, lambda: self.fetch_error(str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def set_periods(self, periods):
        self.periods = periods
        self.combo["values"] = [self.format_period(x) for x in periods]
        self.combo.current(0)
        self.load_selected()

    @staticmethod
    def format_period(term):
        y, m = int(term[:3]), int(term[3:])
        return f"{y}年{m:02d}-{m+1:02d}月"

    def on_period_change(self, _event=None):
        self.load_selected()

    def load_selected(self):
        index = self.combo.current()
        if index < 0 or not self.periods:
            return
        term = self.periods[index]
        if term in self.period_data:
            self.status.set(f"已載入 {self.format_period(term)} 財政部開獎號碼（線上資料）")
            return
        self.status.set(f"正在連線財政部載入 {self.format_period(term)}…")
        self.check_btn.configure(state="disabled")
        def worker():
            try:
                page = fetch_text(OFFICIAL_PERIOD.format(term=term))
                data = parse_numbers(page)
                self.after(0, lambda: self.set_data(term, data))
            except Exception as exc:
                self.after(0, lambda: self.fetch_error(str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def set_data(self, term, data):
        self.period_data[term] = data
        self.status.set(f"已連線並載入 {self.format_period(term)} 財政部開獎號碼")
        self.check_btn.configure(state="normal")

    def fetch_error(self, error):
        self.check_btn.configure(state="disabled")
        self.status.set("無法取得官方資料；請確認網路連線後重新選擇期別。")
        messagebox.showerror("連線失敗", f"無法從財政部取得開獎資料。\n\n{error}\n\n本程式需連網才能使用。")

    def check(self):
        raw = self.entry.get().strip()
        number = re.sub(r"\s+", "", raw)
        if not re.fullmatch(r"\d{3}|\d{8}", number):
            messagebox.showwarning("號碼格式", "請輸入 3 碼或完整 8 碼數字。")
            self.entry.focus_set()
            return
        index = self.combo.current()
        if index < 0:
            messagebox.showwarning("尚未載入", "請先連線載入開獎期別。")
            return
        term = self.periods[index]
        data = self.period_data.get(term)
        if not data:
            messagebox.showwarning("尚未載入", "這一期的開獎號碼尚未載入完成，請稍候。")
            return
        checked_number = number
        jackpot_suffixes = {data["special"][-3:], data["grand"][-3:]}
        jackpot_suffixes.update(n[-3:] for n in data["first"])
        if len(number) == 3 and number in jackpot_suffixes:
            completed = self.ask_full_number(number)
            if completed is None:
                return
            checked_number = completed

        prize, amount = prize_for(checked_number, data)
        self.tree.insert("", "end", values=(self.format_period(term), checked_number, prize, f"NT$ {amount:,}"))
        self.records.append(amount)
        total = sum(self.records)
        self.total_label.configure(text=f"累計獎金　NT$ {total:,}")
        self.entry.delete(0, "end")
        self.entry.focus_set()

    def ask_full_number(self, suffix):
        dialog = tk.Toplevel(self)
        dialog.title("輸入完整發票號碼")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        result = {"number": None}
        frame = tk.Frame(dialog, padx=22, pady=18)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=f"末三碼 {suffix} 符合頭獎、特獎或特別獎號碼。\n請輸入這張發票完整的 8 碼號碼：",
                 justify="left", font=("Microsoft JhengHei UI", 10)).pack(anchor="w")
        full_entry = ttk.Entry(frame, font=("Consolas", 15), width=18)
        full_entry.pack(anchor="w", pady=(12, 14))

        def submit():
            value = re.sub(r"\s+", "", full_entry.get().strip())
            if not re.fullmatch(r"\d{8}", value):
                messagebox.showwarning("號碼格式", "請輸入完整 8 碼數字。", parent=dialog)
                full_entry.focus_set()
                return
            if not value.endswith(suffix):
                messagebox.showwarning("末三碼不符", f"完整號碼的末三碼必須是 {suffix}。", parent=dialog)
                full_entry.focus_set()
                return
            result["number"] = value
            dialog.destroy()

        buttons = tk.Frame(frame)
        buttons.pack(fill="x")
        tk.Button(buttons, text="取消", command=dialog.destroy, relief="flat", padx=14, pady=6).pack(side="right")
        tk.Button(buttons, text="確認對獎", command=submit, bg="#1570c8", fg="white",
                  activebackground="#0f5da8", activeforeground="white", relief="flat",
                  padx=14, pady=6).pack(side="right", padx=(0, 8))
        full_entry.bind("<Return>", lambda _event: submit())
        full_entry.focus_set()
        self.wait_window(dialog)
        return result["number"]

    def clear_records(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.records.clear()
        self.total_label.configure(text="累計獎金　NT$ 0")


if __name__ == "__main__":
    App().mainloop()

