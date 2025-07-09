import requests
import json
from typing import Dict, List, Optional
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


class MusicAPI:
    """音乐API接口封装"""

    def __init__(self, base_url: str = "http://host.docker.internal:3000"):
        self.base_url = base_url
        self.search_endpoint = f"{base_url}/platform/musicSearch"

    def search_music(self, keywords: str, device_id: str) -> Optional[List[Dict]]:
        """
        搜索音乐

        Args:
            keywords: 搜索关键词
            device_id: 设备ID

        Returns:
            成功返回音乐列表，失败返回None
        """
        try:
            headers = {
                "Device-Id": device_id,
                "Content-Type": "application/json"
            }

            params = {
                "keywords": keywords
            }

            logger.bind(tag=TAG).info(f"搜索音乐: {keywords}")

            response = requests.get(
                self.search_endpoint,
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    music_data = data.get("data", {})
                    if music_data:
                        # 构造音乐信息
                        music_info = {
                            "id": music_data.get("id"),
                            "name": music_data.get("name"),
                            "url": music_data.get("url", ""),
                            "tryListen": music_data.get("tryListen", False),
                            "duration": music_data.get("duration", 0)
                        }
                        logger.bind(tag=TAG).info(f"解析音乐信息: {music_info}")
                        return [music_info]  # 返回列表格式以保持兼容性
                    else:
                        logger.bind(tag=TAG).warning("API返回数据为空")
                        return None
                else:
                    logger.bind(tag=TAG).error(f"API返回错误: {data.get('message', '未知错误')}")
                    return None
            else:
                logger.bind(tag=TAG).error(f"HTTP请求失败: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logger.bind(tag=TAG).error(f"网络请求异常: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.bind(tag=TAG).error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.bind(tag=TAG).error(f"搜索音乐时发生未知错误: {e}")
            return None

    def get_music_info(self, music_data: Dict) -> Dict:
        """
        解析音乐信息

        Args:
            music_data: API返回的音乐数据

        Returns:
            标准化的音乐信息
        """
        return {
            "id": music_data.get("id"),
            "name": music_data.get("name", ""),
            "sq": music_data.get("sq", ""),  # 音质等级（字符串，仅用于显示）
            "url": music_data.get("url", ""),
            "try_listen": music_data.get("tryListen", False),  # 是否是试听
            "duration": music_data.get("duration", 0)  # 歌曲时长
        }
