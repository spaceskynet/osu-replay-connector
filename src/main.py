#!/usr/bin/env python3
#-*- coding: utf-8 -*-
# By: SpaceSkyNet
import os, copy, toml, argparse, colorama, datetime
from colorama import Fore, Back, Style
from typing import List, Optional
from osrparse import Replay, ReplayEvent, Mod, GameMode

MAX_TIME_DIFF = 50 # 搜索的最大时间差（毫秒）
MAX_DISTANCE = 60 # 光标之间最大距离（一个 note 的直径大约为 50）
ERROR_SHOW_COUNT = 5 # 出错时展示的帧的个数
START_POS = 0 # 去除开头奇怪的帧（如果你的回放都是某些奇怪的客户端导出来，并且多余的帧都一样的话)，不过不去除一般来说也没问题（只要你的切分时间点是正确的）

def print_error(text: str) -> str:
    print(f"{Fore.RED}[Error]{Style.RESET_ALL} {text}\n")

def print_warning(text: str) -> str:
    print(f"{Fore.YELLOW}[Warning]{Style.RESET_ALL} {text}")

def print_info(text: str) -> str:
    print(f"{Fore.GREEN}[Info]{Style.RESET_ALL} {text}")

def lower_bound(nums: List, target: int) -> int:
    """用于在指定范围内查找不小于目标值的第一个元素

    Args:
        nums (List): 要用于查找的数组
        target (int): 要查找的数值

    Returns:
        int:  return the target lower bound index in nums
    """
    first, last = 0, len(nums)
    while first < last:
        mid = first + (last - first) // 2
        if nums[mid] < target:
            first = mid + 1
        else:
            last = mid
    return first

def upper_bound(nums: List, target: int) -> int:
    """用于在指定范围内查找大于目标值的第一个元素

    Args:
        nums (List): 要用于查找的数组
        target (int): 要查找的数值

    Returns:
        int: return the first idx in nums when nums[idx] > target
    """
    first, last = 0, len(nums)
    while first < last:
        mid = first + (last - first) // 2
        if nums[mid] <= target:
            first = mid + 1
        else:
            last = mid
    return first

def duration_format(d: int, colored: bool = False) -> str:
    """视频时长格式化

    Args:
        d (int): 时长（毫秒数）
        colored (bool): 是否着色

    Returns:
        str: 格式化后字符串(HH:MM:SS.MS)
    """
    if d < 0: d = 0
    d = int(d)
    msec = d % 1000
    d = d // 1000
    hour = int(d / (60 * 60))
    dd = int(d % (60 * 60))
    min = int(dd / 60)
    sec = int(dd % 60)
    if colored:
        return "{}{:0>2}{}:{}{:0>2}{}:{}{:0>2}{}.{}{:0>3}{}".format(Fore.GREEN, hour, Style.RESET_ALL, Fore.GREEN, min, Style.RESET_ALL, Fore.GREEN, sec, Style.RESET_ALL, Fore.RED, msec, Style.RESET_ALL)
    return "{:0>2}:{:0>2}:{:0>2}.{:0>3}".format(hour, min, sec, msec)

def duration_unformat(s: str) -> int:
    """视频时长反格式化

    Args:
        s (str): 格式化后字符串

    Returns:
        int: 时长（毫秒数）
    """
    use_msec: bool = '.' in s # 格式化的时间字符串是否使用了毫秒（当有 4 部分或只有 1 部分时此项会被忽略）
    org_s = s
    s = list(map(int, s.replace('.', ':').split(':')))
    hour, min, sec, msec = 0, 0, 0, 0
    if len(s) == 4:
        hour, min, sec, msec = s
    elif len(s) == 3:
        if not use_msec:
            hour, min, sec = s
        else:
            min, sec, msec = s
    elif len(s) == 2:
        if not use_msec:
            min, sec = s
        else:
            sec, msec = s
    elif len(s) == 1:
        sec = s
    else:
        raise NotImplementedError(f"The format of time node({org_s}) is not be supported!")

    duration = msec
    duration += sec * 1000
    duration += min * 1000 * 60
    duration += hour * 1000 * 60 * 60
    return duration

