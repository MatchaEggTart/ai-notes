# 自建 SearXNG：给 opencode 和 Cherry Studio 接上 Google 搜索

> 目标：在自己机器上用 rootless Podman 跑一个只监听本机的 SearXNG 实例，把 Google 设成它的引擎之一，
> 然后让 **Cherry Studio**（原生支持 SearXNG）和 **opencode**（只能走 MCP）都用上它。
>
> 本文是「照着做」的教学，每一步都说明**为什么**。所有命令都在 Arch Linux 上验证过前提条件。

---

## 0. 先搞清楚数据流

```text
  Cherry Studio ────┐
  (设置里填 URL)     │
                    ├──▶  SearXNG  ──▶  Google / DuckDuckGo / Brave / ...
  opencode ─────────┘     127.0.0.1:8080
    └─ MCP 服务器
       mcp-searxng

  客户端 --JSON 接口 GET /search?format=json--> SearXNG
```

关键点：

- SearXNG 是一个**元搜索引擎**：它自己去抓 Google / DDG / Brave……，聚合结果后返回。它本身**不自带** Google，只是把 Google 当成一个「引擎」来调用。
- Cherry Studio 和 opencode 都通过 SearXNG 的 **JSON 接口** `GET /search?format=json` 拿结果。
  所以 **`json` 输出格式必须显式打开**（SearXNG 默认只开 `html`）——这是最容易踩的坑。
- opencode v2 的内置 `websearch` 只认 Exa / Firecrawl / Parallel / Tavily 四家，**没有**自定义 provider 入口，所以只能靠 **MCP** 接进来。
- 全程只监听 `127.0.0.1`，不对外网暴露。

---

## 1. 前置检查（1 分钟）

```bash
# rootless Podman 需要 subuid/subgid 映射，Arch 上通常已就绪
grep "$USER" /etc/subuid /etc/subgid     # 应各有一行，形如 matchaeggtart:100000:65536

# 需要 cgroup v2
stat -fc %T /sys/fs/cgroup               # 应输出 cgroup2fs

# 生成密钥要用 openssl
command -v openssl
```

上面三条都正常就可以往下走。如果 `subuid/subgid` 缺失，用 `sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"` 补上。

---

## 2. 安装 Podman

```bash
sudo pacman -S podman
```

选 1（crun），直接回车就行（它本来就是默认值）。
理由：

- crun：C 写的轻量 OCI 运行时，Podman 的原生默认，rootless 支持和性能最好 —— 就是你要的。
- runc：Docker 的遗留默认，能用但更重、启动略慢，没必要。
- krun：基于 libkrun 的 microVM 隔离运行时，会给每个容器套一层轻量虚拟机，普通自建 SearXNG 用不上，反而更麻烦。

说明：

- 官方仓库的 `podman` 会带齐依赖：`conmon`、`oci-runtime`（crun）、`nftables`、`passt`、`shadow`（提供 `newuidmap`/`newgidmap`）。
- Arch 没有 SELinux，所以本文里挂载参数上的 `:Z` 是**空操作**，写了无害、不写也行。
- 不需要 `podman-docker`（那是给习惯 `docker` 命令的人用的），也不需要一开始就装 `podman-compose`。

装完验证：

```bash
podman info --format '{{.Host.CgroupsVersion}}'   # v2
podman run --rm docker.io/library/hello-world
# 删除测试镜像
podman rmi hello-world
```

第一次会拉镜像，看到 `Hello from Docker!` 就说明 rootless 容器能跑。

> 为什么用 rootless：容器里的 `root` 会被映射成你本人，容器逃逸拿不到真实 root，权限最小。

---

## 3. 规划：配置入库，机密用 .gitignore 挡住

你用 GNU stow 管理 `~/Dotfiles`。stow 会把 `~/Dotfiles/matchaeggtart/config/searxng/`
**整个目录软链**成 `~/.config/searxng`，所以「放进 `~/.config/searxng/` 的文件」物理上
都躺在公开的 Dotfiles 仓库里。机密的 `searxng.env` 靠 `.gitignore` 拦下来。

> 本仓库已有先例：根 `.gitignore` 里就是用同样的方式挡掉 `config/opencode/service.json` 的。

| 文件 | 角色 | 进 Dotfiles？ |
| --- | --- | --- |
| `~/Dotfiles/matchaeggtart/config/searxng/settings.yml`（stow 后即 `~/.config/searxng/settings.yml`） | 实例配置（开 `google` + `bing`、开 JSON） | 是 |
| `~/Dotfiles/matchaeggtart/config/searxng/limiter.toml` | 空的占位文件，只为消除警告 | 是 |
| `~/Dotfiles/matchaeggtart/config/searxng/searxng.env` | `SEARXNG_SECRET` / `FORCE_OWNERSHIP=false` / 代理变量 | **否**（被 `.gitignore` 忽略） |
| `~/Dotfiles/matchaeggtart/config/containers/systemd/searxng.container`（stow 后即 `~/.config/containers/systemd/searxng.container`） | Quadlet 服务定义，**第 7 步**才创建 | 是 |

建目录（空目录 git 不跟踪，所以建完不会立刻出现在 `git status` 里）：

```bash
mkdir -p "$HOME/Dotfiles/matchaeggtart/config/searxng"
```

**先**把忽略规则写好，追加到仓库根 `.gitignore`（幂等写法，重复执行不会插两条）：

```bash
grep -qxF 'matchaeggtart/config/searxng/searxng.env' "$HOME/Dotfiles/.gitignore" \
  || cat >> "$HOME/Dotfiles/.gitignore" <<'EOF'

# ---- SearXNG 机密，不入库 ----
matchaeggtart/config/searxng/searxng.env
EOF
```

