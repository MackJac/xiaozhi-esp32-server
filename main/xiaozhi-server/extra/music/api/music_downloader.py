import os
import asyncio
import aiohttp
import aiofiles
import tempfile
import shutil
from typing import Optional, Callable
from pathlib import Path
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MusicDownloader:
    """音乐下载器，支持边下载边播放"""

    def __init__(self, cache_dir: str = "./data/music_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.downloading_tasks = {}  # 记录正在下载的任务

    def get_cache_path(self, music_id: str) -> Path:
        """获取音乐缓存路径"""
        return self.cache_dir / f"{music_id}.mp3"

    def is_cached(self, music_id: str) -> bool:
        """检查音乐是否已缓存"""
        cache_path = self.get_cache_path(music_id)
        return cache_path.exists()

    async def download_music(self, music_url: str, music_id: str,
                           progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        下载音乐文件

        Args:
            music_url: 音乐文件URL
            music_id: 音乐ID
            progress_callback: 进度回调函数

        Returns:
            成功返回本地文件路径，失败返回None
        """
        cache_path = self.get_cache_path(music_id)

        # 如果已经缓存，直接返回
        if cache_path.exists():
            logger.bind(tag=TAG).info(f"音乐已缓存: {music_id}")
            return str(cache_path)

        # 如果正在下载，等待下载完成
        if music_id in self.downloading_tasks:
            logger.bind(tag=TAG).info(f"等待音乐下载完成: {music_id}")
            try:
                return await self.downloading_tasks[music_id]
            except Exception as e:
                logger.bind(tag=TAG).error(f"等待下载失败: {e}")
                return None

        # 开始下载
        download_task = asyncio.create_task(
            self._download_file(music_url, cache_path, progress_callback)
        )
        self.downloading_tasks[music_id] = download_task

        try:
            result = await download_task
            return result
        except Exception as e:
            logger.bind(tag=TAG).error(f"下载音乐失败: {e}")
            return None
        finally:
            # 清理下载任务记录
            self.downloading_tasks.pop(music_id, None)

    async def _download_file(self, url: str, file_path: Path,
                           progress_callback: Optional[Callable] = None) -> Optional[str]:
        """实际下载文件"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.bind(tag=TAG).error(f"下载失败，状态码: {response.status}")
                        return None

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0

                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                            downloaded_size += len(chunk)

                            # 调用进度回调
                            if progress_callback and total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                await progress_callback(progress)

            logger.bind(tag=TAG).info(f"音乐下载完成: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.bind(tag=TAG).error(f"下载文件时发生错误: {e}")
            # 删除可能部分下载的文件
            if file_path.exists():
                file_path.unlink()
            return None

    async def stream_download_and_play(self, music_url: str, music_id: str, play_callback: Callable) -> Optional[str]:
        """
        流式下载并播放（边下载边播放），下载完成后缓存到正式目录
        Returns: 成功返回正式缓存路径，失败返回None
        """
        temp_fd, temp_path = tempfile.mkstemp(suffix=".opus", prefix=f"stream_{music_id}_")
        os.close(temp_fd)  # 用aiofiles写，不用fd
        success = False
        try:
            logger.bind(tag=TAG).info(f"流式下载开始")
            async with aiohttp.ClientSession() as session:
                async with session.get(music_url) as response:
                    if response.status != 200:
                        logger.bind(tag=TAG).error(f"流式下载失败，状态码: {response.status}")
                        return None
                    async with aiofiles.open(temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                            await play_callback(chunk, temp_path)
            success = True
        except Exception as e:
            logger.bind(tag=TAG).error(f"流式下载播放失败: {e}")
        if success:
            cache_path = self.get_cache_path(music_id)
            shutil.move(temp_path, cache_path)
            logger.bind(tag=TAG).info(f"流式下载播放完成并缓存: {cache_path}")
            return str(cache_path)
        else:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return None

    def clear_cache(self, music_id: Optional[str] = None):
        """清理缓存"""
        if music_id:
            cache_path = self.get_cache_path(music_id)
            if cache_path.exists():
                cache_path.unlink()
                logger.bind(tag=TAG).info(f"清理音乐缓存: {music_id}")
        else:
            # 清理所有缓存
            for cache_file in self.cache_dir.glob("*.mp3"):
                cache_file.unlink()
            logger.bind(tag=TAG).info("清理所有音乐缓存")

    def get_cache_size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.mp3"):
            total_size += cache_file.stat().st_size
        return total_size
