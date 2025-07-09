import asyncio
from typing import Optional, Dict, Any, List

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from extra.music import get_music_player

logger = setup_logging()

TAG = __name__

# 全局变量：记录上一次function call是否是播放音乐
last_function_was_play_music = False
# 全局变量：记录音乐是否成功播放
music_play_success = False

online_music_function_desc = {
    "type": "function",
    "function": {
        "name": "online_music",
        "description": "播放在线音乐、搜索音乐、收藏音乐的方法。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型：play(播放)、search(搜索)、favorite(收藏)、play_favorite(播放收藏)、next(下一首)、stop(停止)",
                    "enum": ["play", "search", "favorite", "play_favorite", "next", "stop"]
                },
                "keywords": {
                    "type": "string",
                    "description": "搜索关键词或歌曲名称，当action为play、search、play_favorite时必填"
                }
            },
            "required": ["action"],
        },
    },
}

favorite_music_function_desc = {
    "type": "function",
    "function": {
        "name": "favorite_music",
        "description": "收藏当前播放的音乐。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

next_music_function_desc = {
    "type": "function",
    "function": {
        "name": "next_music",
        "description": "播放下一首音乐。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

stop_music_function_desc = {
    "type": "function",
    "function": {
        "name": "stop_music",
        "description": "停止播放音乐。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

@register_function("online_music", online_music_function_desc, ToolType.SYSTEM_CTL)
def online_music(conn, action: str, keywords: str = ""):
    """在线音乐功能入口"""
    try:
        global last_function_was_play_music
        player = get_music_player()

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(action=Action.RESPONSE, result="系统繁忙", response="请稍后再试")

        if action == "play":
            if not keywords:
                return ActionResponse(Action.RESPONSE, False, "请提供要播放的音乐名称")

            # 创建异步任务
            task = asyncio.run_coroutine_threadsafe(player.search_and_play(conn, keywords), conn.loop)
            task.add_done_callback(handle_done)
            # 标记这次是播放音乐的指令
            last_function_was_play_music = True

        elif action == "favorite":
            # 检查上一次指令是否是播放音乐且播放成功
            if not (last_function_was_play_music and music_play_success):
                conn.logger.bind(tag=TAG).warning("没有音乐可以收藏")
                return ActionResponse(Action.RESPONSE, False, "没有音乐可以收藏")

            task = asyncio.run_coroutine_threadsafe(player.add_favorite(conn), conn.loop)
            task.add_done_callback(handle_done)

        elif action == "play_favorite":
            task = asyncio.run_coroutine_threadsafe(player.play_favorites(conn, keywords), conn.loop)
            task.add_done_callback(handle_done)
            # 标记这次是播放音乐的指令
            last_function_was_play_music = True

        elif action == "next":
            task = asyncio.run_coroutine_threadsafe(player.next_music(conn), conn.loop)
            task.add_done_callback(handle_done)

        elif action == "stop":
            task = asyncio.run_coroutine_threadsafe(player.stop_music(conn), conn.loop)
            task.add_done_callback(handle_done)

        else:
            return ActionResponse(Action.RESPONSE, False, f"不支持的操作类型: {action}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"在线音乐功能异常: {e}")
        return ActionResponse(Action.ERROR, False, str(e))

@register_function("favorite_music", favorite_music_function_desc, ToolType.SYSTEM_CTL)
def favorite_music(conn):
    """收藏当前播放的音乐"""
    try:
        # 检查上一次指令是否是播放音乐且播放成功
        if not (last_function_was_play_music and music_play_success):
            conn.logger.bind(tag=TAG).warning("没有音乐可以收藏")
            return ActionResponse(Action.RESPONSE, False, "没有音乐可以收藏")

        player = get_music_player()
        task = asyncio.run_coroutine_threadsafe(player.add_favorite(conn), conn.loop)
        task.add_done_callback(handle_done)

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"收藏音乐异常: {e}")
        return ActionResponse(Action.ERROR, False, str(e))

@register_function("next_music", next_music_function_desc, ToolType.SYSTEM_CTL)
def next_music(conn):
    """播放下一首音乐"""
    try:
        player = get_music_player()
        task = asyncio.run_coroutine_threadsafe(player.next_music(conn), conn.loop)
        task.add_done_callback(handle_done)

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放下一首异常: {e}")
        return ActionResponse(Action.ERROR, False, str(e))

@register_function("stop_music", stop_music_function_desc, ToolType.SYSTEM_CTL)
def stop_music(conn):
    """停止播放音乐"""
    try:
        player = get_music_player()
        task = asyncio.run_coroutine_threadsafe(player.stop_music(conn), conn.loop)
        task.add_done_callback(handle_done)

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"停止播放异常: {e}")
        return ActionResponse(Action.ERROR, False, str(e))

def handle_done(f):
    """异步任务完成回调"""
    try:
        f.result()
    except Exception as e:
        logger.bind(tag=TAG).error(f"音乐任务异常: {e}")
