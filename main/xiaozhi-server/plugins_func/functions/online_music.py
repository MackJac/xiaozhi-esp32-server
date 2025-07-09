import asyncio
import re
import time
import random
import traceback
from typing import Dict, List, Optional
from pathlib import Path
import tempfile

from config.logger import setup_logging
from core.utils import p3
from core.handle.sendAudioHandle import send_stt_message, sendAudioMessage
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

# 导入自定义模块
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "extra" / "music" / "api"))
from music_api import MusicAPI
from music_downloader import MusicDownloader
from favorite_manager import FavoriteManager
from extra.music.online_music_stream import OnlineMusicStreamPlayer

TAG = __name__

# 全局变量
MUSIC_PLAYER = None
CURRENT_PLAYING = None
PLAY_QUEUE = []
PRELOAD_TASK = None

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


class OnlineMusicPlayer:
    """在线音乐播放器"""

    def __init__(self):
        self.music_api = MusicAPI()
        self.downloader = MusicDownloader()
        self.favorite_manager = FavoriteManager()
        self.current_music = None
        self.play_queue = []
        self.preload_task = None
        self.is_playing = False
        self._stream_started = False

    def get_device_id(self, conn) -> str:
        """获取设备ID"""
        # 从连接中获取设备ID，这里需要根据实际情况调整
        return getattr(conn, 'device_id', 'default_device')

    async def search_and_play(self, conn, keywords: str) -> bool:
        """搜索并播放音乐"""
        try:
            device_id = self.get_device_id(conn)

            # 搜索音乐
            music_list = self.music_api.search_music(keywords, device_id)
            if not music_list:
                conn.logger.bind(tag=TAG).warning(f"未找到与'{keywords}'相关的音乐")
                return False

            # 选择最佳匹配的音乐
            best_music = self._select_best_music(music_list, keywords)
            if not best_music:
                conn.logger.bind(tag=TAG).warning("未找到合适的音乐")
                return False

            # 播放音乐
            return await self.play_music(conn, best_music)

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"搜索播放失败: {e}")
            return False

    def _select_best_music(self, music_list: List[Dict], keywords: str) -> Optional[Dict]:
        """选择最佳匹配的音乐"""
        if not music_list:
            return None

        # 优先选择非试听版本
        non_trial_music = [m for m in music_list if not m.get("tryListen", False)]
        if non_trial_music:
            music_list = non_trial_music

        # 优先选择非试听版本，音质等级仅用于显示，不参与排序

        return music_list[0] if music_list else None

    async def play_music(self, conn, music_info: Dict) -> bool:
        """播放音乐"""
        try:
            # 更新当前播放信息
            self.current_music = music_info

            # 发送播放提示
            music_name = music_info.get("name", "未知歌曲")

            # 下载并播放
            music_url = music_info.get("url")
            music_id = music_info.get("id")

            if not music_url or not music_id:
                conn.logger.bind(tag=TAG).error("音乐信息不完整，无法播放")
                return False

            # 检查是否已缓存
            if self.downloader.is_cached(music_id):
                cache_path = self.downloader.get_cache_path(music_id)
                await self._play_local_file(conn, str(cache_path), music_name)
            else:
                # 下载并播放
                await self._download_and_play(conn, music_url, music_id, music_name)

            # 预加载下一首
            await self._preload_next(conn)

            return True

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"播放音乐失败: {e}")
            return False

    async def _download_and_play(self, conn, music_url: str, music_id: str, music_name: str):
        """下载并播放音乐"""
        try:
            self._stream_started = False  # 重置流式播放状态
            # 流式下载并播放，返回最终缓存路径
            cache_path = await self.downloader.stream_download_and_play(
                music_url, music_id,
                lambda chunk, temp_path: self._play_audio_chunk(conn, chunk, temp_path)
            )
            if cache_path:
                await self._play_local_file(conn, cache_path, music_name)
            else:
                conn.logger.bind(tag=TAG).error("下载音乐失败")
        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"下载播放失败: {e}")

    async def _play_local_file(self, conn, file_path: str, music_name: str):
        """播放本地文件"""
        try:
            play_prompt = self._get_play_prompt(music_name)
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=play_prompt,
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.FILE,
                    content_file=file_path,
                )
            )
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"播放本地文件失败: {e}")

    async def _play_audio_chunk(self, conn, chunk: bytes, temp_path: str):
        """播放音频数据块（流式播放）"""
        # 只负责推送TTS，文件写入由downloader负责
        if not self._stream_started:
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.FILE,
                    content_file=temp_path,
                )
            )
            self._stream_started = True

    async def _preload_next(self, conn):
        """预加载下一首音乐"""
        try:
            if self.preload_task and not self.preload_task.done():
                self.preload_task.cancel()

            # 这里可以实现预加载逻辑
            # 比如从播放队列中获取下一首，或者推荐相关音乐
            pass

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"预加载失败: {e}")

    def _get_play_prompt(self, music_name: str) -> str:
        """生成播放提示语"""
        prompts = [
            f"正在为您播放，{music_name}",
            f"请欣赏歌曲，{music_name}",
            f"即将为您播放，{music_name}",
            f"为您带来，{music_name}",
            f"让我们聆听，{music_name}",
        ]
        return random.choice(prompts)

    async def pause_music(self, conn):
        """暂停音乐播放（通过状态标记实现）"""
        self.is_playing = False
        conn.logger.bind(tag=TAG).info("音乐已暂停，等待收藏提示播报")

    async def resume_music(self, conn):
        """恢复音乐播放（通过状态标记实现）"""
        self.is_playing = True
        conn.logger.bind(tag=TAG).info("音乐恢复播放")

    async def add_favorite(self, conn) -> bool:
        """收藏当前播放的音乐"""
        try:
            if not self.current_music:
                conn.logger.bind(tag=TAG).warning("当前没有播放的音乐")
                return False

            device_id = self.get_device_id(conn)
            success = self.favorite_manager.add_favorite(device_id, self.current_music)

            if success:
                music_name = self.current_music.get("name", "未知歌曲")
                await send_stt_message(conn, f"已收藏 {music_name}")
                # 1. 暂停音乐播放
                await self.pause_music(conn)
                # 2. 朗读收藏提示
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.FIRST,
                        content_type=ContentType.ACTION,
                    )
                )
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.MIDDLE,
                        content_type=ContentType.TEXT,
                        content_detail=f"已收藏 {music_name}",
                    )
                )
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.LAST,
                        content_type=ContentType.ACTION,
                    )
                )
                # 3. 等待收藏提示播报完毕后恢复音乐
                await self._wait_tts_queue_empty(conn)
                await self.resume_music(conn)
            else:
                conn.logger.bind(tag=TAG).error("收藏失败")

            return success

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"收藏失败: {e}")
            return False

    async def _wait_tts_queue_empty(self, conn, timeout=10):
        """等待TTS队列清空，表示收藏提示播报完毕"""
        start = time.time()
        while True:
            if conn.tts.tts_text_queue.qsize() == 0:
                break
            if time.time() - start > timeout:
                conn.logger.bind(tag=TAG).warning("等待TTS队列清空超时")
                break
            await asyncio.sleep(0.1)

    async def play_favorites(self, conn, keywords: str = "") -> bool:
        """播放收藏的音乐"""
        try:
            device_id = self.get_device_id(conn)

            if keywords:
                favorites = self.favorite_manager.search_favorites(device_id, keywords)
            else:
                favorites = self.favorite_manager.get_favorites(device_id)

            if not favorites:
                conn.logger.bind(tag=TAG).warning("没有找到收藏的音乐")
                return False

            # 随机选择一首收藏的音乐
            selected_music = random.choice(favorites)
            return await self.play_music(conn, selected_music)

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"播放收藏失败: {e}")
            return False


