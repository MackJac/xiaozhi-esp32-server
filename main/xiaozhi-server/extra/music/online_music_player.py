import re
import time
import asyncio
import traceback
from typing import Dict, List, Optional
from pathlib import Path
import random
from config.logger import setup_logging
from core.utils import p3
from core.handle.sendAudioHandle import send_stt_message, sendAudioMessage
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from plugins_func.functions.online_music import music_play_success

# 导入自定义模块
from .api.music_api import MusicAPI
from .api.music_downloader import MusicDownloader
from .api.favorite_manager import FavoriteManager

TAG = __name__
logger = setup_logging()

class OnlineMusicPlayer:
    """在线音乐播放器"""

    def __init__(self):
        self.music_api = MusicAPI()
        self.downloader = MusicDownloader()
        self.favorite_manager = FavoriteManager()
        self.current_music = None  # 当前正在处理的音乐
        self.last_played_music = None  # 最后一次播放的音乐，用于跨会话记录
        self.play_queue = []
        self.preload_task = None
        self.is_playing = False
        self._stream_started = False
        self.last_command_was_play = False  # 记录上一次指令是否是播放音乐

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

        return music_list[0] if music_list else None

    async def play_music(self, conn, music_info: Dict) -> bool:
        """播放音乐"""
        try:
            # 标记这次指令是播放音乐
            self.last_command_was_play = True
            # 更新当前播放信息
            self.current_music = music_info
            # 记录最后一次播放的音乐
            self.last_played_music = music_info

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
            global music_play_success
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

            # 播放成功
            music_play_success = True

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"播放本地文件失败: {e}")

    async def _play_audio_chunk(self, conn, chunk: bytes, temp_path: str):
        """播放音频数据块（流式播放）"""
        # 只负责推送TTS，文件写入由downloader负责
        global music_play_success
        # 播放成功
        music_play_success = True

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
            f"为您播放，{music_name}",
            f"请欣赏歌曲，{music_name}",
            f"为您带来，{music_name}",
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
            # 检查上一次指令是否是播放音乐
            if not self.last_command_was_play:
                conn.logger.bind(tag=TAG).warning("只能收藏刚刚播放的音乐")
                await send_stt_message(conn, "只能收藏刚刚播放的音乐")
                return False

            if not self.current_music:
                conn.logger.bind(tag=TAG).warning("没有可收藏的音乐")
                return False

            device_id = self.get_device_id(conn)
            success = self.favorite_manager.add_favorite(device_id, self.current_music)

            if success:
                music_name = self.current_music.get("name", "未知歌曲")
                await send_stt_message(conn, f"已收藏{music_name}")

                # 播放收藏成功提示
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
                        content_detail=f"已收藏{music_name}",
                    )
                )
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.LAST,
                        content_type=ContentType.ACTION,
                    )
                )

                # 重新播放音乐
                await self.play_music(conn, self.current_music)

            return success

        except Exception as e:
            conn.logger.bind(tag=TAG).error(f"收藏音乐失败: {e}")
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

    # 添加一个方法来重置上一次指令的标记
    def reset_last_command(self):
        """重置上一次指令的标记"""
        self.last_command_was_play = False

# 单例模式
_instance = None

def get_music_player() -> OnlineMusicPlayer:
    """获取音乐播放器实例（单例模式）"""
    global _instance
    if _instance is None:
        _instance = OnlineMusicPlayer()
    return _instance
