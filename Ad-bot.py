import sys
import os

# 將 lib 資料夾加入到 Python 的模組搜尋路徑中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

import requests
import json
import random
import time
from system.lib.minescript import *
import queue # 為了處理非阻塞的事件佇列

def print_info(message):
    echo(f"§a[INFO]§r {message}")

def print_warning(message):
    echo(f"§e[WARN]§r {message}")

def print_error(message):
    echo(f"§c[ERROR]§r {message}")

def print_success(message):
    echo(f"§b[SUCCESS]§r {message}")

# --- 全域變數 ---
all_contexts = {} # 新的資料結構，用字典管理所有文案列表

# get_context 函式不再需要參數
def get_context(context_type='default'):
    global all_contexts
    target_list = all_contexts.get(context_type)

    # 如果列表為空，返回一個預設訊息
    if not target_list:
        return f"廣告列表 '{context_type}' 為空或不存在。"
        
    text = random.choice(target_list)
    return text


# 將 chat 函式重新命名為 send_discord_message 以避免與 minescript 的內建 chat() 函式衝突
def send_discord_message(chanel_list, authorization_list, content_override=None, context_type='casino'):
    for authorization in authorization_list:
        header = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",
        }
        for channel_id in chanel_list:
            # 如果有提供 content_override，就使用它，否則使用 get_context()
            msg = {
                "content": content_override if content_override is not None else get_context(context_type),
                "nonce": "82329451214{}33232234".format(random.randrange(0, 1000)),
                "tts": False,
            }
            url = "https://discord.com/api/v9/channels/{}/messages".format(channel_id)
            try:
                res = requests.post(url=url, headers=header, data=json.dumps(msg))
                # 檢查請求是否成功 (HTTP 狀態碼 2xx)
                if res.ok:
                    print_success(f"訊息已成功發送至頻道 {channel_id} (狀態碼: {res.status_code})")
                else:
                    # 如果失敗，印出狀態碼和錯誤訊息
                    print_error(f"發送失敗 (狀態碼: {res.status_code}) - 回應: {res.text[:200]}")
            except Exception as e:
                 print_error(f"Error during request: {e}")
            continue
        time.sleep(random.randrange(1, 3))

def get_data_path(filename):
    """獲取資料檔案的絕對路徑，確保在 'data' 子目錄下。"""
    script_dir = os.path.dirname(__file__)
    data_dir = os.path.join(script_dir, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, filename)

def save_contexts(context_type='default'):
    """將指定的文案列表儲存到 JSON 檔案中。"""
    global all_contexts
    if context_type not in all_contexts:
        print_error(f"找不到名為 '{context_type}' 的文案列表，無法儲存。")
        return

    filename = get_data_path(f"{context_type}_contexts.json")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_contexts[context_type], f, ensure_ascii=False, indent=4)
        print_success(f"已將 {len(all_contexts[context_type])} 則 '{context_type}' 文案儲存至 {os.path.basename(filename)}。")
    except Exception as e:
        print_error(f"儲存文案時發生錯誤: {e}")

def load_contexts(context_type='default', silent=False):
    """從 JSON 檔案中載入文案列表。"""
    global all_contexts
    filename = get_data_path(f"{context_type}_contexts.json")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            all_contexts[context_type] = json.load(f)
        if not silent:
            print_success(f"已從 {os.path.basename(filename)} 載入 {len(all_contexts[context_type])} 則 '{context_type}' 文案。")
    except FileNotFoundError:
        if not silent:
            print_warning(f"找不到文案檔案 {os.path.basename(filename)}。")
    except Exception as e:
        if not silent:
            print_error(f"載入文案檔案 {os.path.basename(filename)} 時發生錯誤: {e}")


# --- 全域變數 ---
# 將 channel_configs 提升為全域變數，以便 on_chat 函式可以存取
channel_configs = []

# --- 全域狀態旗標 ---
is_loop_active = False
is_script_running = True
authorization_list = []