> 两个必须记住的限制：
>
> 1. `.gitignore` **只对未跟踪的文件生效**。若某文件已经被 `git add` 过，加规则没用，
>    得先 `git rm --cached`。所以顺序是「先写规则，再生成文件」。
> 2. `git add -f` 会强行绕过规则 —— 别对 `searxng.env` 用它。

---

## 4. 写配置：开引擎（Google + bing）+ 开 JSON

新建 `~/Dotfiles/matchaeggtart/config/searxng/settings.yml`（stow 之后它同时也是 `~/.config/searxng/settings.yml`）：

```yaml
# SearXNG 用户配置。只在默认配置的基础上做最小覆盖，其余全部继承默认值。
use_default_settings:
  engines:
    remove:
      # 这两个引擎依赖 Tor，本机没跑 Tor，留着只会刷日志报错
      - ahmia
      - torch

general:
  instance_name: "SearXNG (local)"

search:
  safe_search: 0          # 0=不过滤 1=中等 2=严格；技术查询用 0
  autocomplete: "duckduckgo"
  formats:
    - html                # 给人看的网页界面
    - json                # Cherry Studio 和 MCP 都依赖它（默认没有！）

server:
  base_url: "http://127.0.0.1:8080/"
  limiter: false          # 只监听回环地址，单机用不需要限流器
  image_proxy: false
  public_instance: false  # 不要开：那是给公开实例防滥用的

# 默认配置里 `google` 和 `bing` 都是 `disabled: true`。
# 指定同一 name 时，SearXNG 会按 name 合并覆盖，所以这里只写需要改的字段。
engines:
  - name: google
    disabled: false
  # 本机实测（2026-10）：google 的 /wml/search 端点被 Google 封了（恒 403，与出口无关）；
  # brave/duckduckgo/qwant 是间歇性机器人判定。bing 是稳定可用的第二来源 ——
  # 少了它，普通搜索就只剩 google cse 一个来源（见附录「哪些引擎真的出得来结果」）。
  - name: bing
    disabled: false
```

四个「为什么」：

1. **`use_default_settings`**：不写全量配置，只写差异，SearXNG 会把默认值和你这份递归合并。
   这里用**映射写法**而不是 `true`，是为了能用下面的 `engines.remove`。
2. **`engines.remove: [ahmia, torch]`**：这两个默认开启的引擎都需要 Tor。本机没跑 Tor，
   不摘掉的话日志里会一直出现 `can't register engine (loading engine failed)`。
3. **`formats` 加 `json`**：不加的话 `/search?format=json` 直接返回 **403**，MCP 和 Cherry 全都会「能用但搜不出东西」。
4. **`limiter: false`**：官方默认开启限流器，而限流器要连 valkey（Redis 系）。单机回环地址没必要，关掉就省掉一个容器。

> **引擎的"默认状态"分三档，别混为一谈**。下面这三档是本机用
> `curl -s http://127.0.0.1:8080/config` 实测出来的，不是猜的：
>
> | 档位 | settings.yml 里 | 在 `/config` 里？ | `!bang` 能临时激活？ | 本机默认属于这档的 |
> | --- | --- | --- | --- | --- |
> | **启用** | 不写，或 `disabled: false` | 在，`enabled: true` | —— | `brave`、`duckduckgo`、`wikipedia`、`wikidata` |
> | **注册但关闭** | `disabled: true` | 在，`enabled: false` | **能** | `google`、`bing`、`qwant` |
> | **未注册** | `inactive: true` | **不在**（压根不存在） | **不能**，bang 被静默忽略 | `startpage`、`mojeek` |
>
> `inactive` 这档是个**静默陷阱**：引擎根本没注册，`!bang` 不会报错，而是被当成普通词丢掉 ——
> 你会拿到**别的引擎**的结果，却以为那个引擎通了。本机实测：`!startpage` / `!mojeek` 都返回了
> 20 条，但 JSON 里 `results[].engine` 全是 `google cse`。**所以怀疑任何一个 bang 之前，先看
> `results[].engine` 到底是谁。**（默认 settings.yml 里 `inactive: true` 有 89 处。）
>
> 想额外开谁，照葫芦画瓢；两种档位要多写的东西不一样：
>
> ```yaml
> engines:
>   - name: bing        # 「注册但关闭」档：取消 disabled 即可
>     disabled: false
>   - name: startpage   # 「未注册」档：必须显式 inactive: false 才能进入注册流程
>     inactive: false
> ```
>
> 依据：`searx/settings_loader.py` 的 `update_dict(default_engine, user_engine)`（**你的字段覆盖默认的字段**），
> 以及 `searx/engines/__init__.py` 的 `load_engines()` 会把 `inactive is True` 的条目直接跳过。
> 改完务必用 `/config` 核对引擎真的进来了。

同一目录再放一个空的 `limiter.toml`，纯粹为了消掉启动时那句
`missing config file: /etc/searxng/limiter.toml` 警告：

```bash
printf '# limiter 已在 settings.yml 里关闭；此文件仅用于消除警告\n' \
  > "$HOME/Dotfiles/matchaeggtart/config/searxng/limiter.toml"
```

再生成机密文件 `~/Dotfiles/matchaeggtart/config/searxng/searxng.env`：

```bash
# 代理地址从宿主机抄：env | grep -i proxy
cat > "$HOME/Dotfiles/matchaeggtart/config/searxng/searxng.env" <<EOF
SEARXNG_SECRET=$(openssl rand -hex 32)
FORCE_OWNERSHIP=false
HTTP_PROXY=http://127.0.0.1:1080
HTTPS_PROXY=http://127.0.0.1:1080
http_proxy=http://127.0.0.1:1080
https_proxy=http://127.0.0.1:1080
NO_PROXY=localhost,127.0.0.1,::1
no_proxy=localhost,127.0.0.1,::1
EOF
chmod 600 "$HOME/Dotfiles/matchaeggtart/config/searxng/searxng.env"
```

