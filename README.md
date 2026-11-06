# 阳光晨跑桌面工具

Windows 路线模拟与 Android Emulator 界面测试工具，当前发布版本 1.5.5。基于 [suiyuan1145/virtual_run](https://github.com/suiyuan1145/virtual_run) 的 MIT 代码修改，原许可证保留。

## 下载和启动

在 [Releases](https://github.com/zhuozhuoruichen-hub/morning-jog/releases/latest) 下载 Windows 便携包并完整解压，双击「启动虚拟跑步.cmd」。使用源码时需安装 Python 3.13 x64，运行 python -X utf8 android_location_test.py。

进入「首次安装」阅读并接受 Google SDK 许可后下载官方 Android Emulator、Platform Tools 和 Android 11 系统镜像。也可从 [Android 官方网站](https://developer.android.com/studio) 安装所需组件。安小信 APK 需自行合法取得，在模拟器内安装、授权和登录。

## 当前默认设置

- 默认速度 10 km/h，最长时限 2000 秒。
- 安小信显示达到 3 km 时优先结束并检查结算页。
- 每天北京时间 06:00 准备，06:30 开始，08:00 停止轨迹。
- 本学期截止日期 2026-11-30。仅在「保存并启用每日晨跑」后注册本机计划任务。
- 准备阶段最多重试 30 次，并受 06:31 截止限制。已有记录或已尝试开始后阻止重复创建。
- 结算返回 503、记录被拒绝或无法确认结果时保存现场。累计有效里程以智慧运动系统为准。

## 验证范围

已检查本地脚本语法、时间边界、3 km 阈值、正常结算与 503 错误处理。本地曾发生跑步网页 ERR_EMPTY_RESPONSE，网络根因尚未查明。首次安装到其他电脑及完整定时运行仍需在各自环境验证。

电脑须开机、联网且 Windows 用户已登录，应用需保持有效登录。账号保存采用当前 Windows 用户 DPAPI 加密。首次配置请核对 SDK、AVD、当前账号和起点。

Google SDK、系统镜像及安小信属于第三方软件，下载包提供本项目程序及 Python 运行环境。使用须遵守相关服务规则，模拟轨迹测试不代表真实运动记录。

## 构建

GitHub Actions 在 main 更新后构建 Windows 便携包并发布 Release。也可在 Windows Python 3.13 环境运行 python build_portable.py。
