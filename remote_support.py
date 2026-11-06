"""Explicit USB bootstrap, tailnet peer verification, and scrcpy control."""
from pathlib import Path
import json
import os
import queue
import subprocess
import threading
import time
import webbrowser
from desktop_support import APP_DIR, DATA_DIR, RESOURCE_DIR
from wifi_support import call, endpoint, device_serial, usb_devices, default_apk


def tool_directory():
    for root in (APP_DIR / 'remote-tools', RESOURCE_DIR / 'local-install/remote-tools'):
        if root.is_dir():
            return root
    raise RuntimeError('未找到远程控制组件，请使用完整新版软件包。')


def tailscale_executable():
    path = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Tailscale/tailscale.exe'
    if not path.is_file():
        raise RuntimeError('尚未安装 Tailscale，请点击“安装电脑组网工具”，按安装界面完成操作。')
    return path


def tailscale_status():
    result = subprocess.run([str(tailscale_executable()), 'status', '--json'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('Tailscale 尚未连接，请在系统托盘中登录并连接。')
    data = json.loads(result.stdout)
    if data.get('BackendState') != 'Running':
        raise RuntimeError('请在电脑和手机的 Tailscale 中登录同一账号并连接。')
    return data


def verify_peer(address):
    target = endpoint(address, allow_tailnet=True)
    ip = target.split(':')[0]
    # A private LAN address must not accidentally be accepted as a remote peer.
    import ipaddress
    if ipaddress.IPv4Address(ip) not in ipaddress.IPv4Network('100.64.0.0/10'):
        raise ValueError('远程模式请填写手机 Tailscale 的 100.x.x.x 地址和端口。')
    data = tailscale_status()
    peers = [p for p in data.get('Peer', {}).values() if ip in p.get('TailscaleIPs', [])]
    if not peers:
        raise RuntimeError('此地址不在当前 Tailscale 设备列表中；请确认两端使用同一组网账号。')
    if not any(p.get('Online') for p in peers):
        raise RuntimeError('手机组网状态离线；请打开手机 Tailscale 并连接。')
    return target


def prepare_tcpip(serial):
    serial = device_serial(serial)
    if ':' in serial:
        raise ValueError('首次准备必须选择 USB 连接的手机。')
    if serial not in usb_devices(call(['devices', '-l'])):
        raise RuntimeError('未发现这台已授权的 USB 手机。请连接数据线并在手机确认 USB 调试授权。')
    output = call(['tcpip', '5555'], serial)
    return output + '\n手机已请求监听 5555。请保持 USB，先连接组网地址验证，再拔线复测。重启手机后通常需要重新准备。'


def connect_remote(address):
    target = verify_peer(address)
    output = call(['connect', target])
    if call(['get-state'], target).strip() != 'device':
        raise RuntimeError('手机 ADB 尚未就绪。请重新连接 USB 准备，并确认授权提示。')
    model = call(['shell', 'getprop', 'ro.product.model'], target)
    return output + '\n手机型号：' + model


def scrcpy_executable():
    candidates = list(tool_directory().glob('scrcpy-*/scrcpy.exe'))
    if len(candidates) != 1:
        raise RuntimeError('scrcpy 组件缺失或版本不唯一，请重新安装完整包。')
    return candidates[0]


def launch_screen(serial):
    from android_location_test import find_adb
    serial = device_serial(serial)
    if call(['get-state'], serial).strip() != 'device':
        raise RuntimeError('请先连接并验证手机。')
    executable = scrcpy_executable()
    logs = DATA_DIR / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / ('scrcpy-' + str(time.time_ns()) + '.log')
    environment = dict(os.environ, ADB=find_adb())
    with log.open('wb') as output:
        child = subprocess.Popen([str(executable), '--serial', serial, '--max-size=1280',
                                  '--max-fps=30', '--video-bit-rate=4M', '--no-audio',
                                  '--window-title=手机远程控制 · 虚拟跑步'],
                                 cwd=executable.parent, env=environment,
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return child, log


def add_remote_tab(app, notebook):
    import tkinter as tk
    from tkinter import ttk, messagebox
    page = ttk.Frame(notebook, padding=16)
    notebook.add(page, text='远程控制 / USB')
    page.columnconfigure(1, weight=1)
    ttk.Label(page, text='电脑控制手机 · USB / 跨网络', font=('Microsoft YaHei UI', 14, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w')
    instructions = ('USB：用数据线连接，打开手机 USB 调试，确认授权后刷新并选择设备。\n'
                    '跨网络：电脑和手机安装 Tailscale，登录同一账号并连接，再用 USB 完成首次准备。\n'
                    '填写手机 Tailscale 的 100.x.x.x:5555，验证后拔线复测。无需路由器端口映射。\n'
                    '手机重启后通常需要再次 USB 准备；HyperOS 流量联网兼容性仍需实测。\n'
                    '小米若只能看画面、不能点击，需在手机开启“USB 调试（安全设置）”并按系统提示操作。')
    ttk.Label(page, text=instructions, wraplength=900, justify='left').grid(row=1, column=0, columnspan=3, sticky='w', pady=10)
    mode = tk.StringVar(value='USB')
    choices = ttk.Frame(page)
    choices.grid(row=2, column=0, columnspan=3, sticky='w')
    ttk.Radiobutton(choices, text='USB 数据线', variable=mode, value='USB').pack(side='left', padx=(0, 18))
    ttk.Radiobutton(choices, text='跨网络（Tailscale）', variable=mode, value='remote').pack(side='left')
    usb = tk.StringVar()
    ttk.Label(page, text='USB 手机').grid(row=3, column=0, sticky='w', padx=(0, 10))
    combo = ttk.Combobox(page, textvariable=usb, state='readonly')
    combo.grid(row=3, column=1, sticky='ew', pady=6)
    address = tk.StringVar()
    state_file = DATA_DIR / 'remote-device.json'
    try:
        address.set(endpoint(json.loads(state_file.read_text(encoding='utf-8'))['address'], allow_tailnet=True))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    ttk.Label(page, text='手机组网 IP:端口').grid(row=4, column=0, sticky='w', padx=(0, 10))
    ttk.Entry(page, textvariable=address).grid(row=4, column=1, sticky='ew', pady=6)
    controls, events = [], queue.Queue()
    status = tk.StringVar(value='尚未连接。首次请使用 USB；远程准备由你点击后才执行。')
    ttk.Label(page, textvariable=status, wraplength=900).grid(row=8, column=0, columnspan=3, sticky='w', pady=8)
    log = tk.Text(page, height=8, wrap='word', state='disabled', font=('Consolas', 9))
    log.grid(row=9, column=0, columnspan=3, sticky='nsew')
    page.rowconfigure(9, weight=1)
    screen = None
    screen_log = None
    busy = False

    def append(text):
        log.configure(state='normal')
        log.insert('end', text + '\n\n')
        log.see('end')
        log.configure(state='disabled')

    def task(title, operation, after=None):
        nonlocal busy
        if busy:
            return
        busy = True
        status.set(title + '……')
        for button in controls:
            button.configure(state='disabled')
        def worker():
            try:
                events.put((True, title, operation(), after))
            except Exception as exc:
                events.put((False, title, str(exc), None))
        threading.Thread(target=worker, daemon=True).start()

    def target():
        return usb.get() if mode.get() == 'USB' else address.get()

    def refresh():
        def display(result):
            available = usb_devices(result)
            combo['values'] = available
            if usb.get() not in available:
                usb.set(available[0] if len(available) == 1 else '')
        task('刷新 USB 设备', lambda: call(['devices', '-l']), display)

    def prepare():
        serial = usb.get()
        if not messagebox.askyesno('准备手机远程连接',
                '将请求这台 USB 手机开启 ADB TCP 5555。此端口可能同时在手机其他网络接口监听。\n'
                '仅在可信网络准备，不设置公网映射；用完可点击“关闭手机网络调试”。\n继续？', parent=app):
            return
        task('USB 准备远程连接', lambda: prepare_tcpip(serial))

    def verify():
        serial, use_usb = target(), mode.get() == 'USB'
        def operation():
            if use_usb:
                if serial not in usb_devices(call(['devices', '-l'])):
                    raise RuntimeError('请选择已授权的 USB 手机；若显示 unauthorized，请在手机确认调试授权。')
                return '已连接 USB 手机：' + call(['shell', 'getprop', 'ro.product.model'], serial)
            result = connect_remote(serial)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temporary = state_file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'address': endpoint(serial, allow_tailnet=True)}), encoding='utf-8')
            temporary.replace(state_file)
            return result
        task('连接并验证手机', operation)

    def start():
        nonlocal screen
        if screen is not None and screen.poll() is None:
            append('控制窗口已在运行，请使用该窗口。')
            return
        serial, use_remote = target(), mode.get() == 'remote'
        def operation():
            if use_remote:
                verify_peer(serial)
            return launch_screen(serial)
        def launched(result):
            nonlocal screen, screen_log
            screen, screen_log = result
            append('已启动画面进程；连接结果将显示在独立窗口或下方日志。')
        task('打开手机画面', operation, launched)

    def stop_screen():
        if screen is not None and screen.poll() is None:
            screen.terminate()
            status.set('已请求关闭控制窗口；手机网络调试需单独关闭。')

    def close_network():
        serial = target()
        task('关闭手机网络调试', lambda: call(['usb'], serial))

    def install_phone():
        serial, use_remote = target(), mode.get() == 'remote'
        def operation():
            if use_remote:
                verify_peer(serial)
            return call(['install', '-r', str(default_apk())], serial, timeout=150)
        task('安装虚拟跑步安卓版', operation)

    def install_tailscale():
        paths = list(tool_directory().glob('tailscale-setup-*-amd64.msi'))
        if len(paths) != 1:
            messagebox.showerror('安装组件', '未找到 Tailscale 安装包，请从官方网站下载。', parent=app)
            return
        os.startfile(paths[0])
        status.set('已打开官方安装包，请完成安装及电脑登录。管理员授权由你在系统提示中确认。')

    def group(row, buttons):
        container = ttk.Frame(page)
        container.grid(row=row, column=0, columnspan=3, sticky='w')
        for text, command in buttons:
            button = ttk.Button(container, text=text, command=command)
            button.pack(side='left', padx=(0, 8), pady=4)
            controls.append(button)

    group(5, [('刷新 USB 手机', refresh), ('USB 首次准备远程', prepare), ('连接并验证', verify)])
    group(6, [('打开手机画面并控制', start), ('关闭控制窗口', stop_screen), ('关闭手机网络调试', close_network), ('安装安卓版', install_phone)])
    group(7, [('安装电脑组网工具', install_tailscale), ('查看组网设备', lambda: task('组网设备', lambda: json.dumps({
        'devices': [{'name': p.get('HostName'), 'ip': p.get('TailscaleIPs'), 'online': p.get('Online')} for p in tailscale_status().get('Peer', {}).values()]}, ensure_ascii=False, indent=2))),
        ('手机组网工具下载', lambda: webbrowser.open('https://tailscale.com/download/android'))])

    def poll():
        nonlocal busy, screen
        try:
            while True:
                ok, title, result, after = events.get_nowait()
                busy = False
                for button in controls:
                    button.configure(state='normal')
                status.set(title + ('完成' if ok else '失败，请查看日志'))
                if ok and after:
                    after(result)
                    if title != '打开手机画面':
                        append(title + '\n' + str(result))
                else:
                    append(title + '\n' + str(result))
        except queue.Empty:
            pass
        if screen is not None and screen.poll() is not None:
            code = screen.returncode
            append('控制窗口已退出，退出码 ' + str(code) + '\n' + screen_log.read_text(encoding='utf-8', errors='replace')[-5000:])
            status.set('控制窗口已关闭' if code == 0 else '控制窗口未成功运行，请查看日志和手机授权提示')
            screen = None
        app.after(150, poll)

    def cleanup(event):
        if event.widget is app:
            if screen is not None and screen.poll() is None:
                screen.terminate()
    app.bind('<Destroy>', cleanup, add='+')
    poll()
    return page