`podman --env-file` 对格式很挑：只能 `KEY=value`，一行一个，不要 `export`、不要加引号。

三组变量的作用：

- **`SEARXNG_SECRET`**：覆盖 `settings.yml` 里的 `server.secret_key`，所以机密不进版本控制。
- **`FORCE_OWNERSHIP=false`**：**rootless 下必设**。镜像默认是 `true`，会让容器在启动时把挂载目录
  `chown` 给容器内的 `searxng` 用户 —— 而 rootless 下那个用户被映射成宿主机的 **subuid**
  （实测 uid `100976`），结果是**你自己的 dotfiles 文件你反而没权限改**（`permission denied`）。
  关掉它，容器改用 ns-root 运行（= 宿主机上的你），读写都正常，属主也不再被动。
- **代理变量（上/下写各一份）**：`--network=host` 下容器要访问宿主机的 `127.0.0.1:1080` 代理才能出网。
  手动 `podman run` 时 podman 会自动从你的 shell 继承注入，**但 Quadlet 是由 systemd 用户管理器拉起的，
  那里没有这些变量**，于是容器直连外网 → 所有引擎 timeout、搜索 0 结果。所以必须显式写进来。
  放这里（而不是 `.container` 里）是因为本文件被 `.gitignore` 忽略，不会把代理地址提交到公开仓库。

> 如果 `SEARXNG_SECRET` 格式写错（例如只写了值、漏了 `SEARXNG_SECRET=`），容器会启动失败并报
> `server.secret_key is not changed`——因为它读到的仍是默认的 `ultrasecretkey`。

生成完**立刻**确认 git 真的忽略它：

```bash
cd "$HOME/Dotfiles"
git check-ignore -v matchaeggtart/config/searxng/searxng.env   # 应打印命中的规则行
git status --short                                             # 只应出现 settings.yml，不该有 searxng.env
```

最后把配置链到位。`config` 这个 stow 包你之前已经装过，重跑一次就会把新加的 `searxng/` 目录纳入：

```bash
cd "$HOME/Dotfiles/matchaeggtart"
stow --target="$HOME/.config" config
ls -l "$HOME/.config/searxng"     # 应指向 ../Dotfiles/matchaeggtart/config/searxng
```

> 如果你的 `01_run_stow.sh` 里有 `rm -rf $HOME/.config/searxng`，记得确认删的是**软链**
> （`rm` 不带尾斜杠只删链接本身，不会动仓库里的真文件）。

---

## 5. 启动容器

```bash
podman run -d \
  --name searxng \
  --restart unless-stopped \
  --network=host \
  -e GRANIAN_HOST=127.0.0.1 \
  -e GRANIAN_PORT=8080 \
  -v "$HOME/.config/searxng:/etc/searxng:Z" \
  -v searxng-cache:/var/cache/searxng:Z \
  --env-file "$HOME/.config/searxng/searxng.env" \
  docker.io/searxng/searxng:latest
```

逐项说明：

| 参数 | 作用 |
| --- | --- |
| `--network=host` | 让容器直接共用宿主机的网络栈。**本机必须**：你的机器靠本地代理 `127.0.0.1:1080` 出网，而 podman 默认的 pasta 网络里容器看到的 `127.0.0.1` 是它自己，够不到宿主机的代理（症状：日志刷 `Failed to connect ... over proxy 127.0.0.1`、搜索 0 结果） |
| `-e GRANIAN_HOST=127.0.0.1` | **必须**：镜像默认监听 `::`（所有网卡），在 host 网络下那就等于把 8080 暴露给整个局域网 |
| `-e GRANIAN_PORT=8080` | 监听端口，要和客户端里填的地址一致 |
| `-v .../searxng:/etc/searxng` | 挂载配置目录，让容器读到第 4 步那份 `settings.yml` |
| `-v searxng-cache:/var/cache/searxng` | 命名卷存 favicon 缓存等，可随时丢 |
| `--env-file` | 注入 `SEARXNG_SECRET` / `FORCE_OWNERSHIP=false` |

> 用了 `--network=host` 就**不要再加 `-p`**（会被忽略）。想保留网络隔离，可以改用
> `--network=slirp4netns:allow_host_loopback=true`（需先 `pacman -S slirp4netns`）并把代理改成
> `http://10.0.2.2:1080`；但多一个包、配置更绕，本机回环场景用 host 网络足够。
>
> **为什么一定要挂 `settings.yml`**：如果挂载的目录里没有这个文件，容器**不会报错**，
> 而是自动从内置模板生成一份最小配置（并随机生成一个 `secret_key`）。但那份默认配置
> **既不启用 Google、也不开 JSON**，客户端照样用不了——所以必须放上第 4 步那份。

首次会拉 ~250 MB 镜像（Docker Hub 也有速率限制，拉不动可以换 `ghcr.io/searxng/searxng:latest`）。

等 10~20 秒后：

```bash
podman ps                        # 状态应为 Up
podman logs --tail 30 searxng    # 没有 traceback 即可
ss -tlnp | grep 8080             # 应只看到 127.0.0.1:8080；绝不能是 0.0.0.0:8080 或 :::8080
```

---

## 6. 验证：网页 + JSON + 引擎健康度

**a) 网页能开**：浏览器访问 <http://127.0.0.1:8080>，随便搜一下。

**b) JSON 接口能用**（这是给 Cherry / MCP 用的那条路）：

```bash
curl -sG 'http://127.0.0.1:8080/search' \
  --data-urlencode 'q=arch linux wayland' \
  --data-urlencode 'format=json' \
  | python3 -m json.tool | head -40
```

