# 哔哩哔哩 Index-Translate 翻译本地代理

一个**零依赖**的本地代理，把 B 站的**免费、无需密钥**的
[Index-Translate](https://index-translate.bilibili.com/) 接口，包装成一个
标准的 **OpenAI 兼容**接口，让**陪读蛙 / 沉浸式翻译**等浏览器插件可以把它当成
「自定义 OpenAI 翻译服务」来用。


---

## 有什么功能

B 站的翻译接口要求请求里带一个隐藏参数
`chat_template_kwargs: {"enable_thinking": false}`。不带的话，模型会输出一大段
「思维链（CoT）」推理文字，而不是译文，插件拿到的是乱码。大部分插件不会发这个参数，所以必须由本地代理帮它补上。

本代理只做三件事：
1. **始终注入** `enable_thinking=false`。
2. 默认 `temperature=0`。
3. 转发到 B 站免费接口，并把结果（含流式 SSE）回传给插件。

**零依赖**：只用 Python 标准库，不需要 `pip install` 任何东西。

---

## 安装与运行

### Windows（推荐：一键安装向导）
- **一键启动（推荐）**：双击 `setup.bat` → 弹出命令行窗口，直接输入一个数字即可：
  - `1` 安装 / 启动（向导会自动启动代理、自检、询问是否开机自启，最后打印 API 地址 / 模型 / API Key）
  - `2` 立即停止（**保留**开机自启注册，下次登录仍会自动启动）
  - `3` 彻底关闭（**取消**开机自启 + 停止进程，之后不会再自启）
  - `4` 退出
- **仅静默自启**：双击 `install_autostart.bat` → 注册开机自启并立即启动，无窗口，意外退出会自动重启。
- **控制台调试**：双击 `run_windows.bat`（可见窗口，Ctrl+C 停止）。
- **停止代理**：双击 `stop_proxy.bat`（等价于 `proxy.py stop`，保留自启注册）。
- **彻底关闭**：双击 `uninstall.bat`（等价于 `proxy.py uninstall`，取消自启并停止进程）。

> 以上"停止 / 关闭"只会结束**本项目**的进程，不会影响你电脑上其他的 Python 程序。

### macOS / Linux
```bash
chmod +x run.sh
./run.sh install      # 注册开机自启（Linux 为 systemd 用户服务）
./run.sh serve        # 或直接前台运行
./run.sh test         # 自检两条出口路径
```
*未在mac/linux上实测，如有遇到问题请及时联系/提出issue*

---

## 在「陪读蛙」（或任意 OpenAI 兼容客户端）里配置

把翻译服务设为「自定义 / OpenAI 兼容」，按下面填写：

| 配置项 | 填写内容 |
|---|---|
| API 地址 / Base URL | `http://127.0.0.1:8080/v1` |
| 模型 Model | `Index-Translate-35B-A3B` |
| API Key | 任意字符串，例如 `index`（上游不校验） |

> 如果你用了自定义端口（例如 9000），把上面的 `8080` 换成对应端口即可。

模型列表：
- `Index-Translate-35B-A3B`（推荐）
- `Index-Translate-9B`
- `Index-Translate-2B`

---

## 命令行（CLI）

```
python proxy.py serve      [--port 8080] [--host 127.0.0.1] [--model ...] [--api-base ...] [--upstream-proxy ...]
python proxy.py setup      交互式安装向导（检查 Python → 启动代理 → 自检 → 询问自启 → 打印配置）
python proxy.py install    注册当前用户的开机自启，并启动看门狗
python proxy.py stop       停止正在运行的代理（保留开机自启注册）
python proxy.py uninstall  取消开机自启 + 停止代理（彻底关闭）
python proxy.py test       自检两条出口路径是否连通
```

> `stop` / `uninstall` 只结束本项目的 watchdog 与代理进程，不会误杀其他 Python 程序。

- `--port`（默认 8080）、`--host`（默认 127.0.0.1；`0.0.0.0` 暴露到局域网）
- `--model` 默认上游模型
- `--api-base` 上游地址（默认 `https://index-translate.bilibili.com/v1`）
- `--upstream-proxy` 强制指定出口代理（例如 `http://127.0.0.1:7890`）；
  留空 = 从 `HTTPS_PROXY` 自动探测、直连优先。环境变量
  `INDEX_TRANSLATE_UPSTREAM_PROXY` 同样生效。

---

## 支持的接口

- `POST /v1/chat/completions` —— 核心翻译接口（支持流式 SSE）
- `GET  /v1/models` —— 列出可用模型（供插件自动探测）
- `POST /v1/responses` —— 兼容 OpenAI Responses API（把 `input` 自动映射为 `messages`）
- `GET  /` `/healthz` —— 健康检查

---

## 常见问题排查

| 现象 | 原因 / 解决 |
|---|---|
| 插件拿到一堆推理文字而非译文 | 请求没经过本代理，或代理没注入参数。确认插件填的是 `http://127.0.0.1:8080/v1`，且代理在运行。 |
| `502` / 翻译一直失败 | 所有路径都连不上上游。运行 `proxy.py test` 看哪条出口可用；确认浏览器能打开 `https://index-translate.bilibili.com`（直连或走你的代理都行）。 |
| 连接被拒绝 / 超时 | 代理没在跑 → 双击 `setup.bat` 或 `install_autostart.bat` 启动；或端口被占用 → 用 `--port` 换一个。 |
| 翻译很慢 | 免费端点偶尔波动；可换 `Index-Translate-9B`/`2B`。超过 8 秒基本是网络问题。 |
| 想给局域网内其他设备用 | 启动时加 `--host 0.0.0.0`（仅可信网络使用），并把插件地址改成你电脑的局域网 IP。 |

> **macOS launchd 示例**（保存为 `~/Library/LaunchAgents/com.index.translate.proxy.plist`）：
>
> ```xml
> <plist version="1.0"><dict>
> <key>Label</key><string>com.index.translate.proxy</string>
> <key>ProgramArguments</key><array><string>/usr/bin/python3</string>
>  <string>/path/to/proxy.py</string><string>serve</string></array>
> <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
> </dict></plist>
> ```
> 然后执行 `launchctl load ~/Library/LaunchAgents/com.index.translate.proxy.plist`。

---

## 隐私说明

所有翻译文本都会发送到 B 站的公网接口（`index-translate.bilibili.com`）。请勿翻译涉密内容。本代理仅把请求元数据记录到 `proxy_requests.log` 用于调试，
**本脚本不会记录和上传任何额外数据**
