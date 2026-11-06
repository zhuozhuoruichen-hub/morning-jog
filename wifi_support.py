"""Local Android wireless-debugging connection and explicit file transfer."""
from __future__ import annotations
import ipaddress
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import unicodedata
from desktop_support import APP_DIR, DATA_DIR, RESOURCE_DIR


def normalize_input(value):
    return unicodedata.normalize('NFKC', value).strip().replace('∶', ':')


def endpoint(value, allow_tailnet=False):
    parts = [part.strip() for part in normalize_input(value).split(':')]
    if len(parts) != 2:
        raise ValueError('地址需包含 IP 和端口，例如 172.20.10.2:41009；请勿填写手机名称或网址。')
    address = ipaddress.IPv4Address(parts[0])
    lan = any(address in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    tailnet = allow_tailnet and address in ipaddress.IPv4Network('100.64.0.0/10')
    if not (lan or tailnet):
        raise ValueError('请填写同一局域网内手机的私有 IPv4 地址。')
    if not parts[1].isascii() or not parts[1].isdigit() or not 1 <= int(parts[1]) <= 65535:
        raise ValueError('端口必须为 1–65535。')
    return f'{address}:{int(parts[1])}'


def device_serial(value):
    value = normalize_input(value)
    if ':' in value:
        return endpoint(value, allow_tailnet=True)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', value) or value.startswith('emulator-'):
        raise ValueError('请选择已授权的 USB 手机序列号，或填写手机网络 IP:端口。')
    return value


def usb_devices(output):
    return [line.split()[0] for line in output.splitlines()
            if len(line.split()) >= 2 and line.split()[1] == 'device'
            and ':' not in line.split()[0] and not line.split()[0].startswith('emulator-')]


def call(arguments, serial=None, input_text=None, timeout=40):
    from android_location_test import find_adb
    command = [find_adb()]
    if serial is not None:
        command += ['-s', device_serial(serial)]
    result = subprocess.run(command + list(arguments), input=input_text,
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    output = (result.stdout + '\n' + result.stderr).strip()
    if result.returncode or re.search(r'\b(failed|unable|cannot|error)\b', output, re.I):
        raise RuntimeError(output or f'ADB 退出码 {result.returncode}')
    return output


def devices(output):
    return [line.split()[0] for line in output.splitlines()
            if len(line.split()) >= 2 and line.split()[1] == 'device'
            and re.fullmatch(r'\d+\.\d+\.\d+\.\d+:\d+', line.split()[0])]


def pair(address, code):
    address = endpoint(address)
    code = normalize_input(code)
    if not re.fullmatch(r'[0-9]{6}', code):
        raise ValueError('配对码应为手机当前显示的 6 位数字。')
    # Pass the short-lived code over stdin; never persist it or put it in process arguments.
    output = call(['pair', address], input_text=code + '\n')
    if 'successfully paired' not in output.lower():
        raise RuntimeError('尚未确认配对成功：' + output)
    return output


def default_apk():
    for p in (APP_DIR / 'phone/虚拟跑步-Android-1.0.0.apk',
              RESOURCE_DIR / 'dist/android/虚拟跑步-Android-1.0.0.apk'):
        if p.is_file():
            return p
    raise RuntimeError('未找到已构建的安卓版 APK。')


def add_wifi_tab(app, notebook):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    page = ttk.Frame(notebook, padding=16)
    notebook.add(page, text='手机互通（Wi-Fi）')
    page.columnconfigure(1, weight=1)
    ttk.Label(page, text='小米 15 · 同一 Wi-Fi', font=('Microsoft YaHei UI', 14, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w')
    help_text = ('手机：设置 → 更多设置 → 开发者选项 → 无线调试（菜单名称随系统版本不同）。\n'
                 '首次使用可在“我的设备”的系统版本处连续点击以启用开发者选项。\n'
                 '1. 打开“使用配对码配对设备”，填写配对地址和当前配对码。\n'
                 '2. 配对成功后，填写无线调试主页面的 IP:端口，再连接。两个端口通常不同。\n'
                 '3. 连接成功后可打开手机画面控制，或安装安卓版并完成系统授权。\n'
                 '电脑和手机连接同一个 Wi-Fi；本页不需要登录 Tailscale。\n'
                 '此面板管理真机连接和文件传输；桌面的自动轨迹与定时任务仅支持模拟器。')
    ttk.Label(page, text=help_text, justify='left', wraplength=780).grid(row=1, column=0, columnspan=3, sticky='w', pady=(8, 14))
    pair_address, code, connect_address = tk.StringVar(), tk.StringVar(), tk.StringVar()
    state_file = DATA_DIR / 'wifi-device.json'
    try:
        connect_address.set(endpoint(json.loads(state_file.read_text(encoding='utf-8'))['address']))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    for row, title, variable in ((2, '配对 IP:端口', pair_address), (3, '6 位临时配对码', code), (5, '连接 IP:端口', connect_address)):
        ttk.Label(page, text=title).grid(row=row, column=0, sticky='w', padx=(0, 10), pady=4)
        ttk.Entry(page, textvariable=variable, show='●' if row == 3 else '', width=32).grid(row=row, column=1, sticky='ew', pady=4)
    status = tk.StringVar(value='尚未连接手机。配对码仅用于本次配对，不会保存。')
    ttk.Label(page, textvariable=status, wraplength=780).grid(row=9, column=0, columnspan=3, sticky='w', pady=8)
    log = tk.Text(page, height=9, wrap='word', state='disabled', font=('Consolas', 9))
    log.grid(row=10, column=0, columnspan=3, sticky='nsew')
    page.rowconfigure(10, weight=1)
    events, controls = queue.Queue(), []
    busy = False
    screen = None
    screen_log = None

    def task(title, operation, after=None):
        nonlocal busy
        if busy:
            return
        busy = True
        for b in controls:
            b.configure(state='disabled')
        status.set(title + '……')
        def run():
            try:
                events.put((True, title, operation(), after))
            except Exception as exc:
                events.put((False, title, str(exc), None))
        threading.Thread(target=run, daemon=True).start()

    def poll():
        nonlocal busy, screen
        try:
            while True:
                ok, title, result, after = events.get_nowait()
                busy = False
                for b in controls:
                    b.configure(state='normal')
                status.set(title + ('完成' if ok else '失败，请查看下方信息'))
                log.configure(state='normal')
                log.insert('end', title + '\n' + str(result) + '\n\n')
                log.see('end')
                log.configure(state='disabled')
                if ok and after:
                    after(value)
        except queue.Empty:
            pass
        if screen is not None and screen.poll() is not None:
            exit_code = screen.returncode
            log.configure(state='normal')
            log.insert('end', '\n手机控制窗口退出码：' + str(exit_code) + '\n' +
                       screen_log.read_text(encoding='utf-8', errors='replace')[-4000:] + '\n')
            log.see('end')
            log.configure(state='disabled')
            status.set('控制窗口已关闭' if exit_code == 0 else '控制窗口启动失败，请查看下方日志')
            screen = None
        app.after(120, poll)

    def button(parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        b.pack(side='left', padx=(0, 8), pady=4)
        controls.append(b)

    def start_pair():
        address, secret = pair_address.get(), code.get()
        code.set('')
        task('无线配对', lambda: pair(address, secret), lambda _: pair_address.set(endpoint(address)))

    def connect():
        address = connect_address.get()
        def operation():
            target = endpoint(address)
            result = call(['connect', target])
            if call(['get-state'], target).strip() != 'device':
                raise RuntimeError('设备尚未就绪。')
            model = call(['shell', 'getprop', 'ro.product.model'], target)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temporary = state_file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'address': target}), encoding='utf-8')
            temporary.replace(state_file)
            return result + '\n设备型号：' + model
        task('连接并验证手机', operation, lambda _: connect_address.set(endpoint(address)))

    row = ttk.Frame(page)
    row.grid(row=4, column=1, sticky='w')
    button(row, '使用配对码配对', start_pair)
    row = ttk.Frame(page)
    row.grid(row=6, column=0, columnspan=3, sticky='w')
    button(row, '连接并验证', connect)
    button(row, '刷新设备', lambda: task('设备列表', lambda: call(['devices', '-l'])))
    button(row, '发现无线设备', lambda: task('无线发现', lambda: call(['mdns', 'services'])))
    def install():
        address = connect_address.get()
        task('安装安卓版', lambda: call(['install', '-r', str(default_apk())], address, timeout=150))
    def open_phone():
        address = connect_address.get()
        task('打开安卓版', lambda: call(['shell', 'am', 'start', '-n', 'com.virtualrun.android/.MainActivity'], address))
    def disconnect():
        address = connect_address.get()
        task('断开连接', lambda: call(['disconnect', endpoint(address)]))
    row = ttk.Frame(page)
    row.grid(row=7, column=0, columnspan=3, sticky='w')
    button(row, '安装安卓版 APK', install)
    button(row, '在手机上打开', open_phone)
    button(row, '断开此手机', disconnect)

    def open_screen():
        if screen is not None and screen.poll() is None:
            status.set('手机画面窗口已在运行，请使用该窗口。')
            return
        address = connect_address.get()
        def operation():
            nonlocal screen, screen_log
            from remote_support import launch_screen
            screen, screen_log = launch_screen(endpoint(address))
            return '已请求打开手机控制窗口；如果只能看不能点击，请在手机开启 USB 调试（安全设置）。'
        task('打开同 Wi-Fi 手机画面', operation)

    def close_screen():
        if screen is not None and screen.poll() is None:
            screen.terminate()

    button(row, '打开手机画面并控制', open_screen)
    button(row, '关闭控制窗口', close_screen)

    def pull():
        address = connect_address.get()
        target = filedialog.asksaveasfilename(parent=app, title='保存手机导出的轨迹', initialfile='virtualrun-track.json', defaultextension='.json', filetypes=[('JSON', '*.json')])
        if target:
            task('接收手机轨迹', lambda: call(['pull', '/sdcard/Download/virtualrun-track.json', target], address))
    def push():
        address = connect_address.get()
        source = filedialog.askopenfilename(parent=app, title='选择要传到手机 Download 的 JSON 文件', filetypes=[('JSON', '*.json')])
        if not source:
            return
        if not messagebox.askyesno('发送文件', '发送到手机 Download/virtualrun-pc.json？若同名文件已存在，将覆盖。', parent=app):
            return
        task('发送 JSON 到手机', lambda: call(['push', source, '/sdcard/Download/virtualrun-pc.json'], address))
    row = ttk.Frame(page)
    row.grid(row=8, column=0, columnspan=3, sticky='w')
    button(row, '接收手机轨迹 JSON', pull)
    button(row, '发送 JSON 到手机', push)
    ttk.Label(row, text='先在手机导出到 Download/virtualrun-track.json').pack(side='left')
    def cleanup(event):
        if event.widget is app and screen is not None and screen.poll() is None:
            screen.terminate()
    app.bind('<Destroy>', cleanup, add='+')
    poll()
    return page