看到 `"results": [ ... ]` 就对了。返回 **403** → `formats` 里没写 `json`，回第 4 步。

**c) 引擎健康度**：用 bang 语法强制只走某一家（`!go` 是 google 引擎的 shortcut）：

```bash
curl -sG 'http://127.0.0.1:8080/search' \
  --data-urlencode 'q=!go arch linux' \
  --data-urlencode 'format=json' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);[print(r["engine"],"|",r["title"][:70]) for r in d["results"][:5]]'
```

**看 `results[].engine`，别只看条数** —— `inactive` 引擎的 bang 会静默失效，条数再好看也是别的引擎给的（第 4 节）。

> **⚠️ 但 `!go` 这一条不要当验收标准。** 本机实测（2026-10，镜像 `2026.10.4+d48c4b555`）：`!go`
> 恒为 **0 条**、报 `access denied`。根因在**上游**：这版 `google` 引擎请求的是
> `https://www.google.com/wml/search`（Nokia 功能机 WML 界面，见 `searx/engines/google.py` 的
> `google_request()`），而 Google 已经封了这个老端点。对照实验（**同一条代理、同一台机器**）证明
> 这跟你的出口 IP 无关：
>
> ```bash
> P=http://127.0.0.1:1080
> # ① SearXNG 的打法：/wml/search + Nokia UA  → 403
> curl -s -x $P -o /dev/null -w '%{http_code}\n' \
>   -A 'Nokia6230/2.0 (05.50) Profile/MIDP-2.0 Configuration/CLDC-1.1' \
>   'https://www.google.com/wml/search?q=test'
> # ② 浏览器的打法：/search + Chrome UA      → 200（说明 IP 正常的很）
> curl -s -x $P -o /dev/null -w '%{http_code}\n' \
>   -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' \
>   'https://www.google.com/search?q=test'
> # ③ 换个头再打同样的端点              → 还是 403（判别因素是端点，不是 UA）
> ```
>
> 所以**实例是否健康，看这两样**：`results` 不为空 + `unresponsive_engines` 清单：
>
> ```bash
> curl -sG 'http://127.0.0.1:8080/search' --data-urlencode 'q=test' --data-urlencode 'format=json' \
>  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("结果数:",len(d["results"]));print("掉线引擎:",d.get("unresponsive_engines"))'
> ```
>
> 有结果 + 有掉线引擎 = 正常；0 结果且全是 timeout = 代理没通。
> （刚 `restart` 完的**第一条**查询可能因为冷启动整批 timeout —— 再查一次再下结论。）

---

## 7. 让它常驻、开机自启（推荐 Quadlet）

上一步的 `--restart unless-stopped` 在 rootless 下**只在容器被 systemd 托管时才真正生效**。
Arch 上现在的最佳实践是 **Podman Quadlet**：写一个 `.container` 文件，systemd 自动生成服务单元。

> **前置条件：镜像必须先在本机（实测踩过）。** Quadlet 生成的 unit 是由 **systemd 用户管理器**
> 拉起 podman 的，那个上下文里**没有**你 shell 里的 `HTTP(S)_PROXY` —— 代理是桌面会话注入的，
> `systemctl --user show-environment` 里根本看不到它（`loginctl enable-linger` 后更是开机就起，
> 永远拿不到）。而本机对 `registry-1.docker.io` 的 DNS 是被污染的（解析成 `108.160.163.102`、
> `162.125.32.13` 这类假地址，直连必然超时）。两件事叠加，如果本地还没有镜像，第一次
> `systemctl --user start` 就会去直连 Docker Hub 拉取 → 卡约 30 秒 → 失败 → 因为 `Restart=always`
> 进入**无限重启**：`status` 永远停在 `activating`，restart counter 一路往上涨。
>
> 所以**先在一个带代理的 shell 里把镜像拉下来**（Quadlet 的 pull policy 默认是 `missing`，
> 镜像在手就不会再拉）：
>
> ```bash
> podman pull docker.io/searxng/searxng:latest   # 必须在这个带 HTTP(S)_PROXY 的交互式 shell 里跑
> podman images                                   # 确认能看到 searxng/searxng
> ```
>
> **就算你跳过了第 5 步，这一步也不能省** —— 第 5 步的价值不只是"验证能不能跑"，它同时是全程
> 唯一一次在带代理的上下文里拉镜像。拉完之后先 `systemctl --user reset-failed searxng.service`
> 清掉失败计数，再往下走。

先删掉第 5 步手动跑的容器（没跑过第 5 步的话这句会报 `no container with name or ID "searxng" found`，无害）：

```bash
podman rm -f searxng
```

新建 `~/.config/containers/systemd/searxng.container`。**但它和前面那些配置一样，放进 Dotfiles 更省事** ——
否则换机重装时这一步是"手工重敲"，而且它不在版本控制里，跟其它东西不对称：

```bash
mkdir -p "$HOME/Dotfiles/matchaeggtart/config/containers/systemd"
$EDITOR "$HOME/Dotfiles/matchaeggtart/config/containers/systemd/searxng.container"
```

写完把 `config` 包重跑一次 stow，让它被纳入：

```bash
cd "$HOME/Dotfiles/matchaeggtart"
stow --target="$HOME/.config" config
readlink -f "$HOME/.config/containers/systemd/searxng.container"   # 应指向 Dotfiles 里那个文件
```

> 上面这条 stow 会把 `~/.config/containers/systemd` 做成**软链**指向 Dotfiles。不用担心 ——
> Quadlet 生成器**能穿过软链**读 `.container`（实测：`daemon-reload` 后 `systemctl --user cat searxng.service`
> 第一条仍是 `# Automatically generated by /usr/lib/systemd/user-generators/podman-user-generator`）。
> 但要注意 `~/.config/containers/` 同时也是 podman 放自己的 `containers.conf` 等文件的地方，
> 所以**不要**拿 `rm -rf ~/.config/containers` 去清 —— 要清就清 `~/.config/containers/systemd` 这一层
> （`01_run_stow.sh` 里加的就是这一层）。