# --- 指令列表 ---
HELP_COMMANDS = [
    ("!ad start [別名]", "啟動全部或單一任務的廣告循環。"),
    ("!ad stop [別名]", "停止全部或單一任務的廣告循環。"),
    ("!ad time", "顯示所有任務的詳細狀態。"),
    ("!ad now <別名>", "手動觸發廣告 (別名: random, fixed)。"),
    ("!ad pause <別名>", "暫停或恢復任務 (別名: random, fixed)。"),
    ("!ad interval <別名> <秒數>", "修改任務的發送間隔(秒)。"),
    ("!ad list [類型]", "列出指定類型的文案或所有列表。"),
    ("!ad list add <名稱>", "新增一個新的廣告文案列表。"),
    ("!ad add <類型> <內容>", "新增一則廣告文案。"),
    ("!ad del <類型> <索引>", "刪除指定索引的廣告文案。"),
    ("!ad save [類型]", "將指定類型的文案列表儲存至檔案。"),
    ("!ad load [類型]", "從檔案重新載入指定類型的文案列表。"),
    ("!ad channel add <別名> <頻道ID>", "為任務新增一個發送頻道。"),
    ("!ad channel del <別名> <頻道ID>", "從任務移除一個發送頻道。"),
    ("!ad channel list", "列出每個任務的發送頻道。"),
    ("!ad reload", "重新載入並重置機器人所有設定。"),
    ("!ad leave", "卸載廣告機器人。"),
    ("!ad auth edit <新金鑰>", "修改Discord授權金鑰。"),
    ("!ad help [頁碼]", "顯示此幫助訊息。")
]

def initialize_settings():
    """初始化或重置所有腳本設定。"""
    global all_contexts, channel_configs, authorization_list, is_loop_active, ccalc_config

    is_loop_active = False
    all_contexts.clear()

    authorization_list[:] = ["YOUR_DISCORD_AUTH"]

    # 初始化預設列表
    all_contexts['default'] = []
    load_contexts('default', silent=True)
    if not all_contexts['default']:
        print_warning(f"未找到或無法載入 'default' 廣告，將使用預設列表。")
        all_contexts['default'] = [
            ""
        ]

    channel_configs[:] = [
        {
            "name": "隨機廣告", "alias": "random", "channels": ["CHANNEL_ID"], "context_type": "default",
            "get_interval": lambda: random.randrange(3600, 3900), "next_send_time": 0,
            "announced_milestones": set(), "paused": False, "remaining_on_pause": 0
        },
        {
            "name": "固定廣告", "alias": "fixed", "channels": ["CHANNEL_ID"], "context_type": "default",
            "get_interval": lambda: 86400, "next_send_time": 0,
            "announced_milestones": set(), "paused": False, "remaining_on_pause": 0
        }
    ]