def get_time_nodes(replay_data: List[ReplayEvent])-> List[int]:
    """获取回放数据的时间节点

    Args:
        replay_data (List[ReplayEvent]): 回放数据列表

    Returns:
        List[int]: 回放数据的时间节点列表
    """
    replay_event_time_nodes = []
    delta = 0
    for e in replay_data:
        delta += e.time_delta
        replay_event_time_nodes.append(delta)
    return replay_event_time_nodes

def inner_time_diff(t: int, time_node: int) -> bool:
    return abs(t - time_node) <= MAX_TIME_DIFF

def inner_cursor_diff(x1: float, y1: float, x2: float, y2: float) -> bool:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2 <= MAX_DISTANCE ** 2

def inner_cursor_diff(diff_square: float) -> bool:
    return diff_square <= MAX_DISTANCE ** 2

def cursor_diff_square(x1: float, y1: float, x2: float, y2: float) -> float:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2

def get_cut_index(pre_time_nodes: List[int], pre_data: List[ReplayEvent], 
                  nxt_time_nodes: List[int], nxt_data: List[ReplayEvent], 
                  time_node: int):
    """根据拼接的时间点，在时间点附近找到光标最近时，两个回放数据的各自的下标

    大致的原理：解开各自回放的移动数据，按照给定的排列和时间点，在相邻两个回放的对应时间点向前后寻找距离最近的两个光标位置（当然时间差不能太大），然后以此为标准来拼接，并注意一下按下的键和 offset

    Args:
        pre_time_nodes (List[int]): 前一个回放数据的时间节点列表
        pre_data (List[ReplayEvent]): 前一个回放数据
        nxt_time_nodes (List[int]): 后一个回放数据的时间节点列表
        nxt_data (List[ReplayEvent]): 后一个回放数据
        time_node (int): 拼接的时间点

    Returns:
        两个回放数据的各自的下标及对应光标最小距离
    """
    p, q = upper_bound(pre_time_nodes, time_node), lower_bound(nxt_time_nodes, time_node)
    pre_len, nxt_len = len(pre_time_nodes), len(nxt_time_nodes)
    pre_pos, nxt_pos, min_dis = -1, -1, float("inf")
    if p > 0 and q >= 0:
        i, j = p - 1, q
        while (i > 0 and j > 0) and inner_time_diff(pre_time_nodes[i], time_node) and inner_time_diff(nxt_time_nodes[j], time_node):
            while j + 1 < nxt_len and inner_time_diff(nxt_time_nodes[j + 1], pre_time_nodes[i]): j += 1
            while j > 0 and inner_time_diff(nxt_time_nodes[j], pre_time_nodes[i]) and pre_time_nodes[i] < nxt_time_nodes[j]:
                dis = cursor_diff_square(pre_data[i].x, pre_data[i].y, nxt_data[j].x, nxt_data[j].y)
                if inner_cursor_diff(dis):
                    if dis < min_dis: pre_pos, nxt_pos, min_dis = i, j, dis
                j -= 1
            i -= 1

    if p < pre_len and q + 1 < nxt_len:
        i, j = p, q + 1
        while (i < pre_len and j < nxt_len) and inner_time_diff(pre_time_nodes[i], time_node) and inner_time_diff(nxt_time_nodes[j], time_node):
            while i - 1 > 0 and inner_time_diff(pre_time_nodes[i - 1], nxt_time_nodes[j]): i -= 1
            while i < pre_len and inner_time_diff(pre_time_nodes[i], nxt_time_nodes[j]) and pre_time_nodes[i] < nxt_time_nodes[j]:
                dis = cursor_diff_square(pre_data[i].x, pre_data[i].y, nxt_data[j].x, nxt_data[j].y)
                if inner_cursor_diff(dis):
                    if dis < min_dis: pre_pos, nxt_pos, min_dis = i, j, dis
                i += 1
            j += 1

    if min_dis == float("inf"):
        print_warning(f"Cannot find proper time to merge replay in {duration_format(time_node, True)}")
        print(f"\t{Fore.MAGENTA}Previous{Style.RESET_ALL}: {pre_data[p - ERROR_SHOW_COUNT:p]}")
        print(f"\t{Fore.MAGENTA}Next{Style.RESET_ALL}: {nxt_data[q:q + ERROR_SHOW_COUNT]}\n")
        return p - 1, q, min_dis

    return pre_pos, nxt_pos, min_dis