```ini
[Quadlet]
DefaultDependencies=false

[Unit]
Description=SearXNG metasearch engine (rootless Podman)

[Container]
Image=docker.io/searxng/searxng:latest
ContainerName=searxng
Network=host
Environment=GRANIAN_HOST=127.0.0.1
Environment=GRANIAN_PORT=8080
Volume=%h/.config/searxng:/etc/searxng:Z
Volume=searxng-cache:/var/cache/searxng:Z
EnvironmentFile=%h/.config/searxng/searxng.env

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
```

> **`[Quadlet] DefaultDependencies=false` 是必需的（实测踩过）**：默认情况下 Quadlet 会给用户级 unit 加上
> `Wants=/After=podman-user-wait-network-online.service`，而那个 helper 的实现是
> `until systemctl is-active network-online.target; do sleep 0.5; done`。
> 本机没有任何东西会在开机时拉起系统的 `network-online.target`，于是 helper 死等到它自己的
> **90 秒超时**才失败，`searxng.service` 才接着启动 —— 表现就是「`systemctl --user start` 静默卡约 90 秒」。
> 加上这一节后那两行依赖会被去掉（已用 generator `--dryrun` 实测：其余依赖不变，无副作用）。

启动：

```bash
loginctl enable-linger "$USER"      # 没登录也保持用户服务运行（开机自启的前提）
systemctl --user daemon-reload      # 让 generator 读取 .container 生成 .service
systemctl --user start searxng.service
systemctl --user status searxng.service
```

> `systemctl --user start` 是**同步且静默**的：它会一直等到 unit 变 `active` 才返回，过程中**不打印任何东西**。
> 看起来像卡住时先别急着 `Ctrl+C` —— `Ctrl+C` 只中断你这条命令，**systemd 的 job 仍会继续执行**。
> 想立刻拿回终端就用 `systemctl --user start --no-block searxng.service`，再用 `status` 看结果。

四个容易困惑的点：

- Quadlet 生成的服务对 systemd 来说是「瞬态单元」，**不能也不需要 `systemctl --user enable`**。`[Install] WantedBy=default.target` 会由 generator 在 `daemon-reload` 时自动生效。
- 单元名是 `searxng.service`（由 `searxng.container` 生成），容器的实际名字由 `ContainerName=` 决定。
- 改了 `.container` 文件后要再 `systemctl --user daemon-reload`，然后 `systemctl --user restart searxng.service`。
- **代理变量必须写进 `searxng.env`**（第 4 步）。从手动 `podman run` 换成 Quadlet 后，容器不再继承
  你 shell 的 `HTTP(S)_PROXY`，症状是「服务正常启动、网页能开，但搜什么都 0 结果」，
  `/search?format=json` 里 `unresponsive_engines` 全是 `timeout`。

可选：想让它自动跟进镜像更新，在 `[Container]` 加一行 `AutoUpdate=registry`，再开 `systemctl --user enable --now podman-auto-update.timer`。

---

## 8. 接入两个客户端

### 8.1 Cherry Studio（原生支持，最简单）

1. 打开「设置 → 网络搜索」。
2. 「搜索服务商」选 **SearXNG**。
3. 地址填：`http://127.0.0.1:8080`
4. 保存，随便问一个需要实时信息的问题测试。

注意：

- 地址**要带 `http://` 前缀**，别只填 `127.0.0.1:8080`。
- Cherry 读的是 JSON 接口——第 4 步已经打开，不用再管。
- Cherry 若是 Flatpak 安装，默认共享宿主网络，一般能访问 `127.0.0.1`；若不行，给它的 flatpak 授权加 `--share=network`。

### 8.2 opencode（走 MCP）

用官方查得到的开源 MCP 服务器 [`mcp-searxng`](https://github.com/ihor-sokoliuk/mcp-searxng)。你的机器 Node 是 v24，满足它「Node ≥ 22」的要求。

编辑 `~/.config/opencode/opencode.jsonc`，**保留原有字段**，加上 `mcp` 段：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "deepseek/deepseek-flash",
  "update": "disable",
  "mcp": {
    "servers": {
      "searxng": {
        "type": "local",
        "command": ["npx", "-y", "mcp-searxng"],
        "environment": {
          "SEARXNG_URL": "http://127.0.0.1:8080"
        },
        "timeout": {
          "startup": 60000
        }
      }
    }
  }
}
```

要点：

- **V2 的 MCP 结构是 `mcp.servers`**（不是 V1 那样把服务器名直接挂在 `mcp` 下面）。
- `SEARXNG_URL` 填 SearXNG 的**根地址**，不带 `/search`、不带尾斜杠；`mcp-searxng` 自己拼接口路径。
- `timeout.startup` 放大到 60s：第一次 `npx` 要下载包，默认 30s 可能超时。
- 该 MCP 会暴露 4 个工具，最常用的是 `searxng_web_search`；在 opencode 的 Code Mode 下调用名字是 `tools.searxng.searxng_web_search(...)`。

验证：

```bash
opencode service restart          # 先让后台服务重读配置
opencode mcp list                 # 第一次可能显示 No MCP servers configured —— 再跑一次
```

> **`opencode mcp list` 的坑（实测）**：MCP 连接是**按目录懒建立**的。在某个目录**第一次**跑它，
> 常常会抢在连接建立之前打印 `No MCP servers configured` —— 即使配置完全正常；**再跑一次**就会看到
> `○ searxng pending`，连上后变 `✓ searxng connected`。所以别拿第一次的输出下结论。
>
> 想看**服务端的真实状态**，用 API（最权威，不受 CLI 文案影响）：
>
> ```bash
> opencode api get /api/mcp
> # {"location":{"directory":"..."},"data":[{"name":"searxng","status":{"status":"connected"}}]}
> ```
>
> TUI 里也可以用 `/mcps` 看。上游相关 issue：`anomalyco/opencode#50725`（`mcp list` 与 `/api/mcp` 不一致）。