if __name__ == "__main__":
    # 首次啟動時初始化所有設定
    initialize_settings()

    # 設定事件攔截器，讓指令不被其他玩家看見
    event_queue = EventQueue()
    # 將所有 !ad 指令攔截器合併為一個，避免錯誤指令發送到公頻
    event_queue.register_outgoing_chat_interceptor(prefix='!ad')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad time')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad now ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad pause ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad help')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad start')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad stop')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad interval ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad add ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad del ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad list') # list context
    event_queue.register_outgoing_chat_interceptor(prefix='!ad list add ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad save')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad load')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad channel add ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad channel del ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad channel list')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad auth edit ')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad leave')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad reload')
    event_queue.register_outgoing_chat_interceptor(prefix='!ad ccalc ')
    event_queue.register_chat_listener() # 註冊監聽所有傳入的聊天訊息
    print_info("廣告機器人已載入，處於待命狀態。")
    print_warning("請輸入 '!ad start' 來啟動廣告循環，或輸入 '!ad help' 查詢指令。")

    # 主循環：持續處理指令，並在啟動後執行任務
    while is_script_running:
        try:
            # --- 事件處理 ---
            try:
                event = event_queue.get(block=False) # 非阻塞地獲取事件

                # --- 處理玩家指令 ---
                if event.type == EventType.OUTGOING_CHAT_INTERCEPT:
                    message = event.message.strip()
                    
                    # 處理 !ad help [頁碼] 指令
                    if message.lower().startswith('!ad help'):
                        parts = message.split()
                        page = 1
                        try:
                            if len(parts) > 2:
                                page = int(parts[2])
                        except ValueError:
                            page = 1

                        items_per_page = 5
                        total_items = len(HELP_COMMANDS)
                        total_pages = (total_items + items_per_page - 1) // items_per_page

                        if page < 1 or page > total_pages:
                            print_error(f"頁碼無效。請輸入 1 到 {total_pages} 之間的數字。")
                            continue

                        print_info(f"--- 廣告機器人指令列表 (第 {page}/{total_pages} 頁) ---")
                        
                        start_index = (page - 1) * items_per_page
                        end_index = start_index + items_per_page

                        for i in range(start_index, min(end_index, total_items)):
                            command, description = HELP_COMMANDS[i]
                            echo(f"§b{command}§r: {description}")
                        # 新增更完善的分頁提示
                        footer_parts = []
                        if page > 1: footer_parts.append(f"使用 !ad help {page - 1} 查看上一頁")
                        if page < total_pages: footer_parts.append(f"使用 !ad help {page + 1} 查看下一頁")
                        if footer_parts: print_info(" | ".join(footer_parts))
                    # 處理 !ad start [別名] 指令
                    elif message.lower().startswith('!ad start'):
                        parts = message.split()
                        if len(parts) == 2: # !ad start
                            if is_loop_active:
                                print_warning("廣告循環已經在執行中。")
                            else:
                                is_loop_active = True
                                print_success("廣告發送循環已啟動！")
                                # 初始化每個設定的首次發送時間
                                for config in channel_configs:
                                    if not config['paused']: # 只初始化未暫停的任務
                                        interval = config["get_interval"]()
                                        config["next_send_time"] = time.time() + interval
                                        config["announced_milestones"].clear()
                                        print_info(f"設定 '{config['name']}' 的首次發送時間在 {interval/60:.2f} 分鐘後。")
                        elif len(parts) == 3: # !ad start <別名>
                            task_alias_to_start = parts[2].lower()
                            started = False
                            for config in channel_configs:
                                if config['alias'] == task_alias_to_start:
                                    if config['paused']:
                                        config['paused'] = False
                                        config['next_send_time'] = time.time() + config['remaining_on_pause']
                                        config['announced_milestones'].clear()
                                        print_success(f"任務 '{config['name']}' 已恢復。")
                                    else:
                                        print_warning(f"任務 '{config['name']}' 已經在執行中。")
                                    started = True
                                    break
                            if not started:
                                print_error(f"找不到別名為 '{task_alias_to_start}' 的任務。")

                    # 處理 !ad stop [別名] 指令
                    elif message.lower().startswith('!ad stop'):
                        parts = message.split()
                        if len(parts) == 2: # !ad stop
                            is_loop_active = False
                            print_warning("廣告發送循環已停止。")
                        elif len(parts) == 3: # !ad stop <別名>
                            task_alias_to_stop = parts[2].lower()
                            stopped = False
                            for config in channel_configs:
                                if config['alias'] == task_alias_to_stop:
                                    if not config['paused']:
                                        config['paused'] = True
                                        remaining = config['next_send_time'] - time.time()
                                        config['remaining_on_pause'] = remaining if remaining > 0 else 0
                                        print_warning(f"任務 '{config['name']}' 已暫停。")
                                    else:
                                        print_warning(f"任務 '{config['name']}' 已經是暫停狀態。")
                                    stopped = True
                                    break
                            if not stopped:
                                print_error(f"找不到別名為 '{task_alias_to_stop}' 的任務。")
                        else:
                            print_error("指令格式錯誤。請使用 !ad stop 或 !ad stop <別名>")

                    # 處理 !ad time 指令
                    elif message.lower() == '!ad time':
                        print_info("--- 廣告任務詳細狀態 ---")
                        if not is_loop_active and not any(c['paused'] for c in channel_configs):
                            print_warning("廣告循環未啟動。請使用 !ad start 啟動。")
                        
                        for config in channel_configs:
                            status_color = "§e" if config['paused'] else "§a"
                            status_text = "已暫停" if config['paused'] else "執行中"
                            
                            # 獲取當前間隔
                            current_interval = config['get_interval']()
                            interval_text = f"{current_interval} 秒"
                            
                            # 計算剩餘時間
                            if config['paused']:
                                minutes, seconds = divmod(int(config.get("remaining_on_pause", 0)), 60)
                            else:
                                remaining_seconds = int(config.get("next_send_time", 0) - time.time())
                                minutes, seconds = divmod(remaining_seconds, 60) if remaining_seconds > 0 else (0, 0)
                            
                            remaining_text = f"{minutes}分 {seconds}秒"
                            echo(f"§f{config['name']}: {status_color}{status_text}§r | 剩餘: §b{remaining_text}§r | 間隔: §d{interval_text}§r")
                    
                    # 處理 !ad now <任務別名> 指令
                    elif message.lower().startswith('!ad now '):
                        parts = message.split(maxsplit=2)
                        if len(parts) >= 2:
                            task_alias_to_trigger = parts[2].lower() if len(parts) > 2 else ""
                            triggered = False
                            for config in channel_configs:
                                if config['alias'] == task_alias_to_trigger:
                                    print_info(f"收到手動觸發指令，立即為 '{config['name']}' 發送廣告...")
                                    send_discord_message(config["channels"], authorization_list, context_type=config.get('context_type', 'default'))
                                    new_interval = config["get_interval"]()
                                    config["next_send_time"] = time.time() + new_interval
                                    config["announced_milestones"].clear()
                                    print_warning(f"'{config['name']}' 手動發送完畢，下次發送將在 {new_interval/60:.2f} 分鐘後。")
                                    triggered = True
                                    break
                            if not triggered:
                                print_error(f"找不到別名為 '{task_alias_to_trigger}' 的任務。請使用 'random' 或 'fixed'。")

                    # 處理 !ad pause <任務別名> 指令
                    elif message.lower().startswith('!ad pause '):
                        parts = message.split(maxsplit=2)
                        if len(parts) >= 2:
                            task_alias_to_toggle = parts[2].lower() if len(parts) > 2 else ""
                            toggled = False
                            for config in channel_configs:
                                if config['alias'] == task_alias_to_toggle:
                                    # 切換暫停狀態
                                    config['paused'] = not config['paused']
                                    if config['paused']:
                                        # 進入暫停狀態
                                        remaining = config['next_send_time'] - time.time()
                                        config['remaining_on_pause'] = remaining if remaining > 0 else 0
                                        print_warning(f"任務 '{config['name']}' 已暫停。")
                                    else:
                                        # 恢復任務
                                        config['next_send_time'] = time.time() + config['remaining_on_pause']
                                        config['announced_milestones'].clear() # 重置倒數提示
                                        print_success(f"任務 '{config['name']}' 已恢復。")
                                    toggled = True
                                    break
                            if not toggled:
                                print_error(f"找不到別名為 '{task_alias_to_toggle}' 的任務。請使用 'random' 或 'fixed'。")

                    # 處理 !ad interval <別名> <秒數> 指令
                    elif message.lower().startswith('!ad interval '):
                        parts = message.split()
                        if len(parts) != 4:
                            print_error("指令格式錯誤。請使用: !ad interval <別名> <秒數>")
                            continue
                        
                        task_alias_to_modify = parts[2].lower()
                        try:
                            new_interval_seconds = int(parts[3])
                            if new_interval_seconds <= 10: # 增加一個最小值保護，避免過於頻繁
                                print_error("秒數必須大於 10。")
                                continue
                        except ValueError:
                            print_error("秒數必須是有效的整數。")
                            continue

                        modified = False
                        for config in channel_configs:
                            if config['alias'] == task_alias_to_modify:
                                config['get_interval'] = lambda s=new_interval_seconds: s
                                print_success(f"任務 '{config['name']}' 的發送間隔已更新為 {new_interval_seconds} 秒。")
                                modified = True
                                break
                        if not modified:
                            print_error(f"找不到別名為 '{task_alias_to_modify}' 的任務。請使用 'random' 或 'fixed'。")

                    # 處理 !ad list [類型] / !ad list add <名稱> 指令 (已修正)
                    elif message.lower().startswith('!ad list'):
                        parts = message.split()
                        if len(parts) == 2: # !ad list
                            print_info("--- 可用的文案列表 ---")
                            for list_name in all_contexts.keys():
                                print_success(f"- {list_name} (共 {len(all_contexts[list_name])} 則)")
                        elif len(parts) == 4 and parts[2].lower() == 'add': # !ad list add <名稱>
                            new_list_name = parts[3].lower()
                            if new_list_name in all_contexts:
                                print_error(f"名為 '{new_list_name}' 的列表已存在。")
                            else:
                                all_contexts[new_list_name] = []
                                print_success(f"已成功新增空的文案列表 '{new_list_name}'。")
                        elif len(parts) == 3: # !ad list <類型>
                            context_type = parts[2].lower()
                            target_list = all_contexts.get(context_type)
                            print_info(f"--- '{context_type}' 文案列表 ---")
                            if target_list is None:
                                print_error(f"找不到名為 '{context_type}' 的列表。")
                            elif not target_list:
                                print_warning("此列表是空的。")
                            else:
                                for i, text in enumerate(target_list):
                                    echo(f"[{i}]: {text[:50]}...")

                    # 處理 !ad add <類型> <內容> 指令 (已修正)
                    elif message.lower().startswith('!ad add '):
                        parts = message.split(maxsplit=3)
                        if len(parts) < 4:
                            print_error("指令格式錯誤。請使用: !ad add <類型> <內容>")
                            continue
                        context_type = parts[2].lower()
                        new_context = parts[3]
                        if context_type not in all_contexts:
                            print_error(f"找不到名為 '{context_type}' 的文案列表。")
                            continue
                        all_contexts[context_type].append(new_context)
                        print_success(f"已新增文案至 '{context_type}' (目前共 {len(all_contexts[context_type])} 則)。")

                    # 處理 !ad del <類型> <索引> 指令 (已修正)
                    elif message.lower().startswith('!ad del '):
                        parts = message.split()
                        if len(parts) != 4:
                            print_error("指令格式錯誤。請使用: !ad del <類型> <索引>")
                            continue
                        context_type = parts[2].lower()
                        if context_type not in all_contexts:
                            print_error(f"找不到名為 '{context_type}' 的文案列表。")
                            continue
                        target_list = all_contexts[context_type]
                        try:
                            index_to_del = int(parts[3])
                            if 0 <= index_to_del < len(target_list):
                                target_list.pop(index_to_del)
                                print_success(f"已從 '{context_type}' 刪除索引為 {index_to_del} 的文案。")
                            else:
                                print_error(f"索引無效。請輸入 0 到 {len(target_list) - 1} 之間的數字。")
                        except ValueError:
                            print_error("索引必須是有效的數字。")

                    # 處理 !ad save/load [類型] 指令
                    elif message.lower().startswith('!ad save') or message.lower().startswith('!ad load'):
                        parts = message.split()
                        action = parts[1].lower()
                        context_type = parts[2].lower() if len(parts) > 2 else 'default'
                        
                        if action == 'save':
                            save_contexts(context_type)
                        elif action == 'load':
                            load_contexts(context_type)

                    # 處理 !ad channel add <別名> <頻道ID> 指令
                    elif message.lower().startswith('!ad channel add '):
                        parts = message.split()
                        if len(parts) != 5: # !ad channel add <alias> <id>
                            print_error("指令格式錯誤。請使用: !ad channel add <別名> <頻道ID>")
                            continue
                        
                        task_alias = parts[3].lower()
                        channel_id = parts[4]

                        if not channel_id.isdigit():
                            print_error("頻道ID必須是有效的數字。")
                            continue

                        modified = False
                        for config in channel_configs:
                            if config['alias'] == task_alias:
                                if channel_id not in config['channels']:
                                    config['channels'].append(channel_id)
                                    print_success(f"已將頻道 {channel_id} 新增至任務 '{config['name']}'。")
                                else:
                                    print_warning(f"頻道 {channel_id} 已經在任務 '{config['name']}' 中。")
                                modified = True
                                break
                        if not modified:
                            print_error(f"找不到別名為 '{task_alias}' 的任務。")

                    # 處理 !ad channel del <別名> <頻道ID> 指令
                    elif message.lower().startswith('!ad channel del '):
                        parts = message.split()
                        if len(parts) != 5: # !ad channel del <alias> <id>
                            print_error("指令格式錯誤。請使用: !ad channel del <別名> <頻道ID>")
                            continue
                        
                        task_alias = parts[3].lower()
                        channel_id = parts[4]

                        modified = False
                        for config in channel_configs:
                            if config['alias'] == task_alias:
                                if channel_id in config['channels']:
                                    config['channels'].remove(channel_id)
                                    print_success(f"已從任務 '{config['name']}' 移除頻道 {channel_id}。")
                                else:
                                    print_warning(f"在任務 '{config['name']}' 中找不到頻道 {channel_id}。")
                                modified = True
                                break
                        if not modified:
                            print_error(f"找不到別名為 '{task_alias}' 的任務。")

                    # 處理 !ad auth edit <新金鑰> 指令
                    elif message.lower().startswith('!ad auth edit '):
                        parts = message.split(maxsplit=3)
                        if len(parts) < 4:
                            print_error("指令格式錯誤。請使用: !ad auth edit <新金鑰>")
                            continue
                        
                        new_auth_token = parts[3]
                        if authorization_list:
                            authorization_list[0] = new_auth_token
                        else:
                            authorization_list.append(new_auth_token)
                        print_success("Discord 授權金鑰已更新。")

                    # 處理 !ad channel list 指令
                    elif message.lower() == '!ad channel list':
                        print_info("--- 任務頻道列表 ---")
                        if not channel_configs:
                            print_warning("尚未設定任何任務。")
                        else:
                            for config in channel_configs:
                                echo(f"§f任務 '{config['name']}' ({config['alias']}):")
                                if not config['channels']:
                                    print_warning("  - 此任務沒有設定任何頻道。")
                                else:
                                    for channel_id in config['channels']:
                                        print_success(f"  - {channel_id}")
                    
                    # 處理 !ad leave 指令
                    elif message.lower() == '!ad leave':
                        print_warning("正在卸載廣告機器人...")
                        is_script_running = False

                    # 處理 !ad reload 指令
                    elif message.lower() == '!ad reload':
                        print_warning("正在重新載入廣告機器人...")
                        initialize_settings()
                        print_success("機器人已重新載入並重置所有設定。")
                    
                    else:
                        print_error("指令錯誤，請輸入 !ad help 查看可用指令。")

            except queue.Empty:
                pass # 佇列中沒有事件，正常現象

            # --- 計時器處理 (僅在循環啟動時執行) ---
            if is_loop_active:
                current_time = time.time()
                for config in channel_configs:
                    # 如果任務已暫停，則跳過所有處理
                    if config['paused']:
                        continue

                    if current_time >= config["next_send_time"]:
                        print_info(f"'{config['name']}' 的發送時間已到，開始發送訊息...")
                        send_discord_message(config["channels"], authorization_list, context_type=config.get('context_type', 'default'))
                        
                        # 計算並更新下一次的發送時間
                        new_interval = config["get_interval"]()
                        config["next_send_time"] = time.time() + new_interval
                        config["announced_milestones"].clear() # 重置已宣告的倒數時間點
                        print_warning(f"'{config['name']}' 的下次發送將在 {new_interval/60:.2f} 分鐘後。")
                        continue # 處理完畢，跳過此任務的倒數檢查

                    # --- 倒數計時檢查 ---
                    remaining_time = int(config["next_send_time"] - current_time)
                    
                    # 檢查 5 分鐘
                    if remaining_time <= 300 and 300 not in config["announced_milestones"]:
                        print_warning(f"'{config['name']}' 距離下次發送還有 5 分鐘...")
                        config["announced_milestones"].add(300)
                    # 檢查 1 分鐘
                    elif remaining_time <= 60 and 60 not in config["announced_milestones"]:
                        print_warning(f"'{config['name']}' 距離下次發送還有 1 分鐘...")
                        config["announced_milestones"].add(60)
                    # 檢查最後 10 秒
                    elif 1 <= remaining_time <= 10 and remaining_time not in config["announced_milestones"]:
                        print_warning(f"'{config['name']}' 距離下次發送還有 {remaining_time} 秒...")
                        config["announced_milestones"].add(remaining_time)

            time.sleep(1) # 每秒檢查一次，避免 CPU 空轉
        except Exception as e:
            print_error(f"主循環發生錯誤: {e}")
            break
    
    print_info("廣告機器人已成功卸載。")