def merge_replays(replays: List[Replay], cut_times: List[str]) -> List[ReplayEvent]:
    """按照给定的时间节点合并回放文件

    这里输出的时间线信息是指的每一个回放被采用的时间区间，前后范围有 50 ms 以内的误差很正常

    Args:
        replays (List[Replay]): 回放文件列表
        cut_times (List[str]): 时间节点列表

    Returns:
        List[ReplayEvent]:  合并后的回放数据
    """

    cut_indexs = [[0, 0] for _ in replays]
    pre_data = replays[0].replay_data
    pre_time_nodes = get_time_nodes(pre_data)
    
    for i in range(len(replays) - 1):
        time_node = duration_unformat(cut_times[i])
        nxt_data = replays[i + 1].replay_data
        nxt_time_nodes = get_time_nodes(nxt_data)

        p, q, dis = get_cut_index(pre_time_nodes, pre_data, nxt_time_nodes, nxt_data, time_node)

        time_delta = nxt_time_nodes[q] - pre_time_nodes[p]
        assert(time_delta >= 0)
        if dis == float("inf"):
            print_warning(f"{Fore.RED + replays[i].username+ Style.RESET_ALL}'s replay and {Fore.RED + replays[i + 1].username + Style.RESET_ALL}'s replay cannot be connected properly, maybe miss!")

        nxt_data[q].time_delta = time_delta
        cut_indexs[i][1] = p
        cut_indexs[i + 1][0] = q
        # print(time_delta, dis ** 0.5)
        pre_data = nxt_data
        pre_time_nodes = nxt_time_nodes
    
    cut_indexs[-1][1] = len(replays[-1].replay_data) - 1
    # print(cut_indexs)

    replays_data = []
    print_info("Timeline:")
    for i, replay in enumerate(replays):
        l, r = cut_indexs[i]
        data = replay.replay_data
        
        time_nodes = get_time_nodes(data)
        replays_data.extend(data[l:r + 1])
        print(f"\t{duration_format(time_nodes[l], True)}-{duration_format(time_nodes[r], True)}: {Fore.CYAN}{replay.username}{Style.RESET_ALL} + {Fore.BLUE}{unpack_mods(replay.mods)}{Style.RESET_ALL}")

    return replays_data

def unpack_mods(Mods: Mod) -> str:
    """从 Mod（int）变量获取 mods 字符串

    Args:
        mods (Mod): Mod（int）变量

    Returns:
        str:  mods 字符串
    """
    mods_str = ["",  "NF",  "EZ", "TD",  "HD",  "HR",  "SD", "DT", "RX", "HT", "NC", "FL", "AT", "SO", "AP", "PF"] + [""] * 14 + ["V2",  ""]
    mods = ""
    index, m = 1, Mods
    while m and index <= 31:
        if m & 1: mods += mods_str[index]
        m >>= 1
        index += 1
    if not mods: mods += "NM"
    return mods