进 TUI 后也可以用 `/mcps` 查看连接状态、连接/断开服务器。

> 如果 `npx` 方式一直超时：改成全局预装再指向绝对路径，避免每次冷启动。

```bash
npm install -g mcp-searxng
```

> 然后把 `command` 换成全局 bin 的绝对路径（你的 nvm 前缀是 `~/.nvm/versions/node/v24.21.0/bin/mcp-searxng`）。
> 注意：nvm 的路径带 Node 版本号，将来升级 Node 后要回来改。
>
> **opencode 不会在 SearXNG 和别的服务商之间自动故障转移。** 内置 `websearch` 的「自动换一家」只在它
> 自带的 4 家（Exa / Firecrawl / Parallel / Tavily）之间、且**只在 HTTP 429 限流时**触发，它压根不知道
> SearXNG 的存在。SearXNG 只是一个普通 MCP 工具，失败时 opencode 不会去调别的搜索服务商。
> SearXNG 自己的降级是**引擎级**的（DDG 出验证码时其它引擎照常返回，见 `unresponsive_engines`）；
> 但代理/专线整体挂掉时所有引擎会一起超时、返回 0 结果 —— 而那时任何云端搜索服务商同样出不了网，
> 所以这个场景没有兜底可言。判断方法：
>
> ```bash
> curl -sG 'http://127.0.0.1:8080/search' --data-urlencode 'q=test' --data-urlencode 'format=json' \
>  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("结果数:",len(d["results"]));print("掉线引擎:",d.get("unresponsive_engines"))'
> ```
>
> 有结果但有掉线引擎 = 正常；0 结果且全是 timeout = 代理问题。

### 8.3（可选）顺手告诉技能：优先用它

在 `~/.config/opencode/skills/flan-legion-env/SKILL.md` 的「加载时机」后面加一段，让 agent 在英文/技术类检索时优先调这个工具：

```markdown
## Search / 搜索

- For English or technical lookups, prefer the SearXNG search tool
  (`tools.searxng.searxng_web_search`, backed by Google) over the built-in
  websearch providers.
- 英文或技术类查询，优先用 SearXNG 搜索工具（内含 Google 引擎），而不是内置搜索。
```

> 建议先确认 `opencode mcp list` 显示 `connected` 再加这段，否则技能会指向一个不存在的工具。

---

## 9. 排错速查

