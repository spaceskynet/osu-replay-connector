# osu replay connector

用于接力游玩谱面时拼接多个人的回放文件的工具

[English](README.md)

## 使用方式

> PS: 注意合成的回放需要手动修正 300 个数等数据（不过使用 <a href="https://github.com/Wieku/danser-go">DANSER</a> 导出可以避免这个问题）

```shell
usage: main.py [options]

osu replay connector by SpaceSkyNet

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  the config file path, defaults to `./config.toml`
  -o OUTPUT, --output OUTPUT
                        the output replay path, defaults to `./merged.osr`
```

### 使用的例子

```shell
# 使用默认配置文件路径和输出回放路径
./main.py 

# 使用 `settings.toml` 作为配置文件和 `replay.osr` 作为输出回放的名称
./main.py -f settings.toml -o replay.osr
```

## 配置文件

默认文件名为 `config.toml`.

回放文件路径列表按照打图的时间顺序排列，拼接的时间节点建议使用 `Circleguard` 等工具查看时间节点附近回放比较重合的部分作为拼接的时间节点（建议两个回放的光标距离不超过一个 note 的直径，也最好选择没有按键的时间段）

![Circleguard](assets/Circleguard.png)

时间节点的格式支持 `HH:MM:SS.MS`、`MM:SS.MS`、`SS.MS`、`HH:MM:SS`、`MM:SS`、`SS`, 像上方 `Circleguard` 的时间可写为 `00.116125`.

> PS：回放文件路径列表个数比拼接的时间节点个数多一（很自然）

### 配置文件样例:

```toml
# 输出的回放文件中的用户名
REPLAY_USERNAME = "ALL"
# 输出的回放文件的 Mods (HDNF, etc.)
REPLAY_MODS = "NF"
# 回放文件路径列表
REPLAY_PATH_LIST = [
	"./test/0.osr",
	"./test/1.osr", 
	"./test/2.osr",
	"./test/3.osr",
	"./test/4.osr",
	"./test/6.osr",
	"./test/7.osr",
	"./test/8.osr",
	"./test/9.osr",
	"./test/10.osr", 
]
# 回放文件需要加上的偏移（相当于全局偏移）
REPLAY_OFFSETS = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
# 拼接的时间节点列表
CUT_TIME_LIST = [
	'0:30.208', 
	'1:11.511', 
	'1:33.545', 
	'1:55.877',
	'2:16.469', 
	'2:53.918',
	'3:10.000',
	'4:13.195',
	'4:35.800', 	
]
```