def pack_mods(mods: str) -> Mod:
    """从 mods 字符串获取 Mod（int）变量

    Args:
        mods (str): mods 字符串

    Returns:
        Mod: Mod（int）变量
    """
    mods_str = ["", "NF", "EZ", "TD",  "HD",  "HR",  "SD", "DT", "RX", "HT", "NC", "FL", "AT", "SO", "AP", "PF"] + [""] * 14 + ["V2",  ""]
    mods_dict = {mod: index for index, mod in enumerate(mods_str)}
    Mods = 0
    mods = mods[:len(mods) // 2 * 2] # ignore odd length string
    for i in range(0, len(mods), 2):
        mod = mods[i : i + 2]
        if mod in mods_str:
            Mods |= 1 << (mods_dict[mod] - 1)
    return Mod(Mods)


def replay_processing(output_path: str = None, config_path:str = None):
    """合并回放文件主逻辑

    Args:
        output_path (str, optional): 输出的回放文件路径. Defaults to None.
        config_path (str, optional): 配置文件路径. Defaults to None.

    Raises:
        TypeError: 回放文件格式无效
        FileNotFoundError: 未找到回放文件
        KeyError: 回放文件的模式不是 std
        ValueError: 回放文件的谱面不一致
    """
    if config_path is None:
        work_dir = os.path.dirname(__file__)
        config_path = os.path.join(work_dir, 'config.toml')
    else:
        work_dir = os.path.dirname(config_path)
    config = toml.load(config_path)
    print_info(f"Load config file from {config_path}.")

    # print(config['OSR_PATH_LIST'], config['CUT_TIME_LIST'])
    try:
        replay_paths = config['REPLAY_PATH_LIST']
        cut_times = config['CUT_TIME_LIST']
        replay_mods = config['REPLAY_MODS']
        replay_username = config['REPLAY_USERNAME']
        replay_offsets = config['REPLAY_OFFSETS'] 
    except Exception:
        raise TypeError(f"Incomplete configuration file!")
    
    if not (len(replay_paths) - 1 == len(cut_times) and len(replay_offsets) == len(replay_paths) and len(cut_times) > 0 and type(replay_mods) == str):
        raise TypeError(f"The configuration file format is invalid, please check whether the length of each list corresponds correctly!")

    replays = []
    beatmap_hashs = set()
    for replay_offset, replay_path in zip(replay_offsets, replay_paths):
        replay_path = os.path.abspath(os.path.join(work_dir, replay_path))
        if not os.path.isfile(replay_path):
            raise FileNotFoundError(f"{replay_path} is not found!")
        replay = Replay.from_path(replay_path)
        if replay.mode != GameMode.STD:
            raise KeyError(f"{replay_path} is not a replay of std map!")
        # 去除奇怪的帧
        replay.replay_data = replay.replay_data[START_POS:]
        # 加上偏移
        replay.replay_data[0].time_delta += replay_offset
        replays.append(replay)

        beatmap_hashs.add(replay.beatmap_hash)
        print_info(f"Beatmap hash: {Fore.RED}{replay.beatmap_hash}{Style.RESET_ALL}, from {replay_path}")
        if len(beatmap_hashs) > 1 or not replay.beatmap_hash:
            raise ValueError("The beatmap hash of replays must be same!")

    replay = copy.deepcopy(replays[0])
    replay.mods = pack_mods(replay_mods)
    replay.username = replay_username
    replay.timestamp = datetime.datetime.now()

    replay_data = merge_replays(replays, cut_times)
    replay.replay_data = replay_data
    
    if output_path is None:
        output_path = os.path.join(work_dir, 'merged.osr')
    else:
        output_path = os.path.abspath(output_path)
    replay.write_path(output_path)
    print_info(f"Write replay file to {output_path} with {Fore.BLUE}{unpack_mods(replay.mods)}{Style.RESET_ALL}.")

if __name__ == "__main__":
    colorama.init()
    parser = argparse.ArgumentParser(description=f"{Fore.MAGENTA}osu replay connector{Style.RESET_ALL} by SpaceSkyNet, more information on {Fore.RED}https://github.com/spaceskynet/osu-replay-connector{Style.RESET_ALL}", usage='%(prog)s [options]')
    parser.add_argument("-f", "--file", type=str, help="the config file path, defaults to `./config.toml`")
    parser.add_argument("-o", "--output", type=str, help="the output replay path, defaults to `./merged.osr`")
    args = parser.parse_args()

    try:
        replay_processing(args.output, args.file)
    except Exception as e:
        print_error(e)
        parser.print_help()