| 现象 | 原因 / 处理 |
| --- | --- |
| 容器反复重启，日志 `server.secret_key is not changed` | `searxng.env` 格式错（缺少 `SEARXNG_SECRET=` 前缀，或值不是 64 位 hex）。自检：`head -c 15 ~/.config/searxng/searxng.env` 应输出 `SEARXNG_SECRET=` |
| 服务一直 `activating`、无限重启，日志 `Trying to pull ... registry-1.docker.io: ... i/o timeout` 或 `connection refused` | 本机 DNS 把 `registry-1.docker.io` 污染成了假 IP，而 Quadlet 由 systemd 用户管理器拉 podman，那儿**没有**你 shell 的代理 → 拉不动镜像。处理：在一个带 `HTTP(S)_PROXY` 的 shell 里 `podman pull docker.io/searxng/searxng:latest`，然后 `systemctl --user reset-failed searxng.service` 再 restart（见第 7 步） |
| 改 dotfiles 里的 `settings.yml` 报 `Permission denied`，`ls -ln` 看到属主是 `100976` 之类 | `FORCE_OWNERSHIP` 把文件 chown 成了 subuid。先加 `FORCE_OWNERSHIP=false`，再 `podman unshare chown -R 0:0 <该目录>` 抢回属主 |
| 日志刷 `Failed to connect ... over proxy 127.0.0.1`（手动 `podman run` 场景） | 容器够不到宿主机的本地代理。改用 `--network=host` + `-e GRANIAN_HOST=127.0.0.1`（第 5 步） |
| 服务正常、网页能开，但搜什么都 **0 结果**，日志里各引擎 `Timeout` | Quadlet 场景下容器没继承代理变量。把 `HTTP(S)_PROXY`/`NO_PROXY` 写进 `searxng.env`（第 4 步）后 `systemctl --user restart searxng.service` |
| 日志 `ahmia: can't register engine` / `torch: can't register engine` | 这两个引擎要 Tor。用 `use_default_settings.engines.remove` 摘掉（第 4 步） |
| 日志 `missing config file: /etc/searxng/limiter.toml` | 无害警告。放一个空的 `limiter.toml` 即可消除（第 4 步） |
| 日志 `ERROR:searx.botdetection: X-Forwarded-For nor X-Real-IP header is set!` | 无害噪音，**不用管**。SearXNG 假设自己跑在反向代理后面，靠 `X-Forwarded-For` / `X-Real-IP` 头判断真实客户端 IP；你直连 `127.0.0.1:8080`，两个头都没有，它就报一声。`searx/webapp.py` 里 `app.wsgi_app = ProxyFix(app.wsgi_app)` 是**无条件**挂的，所以和 `limiter: false` 无关；代码会回退用 `REMOTE_ADDR`（= 127.0.0.1），且 `botdetection/_helpers.py` 里的 `log_error_only_once` 保证每个进程只打一次。日志级别 `LOG_LEVEL_PROD = logging.WARNING` 是硬编码的，没有配置项可关 |
| 日志出现 `settings.yml does not exist, creating from template` | 没挂到你的 `settings.yml`（路径写错）。此时默认 JSON 是关的，按第 4 步补上并重启 |
| 改了配置但不生效 | 忘重启：`podman restart searxng`；Quadlet 场景是先 `daemon-reload` 再 `restart`。改 `--env-file` 则必须 `podman rm -f` 后重建 |
| `systemctl --user start searxng.service` 静默卡约 **90 秒** | Quadlet 隐式等待系统的 `network-online.target`，而本机没人拉它。在 `.container` 加 `[Quadlet] DefaultDependencies=false`（第 7 步） |
| `systemctl --user start` 看起来永久卡住 | 它只是同步等待、不打印；`Ctrl+C` 不会取消 job。用 `systemctl --user status searxng.service` 和 `journalctl --user -u searxng.service -n 40` 看真实情况 |
| `curl ... format=json` 返回 **403** | `search.formats` 没加 `json`（第 4 步） |
| `!go` 恒为 0 条、`unresponsive_engines` 里 `google: access denied` | **上游 SearXNG 的问题，不是你的配置、也不是你的 IP**：这版 `google` 引擎走 `https://www.google.com/wml/search`（Nokia 功能机 WML 界面），Google 已封该端点。实测同一条代理下 `/wml/search` → 403、普通 `/search` → 200。配置层面无解 —— 等上游修（镜像 `latest` 现在就是最新的 `2026.10.4`，先 `podman pull` 试试有没有新版本），日常用 `google cse` 顶（第 6 节 c） |
| `brave: too many requests` / `duckduckgo: CAPTCHA` / `qwant: CAPTCHA` | 这些是**客户端行为触发的机器人判定，不是 IP 被拉黑**：实测同一条出口用普通 HTTP 请求能从 DDG 拿到 **11 条真结果**（附录）。DDG 报的 `CAPTCHA` 是 DDG **自己的** `challenge-form` 图灵测试（`searx/engines/duckduckgo.py` 的 `is_ddg_captcha()` 就是找 `//form[@id='challenge-form']`），**不是** Google 的 reCAPTCHA。SearXNG 是个"无 cookie、无 JS"的 HTTP 客户端，会被**间歇性**挑战。**没有配置开关能关** —— 逐个试过 UA、`Sec-Fetch` 头、`kl` 地区、关掉全局 Chrome TLS 伪装，样本一多还是被挑战（见附录）。实测最稳的替代是 `bing`（第 4 节） |
| 日志里各引擎零星 `CAPTCHA`/`timeout`，结果时好时坏 | 元搜索的正常波动：一家被挡，别家照常返回。这就是 `unresponsive_engines` 存在的意义 —— 它列出的是**掉队的那几个**，不是失败 |
| 端口被占用 | 改 `-e GRANIAN_PORT=8099` 并同步改客户端地址。**不要**用 `-p`——host 网络下它会被忽略 |
| Cherry 连不上 | 地址缺 `http://`；或 flatpak 未共享网络 |
| `opencode mcp list` 显示失败/超时 | 先手动跑 `npx -y mcp-searxng` 看能否启动；确认 `SEARXNG_URL` 可 curl；或改全局安装 + 绝对路径 |

看日志、进容器排查：

```bash
podman logs -f searxng
podman exec -it --user root searxng /bin/sh -l
```

---

## 10. 维护

```bash
# 升级到最新镜像（Quadlet 场景）
podman pull docker.io/searxng/searxng:latest
systemctl --user restart searxng.service

# 固定版本（推荐生产用法）：把 Image 换成带日期的 tag，例如
#   docker.io/searxng/searxng:2026.9.29-4e2c1ea7f

# 备份：只需要这两样，缓存可丢
#   settings.yml           （在 dotfiles 仓库里，跟着 git 走）
#   searxng.container      （同上，也已经 stow 进 dotfiles）
#   searxng.env            （被 gitignore 的机密文件，记得单独备份！）

# 彻底卸载
systemctl --user stop searxng.service
rm ~/Dotfiles/matchaeggtart/config/containers/systemd/searxng.container  # Quadlet 定义（真文件在 dotfiles 里）
rm ~/.config/containers/systemd                                          # 断掉 stow 留下的那条软链
rmdir ~/.config/containers 2>/dev/null                                   # 里面没别的东西就一起删
systemctl --user daemon-reload
podman rm -f searxng
podman volume rm searxng-cache
```

---

## 11. 安全清单

- 用 `--network=host` 时**必须**配 `-e GRANIAN_HOST=127.0.0.1`；否则 granian 默认的 `::` 会把
  8080 暴露到局域网。复核方式：`ss -tlnp | grep 8080` 应只出现 `127.0.0.1:8080`。
- `public_instance: false`，不要开。
- `secret_key` 只存在于 `searxng.env`，不进公开的 Dotfiles 仓库。
- `FORCE_OWNERSHIP=false` 之后容器以 ns-root 运行（= 宿主机的你）。可接受，但如果想更保守，
  删掉这一行并接受「容器每次启动会 chown 配置目录」，或改用 `--userns=keep-id:uid=977,gid=977`。
- 如果要给局域网/公网用：别用 host 网络，改回端口映射，并加反向代理 + HTTPS + `limiter: true` + valkey + 认证。
- 定期 `podman pull` 跟进安全更新。

---

## 附：命令速查

```bash
sudo pacman -S podman                                   # 装
openssl rand -hex 32                                    # 生成密钥
podman ps / podman logs -f searxng / podman exec ...    # 看状态/日志/进容器
curl -sG http://127.0.0.1:8080/search \
     --data-urlencode 'q=test' --data-urlencode 'format=json'   # 测接口
systemctl --user {start,stop,restart,status} searxng.service    # Quadlet 管理
opencode mcp list                                       # 看 MCP 连接
```