def get_music_player() -> OnlineMusicPlayer:
    """获取音乐播放器实例"""
    global MUSIC_PLAYER
    if MUSIC_PLAYER is None:
        MUSIC_PLAYER = OnlineMusicPlayer()
    return MUSIC_PLAYER


@register_function("online_music", online_music_function_desc, ToolType.SYSTEM_CTL)
def online_music(conn, action: str, keywords: str = ""):
    """在线音乐播放主函数"""
    try:
        music_player = get_music_player()

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 根据操作类型执行相应功能
        if action == "play":
            if not keywords:
                return ActionResponse(
                    action=Action.RESPONSE, result="参数错误", response="请指定要播放的音乐"
                )

            future = asyncio.run_coroutine_threadsafe(
                music_player.search_and_play(conn, keywords), conn.loop
            )

        elif action == "search":
            if not keywords:
                return ActionResponse(
                    action=Action.RESPONSE, result="参数错误", response="请指定搜索关键词"
                )

            future = asyncio.run_coroutine_threadsafe(
                music_player.search_and_play(conn, keywords), conn.loop
            )

        elif action == "favorite":
            future = asyncio.run_coroutine_threadsafe(
                music_player.add_favorite(conn), conn.loop
            )

        elif action == "play_favorite":
            future = asyncio.run_coroutine_threadsafe(
                music_player.play_favorites(conn, keywords), conn.loop
            )

        else:
            return ActionResponse(
                action=Action.RESPONSE, result="不支持的操作", response="不支持的操作类型"
            )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()
                conn.logger.bind(tag=TAG).info("音乐操作完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"音乐操作失败: {e}")

        future.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在处理您的音乐请求"
        )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理音乐请求错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="处理音乐请求时出错了"
        )


@register_function("favorite_music", favorite_music_function_desc, ToolType.SYSTEM_CTL)
def favorite_music(conn):
    """收藏当前播放的音乐"""
    try:
        music_player = get_music_player()

        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        future = asyncio.run_coroutine_threadsafe(
            music_player.add_favorite(conn), conn.loop
        )

        def handle_done(f):
            try:
                f.result()
                conn.logger.bind(tag=TAG).info("收藏操作完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"收藏操作失败: {e}")

        future.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在处理收藏请求"
        )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"收藏音乐错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="收藏音乐时出错了"
        )


@register_function("next_music", next_music_function_desc, ToolType.SYSTEM_CTL)
def next_music(conn):
    """播放下一首音乐"""
    try:
        music_player = get_music_player()

        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 这里可以实现播放下一首的逻辑
        # 比如从播放队列中获取下一首，或者播放推荐音乐

        return ActionResponse(
            action=Action.RESPONSE, result="功能开发中", response="下一首功能正在开发中"
        )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"下一首音乐错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放下一首时出错了"
        )


@register_function("stop_music", stop_music_function_desc, ToolType.SYSTEM_CTL)
def stop_music(conn):
    """停止播放音乐"""
    try:
        music_player = get_music_player()

        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 这里可以实现停止播放的逻辑
        # 比如清空播放队列，停止当前播放等

        return ActionResponse(
            action=Action.RESPONSE, result="功能开发中", response="停止播放功能正在开发中"
        )

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"停止音乐错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="停止播放时出错了"
        )