## 附：SearXNG 到底用了哪些引擎

SearXNG 是**元搜索**：一次查询同时发给很多引擎，再对结果去重、加权、合并。它**不是**只搜 Google。
本机实例实测：**261 个引擎定义，82 个已启用**；网页类（`general`/`web`）里默认启用的有
`brave`、`duckduckgo`、`wikipedia`、`wikidata` 等十几个（剩下的默认状态见第 4 节那张三档表）。
本配置做的事：**把默认关闭的 `google` 和 `bing` 打开**，外加摘掉两个需要 Tor 的引擎。

查你实例的真实启用情况：

```bash
curl -s http://127.0.0.1:8080/config | python3 -c 'import sys,json;d=json.load(sys.stdin);print(sorted({e["name"] for e in d["engines"] if e.get("enabled") and ({"general","web"} & set(e.get("categories",[])))}))'
```

**只想走某一家**：查询里加 bang —— `!go`(google)、`!br`(brave)、`!ddg`(duckduckgo)、`!wp`(wikipedia)、`!bi`(bing)。
注意 `inactive` 引擎（如 `startpage`/`mojeek`）的 bang **既不生效也不报错**，你会静默拿到别的引擎的结果
（第 4 节：先看 `results[].engine`）。

### 本机实测：哪些引擎真的出得来结果（2026-10）

出口是 VPN（hiddify）时，逐家实测的结果（不是推断）：

| 类别 | 引擎 | 说明 |
| --- | --- | --- |
| ✅ 能出结果 | `google cse`、`bing`、`mwmbl`、`wiby`、`privacywall`、`resulthunter`、`quark`、`zapmeta` | `google cse` 默认开着；**`bing` 默认关着但实测能用，是性价比最高的补充**；后面几家是小众/聚合器，质量自己掂量 |
| ❌ 被挡 | `google`(403)、`brave`(429)、`duckduckgo`(CAPTCHA)、`qwant`(CAPTCHA)、`yep`(403)、`sogou`(崩溃) | 见第 9 节：`google` 是**上游端点被 Google 封了**（换任何出口都没用）；其余是**客户端行为**触发的间歇性机器人判定 —— 同一条出口的原始请求能正常拿到结果，所以别急着怪出口 IP |

### 一个走过弯路才排除的嫌疑人：Chrome TLS 伪装

`searx/network/client.py` 里写着 `DEFAULT_IMPERSONATE = "chrome"` —— **SearXNG 默认给所有引擎请求套上 Chrome 的 TLS 指纹**（`google` 引擎则自己覆盖成 `chrome99_android`）。看起来很像"DDG 挑战 Chrome 指纹"的元凶，但：

- 实测同样一组请求头，`impersonate="chrome"` 与不伪装**都能拿到 11 条结果**；
- 这个值**在 `settings.yml` 里改不动** —— 试过给引擎加 `impersonate: "none"`，行为毫无变化。原因是
  `searx/search/processors/abstract.py` 的 `get_params()` 只返回一个**固定字段集**，引擎级配置里的
  `impersonate` 根本不会被读进 `params`；只有引擎模块自己在代码里写 `params["impersonate"] = ...` 才有效。

结论：这条路是死胡同，别再试了。DDG 的挑战是**概率性**的（同一组参数连打，前几次成功、后面开始 202 challenge），
换 UA / TLS / 地区都只是抖动，不是开关。
| ⚠️ 注册了但返回 0 条 | `yahoo`、`yandex`、`seznam`、`mozhi`、`fastbot`、`searchmysite`、`boardreader`、`baidu`、`encyclosearch`、`vuhuv` | bang 是生效的，引擎就是没给结果 |
| ⚠️ `inactive`：bang 被静默忽略 | `startpage`、`mojeek` | 见第 4 节 |

**所以"怎么才不被挡"的答案**：配置层面**做不到**让 `google`/`brave`/`duckduckgo` 恢复 ——
`google` 是上游端点被 Google 封了（和出口无关），`brave`/`duckduckgo`/`qwant` 是间歇性的机器人判定
（**不是** IP 被拉黑，换出口未必有用）。现实的解法是**多开几家能用的**：把 `bing` 打开（第 4 节），
普通搜索就从"只有 `google cse` 一个来源"变成两个 —— 本配置已经这么做了，实测
`arch linux wayland` 一次返回 **30 条 = google cse 20 + bing 10**。

**想让某家排前面**：在 `settings.yml` 的 `engines` 里给它 `weight`（默认 1.0）：

```yaml
engines:
  - name: google
    disabled: false
    weight: 1.5
```

> **别去折腾 Google 官方那个 "Custom Search JSON API"**：它对**新用户已关闭**，且将在
> **2027-01-01 关停**。而且 SearXNG 的 `google cse` 引擎**根本不用它** —— 它走的是 CSE 的 element
> 接口，`CX` 硬编码为第三方（blackle.com）的公共 CSE ID，`require_api_key: False`，**没有可配的 key**。
> 代价是这类查询会经过那个公共 CSE ID，隐私上略弱于自建，但不受配额和验证码影响。

## 参考

- SearXNG 容器安装：<https://docs.searxng.org/admin/installation-docker.html>
- SearXNG `use_default_settings` 合并规则：<https://docs.searxng.org/admin/settings/settings.html>
- mcp-searxng：<https://github.com/ihor-sokoliuk/mcp-searxng>
- opencode MCP 配置：<https://opencode.ai/v2/docs/mcp-servers>
- opencode Websearch（为什么只能走 MCP）：<https://opencode.ai/v2/docs/websearch>
- Podman Quadlet：<https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html>
